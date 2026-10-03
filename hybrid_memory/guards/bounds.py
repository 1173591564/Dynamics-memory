"""有界校验（P4/N25）：请求标识原语与批量校验。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Sized

from ..errors import Rejected

MAX_PROPOSE_BATCH = 50              # /propose 单批上限（现状行为，冻结）
MAX_BODY_BYTES = 4 * 1024 * 1024    # HTTP 请求体上限 4MiB（现状行为，冻结）

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._:-]{8,80}")


def validate_request_id(value):
    """请求 id 语法校验（P4 从 server 原样迁入）。"""
    if value is None:
        return None
    if not isinstance(value, str) or _REQUEST_ID_RE.fullmatch(value) is None:
        raise ValueError("request_id must be 8–80 characters of [A-Za-z0-9._:-]")
    return value


def capture_fingerprint(fields: dict) -> str:
    """请求体规范指纹（幂等绑定用；P4 从 server 迁入）。"""
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_batch_size(items: Sized, limit: int) -> None:
    """超限抛 `Rejected("bad_request")`，且调用方保证不部分应用。"""
    if len(items) > limit:
        raise Rejected("bad_request", f"batch size {len(items)} exceeds limit {limit}")
