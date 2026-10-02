"""TaskStore 双状态机 characterization（P3/A4）：冻结现状，合并后逐字节比对。

冻结范围：合法流的任务状态序列 / checkpoint revision 序列 / 效果与回执。
不冻结：已删除方法的误用错误（kind-guard 类 TaskLeaseLost 不在冻结范围——
P3 exit 要求删方法，API 形状变化是既定的）；token 取随机值，统一归一化；
时钟只前进（ManualClock），sqlite id 自增，均确定。

运行：默认比对 `snapshots/*.json`（缺失即红）；`FREEZE_CHAR=1` 重冻快照。
P3 合并后只改本文件底部的 API 绑定 helper（old→new），场景脚本与快照不动——
快照逐字节一致即证明合并零行为差。本套件是临时套件，P6 末删除（H23 唯一允许的删）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hybrid_memory.store.tasks import (SEMANTIC_KINDS, WORKFLOW_KINDS,
                                     CaptureConflict, CheckpointConflict,
                                     TaskLeaseLost, TaskQueueFull, TaskStore)

SNAP_DIR = Path(__file__).resolve().parent / "snapshots"
FREEZE = os.environ.get("FREEZE_CHAR") == "1"


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _norm_row(store: TaskStore, tid: int) -> dict:
    row = store.get(tid)
    row["token"] = "<tok>" if row["token"] else None
    return row


def _snap_state(store: TaskStore) -> dict:
    try:
        rev, blob = store.checkpoint()
        ckpt_err = None
    except CheckpointConflict as exc:
        # B 流不写 checkpoint，读即弹冲突——这本身就是被冻结的行为。
        rev, blob, ckpt_err = None, None, f"CheckpointConflict: {exc}"
    return {
        "tasks": [_norm_row(store, r["id"])
                  for r in store.list_tasks()],
        "revision": rev,
        "checkpoint": blob.decode() if blob else None,
        "checkpoint_error": ckpt_err,
        "counts": store.stats(),
        "queued": store.queued_counts(),
    }


class Rec:
    """场景记录器：每步记 {op, out, state}，out 中 token/异常归一化。"""

    def __init__(self, store: TaskStore) -> None:
        self.store = store
        self.steps: list[dict] = []

    def op(self, name: str, out=None) -> None:
        self.steps.append({"op": name, "out": _norm_out(out),
                           "state": _snap_state(self.store)})


def _norm_out(out):
    if isinstance(out, dict):
        out = dict(out)
        if out.get("token"):
            out["token"] = "<tok>"
        return out
    if isinstance(out, tuple) and len(out) == 2 and isinstance(out[1], int):
        return [out[0], out[1]]  # (response, revision)
    if isinstance(out, Exception):
        return f"{type(out).__name__}: {out}"
    return out


def _check(name: str, rec: Rec) -> None:
    SNAP_DIR.mkdir(exist_ok=True)
    text = json.dumps(rec.steps, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    path = SNAP_DIR / f"{name}.json"
    if FREEZE:
        path.write_text(text, encoding="utf-8")
        print(f"froze {path} ({len(rec.steps)} steps)")
        return
    if not path.is_file():
        pytest.fail(f"缺快照 {path.name}，先跑 FREEZE_CHAR=1 重冻")
    want = path.read_text(encoding="utf-8")
    if text != want:
        wl, tl = want.splitlines(), text.splitlines()
        diff = [f"line {n}: snap={a!r} live={b!r}"
                for n, (a, b) in enumerate(zip(wl, tl)) if a != b][:5]
        if len(wl) != len(tl):
            diff.append(f"行数 snap={len(wl)} live={len(tl)}")
        pytest.fail(f"{name} 与快照逐字节不一致:\n" + "\n".join(diff))


def _store() -> tuple[TaskStore, Clock]:
    clock = Clock()
    return TaskStore(clock=clock), clock


# ------------------------------------------------------- A 机（调查类）


def test_char_a_lifecycle():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("recall_miss", {"q": "one"}, 0, key="q")
        rec.op("enqueue", tid)
        row = _claim_a(store, tid, before=5, rev=0)
        rec.op("claim", row)
        rev = store.store_result(tid, row["token"], {"answer": "x"},
                                 checkpoint=b"state-2", expected_revision=1)
        rec.op("store_result", rev)
        row2 = _claim_a(store, tid, before=9, rev=2)
        assert row2["state"] == "applying" and row2["before_t"] == 5
        rec.op("claim_applying", row2)
        store.finish(tid, row2["token"])
        rec.op("finish", None)
        _check("a_lifecycle", rec)
    finally:
        store.close()


def test_char_a_retry_dead():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("extract_due", {"u": 1}, 0)
        rec.op("enqueue", tid)
        for i in range(3):
            row = _claim_a(store, tid, rev=store.checkpoint()[0])
            if row is None:
                rec.op(f"claim{i}", None)
                break
            rec.op(f"claim{i}", {"state": row["state"], "attempts": row["attempts"]})
            st = store.retry(tid, row["token"], f"boom{i}",
                             max_attempts=2, max_apply_attempts=3, delay=10)
            rec.op(f"retry{i}", st)
            clock.advance(11)
        assert store.get(tid)["state"] == "dead"
        _check("a_retry_dead", rec)
    finally:
        store.close()


def test_char_a_recover_and_gates():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("recall_miss", {}, 0)
        row = _claim_a(store, tid, lease_s=10, rev=0)
        rec.op("claim", row["state"])
        clock.advance(11)
        _recover_a(store, 3, 3)
        rec.op("recover_expired", store.get(tid)["state"])
        # version 失配 / daily_cap / next_run_at 门
        row2 = _claim_a(store, tid, rev=1)
        store.retry(tid, row2["token"], "x", max_attempts=3,
                    max_apply_attempts=3, delay=100)
        rec.op("retry_delay100", store.get(tid)["next_run_at"])
        assert _claim_a(store, tid, rev=1) is None
        rec.op("claim_gated_by_next_run_at", None)
        clock.advance(101)
        assert _claim_a(store, tid, rev=1, expected_version=999) is None
        rec.op("claim_version_mismatch", None)
        assert _claim_a(store, tid, rev=1, daily_cap=0) is None
        rec.op("claim_daily_cap", None)
        try:
            store.store_result(tid, "bad-token", {}, checkpoint=b"s",
                               expected_revision=1)
        except TaskLeaseLost as exc:
            rec.op("store_bad_token", exc)
        _check("a_recover_and_gates", rec)
    finally:
        store.close()


def test_char_a_pending_at_limit_dead_and_skip():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("recall_miss", {"q": "d"}, 0, key="dedupe")
        for i in range(2):
            row = _claim_a(store, tid, rev=i)
            store.retry(tid, row["token"], "e", max_attempts=3,
                        max_apply_attempts=3)
            clock.advance(1)
        rec.op("attempts2", store.get(tid)["attempts"])
        _recover_a(store, 2, 3)
        rec.op("recover_dead_at_limit", store.get(tid)["state"])
        assert store.get(tid)["last_error"] == "attempt limit exhausted"
        # skip_recent：同 key 已 done 且在 TTL 内 → skipped
        d1 = store.enqueue("extract_due", {"q": "s"}, 0, key="skipme")
        r = _claim_a(store, d1, rev=store.checkpoint()[0])
        store.store_result(d1, r["token"], {}, checkpoint=b"sd",
                           expected_revision=r["revision"])
        r2 = _claim_a(store, d1, rev=r["revision"] + 1)
        store.finish(d1, r2["token"])
        d2 = store.enqueue("extract_due", {"q": "s2"}, 0, key="skipme")
        rec.op("enqueue_same_key", {"id": d2,
                                    "dedupe": store.get(d2)["dedupe_id"]})
        assert store.skip_recent(d2, ttl=3600) is True
        rec.op("skip_recent_hit", store.get(d2)["state"])
        d3 = store.enqueue("extract_due", {"q": "s3"}, 0, key="skipme")
        assert store.skip_recent(d3, ttl=0) is False
        rec.op("skip_recent_miss", store.get(d3)["state"])
        _check("a_pending_at_limit_dead_and_skip", rec)
    finally:
        store.close()


def test_char_a_checkpoint_conflict_no_daily_charge():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("recall_miss", {}, 0)
        store.save_checkpoint(b"newer", 0)
        rec.op("save_checkpoint", 1)
        try:
            _claim_a(store, tid, rev=0)
        except CheckpointConflict as exc:
            rec.op("claim_stale_revision", exc)
        rec.op("after", {"state": store.get(tid)["state"],
                         "runs": store.runs_today("2026-10-01"),
                         "checkpoint": store.checkpoint()[0]})
        _check("a_checkpoint_conflict_no_daily_charge", rec)
    finally:
        store.close()


# ------------------------------------------------------- B 机（语义+trio类）


def test_char_b_lifecycle_with_mutate_enqueue():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("conflict_pending", {"pairs": [[0, 1]]}, 0)
        rec.op("enqueue", tid)
        row = _claim_b(store, tid)
        rec.op("claim", {"state": row["state"], "attempts": row["attempts"]})
        store.store_result(tid, row["token"], {"verdicts": ["update"]},
                           rule_ids=(7,))
        rec.op("store_result", store.get(tid)["state"])
        row2 = _claim_b(store, tid)
        rec.op("claim_applying", row2["state"])

        def mutate(conn, result):
            assert result == {"verdicts": ["update"]}
            store._enqueue(conn, "reviewer_due", {"u": 1}, 0, key="rx",
                           memory_next_id=0)
            return {"resolved": 1, "recog_fail": True}

        out, rev = store.complete(tid, row2["token"], mutate,
                                  lambda: b"state-1", 0)
        rec.op("complete", [out, rev])
        ops = store._conn.execute("SELECT op_key,response FROM operations").fetchall()
        rec.op("operations", [dict(r) for r in ops])
        uses = store._conn.execute("SELECT task_id,rule_id FROM agent_rule_uses").fetchall()
        rec.op("rule_uses", [dict(r) for r in uses])
        assert store.semantic_stats()["recog_fail"] == 1
        _check("b_lifecycle_with_mutate_enqueue", rec)
    finally:
        store.close()


def test_char_b_retry_model_and_backoff():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("feedback_pending", {"r": 1}, 0)
        row = _claim_b(store, tid)
        store.store_result(tid, row["token"], {"used": [True]})
        row2 = _claim_b(store, tid)
        store.retry(tid, row2["token"], ValueError("model 502"),
                    retry_model=True)
        got = store.get(tid)
        rec.op("retry_model", {"state": got["state"], "result": got["result"],
                               "next_run_at": got["next_run_at"]})
        assert got["state"] == "pending" and got["result"] is None
        # 退避序列：2^attempts（cap 300），attempts 侧
        delays = []
        for _ in range(4):
            clock.advance(400)
            r = _claim_b(store, tid)
            store.retry(tid, r["token"], RuntimeError("x"))
            delays.append(store.get(tid)["next_run_at"] - clock())
        rec.op("backoff", delays)
        assert delays == [4, 8, 16, 32]
        _check("b_retry_model_and_backoff", rec)
    finally:
        store.close()


def test_char_b_trio_dead_at_five():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("hauler_due", {"unit_id": 3}, 0)
        for i in range(6):
            clock.advance(400)
            row = _claim_b(store, tid)
            if row is None:
                rec.op(f"claim{i}", None)
                break
            rec.op(f"claim{i}", row["attempts"])
            # trio 形状：retry_model 按异常类型，上限 5 由政策持有（P3 前调用方传 5）
            store.retry(tid, row["token"], ValueError("bad shape"),
                        retry_model=True)
            rec.op(f"retry{i}", store.get(tid)["state"])
        assert store.get(tid)["state"] == "dead"
        _check("b_trio_dead_at_five", rec)
    finally:
        store.close()


def test_char_b_recover_and_gates():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("maintenance_due", {"scene": "s"}, 0)
        row = _claim_b(store, tid, lease_s=10)
        rec.op("claim", row["state"])
        clock.advance(11)
        _recover_b(store)
        got = store.get(tid)
        rec.op("recover", {"state": got["state"], "next_run_at": got["next_run_at"]})
        assert got["next_run_at"] == clock()  # B 机重置 next_run_at
        row2 = _claim_b(store, tid)
        rec.op("reclaim", row2["state"])
        try:
            store.store_result(tid, row["token"], {})
        except TaskLeaseLost as exc:
            rec.op("store_old_token", exc)
        assert _claim_b(store, tid, version=999) is None
        rec.op("claim_version_mismatch", None)
        _check("b_recover_and_gates", rec)
    finally:
        store.close()


# ------------------------------------------------------- 共享：入队/回执/台账


def test_char_enqueue_merge_dedupe_capacity():
    store, clock = _store()
    try:
        rec = Rec(store)
        store.capacity = 2
        a = store.enqueue("recall_miss", {"q": "old"}, 0, key="q")
        rec.op("enqueue", a)
        assert store.enqueue("recall_miss", {"q": "new"}, 8, key="q") == a
        got = store.get(a)
        rec.op("merge", {"payload": got["payload"], "t": got["t"],
                         "version": got["version"]})
        assert (got["payload"], got["t"], got["version"]) == ({"q": "new"}, 8, 1)
        b = store.enqueue("recall_miss", {"q": "b"}, 0, key="k2")
        rec.op("enqueue_b", b)
        try:
            store.enqueue("recall_miss", {"q": "c"}, 0, key="k3")
        except TaskQueueFull as exc:
            rec.op("capacity_full", exc)
        assert store.memory_next_id() == 0
        store.capacity = 9  # 扩容后继续（容量是运行属性，不进快照）
        store.enqueue("extract_due", {}, 0, memory_next_id=42)
        rec.op("memory_next_id", store.memory_next_id())
        _check("enqueue_merge_dedupe_capacity", rec)
    finally:
        store.close()


def test_char_receipts_and_captured_effects():
    store, clock = _store()
    try:
        rec = Rec(store)
        out, rev, replayed = store.apply_unit(
            0, lambda: {"units": 1, "next_memory_id": 5}, lambda: b"u0", [], 0)
        rec.op("apply_unit", [out, rev, replayed])
        out2, rev2, replayed2 = store.apply_unit(
            0, lambda: {"units": 999, "next_memory_id": 9}, lambda: b"uX", [], 1)
        rec.op("apply_unit_replay", [out2, rev2, replayed2])
        assert replayed2 and out2 == out
        resp, replayed3 = store.remember_capture("r1", "feedback", "fp1", {"ok": 1})
        rec.op("remember_capture", [resp, replayed3])
        assert store.read_capture("r1")["response"] == {"ok": 1}
        out3, rev3, rp3 = store.apply_captured_effect(
            lambda conn: {"n": 1}, lambda: b"c1", 1,
            {"request_id": "r2", "kind": "feedback", "fingerprint": "fp2"})
        rec.op("apply_captured", [out3, rev3, rp3])
        out4, rev4, rp4 = store.apply_captured_effect(
            lambda conn: {"n": 2}, lambda: b"cX", 2,
            {"request_id": "r2", "kind": "feedback", "fingerprint": "fp2"})
        rec.op("apply_captured_replay", [out4, rev4, rp4])
        assert rp4 and out4 == out3 and rev4 == 2
        try:
            store.remember_capture("r2", "feedback", "OTHER", {"ok": 0})
        except CaptureConflict as exc:
            rec.op("capture_conflict", exc)
        _check("receipts_and_captured_effects", rec)
    finally:
        store.close()


def test_char_apply_operation_replay_and_lease():
    store, clock = _store()
    try:
        rec = Rec(store)
        tid = store.enqueue("recall_miss", {}, 0)
        row = _claim_a(store, tid, lease_s=100, rev=0)
        req = {"op": "embed", "ids": [1]}
        resp, rev, rp = store.apply_operation(
            tid, row["token"], req, lambda: {"v": [0.1]}, lambda: b"op1", 1)
        rec.op("apply_operation", [resp, rev, rp])
        resp2, rev2, rp2 = store.apply_operation(
            tid, row["token"], req, lambda: {"v": [0.2]}, lambda: b"opX", 2)
        rec.op("apply_operation_replay", [resp2, rev2, rp2])
        assert rp2 and resp2 == resp and rev2 == 2
        try:
            store.apply_operation(tid, "nope", req, lambda: {}, lambda: b"x", 2)
        except TaskLeaseLost as exc:
            rec.op("apply_operation_bad_token", exc)
        _check("apply_operation_replay_and_lease", rec)
    finally:
        store.close()


def test_char_rules_trace_reviews_stats():
    store, clock = _store()
    try:
        rec = Rec(store)
        with store._conn:
            store._conn.execute(
                "INSERT INTO agent_rules(source_task,target,instruction,scope,created_at)"
                " VALUES(?,?,?,?,?)",
                (1, "selector", "prefer B", "project", clock()))
            store._conn.execute(
                "INSERT INTO agent_rules(source_task,target,instruction,scope,created_at)"
                " VALUES(?,?,?,?,?)",
                (2, "selector", "avoid C", "entity:特殊", clock()))
            store._conn.execute(
                "INSERT INTO human_reviews(source_task,target_id,candidate,reason,created_at)"
                " VALUES(?,?,?,?,?)",
                (1, 9, "cand", "why", clock()))
        rec.op("rule_snapshot", store.rule_snapshot("selector", "含特殊字的上下文"))
        rec.op("rules_for", store.rules_for("selector"))
        rec.op("rule_report_uses", store.rule_report())
        assert store.disable_rule(1) is True
        rec.op("disable_rule", store.rule_report())
        assert store.disable_rule(1) is False
        rec.op("pending_reviews", store.pending_reviews())
        h = store.enqueue("hauler_due", {"unit_id": 5}, 0)
        s = store.enqueue("selector_due", {"unit_id": 5, "parent_task": h,
                                           "candidates": [{"text": "t"}]}, 0)
        # 完成 selector（B 流），再发 reviewer 作 trigger：trace 含 done + pending 两态
        row = _claim_b(store, s)
        store.store_result(s, row["token"], {"decisions": ["keep"]})
        row2 = _claim_b(store, s)
        store.complete(s, row2["token"],
                       lambda conn, result: {"applied": 1},
                       lambda: b"sel", 0)
        clock.advance(5)
        r = store.enqueue("reviewer_due", {"unit_id": 5}, 0)
        rec.op("queued_counts", store.queued_counts())
        rec.op("semantic_stats", store.semantic_stats())
        trace = store.workflow_trace([5], before_task_id=r)
        rec.op("workflow_trace", trace)
        try:
            store.workflow_trace([5], before_task_id=9999)
        except ValueError as exc:
            rec.op("trace_missing_trigger", exc)
        _check("rules_trace_reviews_stats", rec)
    finally:
        store.close()


# ------------------------------------------------------- API 绑定（合并后只改这里）


def _claim_a(store, tid, *, before=1, rev=0, lease_s=10, daily_cap=10,
             expected_version=None):
    return store.claim(
        tid, before=before, origin="repair", day="2026-10-01",
        daily_cap=daily_cap, lease_s=lease_s, checkpoint=f"state-{rev}".encode(),
        expected_revision=rev,
        expected_version=(store.get(tid)["version"] if expected_version is None
                          else expected_version))


def _claim_b(store, tid, *, lease_s=None, version=None):
    return store.claim(
        tid, lease_s=lease_s,
        expected_version=(store.get(tid)["version"] if version is None
                          else version))


def _recover_a(store, max_attempts, max_apply_attempts):
    store.recover_expired(max_attempts, max_apply_attempts,
                          kinds=("recall_miss", "extract_due"),
                          reset_next_run_at=False)


def _recover_b(store):
    store.recover_expired(kinds=SEMANTIC_KINDS | WORKFLOW_KINDS,
                          reset_next_run_at=True)
