"""SQLite 向量缓存：只保存 cache_key → float32 bytes，不存原文/密钥/响应全文。"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

_SCHEMA = ("CREATE TABLE IF NOT EXISTS embeddings ("
           "cache_key TEXT PRIMARY KEY, "
           "dimensions INTEGER NOT NULL, "
           "vector BLOB NOT NULL)")


class SqliteEmbeddingCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(self.path))) as conn:
            with conn:
                conn.execute(_SCHEMA)

    def get(self, cache_key: str) -> np.ndarray | None:
        with closing(sqlite3.connect(str(self.path))) as conn:
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
        with closing(sqlite3.connect(str(self.path))) as conn:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings"
                    " (cache_key, dimensions, vector) VALUES (?, ?, ?)",
                    (cache_key, int(vec.size), vec.tobytes()))
