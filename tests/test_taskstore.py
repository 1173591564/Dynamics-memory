from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from hybrid_memory.taskstore import CheckpointConflict, TaskLeaseLost, TaskQueueFull, TaskStore


def _claim(store, task_id, **overrides):
    args = dict(before=1, origin="repair", day="2026-10-01", daily_cap=10,
                lease_s=10, checkpoint=b"unit-test checkpoint", expected_revision=0)
    args.update(overrides)
    return store.claim(task_id, **args)


def test_parallel_connections_only_one_claim_and_one_daily_charge(tmp_path):
    stores = [TaskStore(tmp_path / "tasks.sqlite") for _ in range(4)]
    tid = stores[0].enqueue("recall_miss", {"q": "one"}, 0)
    barrier = threading.Barrier(4)

    def claim(i):
        barrier.wait(timeout=5)
        return _claim(stores[i], tid)

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(claim, range(4)))
        assert sum(r is not None for r in rows) == 1
        assert stores[0].runs_today("2026-10-01") == 1
    finally:
        for store in stores:
            store.close()


def test_stale_claim_token_cannot_store_result_or_finish():
    now = [100.0]
    store = TaskStore(clock=lambda: now[0])
    tid = store.enqueue("recall_miss", {}, 0)
    old = _claim(store, tid)
    now[0] += 11
    store.recover_expired(3, 3)
    fresh = _claim(store, tid, expected_revision=1)
    with pytest.raises(TaskLeaseLost):
        store.store_result(tid, old["token"], {})
    with pytest.raises(TaskLeaseLost):
        store.finish(tid, old["token"])
    assert store.get(tid)["token"] == fresh["token"]


def test_stale_checkpoint_cannot_overwrite_or_consume_daily_allowance():
    store = TaskStore()
    tid = store.enqueue("recall_miss", {}, 0)
    store.save_checkpoint(b"newer", 0)
    with pytest.raises(CheckpointConflict):
        _claim(store, tid)
    assert store.get(tid)["state"] == "pending"
    assert store.runs_today("2026-10-01") == 0
    assert store.checkpoint() == (1, b"newer")


def test_merged_payload_version_must_match_claim_bound():
    store = TaskStore()
    tid = store.enqueue("recall_miss", {"q": "old"}, 0, key="q")
    version = store.get(tid)["version"]
    assert store.enqueue("recall_miss", {"q": "new"}, 8, key="q") == tid
    assert _claim(store, tid, expected_version=version) is None
    assert store.get(tid)["state"] == "pending"
    assert store.runs_today("2026-10-01") == 0


def test_capacity_rejects_instead_of_evicting_accepted_task():
    store = TaskStore(capacity=1)
    tid = store.enqueue("recall_miss", {"q": "first"}, 0, key="same")
    assert store.enqueue("recall_miss", {"q": "merged"}, 1, key="same") == tid
    with pytest.raises(TaskQueueFull):
        store.enqueue("recall_miss", {"q": "other"}, 1, key="other")
    assert len(store.list_tasks()) == 1 and store.get(tid)["payload"] == {"q": "merged"}
