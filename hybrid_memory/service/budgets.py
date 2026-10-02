"""调查预算开/关（P4 从 server.py 原样迁入）：open/close_budget。

spend/meter/check_cost_caps 未落地（§2.6 愿望）：调用计数与窗口计量
内联在 _investigate_context 临界区内，无独立等价函数；行为保留在门面。
RealBudget/BasicCostTracker/PAPER_BUDGET 在代码库中不存在。
"""
from __future__ import annotations

import time
from dataclasses import replace

from .context import _ORIGINS, InvestigationContext, SignalClosed

MAIN_WINDOW_CAP = 1500          # 无信号上下文（主 agent）的单次回展上限


def open_budget(svc, signal_id: str, *, tool_calls: int,
                window_chars: int, before: int,
                origin: str | None = None, task_id: int | None = None,
                lease_token: str | None = None) -> InvestigationContext:
    """打开一次调查并返回仅供进程内最终 JSON 使用的不可变上下文。
    HTTP 工具必须使用活跃 signal_id；不能提供此对象跳过计量。
    """
    if not isinstance(signal_id, str) or not signal_id.strip():
        raise ValueError("signal_id required")
    for name, value in (("tool_calls", tool_calls), ("window_chars", window_chars),
                        ("before", before)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative int")
    ctx = InvestigationContext(signal_id, before,
                               origin if origin in _ORIGINS else "agent", task_id, lease_token)
    with svc._lock:
        if signal_id in svc._budgets:
            raise ValueError(f"signal {signal_id} already open")
        svc._budgets[signal_id] = {"tool_calls": tool_calls,
                                    "window_chars": window_chars,
                                    "calls": 0, "window_used": 0,
                                    "window_reserved": 0, "context": ctx,
                                    "opened": time.time()}
    return ctx


def close_budget(svc, signal_id: str) -> dict:
    with svc._lock:
        bud = svc._budgets.pop(signal_id, None)
        if bud is None:
            return {}
        return {"calls": bud["calls"], "window_used": bud["window_used"],
                "window_reserved": bud["window_reserved"],
                "elapsed_s": round(time.time() - bud["opened"], 1)}


def admit(svc, signal_id: str | None, before: int | None = None, *,
          window: bool = False, max_chars: int | None = None
          ) -> tuple[InvestigationContext, dict | None, int]:
    """同一临界区内校验存活、计调用、固定因果界，并预留回展额度。

    返回不可变上下文、该次预算对象和预留量。I/O 后只用这些对象，
    不再按 signal_id 二次查找，避免 close/reopen 丢失边界或串账。
    calls 统计尝试次数（含 429），window_used 只统计成功返回的原文字数。
    """
    if before is not None and (type(before) is not int or before < 0):
        raise ValueError("before must be a non-negative int")
    if max_chars is not None and (type(max_chars) is not int or max_chars <= 0):
        raise ValueError("max_chars must be a positive int")
    with svc._lock:
        svc._ensure_healthy()
        bud = None
        ctx = InvestigationContext(None, before)
        if signal_id is not None:
            bud = svc._budgets.get(signal_id)
            if bud is None:
                raise SignalClosed(f"signal {signal_id} 已关闭或不存在")
            bud["calls"] += 1
            if bud["calls"] > bud["tool_calls"]:
                raise PermissionError(
                    f"该信号工具调用预算 {bud['tool_calls']} 已用尽，请立即汇总输出")
            base = bud["context"]
            if base.task_id is not None:
                svc.tasks.check_owned(base.task_id, base.lease_token)
            bound = base.before if before is None else min(before, base.before)
            ctx = replace(base, before=bound)
        cap = 0
        if window:
            remaining = (bud["window_chars"] - bud["window_used"]
                         - bud["window_reserved"] if bud is not None
                         else MAIN_WINDOW_CAP)
            if remaining <= 0:
                raise PermissionError("该信号回展预算已用尽（含在途预留）")
            cap = min(remaining, max_chars) if max_chars is not None else remaining
            if bud is not None:
                bud["window_reserved"] += cap
        return ctx, bud, cap
