"""建表与迁移（P2 空壳，H10；P3/P4 通电）。"""
from __future__ import annotations

SCHEMA_VERSION = 1


def open_db(path):  # noqa: ANN001, ANN202 — 壳，P3 定类型
    """打开 SQLite：WAL + busy_timeout（返回连接）。"""
    raise NotImplementedError("store.schema.open_db: P3/P4 通电")


def ensure_schema(conn) -> None:  # noqa: ANN001 — 壳，P3 定类型
    """建表（幂等）。"""
    raise NotImplementedError("store.schema.ensure_schema: P3/P4 通电")


def migrate(conn) -> None:  # noqa: ANN001 — 壳，P3 定类型
    """版本迁移；高版本库抛 `Fatal`（拒绝启动，不自动降级）。"""
    raise NotImplementedError("store.schema.migrate: P3/P4 通电")
