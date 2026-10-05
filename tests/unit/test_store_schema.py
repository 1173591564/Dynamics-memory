"""store/schema.py 接线回归（P0-2 / H10/N23 / N45）。

覆盖：
- 三库身份版本（log/tasks/cache）分别登记在各自库的 schema_version；
- 高版本库 → open_db Fatal 且先于任何新 DDL（不留半迁移痕迹）；
- 无版本 legacy 库迁入 v1：不清数据、增量补列；
- sqlite3 隐式事务坑：连接 isolation_level=None（自动提交），事务全部
  显式 BEGIN，回滚完整；
- 双 DDL 消除：三个 Store 源文件不再内联 CREATE TABLE。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.errors import Fatal
from hybrid_memory.store import schema
from hybrid_memory.store.evidence import LogStore
from hybrid_memory.store.tasks import TaskStore


def test_review_v1_migration_preserves_rows_and_adds_version_keys(tmp_path):
    db = tmp_path / "tasks.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE schema_version(kind TEXT PRIMARY KEY, version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES('tasks', 1)")
        conn.execute("CREATE TABLE human_reviews(id INTEGER PRIMARY KEY, source_task INTEGER NOT NULL, "
                     "target_id INTEGER NOT NULL, candidate TEXT NOT NULL, reason TEXT NOT NULL, "
                     "status TEXT NOT NULL DEFAULT 'pending', decision TEXT, created_at REAL NOT NULL, "
                     "UNIQUE(source_task,target_id,candidate))")
        conn.execute("INSERT INTO human_reviews VALUES(1,2,3,'{}','legacy','pending',NULL,1)")
    store = TaskStore(db)
    try:
        row = dict(store._conn.execute("SELECT * FROM human_reviews WHERE id=1").fetchone())
        assert row["reason"] == "legacy" and row["status"] == "pending"
        assert row["review_key"] == row["target_stamp"] == ""
        assert schema.SCHEMA_VERSION >= 2
    finally:
        store.close()


def test_three_db_identities_are_separate(tmp_path):
    ts = TaskStore(tmp_path / "tasks.sqlite")
    try:
        rows = {r[0]: r[1] for r in ts._conn.execute(
            "SELECT kind, version FROM schema_version")}
        assert rows == {"tasks": schema.SCHEMA_VERSION}
    finally:
        ts.close()
    ls = LogStore(tmp_path / "log.sqlite")
    try:
        rows = {r[0]: r[1] for r in ls._conn.execute(
            "SELECT kind, version FROM schema_version")}
        assert rows == {"log": schema.SCHEMA_VERSION}
    finally:
        ls.close()
    cache = SqliteEmbeddingCache(tmp_path / "emb.sqlite3")
    with sqlite3.connect(tmp_path / "emb.sqlite3") as conn:
        rows = {r[0]: r[1] for r in conn.execute(
            "SELECT kind, version FROM schema_version")}
    assert rows == {"cache": schema.SCHEMA_VERSION}


def test_higher_version_refuses_before_ddl(tmp_path):
    """高版本库：先 Fatal，不执行新 DDL（不留半迁移痕迹）。"""
    db = tmp_path / "tasks.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE schema_version "
                     "(kind TEXT PRIMARY KEY, version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES('tasks', 99)")
        # 预置一个会被 ensure_schema 补建的表的反例：老库没有 checkpoint
    with pytest.raises(Fatal, match="99"):
        TaskStore(db)
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "checkpoint" not in tables, "Fatal 必须先于任何新 DDL"
    assert "tasks" not in tables, "老库结构不得被动"


def test_legacy_no_version_db_migrates_without_data_loss(tmp_path):
    """无版本 legacy 库：建旧形状 tasks 表+数据 → 迁入 v1 保数据补列。"""
    db = tmp_path / "tasks.sqlite"
    with sqlite3.connect(db) as conn:
        # 旧形状：无 version/dedupe_id 列（pre-schema 真实老库；其余列齐全）
        conn.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " kind TEXT NOT NULL, task_key TEXT NOT NULL, payload TEXT NOT NULL,"
            " t INTEGER NOT NULL, state TEXT NOT NULL,"
            " attempts INTEGER NOT NULL DEFAULT 0,"
            " apply_attempts INTEGER NOT NULL DEFAULT 0,"
            " before_t INTEGER, origin TEXT, token TEXT, lease_until REAL,"
            " result TEXT, last_error TEXT NOT NULL DEFAULT '',"
            " next_run_at REAL NOT NULL DEFAULT 0,"
            " created_at REAL NOT NULL, updated_at REAL NOT NULL)")
        conn.execute(
            "INSERT INTO tasks(kind,task_key,payload,t,state,result,"
            "created_at,updated_at)"
            " VALUES('conflict_pending','k','{}',0,'done','{\"x\":1}',1.0,1.0)")
    ts = TaskStore(db)
    try:
        row = ts.get(1)
        assert row is not None and row["kind"] == "conflict_pending", "数据必须保留"
        assert row["result"] == {"x": 1}, "产物数据必须保留"
        assert row["version"] == 0, "增量补列（version 默认 0）"
        ver = ts._conn.execute(
            "SELECT version FROM schema_version WHERE kind='tasks'").fetchone()
        assert ver[0] == schema.SCHEMA_VERSION, "legacy v0 迁入登记当前版本"
    finally:
        ts.close()


def test_legacy_log_db_migrates_without_data_loss(tmp_path):
    db = tmp_path / "log.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE units (id INTEGER PRIMARY KEY, t INTEGER NOT NULL,"
            " ts REAL NOT NULL, scene TEXT NOT NULL DEFAULT '',"
            " user_text TEXT NOT NULL, assistant_text TEXT NOT NULL,"
            " assistant_turns INTEGER NOT NULL DEFAULT 1)")
        conn.execute(
            "INSERT INTO units(id,t,ts,user_text,assistant_text)"
            " VALUES(0,0,1.0,'旧证据','旧回答')")
    ls = LogStore(db)
    try:
        u = ls.get(0)
        assert u is not None and u["user_text"] == "旧证据", "L0 数据必须保留"
        cols = {r[1] for r in ls._conn.execute("PRAGMA table_info(unit_work)")}
        assert "context" in cols, "增量补列（unit_work.context）"
    finally:
        ls.close()


def test_connections_use_explicit_transaction_mode(tmp_path):
    """isolation_level=None：无 Python 隐式事务；事务显式 BEGIN 且回滚完整。"""
    ts = TaskStore(tmp_path / "tasks.sqlite")
    try:
        assert ts._conn.isolation_level is None, "连接必须是自动提交模式"
        # 回滚完整：事务中写入后抛错 → 不留半行
        class _Boom(Exception):
            pass
        try:
            with ts.transaction() as conn:
                conn.execute(
                    "INSERT INTO tasks(kind,task_key,payload,t,state,"
                    "created_at,updated_at) VALUES('x','k','{}',0,'pending',1,1)")
                raise _Boom
        except _Boom:
            pass
        n = ts._conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE kind='x'").fetchone()[0]
        assert n == 0, "回滚必须完整"
        # 无活动悬挂事务（自动提交模式下 DML 即时生效）
        ts._conn.execute(
            "INSERT INTO tasks(kind,task_key,payload,t,state,"
            "created_at,updated_at) VALUES('y','k','{}',0,'pending',1,1)")
        assert not ts._conn.in_transaction, "自动提交模式不得留悬挂事务"
    finally:
        ts.close()
    ls = LogStore(tmp_path / "log.sqlite")
    try:
        assert ls._conn.isolation_level is None
    finally:
        ls.close()


def test_cache_higher_version_refuses(tmp_path):
    db = tmp_path / "emb.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE schema_version "
                     "(kind TEXT PRIMARY KEY, version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES('cache', 42)")
    with pytest.raises(Fatal):
        SqliteEmbeddingCache(db)


def test_cache_roundtrip_after_schema_wiring(tmp_path):
    db = tmp_path / "emb.sqlite3"
    cache = SqliteEmbeddingCache(db)
    vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    cache.put("k1", vec)
    back = cache.get("k1")
    assert back is not None and np.allclose(back, vec)
    assert cache.get("missing") is None


def test_dual_ddl_sources_eliminated():
    """三个 Store 源文件不再内联 CREATE TABLE（唯一 DDL 源 = store/schema.py）。"""
    import hybrid_memory
    root = Path(hybrid_memory.__file__).parent
    for rel in ("store/tasks.py", "store/evidence.py", "embed/cache.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "CREATE TABLE" not in src, f"{rel} 不得再内联 DDL"
    # schema.py 持有三库 DDL
    for kind in ("tasks", "log", "cache"):
        assert kind in schema._DDL, f"schema.py 缺 {kind} 库 DDL"
