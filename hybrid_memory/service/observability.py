"""pin 占用与 checkpoint 预算水位（N49；PENDING-09/10）。

为什么独立模块：telemetry 属地基层（只用标准库，import 边界测试强制），
而 pin 口径真源 `core.dynamics.pinned_ids` 在 core——计算回落 service 层，
health_view（service.health_view）负责并进 /health 输出。常量也定在此处：
`_rollback_effect` 预算闸与展示侧都引用本模块属性（调用期取值，测试可
monkeypatch）。
"""
from __future__ import annotations

from ..core import dynamics

# PENDING-09 预算线（design-debts §2）：单次引擎状态序列化超过此值拒收
# 新效果（吵闹失败，不静默变慢）。解冻=分段 pickle ADR（I5 单点接入）。
CHECKPOINT_BUDGET_BYTES = 2 * 1024 * 1024
# PENDING-10 告警阈值：pin 占上下文容量比 ≥ 此值时 health 外显告警。
PIN_OCCUPANCY_ALERT = 0.7


def capacity_status(service: object) -> dict:
    """只读水位：pin 占用（口径=enforce_capacity 同源）与 checkpoint 预算。

    - pin 口径与容量收口同源：pinned_ids 即 enforce_capacity 实际保护的
      集合，不另造第二套计算；
    - 分子只计仍占上下文的 pin（非退役）：退役 pin 不占 context 槽，
      503 的逼近由非退役 pin 决定；
    - 只读，不触发裁决/收口；alerts 为外显告警键（空列表=无告警）。
    """
    pinned = dynamics.pinned_ids(service.engine)
    non_retired = {m.id for m in service.engine.mems.values()
                   if m.superseded_by is None and m.aggregated_into is None}
    occupied = len(pinned & non_retired)
    cap = service.cfg.cap_context
    ratio = (occupied / cap) if cap else 0.0
    alerts: list[str] = []
    if ratio >= PIN_OCCUPANCY_ALERT:
        alerts.append("pin_occupancy_high")
    if service._state_bytes > CHECKPOINT_BUDGET_BYTES:
        alerts.append("checkpoint_over_budget")
    return {"pin_roots": len(pinned), "pinned_context": occupied,
            "cap_context": cap, "pin_occupancy": round(ratio, 4),
            "checkpoint_bytes": service._state_bytes,
            "checkpoint_budget": CHECKPOINT_BUDGET_BYTES,
            "capacity_on": service.cfg.capacity_on,
            "alerts": alerts}
