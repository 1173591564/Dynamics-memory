"""三类错误 + 唯一 HTTP 映射（H24）。纯数据、无 I/O，可被任何层 import。

Rejected = 调用方错（4xx）；Degraded = 可继续但必须外显的降级；
Fatal = 拒绝启动（不进 HTTP）。P2 先行落地（真实现，非壳）；
P5 由 transport 统一映射（届时响应加 `code` 字段，保留 `error` 文案）。
"""
from __future__ import annotations


class MemoryError(Exception):
    """基类：code 稳定（给插件判），message 给人读，detail 给运维查。"""

    def __init__(self, code: str, message: str = "", detail: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.detail = detail


class Rejected(MemoryError):
    """调用方错：4xx，不重试（幂等键冲突靠重放，不靠重试语义）。"""


class Degraded(MemoryError):
    """可继续但必须外显：调用方收到 200/503 + 降级标志或计数。"""


class Fatal(MemoryError):
    """拒绝启动：配置错/版本错/自检不过，不进 HTTP。"""


_STATUS: dict[str, int] = {
    "bad_request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "direct_write_disabled": 403,   # trio 下直写三入口（H35）
    "not_found": 404,
    "conflict": 409,
    "payload_too_large": 413,
    "unsupported_media_type": 415,
    "rate_limited": 429,
    "queue_full": 503,              # 任务队满（H9）
    "internal": 500,
}


def http_status(code: str) -> int:
    """错误码 → 状态码唯一映射。未知码抛 KeyError（调用方 bug，必须 loud）。"""
    return _STATUS[code]
