"""任务 → 载荷（P6 从 agent/trio.py 拆出）：窗口/溯源/规则/记忆快照。

窗口 12k 超限沿用 ValueError（整轮重试，不静默截断；H16 的 Degraded 化不在 P6）。
"""
from __future__ import annotations


def rules_for(svc, kind, row, unit):
    """作用域规则注入：三角色各取自己的规则快照（文本不同）。"""
    if kind == "hauler_due":
        return svc.tasks.rule_snapshot("hauler", unit["user_text"] + "\n" + unit["assistant_text"])
    if kind == "reviewer_due":
        return svc.tasks.rule_snapshot("reviewer", unit["user_text"])
    return svc.tasks.rule_snapshot("selector", "\n".join(c["text"] for c in row["payload"]["candidates"]))


def memory_snapshot(svc):
    """未退役记忆的确定性 id 序快照；超 500 直接失败，禁截断猜测（H17）。"""
    memories = [m for m in svc.engine.mems.values()
                if m.superseded_by is None and m.aggregated_into is None
                and m.withdrawn_at is None]
    # Never let a truncated pool be mistaken for the whole store.
    if len(memories) > 500:
        raise RuntimeError("selector memory context exceeds limit; needs indexed paging")
    return [{"id": m.id, "text": m.text, "src": sorted(m.src),
             "entity": m.entity, "birth": m.birth, "pool": m.pool.value, "v": m.v,
             "claim_key": list(m.claim_key), "claim_value": m.claim_value,
             "claim_unit": m.claim_unit, "reviewed_after": m.reviewed_after,
             "pending_review": m.pending_review}
            for m in sorted(memories, key=lambda m: m.id)]


PROTOCOL_VERSION = 2  # 模型调用 payload 形状版本（N10：封存上下文随附）


def seal_context(kind: str, built: dict, revision: int) -> dict:
    """封存一次模型调用的输入上下文（N10）：窗口/规则/候选/移交规则 ids、
    快照 revision、协议版本与正文摘要。校验时对照封存值，不重建批准旧输出
    （迟到数据不能事后混进窗口/观测集）。"""
    import hashlib
    import json as _json
    digest = hashlib.sha256(_json.dumps(
        built, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    ctx = {
        "kind": kind,
        "protocol_version": PROTOCOL_VERSION,
        "snapshot_revision": revision,
        "payload_sha256": digest,
    }
    if kind in ("hauler_due", "selector_due", "reviewer_due"):
        ctx["unit_id"] = built.get("unit_id")
        # 窗口只封真实存在的（selector payload 无 window，其候选引用
        # 边界由父 hauler 任务的封存窗口约束，见 hauler.sealed_window）
        if isinstance(built.get("window"), list):
            ctx["window_ids"] = [u.get("unit_id") for u in built.get("window", [])]
    if kind in ("hauler_due", "selector_due"):
        ctx["rule_ids"] = [r.get("id") for r in built.get("rules", [])]
    if kind == "selector_due":
        ctx["candidate_texts"] = [c.get("text") for c in built.get("candidates", [])]
        ctx["memory_ids"] = [m["id"] for m in built.get("memories", [])]
    if kind == "reviewer_due":
        ctx["handoff_rule_ids"] = sorted(
            {rid for t in built.get("handoffs", [])
             for rid in t.get("rule_ids", [])})
    return ctx


def build_payload(kind, svc, row):
    """组装某工作流任务的 agent 输入；只读（调用方持锁与否由调用点定）。"""
    with svc.lock:
        uid = row["payload"]["unit_id"]
        unit = svc.log.get(uid)
        if unit is None:
            raise ValueError(f"unit {uid} missing from L0")
        if kind == "hauler_due":
            # Window closes at this unit, never includes future interactions.
            ids = svc.log.recent_ids(uid, limit=6)
            win = svc.log.window(ids, max_chars=12000, before=unit["t"] + 1)
            if win["truncated"]:
                raise ValueError("Hauler window exceeded 12000 characters; cannot silently omit evidence")
            return {"kind": kind, "task_id": row["id"], "unit_id": uid,
                    "window": win["units"], "rules": rules_for(svc, kind, row, unit)}
        if kind == "reviewer_due":
            ids = svc.log.recent_ids(uid, limit=6)
            win = svc.log.window(ids, max_chars=12000, before=unit["t"] + 1)
            if win["truncated"]:
                raise ValueError("Reviewer window exceeded 12000 characters; cannot silently omit evidence")
            work = svc.log.work(uid)
            trace = svc.tasks.workflow_trace(ids, before_task_id=row["id"])
            return {"kind": kind, "task_id": row["id"], "complaint": unit,
                    "window": win["units"], "handoffs": trace,
                    "previous_retrieval": (work or {}).get("context", {}),
                    "rules": rules_for(svc, kind, row, unit),
                    "memories": memory_snapshot(svc)}
        source_ids = sorted({i for c in row["payload"]["candidates"] for i in c["source_unit_ids"]})
        evidence = svc.log.window(source_ids, max_chars=12000, before=unit["t"] + 1)
        if evidence["truncated"]:
            raise ValueError("Selector evidence exceeded 12000 characters")
        return {"kind": kind, "task_id": row["id"], "unit_id": uid,
                "candidates": row["payload"]["candidates"], "source_units": evidence["units"],
                "memories": memory_snapshot(svc),
                "rules": rules_for(svc, kind, row, unit)}
