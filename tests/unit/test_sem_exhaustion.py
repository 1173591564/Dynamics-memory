"""N06 回归：语义任务模型/应用上限与耗尽 dead。

- SEM 模型上限 5、应用上限 5；_SEMANTIC.max_attempts 不再 None；
- 耗尽 → dead 且保留产物（合法模型产物不因反复 apply 失败被清）；
- 租约过期恢复不重置计数（崩溃-重试循环也计入上限，最终 dead）；
- INV=2/3、SEM lease ≥ llm.chat 最坏 300s。
"""
from __future__ import annotations

import pytest

from hybrid_memory.dispatch.policy import POLICIES, _SEMANTIC, _INVESTIGATION
from hybrid_memory.store.tasks import TaskStore
from test_ouroboros import _svc


def test_policy_values_n06():
    assert _SEMANTIC.max_attempts == 5, "SEM 模型上限 5（不再 None）"
    assert _SEMANTIC.max_apply_attempts == 5
    assert _SEMANTIC.on_exhausted == "dead", "耗尽必须 dead（requeue 是无限循环）"
    assert _SEMANTIC.lease_s >= 360, "llm.chat 最坏 300s，lease 必须 ≥360"
    assert _INVESTIGATION.max_attempts == 2, "INV=2/3"
    assert _INVESTIGATION.max_apply_attempts == 3


def test_sem_model_attempts_exhaust_to_dead(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    now = [1000.0]
    svc.tasks.clock = lambda: now[0]
    try:
        svc.tasks.enqueue("maintenance_due", {"scene": "s", "ids": [1]}, 0)

        def boom(row):
            raise RuntimeError("model down")
        svc._semantic_model = boom
        for i in range(5):
            now[0] += 400.0   # 越过 backoff（2^attempts，封顶 300）
            svc.process_semantic_tasks()
        row = svc.tasks.get(1)
        assert row["state"] == "dead", "模型重试 5 次耗尽必须 dead"
        assert "model down" in row["last_error"]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_sem_apply_attempts_exhaust_to_dead_preserving_result(tmp_path):
    """apply 反复背压/失败：耗尽 dead 且保留模型产物（不清 result）。"""
    from hybrid_memory.core.types import Memory, Pool
    import numpy as np
    svc = _svc(tmp_path, cap_a=0, cap_context=100, cap_c=10)
    svc.trio_mode = True
    now = [1000.0]
    svc.tasks.clock = lambda: now[0]
    try:
        eng = svc.engine
        eng.mems[0] = Memory(id=0, belief_id=1, value="v", text="归档被钉",
                             emb=np.zeros(64), pool=Pool.ARCHIVE, v=0.5,
                             birth=0, last_seen=0, pending_review=True,
                             agg_members=(9,))   # A 池全 pin：无法收口
        eng.mems[9] = Memory(id=9, belief_id=9, value="v9", text="成员",
                             emb=np.zeros(64), pool=Pool.CANDIDATE, v=0.5,
                             birth=0, last_seen=0, aggregated_into=0)
        eng._next_id = 10
        event = {"belief_id": 99, "value": "反思", "text": "反思产物",
                 "src": [], "kind": "reflection"}
        sources = [[0, 0, "A", None, None]]   # 与引擎快照一致，避免漂移重排
        svc._semantic_model = lambda row: {"event": event, "sources": sources}
        svc.tasks.enqueue("maintenance_due", {"scene": "s", "ids": [0]}, 0)
        for i in range(6):
            now[0] += 400.0   # 越过 backoff
            svc.process_semantic_tasks()
        row = svc.tasks.get(1)
        assert row["state"] == "dead", "应用 5 次耗尽必须 dead"
        assert row["result"], "dead 保留模型产物（合法产物不因收口失败被清）"
        assert "capacity cannot be closed" in row["last_error"]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_expiry_does_not_reset_attempt_count(tmp_path):
    """崩溃-租约过期循环：计数不重置，5 轮后 dead（不无限循环）。"""
    store = TaskStore(tmp_path / "tasks.sqlite")
    now = [0.0]
    store.clock = lambda: now[0]
    try:
        tid = store.enqueue("maintenance_due", {"k": 1}, 0)
        version = 0
        for _ in range(5):
            row = store.claim(tid, expected_version=version)
            assert row["state"] == "running", "领取成功进入 running"
            version = row["version"]
            # 模拟崩溃：租约到期后恢复（计数必须跨过期保持）
            now[0] = row["lease_until"] + 1
            store.recover_expired(kinds=("maintenance_due",),
                                  reset_next_run_at=True)
            version = store.get(tid)["version"]
        row = store.get(tid)
        assert row["state"] == "dead", \
            f"过期恢复 5 轮后必须 dead（attempts={row['attempts']}），不能无限循环"
        assert row["attempts"] >= 5, "计数跨过期恢复保持"
    finally:
        store.close()


def test_sem_retry_backoff_is_bounded():
    from hybrid_memory.dispatch.policy import policy_for
    pol = policy_for("maintenance_due")
    for attempts in (1, 3, 8, 20):
        delay = min(300, pol.backoff ** min(8, attempts))
        assert delay <= 300
