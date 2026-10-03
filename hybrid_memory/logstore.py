"""LogStore 旧导入位（H23/N24/N26）：真实实现已迁入 store/evidence.py。"""
from __future__ import annotations

from .store.evidence import (
    LogStore,
    _fts_expr,
    _snippet,
    _tokens,
    entities_in,
)

__all__ = [
    "LogStore",
    "entities_in",
    "_tokens",
    "_fts_expr",
    "_snippet",
]
