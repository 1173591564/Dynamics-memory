"""有界校验（P2：常量先行；函数 P4/P5 通电）。"""
from __future__ import annotations

from typing import Sized

MAX_PROPOSE_BATCH = 50              # /propose 单批上限（现状行为，冻结）
MAX_BODY_BYTES = 4 * 1024 * 1024    # HTTP 请求体上限 4MiB（现状行为，冻结）


def validate_request_id(value: str) -> str:
    """请求 id 合法才返回归一化值，否则抛 `Rejected(\"bad_request\")`。"""
    raise NotImplementedError("guards.bounds.validate_request_id: P4/P5 通电")


def require_batch_size(items: Sized, limit: int) -> None:
    """超限抛 `Rejected(\"bad_request\")`，且调用方保证不部分应用。"""
    raise NotImplementedError("guards.bounds.require_batch_size: P4/P5 通电")


def clamp(x: float, lo: float, hi: float) -> float:
    """闭区间钳制（纯函数）。"""
    raise NotImplementedError("guards.bounds.clamp: P4/P5 通电")
