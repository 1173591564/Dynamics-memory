"""分解诊断：评测点上"要点覆盖率"在 全池 vs top-5 vs pred 三层的落差。

复用 qa_continuity 的回放逻辑（全部走缓存），在每个 eval 点 dump：
  - top-5 ctx（selected）
  - 全部活跃记忆文本（C+M，排除 archive/superseded/aggregated）
然后由 rejudge_kp 的判定器对各层做要点覆盖判定。

用法：python -m experiments.pool_cov --allow-remote --feature-set p01
"""
from __future__ import annotations

import argparse
import io
import json
import time
from collections import defaultdict
from pathlib import Path

from experiments import paths as P
from experiments.dynamics_v3 import FEATURE_SETS, configure
from experiments.qa_real import _load_candgen
from experiments.qa_continuity import (_pick_eval_points, _unit_text,
                                       DATA, CANDGEN, CHAT_CACHE, DOTENV)
from experiments.real_embedding import load_dotenv_key
from experiments.rejudge_kp import _extract_kps, _judge_kp, _hit
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Pool, Query
from hybrid_memory.datasets.real_chat import (build_interaction_windows,
                                              load_interaction_units)
from hybrid_memory.embed.base import cosine
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder
from hybrid_memory.llm import chat
from hybrid_memory.semantics import RealChatSemantics, normalize
from hybrid_memory.semantics.llm import LLMSemantics
from hybrid_memory.semantics.opencode import OpencodeSemantics
from hybrid_memory.worker import SignalWorker

READER_SYS = ("你在协助一个进行中的工程项目。根据给出的记忆回答问题。"
              "标为[未确认]的条目只能作为线索，不得作为确定结论；"
              "未决冲突必须同时说明版本与时间，不得擅自裁决。"
              "不知道的事不要编造，可以说不确定。用中文简洁回答。")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-set", default="p01")
    ap.add_argument("--out-prefix", default="poolcov")
    ap.add_argument("--candgen", type=Path, default=CANDGEN)
    ap.add_argument("--size", type=int, default=3, help="窗口大小（须与 candgen 一致）")
    ap.add_argument("--stride", type=int, default=3, help="窗口步长（须与 candgen 一致）")
    ap.add_argument("--lex-weight", type=float, default=0.0)
    ap.add_argument("--opencode", action="store_true",
                    help="LLM 裁判走 opencode agent 壳")
    ap.add_argument("--opencode-strict", action="store_true",
                    help="opencode 裁判失败即中止（默认降级并计数）")
    ap.add_argument("--allow-remote", action="store_true")
    args = ap.parse_args()

    key = load_dotenv_key(DOTENV)
    units = load_interaction_units(DATA)
    windows = build_interaction_windows(units, size=args.size,
                                        stride=args.stride)
    candgen = _load_candgen(args.candgen)
    eval_pts = _pick_eval_points(units, 25, 5)

    emb = ZhipuEmbedder(api_key=key, cache=SqliteEmbeddingCache(P.EMB_CACHE),
                        offline=False)
    if args.opencode:
        semantics = OpencodeSemantics(
            P.QA / "tension_labels.jsonl", cache_dir=CHAT_CACHE,
            env_extra={"ZAI_API_KEY": key}, strict=args.opencode_strict)
    else:
        semantics = LLMSemantics(P.QA / "tension_labels.jsonl",
                                 model="glm-5.3-flash",
                                 cache_dir=CHAT_CACHE, api_key=key)
    cfg = configure(Cfg(theta=0.35, cap_m=8, k=5,
                        tau_dup=0.85, tau_sim=0.78,
                        lex_weight=args.lex_weight,
                        useful_hit=True, defer_credit=True),
                    args.feature_set)
    eng = MemoryEngine(cfg, emb, semantics)
    worker = SignalWorker(eng, semantics)

    by_avail = defaultdict(list)
    for w in windows:
        if w.id in candgen:
            by_avail[w.end_unit_id + 1].append(w.id)

    def _observe(wid, t):
        evs = [Event(eng.semantics.fingerprint(normalize(c["text"])),
                     normalize(c["text"]), c["text"], c["src"],
                     salience=c["salience"], scene=c["scene"])
               for c in candgen[wid]]
        eng.observe(evs, t)

    dumps = []
    t0 = time.time()
    for t in range(len(units)):
        for wid in by_avail.get(t, []):
            _observe(wid, t)
        qv = emb.embed([units[t].user_text])[0]
        ret = eng.retrieve(qv, Query(-1, units[t].user_text), t)
        pred_mem = None
        if t in eval_pts:
            prov_ids = {m.id for m in ret.provisional}
            lines = [f"- {'[未确认] ' if m.id in prov_ids else ''}"
                     f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
                     f"[t={m.birth}] {m.text}" for m in ret.selected]
            ctx = "\n".join(lines)
            pred_mem = chat(api_key=key, model="glm-5.3-flash",
                            system=READER_SYS,
                            user=f"记忆/上下文：\n{ctx}\n\n问题：{units[t].user_text}",
                            cache_dir=CHAT_CACHE)
            pool_text = "\n".join(
                f"[t={m.birth}] {m.text}" for m in eng.mems.values()
                if m.pool is not Pool.ARCHIVE
                and m.superseded_by is None and m.aggregated_into is None)
            dumps.append({"t": t, "unit_id": units[t].id,
                          "ctx5": ctx, "pool": pool_text,
                          "pool_n": pool_text.count("\n") + 1
                          if pool_text else 0})
        eng.feedback(ret, units[t].user_text,
                     pred_mem or units[t].assistant_text, t)
        eng.step(t)
        worker.process(t)
    print(f"replay {time.time()-t0:.0f}s, {len(dumps)} eval pts", flush=True)

    for d in dumps:
        u = units[d["t"]]
        d["kps"] = _extract_kps(u.user_text, u.assistant_text, key,
                                "glm-5.3-flash")

    def cov(text):
        marks, fab, note = _judge_kp(u.user_text, d["kps"], text,
                                     u.assistant_text, key, "glm-5.3-flash")
        return _hit(marks)

    for d in dumps:
        u = units[d["t"]]
        d["cov_ctx5"] = cov(d["ctx5"])
        d["cov_pool"] = cov(d["pool"])
        print(f"t={d['t']} pool_n={d['pool_n']} "
              f"ctx5={d['cov_ctx5']} pool={d['cov_pool']}",
              flush=True)

    out = P.QA / f"{args.out_prefix}-{args.feature_set}.json"
    out.write_text(json.dumps(dumps, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("saved", out)
    n_failed = getattr(semantics, "n_failed", 0)
    if n_failed:
        print(f"⚠ opencode 裁判失败 {n_failed} 次（已走降级路径）", flush=True)


if __name__ == "__main__":
    main()
