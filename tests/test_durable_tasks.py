"""真实 SQLite + 服务重启/故障注入：调查状态与幂等写回，不调用外部模型。"""
import pickle

import pytest

from hybrid_memory.agent.investigator import Investigation
from hybrid_memory.agent.loop import AgentWorker
from test_ouroboros import _svc, _fake


PROPOSAL = {"text": "服务端口是 8080。", "source_unit_ids": [0]}


def _queued(path=None):
    svc = _svc(path)
    svc.log.add_unit(0, 0, user_text="端口", assistant_text="8080")
    svc.report_miss("端口是多少")
    return svc


def _close(svc):
    svc.tasks.close()
    svc.log.close()


def test_emitted_task_survives_restart_without_save_or_worker(tmp_path):
    svc = _queued(tmp_path)
    _close(svc)
    restored = _svc(tmp_path)
    try:
        agent = AgentWorker(restored, _fake(proposals=[PROPOSAL]))
        assert agent.process_once()["accepted"] == 1
        assert restored.tasks.list_tasks()[0]["state"] == "done"
    finally:
        _close(restored)


def test_queue_eviction_does_not_drop_durable_jobs():
    svc = _svc(signal_queue_cap=1)
    for i in range(4):
        svc.report_miss(f"question {i}")
    assert len(svc.engine.signals) == 1
    agent = AgentWorker(svc, _fake(diagnosis={"miss_type": "no_miss"}))
    assert agent.process_once()["run"] == 4
    assert len(svc.tasks.list_tasks(states=("done",))) == 4


def test_apply_failure_keeps_result_and_rest_of_batch(tmp_path, monkeypatch):
    svc = _queued(tmp_path)
    svc.report_miss("second task")
    fake = _fake(proposals=[PROPOSAL])
    agent = AgentWorker(svc, fake)
    original = svc.engine.propose
    failures = [True]

    def fail_once(events, t):
        if failures:
            failures.pop()
            # 确认失败能回滚部分内存修改，而不是只保护 SQLite。
            original(events, t)
            raise RuntimeError("apply failed after mutation")
        return original(events, t)

    monkeypatch.setattr(svc.engine, "propose", fail_once)
    stats = agent.process_once()
    assert stats["failed"] == 1 and stats["run"] == 2
    rows = svc.tasks.list_tasks()
    assert [r["state"] for r in rows] == ["ready", "done"]
    assert rows[0]["result"] is not None
    assert len(svc.engine.mems) == 1 and next(iter(svc.engine.mems.values())).evid == 1
    assert agent.process_once()["run"] == 0  # 重试保存的产物，不再问模型
    assert len(fake.calls) == 2
    assert all(r["state"] == "done" for r in svc.tasks.list_tasks())


def test_partial_result_retry_does_not_repeat_first_effect_or_diagnosis(tmp_path, monkeypatch):
    svc = _queued(tmp_path)
    second = {"text": "部署在 B 服务器", "source_unit_ids": [0]}
    fake = _fake(proposals=[PROPOSAL, second], diagnosis={"miss_type": "too_coarse"})
    agent = AgentWorker(svc, fake)
    original = svc.engine.propose

    def fail_second(events, t):
        if events[0].text == second["text"]:
            raise RuntimeError("second proposal failed")
        return original(events, t)

    monkeypatch.setattr(svc.engine, "propose", fail_second)
    assert agent.process_once()["failed"] == 1
    assert svc.n_proposals == 1
    _close(svc)
    restored = _svc(tmp_path)
    try:
        never = _fake()
        resumed = AgentWorker(restored, never)
        assert resumed.process_once()["run"] == 0
        assert never.calls == []
        assert restored.n_proposals == 2
        assert all(m.evid == 1 for m in restored.engine.mems.values())
        assert restored.miss_counts == {"too_coarse": 1}
        assert resumed.process_once()["taken"] == 0
    finally:
        _close(restored)


def test_effect_checkpoint_precedes_ack_and_is_not_lost_to_stale_pickle(tmp_path, monkeypatch):
    svc = _queued(tmp_path)
    svc.save()  # 此文件刻意保留在任务效果之前
    def fail_ack(*args, **kwargs):
        raise RuntimeError("ack unavailable")

    monkeypatch.setattr(svc.tasks, "finish", fail_ack)
    agent = AgentWorker(svc, _fake(proposals=[PROPOSAL], diagnosis={"miss_type": "no_miss"}))
    assert agent.process_once()["failed"] == 1
    assert svc.n_proposals == 1 and svc.miss_counts == {"no_miss": 1}
    _close(svc)
    restored = _svc(tmp_path)
    try:
        fake = _fake()
        assert AgentWorker(restored, fake).process_once()["run"] == 0
        assert not fake.calls and restored.n_proposals == 1
        assert next(iter(restored.engine.mems.values())).evid == 1
        assert restored.miss_counts == {"no_miss": 1}
        assert restored.tasks.list_tasks()[0]["state"] == "done"
    finally:
        _close(restored)


def test_daily_cap_and_dedupe_survive_restart(tmp_path):
    svc = _queued(tmp_path)
    AgentWorker(svc, _fake(diagnosis={"miss_type": "no_miss"}), daily_cap=1).process_once()
    _close(svc)
    restored = _svc(tmp_path)
    try:
        restored.report_miss("端口是多少")
        restored.report_miss("different question")
        fake = _fake()
        out = AgentWorker(restored, fake, daily_cap=1).process_once()
        assert out["skipped"] == 1 and out["run"] == 0 and out["deferred"] == 1
        assert not fake.calls
    finally:
        _close(restored)


def test_investigation_attempts_are_durable_and_exhaustion_is_visible(tmp_path):
    svc = _queued(tmp_path)
    agent = AgentWorker(svc, lambda _: None, max_attempts=2)
    assert agent.process_once()["failed"] == 1
    _close(svc)
    restored = _svc(tmp_path)
    try:
        agent = AgentWorker(restored, lambda _: None, max_attempts=2)
        assert agent.process_once()["failed"] == 1
        row = restored.tasks.list_tasks()[0]
        assert row["state"] == "dead" and row["attempts"] == 2
        assert row["last_error"]
        assert agent.process_once()["taken"] == 0
    finally:
        _close(restored)


def test_tool_and_final_proposal_and_diagnosis_are_idempotent_within_task(tmp_path):
    svc = _queued(tmp_path)

    def investigate(payload):
        sid = payload["signal_id"]
        svc.propose([PROPOSAL], signal_id=sid)
        svc.diagnose("no_miss", "same", signal_id=sid)
        return Investigation(proposals=[dict(PROPOSAL, kind="work_fact", salience=0.5,
                                             entity_key="", supersedes=[])],
                             diagnosis={"miss_type": "no_miss", "note": "same"})

    AgentWorker(svc, investigate).process_once()
    assert svc.n_proposals == 1 and next(iter(svc.engine.mems.values())).evid == 1
    assert svc.miss_counts == {"no_miss": 1}


@pytest.mark.parametrize("corruption", ["blob", "missing"])
def test_durable_checkpoint_corruption_fails_closed(tmp_path, corruption):
    svc = _queued(tmp_path)
    AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once()
    with svc.tasks._conn:
        if corruption == "blob":
            svc.tasks._conn.execute("UPDATE checkpoint SET state=?", (b"broken",))
        else:
            svc.tasks._conn.execute("DELETE FROM checkpoint")
    _close(svc)
    with pytest.raises(RuntimeError, match="checkpoint"):
        _svc(tmp_path)


def test_expired_running_lease_recovers_and_rejects_old_token(tmp_path):
    from hybrid_memory.investigation_context import InvestigationContext
    from hybrid_memory.taskstore import TaskLeaseLost

    svc = _queued(tmp_path)
    agent = AgentWorker(svc, _fake(), lease_s=1)
    claimed = agent._claim(svc.tasks.list_tasks()[0])
    deadline = claimed["lease_until"]
    _close(svc)  # 模拟领取后进程消失，没有显式 retry/finish
    restored = _svc(tmp_path)
    try:
        restored.tasks.clock = lambda: deadline + 1
        fake = _fake(proposals=[PROPOSAL])
        out = AgentWorker(restored, fake).process_once()
        assert out["run"] == 1 and out["accepted"] == 1
        assert restored.tasks.list_tasks()[0]["attempts"] == 2
        ctx = InvestigationContext("old", 1, "repair", claimed["id"], claimed["token"])
        with pytest.raises(TaskLeaseLost):
            restored.propose([PROPOSAL], _context=ctx)
        assert restored.n_proposals == 1
    finally:
        _close(restored)


def test_expired_applying_lease_replays_receipt_not_effect(tmp_path):
    from dataclasses import asdict
    from hybrid_memory.investigation_context import InvestigationContext

    svc = _queued(tmp_path)
    agent = AgentWorker(svc, _fake(), lease_s=1)
    row = agent._claim(svc.tasks.list_tasks()[0])
    svc.tasks.store_result(row["id"], row["token"], {
        "investigation": asdict(Investigation(proposals=[PROPOSAL])), "usage": {}, "signal_id": "old"})
    row = agent._claim(svc.tasks.get(row["id"]))
    ctx = InvestigationContext("old", 1, "repair", row["id"], row["token"])
    svc.propose([PROPOSAL], _context=ctx)
    _close(svc)
    restored = _svc(tmp_path)
    try:
        restored.tasks.clock = lambda: row["lease_until"] + 1
        fake = _fake()
        out = AgentWorker(restored, fake, daily_cap=0).process_once()
        assert out["run"] == out["accepted"] == 0 and not fake.calls
        assert restored.n_proposals == 1
        assert next(iter(restored.engine.mems.values())).evid == 1
        row = restored.tasks.get(row["id"])
        assert row["state"] == "done" and row["apply_attempts"] == 2
    finally:
        _close(restored)


def test_sqlite_receipt_failure_rolls_back_checkpoint_and_preserves_memory_identity(tmp_path):
    svc = _queued(tmp_path)
    svc.propose([PROPOSAL])
    ret_id = svc.recall("服务端口是 8080。")["retrieval_id"]
    original_mem = svc.engine.mems[0]
    assert svc._retrievals[ret_id].selected[0] is original_mem
    svc.tasks._conn.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON operations "
                            "BEGIN SELECT RAISE(ABORT, 'receipt failed'); END")
    fake = _fake(proposals=[PROPOSAL])
    agent = AgentWorker(svc, fake)
    assert agent.process_once()["failed"] == 1
    assert svc.engine.mems[0] is original_mem
    assert svc._retrievals[ret_id].selected[0] is original_mem
    assert original_mem.evid == 1 and svc.n_proposals == 1
    assert svc.tasks.stats()["operations"] == 0
    svc.tasks._conn.execute("DROP TRIGGER fail_receipt")
    assert agent.process_once()["run"] == 0
    assert original_mem.evid == 2 and svc.n_proposals == 2
    assert len(fake.calls) == 1


def test_uncertain_commit_stops_service_until_restart(tmp_path, monkeypatch):
    from hybrid_memory.taskstore import CheckpointConflict

    svc = _queued(tmp_path)
    original = svc.tasks.apply_operation

    def commit_then_raise(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("lost commit acknowledgement")

    monkeypatch.setattr(svc.tasks, "apply_operation", commit_then_raise)
    assert AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once()["failed"] == 1
    assert svc._checkpoint_fault
    from test_server import _http
    post, get, stop = _http(svc)
    try:
        status, health = get("/health")
        assert status == 503 and not health["ok"] and health["checkpoint_fault"]
    finally:
        stop()
    with pytest.raises(CheckpointConflict):
        svc.save()
    with pytest.raises(CheckpointConflict):
        svc.observe("new", "must not run")
    _close(svc)
    restored = _svc(tmp_path)
    try:
        assert restored.n_proposals == 1
        assert AgentWorker(restored, _fake()).process_once()["run"] == 0
        assert restored.n_proposals == 1
        assert restored.tasks.list_tasks()[0]["state"] == "done"
    finally:
        _close(restored)


def test_retry_backoff_and_application_exhaustion_are_durable(tmp_path, monkeypatch):
    svc = _queued(tmp_path)
    now = [100.0]
    svc.tasks.clock = lambda: now[0]
    fake = _fake(proposals=[PROPOSAL])

    def boom(*args, **kwargs):
        raise RuntimeError("permanent embedding outage")

    monkeypatch.setattr(svc.engine, "propose", boom)
    agent = AgentWorker(svc, fake, max_apply_attempts=2, retry_delay_s=5)
    assert agent.process_once()["failed"] == 1
    assert agent.process_once()["deferred"] == 1
    now[0] += 6
    assert agent.process_once()["failed"] == 1
    row = svc.tasks.list_tasks()[0]
    assert row["state"] == "dead" and row["apply_attempts"] == 2
    assert row["result"] is not None and len(fake.calls) == 1
    assert "permanent embedding outage" in row["last_error"]
    _close(svc)
    restored = _svc(tmp_path)
    try:
        assert AgentWorker(restored, _fake()).process_once()["taken"] == 0
        assert restored.signals()["tasks"]["dead"] == 1
    finally:
        _close(restored)


def test_signal_merge_is_durable_but_running_task_payload_is_frozen(tmp_path):
    svc = _queued(tmp_path)
    svc.report_miss("端口是多少", hint="before claim")
    assert len(svc.tasks.list_tasks()) == 1
    seen = []

    def investigate(payload):
        seen.append(payload)
        if len(seen) == 1:
            svc._t = 5
            svc.report_miss("端口是多少", hint="arrived during investigation")
        return Investigation(diagnosis={"miss_type": "no_miss"})

    agent = AgentWorker(svc, investigate)
    assert agent.process_once()["run"] == 1
    assert agent.process_once()["run"] == 1  # 不因前一任务刚完成而丢掉在途新事件
    assert seen[0]["before"] == 1 and seen[1]["before"] == 6
    assert seen[0]["hints"] == ["before claim"]
    assert seen[1]["hints"] == ["arrived during investigation"]


def test_enqueue_failure_does_not_mutate_volatile_signal_or_claim_success():
    import sqlite3

    svc = _queued()
    svc.report_miss("端口是多少", hint="original")
    before = pickle.dumps(svc.engine.signals._items)
    missed = svc.n_missed
    svc.tasks._conn.execute("CREATE TRIGGER fail_enqueue BEFORE UPDATE ON tasks "
                            "BEGIN SELECT RAISE(ABORT, 'enqueue failed'); END")
    with pytest.raises(sqlite3.IntegrityError):
        svc.report_miss("端口是多少", hint="not committed")
    assert pickle.dumps(svc.engine.signals._items) == before
    assert svc.n_missed == missed
    assert svc.tasks.list_tasks()[0]["payload"]["hints"] == ["original"]


def test_normal_save_after_task_updates_authoritative_checkpoint(tmp_path):
    svc = _queued(tmp_path)
    AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once()
    svc.propose([{"text": "新保存的独立事实", "source_unit_ids": [0]}])
    svc.save()
    # SQLite 已是事实源，兼容导出丢失不会使任务效果/后续 save 回退。
    (tmp_path / "state.pkl").unlink()
    _close(svc)
    restored = _svc(tmp_path)
    try:
        assert restored.n_proposals == 2 and len(restored.engine.mems) == 2
        assert restored.tasks.list_tasks()[0]["state"] == "done"
    finally:
        _close(restored)


def test_result_retry_keeps_original_bound_even_if_worker_configuration_changes(tmp_path, monkeypatch):
    svc = _queued(tmp_path)
    svc.log.add_unit(1, 8, user_text="future", assistant_text="not allowed")
    fake = _fake(proposals=[PROPOSAL, {"text": "未来的事实", "source_unit_ids": [1]}])
    monkeypatch.setattr(svc.engine, "propose", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("retry")))
    assert AgentWorker(svc, fake).process_once()["failed"] == 1
    _close(svc)
    restored = _svc(tmp_path)
    try:
        out = AgentWorker(restored, _fake(), before_for=lambda sig: 999).process_once()
        assert out["run"] == 0 and out["accepted"] == 1
        assert restored.n_rejected == 1
        assert restored.tasks.list_tasks()[0]["before_t"] == 1
        assert next(iter(restored.engine.mems.values())).origin == "repair"
    finally:
        _close(restored)


def test_verdict_receipt_prevents_repeated_aggregation_on_ack_retry(tmp_path, monkeypatch):
    from test_ouroboros import _ev

    svc = _queued(tmp_path)
    a = svc.engine.propose([_ev("部署在 A")], 0)[0]
    b = svc.engine.propose([_ev("部署在 B")], 0)[0]
    original = svc.tasks.finish
    monkeypatch.setattr(svc.tasks, "finish", lambda *a: (_ for _ in ()).throw(RuntimeError("ack")))
    agent = AgentWorker(svc, _fake(verdicts=[(a, b, "contradiction")]))
    assert agent.process_once()["failed"] == 1
    assert svc.engine.n_agg == 1 and len(svc.engine.mems) == 3
    monkeypatch.setattr(svc.tasks, "finish", original)
    assert agent.process_once()["run"] == 0
    assert svc.engine.n_agg == 1 and len(svc.engine.mems) == 3


@pytest.mark.parametrize("point", ["result", "effect", "uncommitted_effect"])
def test_actual_process_exit_recovers_without_duplicate_effect(tmp_path, point):
    import subprocess
    import sys
    from pathlib import Path

    script = r'''
import os, runpy, sys
from hybrid_memory.agent.investigator import Investigation
from hybrid_memory.agent.loop import AgentWorker
svc = runpy.run_path('tests/test_ouroboros.py')['_svc'](sys.argv[1])
svc.log.add_unit(0, 0, user_text='port', assistant_text='8080')
svc.report_miss('port?')
point = sys.argv[2]
if point == 'uncommitted_effect':
    original = svc.engine.propose
    def kill(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(17)
    svc.engine.propose = kill
else:
    name = 'store_result' if point == 'result' else 'apply_operation'
    original = getattr(svc.tasks, name)
    def kill(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(17)
    setattr(svc.tasks, name, kill)
AgentWorker(svc, lambda _: Investigation(proposals=[
    {'text': '服务端口是 8080。', 'source_unit_ids': [0]}]), lease_s=1).process_once()
'''
    out = subprocess.run([sys.executable, "-c", script, str(tmp_path), point],
                         cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=20)
    assert out.returncode == 17, out.stderr.decode()
    restored = _svc(tmp_path)
    try:
        row = restored.tasks.list_tasks()[0]
        if row["lease_until"] is not None:
            restored.tasks.clock = lambda: row["lease_until"] + 1
        fake = _fake()
        assert AgentWorker(restored, fake).process_once()["run"] == 0
        assert not fake.calls
        assert restored.tasks.list_tasks()[0]["state"] == "done"
        assert restored.n_proposals == 1
        assert len(restored.engine.mems) == 1 and restored.engine.mems[0].evid == 1
        assert restored.tasks.stats()["operations"] == 1
    finally:
        _close(restored)


def test_stop_timeout_does_not_hide_live_thread_or_start_duplicate():
    import threading

    svc = _queued()
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def investigate(payload):
        calls.append(payload)
        entered.set()
        assert release.wait(5)
        return Investigation(diagnosis={"miss_type": "no_miss"})

    original = svc.tasks.finish

    def finish(*args):
        original(*args)
        finished.set()

    svc.tasks.finish = finish
    agent = AgentWorker(svc, investigate, idle_s=0.01)
    agent.start()
    try:
        assert entered.wait(5)
        thread = agent._thread
        agent.stop(timeout=0)
        assert agent.stats()["alive"] and agent._thread is thread
        agent.start()
        assert agent._thread is thread
    finally:
        release.set()
        agent.stop(timeout=5)
    assert svc.tasks.list_tasks()[0]["state"] == "ready"
    agent.start()
    try:
        assert finished.wait(5)
        assert len(calls) == 1 and svc.miss_counts == {"no_miss": 1}
    finally:
        agent.stop()


def test_task_queue_full_is_explicit_http_backpressure():
    from test_server import _http

    svc = _queued()
    svc.tasks.capacity = 1
    post, get, stop = _http(svc)
    try:
        status, out = post("/miss", {"query": "another task"})
        assert status == 503 and "容量" in out["error"]
        assert svc.n_missed == 1 and len(svc.tasks.list_tasks()) == 1
    finally:
        stop()


def test_pending_task_reserves_referenced_memory_ids_before_any_checkpoint(tmp_path):
    svc = _svc(tmp_path)
    svc.log.add_unit(0, 0, user_text="port", assistant_text="8080")
    old = svc.propose([PROPOSAL])["new_ids"][0]
    svc.report_miss("old memory may be missing after crash")
    _close(svc)  # 从未 save，也没有 worker 领取
    restored = _svc(tmp_path)
    try:
        assert not restored.engine.mems
        new = restored.propose([{"text": "完全不同的新条目", "source_unit_ids": [0]}])["new_ids"][0]
        assert new > old  # 持久任务的旧引用不能指到重用编号后的另一个事实
    finally:
        _close(restored)


def test_result_and_current_memory_checkpoint_are_saved_together(tmp_path, monkeypatch):
    svc = _queued(tmp_path)
    original = svc.tasks.store_result

    def store_then_interrupt(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("stopped after result commit")

    monkeypatch.setattr(svc.tasks, "store_result", store_then_interrupt)

    def investigate(payload):
        # 模拟任务领取以后主回路新增、可能被调查工具引用的记忆。
        svc.propose([PROPOSAL])
        return Investigation(diagnosis={"miss_type": "no_miss"})

    assert AgentWorker(svc, investigate).process_once()["failed"] == 1
    _close(svc)
    restored = _svc(tmp_path)
    try:
        assert len(restored.engine.mems) == 1 and restored.n_proposals == 1
        assert AgentWorker(restored, _fake()).process_once()["run"] == 0
        assert restored.miss_counts == {"no_miss": 1}
    finally:
        _close(restored)


def test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from hybrid_memory.candgen.base import CandidateGeneration
    from hybrid_memory.server import triggers
    from hybrid_memory.taskstore import CheckpointConflict

    svc = _queued()
    entered, release = threading.Event(), threading.Event()

    class BlockedGenerator:
        def generate(self, *args):
            entered.set()
            assert release.wait(5)
            return CandidateGeneration(candidates=(), scene_name="must not publish")

    svc.generator = BlockedGenerator()
    monkeypatch.setattr(triggers, "scan_unit", lambda *args: [])
    original = svc.tasks.apply_operation

    def commit_then_raise(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("uncertain commit")

    monkeypatch.setattr(svc.tasks, "apply_operation", commit_then_raise)
    with ThreadPoolExecutor(max_workers=1) as pool:
        observe = pool.submit(svc.observe, "hello", "world")
        try:
            assert entered.wait(5)
            AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once()
            assert svc._checkpoint_fault
        finally:
            release.set()
        with pytest.raises(CheckpointConflict):
            observe.result(timeout=5)
    assert svc._scene != "must not publish" and svc.log.count() == 2


def test_oversized_saved_result_is_visible_failure_not_silently_truncated():
    svc = _queued()
    fake = _fake(proposals=[dict(PROPOSAL) for _ in range(51)])
    out = AgentWorker(svc, fake, max_apply_attempts=1).process_once()
    assert out["failed"] == 1 and svc.n_proposals == 0 and not svc.engine.mems
    row = svc.tasks.list_tasks()[0]
    assert row["state"] == "dead" and "limit 50" in row["last_error"]
    assert len(row["result"]["investigation"]["proposals"]) == 51
