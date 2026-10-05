"""建表与迁移（H10/N23/N45）：三库（log/tasks/cache）身份、版本与增量迁移。

- open_db(path, kind)：唯一连接入口——WAL + synchronous=FULL + FK +
  busy_timeout，isolation_level=None（自动提交模式，事务由调用方显式
  BEGIN/COMMIT；消除 sqlite3 legacy 隐式事务坑）；
- migrate(conn, kind)：高版本库先 Fatal 再谈 DDL（不留半迁移痕迹）；
  无版本 legacy 库（v0）迁入当前版本，不清数据、不降级；
- ensure_schema(conn, kind)：幂等建对应库表索引 + legacy 增量补列。

三库身份版本分别登记在各自库的 schema_version(kind, version)，不能共用
错误 DDL。业务表 DDL 的唯一来源是本模块（Store 不得再内联 CREATE TABLE）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..errors import Fatal

SCHEMA_VERSION = 2

_DDL_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 kind TEXT NOT NULL, task_key TEXT NOT NULL, payload TEXT NOT NULL, t INTEGER NOT NULL,
 version INTEGER NOT NULL DEFAULT 0, dedupe_id INTEGER,
 state TEXT NOT NULL CHECK(state IN ('pending','running','ready','applying','done','dead','skipped')),
 attempts INTEGER NOT NULL DEFAULT 0, apply_attempts INTEGER NOT NULL DEFAULT 0,
 before_t INTEGER, origin TEXT, token TEXT, lease_until REAL,
 result TEXT, last_error TEXT NOT NULL DEFAULT '', next_run_at REAL NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS tasks_state ON tasks(state, next_run_at, id);
CREATE INDEX IF NOT EXISTS tasks_key ON tasks(kind, task_key, state, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS tasks_mergeable ON tasks(kind, task_key)
 WHERE state='pending' AND attempts=0 AND task_key<>'';
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS daily_runs (day TEXT PRIMARY KEY, runs INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS checkpoint (
 id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, state BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS operations (
 task_id INTEGER NOT NULL REFERENCES tasks(id), op_key TEXT NOT NULL,
 request TEXT NOT NULL, response TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(task_id, op_key)
);
CREATE TABLE IF NOT EXISTS unit_receipts (
 unit_id INTEGER PRIMARY KEY, response TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_rules (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_task INTEGER NOT NULL, target TEXT NOT NULL,
 instruction TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL,
 scope TEXT NOT NULL DEFAULT 'project',
 UNIQUE(source_task,target,instruction)
);
CREATE TABLE IF NOT EXISTS agent_rule_uses (
 task_id INTEGER NOT NULL, rule_id INTEGER NOT NULL, PRIMARY KEY(task_id,rule_id)
);
CREATE TABLE IF NOT EXISTS agent_rule_audit (
 id INTEGER PRIMARY KEY, rule_id INTEGER NOT NULL, action TEXT NOT NULL,
 actor TEXT NOT NULL, at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_rule_feedback (
 reviewer_task INTEGER NOT NULL, rule_id INTEGER NOT NULL, assessment TEXT NOT NULL,
 reason TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY(reviewer_task,rule_id)
);
CREATE TABLE IF NOT EXISTS human_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_task INTEGER NOT NULL, target_id INTEGER NOT NULL,
 candidate TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 decision TEXT, created_at REAL NOT NULL, review_key TEXT NOT NULL DEFAULT '',
 target_stamp TEXT NOT NULL DEFAULT '', UNIQUE(source_task,target_id,candidate)
);
CREATE UNIQUE INDEX IF NOT EXISTS reviews_pending_key ON human_reviews(review_key)
 WHERE status='pending' AND review_key<>'';
CREATE TABLE IF NOT EXISTS capture_receipts (
 request_id TEXT PRIMARY KEY, kind TEXT NOT NULL, fingerprint TEXT NOT NULL,
 response TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS task_call_contexts (
 task_id INTEGER NOT NULL REFERENCES tasks(id), token TEXT NOT NULL,
 context TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(task_id, token)
);
"""

_DDL_LOG = """
CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY,
    t INTEGER NOT NULL,
    ts REAL NOT NULL,
    scene TEXT NOT NULL DEFAULT '',
    user_text TEXT NOT NULL,
    assistant_text TEXT NOT NULL,
    assistant_turns INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS units_t ON units(t);
CREATE VIRTUAL TABLE IF NOT EXISTS units_fts USING fts5(
    user_text, assistant_text, content='units', content_rowid='id',
    tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS units_ai AFTER INSERT ON units BEGIN
    INSERT INTO units_fts(rowid, user_text, assistant_text)
    VALUES (new.id, new.user_text, new.assistant_text);
END;
CREATE TABLE IF NOT EXISTS mentions (
    entity TEXT NOT NULL,
    kind TEXT NOT NULL,
    unit_id INTEGER NOT NULL,
    PRIMARY KEY (entity, unit_id)
);
CREATE INDEX IF NOT EXISTS mentions_unit ON mentions(unit_id);
CREATE TABLE IF NOT EXISTS unit_emb (
    unit_id INTEGER PRIMARY KEY,
    dims INTEGER NOT NULL,
    vec BLOB NOT NULL
);
-- Only online append creates a row. Legacy units are deliberately not replayed.
CREATE TABLE IF NOT EXISTS unit_work (
    unit_id INTEGER PRIMARY KEY REFERENCES units(id),
    state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','done')),
    result TEXT, context TEXT NOT NULL DEFAULT '{}', attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '', next_run_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS unit_work_order ON unit_work(state,unit_id);
CREATE TABLE IF NOT EXISTS capture_receipts (
    request_id TEXT PRIMARY KEY,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    fingerprint TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""

_DDL_CACHE = ("CREATE TABLE IF NOT EXISTS embeddings ("
              "cache_key TEXT PRIMARY KEY, "
              "dimensions INTEGER NOT NULL, "
              "vector BLOB NOT NULL)")

_DDL: dict[str, str] = {"tasks": _DDL_TASKS, "log": _DDL_LOG, "cache": _DDL_CACHE}

KINDS = tuple(sorted(_DDL))


def _connect(path: str | Path) -> sqlite3.Connection:
    """打开连接：自动提交模式（isolation_level=None，事务显式 BEGIN）。"""
    if str(path) == ":memory:":
        return sqlite3.connect(":memory:", check_same_thread=False,
                               isolation_level=None)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(p), check_same_thread=False,
                           isolation_level=None)


def open_db(path: str | Path, kind: str = "tasks") -> sqlite3.Connection:
    """按库身份打开 SQLite：WAL + synchronous + FK + busy_timeout（返回连接）。

    迁移顺序：migrate（高版本先 Fatal）→ ensure_schema（幂等 DDL + 增量列）。
    """
    if kind not in _DDL:
        raise Fatal(f"unknown database kind: {kind!r} (expected one of {KINDS})")
    conn = _connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    migrate(conn, kind=kind)
    ensure_schema(conn, kind=kind)
    return conn


def _ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version "
                 "(kind TEXT PRIMARY KEY, version INTEGER NOT NULL)")


def migrate(conn: sqlite3.Connection, kind: str = "tasks") -> None:
    """版本迁移；高版本库抛 `Fatal`（拒绝启动，不自动降级，先于 DDL）。

    无版本 legacy 库（v0，早于 schema 接线的现存数据）由 ensure_schema
    幂等建表 + 增量补列迁入并登记当前版本；不清数据、不降级。
    """
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
                raise Fatal(
                    f"database {kind} version {v} is higher than supported "
                    f"{SCHEMA_VERSION}; refusing to start (no downgrade, no "
                    "partial DDL)")


def ensure_schema(conn: sqlite3.Connection, kind: str = "tasks") -> None:
    """幂等建表（记录版本）+ legacy 增量补列（不清数据）。"""
    if kind == "tasks":
        review_columns = {r[1] for r in conn.execute("PRAGMA table_info(human_reviews)")}
        if review_columns:
            for name in ("review_key", "target_stamp"):
                if name not in review_columns:
                    conn.execute(f"ALTER TABLE human_reviews ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    conn.executescript(_DDL[kind])
    # ---- legacy 增量迁移：老库缺列就地补（有数据的库不清不重建） ----
    if kind == "tasks":
        columns = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        for name, definition in (("version", "INTEGER NOT NULL DEFAULT 0"),
                                 ("dedupe_id", "INTEGER")):
            if name not in columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")
        rule_columns = {r[1] for r in conn.execute("PRAGMA table_info(agent_rules)")}
        if "scope" not in rule_columns:
            conn.execute("ALTER TABLE agent_rules ADD COLUMN scope "
                         "TEXT NOT NULL DEFAULT 'project'")
    elif kind == "log":
        cols = {r[1] for r in conn.execute("PRAGMA table_info(unit_work)")}
        if "context" not in cols:
            conn.execute("ALTER TABLE unit_work ADD COLUMN context "
                         "TEXT NOT NULL DEFAULT '{}'")
    _ensure_version_table(conn)
    conn.execute(
        "INSERT INTO schema_version(kind, version) VALUES(?, ?) "
        "ON CONFLICT(kind) DO UPDATE SET version=MAX(version, excluded.version)",
        (kind, SCHEMA_VERSION),
    )
