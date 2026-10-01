"""SQLite 调查与语义任务日志。任务/产物是 JSON，效果 checkpoint 与回执同事务提交。

不承诺模型只执行一次；租约超时可重试，过期 token 无权提交。多个进程不能
共享一个内存引擎，checkpoint revision CAS 至少阻止旧实例覆盖新状态。
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time

from .investigation_context import SignalClosed


SEMANTIC_KINDS = frozenset({"conflict_pending", "feedback_pending", "maintenance_due"})


class TaskLeaseLost(SignalClosed):
    pass


class CheckpointConflict(RuntimeError):
    pass


class TaskQueueFull(RuntimeError):
    pass


class CaptureConflict(Exception):
    """同一 request-id 已绑定不同正文。不得改绑，也不得当成新请求执行。"""


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


_SCHEMA = """
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
CREATE TABLE IF NOT EXISTS capture_receipts (
 request_id TEXT PRIMARY KEY, kind TEXT NOT NULL, fingerprint TEXT NOT NULL,
 response TEXT NOT NULL, created_at REAL NOT NULL
);
"""


class TaskStore:
    def __init__(self, path: str | Path | None = None, *, clock=None, capacity=4096):
        self.clock = clock or time.time
        self.capacity = max(1, int(capacity))
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path) if path else ":memory:",
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.execute("PRAGMA foreign_keys=ON")
        if path:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(_SCHEMA)
        columns = {r[1] for r in self._conn.execute("PRAGMA table_info(tasks)")}
        for name, definition in (("version", "INTEGER NOT NULL DEFAULT 0"), ("dedupe_id", "INTEGER")):
            if name not in columns:
                self._conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")

    @contextmanager
    def transaction(self):
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            yield self._conn

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        out = dict(row)
        for key in ("payload", "result"):
            if out[key] is not None:
                out[key] = json.loads(out[key])
        return out

    def get(self, task_id):
        with self._lock:
            return self._decode(self._conn.execute("SELECT * FROM tasks WHERE id=?",
                                                   (task_id,)).fetchone())

    def list_tasks(self, *, states=None, kinds=None):
        query, params = "SELECT * FROM tasks WHERE 1=1", []
        for field, values in (("state", states), ("kind", kinds)):
            if values is not None:
                values = tuple(values)
                if not values:
                    return []
                query += f" AND {field} IN ({','.join('?' for _ in values)})"
                params.extend(values)
        with self._lock:
            return [self._decode(r) for r in self._conn.execute(query + " ORDER BY id", params)]

    def enqueue(self, kind, payload, t, *, key="", merge=None, memory_next_id=0):
        with self.transaction() as conn:
            return self._enqueue(conn, kind, payload, t, key=key, merge=merge,
                                 memory_next_id=memory_next_id)

    def _enqueue(self, conn, kind, payload, t, *, key="", merge=None, memory_next_id=0):
        """与 unit checkpoint 共用事务；不得在此方法内部再次 BEGIN。"""
        now = self.clock()
        conn.execute("INSERT INTO metadata(key,value) VALUES('memory_next_id',?) "
                     "ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)",
                     (memory_next_id,))
        row = conn.execute("SELECT * FROM tasks WHERE kind=? AND task_key=? "
                           "AND state='pending' AND attempts=0", (kind, key)).fetchone() if key else None
        if row:
            old = json.loads(row["payload"])
            value = merge(old, payload) if merge else payload
            conn.execute("UPDATE tasks SET payload=?,t=?,updated_at=?,version=version+1 WHERE id=?",
                         (encode(value), max(t, row["t"]), now, row["id"]))
            return row["id"]
        count = conn.execute("SELECT COUNT(*) FROM tasks WHERE state IN "
                             "('pending','running','ready','applying')").fetchone()[0]
        if count >= self.capacity:
            raise TaskQueueFull(f"任务队列容量 {self.capacity} 已满；未接受新任务")
        completed = conn.execute("SELECT id FROM tasks WHERE kind=? AND task_key=? "
                                 "AND state='done' ORDER BY updated_at DESC,id DESC LIMIT 1",
                                 (kind, key)).fetchone() if key else None
        cur = conn.execute("INSERT INTO tasks(kind,task_key,payload,t,state,created_at,updated_at,dedupe_id) "
                           "VALUES (?,?,?,?,'pending',?,?,?)",
                           (kind, key, encode(payload), t, now, now, completed[0] if completed else None))
        return cur.lastrowid

    def memory_next_id(self):
        with self._lock:
            row = self._conn.execute("SELECT value FROM metadata WHERE key='memory_next_id'").fetchone()
            return row[0] if row else 0

    def checkpoint(self):
        with self._lock:
            row = self._conn.execute("SELECT revision,state FROM checkpoint WHERE id=1").fetchone()
            if row is not None:
                if type(row["revision"]) is not int or row["revision"] < 1:
                    raise CheckpointConflict("durable checkpoint revision 非法")
                return row["revision"], row["state"]
            used = self._conn.execute("SELECT 1 FROM tasks WHERE attempts>0 LIMIT 1").fetchone()
            receipt = self._conn.execute("SELECT 1 FROM operations LIMIT 1").fetchone()
            unit_receipt = self._conn.execute("SELECT 1 FROM unit_receipts LIMIT 1").fetchone()
            if used or receipt or unit_receipt:
                raise CheckpointConflict("durable checkpoint 缺失，但存在已领取任务/操作回执")
            return 0, None

    @staticmethod
    def _write_checkpoint(conn, state: bytes, expected_revision: int):
        row = conn.execute("SELECT revision FROM checkpoint WHERE id=1").fetchone()
        revision = row[0] if row else 0
        if revision != expected_revision:
            raise CheckpointConflict("checkpoint 已由其他服务实例推进；请重启加载最新状态")
        revision += 1
        conn.execute("INSERT INTO checkpoint(id,revision,state) VALUES(1,?,?) "
                     "ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,state=excluded.state",
                     (revision, state))
        return revision

    def save_checkpoint(self, state, expected_revision):
        with self.transaction() as conn:
            revision = self._write_checkpoint(conn, state, expected_revision)
        return revision

    def runs_today(self, day):
        with self._lock:
            row = self._conn.execute("SELECT runs FROM daily_runs WHERE day=?", (day,)).fetchone()
            return row[0] if row else 0

    def recover_expired(self, max_attempts, max_apply_attempts):
        now = self.clock()
        with self.transaction() as conn:
            for active, pending, field, maximum in (
                    ("running", "pending", "attempts", max_attempts),
                    ("applying", "ready", "apply_attempts", max_apply_attempts)):
                conn.execute(f"UPDATE tasks SET state=CASE WHEN {field}>=? THEN 'dead' ELSE ? END, "
                             "token=NULL,lease_until=NULL,last_error='lease expired',updated_at=? "
                             "WHERE kind IN ('recall_miss','extract_due') AND state=? AND lease_until<=?", (maximum, pending, now, active, now))
            conn.execute("UPDATE tasks SET state='dead',last_error='attempt limit exhausted',updated_at=? "
                         "WHERE kind IN ('recall_miss','extract_due') AND ((state='pending' AND attempts>=?) OR (state='ready' AND apply_attempts>=?))",
                         (now, max_attempts, max_apply_attempts))

    def skip_recent(self, task_id, ttl):
        now = self.clock()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row or row["state"] != "pending" or row["attempts"] or not row["task_key"]:
                return False
            hit = conn.execute("SELECT 1 FROM tasks WHERE id=? AND state='done' "
                               "AND updated_at>? LIMIT 1", (row["dedupe_id"], now - ttl)).fetchone()
            if not hit:
                return False
            conn.execute("UPDATE tasks SET state='skipped',updated_at=? WHERE id=?", (now, task_id))
            return True

    def claim(self, task_id, *, before, origin, day, daily_cap, lease_s,
              checkpoint: bytes, expected_revision: int, expected_version: int):
        now = self.clock()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row or row["state"] not in ("pending", "ready") or row["next_run_at"] > now:
                return None
            if row["version"] != expected_version:
                return None  # 列出任务后发生合并，下一轮使用新的 payload/t 重新算因果界
            applying = row["state"] == "ready"
            if not applying:
                daily = conn.execute("SELECT runs FROM daily_runs WHERE day=?", (day,)).fetchone()
                if (daily[0] if daily else 0) >= daily_cap:
                    return None
                conn.execute("INSERT INTO daily_runs(day,runs) VALUES(?,1) "
                             "ON CONFLICT(day) DO UPDATE SET runs=runs+1", (day,))
            revision = self._write_checkpoint(conn, checkpoint, expected_revision)
            token = secrets.token_hex(16)
            field = "apply_attempts" if applying else "attempts"
            conn.execute(f"UPDATE tasks SET state=?,{field}={field}+1,token=?,lease_until=?,"
                         "before_t=COALESCE(before_t,?),origin=COALESCE(origin,?),updated_at=? WHERE id=?",
                         ("applying" if applying else "running", token, now + lease_s,
                          before, origin, now, task_id))
            result = self._decode(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
            result["revision"] = revision
        return result

    def _owned(self, conn, task_id, token, states=("running", "applying")):
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if (not row or row["state"] not in states or row["token"] != token
                or row["lease_until"] <= self.clock()):
            raise TaskLeaseLost(f"task {task_id} 租约已失效")
        return row

    def check_owned(self, task_id, token):
        with self._lock:
            self._owned(self._conn, task_id, token)

    def store_result(self, task_id, token, result, *, checkpoint: bytes, expected_revision: int):
        with self.transaction() as conn:
            self._owned(conn, task_id, token, ("running",))
            revision = self._write_checkpoint(conn, checkpoint, expected_revision)
            conn.execute("UPDATE tasks SET result=?,state='ready',token=NULL,lease_until=NULL,"
                         "updated_at=?,next_run_at=0 WHERE id=?", (encode(result), self.clock(), task_id))
        return revision

    def retry(self, task_id, token, error, *, max_attempts, max_apply_attempts, delay=0):
        with self.transaction() as conn:
            row = self._owned(conn, task_id, token)
            applying = row["state"] == "applying"
            attempts = row["apply_attempts"] if applying else row["attempts"]
            maximum = max_apply_attempts if applying else max_attempts
            state = "dead" if attempts >= maximum else ("ready" if applying else "pending")
            conn.execute("UPDATE tasks SET state=?,token=NULL,lease_until=NULL,last_error=?,"
                         "next_run_at=?,updated_at=? WHERE id=?",
                         (state, str(error)[:1000], self.clock() + delay, self.clock(), task_id))
            return state

    def finish(self, task_id, token):
        with self.transaction() as conn:
            self._owned(conn, task_id, token, ("applying",))
            conn.execute("UPDATE tasks SET state='done',token=NULL,lease_until=NULL,"
                         "last_error='',updated_at=? WHERE id=?", (self.clock(), task_id))

    def unit_receipt(self, unit_id):
        with self._lock:
            row = self._conn.execute("SELECT response FROM unit_receipts WHERE unit_id=?",
                                     (unit_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def apply_unit(self, unit_id, mutate, dump_state, handoffs, expected_revision):
        """单元效果、调查交接、checkpoint 和回执原子提交；跨库 ack 另行执行。"""
        with self.transaction() as conn:
            current = conn.execute("SELECT revision FROM checkpoint WHERE id=1").fetchone()
            if (current[0] if current else 0) != expected_revision:
                raise CheckpointConflict("checkpoint 已推进；拒绝旧内存实例处理 L0")
            old = conn.execute("SELECT response FROM unit_receipts WHERE unit_id=?",
                               (unit_id,)).fetchone()
            if old:
                return json.loads(old[0]), expected_revision, True
            response = mutate()
            for kind, payload, t, key, merge in handoffs:
                self._enqueue(conn, kind, payload, t, key=key, merge=merge,
                              memory_next_id=response["next_memory_id"])
            revision = self._write_checkpoint(conn, dump_state(), expected_revision)
            conn.execute("INSERT INTO unit_receipts VALUES(?,?,?)",
                         (unit_id, encode(response), self.clock()))
        return response, revision, False

    def read_capture(self, request_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT kind, fingerprint, response FROM capture_receipts WHERE request_id=?",
                (request_id,)).fetchone()
        if row is None:
            return None
        return {"kind": row[0], "fingerprint": row[1], "response": json.loads(row[2])}

    def _capture_hit(self, conn, capture):
        old = conn.execute(
            "SELECT fingerprint, response FROM capture_receipts WHERE request_id=?",
            (capture["request_id"],)).fetchone()
        if old is None:
            return None
        if old[0] != capture["fingerprint"]:
            raise CaptureConflict(f"request_id {capture['request_id']} 已绑定不同请求")
        return json.loads(old[1])

    def remember_capture(self, request_id, kind, fingerprint, response):
        """无引擎效果的接受回执。与查找同事务，避免空反馈在挤出检索后无法回放。"""
        capture = {"request_id": request_id, "fingerprint": fingerprint}
        with self.transaction() as conn:
            old = self._capture_hit(conn, capture)
            if old is not None:
                return old, True
            conn.execute(
                "INSERT INTO capture_receipts(request_id, kind, fingerprint, response, created_at)"
                " VALUES(?,?,?,?,?)",
                (request_id, kind, fingerprint, encode(response), self.clock()))
        return response, False

    def apply_effect(self, mutate, dump_state, expected_revision):
        """非单元 sidecar 改动、发射的任务和 checkpoint 共用一笔事务。"""
        with self.transaction() as conn:
            current = conn.execute("SELECT revision FROM checkpoint WHERE id=1").fetchone()
            if (current[0] if current else 0) != expected_revision:
                raise CheckpointConflict("checkpoint 已推进；拒绝旧内存实例")
            out = mutate(conn)
            revision = self._write_checkpoint(conn, dump_state(), expected_revision)
        return out, revision

    def apply_captured_effect(self, mutate, dump_state, expected_revision, capture):
        """效果、checkpoint 与 request-id 回执同事务。已有回执只返回，不执行 mutate。"""
        with self.transaction() as conn:
            current = conn.execute("SELECT revision FROM checkpoint WHERE id=1").fetchone()
            if (current[0] if current else 0) != expected_revision:
                raise CheckpointConflict("checkpoint 已推进；拒绝旧内存实例")
            old = self._capture_hit(conn, capture)
            if old is not None:
                return old, expected_revision, True
            out = mutate(conn)
            revision = self._write_checkpoint(conn, dump_state(), expected_revision)
            conn.execute(
                "INSERT INTO capture_receipts(request_id, kind, fingerprint, response, created_at)"
                " VALUES(?,?,?,?,?)",
                (capture["request_id"], capture["kind"], capture["fingerprint"],
                 encode(out), self.clock()))
        return out, revision, False

    def recover_semantic_expired(self):
        now = self.clock()
        with self.transaction() as conn:
            conn.execute("UPDATE tasks SET state=CASE WHEN state='running' THEN 'pending' ELSE 'ready' END, "
                         "token=NULL,lease_until=NULL,last_error='lease expired',next_run_at=?,updated_at=? "
                         "WHERE kind IN ('conflict_pending','feedback_pending','maintenance_due') "
                         "AND state IN ('running','applying') AND lease_until<=?", (now, now, now))

    def claim_semantic(self, task_id, version, lease_s=120):
        now = self.clock()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if (not row or row["kind"] not in SEMANTIC_KINDS
                    or row["state"] not in ("pending", "ready")
                    or row["version"] != version or row["next_run_at"] > now):
                return None
            token = secrets.token_hex(16)
            field = "attempts" if row["state"] == "pending" else "apply_attempts"
            state = "running" if row["state"] == "pending" else "applying"
            conn.execute(f"UPDATE tasks SET state=?,{field}={field}+1,token=?,lease_until=?,"
                         "updated_at=? WHERE id=?", (state, token, now + lease_s, now, task_id))
            return self._decode(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def store_semantic_result(self, task_id, token, result):
        with self.transaction() as conn:
            row = self._owned(conn, task_id, token, ("running",))
            if row["kind"] not in SEMANTIC_KINDS:
                raise TaskLeaseLost("非语义任务")
            conn.execute("UPDATE tasks SET result=?,state='ready',token=NULL,lease_until=NULL,"
                         "next_run_at=0,updated_at=? WHERE id=?",
                         (encode(result), self.clock(), task_id))

    def complete_semantic(self, task_id, token, mutate, dump_state, expected_revision):
        """效果/checkpoint/回执/完成状态同事务，不存在效果提交后未 ack 窗口。"""
        with self.transaction() as conn:
            row = self._owned(conn, task_id, token, ("applying",))
            if row["kind"] not in SEMANTIC_KINDS or row["result"] is None:
                raise TaskLeaseLost("非语义任务或产物缺失")
            result = json.loads(row["result"])
            current = conn.execute("SELECT revision FROM checkpoint WHERE id=1").fetchone()
            if (current[0] if current else 0) != expected_revision:
                raise CheckpointConflict("checkpoint 已推进；拒绝旧内存实例")
            # 同一事务中先释放旧任务的容量名额，允许迟到结果再发新的待办；
            # 整笔提交前其他连接看不到 done，失败则状态也回滚为 applying。
            conn.execute("UPDATE tasks SET state='done',token=NULL,lease_until=NULL,"
                         "last_error='',updated_at=? WHERE id=?", (self.clock(), task_id))
            out = mutate(conn, result)
            if out.get("recog_fail"):
                conn.execute("INSERT INTO metadata(key,value) VALUES('semantic_recog_fail',1) "
                             "ON CONFLICT(key) DO UPDATE SET value=value+1")
            if row["lease_until"] <= self.clock():
                raise TaskLeaseLost(f"task {task_id} 租约已失效")
            revision = self._write_checkpoint(conn, dump_state(), expected_revision)
            conn.execute("INSERT INTO operations(task_id,op_key,request,response,created_at) "
                         "VALUES (?,'semantic',?,?,?)", (task_id, row["result"], encode(out), self.clock()))
        return out, revision

    def retry_semantic(self, task_id, token, error):
        with self.transaction() as conn:
            row = self._owned(conn, task_id, token)
            if row["kind"] not in SEMANTIC_KINDS:
                raise TaskLeaseLost("非语义任务")
            state = "ready" if row["state"] == "applying" else "pending"
            attempts = row["apply_attempts"] if state == "ready" else row["attempts"]
            delay = min(300, 2 ** min(8, attempts))
            conn.execute("UPDATE tasks SET state=?,token=NULL,lease_until=NULL,last_error=?,"
                         "next_run_at=?,updated_at=? WHERE id=?",
                         (state, str(error)[:1000], self.clock() + delay, self.clock(), task_id))

    def apply_operation(self, task_id, token, request, mutate, dump_state, expected_revision):
        request_json = encode(request)
        key = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        with self.transaction() as conn:
            self._owned(conn, task_id, token)
            current = conn.execute("SELECT revision FROM checkpoint WHERE id=1").fetchone()
            if (current[0] if current else 0) != expected_revision:
                raise CheckpointConflict("checkpoint 已推进；拒绝旧内存实例应用或重放结果")
            old = conn.execute("SELECT response FROM operations WHERE task_id=? AND op_key=?",
                               (task_id, key)).fetchone()
            if old:
                return json.loads(old[0]), expected_revision, True
            response = mutate()
            self._owned(conn, task_id, token)  # 慢 embedding 后再次检查，不让过期执行体写入
            revision = self._write_checkpoint(conn, dump_state(), expected_revision)
            conn.execute("INSERT INTO operations VALUES (?,?,?,?,?)",
                         (task_id, key, request_json, encode(response), self.clock()))
        return response, revision, False

    def queued_counts(self):
        with self._lock:
            return dict(self._conn.execute(
                "SELECT kind,COUNT(*) FROM tasks WHERE state IN ('pending','ready') GROUP BY kind"))

    def semantic_stats(self):
        with self._lock:
            rows = list(self._conn.execute(
                "SELECT state,COUNT(*) FROM tasks WHERE kind IN "
                "('conflict_pending','feedback_pending','maintenance_due') GROUP BY state"))
            errors = [dict(r) for r in self._conn.execute(
                "SELECT id,kind,attempts,apply_attempts,last_error,next_run_at FROM tasks "
                "WHERE kind IN ('conflict_pending','feedback_pending','maintenance_due') "
                "AND last_error<>'' ORDER BY updated_at DESC LIMIT 5")]
            retrying = self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE kind IN "
                "('conflict_pending','feedback_pending','maintenance_due') "
                "AND state IN ('pending','ready') AND next_run_at>?", (self.clock(),)).fetchone()[0]
            failure = self._conn.execute(
                "SELECT value FROM metadata WHERE key='semantic_recog_fail'").fetchone()
            return {"states": dict(rows), "retrying": retrying, "errors": errors,
                    "recog_fail": failure[0] if failure else 0}

    def stats(self):
        with self._lock:
            counts = {r[0]: r[1] for r in self._conn.execute("SELECT state,COUNT(*) FROM tasks GROUP BY state")}
            counts["operations"] = self._conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
            return counts

    def close(self):
        with self._lock:
            self._conn.close()
