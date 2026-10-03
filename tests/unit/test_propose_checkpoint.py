"""propose 直写路径的 checkpoint 与容量收口回归（P0-2 遗留 / §5.2 / N46）。

规范 §5.2：propose "Legacy 直写也立即 checkpoint"；§4.2：每种新增在
commit 前 plan_capacity，全 pin 整批拒收/回滚。旧实现直写路径
（ctx.task_id is None）在锁内直接改引擎——无 checkpoint、无回滚、无收口。
"""
from __future__ import annotations

import numpy as np
import pytest

from hybrid_memory.core.types import Memory, Pool
from hybrid_memory.errors import Degraded
from test_ouroboros import _svc


def _pinned_archive(svc, mid=0):
    """预置一条 pin 保护的 A 池记忆（待审目标，pin root）。"""
    eng = svc.engine
    eng.mems[mid] = Memory(id=mid, belief_id=mid + 1, value=f"v{mid}",
                           text="被保护的旧记忆", emb=np.zeros(64),
                           pool=Pool.ARCHIVE, v=0.5, birth=0, last_seen=0,
                           pending_review=True)
    eng._next_id = max(eng._next_id, mid + 1)
    return eng.mems[mid]


def test_direct_propose_checkpoints_immediately(tmp_path):
    svc = _svc(tmp_path)
    try:
        svc.observe("项目改用 bun 构建", "好的")     # L0 unit 0
        rev_before = svc.tasks.checkpoint()[0]
        out = svc.propose([{"text": "项目统一使用 bun 工具", "src": [0]}])
        assert out["accepted"] == 1 and out["new_ids"]
        # 直写必须立即写 durable checkpoint（§5.2）
        revision, state = svc.tasks.checkpoint()
        assert revision > rev_before, "直写 propose 不写 checkpoint（§5.2 缺口）"
        assert "项目统一使用 bun 工具".encode("utf-8") in state, \
            "checkpoint 状态必须包含直写产物"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_direct_propose_survives_restart(tmp_path):
    svc = _svc(tmp_path)
    try:
        svc.observe("项目改用 bun 构建", "好的")
        svc.propose([{"text": "构建部署在 B 服务器", "src": [0]}])   # "构建"落在来源上
    finally:
        svc.tasks.close()
        svc.log.close()
    fresh = _svc(tmp_path)                      # 同 state_dir 重启
    try:
        texts = [m.text for m in fresh.engine.mems.values()]
        assert "构建部署在 B 服务器" in texts, "直写产物必须经 checkpoint 存活重启"
    finally:
        fresh.tasks.close()
        fresh.log.close()


def test_direct_propose_capacity_backpressure_rolls_back(tmp_path):
    """§4.2：直写新增同样 commit 前收口；全 pin 无法收口 → 整批拒收回滚。"""
    svc = _svc(tmp_path, cap_context=1)
    try:
        svc.observe("项目改用 bun 构建", "好的")
        _pinned_archive(svc)
        before = len(svc.engine.mems)
        n_prop_before = svc.n_proposals
        with pytest.raises(Degraded) as exc:
            svc.propose([{"text": "构建方式已改", "src": [0]}])   # "构建"落在来源上
        assert exc.value.code == "capacity_backpressure"
        # 回滚完整：引擎无残留、计数器无泄漏
        assert len(svc.engine.mems) == before, "回滚必须移除直写新增"
        assert svc.n_proposals == n_prop_before, "回滚必须恢复服务计数器"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_direct_propose_partial_validation_still_atomic(tmp_path):
    """批量里部分非法：非法条目拒绝，合法条目原子应用并 checkpoint。"""
    svc = _svc(tmp_path)
    try:
        svc.observe("项目改用 bun 构建", "好的")
        out = svc.propose([
            {"text": "构建工具用 bun", "src": [0]},   # "构建"落在来源上
            {"text": "", "src": [0]},                    # 非法：空文本
            {"text": "引用幽灵来源", "src": [99]},        # 非法：来源不存在
        ])
        assert out["accepted"] == 1 and out["new_ids"]
        assert [r["index"] for r in out["rejected"]] == [1, 2]
        texts = [m.text for m in svc.engine.mems.values()]
        assert texts == ["构建工具用 bun"]
        assert svc.tasks.checkpoint()[0] >= 1
    finally:
        svc.tasks.close()
        svc.log.close()
