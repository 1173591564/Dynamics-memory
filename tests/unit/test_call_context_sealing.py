"""store_call_context 封存调用上下文回归（P0-1.3 / N10）。

覆盖：
- worker 在模型调用前封存：窗口 ids、规则 id、快照 revision、协议版本、
  正文摘要（workflow 路径与 run_semantic_tasks 语义路径）；
- 校验对照封存上下文：hauler.validate_sources 用封存窗口，不重建
  recent_ids 批准旧输出（迟到导入的旧单元不能事后混进窗口）；
- reviewer.validate 用封存 handoff 规则 id，不重建 payload；
- 无封存（旧任务行）时回退重建，保持兼容。
"""
from __future__ import annotations

import json

import pytest

from hybrid_memory.agents import hauler, payload as payload_mod, reviewer
from hybrid_memory.dispatch.worker import DispatchWorker
from test_ouroboros import _svc


def _fake(calls):
    def fake(name, p):
        calls.append((name, p))
        if name == "hauler":
            return {"candidates": [{"text": "项目统一使用 bun 工具",
                                    "source_unit_ids": [p["unit_id"]]}]}
        if name == "reviewer":
            return {"diagnosis": "d", "rules": [], "repair_candidates": [],
                    "rule_reviews": []}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
    return fake


def _context(svc, task_id):
    with svc.tasks._lock:
        row = svc.tasks._conn.execute(
            "SELECT context FROM task_call_contexts WHERE task_id=? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (task_id,)).fetchone()
    return json.loads(row[0]) if row else None


def test_worker_seals_workflow_call_context(tmp_path):
    calls = []
    svc = _svc(tmp_path)
    svc.trio_mode = True
    worker = DispatchWorker(svc, _fake(calls))
    try:
        svc.observe("以后统一用 bun", "好的")
        worker.process_once()
        hauler_task = [t for t in svc.tasks.list_tasks(kinds=("hauler_due",))
                       if t["state"] == "done"][0]
        ctx = _context(svc, hauler_task["id"])
        assert ctx is not None, "模型调用前必须封存上下文"
        assert ctx["kind"] == "hauler_due"
        assert ctx["unit_id"] == 0
        assert ctx["window_ids"] == [0]
        assert ctx["rule_ids"] == []
        assert ctx["protocol_version"] == payload_mod.PROTOCOL_VERSION
        assert isinstance(ctx["snapshot_revision"], int)
        # 正文摘要与实际发给模型的 payload 绑定
        sent = calls[0][1]
        import hashlib
        from hybrid_memory.store.tasks import encode
        assert ctx["payload_sha256"] == hashlib.sha256(
            encode(sent).encode("utf-8")).hexdigest()
        # 同 token 重复封存同内容 = no-op（幂等）
        owned = None
        # 封存发生在 running 窗口内：完成后无法再补封（状态已 done）
        with pytest.raises(Exception):
            svc.tasks.store_call_context(
                hauler_task["id"], "forged-token", ctx)
    finally:
        svc.tasks.close()
        svc.log.close()


def test_semantic_path_seals_call_context(tmp_path):
    import time as _time
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.tasks.enqueue("maintenance_due", {"scene": "s", "ids": [1]}, 0)
        svc._semantic_model = lambda row: {"verdicts": []}
        svc.process_semantic_tasks()
        ctx = _context(svc, 1)
        assert ctx is not None, "语义路径同样封存"
        assert ctx["kind"] == "maintenance_due"
        assert ctx["protocol_version"] == payload_mod.PROTOCOL_VERSION
        assert isinstance(ctx["snapshot_revision"], int)
        import hashlib
        from hybrid_memory.store.tasks import encode
        assert ctx["payload_sha256"] == hashlib.sha256(
            encode({"scene": "s", "ids": [1]}).encode("utf-8")).hexdigest()
    finally:
        svc.tasks.close()
        svc.log.close()


def test_validate_sources_uses_sealed_window_not_rebuild(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.observe("第一轮原文", "说明")          # unit 0
        row = {"id": 42, "kind": "hauler_due",
               "payload": {"unit_id": 0}}
        # 封存窗口只有 [0]；模型只见过 unit 0（封存须在 running 租约内）
        import time as _time
        with svc.tasks.transaction() as conn:
            conn.execute("INSERT INTO tasks(id,kind,task_key,payload,t,state,"
                         "token,lease_until,created_at,updated_at) "
                         "VALUES(42,'hauler_due','k42','{\"unit_id\":0}',0,"
                         "'running','tok',?,0,0)", (_time.time() + 600,))
        svc.tasks.store_call_context(42, "tok", {"window_ids": [0]})
        with svc.tasks.transaction() as conn:
            conn.execute("UPDATE tasks SET state='done', token='tok' WHERE id=42")
        # 模型输出引用 unit 0：在封存窗口内 → 合法
        hauler.validate_sources(svc, [{"text": "第一轮原文",
                                       "source_unit_ids": [0]}], 0)
        # 迟到导入旧单元 1（t=0）：重建 recent_ids 会把它算进窗口，
        # 但模型从未见过——必须按封存窗口拒绝（N10）
        svc.log.add_unit(1, 0, user_text="迟到的旧单元", assistant_text="x")
        assert 1 in svc.log.recent_ids(0, limit=6), "前置：重建口径确实含 1"
        with pytest.raises(ValueError):
            hauler.validate_sources(svc, [{"text": "迟到的旧单元",
                                           "source_unit_ids": [1]}], 0,
                                    sealed=[0])
        with pytest.raises(ValueError):
            hauler.validate(svc_reply({"candidates": [{"text": "迟到的旧单元",
                                                       "source_unit_ids": [1]}]}),
                            dict(row, payload={"unit_id": 0}), svc)
    finally:
        svc.tasks.close()
        svc.log.close()


def test_reviewer_validate_uses_sealed_rule_ids(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.observe("第一轮原文", "说明")
        # 前置 hauler 任务（id=1，unit 0）用过规则 7；触发 reviewer（id=43）
        import time as _time
        with svc.tasks.transaction() as conn:
            conn.execute("INSERT INTO agent_rules(id,source_task,target,"
                         "instruction,scope,created_at) "
                         "VALUES(7,1,'hauler','规则7','project',0)")
            # observe 已产生任务 1（unit 0 的 hauler_due）：标记 done 并补产物，
            # 让重建口径（trace）能读到它的规则使用
            conn.execute("UPDATE tasks SET state='done', updated_at=0, "
                         "result='{\"candidates\": []}' WHERE id=1")
            conn.execute("INSERT INTO agent_rule_uses(task_id,rule_id) "
                         "VALUES(1,7)")
            conn.execute("INSERT INTO tasks(id,kind,task_key,payload,t,state,"
                         "token,lease_until,created_at,updated_at) "
                         "VALUES(43,'reviewer_due','k43','{\"unit_id\":0}',0,"
                         "'running','tok2',?,0,0)", (_time.time() + 600,))
        # 封存：模型当时只观测过规则 7；封存后又出现规则 8 的使用记录
        svc.tasks.store_call_context(43, "tok2", {"handoff_rule_ids": [7]})
        with svc.tasks.transaction() as conn:
            conn.execute("INSERT INTO agent_rules(id,source_task,target,"
                         "instruction,scope,created_at) "
                         "VALUES(8,1,'hauler','规则8','project',0)")
            conn.execute("INSERT INTO agent_rule_uses(task_id,rule_id) "
                         "VALUES(1,8)")
            conn.execute("UPDATE tasks SET state='done', token='tok2' WHERE id=43")
        # 前置：重建口径（无封存）确实会把规则 8 算进观测集
        rebuilt = payload_mod.build_payload("reviewer_due", svc,
                                            {"id": 43, "payload": {"unit_id": 0}})
        rebuilt_used = {rid for t in rebuilt["handoffs"]
                        for rid in t.get("rule_ids", [])}
        assert 8 in rebuilt_used, "前置：重建口径含规则 8（这就是 N10 漏洞）"
        row = {"id": 43, "kind": "reviewer_due", "payload": {"unit_id": 0}}
        reply = {"diagnosis": "d", "rules": [], "repair_candidates": [],
                 "rule_reviews": [{"rule_id": 8, "assessment": "helpful",
                                   "reason": "r"}]}
        # 规则 8 不在封存观测集内：必须按封存口径拒绝（重建口径会放行）
        with pytest.raises(ValueError):
            reviewer.validate(reply, row, svc)
    finally:
        svc.tasks.close()
        svc.log.close()


def test_validate_falls_back_without_seal(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.observe("第一轮原文", "说明")
        row = {"id": 44, "kind": "hauler_due",
               "payload": {"unit_id": 0}}
        # 无封存（旧任务行）：回退重建口径
        hauler.validate_sources(svc, [{"text": "第一轮原文",
                                       "source_unit_ids": [0]}], 0)
    finally:
        svc.tasks.close()
        svc.log.close()


def svc_reply(obj):
    return obj
