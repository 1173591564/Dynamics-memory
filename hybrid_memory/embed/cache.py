"""SQLite 向量缓存：只保存 cache_key → float32 bytes，不存原文/密钥/响应全文。"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from ..store.schema import open_db


class SqliteEmbeddingCache:
    """向量缓存（kind=cache 三库身份之一，N45）：启动时经 schema.open_db
    建表与版本登记；读写走短连接（自动提交模式，单条语句即时生效）。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        conn = open_db(self.path, kind="cache")
        conn.close()

    def _short(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False,
                               isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def get(self, cache_key: str) -> np.ndarray | None:
        with closing(self._short()) as conn:
            row = conn.execute(
                "SELECT dimensions, vector FROM embeddings WHERE cache_key = ?",
                (cache_key,)).fetchone()
        if row is None:
            return None
        dimensions, blob = row
        if len(blob) != dimensions * np.dtype(np.float32).itemsize:
            return None
        return np.frombuffer(blob, dtype="<f4").copy()

    def put(self, cache_key: str, vector: np.ndarray) -> None:
        vec = np.ascontiguousarray(vector, dtype="<f4").reshape(-1)
        with closing(self._short()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embeddings"
                " (cache_key, dimensions, vector) VALUES (?, ?, ?)",
                (cache_key, int(vec.size), vec.tobytes()))
