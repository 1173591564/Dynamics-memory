"""Hauler 校验（P6 从 agent/trio.py 拆出）：候选结构 + 引用 ⊆ 窗口。

空列表合法（无候选可抽）；去重未做——现状无去重，P6 不加行为。
"""
from __future__ import annotations


def validate_sources(svc, candidates, uid):
    """每条候选必须是非空文本，且只引用所给窗口内的 unit。"""
    allowed = set(svc.log.recent_ids(uid, limit=6))
    for c in candidates:
        if (not isinstance(c, dict) or not isinstance(c.get("text"), str)
            or not c["text"].strip() or not isinstance(c.get("source_unit_ids"), list)
            or not c["source_unit_ids"] or any(type(i) is not int or i not in allowed
                                                 for i in c["source_unit_ids"])):
            raise ValueError("candidate must cite only units in the supplied window")


def validate(reply, row, svc):
    """校验 Hauler 输出并返回候选列表（结构 + 长度 + 引用范围）。"""
    candidates = reply.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 50:
        raise ValueError("Hauler candidates must be a list of at most 50")
    validate_sources(svc, candidates, row["payload"]["unit_id"])
    return candidates
