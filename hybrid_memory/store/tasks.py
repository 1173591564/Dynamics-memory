"""SQLite 调查与语义任务日志。任务/产物是 JSON，效果 checkpoint 与回执同事务提交。

不承诺模型只执行一次；租约超时可重试，过期 token 无权提交。多个进程不能
共享一个内存引擎，checkpoint revision CAS 至少阻止旧实例覆盖新状态。

P3 合并：claim/store_result/retry/finish/complete/recover 单状态机 + KindPolicy
（H7/H8）；旧 claim_semantic/store_semantic_result/complete_semantic/
retry_semantic/recover_semantic_expired 已删除（调用方已切统一 API）。
本模块 import dispatch.policy 是数据依赖（policy 是只引 errors 的叶子），
P5 分层测试将其列入白名单。
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

from ..dispatch.policy import policy_for
from ..service.context import SignalClosed


SEMANTIC_KINDS = frozenset({"conflict_pending", "feedback_pending", "maintenance_due"})
WORKFLOW_KINDS = frozenset({"hauler_due", "selector_due", "reviewer_due"})


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
 decision TEXT, created_at REAL NOT NULL, UNIQUE(source_task,target_id,candidate)
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
        rule_columns = {r[1] for r in self._conn.execute("PRAGMA table_info(agent_rules)")}
        if "scope" not in rule_columns:
            self._conn.execute("ALTER TABLE agent_rules ADD COLUMN scope TEXT NOT NULL DEFAULT 'project'")

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

    def recover_expired(self, max_attempts=None, max_apply_attempts=None, *,
                        kinds, reset_next_run_at):
        """统一过期回收（P3 合并 H7/H8，照抄两机旧语义）。

        kinds：显式回收范围（无默认——调用方必须声明，避免调查 worker
        误触 trio/语义任务）。dead 需同时满足：调用方给了上限、计数达限、
        政策 on_exhausted=dead。reset_next_run_at 照抄旧机差异：A 机不碰
        next_run_at，B 机重置为 now（前向时钟下不影响可领性，但快照值不同）。
        """
        now = self.clock()
        kinds = tuple(kinds)
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT id,kind,state,attempts,apply_attempts FROM tasks "
                f"WHERE kind IN ({','.join('?' for _ in kinds)}) "
                "AND state IN ('running','applying') AND lease_until<=?",
                (*kinds, now)).fetchall()
            for r in rows:
                policy = policy_for(r["kind"])
                applying = r["state"] == "applying"
                attempts = r["apply_attempts"] if applying else r["attempts"]
                cap = max_apply_attempts if applying else max_attempts
                if (cap is not None and attempts >= cap
                        and policy.on_exhausted == "dead"):
                    state = "dead"
                else:
                    state = "ready" if applying else "pending"
                if reset_next_run_at:
                    conn.execute("UPDATE tasks SET state=?,token=NULL,lease_until=NULL,"
                                 "last_error='lease expired',next_run_at=?,updated_at=? WHERE id=?",
                                 (state, now, now, r["id"]))
                else:
                    conn.execute("UPDATE tasks SET state=?,token=NULL,lease_until=NULL,"
                                 "last_error='lease expired',updated_at=? WHERE id=?",
                                 (state, now, r["id"]))
            # A 机旧语义：pending/ready 上已达上限的 dead-policy 任务直接 dead
            #（B 机无此条：语义/trio 调用方不传上限，天然跳过）。
            if max_attempts is not None or max_apply_attempts is not None:
                for kind in kinds:
                    if policy_for(kind).on_exhausted != "dead":
                        continue
                    conn.execute("UPDATE tasks SET state='dead',"
                                 "last_error='attempt limit exhausted',updated_at=? "
                                 "WHERE kind=? AND ((state='pending' AND attempts>=?) "
                                 "OR (state='ready' AND apply_attempts>=?))",
                                 (now, kind,
                                  max_attempts if max_attempts is not None else 2**62,
                                  max_apply_attempts if max_apply_attempts is not None else 2**62))

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

    def claim(self, task_id, *, before=None, origin=None, day=None, daily_cap=None,
              lease_s=None, checkpoint: bytes | None = None,
              expected_revision: int | None = None, expected_version: int):
        """统一领取（P3 合并：A 机全参 + B 机只传 expected_version/lease_s）。

        None 语义（照抄 B 机旧行为）：daily_cap=None 跳过每日计数；
        lease_s=None 取政策值；checkpoint=None 不写 checkpoint、返回无 revision 键；
        before/origin=None 时 COALESCE 保持原值。未知 kind 抛 Fatal（H25）。
        """
        now = self.clock()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                return None
            policy = policy_for(row["kind"])
            if row["state"] not in policy.claim_from or row["next_run_at"] > now:
                return None
            if row["version"] != expected_version:
                return None  # 列出任务后发生合并，下一轮使用新的 payload/t 重新算因果界
            applying = row["state"] == "ready"
            if not applying and daily_cap is not None:
                daily = conn.execute("SELECT runs FROM daily_runs WHERE day=?", (day,)).fetchone()
                if (daily[0] if daily else 0) >= daily_cap:
                    return None
                conn.execute("INSERT INTO daily_runs(day,runs) VALUES(?,1) "
                             "ON CONFLICT(day) DO UPDATE SET runs=runs+1", (day,))
            if lease_s is None:
                lease_s = policy.lease_s
            extra = {}
            if checkpoint is not None:
                extra["revision"] = self._write_checkpoint(conn, checkpoint, expected_revision)
            token = secrets.token_hex(16)
            field = "apply_attempts" if applying else "attempts"
            conn.execute(f"UPDATE tasks SET state=?,{field}={field}+1,token=?,lease_until=?,"
                         "before_t=COALESCE(before_t,?),origin=COALESCE(origin,?),updated_at=? WHERE id=?",
                         ("applying" if applying else "running", token, now + lease_s,
                          before, origin, now, task_id))
            result = self._decode(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
            result.update(extra)
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

    def store_result(self, task_id, token, result, *, checkpoint: bytes | None = None,
                     expected_revision: int | None = None, rule_ids=()):
        """统一存产物（P3 合并）。checkpoint=None 不写检查点、返回 None（B 机旧形状）；
        否则写检查点并返回新 revision（A 机旧形状）。rule_ids 为空时无额外写入。"""
        with self.transaction() as conn:
            self._owned(conn, task_id, token, ("running",))
            revision = None
            if checkpoint is not None:
                revision = self._write_checkpoint(conn, checkpoint, expected_revision)
            conn.execute("UPDATE tasks SET result=?,state='ready',token=NULL,lease_until=NULL,"
                         "next_run_at=0,updated_at=? WHERE id=?",
                         (encode(result), self.clock(), task_id))
            for rule_id in rule_ids:
                conn.execute("INSERT OR IGNORE INTO agent_rule_uses(task_id,rule_id) VALUES(?,?)",
                             (task_id, rule_id))
        return revision

    def retry(self, task_id, token, error, *, max_attempts=None, max_apply_attempts=None,
              delay=None, retry_model=False):
        """统一重试（P3 合并 H8）。上限取调用值，无则取政策值，再无则永不 dead；
        dead 还需政策 on_exhausted=dead。delay=None 时按政策 backoff 公式退避
        （B 机旧公式）；retry_model 重开整轮并清空产物（B 机旧语义）。恒返回新状态
        （B 机旧调用方忽略返回值）。"""
        with self.transaction() as conn:
            row = self._owned(conn, task_id, token)
            policy = policy_for(row["kind"])
            applying = row["state"] == "applying"
            attempts = (row["apply_attempts"] if applying else row["attempts"])
            state = "pending" if retry_model else ("ready" if applying else "pending")
            cap = max_apply_attempts if applying else max_attempts
            if cap is None:
                cap = policy.max_attempts
            if cap is not None and attempts >= cap and policy.on_exhausted == "dead":
                state = "dead"
            if delay is None:
                delay = min(300, policy.backoff ** min(8, attempts))
            conn.execute("UPDATE tasks SET state=?,token=NULL,lease_until=NULL,last_error=?,"
                         "result=CASE WHEN ? THEN NULL ELSE result END,"
                         "next_run_at=?,updated_at=? WHERE id=?",
                         (state, str(error)[:1000], int(retry_model and state != "dead"),
                          self.clock() + delay, self.clock(), task_id))
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

    def complete(self, task_id, token, mutate, dump_state, expected_revision):
        """效果/checkpoint/回执/完成状态同事务，不存在效果提交后未 ack 窗口。

        原 complete_semantic 改名（P3 合并）：kind-guard 随旧 API 删除，
        产物缺失检查保留；其余逐行照抄。
        """
        with self.transaction() as conn:
            row = self._owned(conn, task_id, token, ("applying",))
            if row["result"] is None:
                raise TaskLeaseLost("产物缺失")
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

    def rule_snapshot(self, target, context):
        """Versioned and scoped prompt guidance, with a literal scope guard."""
        text = context.casefold()
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,target,scope,instruction FROM agent_rules "
                "WHERE target=? AND enabled=1 ORDER BY id", (target,)).fetchall()
        return [dict(row) for row in rows if row["scope"] == "project" or
                (row["scope"].startswith("entity:") and
                 row["scope"][7:].casefold() in text)]

    def rule_report(self):
        with self._lock:
            return [dict(r) for r in self._conn.execute(
                "SELECT r.id,r.target,r.scope,r.instruction,r.enabled,r.source_task,"
                "COUNT(u.task_id) AS uses FROM agent_rules r "
                "LEFT JOIN agent_rule_uses u ON u.rule_id=r.id GROUP BY r.id ORDER BY r.id")]

    def disable_rule(self, rule_id):
        """Human/offline rollback; history and usage remain inspectable."""
        with self.transaction() as conn:
            cur = conn.execute("UPDATE agent_rules SET enabled=0 WHERE id=? AND enabled=1",
                               (rule_id,))
            if cur.rowcount:
                conn.execute("INSERT INTO agent_rule_audit(rule_id,action,actor,at) "
                             "VALUES(?,'disable','local_human',?)", (rule_id, self.clock()))
            return bool(cur.rowcount)

    def rules_for(self, target):
        with self._lock:
            return [r[0] for r in self._conn.execute(
                "SELECT instruction FROM agent_rules WHERE target=? AND enabled=1 ORDER BY id",
                (target,)).fetchall()]

    def workflow_trace(self, unit_ids, *, before_task_id):
        """Bounded persisted handoff evidence that existed before review routing.

        A pending task is not presented as an accepted candidate or decision.
        """
        ids = set(unit_ids)
        trace = []
        with self._lock:
            trigger = self._conn.execute("SELECT created_at FROM tasks WHERE id=?",
                                         (before_task_id,)).fetchone()
            if trigger is None:
                raise ValueError("review trigger task missing")
            rows = self._conn.execute(
                "SELECT t.id,t.kind,t.payload,t.result,t.state,t.updated_at,o.response "
                "FROM tasks t LEFT JOIN operations o ON o.task_id=t.id "
                "AND o.op_key='semantic' WHERE t.id<? "
                "AND t.kind IN ('hauler_due','selector_due') ORDER BY t.id",
                (before_task_id,)).fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                if payload.get("unit_id") not in ids:
                    continue
                entry = {"task_id": row["id"], "kind": row["kind"],
                         "unit_id": payload["unit_id"],
                         "state": ("done" if row["state"] == "done" and
                                   row["updated_at"] <= trigger[0] else
                                   "pending_at_complaint")}
                if row["kind"] == "selector_due":
                    entry["parent_task"] = payload.get("parent_task")
                    entry["candidates"] = payload.get("candidates", [])
                if entry["state"] == "done":
                    entry["rule_ids"] = [r[0] for r in self._conn.execute(
                        "SELECT rule_id FROM agent_rule_uses WHERE task_id=? ORDER BY rule_id",
                        (row["id"],))]
                    entry["agent_output"] = json.loads(row["result"])
                    entry["committed_effect"] = (json.loads(row["response"])
                                                if row["response"] else None)
                trace.append(entry)
        if len(trace) > 18 or len(encode(trace)) > 24000:
            raise ValueError("review trace exceeds bounded context; manual investigation required")
        return trace

    def pending_reviews(self):
        with self._lock:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM human_reviews WHERE status='pending' ORDER BY id")]

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
                "WHERE kind IN ('conflict_pending','feedback_pending','maintenance_due','hauler_due','selector_due','reviewer_due') "
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
