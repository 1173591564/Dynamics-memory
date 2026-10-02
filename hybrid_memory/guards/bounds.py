"""有界校验（P4：请求标识原语通电；批量/钳制随 P5 落地）。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Sized

MAX_PROPOSE_BATCH = 50              # /propose 单批上限（现状行为，冻结）
MAX_BODY_BYTES = 4 * 1024 * 1024    # HTTP 请求体上限 4MiB（现状行为，冻结）

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._:-]{8,80}")


def validate_request_id(value):
    """请求 id 语法校验（P4 从 server 原样迁入；仍抛 ValueError，P5 随 transport 统一转 Rejected）。"""
    if value is None:
        return None
    if not isinstance(value, str) or _REQUEST_ID_RE.fullmatch(value) is None:
        raise ValueError("request_id must be 8–80 characters of [A-Za-z0-9._:-]")
    return value


def capture_fingerprint(fields: dict) -> str:
    """请求体规范指纹（幂等绑定用；P4 从 server 迁入，与 validate 同属请求标识原语）。"""
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_batch_size(items: Sized, limit: int) -> None:
    """超限抛 `Rejected("bad_request")`，且调用方保证不部分应用。"""
    raise NotImplementedError("guards.bounds.require_batch_size: P5 通电")


def clamp(x: float, lo: float, hi: float) -> float:
    """闭区间钳制（纯函数）。"""
    raise NotImplementedError("guards.bounds.clamp: P5 通电")
