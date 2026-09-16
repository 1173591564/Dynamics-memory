"""离线词法通道探针——零 API 调用。

poolcov-p01.json 已 dump 每个评测点的完整活跃池文本；
嵌入走 SQLite 缓存（offline=True，miss 即报错）。
对每个评测点分别按原公式和 +w·lex 重排 top-5，
报告新进入者文本，人工核对是否是要点承载者。

用法：python -m experiments.offline_lex_probe --lex-weight 0.25
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

from experiments import paths as P
from hybrid_memory.core.retrieval import _lex_tokens
from hybrid_memory.datasets.real_chat import load_interaction_units
from hybrid_memory.embed.base import cosine
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder

FRESH_ALPHA, LAM, THETA, K = 0.10, 0.02, 0.35, 5
_LINE = re.compile(r"\[t=(\d+)\]\s*(.*)")


def parse_pool(pool: str):
    out = []
    for ln in pool.split("\n"):
        m = _LINE.match(ln.strip())
        if m:
            out.append({"birth": int(m.group(1)), "text": m.group(2)})
    return out


def lex_scores(query: str, mems: list[dict]) -> dict[int, float]:
    qtok = _lex_tokens(query)
    if not qtok:
        return {}
    toks = [_lex_tokens(m["text"]) for m in mems]
    df: dict[str, int] = {}
    for mt in toks:
        for tok in mt:
            df[tok] = df.get(tok, 0) + 1
    n = max(len(mems), 1)
    if not any(df.get(t, 0) <= max(3, int(0.15 * n)) for t in qtok):
        return {}

    def idf(t):
        return math.log((n + 1) / (df.get(t, 0) + 0.5))

    denom = sum(idf(t) for t in qtok) or 1.0
    return {i: sum(idf(t) for t in (qtok & mt)) / denom
            for i, mt in enumerate(toks) if qtok & mt}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lex-weight", type=float, default=0.25)
    ap.add_argument("--poolcov", type=Path,
                    default=P.QA / "poolcov-p01.json")
    ap.add_argument("--kps", type=Path,
                    default=P.QA / "qa-cont-v4-p01-kp.json")
    args = ap.parse_args()

    emb = ZhipuEmbedder(api_key=None,
                        cache=SqliteEmbeddingCache(P.EMB_CACHE),
                        offline=True)
    units = {u.id: u for u in load_interaction_units(P.DATA_REAL)}
    dumps = json.loads(args.poolcov.read_text(encoding="utf-8"))
    kps = {r["t"]: r["kps"] for r in
           json.loads(args.kps.read_text(encoding="utf-8"))["results"]}

    for d in dumps:
        t, u = d["t"], units[d["unit_id"]]
        mems = parse_pool(d["pool"])
        qv = emb.embed([u.user_text])[0]
        mv = emb.embed([m["text"] for m in mems])
        lex = lex_scores(u.user_text, mems)
        for i, m in enumerate(mems):
            s = cosine(qv, mv[i])
            m["base"] = s + FRESH_ALPHA * math.exp(-LAM * (t - m["birth"]))
            m["lex"] = lex.get(i, 0.0)
            m["boosted"] = m["base"] + args.lex_weight * m["lex"]
        gate = [m for m in mems if m["base"] >= THETA]
        base_top = sorted(gate, key=lambda m: m["base"], reverse=True)[:K]
        new_top = sorted(gate, key=lambda m: m["boosted"], reverse=True)[:K]
        base_ids = {id(m) for m in base_top}
        entered = [m for m in new_top if id(m) not in base_ids]
        left = [m for m in base_top if id(m) not in {id(x) for x in new_top}]
        print(f"\n===== t={t}  query: {u.user_text[:60]} =====")
        print("keypoints:")
        for kp in kps.get(t, []):
            print("   *", kp[:80])
        if not entered:
            print("  top-5 无变化")
            continue
        for m in entered:
            print(f"  +进 base={m['base']:.3f} lex={m['lex']:.3f}"
                  f" | {m['text'][:90]}")
        for m in left:
            print(f"  -出 base={m['base']:.3f}      | {m['text'][:90]}")


if __name__ == "__main__":
    main()
