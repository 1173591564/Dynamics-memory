"""Selector 校验（P6 从 agent/trio.py 拆出）：决定形状 + 目标门（应用前预检）。

预检只读：同事务内前序决定造成的状态漂移，由 applier 在写入时逐条复核；
任一失败整笔回滚——对外行为（异常类型/文案/重试）与预检无关。
UPDATE 门（未确认降 CONFLICT）不抛错，只活在 applier 内。
"""
from __future__ import annotations

from typing import TypedDict

from . import hauler


class Decision(TypedDict, total=False):
    candidate_index: int
    action: str
    target_id: int
    verified_correction: bool
    reason: str


def validate(reply, row, svc) -> list[Decision]:
    """预检每候选恰一合法决定 + 目标存在且未退役；返回决定列表。"""
    decisions = reply.get("decisions")
    candidates = row["payload"]["candidates"]
    if (not isinstance(decisions, list) or len(decisions) != len(candidates)
            or sorted(d.get("candidate_index") for d in decisions if isinstance(d, dict))
            != list(range(len(candidates)))):
        raise ValueError("Selector must return exactly one decision per candidate")
    uid = row["payload"]["unit_id"]
    for d in decisions:
        idx, action = d["candidate_index"], d.get("action")
        c = candidates[idx]
        if action not in {"CREATE", "EXIST", "UPDATE", "CONFLICT", "REJECT"}:
            raise ValueError("invalid Selector action")
        if action == "REJECT":
            continue
        # The selector cannot widen a source boundary established by its parent.
        hauler.validate_sources(svc, [c], uid)
        # Treat even model-produced recommendations as untrusted input.
        ev, _ = svc._validate_proposal(c, None)
        ev.origin = "agent"
        target = d.get("target_id")
        old = svc.engine.mems.get(target) if type(target) is int else None
        # Exact re-extraction from overlapping windows cannot yield a second
        # identical memory even when the model misclassifies it as CREATE.
        if action == "CREATE":
            same = next((m for m in svc.engine.mems.values()
                         if m.superseded_by is None and m.aggregated_into is None
                         and m.text == ev.text), None)
            if same is not None:
                action, old = "EXIST", same
        if action != "CREATE" and (old is None or old.superseded_by is not None
                                   or old.aggregated_into is not None):
            raise ValueError("Selector target is retired or unknown")
    return decisions
