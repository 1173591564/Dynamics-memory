"""观测面（P4 通电）。只用标准库（地基层，不碰任何包）。

视图函数与服务对象是 intimate 的（§2.1 定死 `health_view(service)` 形状）：
读 service 私有状态，但只经公开的 `service.lock` 加锁。
"""
from __future__ import annotations

import json
import sys
import threading
import time
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
    """现字段集冻结（只许加字段，A7）。从 server.py 原样迁入（P4）。"""
    with service.lock:
        if service._snapshot_quarantined:
            snapshot = "quarantined"
        else:
            snapshot = service._snapshot_status
        return {"ok": not service._checkpoint_fault,
                "checkpoint_fault": service._checkpoint_fault,
                "snapshot": snapshot,
                "corrupt_file": service._corrupt_file_exists(),
                "units_pending": service.log.work_stats()["pending"],
                "validation": "unverified",
                "t": service._t,
                "mems": service.engine.pool_sizes(),
                "tensions": len(service.engine.tensions),
                "signals": sum(service.tasks.queued_counts().values()) + len(service.engine.signals),
                "log_units": service.log.count(),
                "agent": bool(service.agent or service.dispatch_worker)}


def signals_view(service: object) -> dict:
    """现字段集冻结。从 server.py 原样迁入（P4）。"""
    with service.lock:
        q = service.engine.signals
        return {"queued": service.tasks.queued_counts() | q.peek_kinds(), "n_emitted": q.n_emitted,
                "n_dropped": q.n_dropped,
                "open_budgets": sorted(service._budgets),
                "tasks": service.tasks.stats(), "semantic": service.tasks.semantic_stats(),
                "checkpoint_fault": service._checkpoint_fault,
                "missed": service.n_missed, "proposals": service.n_proposals,
                "rejected": service.n_rejected,
                "candgen_fail": service.n_candgen_fail,
                "miss_counts": dict(service.miss_counts),
                "log_units": service.log.count(), "units": service.log.work_stats(),
                "agent": service.agent.stats() if service.agent else None,
                "t": service._t}


def log_event(kind: str, **fields) -> None:
    """JSON 一行到 stderr（{"t", "kind", **fields}）。"""
    print(json.dumps({"t": time.time(), "kind": kind, **fields}, ensure_ascii=False),
          file=sys.stderr, flush=True)


_warned: set[str] = set()
_warned_lock = threading.Lock()


def warn_once(key: str, message: str) -> None:
    """限频告警（同 key 进程内只报一次）。"""
    with _warned_lock:
        if key in _warned:
            return
        _warned.add(key)
    print(f"[memory:{key}] {message}", file=sys.stderr, flush=True)
