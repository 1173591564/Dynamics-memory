"""效果落地（P5 落地，H21/H25/I3/I5）：每种持久 kind 的 applier 注册表。

EFFECTS 覆盖 9 种 kind（POLICIES 的 8 种 + 回执 kind 'feedback'）；
语义/工作流类 applier 为真实效果函数（工作流类 P6 随 agents/ 收敛，
validate 进 agents/*，mutate 留本模块）；调查类归外部循环所有
（legacy-agent），此处登记归属不断言实现。
effect_transaction 是效果 + checkpoint 同事务的唯一入口（I5）。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable

from ..agents import hauler, reviewer, selector
from ..core import triggers
from ..core.types import Event, Pool, is_visible
from ..logstore import entities_in
from ..store.tasks import SEMANTIC_KINDS, WORKFLOW_KINDS


@dataclass(frozen=True)
class Applier:
    """一种 kind 的消费者登记：dispatch 自持 applier 函数，
    外部循环（legacy-agent/service）只登记归属；工作流类 P6 起归 dispatch。"""
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


def send_workflow(conn, svc, kind, uid, candidates, parent):
    """工作流交接：下发下一角色任务；空候选不建任务（原 TrioWorker._send）。"""
    if not candidates:
        return
    svc.tasks._enqueue(conn, kind,
        {"unit_id": uid, "candidates": candidates, "parent_task": parent},
        svc._t, key=f"{kind}:{parent}", memory_next_id=svc.engine._next_id)


def apply_hauler(svc, row, output, conn) -> dict:
    """hauler_due applier：校验候选 → 下发 selector_due。"""
    candidates = hauler.validate(output, row, svc)
    send_workflow(conn, svc, "selector_due", row["payload"]["unit_id"],
                  candidates, row["id"])
    return {"candidates": len(candidates)}


def apply_selector(svc, row, output, conn) -> dict:
    """selector_due applier：预检 → 逐决定校验+写入（同一事务，全有或全无）。"""
    selector.validate(output, row, svc)
    decisions = output.get("decisions")
    candidates = row["payload"]["candidates"]
    if (not isinstance(decisions, list) or len(decisions) != len(candidates)
            or sorted(d.get("candidate_index") for d in decisions if isinstance(d, dict))
            != list(range(len(candidates)))):
        raise ValueError("Selector must return exactly one decision per candidate")
    uid = row["payload"]["unit_id"]
    outcomes = []
    for d in decisions:
        idx, action = d["candidate_index"], d.get("action")
        c = candidates[idx]
        if action not in {"CREATE", "EXIST", "UPDATE", "CONFLICT", "REJECT"}:
            raise ValueError("invalid Selector action")
        if action == "REJECT":
            outcomes.append({"index": idx, "action": action})
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
        if action == "EXIST":
            new_sources = set(ev.src) - set(old.src)
            old.src = old.src | frozenset(ev.src)
            old.evid += len(new_sources)
            if old.pool is Pool.ARCHIVE:
                old.pool = Pool.CANDIDATE if svc.cfg.two_pool else Pool.MEMORY
            old.last_seen = max(old.last_seen, svc._t)
            outcomes.append({"index": idx, "action": action, "target_id": old.id,
                             "new_evidence": len(new_sources)})
            continue
        if action == "UPDATE":
            # Recent != correct. Without an explicit user correction, refer
            # incompatible statements to a human rather than choosing newest.
            confirmed = bool(d.get("verified_correction")) and any(
                triggers.is_correction(svc.log.get(i)["user_text"])
                for i in ev.src if svc.log.get(i))
            if not confirmed:
                action = "CONFLICT"
        if action == "CONFLICT":
            conn.execute("INSERT OR IGNORE INTO human_reviews"
                         "(source_task,target_id,candidate,reason,created_at) VALUES(?,?,?,?,?)",
                         (row["id"], old.id, json.dumps(c, ensure_ascii=False, sort_keys=True),
                          str(d.get("reason", "conflicting evidence"))[:500], time.time()))
            old.pending_review = True
            outcomes.append({"index": idx, "action": action, "target_id": old.id})
            continue
        ids = svc.engine.propose([ev], svc._t)
        if action == "UPDATE" and ids:
            svc.engine.add_tension(ids[0], old.id, svc._t)
            svc.engine.submit_verdicts([(ids[0], old.id, "update")], svc._t)
        outcomes.append({"index": idx, "action": action if ids else "EXIST", "new_ids": ids})
    return {"outcomes": outcomes}


def apply_reviewer(svc, row, output, conn) -> dict:
    """reviewer_due applier：预检 → 规则反馈/新规则/修复交接写入（同一事务）。"""
    bundle = reviewer.validate(output, row, svc)
    for rr in bundle["rule_reviews"]:
        conn.execute("INSERT INTO agent_rule_feedback"
            "(reviewer_task,rule_id,assessment,reason,at) VALUES(?,?,?,?,?)",
            (row["id"], rr["rule_id"], rr["assessment"],
             rr["reason"].strip(), time.time()))
        if rr["assessment"] == "ineffective":
            updated = conn.execute("UPDATE agent_rules SET enabled=0 "
                "WHERE id=? AND enabled=1", (rr["rule_id"],))
            if updated.rowcount:
                conn.execute("INSERT INTO agent_rule_audit(rule_id,action,actor,at) "
                    "VALUES(?,'disable','reviewer',?)",
                    (rr["rule_id"], time.time()))
    for r in bundle["rules"]:
        scope = r.get("scope", "project")
        cur = conn.execute("INSERT OR IGNORE INTO agent_rules"
                     "(source_task,target,instruction,scope,created_at) "
                     "VALUES(?,?,?,?,?)", (row["id"], r["target"],
                         r["instruction"].strip(), scope, time.time()))
        if cur.rowcount:
            rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO agent_rule_audit(rule_id,action,actor,at) "
                         "VALUES(?,'create','reviewer',?)", (rid, time.time()))
    send_workflow(conn, svc, "selector_due", row["payload"]["unit_id"],
                  bundle["repair_candidates"], row["id"])
    return {"rules": len(bundle["rules"]),
            "repair_candidates": len(bundle["repair_candidates"])}


EFFECTS: dict[str, Applier] = {
    "conflict_pending": Applier("conflict_pending", "dispatch", apply_conflict),
    "feedback_pending": Applier("feedback_pending", "dispatch", apply_feedback),
    "maintenance_due": Applier("maintenance_due", "dispatch", apply_maintenance),
    "recall_miss": Applier("recall_miss", "legacy-agent"),
    "extract_due": Applier("extract_due", "legacy-agent"),
    "hauler_due": Applier("hauler_due", "dispatch", apply_hauler),
    "selector_due": Applier("selector_due", "dispatch", apply_selector),
    "reviewer_due": Applier("reviewer_due", "dispatch", apply_reviewer),
    # 'feedback' 是回执 kind（不进任务表）：消费者是 service/feedback API。
    "feedback": Applier("feedback", "service"),
}
