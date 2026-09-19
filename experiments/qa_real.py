"""真实日志 QA 评测：从原始 l0 日志出的题，在因果回放的指定时点就地提问。

与 run_bench 的区别：问题不在流尾集中提，而是每个问题挂 ask_at（unit index），
在回放到该时点时用当时的引擎状态 retrieve → reader → judge。问题的检索命中
同样走 step() 记账，信用回路被真实使用。

用法：
    python -m experiments.qa_real --allow-remote
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiments import paths as P
from experiments.dynamics_v3 import FEATURE_SETS, configure, diagnostics
from experiments.real_embedding import load_dotenv_key
from experiments.run_bench import JUDGE_SYS, _judge_answer
from hybrid_memory.candgen import priority_to_salience, redact_secrets
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Query
from hybrid_memory.datasets.real_chat import (build_interaction_windows,
                                              load_interaction_units)
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder
from hybrid_memory.llm import chat
from hybrid_memory.semantics import RealChatSemantics, normalize
from hybrid_memory.semantics.llm import LLMSemantics
from hybrid_memory.semantics.opencode import OpencodeSemantics

DATA = P.DATA_REAL
CANDGEN = P.CANDGEN_DIR / "real-candgen-k3-s3-v2.jsonl"
QUESTIONS = Path("data/bench/real-qa.jsonl")
DOTENV = Path(".env")

READER_SYS = ("你在根据长期记忆回答问题。只依据给出的记忆条目作答。"
              "标为[未确认]的条目只能作为线索，不得作为确定结论；"
              "未决冲突必须同时说明版本与时间，不得擅自裁决。"
              "用中文简洁回答；记忆里没有答案就回答“不知道”。")


def _load_candgen(path: Path) -> dict[int, list[dict]]:
    candgen: dict[int, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if "error" in rec:
            continue
        cands = []
        for c in rec["candidates"]:
            sal = c.get("salience")
            if isinstance(sal, bool) or not isinstance(sal, (int, float)):
                sal = priority_to_salience(c.get("priority"))
            else:
                sal = max(0.0, min(1.0, float(sal)))
            cands.append({"text": redact_secrets(c["text"]),
                          "src": tuple(c.get("source_unit_ids") or ()),
                          "salience": sal,
                          "scene": str(rec.get("scene_name", ""))})
        candgen[rec["window_id"]] = cands
    return candgen


def _load_questions(path: Path) -> list[dict]:
    qs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            qs.append(json.loads(line))
    return qs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--candgen", type=Path, default=CANDGEN)
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--labels", type=Path, default=P.QA / "tension_labels.jsonl")
    ap.add_argument("--dotenv", type=Path, default=DOTENV)
    ap.add_argument("--theta", type=float, default=0.35)
    ap.add_argument("--cap-m", type=int, default=8)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--tau-dup", type=float, default=0.85)
    ap.add_argument("--tau-sim", type=float, default=0.78)
    ap.add_argument("--reader-model", default="glm-5.3-flash")
    ap.add_argument("--no-reader", action="store_true")
    ap.add_argument("--llm-judge", action="store_true",
                    help="tension 裁决走 LLM（RealChatSemantics→LLMSemantics）")
    ap.add_argument("--opencode", action="store_true",
                    help="LLM 裁判走 opencode agent 壳（需 --llm-judge）")
    ap.add_argument("--opencode-model", default="zhipu-env/glm-5.3-flash",
                    help="opencode 侧模型（provider/model 格式）")
    ap.add_argument("--opencode-strict", action="store_true",
                    help="opencode 裁判失败即中止（默认降级并计数）")
    ap.add_argument("--feedback", action="store_true",
                    help="延迟记账：recognizer 按回答判 useful-hit")
    ap.add_argument("--feature-set", choices=tuple(FEATURE_SETS), default="p01")
    ap.add_argument("--allow-remote", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out-prefix", default="qa-real")
    args = ap.parse_args()
    if args.allow_remote == args.offline:
        raise SystemExit("choose exactly one of --allow-remote or --offline")
    if args.feature_set == "r1234_full" and not args.llm_judge:
        raise SystemExit("r1234_full requires --llm-judge for consolidation")
    if args.feedback and not args.llm_judge:
        raise SystemExit(
            "--feedback requires --llm-judge（否则 recognizer 缺失，"
            "静默退化为 selected-hit 全记，strict 记账失效）")
    if args.opencode and not args.llm_judge:
        raise SystemExit("--opencode requires --llm-judge")
    if args.opencode and args.offline:
        raise SystemExit("--opencode 无法离线运行（CLI 需要远端）")

    units = load_interaction_units(args.data)
    windows = build_interaction_windows(units, size=3, stride=3)
    candgen = _load_candgen(args.candgen)
    questions = _load_questions(args.questions)

    key = None if args.offline else load_dotenv_key(args.dotenv)
    emb = ZhipuEmbedder(api_key=key, cache=SqliteEmbeddingCache(
        P.EMB_CACHE), offline=args.offline)
    if args.llm_judge and args.opencode:
        semantics = OpencodeSemantics(
            args.labels, model=args.opencode_model, cache_dir=P.CHAT_CACHE,
            env_extra={"ZAI_API_KEY": key}, strict=args.opencode_strict)
    elif args.llm_judge:
        semantics = LLMSemantics(args.labels, model=args.reader_model,
                                 cache_dir=P.CHAT_CACHE, api_key=key)
    else:
        semantics = RealChatSemantics(args.labels)
    cfg = configure(
        Cfg(theta=args.theta, cap_m=args.cap_m, k=args.k,
            tau_dup=args.tau_dup, tau_sim=args.tau_sim,
            useful_hit=args.feedback, defer_credit=args.feedback),
        args.feature_set)
    eng = MemoryEngine(cfg, emb, semantics)

    by_avail: dict[int, list] = defaultdict(list)
    for w in windows:
        if w.id in candgen:
            by_avail[w.end_unit_id + 1].append(w.id)
    by_ask: dict[int, list] = defaultdict(list)
    for q in questions:
        by_ask[q["ask_at"]].append(q)

    def _observe(wid: int, t: int) -> None:
        evs = [Event(eng.semantics.fingerprint(normalize(c["text"])),
                     normalize(c["text"]), c["text"], c["src"],
                     salience=c["salience"], scene=c["scene"])
               for c in candgen[wid]]
        eng.observe(evs, t)

    def _answer(q: dict, t: int) -> dict:
        qv = emb.embed([q["question"]])[0]
        ret = eng.retrieve(qv, Query(-1, q["question"]), t)
        prov_ids = {m.id for m in ret.provisional}
        lines = [f"- {'[未确认] ' if m.id in prov_ids else ''}"
                 f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
                 f"[t={m.birth}] {m.text}" for m in ret.selected]
        for m, rival in ret.contested:
            lines.append(f"- ⚠️未决冲突：[t={rival.birth}] {rival.text}"
                         f"（与上述 t={m.birth} 条目冲突，未经裁决）")
        pred = None
        if not args.no_reader and lines:
            pred = chat(api_key=key, model=args.reader_model,
                        system=READER_SYS,
                        user="记忆：\n" + "\n".join(lines)
                             + f"\n\n问题：{q['question']}",
                        cache_dir=P.CHAT_CACHE)
        if args.feedback and pred is not None:
            n_fb = eng.feedback(ret, q["question"], pred, t)
        else:
            n_fb = None
        ev_set = frozenset(q["evidence_units"])
        covered = frozenset().union(*(m.src for m in ret.selected)) \
            & ev_set if ret.selected else frozenset()
        correct = _judge_answer(q["question"], q["gold"], pred, key,
                                args.reader_model,
                                cache_dir=P.CHAT_CACHE) \
            if not args.no_reader else None
        return {"qid": q["qid"], "ask_at": t, "qtype": q["qtype"],
                "n_mem": len(ret.selected), "n_contested": len(ret.contested),
                "n_provisional": len(ret.provisional),
                "n_reflection": sum(m.kind == "reflection" for m in ret.selected),
                "n_useful": n_fb,
                "pred": pred, "correct": correct,
                "evidence_recall": (len(covered) / len(ev_set)
                                    if ev_set else None),
                "pools": eng.pool_sizes()}

    results = []
    t0 = time.time()
    for t in range(len(units)):
        for wid in by_avail.get(t, []):
            _observe(wid, t)
        qv = emb.embed([units[t].user_text])[0]
        ret_u = eng.retrieve(qv, Query(-1, units[t].user_text), t)
        if args.feedback:
            # 真实 log 自带的 assistant 回复 = 隐式回答，喂 recognizer 记 useful-hit
            eng.feedback(ret_u, units[t].user_text,
                         units[t].assistant_text, t)
        for q in by_ask.get(t, []):
            r = _answer(q, t)
            results.append(r)
            print(f"[t={t}] {q['qid']} ({q['qtype']}) n_mem={r['n_mem']} "
                  f"ev={r['evidence_recall']} correct={r['correct']}")
        eng.step(t)
    # ask_at 超出流尾的问题：流末补注后用终态回答
    for tt in sorted(k for k in by_avail if k >= len(units)):
        for wid in by_avail[tt]:
            _observe(wid, len(units))
    eng.step(len(units))
    for tt in sorted(k for k in by_ask if k >= len(units)):
        for q in by_ask[tt]:
            r = _answer(q, tt)
            results.append(r)
            print(f"[t={tt}*] {q['qid']} ({q['qtype']}) n_mem={r['n_mem']} "
                  f"ev={r['evidence_recall']} correct={r['correct']}")

    by_type: dict[str, list] = defaultdict(list)
    for r in results:
        if r["correct"] is not None:
            by_type[r["qtype"]].append(int(r["correct"]))
    scored = [r for r in results if r["correct"] is not None]
    summary = {
        "questions": len(results),
        "acc": round(float(np.mean([r["correct"] for r in scored])), 4)
               if scored else None,
        "acc_by_type": {k: round(float(np.mean(v)), 4)
                        for k, v in sorted(by_type.items())},
        "evidence_recall_mean": round(float(np.mean(
            [r["evidence_recall"] for r in results
             if r["evidence_recall"] is not None])), 4)
            if any(r["evidence_recall"] is not None for r in results) else None,
        "no_hit": sum(1 for r in results if r["n_mem"] == 0),
        "pool_final": eng.pool_sizes(),
        "memory_diagnostics": diagnostics(eng),
        "elapsed_s": round(time.time() - t0, 1),
        "feature_set": args.feature_set,
        "features": list(FEATURE_SETS[args.feature_set]),
        "opencode": {"enabled": bool(args.opencode),
                     "failed": getattr(semantics, "n_failed", 0)},
        "cfg": {"theta": args.theta, "cap_m": args.cap_m, "k": args.k,
                "tau_dup": args.tau_dup, "tau_sim": args.tau_sim},
    }
    out = P.QA / f"{args.out_prefix}-summary.json"
    out.write_text(json.dumps({"summary": summary, "results": results},
                              ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    n_failed = getattr(semantics, "n_failed", 0)
    if n_failed:
        print(f"⚠ opencode 裁判失败 {n_failed} 次（已走降级路径）——"
              f"本轮结果不可用于质量对比", flush=True)


if __name__ == "__main__":
    main()
