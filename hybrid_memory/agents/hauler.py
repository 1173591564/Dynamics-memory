"""Hauler 校验（P6 从 agent/trio.py 拆出）：候选结构 + 引用 ⊆ 窗口。

空列表合法（无候选可抽）；去重未做——现状无去重，P6 不加行为。
"""
from __future__ import annotations


def sealed_context(svc, row):
    """读取该任务模型调用时封存的上下文（N10）；无封存返回 None。

    校验必须对照封存口径：迟到导入的旧单元/新规则使用不能事后混进
    合法观测集。"""
    return svc.tasks.call_context(row["id"])


def sealed_window(svc, row):
    """封存窗口 id 列表（N10）；无封存返回 None（回退重建口径）。

    selector 的候选引用边界由父 hauler 任务建立：取父任务的封存窗口，
    不是 selector 自身的上下文（其 payload 不含 window）。"""
    ctx = None
    if row.get("kind") == "selector_due":
        parent = (row.get("payload") or {}).get("parent_task")
        if type(parent) is int:
            ctx = svc.tasks.call_context(parent)
    if ctx is None or "window_ids" not in ctx:
        ctx = sealed_context(svc, row)
    return (ctx or {}).get("window_ids")


def validate_sources(svc, candidates, uid, sealed=None):
    """每条候选必须是非空文本，且只引用所给窗口内的 unit。

    sealed：封存窗口 id 列表（N10）；None 时回退重建口径（旧任务行兼容）。
    """
    allowed = (set(sealed) if sealed is not None
               else set(svc.log.recent_ids(uid, limit=6)))
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
    validate_sources(svc, candidates, row["payload"]["unit_id"],
                     sealed=sealed_window(svc, row))
    return candidates
