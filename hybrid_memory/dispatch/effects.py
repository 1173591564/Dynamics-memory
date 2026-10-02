"""效果落地（P5 落地，H21/H25/I3/I5）：每种持久 kind 的 applier 注册表。

EFFECTS 覆盖 9 种 kind（POLICIES 的 8 种 + 回执 kind 'feedback'）；
语义类 applier 为真实效果函数，调查/工作流类归外部循环所有
（legacy-agent/trio，P6 随 agents/ 收敛），此处登记归属不断言实现。
effect_transaction 是效果 + checkpoint 同事务的唯一入口（I5）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..core.types import Event, is_visible
from ..logstore import entities_in
from ..store.tasks import SEMANTIC_KINDS, WORKFLOW_KINDS


@dataclass(frozen=True)
class Applier:
    """一种 kind 的消费者登记：dispatch 自持 applier 函数，
    外部循环（legacy-agent/trio/service）只登记归属。"""
    kind: str
    owner: str
    apply: Callable | None = None


def journal_signal(svc, kind, payload, t, key, merge):
    """引擎信号出口：调查类进任务表，其余走易失队列（原 _journal_signal）。"""
    if kind in ("recall_miss", "extract_due"):
        svc._ensure_healthy()
        return svc.tasks.enqueue(kind, payload, t, key=key, merge=merge,
                                 memory_next_id=svc.engine._next_id)
    return None


def signal_payload(svc, kind, payload):
    """仅存稳定 id/JSON；绝不把 Retrieval/Memory 实例放进任务表。"""
    if kind == "conflict_pending":
        # SQLite JSON 会把 tuple 变成 list；在 merge 前规整，避免跨轮去重失效。
        return [list(pair) for pair in payload]
    if kind != "feedback_pending":
        return payload
    ret = payload["retrieval"]
    rid = next((i for i, v in svc._retrievals.items() if v is ret), None)
    if rid is None:
        raise ValueError("feedback retrieval 不在服务注册表")
    texts = getattr(ret, "presented_texts", ())  # 旧快照的 Retrieval 无此字段
    if len(texts) != len(ret.selected):
        texts = tuple(m.text for m in ret.selected)
    return {"retrieval_id": rid, "selected": [m.id for m in ret.selected],
            "texts": list(texts),
            "question": payload["question"], "answer": payload["answer"]}


def effect_transaction(svc, mutate, *, capture=None):
    """sidecar 检索/反馈的记忆变更、语义信号及 checkpoint 同事务（I5 唯一入口）。

    capture 给出时，request-id 回执与效果同一事务。已有回执不执行 mutate，
    返回值带 replayed，调用方不得再跑模型。
    """
    with svc._rollback_effect():
        old_registry = dict(svc._retrievals)
        old_next = svc._next_retrieval
        old_rets = [(ret, dict(ret.__dict__)) for ret in old_registry.values()]
        try:
            def run(conn):
                q = svc.engine.signals
                old_emit = q.on_emit

                def collect(kind, payload, t, key, merge):
                    if kind in SEMANTIC_KINDS | WORKFLOW_KINDS or kind in ("recall_miss", "extract_due"):
                        return svc.tasks._enqueue(
                            conn, kind, signal_payload(svc, kind, payload), t,
                            key=key, merge=merge,
                            memory_next_id=svc.engine._next_id)
                    return old_emit(kind, payload, t, key, merge)

                q.on_emit = collect
                try:
                    return mutate()
                finally:
                    q.on_emit = old_emit

            if capture is None:
                result, revision = svc.tasks.apply_effect(
                    run, svc._dump_state, svc._checkpoint_revision)
                replayed = False
            else:
                result, revision, replayed = svc.tasks.apply_captured_effect(
                    run, svc._dump_state, svc._checkpoint_revision, capture)
            svc._checkpoint_revision = revision
            if replayed and isinstance(result, dict):
                result = dict(result, replayed=True, accepted=True)
            return result
        except BaseException:
            svc._retrievals = old_registry
            svc._next_retrieval = old_next
            for ret, fields in old_rets:
                ret.__dict__.clear()
                ret.__dict__.update(fields)
            raise


def apply_conflict(svc, row, result) -> dict:
    """conflict_pending applier：邮戳一致的裁决落地；过期对重排待判。"""
    t = row["t"]
    current, stale = [], []
    for left, right, verdict, stamp in result["verdicts"]:
        tension = svc.engine.tensions.get(tuple(sorted((left, right))))
        if tension is None:
            continue
        if stamp != [tension.last_seen, tension.observations]:
            stale.append([left, right])
        else:
            current.append((left, right, verdict))
    if stale:
        svc.engine.signals.emit("conflict_pending", stale, t,
                                key="conflict",
                                merge=lambda old, new: old + [p for p in new if p not in old])
    return {"resolved": svc.engine.submit_verdicts(current, t)}


def apply_feedback(svc, row, result) -> dict:
    """feedback_pending applier：展示一致则结账记信用，否则按载荷 id 补记。"""
    payload, t = row["payload"], row["t"]
    used = result["used"]
    selected = payload["selected"]
    if len(used) != len(selected):
        raise ValueError("feedback 结果长度不符")
    ret = svc._retrievals.get(payload["retrieval_id"])
    shown = [m.id for m in ret.selected] if ret is not None else None
    if ret is not None and shown == selected:
        if ret.credited:
            return {"credited": 0}
        n = svc.engine.submit_relevance(ret, used, t)
        if (n == 0 and ret.selected and svc.cfg.miss_on_recognizer_none):
            question = payload["question"]
            svc.engine.report_miss(
                question, t, source="recognizer_none", retrieval=ret,
                entities=tuple(e for e, _ in entities_in(question)))
            svc.n_missed += 1
        return {"credited": n, "recog_fail": bool(result["recog_fail"])}
    # 注册表已退役或不再是当时展示的那一组。载荷 id 才是依据。
    n = svc.engine.credit_shown(selected, used, t)
    if ret is not None:
        ret.credited = True
        ret.n_useful = n
    return {"credited": n, "recog_fail": bool(result["recog_fail"]),
            "retired_source": True}


def apply_maintenance(svc, row, result) -> dict:
    """maintenance_due applier：来源未漂移则写入 reflection，否则重排。"""
    payload, t = row["payload"], row["t"]
    if result["event"] is None:
        return {"reflected": 0}
    sources = [[i, m.last_seen, m.pool.value, m.superseded_by, m.aggregated_into]
               for i in payload["ids"] if (m := svc.engine.mems.get(i)) is not None]
    if sources != result["sources"] or len(sources) != len(payload["ids"]):
        eligible = [i for i in payload["ids"] if (m := svc.engine.mems.get(i))
                    and is_visible(m) and not m.pending_review and m.kind == "fact"]
        if len(eligible) >= svc.cfg.consolidation_min_items:
            svc.engine.signals.emit("maintenance_due",
                                    {"scene": payload["scene"], "ids": eligible}, t,
                                    key=f"maint:{payload['scene']}",
                                    merge=lambda old, new: new)
        return {"reflected": 0}
    svc.engine.add_reflection(Event(**result["event"]), payload["ids"], t)
    return {"reflected": 1}


EFFECTS: dict[str, Applier] = {
    "conflict_pending": Applier("conflict_pending", "dispatch", apply_conflict),
    "feedback_pending": Applier("feedback_pending", "dispatch", apply_feedback),
    "maintenance_due": Applier("maintenance_due", "dispatch", apply_maintenance),
    "recall_miss": Applier("recall_miss", "legacy-agent"),
    "extract_due": Applier("extract_due", "legacy-agent"),
    "hauler_due": Applier("hauler_due", "trio"),
    "selector_due": Applier("selector_due", "trio"),
    "reviewer_due": Applier("reviewer_due", "trio"),
    # 'feedback' 是回执 kind（不进任务表）：消费者是 service/feedback API。
    "feedback": Applier("feedback", "service"),
}
