"""可观测性与 checkpoint 预算闸回归（N49 / PENDING-09 / PENDING-10）。

- PENDING-10：health 暴露 pin 占用——口径与容量收口同源（enforce_capacity
  实际保护的 pinned_ids ∩ 非退役，退役 pin 不占上下文槽），占用率 ≥0.7
  外显告警（含 0.7 边界）；
- PENDING-09：checkpoint 预算线（2MB）——引擎状态序列化超线拒收新效果
  （Degraded(checkpoint_over_budget)→503），回滚无残留；save/恢复不受闸
  （持久化与读取不是写放大）；重启后水位从 durable checkpoint 恢复、
  闸门立即生效。
"""
from __future__ import annotations

import numpy as np
import pytest

from hybrid_memory.service import observability
from hybrid_memory.core.types import Memory, Pool
from hybrid_memory.errors import Degraded, http_status
from test_ouroboros import _svc


def _pin(svc, mid: int, *, retired: bool = False) -> None:
    """直接注入一条被 pin 保护的记忆（待审目标形态）。"""
    eng = svc.engine
    eng.mems[mid] = Memory(
        id=mid, belief_id=mid + 1, value=f"v{mid}", text=f"受保护记忆{mid}",
        emb=np.zeros(64), pool=Pool.MEMORY, v=0.5, birth=0, last_seen=0,
        pending_review=True,
        aggregated_into=(mid + 100) if retired else None)
    eng._next_id = max(eng._next_id, mid + 1)


def test_health_exposes_capacity_and_checkpoint_fields(tmp_path):
    svc = _svc(tmp_path)
    try:
        svc.observe("项目改用 bun 构建", "好的")
        svc.propose([{"text": "构建部署在 B 服务器", "src": [0]}])
        h = svc.health_view()
        # PENDING-10：pin 占用字段齐全，口径字段可核对
        assert h["pin_roots"] == 0 and h["pinned_context"] == 0
        assert h["cap_context"] == svc.cfg.cap_context
        assert h["pin_occupancy"] == 0.0
        # PENDING-09：checkpoint 水位与预算线
        assert h["checkpoint_bytes"] > 0, "提交后必须暴露最近序列化大小"
        assert h["checkpoint_budget"] == observability.CHECKPOINT_BUDGET_BYTES
        assert observability.CHECKPOINT_BUDGET_BYTES == 2 * 1024 * 1024
        assert h["alerts"] == []
    finally:
        svc.tasks.close()
        svc.log.close()


def test_pin_occupancy_alert_threshold_and_boundary(tmp_path):
    svc = _svc(tmp_path, cap_context=10)
    try:
        for mid in range(5):
            _pin(svc, mid)
        h = svc.health_view()
        assert h["pinned_context"] == 5 and abs(h["pin_occupancy"] - 0.5) < 1e-9
        assert "pin_occupancy_high" not in h["alerts"]
        for mid in range(5, 7):          # 到 7/10 = 0.7 边界
            _pin(svc, mid)
        h = svc.health_view()
        assert h["pinned_context"] == 7 and abs(h["pin_occupancy"] - 0.7) < 1e-9
        assert "pin_occupancy_high" in h["alerts"], "阈值语义为 ≥0.7（含边界）"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_retired_pins_do_not_occupy_context(tmp_path):
    svc = _svc(tmp_path, cap_context=10)
    try:
        _pin(svc, 0)                      # 存活 pin
        _pin(svc, 1, retired=True)        # 聚合成员：被保护但已退役
        h = svc.health_view()
        assert h["pin_roots"] == 2, "原始保护集含退役成员"
        assert h["pinned_context"] == 1, "退役 pin 不占上下文槽"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_over_budget_gate_refuses_rolls_back_and_spares_save(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    try:
        svc.observe("项目改用 bun 构建", "好的")     # 首次提交：水位记账
        assert svc._state_bytes > 0
        monkeypatch.setattr(observability, "CHECKPOINT_BUDGET_BYTES", 8)  # 远小于实际水位
        with pytest.raises(Degraded) as exc:
            svc.propose([{"text": "构建部署在 B 服务器", "src": [0]}])
        assert exc.value.code == "checkpoint_over_budget"
        assert http_status(exc.value.code) == 503
        assert not svc.engine.mems, "拒收必须无残留"
        with pytest.raises(Degraded):                 # observe 同为效果提交，同样拒收
            svc.observe("继续", "记录")
        assert "checkpoint_over_budget" in svc.health_view()["alerts"]
        out = svc.save()                              # save 是持久化不是写放大，不受闸
        assert out.get("saved") is True
    finally:
        svc.tasks.close()
        svc.log.close()


def test_over_budget_gate_active_immediately_after_restart(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    try:
        svc.observe("项目改用 bun 构建", "好的")     # durable checkpoint 落库
    finally:
        svc.tasks.close()
        svc.log.close()
    monkeypatch.setattr(observability, "CHECKPOINT_BUDGET_BYTES", 8)
    fresh = _svc(tmp_path)                            # 恢复期从 durable 水位起算
    try:
        assert fresh._state_bytes > 8, "重启必须恢复最近提交的水位"
        with pytest.raises(Degraded) as exc:
            fresh.observe("重启后", "第一笔")
        assert exc.value.code == "checkpoint_over_budget"
    finally:
        fresh.tasks.close()
        fresh.log.close()
