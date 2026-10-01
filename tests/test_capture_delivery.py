"""插件捕获回路的 request-id：真实 SQLite/HTTP、并发，以及响应丢失后的重投。"""
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from test_observe_recovery import Generator, _close
from test_ouroboros import _svc
from test_server import _http, _service

from hybrid_memory.logstore import LogStore
from hybrid_memory.taskstore import CaptureConflict, TaskQueueFull

RID = "observe-retry-01"
FID = "feedback-retry-01"


def test_same_observe_request_id_is_one_unit_and_conflict_does_not_rebind(tmp_path):
    svc = _svc(tmp_path, generator=Generator(("一次事实",)))
    try:
        first = svc.observe("统一用 bun", "好的", request_id=RID)
        second = svc.observe("统一用 bun", "好的", request_id=RID)
        assert first["unit_id"] == second["unit_id"] == 0
        assert second["replayed"] is True and second["accepted"] is True
        assert svc.log.count() == 1
        assert svc.log.capture_receipt(RID)["unit_id"] == 0
        with pytest.raises(CaptureConflict):
            svc.observe("另一轮", "不该写入", request_id=RID)
        assert svc.log.count() == 1
        assert svc.observe("另一轮", "没有 id")["unit_id"] == 1
        assert svc.observe("第三轮", "也没有 id")["unit_id"] == 2
        assert svc.log.count() == 3
    finally:
        _close(svc)


def test_capture_receipt_rolls_back_with_the_unit(tmp_path):
    svc = _svc(tmp_path, generator=Generator())
    svc.log._conn.execute(
        "CREATE TRIGGER fail_cap BEFORE INSERT ON capture_receipts "
        "BEGIN SELECT RAISE(ABORT, 'cap failed'); END")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="cap failed"):
            svc.observe("统一用 bun", "好的", request_id=RID)
        assert svc.log.count() == 0 and svc.log.capture_receipt(RID) is None
    finally:
        _close(svc)


def test_http_capacity_503_is_accepted_and_retry_does_not_append(tmp_path):
    svc = _svc(tmp_path, generator=Generator(("好的",)))
    try:
        svc.tasks.capacity = 1
        svc.report_miss("occupy")
        with _http(svc) as (post, _, _):
            status, body = post("/observe", {
                "user_text": "统一用 bun", "assistant_text": "好的", "request_id": RID})
            assert status == 503 and body["accepted"] is True and body["unit_id"] == 0
            assert body["request_id"] == RID and "容量" in body["error"]
            again_status, again = post("/observe", {
                "user_text": "统一用 bun", "assistant_text": "好的", "request_id": RID})
            assert again_status == 200 and again["accepted"] is True and again["replayed"] is True
            assert again["unit_id"] == 0 and again["pending"] is True
            assert post("/observe", {
                "user_text": "不同正文", "assistant_text": "好的", "request_id": RID})[0] == 409
            assert post("/observe", {"user_text": "x", "assistant_text": "y", "request_id": "short"})[0] == 400
            assert post("/observe", {"user_text": "x", "assistant_text": "y", "request_id": ""})[0] == 400
            mismatch = post("/observe", {
                "user_text": "x", "assistant_text": "y", "request_id": "header-body-01"},
                {"X-Request-Id": "header-body-02"})
            assert mismatch[0] == 400
            assert post("/observe", {
                "user_text": "x", "assistant_text": "y", "request_id": 12345678})[0] == 400
        assert svc.log.count() == 1 and svc.tasks.unit_receipt(0) is None
        with svc.tasks._conn:
            svc.tasks._conn.execute("UPDATE tasks SET state='done' WHERE kind='recall_miss'")
        svc.log._conn.execute("UPDATE unit_work SET next_run_at=0 WHERE unit_id=0")
        assert svc.process_pending_units()[0]["candidates"] == 1
        assert len(svc.engine.mems) == 1 and svc.log.count() == 1
    finally:
        _close(svc)


def test_concurrent_same_request_id_appends_once(tmp_path):
    svc = _svc(tmp_path, generator=Generator(("并发事实",)))
    try:
        with _http(svc) as (post, _, _):
            def once(_):
                return post("/observe", {
                    "user_text": "并发", "assistant_text": "一次", "request_id": "concurrent-id-01"})
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(once, range(2)))
        assert svc.log.count() == 1
        assert {status for status, _ in results} == {200}
        assert {body["unit_id"] for _, body in results} == {0}
        assert all(body.get("accepted") for _, body in results)
    finally:
        _close(svc)


def test_process_exit_after_observe_receipt_replays_same_unit(tmp_path):
    script = r'''
import os, sys
sys.path.insert(0, "tests")
from test_observe_recovery import Generator
from test_ouroboros import _svc
svc = _svc(sys.argv[1], generator=Generator(("好的",)))
svc.generator.generate = lambda *args, **kwargs: os._exit(17)
svc.observe("以后统一用 bun", "好的", request_id="observe-exit-01")
'''
    out = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, timeout=20, check=False)
    assert out.returncode == 17, out.stderr.decode()
    svc = _svc(tmp_path, generator=Generator(("好的",)))
    try:
        replay = svc.observe("以后统一用 bun", "好的", request_id="observe-exit-01")
        assert replay["unit_id"] == 0 and replay["replayed"] is True and replay["accepted"] is True
        assert svc.log.count() == 1 and len(svc.engine.mems) == 1
        assert svc.engine.mems[0].src == {0}
        assert svc.tasks.queued_counts() == {"extract_due": 1}
        assert svc.observe("以后统一用 bun", "好的", request_id="observe-exit-01")["replayed"] is True
        assert len(svc.engine.mems) == 1 and svc.log.count() == 1
    finally:
        _close(svc)


def test_feedback_receipt_survives_response_loss_and_eviction(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        def no_worker():
            return {}
        svc.process_semantic_tasks = no_worker
        first = svc.feedback(rid, "部署在哪", "B", request_id=FID)
        assert first["accepted"] is True and not first.get("replayed")
        assert svc.tasks.list_tasks(kinds=("feedback_pending",)).__len__() == 1
        svc._retrievals.pop(rid)
        replay = svc.feedback(rid, "部署在哪", "B", request_id=FID)
        assert replay["replayed"] is True and replay["accepted"] is True
        assert len(svc.tasks.list_tasks(kinds=("feedback_pending",))) == 1
        with pytest.raises(CaptureConflict):
            svc.feedback(rid, "部署在哪", "另一答案", request_id=FID)
        assert len(svc.tasks.list_tasks(kinds=("feedback_pending",))) == 1
    finally:
        _close(svc)


def test_process_exit_after_feedback_commit_replays_without_second_task(tmp_path):
    script = r'''
import os, sys
sys.path.insert(0, "tests")
from test_server import _service
svc = _service(sys.argv[1])
svc.observe("部署在哪", "已改到 B 服务器")
rid = svc.recall("部署在哪")["retrieval_id"]
svc.process_semantic_tasks = lambda: os._exit(17)
svc.feedback(rid, "部署在哪", "B", request_id="feedback-exit-01")
'''
    out = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, timeout=20, check=False)
    assert out.returncode == 17, out.stderr.decode()
    svc = _service(tmp_path, texts=())
    try:
        rid = next(iter(svc._retrievals))
        replay = svc.feedback(rid, "部署在哪", "B", request_id="feedback-exit-01")
        assert replay["replayed"] is True and replay["accepted"] is True
        assert len(svc.tasks.list_tasks(kinds=("feedback_pending",))) == 1
        svc._retrievals.clear()
        assert svc.feedback(rid, "部署在哪", "B", request_id="feedback-exit-01")["replayed"] is True
        assert len(svc.tasks.list_tasks(kinds=("feedback_pending",))) == 1
    finally:
        _close(svc)


def test_old_log_database_gains_capture_table_without_replaying_units(tmp_path):
    path = tmp_path / "log.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE units (id INTEGER PRIMARY KEY, t INTEGER NOT NULL, ts REAL NOT NULL, "
            "scene TEXT NOT NULL DEFAULT '', user_text TEXT NOT NULL, assistant_text TEXT NOT NULL, "
            "assistant_turns INTEGER NOT NULL DEFAULT 1)")
        conn.execute("INSERT INTO units VALUES (7, 9, 1.0, 'old', 'legacy', 'fact', 1)")
    store = LogStore(path)
    try:
        assert store.capture_receipt("missing-id") is None
        added = store.append_unit(0, user_text="new", assistant_text="fact",
                                   capture_id="upgrade-id-01", capture_fingerprint="abc")
        assert added["unit_id"] == 8 and store.capture_receipt("upgrade-id-01")["unit_id"] == 8
        assert store.get(7)["user_text"] == "legacy"
    finally:
        store.close()


def test_feedback_capacity_failure_keeps_no_receipt(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        svc.tasks.capacity = 1
        svc.report_miss("occupy")
        with pytest.raises(TaskQueueFull):
            svc.feedback(rid, "部署在哪", "B", request_id=FID)
        assert svc.tasks.read_capture(FID) is None
        assert not svc._retrievals[rid].feedback_sent
        assert svc.tasks.list_tasks(kinds=("feedback_pending",)) == []
    finally:
        _close(svc)


def test_http_feedback_retry_and_already_credited_are_distinct(tmp_path):
    svc, rid = _prepared(tmp_path)
    try:
        with _http(svc) as (post, _, _):
            status, body = post("/feedback", {
                "retrieval_id": rid, "question": "部署在哪", "answer": "B", "request_id": FID})
            assert status == 200 and body["accepted"] is True and body["request_id"] == FID
            again_status, again = post("/feedback", {
                "retrieval_id": rid, "question": "部署在哪", "answer": "B", "request_id": FID})
            assert again_status == 200 and again["replayed"] is True
            other = post("/feedback", {
                "retrieval_id": rid, "question": "部署在哪", "answer": "B",
                "request_id": "feedback-other-01"})
            assert other[0] == 409 and other[1]["accepted"] is True
            assert "already" in other[1]["error"]
        assert len(svc.tasks.list_tasks(kinds=("feedback_pending",))) == 1
    finally:
        _close(svc)


def _prepared(tmp_path):
    svc = _service(tmp_path)
    svc.observe("部署在哪", "已改到 B 服务器")
    return svc, svc.recall("部署在哪")["retrieval_id"]
