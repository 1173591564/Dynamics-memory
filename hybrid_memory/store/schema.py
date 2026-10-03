"""建表与迁移（H10/N23）：各库身份、版本与增量迁移，高版本拒绝启动。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..errors import Fatal

SCHEMA_VERSION = 1


def open_db(path: str | Path, kind: str = "tasks") -> sqlite3.Connection:
    """按库身份打开 SQLite：WAL + synchronous + FK + busy_timeout（返回连接）。"""
    if str(path) == ":memory:":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    migrate(conn, kind=kind)
    ensure_schema(conn, kind=kind)
    return conn


def ensure_schema(conn: sqlite3.Connection, kind: str = "tasks") -> None:
    """幂等建表（记录版本）。"""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (kind TEXT PRIMARY KEY, version INTEGER NOT NULL)")
    conn.execute(
        "INSERT INTO schema_version(kind, version) VALUES(?, ?) "
        "ON CONFLICT(kind) DO UPDATE SET version=MAX(version, excluded.version)",
        (kind, SCHEMA_VERSION),
    )


def migrate(conn: sqlite3.Connection, kind: str = "tasks") -> None:
    """版本迁移；高版本库抛 `Fatal`（拒绝启动，不自动降级，先于 DDL）。"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row:
        ver_row = conn.execute(
            "SELECT version FROM schema_version WHERE kind=?", (kind,)
        ).fetchone()
        if ver_row:
            v = ver_row[0]
            if v > SCHEMA_VERSION:
                raise Fatal(f"database {kind} version {v} is higher than supported {SCHEMA_VERSION}")
