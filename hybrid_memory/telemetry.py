"""观测面（P2：计数器数据结构先行；视图与日志函数 P5 通电）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Counters:
    """降级/丢弃计数的唯一口径（§2 telemetry）。"""

    n_missed: int = 0
    n_rejected: int = 0
    n_ungrounded: int = 0
    n_candgen_fail: int = 0
    n_dropped: int = 0
    n_shadow_dropped: int = 0
    n_pool_truncated: int = 0
    n_dead_tasks: int = 0


def health_view(service: object) -> dict:
    """现字段集冻结（只许加字段，A7）+ `semantics` 健康段（H27）。"""
    raise NotImplementedError("telemetry.health_view: P5 通电")


def signals_view(service: object) -> dict:
    """现字段集冻结。"""
    raise NotImplementedError("telemetry.signals_view: P5 通电")


def log_event(kind: str, **fields) -> None:
    """JSON 一行到 stderr。"""
    raise NotImplementedError("telemetry.log_event: P5 通电")


def warn_once(key: str, message: str) -> None:
    """限频告警（同 key 进程内只报一次）。"""
    raise NotImplementedError("telemetry.warn_once: P5 通电")
