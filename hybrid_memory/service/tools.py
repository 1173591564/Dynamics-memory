"""只读工具面（P5 从 service.py 原样迁入）：log_* + conflicts。

before 因果上界 + 预算经门面 _admit；因果集经门面 _causal_*。
"""
from __future__ import annotations


def log_search(svc, query: str, *, before=None, scene=None, k=8,
               signal_id: str | None = None) -> dict:
    ctx, _, _ = svc._admit(signal_id, before)
    hits = svc.log.search(query, before=ctx.before,
                           scene=scene or None, k=min(int(k), 20))
    return {"hits": hits, "n": len(hits)}


def log_timeline(svc, entity: str, *, before=None, limit=30,
                 signal_id: str | None = None) -> dict:
    ctx, _, _ = svc._admit(signal_id, before)
    rows = svc.log.timeline(entity, before=ctx.before,
                             limit=min(int(limit), 100))
    return {"entity": entity, "timeline": rows, "n": len(rows)}


def log_stats(svc, group_by: str = "scene", *, before=None, limit=30,
              signal_id: str | None = None) -> dict:
    ctx, _, _ = svc._admit(signal_id, before)
    rows = svc.log.stats(group_by, before=ctx.before, limit=min(int(limit), 200))
    return {"group_by": group_by, "rows": rows, "n": len(rows),
            "units_total": svc.log.count(ctx.before)}


def log_window(svc, unit_ids, *, max_chars=None,
               signal_id: str | None = None) -> dict:
    ctx, bud, cap = svc._admit(signal_id, window=True, max_chars=max_chars)
    out = None
    try:
        out = svc.log.window(unit_ids, max_chars=cap, before=ctx.before)
        return out
    finally:
        if bud is not None:
            with svc._lock:
                bud["window_reserved"] -= cap
                # 失败退还整笔预留；成功只结算实际字数，未使用部分可继续使用。
                if out is not None:
                    bud["window_used"] += out["chars"]
                    out["budget_left"] = (bud["window_chars"] - bud["window_used"]
                                          - bud["window_reserved"])


def conflicts(svc, *, signal_id: str | None = None) -> dict:
    with svc._lock:
        ctx, _, _ = svc._admit(signal_id)
        tensions = svc.engine.tensions
        if signal_id is not None:
            tensions = svc._causal_tensions(svc._causal_memory_ids(ctx.before),
                                             ctx.before)
        out = []
        for (left, right), tension in tensions.items():
            a, b = svc.engine.mems.get(left), svc.engine.mems.get(right)
            out.append({
                "left": left, "right": right,
                "left_text": a.text if a else None,
                "right_text": b.text if b else None,
                "first_seen": tension.first_seen,
                "observations": tension.observations})
        return {"conflicts": out, "t": svc._t}
