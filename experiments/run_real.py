"""全链路真实数据驱动：candgen JSONL → embedding-3 → engine(observe/retrieve/step)。

因果时间线：t = unit index。window w 的候选在 t = w.end_unit_id+1 才 observe
（该窗所有 unit 结束之后），unit i 的 user_text 在 t=i 检索——无前窥。

真实数据没有 ground truth：
- judge = verbatim 规则 + 人工标注文件（--labels）；未标注 pair 留 tension backlog。
- relevant() 恒 True，故信用记账等价 selected-hit（cfg.useful_hit=False 如实声明）。
- 召回率无真值不可测；输出 hit-rate、sim 分布、池水位、控制事件、backlog。

用法：
    python -m experiments.run_real --allow-remote   # 首次（写向量缓存）
    python -m experiments.run_real --offline        # 复跑不联网
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from experiments import paths as P
from experiments.real_embedding import load_dotenv_key
from hybrid_memory.candgen import priority_to_salience, redact_secrets
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Pool, Query
from hybrid_memory.datasets.real_chat import (build_interaction_windows,
                                              load_interaction_units)
from hybrid_memory.embed.base import cosine
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder
from hybrid_memory.semantics import RealChatSemantics, normalize
from hybrid_memory.worker import SignalWorker

DATA = P.DATA_REAL
CANDGEN = P.CANDGEN_DIR / "real-candgen-k3-s3.jsonl"
DOTENV = Path(".env")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--candgen", type=Path, default=CANDGEN)
    ap.add_argument("--labels", type=Path, default=P.QA / "tension_labels.jsonl")
    ap.add_argument("--dotenv", type=Path, default=DOTENV)
    ap.add_argument("--theta", type=float, default=0.35)
    ap.add_argument("--cap-m", type=int, default=8)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--tau-dup", type=float, default=0.90)
    ap.add_argument("--tau-sim", type=float, default=0.80)
    ap.add_argument("--allow-remote", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out-prefix", default="real-run-k3-s3")
    args = ap.parse_args()
    if args.allow_remote == args.offline:
        raise SystemExit("choose exactly one of --allow-remote or --offline")

    units = load_interaction_units(args.data)
    windows = build_interaction_windows(units, size=3, stride=3)
    candgen = {}
    n_redacted = 0
    for line in args.candgen.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if "error" in rec:
            continue
        cands = []
        for t_ in rec["candidates"]:
            raw = t_["text"] if isinstance(t_, dict) else t_
            rt = redact_secrets(raw)
            n_redacted += int(rt != raw)
            sal = t_.get("salience") if isinstance(t_, dict) else None
            if isinstance(sal, bool) or not isinstance(sal, (int, float)):
                sal = priority_to_salience(
                    t_.get("priority") if isinstance(t_, dict) else None)
            else:
                sal = max(0.0, min(1.0, float(sal)))
            cands.append({"text": rt, "salience": sal,
                          "scene": str(rec.get("scene_name", ""))})
        candgen[rec["window_id"]] = cands

    api_key = None if args.offline else load_dotenv_key(args.dotenv)
    emb = ZhipuEmbedder(api_key=api_key, cache=SqliteEmbeddingCache(
        P.EMB_CACHE), offline=args.offline)
    semantics = RealChatSemantics(args.labels)
    cfg = Cfg(theta=args.theta, cap_m=args.cap_m, k=args.k,
              tau_dup=args.tau_dup, tau_sim=args.tau_sim,
              useful_hit=False)   # 真实数据无 recognizer：selected-hit 记账
    eng = MemoryEngine(cfg, emb, semantics)
    worker = SignalWorker(eng, semantics)   # 标注文件裁决走信号通路

    by_avail: dict[int, list] = {}
    for w in windows:
        if w.id in candgen:
            by_avail.setdefault(w.end_unit_id + 1, []).append(w)

    prompt_tokens = 0
    rows = []
    t0 = time.time()
    for t in range(len(units)):
        for w in by_avail.get(t, []):
            events = [Event(semantics.fingerprint(c["text"]),
                            normalize(c["text"]), c["text"],
                            salience=c["salience"], scene=c["scene"])
                      for c in candgen[w.id]]
            eng.observe(events, t)
            prompt_tokens += emb.last_prompt_tokens
        qv = emb.embed([units[t].user_text])[0]
        prompt_tokens += emb.last_prompt_tokens
        ret = eng.retrieve(qv, Query(-1, units[t].user_text), t)
        pools = eng.pool_sizes()
        top_sim = max((cosine(qv, m.emb) for m in eng.mems.values()),
                      default=0.0)
        rows.append({"t": t, "unit_id": units[t].id,
                     "n_selected": len(ret.selected),
                     "n_shortlisted": ret.n_shortlisted,
                     "n_suppressed": len(ret.suppressed),
                     "top_sim": round(top_sim, 4),
                     "C": pools["C"], "M": pools["M"], "A": pools["A"]})
        eng.step(t)
        worker.process(t)

    # 未消解 tension → 人类工作清单
    review_path = P.QA / "tensions_review.jsonl"
    with review_path.open("w", encoding="utf-8") as f:
        for key, tn in eng.tensions.items():
            a, b = eng.mems.get(tn.left), eng.mems.get(tn.right)
            if a is None or b is None:
                continue
            f.write(json.dumps({
                "left_id": a.id, "right_id": b.id,
                "left_text": a.text, "right_text": b.text,
                "sim": round(float(cosine(a.emb, b.emb)), 4),
                "observations": tn.observations,
            }, ensure_ascii=False) + "\n")

    # 终态记忆清单（脱敏后文本）
    mems_path = P.RUNS / f"{args.out_prefix}-memories.jsonl"
    with mems_path.open("w", encoding="utf-8") as f:
        for m in eng.mems.values():
            f.write(json.dumps({
                "id": m.id, "pool": m.pool.value, "v": round(m.v, 3),
                "evid": m.evid, "hits": m.hits, "shadow": m.shadow_hits,
                "salience": round(m.salience, 3),
                "novelty": round(m.novelty, 3),
                "kind": m.kind, "derived_from": list(m.derived_from),
                "scene": m.scene,
                "conf_pos": round(m.conf_pos, 3),
                "conf_neg": round(m.conf_neg, 3),
                "birth": m.birth, "last_hit": m.last_hit, "text": m.text,
            }, ensure_ascii=False) + "\n")

    traj_path = P.RUNS / f"{args.out_prefix}-trajectory.csv"
    with traj_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    top_sims = [r["top_sim"] for r in rows]
    hits = [r["n_selected"] for r in rows]
    summary = {
        "units": len(units), "windows_injected": len(candgen),
        "candidates_total": sum(len(v) for v in candgen.values()),
        "secrets_redacted": n_redacted,
        "prompt_tokens": prompt_tokens,
        "elapsed_s": round(time.time() - t0, 1),
        "cfg": {"theta": args.theta, "cap_m": args.cap_m, "k": args.k,
                "tau_dup": args.tau_dup, "tau_sim": args.tau_sim,
                "useful_hit": False},
        "hit_rate": round(sum(1 for h in hits if h > 0) / len(hits), 4),
        "mean_selected": round(float(np.mean(hits)), 3),
        "top_sim_p10": round(float(np.percentile(top_sims, 10)), 4),
        "top_sim_p50": round(float(np.percentile(top_sims, 50)), 4),
        "top_sim_p90": round(float(np.percentile(top_sims, 90)), 4),
        "pool_final": eng.pool_sizes(),
        "tensions_pending": len(eng.tensions),
        "events": {k: getattr(eng, k) for k in
                   ("n_promote", "n_demote", "n_evict", "n_archive",
                    "n_revive", "n_merge", "n_collision", "n_tension",
                    "n_resolve", "n_consolidate")},
        "labels_loaded": len(semantics.labels),
    }
    (P.RUNS / f"{args.out_prefix}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
