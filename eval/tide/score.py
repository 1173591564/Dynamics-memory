"""判分：由账本裁决。

检索层（本模块主力，完全确定性）：
  S = 上下文命中的 gold token 比例（gold 为空 → 1）
  H = 上下文含任一 harmful token（失效值）→ 1
  u = S − λ_H·H

归一化时间效用 NTU = (U_sys − U_none) / (U_oracle − U_none)，按流聚类 bootstrap。
回答层的闭集映射（classify_answer）用于接入固定读者后的 T1 回答层判分。
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from .text import has_token

LAMBDA_H = 1.0


def score_context(context: str, gold: list, harmful: list) -> dict:
    s = (sum(has_token(context, g) for g in gold) / len(gold)) if gold else 1.0
    h = 1.0 if any(has_token(context, x) for x in harmful) else 0.0
    return {"S": s, "H": h, "u": s - LAMBDA_H * h}


def classify_answer(answer: str, probe) -> str:
    """回答层第 1 级：字符串映射到账本候选。命中多个类别时取最差（有害优先）；
    都没命中：金值为空 → abstain-ok 候选由调用方二次判定，否则 OTHER（交 LLM/人工）。"""
    order = ["stale", "conflated", "current"]
    hit = {cls for tok, cls in probe.candidates.items()
           if tok != "__ABSENT__" and has_token(answer, tok)}
    for cls in order:
        if cls in hit:
            if cls == "current" and len(hit) > 1:
                continue
            return cls
    return "OTHER"


def _ntu(us, un, uo):
    den = uo - un
    return (us - un) / den if abs(den) > 1e-9 else float("nan")


def aggregate(records: list[dict], system: str, budget: int,
              n_boot: int = 1000, seed: int = 0) -> dict:
    """records：同一数据集、同一预算下 system / none / oracle 三者的探针记录。"""
    by = defaultdict(dict)       # (stream, probe) -> {system: rec}
    for r in records:
        if r["budget"] == budget:
            by[(r["stream"], r["probe"])][r["system"]] = r
    rows = [v for v in by.values() if system in v and "none" in v and "oracle" in v]
    if not rows:
        return {}
    streams = sorted({v[system]["stream"] for v in rows})
    s_idx = {s: i for i, s in enumerate(streams)}
    dims = sorted({v[system]["dimension"] for v in rows})

    def arrays(sel):
        us = np.array([v[system]["u"] for v in sel])
        un = np.array([v["none"]["u"] for v in sel])
        uo = np.array([v["oracle"]["u"] for v in sel])
        st = np.array([s_idx[v[system]["stream"]] for v in sel])
        return us, un, uo, st

    def boot(sel):
        us, un, uo, st = arrays(sel)
        point = _ntu(us.mean(), un.mean(), uo.mean())
        if np.isnan(point):
            return point, (float("nan"), float("nan"))
        rng = np.random.default_rng(seed)
        uniq = np.unique(st)
        # 预聚合到流：每流 (sum_s, sum_n, sum_o, count)
        agg = np.array([[us[st == k].sum(), un[st == k].sum(), uo[st == k].sum(),
                         (st == k).sum()] for k in uniq])
        vals = []
        for _ in range(n_boot):
            pick = agg[rng.integers(len(uniq), size=len(uniq))]
            c = pick[:, 3].sum()
            v = _ntu(pick[:, 0].sum() / c, pick[:, 1].sum() / c, pick[:, 2].sum() / c)
            if not np.isnan(v):
                vals.append(v)
        lo, hi = (np.percentile(vals, [2.5, 97.5]) if vals else (np.nan, np.nan))
        return float(point), (float(lo), float(hi))

    out = {"system": system, "budget": budget, "n_probes": len(rows),
           "n_streams": len(streams), "dims": {}}
    out["ntu"], out["ntu_ci"] = boot(rows)
    for d in dims:
        sel = [v for v in rows if v[system]["dimension"] == d]
        ntu, ci = boot(sel)
        knobs = defaultdict(list)
        for v in sel:
            knobs[v[system]["knob"]].append(v[system])
        out["dims"][d] = {
            "ntu": ntu, "ntu_ci": ci, "n": len(sel),
            "S": float(np.mean([v[system]["S"] for v in sel])),
            "H": float(np.mean([v[system]["H"] for v in sel])),
            "u": float(np.mean([v[system]["u"] for v in sel])),
            "curve": {int(k): {"S": float(np.mean([r["S"] for r in rs])),
                               "H": float(np.mean([r["H"] for r in rs])),
                               "u": float(np.mean([r["u"] for r in rs])),
                               "n": len(rs)}
                      for k, rs in sorted(knobs.items())},
        }
    return out
