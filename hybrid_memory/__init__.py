"""Dynamics-memory 对外极小面（§2.1：P6 后审计落地）。

只此三名 + 延迟组装；不导出 store/dispatch 细节。
`__version__` 随 `pyproject.toml`（P6 后）。
"""
from .config import Cfg, Settings
from .service.service import MemoryService

__all__ = ["Cfg", "MemoryService", "Settings", "build_default_service"]


def __getattr__(name: str):
    if name == "build_default_service":
        from .transport.bootstrap import build_default_service
        return build_default_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
