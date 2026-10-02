"""sidecar 语义工作真实 SQLite/HTTP、失败回滚、子进程重启。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hybrid_memory.core.types import Event, Memory
from hybrid_memory.store.tasks import (SEMANTIC_KINDS, TaskLeaseLost,
                                       TaskQueueFull)
from test_server import _http, _service


def _close(svc):
    svc.stop_unit_recovery()
    svc.tasks.close()
    svc.log.close()


def _prepared(tmp_path):
    svc = _service(tmp_path)
    svc.observe("部署在哪", "已改到 B 服务器")
    rid = svc.recall("部署在哪")["retrieval_id"]
    return svc, rid


def test_feedback_is_durable_before_worker_and_recovers_once(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        with _http(svc) as (post, get, _):
            status, body = post("/feedback", {"retrieval_id": rid,
                                              "question": "部署在哪", "answer": "B 服务器"})
            assert status == 200 and body["n_useful"] == 0
            assert get("/signals")[1]["queued"].get("feedback_pending") == 1
        ret = svc._retrievals[rid]
        assert ret.feedback_sent and not ret.credited
    finally:
        _close(svc)
    restored = _service(tmp_path, texts=())
    try:
        ret = restored._retrievals[rid]
        assert ret.selected[0] is restored.engine.mems[0]
        assert ret.feedback_sent and not ret.credited
        assert restored.process_semantic_tasks()["credited"] == 1
        assert ret.credited and restored.engine.mems[0].hits == 1
        assert restored.process_semantic_tasks()["credited"] == 0
        assert restored.engine.mems[0].hits == 1
        assert restored.tasks.list_tasks(kinds=("feedback_pending",))[0]["state"] == "done"
    finally:
        _close(restored)


def test_feedback_capacity_failure_restores_sent_flag(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.tasks.capacity = 1
        svc.report_miss("occupy")
        with pytest.raises(TaskQueueFull):
            svc.feedback(rid, "部署在哪", "B")
        assert not svc._retrievals[rid].feedback_sent
        assert svc.tasks.list_tasks(kinds=("feedback_pending",)) == []
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET state='done' WHERE kind='recall_miss'")
        assert svc.feedback(rid, "部署在哪", "B")["n_useful"] == 1
    finally:
        _close(svc)


def test_semantic_receipt_sql_failure_rolls_back_in_place_then_retries(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B")
        old = svc.engine.mems[0]
        svc.tasks._conn.execute("CREATE TRIGGER reject_semantic BEFORE INSERT ON operations "
                                "WHEN NEW.op_key='semantic' BEGIN SELECT RAISE(ABORT, 'receipt fail'); END")
        stats = type(svc).process_semantic_tasks(svc)
        row = svc.tasks.list_tasks(kinds=("feedback_pending",))[0]
        assert stats["errors"] == 1 and row["state"] == "ready" and row["result"]
        assert svc.engine.mems[0] is old and old.hits == 0
        assert not svc._retrievals[rid].credited
        svc.tasks._conn.execute("DROP TRIGGER reject_semantic")
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET next_run_at=0 WHERE id=?", (row["id"],))
        assert type(svc).process_semantic_tasks(svc)["credited"] == 1
        assert old.hits == 1
    finally:
        _close(svc)


def test_expired_semantic_lease_fences_old_token(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B")
        task = svc.tasks.list_tasks(kinds=("feedback_pending",))[0]
        first = svc.tasks.claim(task["id"], expected_version=task["version"])
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET lease_until=0 WHERE id=?", (task["id"],))
        svc.tasks.recover_expired(kinds=SEMANTIC_KINDS, reset_next_run_at=True)
        second = svc.tasks.claim(task["id"], expected_version=task["version"])
        assert second["token"] != first["token"]
        with pytest.raises(TaskLeaseLost):
            svc.tasks.store_result(task["id"], first["token"], {"used": [True]})
        svc.tasks.store_result(task["id"], second["token"],
                                        {"used": [True], "recog_fail": False})
        assert svc.tasks.list_tasks(kinds=("feedback_pending",))[0]["state"] == "ready"
    finally:
        _close(svc)


def test_saved_model_result_is_not_invoked_again_after_restart(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B")
        row = svc.tasks.list_tasks(kinds=("feedback_pending",))[0]
        claim = svc.tasks.claim(row["id"], expected_version=row["version"])
        svc.tasks.store_result(row["id"], claim["token"],
                                        {"used": [True], "recog_fail": False})
    finally:
        _close(svc)
    restored = _service(tmp_path, texts=())
    try:
        restored._semantic_model = lambda *_: (_ for _ in ()).throw(AssertionError("repeated model"))
        assert restored.process_semantic_tasks()["credited"] == 1
        assert restored.engine.mems[0].hits == 1
    finally:
        _close(restored)


def test_crashes_before_effect_and_after_atomic_commit(tmp_path):
    for phase in ("before", "after"):
        path = tmp_path / phase
        svc, rid = _prepared(path)
        try:
            svc.process_semantic_tasks = lambda: {}
            svc.feedback(rid, "部署在哪", "B")
        finally:
            _close(svc)
        code = r'''
import os,sys
from test_server import _service
svc=_service(sys.argv[1], texts=())
original=svc.tasks.complete
def crash(*args, **kwargs):
    if sys.argv[2]=='before': os._exit(77)
    result=original(*args, **kwargs)
    os._exit(77)
svc.tasks.complete=crash
svc.process_semantic_tasks()
'''
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run([sys.executable, "-c", code, str(path), phase],
                              cwd=root, env={**os.environ, "PYTHONPATH": str(root) + os.pathsep + str(root / "tests")},
                              capture_output=True, text=True, timeout=20)
        assert proc.returncode == 77, proc.stderr
        restored = _service(path, texts=())
        try:
            task = restored.tasks.list_tasks(kinds=("feedback_pending",))[0]
            if phase == "before":
                assert task["state"] == "applying" and restored.engine.mems[0].hits == 0
                with restored.tasks._conn:
                    restored.tasks._conn.execute("UPDATE tasks SET lease_until=0 WHERE id=?", (task["id"],))
                assert restored.process_semantic_tasks()["credited"] == 1
            else:
                assert task["state"] == "done" and restored.engine.mems[0].hits == 1
                assert restored.process_semantic_tasks()["credited"] == 0
            assert restored.engine.mems[0].hits == 1
        finally:
            _close(restored)


class _Judge:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def judge(self, *args):
        self.calls += 1
        return "update"

    def consolidate(self, mems, t):
        self.calls += 1
        return Event(123, "reflection", "新反思", src=(0,), scene="测试场景")


def test_conflict_and_consolidation_durable_across_restart(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        old = svc.engine.mems[0]
        svc.cfg.tension_delay = 0
        svc.cfg.consolidation_on = True
        svc.cfg.consolidation_min_items = 1
        svc.cfg.consolidation_salience_budget = 0
        svc.engine.mems[1] = Memory(1, old.belief_id, "v2", "部署在 C 服务器",
                                     old.emb.copy(), birth=1, last_seen=svc._t,
                                     scene="测试场景", salience=1.0)
        svc.engine._next_id = 2
        svc.engine.add_tension(0, 1, 0)
        svc.engine._consolidation_pending.add(1)
        svc._commit_sidecar_effect(lambda: svc.engine.step(svc._t))
        assert {t["kind"] for t in svc.tasks.list_tasks(kinds=("conflict_pending", "maintenance_due"))} == {
            "conflict_pending", "maintenance_due"}
    finally:
        _close(svc)
    restored = _service(tmp_path, texts=())
    try:
        judge = _Judge(restored.semantics)
        restored.semantics = restored.engine.semantics = judge
        restored.cfg.consolidation_min_items = 1
        result = restored.process_semantic_tasks()
        assert result["errors"] == 0 and judge.calls == 2
        assert restored.engine.n_resolve == 1 and restored.engine.n_consolidate == 1
        assert restored.process_semantic_tasks()["resolved"] == 0
    finally:
        _close(restored)


def test_process_crash_after_claim_before_model_recovers_without_losing_job(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B")
    finally:
        _close(svc)
    code = r'''
import os,sys
from test_server import _service
svc=_service(sys.argv[1], texts=())
svc._semantic_model=lambda *_: os._exit(77)
svc.process_semantic_tasks()
'''
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=root,
                          env={**os.environ, "PYTHONPATH": str(root) + os.pathsep + str(root / "tests")},
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 77, proc.stderr
    restored = _service(tmp_path, texts=())
    try:
        row = restored.tasks.list_tasks(kinds=("feedback_pending",))[0]
        assert row["state"] == "running" and restored.engine.mems[0].hits == 0
        with restored.tasks._conn:
            restored.tasks._conn.execute("UPDATE tasks SET lease_until=0 WHERE id=?", (row["id"],))
        assert restored.process_semantic_tasks()["credited"] == 1
        assert restored.engine.mems[0].hits == 1
    finally:
        _close(restored)


def test_consolidation_none_is_valid_completion(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        svc.cfg.consolidation_on = True
        svc.cfg.consolidation_min_items = 1
        svc.cfg.consolidation_salience_budget = 0
        svc.engine._consolidation_pending.add(0)
        svc._commit_sidecar_effect(lambda: svc.engine.step(svc._t))
        class NoReflection(_Judge):
            def consolidate(self, mems, t):
                self.calls += 1
                return None
        sem = NoReflection(svc.semantics)
        svc.semantics = svc.engine.semantics = sem
        assert svc.process_semantic_tasks()["reflected"] == 0
        assert sem.calls == 1
        assert svc.tasks.list_tasks(kinds=("maintenance_due",))[0]["state"] == "done"
        assert svc.process_semantic_tasks()["reflected"] == 0 and sem.calls == 1
    finally:
        _close(svc)


def test_concurrent_feedback_accepts_one_durable_job(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            outs = list(pool.map(lambda _: svc.feedback(rid, "部署在哪", "B"), range(2)))
        assert sum("error" in out for out in outs) == 1
        assert len(svc.tasks.list_tasks(kinds=("feedback_pending",))) == 1
        assert type(svc).process_semantic_tasks(svc)["credited"] == 1
        assert svc.engine.mems[0].hits == 1
    finally:
        _close(svc)


def test_l0_effect_hands_off_semantic_work_in_same_task_transaction(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.cfg.consolidation_on = True
        svc.cfg.consolidation_min_items = 1
        svc.cfg.consolidation_salience_budget = 0
        svc.process_semantic_tasks = lambda: {}
        out = svc.observe("部署在哪", "已改到 B 服务器")
        assert out["unit_id"] == 0 and svc.log.work(0)["state"] == "done"
        row = svc.tasks.list_tasks(kinds=("maintenance_due",))[0]
        assert row["state"] == "pending" and row["t"] == svc.log.get(0)["t"]
        assert svc.engine.signals.peek_kinds().get("maintenance_due") is None
    finally:
        _close(svc)
    restored = _service(tmp_path, texts=())
    try:
        restored.cfg.consolidation_min_items = 1
        judge = _Judge(restored.semantics)
        restored.semantics = restored.engine.semantics = judge
        assert restored.process_semantic_tasks()["reflected"] == 1
        assert len([m for m in restored.engine.mems.values() if m.kind == "reflection"]) == 1
        assert restored.process_semantic_tasks()["reflected"] == 0
    finally:
        _close(restored)


def test_semantic_status_shows_retry_and_recent_error(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B")
        def unavailable(row):
            raise RuntimeError("model unavailable")
        svc._semantic_model = unavailable
        assert type(svc).process_semantic_tasks(svc)["errors"] == 1
        with _http(svc) as (_, get, _server):
            status, signals = get("/signals")
        assert status == 200
        semantic = signals["semantic"]
        assert semantic["states"]["pending"] == 1 and semantic["retrying"] == 1
        assert semantic["errors"][0]["kind"] == "feedback_pending"
        assert "model unavailable" in semantic["errors"][0]["last_error"]
    finally:
        _close(svc)


def test_stale_verdict_requeues_current_tension_with_capacity_one(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        old = svc.engine.mems[0]
        svc.engine.mems[1] = Memory(1, old.belief_id, "new", "部署在 C 服务器",
                                     old.emb.copy(), birth=svc._t)
        svc.engine._next_id = 2
        svc.engine.add_tension(0, 1, svc._t)
        svc.cfg.tension_delay = 0
        svc.tasks.capacity = 1
        svc._commit_sidecar_effect(lambda: svc.engine.step(svc._t))
        row = svc.tasks.list_tasks(kinds=("conflict_pending",))[0]
        claim = svc.tasks.claim(row["id"], expected_version=row["version"])
        result = svc._semantic_model(claim)
        svc.tasks.store_result(row["id"], claim["token"], result)
        # 模型调用完成后同一张力又收到新观察；旧 verdict 不得覆盖新版本。
        svc.engine.add_tension(0, 1, svc._t)
        svc._commit_sidecar_effect(lambda: None)
        first = svc.process_semantic_tasks()
        assert first["resolved"] == 0 and first["errors"] == 0
        rows = svc.tasks.list_tasks(kinds=("conflict_pending",))
        assert [r["state"] for r in rows] == ["done", "pending"]
        judge = _Judge(svc.semantics)
        svc.semantics = svc.engine.semantics = judge
        assert svc.process_semantic_tasks()["resolved"] == 1
        assert judge.calls == 1 and svc.engine.n_resolve == 1
    finally:
        _close(svc)


def test_background_recovers_semantic_when_older_unit_is_backed_off(tmp_path):
    import time
    svc, rid = _prepared(tmp_path)
    try:
        svc.process_semantic_tasks = lambda: {}  # 暂缓，制造语义任务占满队列
        svc.feedback(rid, "部署在哪", "B")
        svc.tasks.capacity = 1
        with pytest.raises(TaskQueueFull):
            svc.observe("以后统一用 bun 跑脚本", "好的")
        assert svc.log.work(1)["state"] == "pending"
        del svc.process_semantic_tasks
        svc.start_unit_recovery()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and svc.log.work(1)["state"] != "done":
            time.sleep(0.05)
        assert svc.log.work(1)["state"] == "done"
        assert svc.engine.mems[0].hits == 1
        assert svc.tasks.list_tasks(kinds=("feedback_pending",))[0]["state"] == "done"
    finally:
        _close(svc)


def test_unit_semantic_handoff_failure_rolls_back_effect_and_recovers(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.cfg.consolidation_on = True
        svc.cfg.consolidation_min_items = 1
        svc.cfg.consolidation_salience_budget = 0
        svc.tasks._conn.execute("CREATE TRIGGER reject_maintenance BEFORE INSERT ON tasks "
                                "WHEN NEW.kind='maintenance_due' "
                                "BEGIN SELECT RAISE(ABORT, 'handoff fail'); END")
        with pytest.raises(Exception, match="handoff fail"):
            svc.observe("部署在哪", "已改到 B 服务器")
        assert svc.log.work(0)["state"] == "pending" and svc.engine.mems == {}
        assert svc.tasks.list_tasks(kinds=("maintenance_due",)) == []
        svc.tasks._conn.execute("DROP TRIGGER reject_maintenance")
        with svc.log._conn:
            svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=0")
        svc.process_semantic_tasks = lambda: {}
        assert svc.process_pending_units()[0]["candidates"] == 1
        assert svc.tasks.list_tasks(kinds=("maintenance_due",))[0]["state"] == "pending"
    finally:
        _close(svc)


def test_recognizer_none_handoff_is_atomic_with_credit(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.cfg.miss_on_recognizer_none = True
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "与之无关")
        row = svc.tasks.list_tasks(kinds=("feedback_pending",))[0]
        claim = svc.tasks.claim(row["id"], expected_version=row["version"])
        svc.tasks.store_result(row["id"], claim["token"],
                                        {"used": [False], "recog_fail": False})
        svc.tasks._conn.execute("CREATE TRIGGER reject_miss BEFORE INSERT ON tasks "
                                "WHEN NEW.kind='recall_miss' "
                                "BEGIN SELECT RAISE(ABORT, 'miss handoff fail'); END")
        assert type(svc).process_semantic_tasks(svc)["errors"] == 1
        assert not svc._retrievals[rid].credited and svc.engine.mems[0].hits == 0
        assert svc.n_missed == 0 and svc.tasks.list_tasks(kinds=("recall_miss",)) == []
        svc.tasks._conn.execute("DROP TRIGGER reject_miss")
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET next_run_at=0 WHERE id=?", (row["id"],))
        assert type(svc).process_semantic_tasks(svc)["credited"] == 0
        assert svc._retrievals[rid].credited and svc.n_missed == 1
        assert len(svc.tasks.list_tasks(kinds=("recall_miss",))) == 1
    finally:
        _close(svc)


def test_crash_after_unit_semantic_emission_before_worker(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = r'''
import os,sys
from test_server import _service
svc=_service(sys.argv[1]);svc.cfg.consolidation_on=True
svc.cfg.consolidation_min_items=1;svc.cfg.consolidation_salience_budget=0
svc.process_semantic_tasks=lambda: os._exit(77)
svc.observe('部署在哪','已改到 B 服务器')
'''
    proc = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=root,
                          env={**os.environ, "PYTHONPATH": str(root) + os.pathsep + str(root / "tests")},
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 77, proc.stderr
    svc = _service(tmp_path, texts=())
    try:
        assert svc.log.work(0)["state"] == "done"
        row = svc.tasks.list_tasks(kinds=("maintenance_due",))[0]
        assert row["state"] == "pending"
        svc.cfg.consolidation_min_items = 1
        judge = _Judge(svc.semantics)
        svc.semantics = svc.engine.semantics = judge
        assert svc.process_semantic_tasks()["reflected"] == 1
        assert svc.tasks.list_tasks(kinds=("maintenance_due",))[0]["state"] == "done"
    finally:
        _close(svc)


def test_feedback_for_empty_presented_context_has_no_pending_task(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        rid = svc.recall("部署在哪", budget_tokens=0)["retrieval_id"]
        out = svc.feedback(rid, "部署在哪", "B")
        assert out["pending"] is False and out["n_useful"] == 0
        assert svc.tasks.list_tasks(kinds=("feedback_pending",)) == []
    finally:
        _close(svc)


def test_recognizer_protocol_failure_falls_back_and_is_counted_durably(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        class BadRecognizer:
            def __init__(self, inner):
                self.inner = inner

            def __getattr__(self, name):
                return getattr(self.inner, name)

            def relevant_set(self, texts, question, answer):
                return None

        svc.semantics = svc.engine.semantics = BadRecognizer(svc.semantics)
        result = svc.feedback(rid, "部署在哪", "B")
        assert result["worker"]["recog_fail"] == 1
        assert result["n_useful"] == 1 and not result["pending"]
        assert svc.signals()["semantic"]["recog_fail"] == 1
    finally:
        _close(svc)
    restored = _service(tmp_path, texts=())
    try:
        assert restored.signals()["semantic"]["recog_fail"] == 1
        assert restored.process_semantic_tasks()["recog_fail"] == 0
        assert restored.engine.mems[0].hits == 1
    finally:
        _close(restored)


def test_stale_reflection_requeues_changed_sources_once(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        svc.cfg.consolidation_on = True
        svc.cfg.consolidation_min_items = 1
        svc.cfg.consolidation_salience_budget = 0
        svc.tasks.capacity = 1
        svc.engine._consolidation_pending.add(0)
        svc._commit_sidecar_effect(lambda: svc.engine.step(svc._t))
        judge = _Judge(svc.semantics)
        svc.semantics = svc.engine.semantics = judge
        row = svc.tasks.list_tasks(kinds=("maintenance_due",))[0]
        claim = svc.tasks.claim(row["id"], expected_version=row["version"])
        svc.tasks.store_result(row["id"], claim["token"],
                                        svc._semantic_model(claim))
        svc._commit_sidecar_effect(lambda: setattr(svc.engine.mems[0], "last_seen", svc._t + 1))
        assert svc.process_semantic_tasks()["reflected"] == 0
        rows = svc.tasks.list_tasks(kinds=("maintenance_due",))
        assert [r["state"] for r in rows] == ["done", "pending"]
        assert svc.process_semantic_tasks()["reflected"] == 1
        assert judge.calls == 2
        assert len([m for m in svc.engine.mems.values() if m.kind == "reflection"]) == 1
    finally:
        _close(svc)


def test_conflict_model_result_survives_process_crash_before_effect(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        old = svc.engine.mems[0]
        svc.engine.mems[1] = Memory(1, old.belief_id, "new", "部署在 C 服务器",
                                     old.emb.copy(), birth=svc._t)
        svc.engine._next_id = 2
        svc.engine.add_tension(0, 1, svc._t)
        svc.cfg.tension_delay = 0
        svc._commit_sidecar_effect(lambda: svc.engine.step(svc._t))
    finally:
        _close(svc)
    root = Path(__file__).resolve().parents[1]
    code = r'''
import os,sys
from test_server import _service
from test_semantic_recovery import _Judge
svc=_service(sys.argv[1], texts=())
svc.semantics=svc.engine.semantics=_Judge(svc.semantics)
svc.tasks.complete=lambda *args,**kwargs: os._exit(77)
svc.process_semantic_tasks()
'''
    proc = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=root,
                          env={**os.environ, "PYTHONPATH": str(root) + os.pathsep + str(root / "tests")},
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 77, proc.stderr
    restored = _service(tmp_path, texts=())
    try:
        row = restored.tasks.list_tasks(kinds=("conflict_pending",))[0]
        assert row["state"] == "applying" and row["result"]["verdicts"][0][2] == "update"
        with restored.tasks._conn:
            restored.tasks._conn.execute("UPDATE tasks SET lease_until=0 WHERE id=?", (row["id"],))
        restored._semantic_model = lambda *_: (_ for _ in ()).throw(AssertionError("reran judge"))
        assert restored.process_semantic_tasks()["resolved"] == 1
        assert restored.engine.n_resolve == 1
        assert restored.process_semantic_tasks()["resolved"] == 0
    finally:
        _close(restored)


def test_feedback_model_uses_text_actually_presented_before_memory_changes(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        served = svc._retrievals[rid].presented_texts
        assert served == ("部署在 B 服务器",)
        svc._commit_sidecar_effect(lambda: setattr(svc.engine.mems[0], "text", "后来被修改的内容"))
        class Probe:
            def __init__(self, inner):
                self.inner = inner
                self.seen = None

            def __getattr__(self, name):
                return getattr(self.inner, name)

            def relevant_set(self, texts, question, answer):
                self.seen = texts
                return [True] * len(texts)
        sem = Probe(svc.semantics)
        svc.semantics = svc.engine.semantics = sem
        assert svc.feedback(rid, "部署在哪", "B")["n_useful"] == 1
        assert sem.seen == ["部署在 B 服务器"]
    finally:
        _close(svc)
