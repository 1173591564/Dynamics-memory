"""逐单元 L0 outbox：真实 SQLite、HTTP、并发及 os._exit 后跨库恢复。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from hybrid_memory.candgen.base import CandidateGeneration, MemoryCandidate
from hybrid_memory.logstore import LogStore
from hybrid_memory.taskstore import CheckpointConflict, TaskQueueFull
from test_ouroboros import _svc
from test_server import _http


class Generator:
    def __init__(self, candidates=("unit fact",), scene="新场景"):
        self.candidates = candidates
        self.scene = scene
        self.calls = []

    def generate(self, window, prev_scene=""):
        self.calls.append((window, prev_scene))
        return CandidateGeneration(tuple(MemoryCandidate(x) for x in self.candidates),
                                   self.scene)


def _close(svc):
    svc.stop_unit_recovery()
    svc.tasks.close()
    svc.log.close()


def test_online_registration_is_atomic_and_legacy_units_are_not_replayed(tmp_path):
    log = LogStore(tmp_path / "log.sqlite")
    log.add_unit(3, 5, user_text="legacy", assistant_text="old")
    log._conn.execute("CREATE TRIGGER fail_work BEFORE INSERT ON unit_work "
                      "BEGIN SELECT RAISE(ABORT, 'work failed'); END")
    with pytest.raises(sqlite3.IntegrityError, match="work failed"):
        log.append_unit(6, user_text="new", assistant_text="not accepted")
    assert log.count() == 1 and log.work_stats()["pending"] == 0
    log._conn.execute("DROP TRIGGER fail_work")
    assert log.append_unit(6, user_text="new", assistant_text="accepted")["unit_id"] == 4
    assert log.work(4)["state"] == "pending" and log.work(3) is None
    log.close()
    svc = _svc(tmp_path, generator=Generator(("accepted",)))
    try:
        assert svc.log.pending_units() == [4]
        assert svc.process_pending_units()[4]["candidates"] == 1
        assert svc.log.get(3)["user_text"] == "legacy" and svc.log.work(3) is None
    finally:
        _close(svc)


def test_valid_empty_generation_finishes_without_repeated_model_call(tmp_path):
    gen = Generator((), scene="空候选也是完成")
    svc = _svc(tmp_path, generator=gen)
    try:
        out = svc.observe("在吗", "在")
        assert out["candidates"] == 0 and not out["reasons"]
        assert svc.log.work(0)["state"] == "done"
        assert svc.tasks.unit_receipt(0)["scene"] == "空候选也是完成"
        assert svc.process_pending_units() == {} and len(gen.calls) == 1
        assert svc.signals()["units"] == {"pending": 0, "result_saved": 0,
                                           "failed": 0, "done": 1}
    finally:
        _close(svc)


@pytest.mark.parametrize("stage", ["before_extract", "after_result", "after_effect"])
def test_real_process_exit_recovers_each_cross_db_boundary(tmp_path, stage):
    script = r'''
import os, sys
sys.path.insert(0, 'tests')
from test_observe_recovery import Generator
from test_ouroboros import _svc
svc = _svc(sys.argv[1], generator=Generator(('好的',)))
stage = sys.argv[2]
if stage == 'before_extract':
    svc.generator.generate = lambda *args: os._exit(17)
elif stage == 'after_result':
    svc.tasks.apply_unit = lambda *args: os._exit(17)
else:
    svc.log.finish_work = lambda *args: os._exit(17)
svc.observe('以后统一用 bun 跑脚本', '好的')
'''
    out = subprocess.run([sys.executable, "-c", script, str(tmp_path), stage],
                         cwd=Path(__file__).resolve().parents[1], capture_output=True,
                         timeout=20)
    assert out.returncode == 17, out.stderr.decode()
    gen = Generator(("好的",))
    svc = _svc(tmp_path, generator=gen)
    try:
        row = svc.log.get(0)
        work = svc.log.work(0)
        assert (row["id"], row["t"]) == (0, 0) and work["state"] == "pending"
        assert (work["result"] is not None) is (stage != "before_extract")
        before = svc.tasks.unit_receipt(0)
        assert (before is not None) is (stage == "after_effect")
        svc.start_unit_recovery()  # 模拟 CLI 启动；不挂调查员也能继续
        deadline = time.monotonic() + 5
        while svc.log.work(0)["state"] != "done" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert svc.log.work(0)["state"] == "done"
        assert len(gen.calls) == (1 if stage == "before_extract" else 0)
        assert svc.tasks.queued_counts() == {"extract_due": 1}
        assert svc.tasks.unit_receipt(0)["candidates"] == 1
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].src == {0} and svc.engine.mems[0].evid == 1
        assert svc.log.count() == 1 and svc.process_pending_units() == {}
    finally:
        _close(svc)


def test_saved_result_survives_full_queue_and_retries_without_new_model_call(tmp_path):
    gen = Generator(("好的",))
    svc = _svc(tmp_path, generator=gen)
    try:
        svc.tasks.capacity = 1
        svc.report_miss("already queued")
        with _http(svc) as (post, get, _):
            status, body = post("/observe", {"user_text": "以后统一用 bun 跑脚本",
                                            "assistant_text": "好的"})
            assert status == 503 and "容量" in body["error"]
            counts = get("/signals")[1]["units"]
            assert counts["pending"] == counts["result_saved"] == counts["failed"] == 1
        assert svc.log.count() == 1 and svc.log.work(0)["result"] is not None
        assert not svc.engine.mems and svc.tasks.unit_receipt(0) is None
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET state='done' WHERE kind='recall_miss'")
        svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=0")
        assert svc.process_pending_units()[0]["candidates"] == 1
        assert len(gen.calls) == 1 and len(svc.engine.mems) == 1
        assert svc.tasks.queued_counts() == {"extract_due": 1}
    finally:
        _close(svc)


def test_sql_failure_rolls_back_effect_and_volatile_signal_in_place(tmp_path, monkeypatch):
    gen = Generator(("好的",))
    svc = _svc(tmp_path, generator=gen)
    q = svc.engine.signals
    old = svc.engine.step

    def extra_signal(t):
        old(t)
        q.emit("thin_recall", {"q": "volatile"}, t)

    monkeypatch.setattr(svc.engine, "step", extra_signal)
    svc.tasks._conn.execute("CREATE TRIGGER fail_unit BEFORE INSERT ON unit_receipts "
                            "BEGIN SELECT RAISE(ABORT, 'unit receipt failed'); END")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="unit receipt failed"):
            svc.observe("以后统一用 bun 跑脚本", "好的")
        assert svc.log.work(0)["state"] == "pending"
        assert svc.log.work(0)["result"] is not None
        assert not svc.engine.mems and len(q) == q.n_emitted == 0
        assert svc.tasks.queued_counts() == {} and svc.tasks.checkpoint() == (0, None)
        svc.tasks._conn.execute("DROP TRIGGER fail_unit")
        svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=0")
        svc.process_pending_units()
        assert len(gen.calls) == 1 and len(svc.engine.mems) == 1
        assert svc.tasks.queued_counts() == {"extract_due": 1}
        assert q.peek_kinds() == {}  # 语义 worker 消费；不留失败轮的残影
    finally:
        _close(svc)


def test_duplicate_processing_and_concurrent_observe_do_not_reapply(tmp_path):
    entered, release = threading.Event(), threading.Event()
    gen = Generator(("脚本",))
    original = gen.generate

    def blocked(*args):
        if not gen.calls:
            entered.set()
            assert release.wait(5)
        return original(*args)

    gen.generate = blocked
    svc = _svc(tmp_path, generator=gen)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(svc.observe, "以后统一用 bun 跑脚本", "a")
            try:
                assert entered.wait(5)
                second = pool.submit(svc.observe, "以后统一用 bun 跑脚本 2", "b")
                assert second.result(timeout=5)["pending"] is True
            finally:
                release.set()
            assert first.result(timeout=5)["unit_id"] == 0
        assert svc.log.pending_units() == [1]
        assert svc.process_pending_units()[1]["unit_id"] == 1
        assert len(gen.calls) == 2 and svc.process_pending_units() == {}
        assert svc.tasks.unit_receipt(0) and svc.tasks.unit_receipt(1)
        assert svc.log.work_stats()["done"] == 2
        assert len(svc.tasks.list_tasks(kinds=("extract_due",))) == 2
        # 两次真实单元对同一文本做正常 dedup；并发恢复不额外计证据。
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].src == {0, 1} and svc.engine.mems[0].evid == 2
    finally:
        _close(svc)


def test_correction_keeps_prior_retrieval_even_across_restart(tmp_path):
    from test_server import _service

    svc = _service(tmp_path)
    svc.observe("部署在哪", "已改到 B 服务器")
    rid = svc.recall("部署在哪")["retrieval_id"]
    svc.observe("部署在哪", "B")
    svc.feedback(rid, "部署在哪", "B")
    original = svc.generator.generate

    def stop(*args):
        raise SystemExit("simulated interruption after append")

    svc.generator.generate = stop
    try:
        with pytest.raises(SystemExit):
            svc.observe("不对，现在是 C 服务器", "收到")
    finally:
        svc.generator.generate = original
    uid = 2
    original_unit = svc.log.get(uid)
    assert svc.log.work(uid)["state"] == "pending"
    _close(svc)
    gen = Generator((), "新场景")
    restored = _svc(tmp_path, generator=gen)
    try:
        restored.process_pending_units()
        row = restored.tasks.list_tasks(kinds=("recall_miss",))[0]
        assert row["t"] == original_unit["t"]
        assert row["payload"]["q"] == "部署在哪"
        assert row["payload"]["retrieved"][0]["text"] == "部署在 B 服务器"
        assert restored.log.get(uid) == original_unit
        assert gen.calls[0][1] == original_unit["scene"]
    finally:
        _close(restored)


def test_uncertain_effect_commit_requires_restart(tmp_path, monkeypatch):
    svc = _svc(tmp_path, generator=Generator(("好的",)))
    original = svc.tasks.apply_unit

    def commit_then_lie(*args):
        original(*args)
        raise RuntimeError("commit acknowledgement lost")

    monkeypatch.setattr(svc.tasks, "apply_unit", commit_then_lie)
    try:
        with pytest.raises(RuntimeError, match="acknowledgement"):
            svc.observe("以后统一用 bun 跑脚本", "好的")
        assert svc._checkpoint_fault and svc.log.work(0)["state"] == "pending"
        with pytest.raises(CheckpointConflict):
            svc.save()
    finally:
        _close(svc)
    restored = _svc(tmp_path, generator=Generator(("好的",)))
    try:
        assert restored.process_pending_units()[0]["candidates"] == 1
        assert len(restored.engine.mems) == 1 and restored.engine.mems[0].evid == 1
    finally:
        _close(restored)


def test_handoff_sql_failure_keeps_entire_unit_retriable(tmp_path):
    gen = Generator(("好的",))
    svc = _svc(tmp_path, generator=gen)
    svc.tasks._conn.execute("CREATE TRIGGER fail_handoff BEFORE INSERT ON tasks "
                            "WHEN NEW.kind='extract_due' "
                            "BEGIN SELECT RAISE(ABORT, 'handoff unavailable'); END")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="handoff unavailable"):
            svc.observe("以后统一用 bun 跑脚本", "好的")
        assert svc.tasks.checkpoint() == (0, None)
        assert svc.tasks.unit_receipt(0) is None and not svc.engine.mems
        assert svc.log.work(0)["result"] and svc.log.work(0)["last_error"]
        svc.tasks._conn.execute("DROP TRIGGER fail_handoff")
        svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=0")
        assert svc.process_pending_units()[0]["candidates"] == 1
        assert svc.tasks.queued_counts() == {"extract_due": 1}
        assert len(gen.calls) == 1 and svc.engine.mems[0].src == {0}
    finally:
        _close(svc)


def test_ack_retry_after_later_checkpoint_does_not_repeat_effect(tmp_path, monkeypatch):
    gen = Generator(("好的",))
    svc = _svc(tmp_path, generator=gen)
    original = svc.log.finish_work

    def unavailable(*_):
        raise OSError("log ack unavailable")

    monkeypatch.setattr(svc.log, "finish_work", unavailable)
    try:
        with pytest.raises(OSError, match="log ack"):
            svc.observe("以后统一用 bun 跑脚本", "好的")
        assert svc.log.work(0)["state"] == "pending" and svc.tasks.unit_receipt(0)
        # task checkpoint 可以独立推进；回执检查不可假设 revision 不变。
        svc.save()
        revision = svc._checkpoint_revision
        monkeypatch.setattr(svc.log, "finish_work", original)
        assert svc.process_pending_units()[0]["candidates"] == 1
        assert svc._checkpoint_revision == revision
        assert svc.engine.mems[0].evid == 1 and len(gen.calls) == 1
        assert len(svc.tasks.list_tasks(kinds=("extract_due",))) == 1
    finally:
        _close(svc)


def test_upgrade_creates_work_table_without_replaying_old_rows(tmp_path):
    path = tmp_path / "log.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE units (id INTEGER PRIMARY KEY, t INTEGER NOT NULL, "
                     "ts REAL NOT NULL, scene TEXT NOT NULL DEFAULT '', user_text TEXT NOT NULL, "
                     "assistant_text TEXT NOT NULL, assistant_turns INTEGER NOT NULL DEFAULT 1)")
        conn.execute("INSERT INTO units VALUES (15,24,100.0,'old','legacy','fact',1)")
    store = LogStore(path)
    try:
        assert store.get(15)["ts"] == 100.0
        assert store.work(15) is None and store.pending_units() == []
        assert store.append_unit(0, user_text="new", assistant_text="fact")["unit_id"] == 16
        assert store.work(16)["state"] == "pending"
    finally:
        store.close()


def test_unit_failure_preserves_existing_memory_and_retrieval_identity(tmp_path):
    from test_server import _service

    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        rid = svc.recall("部署在哪")["retrieval_id"]
        old = svc.engine.mems[0]
        svc.tasks._conn.execute("CREATE TRIGGER reject_unit BEFORE INSERT ON unit_receipts "
                                "WHEN NEW.unit_id=1 BEGIN SELECT RAISE(ABORT, 'disk error'); END")
        with pytest.raises(sqlite3.IntegrityError, match="disk error"):
            svc.observe("部署在哪", "仍在 B 服务器")
        assert svc.engine.mems[0] is old and svc._retrievals[rid].selected[0] is old
        assert old.evid == 1 and old.src == {0}
        svc.tasks._conn.execute("DROP TRIGGER reject_unit")
        svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=1")
        svc.process_pending_units()
        assert svc.engine.mems[0] is old and old.evid == 2 and old.src == {0, 1}
    finally:
        _close(svc)


def test_retrying_older_unit_blocks_newer_unit_without_losing_either(tmp_path):
    gen = Generator(("新事实",))
    svc = _svc(tmp_path, generator=gen)
    try:
        svc.tasks.capacity = 1
        svc.report_miss("occupy queue")
        with pytest.raises(TaskQueueFull):
            svc.observe("以后统一用 bun 跑脚本", "好的")
        later = svc.observe("后来再继续", "好的")
        assert later["unit_id"] == 1 and later["pending"]
        assert len(gen.calls) == 1 and not svc.engine.mems
        assert svc.log.pending_units() == [0, 1]
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET state='done' WHERE kind='recall_miss'")
        svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=0")
        done = svc.process_pending_units()
        assert list(done) == [0, 1]
        assert [svc.log.work(i)["state"] for i in (0, 1)] == ["done", "done"]
        assert [svc.log.get(i)["t"] for i in (0, 1)] == [0, 1]
    finally:
        _close(svc)
