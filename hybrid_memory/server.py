"""记忆引擎 sidecar：把 MemoryEngine + L0 logstore HTTP 服务化，供 opencode
插件调用——既服务主 agent（消费记忆），也服务调查员 agent（生产记忆）。

端点（JSON，除 /health 外一律要求 `Authorization: Bearer <token>`；
token 持久化在 state_dir/.memory-token，插件侧同路径读取或经环境变量注入）：

  读记忆
  GET  /health              → 状态。ok 只表示没有 checkpoint fault；
                              snapshot/units_pending/validation 分开报告，免鉴权
  GET  /recall?q=..&k=..    → {retrieval_id, context, selected}
  POST /search              → {query, k} 同 /recall（CJK 长查询走 body）
  GET  /conflicts           → 未决 tension 列表
  GET  /signals             → 调查/语义任务及 L0 单元积压与 worker 遥测

  写记忆（主回路）
  POST /observe             → {user_text, assistant_text, request_id?}：先落 L0 并建索引，
                              触发扫描 → extract_due / recall_miss；再 candgen
                              蒸馏（失败不丢单元）；蒸馏产物进池。
                              可选 request_id 与 L0 同事务绑定；已接受但效果未完成时
                              仍返回 accepted/unit_id（容量不足为 503），不能无 id 重投。
  POST /feedback            → {retrieval_id, question, answer, request_id?} 延迟记账。
                              request_id 与效果同事务；响应丢失后重投返回原回执。
  POST /resolve             → {left, right, verdict, entity_key?} 裁决回报
  POST /miss                → {query, hint?, source?} 上报一次记忆缺失
                              （主 agent 用了 log_* 工具 = 记忆没接住）

  操作日志（agent 工具面；只给片段/聚合，原文只经 /log/window 计量回展）
  POST /log/search          → {query, before?, scene?, k?}
  POST /log/timeline        → {entity, before?, limit?}
  POST /log/stats           → {group_by, before?, limit?}
  POST /log/window          → {unit_ids, max_chars?}

  操作面（agent 产物回流；服务端校验溯源/因果/脱敏/自指）
  POST /propose             → {proposals:[{text, kind, salience,
                               source_unit_ids, entity_key?, supersedes?}],
                               origin?} → {accepted, new_ids, rejected}
  POST /diagnose            → {miss_type, note?}
  POST /save                → 落盘状态快照

进程内调查员直接传 signal_id；兼容 HTTP 调用可带 X-Signal-Id。
按信号计量工具调用与回展预算，统一施加 before 因果上界。
passive=True 在独立引擎视图上检索；budget_tokens 限制整行上下文。

状态：<project>/.opencode/memory/ 下 log.sqlite（L0）与 tasks.sqlite
（调查和语义任务/产物/回执/checkpoint）。有 SQLite checkpoint 时以它为准，否则兼容
state.pkl；/save 更新 checkpoint 并导出 state.pkl。pickle 反序列化仍走白名单。
依赖注入（cfg/emb/semantics/generator/logstore）便于测试。
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from dataclasses import asdict, replace
import hashlib
import io
import json
import math
import os
import pickle
import re
import secrets
import signal as _signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import triggers
from .candgen.base import CandidateGenerator
from .candgen.chat import ChatGenerator
from .candgen.prompt import parse_ids, parse_salience, redact_secrets
from .config import Cfg
from .core.engine import MemoryEngine
from .core.types import Event, Memory, Pool, Query, Retrieval, Tension
from .interaction import InteractionUnit, InteractionWindow
from .embed.base import Embedder
from .llm import chat
from .investigation_context import (CausalViolation, InvestigationContext,
                                    SignalClosed)
from .logstore import LogStore, entities_in
from .semantics import normalize
from .semantics.llm import LLMSemantics
from .core import maintenance
from .core.types import FeedbackSemantics, ConsolidationSemantics, is_visible
from .taskstore import SEMANTIC_KINDS, WORKFLOW_KINDS, TaskLeaseLost
from .taskstore import TaskStore, TaskQueueFull, CheckpointConflict, CaptureConflict, encode

_RETRIEVAL_KEEP = 512   # retrieval 注册表上限（feedback 用，防无界增长）
# [^>]* 单趟即可：匹配内部不含 '>'，嵌套 payload 被整体吃掉，
# 任何残留的 "relevant-memories" 片段都凑不成完整 tag
_MEM_TAG_RE = re.compile(r"<\s*/?\s*relevant-memories[^>]*>", re.IGNORECASE)
# 自指：记忆系统自身的操作过程不是项目事实（candgen prompt 已禁，
# 这里是操作面的第二道闸）
_SELF_REF_RE = re.compile(
    r"(?:memory_(?:search|propose|resolve|diagnose|conflicts)|"
    r"log_(?:search|timeline|stats|window)|relevant-memories|"
    r"(?:我|已|刚|调查员|系统)(?:已经)?(?:检索|查询|查阅|回展|裁决|合并|归档|提议|"
    r"调查)了?(?:一下|一遍|相关)?(?:记忆|日志|冲突)|"
    r"(?:记忆|日志)(?:里|中)(?:没有|未)(?:找到|查到|记录)|"
    r"(?:signal_id|recall_miss|extract_due))", re.IGNORECASE)
_MAX_PROPOSAL_CHARS = 1200
_MAIN_WINDOW_CAP = 1500          # 无信号上下文（主 agent）的单次回展上限
_ORIGINS = {"repair", "extract", "mining", "agent", "user_confirmed"}
_VERDICTS = {"synonym", "update", "contradiction", "collision", "pending"}
_MISS_SOURCES = {"recognizer_none", "correction", "agent_tool", "thin",
                 "external"}


def _safe_mem_text(text: str) -> str:
    """记忆文本进 <relevant-memories> 包裹块前的消毒：中和同名分隔符
    （含嵌套/带属性/自闭合变体），防存储型注入破 tag 逃逸污染
    system prompt。"""
    return _MEM_TAG_RE.sub(" ", text)


_COUNTERS = ("n_promote", "n_demote", "n_evict", "n_archive", "n_revive",
             "n_merge", "n_collision", "n_tension", "n_resolve", "n_agg",
             "n_consolidate", "n_shadow_dropped", "n_chain_broken")

_SERVICE_COUNTERS = ("n_candgen_fail", "n_missed", "n_proposals", "n_rejected",
                     "n_ungrounded")

_STATE_KEYS = {"mems", "tensions", "next_id", "consolidation_pending",
               "consolidation_deferred", "counters", "t", "unit_id", "scene"}

# Memory 后加字段：旧 state.pkl 反序列化出来的对象没有这些属性，
# 加载时按默认值补齐（dataclass 的 __dict__ 直接落盘，不会走 __init__）
_MEMORY_FIELD_DEFAULTS = {"origin": "passive", "entity": ""}

# state.pkl 受限反序列化白名单：state 只含内置容器/标量 + Memory/Tension/
# Pool + numpy 数组重建函数，其余 global 一律拒绝（pickle RCE 防线）
_PICKLE_SAFE = {
    ("builtins", n) for n in
    ("dict", "list", "tuple", "set", "frozenset", "bytes", "bytearray",
     "str", "int", "float", "bool", "complex", "slice", "range",
     "NoneType", "object")
} | {
    ("collections", "OrderedDict"), ("collections", "defaultdict"),
    ("collections", "Counter"),
    ("hybrid_memory.core.types", "Memory"),
    ("hybrid_memory.core.types", "Tension"),
    ("hybrid_memory.core.types", "Pool"),
    ("hybrid_memory.core.types", "Retrieval"),
    ("numpy._core.multiarray", "_reconstruct"),
    ("numpy.core.multiarray", "_reconstruct"),   # numpy<2 兼容
    ("numpy", "dtype"), ("numpy", "ndarray"),
}


def _legacy_pool_member(cls, name):
    """只兼容旧 Enum 的 getattr(Pool, 成员名)，绝不开放通用 getattr。"""
    if cls is Pool and type(name) is str and name in Pool.__members__:
        return Pool.__members__[name]
    raise pickle.UnpicklingError("state.pkl 含非法的 Pool 成员访问")


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if module in ("builtins", "__builtin__") and name == "getattr":
            return _legacy_pool_member
        if (module, name) in _PICKLE_SAFE:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"state.pkl 含未授权 global: {module}.{name}")


class ProposalRejected(ValueError):
    pass


class MemoryService:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics, generator:
                 CandidateGenerator, state_dir: Path | None = None,
                 logstore: LogStore | None = None, task_capacity: int = 4096):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.generator = generator
        self.engine = MemoryEngine(cfg, emb, semantics)
        self._lock = threading.RLock()
        # sidecar 的语义工作由 SQLite 领取，裸 MemoryEngine 仍使用内存 SignalWorker。
        self._semantic_busy = threading.Lock()
        self.state_path = (Path(state_dir) / "state.pkl"
                           if state_dir else None)
        self.log = logstore or LogStore(
            Path(state_dir) / "log.sqlite" if state_dir else None)
        self.tasks = TaskStore(Path(state_dir) / "tasks.sqlite" if state_dir else None,
                               capacity=task_capacity)
        self._checkpoint_revision = 0
        self._checkpoint_fault = False
        self._snapshot_status = "absent"
        self._snapshot_quarantined = False
        self.token = self._load_or_create_token()
        self.human_review_token = self._review_token()
        self.agent = None                 # legacy AgentWorker，attach_agent 挂上
        self.trio_worker = None           # OpenCode protocol worker
        self.trio_mode = False             # OpenCode 三 agent 工作协议；测试可显式注入
        self._t = 0
        self._unit_id = 0
        self._scene = ""
        self._scene_t = -1
        self._unit_busy = threading.Lock()
        self._unit_stop = threading.Event()
        self._unit_wake = threading.Event()
        self._unit_thread: threading.Thread | None = None
        self._retrievals: dict[int, Retrieval] = {}
        self._next_retrieval = 0
        self._last_turn: dict | None = None   # 上一轮 {user, retrieval_id}
        self._budgets: dict[str, dict] = {}   # signal_id → 预算/因果上界
        self.miss_counts: dict[str, int] = {}
        self.n_candgen_fail = 0
        self.n_missed = 0
        self.n_proposals = 0
        self.n_rejected = 0
        self.n_ungrounded = 0
        try:
            revision, checkpoint = self.tasks.checkpoint()
        except Exception as exc:
            self.tasks.close()
            self.log.close()
            raise RuntimeError("durable checkpoint 无法读取；请恢复配套备份") from exc
        if checkpoint is not None:
            try:
                self._load(checkpoint)
                self._checkpoint_revision = revision
                self._snapshot_status = "loaded"
            except Exception as exc:
                self.tasks.close()
                self.log.close()
                raise RuntimeError("durable checkpoint 损坏；拒绝用旧 state.pkl 空启动，请恢复配套备份") from exc
        elif self.state_path and self.state_path.exists():
            try:
                self._load()
                self._snapshot_status = "loaded"
            except Exception as exc:  # noqa: BLE001
                # 损坏/恶意 state 不能让 sidecar 启动即死（桥会整体瘫痪）：
                # 隔离坏文件后空启动，损失状态好过丢记忆服务。
                # 隔离标记在本进程内保持，随后的 save 不能把它洗成干净加载。
                self._snapshot_quarantined = True
                self._snapshot_status = "quarantined"
                corrupt = self.state_path.with_suffix(".corrupt")
                try:
                    os.replace(self.state_path, corrupt)
                except OSError:
                    pass
                print(f"[memory-sidecar] state.pkl 损坏已隔离为 "
                      f"{corrupt.name}（{exc}）——空启动",
                      file=sys.stderr, flush=True)
        elif self._corrupt_file_exists():
            # 上次隔离后没有留下可加载快照。重启不能把丢失显示成合法空目录。
            self._snapshot_quarantined = True
            self._snapshot_status = "quarantined"
        # L0 每轮提交，快照只在 save/退出时更新：正常旧快照、缺快照或坏
        # 快照都可能落后于日志。快照提供下界，绝不能让已提交证据复用 id/t。
        next_id, next_t = self.log.next_position()
        self._unit_id = max(self._unit_id, next_id)
        self._t = max(self._t, next_t)
        self.engine._next_id = max(self.engine._next_id, self.tasks.memory_next_id())
        self.engine.signals.on_emit = self._journal_signal

    def _review_token(self) -> str:
        """Separate capability: ordinary plugin and agent bearer cannot approve conflicts."""
        if not self.state_path:
            return secrets.token_hex(24)
        p = self.state_path.parent / ".human-review-token"
        if not p.exists():
            p.write_text(secrets.token_hex(24), encoding="utf-8")
            os.chmod(p, 0o600)
        token = p.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError("human-review-token is empty")
        return token

    def human_reviews(self) -> list[dict]:
        # The reviewer must see both sides and their provenance before choosing.
        with self._lock:
            reviews = self.tasks.pending_reviews()
            for review in reviews:
                old = self.engine.mems.get(review["target_id"])
                review["existing"] = ({"text": old.text, "source_unit_ids": sorted(old.src),
                                       "pool": old.pool.value} if old else None)
            return reviews

    def decide_human_review(self, review_id: int, decision: str, capability: str) -> dict:
        """An explicitly authenticated human decision, effect and receipt in one DB commit."""
        if not secrets.compare_digest(capability, self.human_review_token):
            raise PermissionError("human review capability required")
        if decision not in ("accept_new", "keep_old"):
            raise ValueError("decision must be accept_new or keep_old")
        with self._lock, self._rollback_effect():
            with self.tasks.transaction() as conn:
                row = conn.execute("SELECT * FROM human_reviews WHERE id=?", (review_id,)).fetchone()
                if row is None:
                    raise ValueError("review not found")
                if row["status"] != "pending":
                    if row["decision"] != decision:
                        raise ValueError("conflicting review decision")
                    return {"review_id": review_id, "decision": decision, "replayed": True}
                old = self.engine.mems.get(row["target_id"])
                if old is None or old.superseded_by is not None:
                    raise ValueError("review target changed; submit a fresh review")
                ids = []
                if decision == "accept_new":
                    ev, _ = self._validate_proposal(json.loads(row["candidate"]), None)
                    ev.origin = "user_confirmed"
                    ids = self.engine.propose([ev], self._t)
                    if not ids:
                        raise ValueError("accepted candidate did not create a distinct version")
                    self.engine.add_tension(ids[-1], old.id, self._t)
                    self.engine.submit_verdicts([(ids[-1], old.id, "update")], self._t)
                if decision == "accept_new":
                    # Other proposals against this now-retired version must be
                    # reconsidered against the new version, never left actionable.
                    conn.execute("UPDATE human_reviews SET status='stale' WHERE target_id=? "
                                 "AND id<>? AND status='pending'", (old.id, review_id))
                remaining = conn.execute("SELECT COUNT(*) FROM human_reviews WHERE target_id=? "
                    "AND id<>? AND status='pending'", (old.id, review_id)).fetchone()[0]
                old.pending_review = bool(remaining)
                conn.execute("UPDATE human_reviews SET status='done',decision=? WHERE id=?",
                             (decision, review_id))
                revision = self.tasks._write_checkpoint(conn, self._dump_state(), self._checkpoint_revision)
            self._checkpoint_revision = revision
            return {"review_id": review_id, "decision": decision, "new_ids": ids}

    def _corrupt_file_exists(self) -> bool:
        return bool(self.state_path and self.state_path.with_suffix(".corrupt").exists())

    def health_view(self) -> dict:
        """进程在不在，和数据有没有干净恢复，是两件事。

        `ok` 只表示没有 checkpoint fault，插件据此复用进程。
        `validation` 固定为 unverified：本进程不能自称远程或 L3 已验证。
        """
        with self._lock:
            if self._snapshot_quarantined:
                snapshot = "quarantined"
            else:
                snapshot = self._snapshot_status
            return {"ok": not self._checkpoint_fault,
                    "checkpoint_fault": self._checkpoint_fault,
                    "snapshot": snapshot,
                    "corrupt_file": self._corrupt_file_exists(),
                    "units_pending": self.log.work_stats()["pending"],
                    "validation": "unverified",
                    "t": self._t,
                    "mems": self.engine.pool_sizes(),
                    "tensions": len(self.engine.tensions),
                    "signals": sum(self.tasks.queued_counts().values()) + len(self.engine.signals),
                    "log_units": self.log.count(),
                    "agent": bool(self.agent or self.trio_worker)}

    def _ensure_healthy(self):
        if self._checkpoint_fault:
            raise CheckpointConflict("checkpoint 状态不确定或已被其他实例推进；请重启服务")

    def _check_checkpoint_error(self, revision):
        try:
            self._checkpoint_fault = self.tasks.checkpoint()[0] != revision
        except Exception:
            self._checkpoint_fault = True

    def _journal_signal(self, kind, payload, t, key, merge):
        if kind in ("recall_miss", "extract_due"):
            self._ensure_healthy()
            return self.tasks.enqueue(kind, payload, t, key=key, merge=merge,
                                      memory_next_id=self.engine._next_id)
        return None

    def _signal_payload(self, kind, payload):
        """仅存稳定 id/JSON；绝不把 Retrieval/Memory 实例放进任务表。"""
        if kind == "conflict_pending":
            # SQLite JSON 会把 tuple 变成 list；在 merge 前规整，避免跨轮去重失效。
            return [list(pair) for pair in payload]
        if kind != "feedback_pending":
            return payload
        ret = payload["retrieval"]
        rid = next((i for i, v in self._retrievals.items() if v is ret), None)
        if rid is None:
            raise ValueError("feedback retrieval 不在服务注册表")
        texts = getattr(ret, "presented_texts", ())  # 旧快照的 Retrieval 无此字段
        if len(texts) != len(ret.selected):
            texts = tuple(m.text for m in ret.selected)
        return {"retrieval_id": rid, "selected": [m.id for m in ret.selected],
                "texts": list(texts),
                "question": payload["question"], "answer": payload["answer"]}

    def _commit_sidecar_effect(self, mutate, *, capture=None):
        """sidecar 检索/反馈的记忆变更、语义信号及 checkpoint 同事务。

        capture 给出时，request-id 回执与效果同一事务。已有回执不执行 mutate，
        返回值带 replayed，调用方不得再跑模型。
        """
        with self._rollback_effect():
            old_registry = dict(self._retrievals)
            old_next = self._next_retrieval
            old_rets = [(ret, dict(ret.__dict__)) for ret in old_registry.values()]
            try:
                def run(conn):
                    q = self.engine.signals
                    old_emit = q.on_emit

                    def collect(kind, payload, t, key, merge):
                        if kind in SEMANTIC_KINDS | WORKFLOW_KINDS or kind in ("recall_miss", "extract_due"):
                            return self.tasks._enqueue(
                                conn, kind, self._signal_payload(kind, payload), t,
                                key=key, merge=merge,
                                memory_next_id=self.engine._next_id)
                        return old_emit(kind, payload, t, key, merge)

                    q.on_emit = collect
                    try:
                        return mutate()
                    finally:
                        q.on_emit = old_emit

                if capture is None:
                    result, revision = self.tasks.apply_effect(
                        run, self._dump_state, self._checkpoint_revision)
                    replayed = False
                else:
                    result, revision, replayed = self.tasks.apply_captured_effect(
                        run, self._dump_state, self._checkpoint_revision, capture)
                self._checkpoint_revision = revision
                if replayed and isinstance(result, dict):
                    result = dict(result, replayed=True, accepted=True)
                return result
            except BaseException:
                self._retrievals = old_registry
                self._next_retrieval = old_next
                for ret, fields in old_rets:
                    ret.__dict__.clear()
                    ret.__dict__.update(fields)
                raise

    @contextmanager
    def _rollback_effect(self):
        """任务操作与单元效果共用的内存回滚；原 Memory/队列对象身份不变。"""
        self._ensure_healthy()
        eng = self.engine
        fields = ("mems", "tensions", "_next_id", "_consolidation_pending",
                  "_consolidation_deferred", "_shadow_pending") + _COUNTERS
        original_mems = dict(eng.mems)
        backup = copy.deepcopy({k: getattr(eng, k) for k in fields})
        counters = {k: getattr(self, k) for k in _SERVICE_COUNTERS}
        service = (self._t, self._unit_id, self._scene, self._scene_t,
                   self._last_turn, dict(self.miss_counts))
        q = eng.signals
        queued = (type(q._items)(q._items), dict(q._by_key), q._next_id,
                  q.n_emitted, q.n_dropped,
                  [(sig, sig.payload, sig.t) for sig in q._items])
        revision = self._checkpoint_revision
        try:
            yield
        except BaseException:
            for mid, original in original_mems.items():
                original.__dict__.clear()
                original.__dict__.update(backup["mems"][mid].__dict__)
            backup["mems"] = original_mems
            for k, v in backup.items():
                setattr(eng, k, v)
            for k, v in counters.items():
                setattr(self, k, v)
            self._t, self._unit_id, self._scene, self._scene_t, self._last_turn, self.miss_counts = service
            q._items, q._by_key, q._next_id, q.n_emitted, q.n_dropped, old = queued
            for sig, payload, t in old:
                sig.payload, sig.t = payload, t
            # 若提交成功但确认丢失，绝不能用回滚后的内存覆盖 DB checkpoint。
            self._check_checkpoint_error(revision)
            raise

    def _task_once(self, ctx, request, mutate):
        """调用方持服务锁；操作、checkpoint、回执同事务。"""
        with self._rollback_effect():
            out, next_revision, replayed = self.tasks.apply_operation(
                ctx.task_id, ctx.lease_token, request, mutate,
                self._dump_state, self._checkpoint_revision)
            self._checkpoint_revision = next_revision
            return dict(out, replayed=replayed)

    def _durable_propose(self, proposals, ctx):
        accepted, ids, rejected, replayed, applied = 0, [], [], 0, 0
        plain = replace(ctx, task_id=None, lease_token=None)
        for i, proposal in enumerate(proposals):
            # 用实际 ingest 字段规整签名，消除 HTTP 与最终 JSON 的默认值差异。
            # supersedes 的因果检查留在 receipt 查询之后：成功更新后的旧链可能
            # 已指向本任务刚创建的新条目，不能把合法重放误判成未来访问。
            try:
                ev, sup = self._validate_proposal(proposal, ctx.before)
                canonical = {"text": ev.text, "src": list(ev.src), "salience": ev.salience,
                             "entity_key": ev.entity, "supersedes": sorted(set(sup))}
            except (ProposalRejected, AttributeError):
                canonical = proposal
            out = self._task_once(ctx, {"action": "propose", "proposal": canonical},
                                  lambda: self.propose([proposal], _context=plain))
            accepted += out["accepted"]
            ids.extend(out["new_ids"])
            replayed += int(out["replayed"])
            applied += out["accepted"] if not out["replayed"] else 0
            rejected.extend(dict(r, index=i) for r in out["rejected"])
        return {"accepted": accepted, "new_ids": ids, "merged": accepted - len(ids),
                "rejected": rejected, "replayed": replayed, "applied": applied, "origin": ctx.origin,
                "pool": self.engine.pool_sizes(), "t": self._t}

    # 供 AgentWorker 使用的最小接口
    @property
    def lock(self):
        return self._lock

    def current(self) -> tuple[int, str]:
        return self._t, self._scene

    def attach_agent(self, agent) -> None:
        self.agent = agent

    def _kick(self) -> None:
        if self.agent is not None:
            self.agent.notify()

    def _load_or_create_token(self) -> str:
        """HTTP 鉴权令牌：持久化在 state_dir/.memory-token（插件侧同路径
        读取），无 state_dir 时临时生成。防浏览器 CSRF 写与端口占位复用。"""
        p = (self.state_path.parent / ".memory-token"
             if self.state_path else None)
        if p and p.exists():
            tok = p.read_text(encoding="utf-8").strip()
            if tok:
                return tok
            # 空/全空白 token 文件 = 坏状态：当作不存在，重写一个
        tok = secrets.token_hex(16)
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(tok, encoding="utf-8")
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        return tok

    # ================================================== 主回路
    def observe(self, user_text: str, assistant_text: str,
                request_id: str | None = None) -> dict:
        request_id = _validate_request_id(request_id)
        fingerprint = _capture_fingerprint(
            {"user_text": user_text, "assistant_text": assistant_text})
        with self._lock:
            self._ensure_healthy()
            prev = self._last_turn
            context = {}
            if triggers.is_dissatisfaction(user_text) and prev:
                ret = self._retrievals.get(prev.get("retrieval_id", -1))
                context = {"previous_user": prev["user"],
                           "retrieved": [{"id": m.id, "t": m.birth, "text": m.text}
                                         for m in (ret.selected if ret else [])]}
            scene = self._scene
            idx = self.log.append_unit(
                self._t, min_unit_id=self._unit_id, user_text=user_text,
                assistant_text=assistant_text, scene=scene, work_context=context,
                capture_id=request_id, capture_fingerprint=fingerprint)
            uid, t = idx["unit_id"], idx["t"]
            replayed = bool(idx.get("replayed"))
            # 重放不得推进时钟或覆盖更新一轮的 last_turn。
            if not replayed:
                self._unit_id, self._t = uid + 1, t
                self._last_turn = {"user": user_text, "retrieval_id": None}
        # 新单元已与 L0 待办同事务接受；即使其他处理器忙，也不会消失。
        self._unit_wake.set()
        try:
            completed = self.process_pending_units()
        except (TaskQueueFull, CheckpointConflict) as exc:
            # L0 已提交。保留原异常类型，让直接调用方的既有 except 仍能匹配，
            # HTTP 层据此附上 accepted/unit_id，避免客户端换成新请求再投一条。
            exc.accepted = True
            exc.unit_id = uid
            exc.request_id = request_id
            raise
        if uid in completed:
            body = completed[uid]
        elif (receipt := self.tasks.unit_receipt(uid)) is not None:
            body = receipt
        else:
            with self._lock:
                body = {"unit_id": uid, "pending": True, "candidates": 0,
                        "scene": scene, "reasons": [],
                        "pool": self.engine.pool_sizes(), "t": self._t, "worker": {}}
        return _annotate_observe(body, uid, replayed=replayed, request_id=request_id)

    def process_pending_units(self, limit: int = 8) -> dict[int, dict]:
        """按原 L0 顺序处理；同服务仅一个处理器。不得越过退避中的旧单元。"""
        if not self._unit_busy.acquire(blocking=False):
            return {}
        completed = {}
        try:
            with self._lock:
                self._ensure_healthy()
            for uid in self.log.pending_units(limit):
                work = self.log.work(uid)
                if work["next_run_at"] > time.time() and self.tasks.unit_receipt(uid) is None:
                    break
                try:
                    completed[uid] = self._process_unit(uid, work)
                except Exception as exc:
                    self.log.fail_work(uid, exc)
                    raise
        finally:
            self._unit_busy.release()
        return completed

    def _process_unit(self, uid: int, work: dict) -> dict:
        ctx = self.log.unit_context(uid)
        unit = ctx["unit"]
        t = unit["t"]
        if work["result"] is None and self.tasks.unit_receipt(uid) is None:
            reasons = triggers.scan_unit(unit["user_text"], unit["assistant_text"],
                                         ctx["new_entities"])
            u = InteractionUnit(uid, t, t, unit["user_text"], unit["assistant_text"],
                                unit["assistant_turns"])
            window = InteractionWindow(uid, uid, uid, t, t, (u,))
            try:
                if self.trio_mode:
                    cands, scene, failure = [], unit["scene"], ""
                else:
                    gen = self.generator.generate(window, unit["scene"])
                    cands, scene, failure = [asdict(c) for c in gen.candidates], gen.scene_name, ""
            except Exception as exc:  # noqa: BLE001  可恢复补抽，而非伪装合法空候选
                cands, scene = [], ""
                failure = f"{type(exc).__name__}: {exc}"[:500]
                reasons = list(dict.fromkeys([*reasons, "candgen_failed"]))
                print(f"[memory-sidecar] candgen 失败（unit {uid}，已留 L0，交调查员补抽）: "
                      f"{failure}", file=sys.stderr, flush=True)
            self.log.save_work_result(uid, encode({"candidates": cands, "scene": scene,
                                                   "reasons": reasons, "failure": failure}))
            work = self.log.work(uid)
        result = json.loads(work["result"]) if work["result"] is not None else None
        handoffs = []
        with self._lock:
            self._ensure_healthy()
            with self._rollback_effect():
                old_emit = self.engine.signals.on_emit

                def collect(kind, payload, at, key, merge):
                    if kind in SEMANTIC_KINDS | WORKFLOW_KINDS or kind in ("recall_miss", "extract_due"):
                        handoffs.append((kind, self._signal_payload(kind, payload), at, key, merge))
                        return -1  # 同任务库事务交接，不进易失队列
                    return old_emit(kind, payload, at, key, merge)

                def mutate():
                    self._unit_id = max(self._unit_id, uid + 1)
                    self._t = max(self._t, t)
                    # 每个单元只在一次 checkpoint 中落地；不让旧单元覆盖较新场景。
                    scene = (result["scene"] or self._scene) if result else self._scene
                    if t >= self._scene_t:
                        self._scene, self._scene_t = scene, t
                    previous = work["context"].get("previous_user") or ctx["previous_user"]
                    if not self.trio_mode and triggers.is_correction(unit["user_text"]) and previous:
                        self.engine.report_miss(
                            previous, t, hint=unit["user_text"][:300], source="correction",
                            retrieved=work["context"].get("retrieved", []),
                            entities=tuple(e for e, _ in entities_in(previous)))
                        self.n_missed += 1
                    reasons = result["reasons"] if result else []
                    if self.trio_mode:
                        self.engine.signals.emit("hauler_due", {"unit_id": uid}, t,
                                                 key=f"hauler:{uid}")
                        if triggers.is_dissatisfaction(unit["user_text"]):
                            self.engine.signals.emit("reviewer_due", {"unit_id": uid}, t,
                                                     key=f"reviewer:{uid}")
                    elif reasons:
                        self.engine.report_unit(uid, t, scene=self._scene,
                                                reasons=tuple(reasons),
                                                entities=tuple(ctx["entities"][:12]))
                    blob = f"{unit['user_text']}\n{unit['assistant_text']}"
                    grounded = []
                    for cand in (result["candidates"] if result else []):
                        if _content_grounded(cand.get("text", ""), blob):
                            grounded.append(cand)
                        else:
                            self.n_ungrounded += 1
                    evs = [Event(self.semantics.fingerprint(normalize(c["text"])),
                                 normalize(c["text"]), c["text"], (uid,),
                                 salience=c["salience"], scene=self._scene)
                           for c in grounded]
                    if evs:
                        self.engine.observe(evs, t)
                    self.engine.step(t)
                    self._t = max(self._t, t + 1)
                    if result and result["failure"]:
                        self.n_candgen_fail += 1
                    return {"unit_id": uid, "candidates": len(evs),
                            "scene": self._scene, "reasons": list(reasons),
                            "pool": self.engine.pool_sizes(), "t": self._t,
                            "next_memory_id": self.engine._next_id}

                self.engine.signals.on_emit = collect
                try:
                    response, revision, replayed = self.tasks.apply_unit(
                        uid, mutate, self._dump_state, handoffs, self._checkpoint_revision)
                    self._checkpoint_revision = revision
                finally:
                    self.engine.signals.on_emit = old_emit
        # 回执先于跨库确认；确认失败则仍是 pending，重试只读回执。
        self.log.finish_work(uid)
        if replayed:
            return {k: v for k, v in response.items() if k != "next_memory_id"} | {"worker": {}}
        wstats = self.process_semantic_tasks()
        self._kick()
        return {k: v for k, v in response.items() if k != "next_memory_id"} | {"worker": wstats}

    # ================================================== 持久语义任务
    def _semantic_model(self, row):
        """只读取判定输入；调用外部语义模型时不持服务锁。"""
        kind, payload = row["kind"], row["payload"]
        with self._lock:
            self._ensure_healthy()
            if kind == "conflict_pending":
                jobs = []
                for left, right in payload:
                    a, b = self.engine.mems.get(left), self.engine.mems.get(right)
                    if a is not None and b is not None:
                        a, b = maintenance.follow_chain(self.engine, a), maintenance.follow_chain(self.engine, b)
                    args = ((a.belief_id, a.value, b.belief_id, b.value)
                            if a is not None and b is not None and a.id != b.id else None)
                    tension = self.engine.tensions.get(tuple(sorted((left, right))))
                    stamp = [tension.last_seen, tension.observations] if tension else None
                    jobs.append((left, right, args, stamp))
            elif kind == "feedback_pending":
                texts = payload.get("texts")
                selected = payload.get("selected")
                if (not isinstance(texts, list) or not isinstance(selected, list)
                        or len(texts) != len(selected)):
                    raise ValueError("反馈文本快照与入选记忆不匹配")
            elif kind == "maintenance_due":
                sources = [[i, m.last_seen, m.pool.value, m.superseded_by, m.aggregated_into]
                           for i in payload["ids"] if (m := self.engine.mems.get(i)) is not None]
                mems = sorted((copy.deepcopy(m) for i in payload["ids"]
                               if (m := self.engine.mems.get(i)) is not None
                               and is_visible(m) and not m.pending_review and m.kind == "fact"),
                              key=lambda m: (m.birth, m.id))
        if kind == "conflict_pending":
            return {"verdicts": [[a, b, self.semantics.judge(*args) if args else "pending", stamp]
                                 for a, b, args, stamp in jobs]}
        if kind == "feedback_pending":
            fn = self.semantics.relevant_set if isinstance(self.semantics, FeedbackSemantics) else None
            used = fn(texts, payload["question"], payload["answer"]) if fn else [True] * len(texts)
            failed = used is None or len(used) != len(texts)
            if failed:
                used = [True] * len(texts)
            return {"used": [bool(u) for u in used], "recog_fail": failed}
        if kind == "maintenance_due":
            if (not isinstance(self.semantics, ConsolidationSemantics)
                    or len(mems) < self.cfg.consolidation_min_items):
                return {"event": None, "sources": sources}
            event = self.semantics.consolidate(mems, row["t"])
            return {"event": asdict(event) if event is not None else None, "sources": sources}
        raise ValueError(f"未知语义任务 {kind}")

    def _apply_semantic(self, row):
        with self._lock, self._rollback_effect():
            old_ret = None
            if row["kind"] == "feedback_pending":
                old_ret = self._retrievals.get(row["payload"]["retrieval_id"])
                ret_fields = dict(old_ret.__dict__) if old_ret is not None else None
            try:
                def mutate(conn, result):
                    q = self.engine.signals
                    old_emit = q.on_emit

                    def collect(kind, payload, t, key, merge):
                        if kind in SEMANTIC_KINDS | WORKFLOW_KINDS or kind in ("recall_miss", "extract_due"):
                            return self.tasks._enqueue(
                                conn, kind, self._signal_payload(kind, payload), t,
                                key=key, merge=merge, memory_next_id=self.engine._next_id)
                        return old_emit(kind, payload, t, key, merge)

                    q.on_emit = collect
                    try:
                        kind, payload, t = row["kind"], row["payload"], row["t"]
                        if kind == "conflict_pending":
                            current, stale = [], []
                            for left, right, verdict, stamp in result["verdicts"]:
                                tension = self.engine.tensions.get(tuple(sorted((left, right))))
                                if tension is None:
                                    continue
                                if stamp != [tension.last_seen, tension.observations]:
                                    stale.append([left, right])
                                else:
                                    current.append((left, right, verdict))
                            if stale:
                                self.engine.signals.emit("conflict_pending", stale, t,
                                                         key="conflict",
                                                         merge=lambda old, new: old + [p for p in new if p not in old])
                            return {"resolved": self.engine.submit_verdicts(current, t)}
                        if kind == "feedback_pending":
                            used = result["used"]
                            selected = payload["selected"]
                            if len(used) != len(selected):
                                raise ValueError("feedback 结果长度不符")
                            ret = self._retrievals.get(payload["retrieval_id"])
                            shown = [m.id for m in ret.selected] if ret is not None else None
                            if ret is not None and shown == selected:
                                if ret.credited:
                                    return {"credited": 0}
                                n = self.engine.submit_relevance(ret, used, t)
                                if (n == 0 and ret.selected and self.cfg.miss_on_recognizer_none):
                                    question = payload["question"]
                                    self.engine.report_miss(
                                        question, t, source="recognizer_none", retrieval=ret,
                                        entities=tuple(e for e, _ in entities_in(question)))
                                    self.n_missed += 1
                                return {"credited": n, "recog_fail": bool(result["recog_fail"])}
                            # 注册表已退役或不再是当时展示的那一组。载荷 id 才是依据。
                            n = self.engine.credit_shown(selected, used, t)
                            if ret is not None:
                                ret.credited = True
                                ret.n_useful = n
                            return {"credited": n, "recog_fail": bool(result["recog_fail"]),
                                    "retired_source": True}
                        if result["event"] is None:
                            return {"reflected": 0}
                        sources = [[i, m.last_seen, m.pool.value, m.superseded_by, m.aggregated_into]
                                   for i in payload["ids"] if (m := self.engine.mems.get(i)) is not None]
                        if sources != result["sources"] or len(sources) != len(payload["ids"]):
                            eligible = [i for i in payload["ids"] if (m := self.engine.mems.get(i))
                                        and is_visible(m) and not m.pending_review and m.kind == "fact"]
                            if len(eligible) >= self.cfg.consolidation_min_items:
                                self.engine.signals.emit("maintenance_due",
                                                         {"scene": payload["scene"], "ids": eligible}, t,
                                                         key=f"maint:{payload['scene']}",
                                                         merge=lambda old, new: new)
                            return {"reflected": 0}
                        self.engine.add_reflection(Event(**result["event"]), payload["ids"], t)
                        return {"reflected": 1}
                    finally:
                        q.on_emit = old_emit

                out, revision = self.tasks.complete_semantic(
                    row["id"], row["token"], mutate,
                    self._dump_state, self._checkpoint_revision)
                self._checkpoint_revision = revision
                self._kick()
                return out
            except BaseException:
                if old_ret is not None:
                    old_ret.__dict__.clear()
                    old_ret.__dict__.update(ret_fields)
                raise

    def process_semantic_tasks(self, limit: int = 8) -> dict:
        """先持久化模型结果，再事务性应用；队列失败可见且独立于调查员。"""
        stats = {"judged": 0, "resolved": 0, "credited": 0,
                 "reflected": 0, "thin": 0, "recog_fail": 0, "errors": 0}
        if not self._semantic_busy.acquire(blocking=False):
            return stats
        try:
            with self._lock:
                stats["thin"] = len(self.engine.signals.take(("thin_recall",)))
            self.tasks.recover_semantic_expired()
            for item in self.tasks.list_tasks(states=("pending", "ready"), kinds=SEMANTIC_KINDS)[:limit]:
                row = None
                try:
                    with self._lock:
                        self._ensure_healthy()
                        row = self.tasks.claim_semantic(item["id"], item["version"])
                    if row is None:
                        continue
                    if row["state"] == "running":
                        result = self._semantic_model(row)
                        if row["kind"] == "conflict_pending":
                            stats["judged"] += len(result["verdicts"])
                        self.tasks.store_semantic_result(row["id"], row["token"], result)
                        with self._lock:
                            self._ensure_healthy()
                            row = self.tasks.claim_semantic(row["id"], row["version"])
                        if row is None:
                            continue
                    out = self._apply_semantic(row)
                    for key in ("resolved", "credited", "reflected", "recog_fail"):
                        stats[key] += out.get(key, 0)
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    if row is not None:
                        try:
                            self.tasks.retry_semantic(row["id"], row["token"], exc)
                        except TaskLeaseLost:
                            pass  # 产物已落库或其他领取者获权，不覆盖它
                    print(f"[memory-sidecar] 语义任务 {item['id']} 待重试: "
                          f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                    if self._checkpoint_fault:
                        break
            return stats
        finally:
            self._semantic_busy.release()

    def start_unit_recovery(self) -> None:
        if self._unit_thread is not None and self._unit_thread.is_alive():
            return
        self._unit_stop.clear()

        def loop():
            while not self._unit_stop.is_set():
                for process in (self.process_pending_units, self.process_semantic_tasks):
                    if self._checkpoint_fault:
                        break  # 只可重启加载权威 checkpoint
                    try:
                        process()
                    except Exception as exc:  # noqa: BLE001  持久待办下一轮重试
                        print(f"[memory-sidecar] 恢复失败: {type(exc).__name__}: {exc}",
                              file=sys.stderr, flush=True)
                if self._checkpoint_fault:
                    break
                self._unit_wake.wait(2)
                self._unit_wake.clear()

        self._unit_thread = threading.Thread(target=loop, name="memory-unit", daemon=True)
        self._unit_thread.start()

    def stop_unit_recovery(self, timeout: float = 5.0) -> None:
        self._unit_stop.set()
        self._unit_wake.set()
        if self._unit_thread is not None:
            self._unit_thread.join(timeout)

    def _context_lines(self, ret: Retrieval) -> list[tuple[str, object]]:
        prov_ids = {m.id for m in ret.provisional}
        lines = []
        for m in ret.selected:
            lines.append((
                f"- {'[未确认] ' if m.id in prov_ids else ''}"
                f"{'[待人审冲突，不可断言为当前事实] ' if m.pending_review else ''}"
                f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
                f"[t={m.birth}] {_safe_mem_text(m.text)}", m))
        for m, rival in ret.contested:
            lines.append((f"- ⚠️未决冲突：[t={rival.birth}] "
                          f"{_safe_mem_text(rival.text)}"
                          f"（与 t={m.birth} 条目冲突）", None))
        return lines

    def _causal_memory_ids(self, before: int | None) -> set[int]:
        """保守的当前版本过滤，不冒充历史版本重建；调用方持 service lock。
        birth 不够：旧记忆也可能在未来被确认/合并，或携带未来来源。
        """
        if before is None:
            return set(self.engine.mems)
        candidates = [m for m in self.engine.mems.values()
                      if m.birth < before and m.last_seen < before]
        src = {uid for m in candidates for uid in m.src}
        known = set(self.log.exists(src, before=before)) if src else set()
        eligible = {m.id for m in candidates if set(m.src) <= known}
        # submit_verdicts 会沿替代/聚合链找当前代表，不能借旧 id 写到未来。
        while True:
            blocked = {mid for mid in eligible
                       if any(ref is not None and ref not in eligible
                              for ref in (self.engine.mems[mid].superseded_by,
                                          self.engine.mems[mid].aggregated_into))}
            if not blocked:
                return eligible
            eligible -= blocked

    def _causal_tensions(self, ids: set[int], before: int | None) -> dict:
        return {pair: tension for pair, tension in self.engine.tensions.items()
                if all(mid in ids for mid in pair)
                and (before is None or tension.last_seen < before)}

    def recall(self, q: str, k: int | None = None, *,
               signal_id: str | None = None, budget_tokens: int | None = None,
               passive: bool = False) -> dict:
        if budget_tokens is not None and (type(budget_tokens) is not int or budget_tokens < 0):
            raise ValueError("budget_tokens must be a non-negative int")
        if not isinstance(passive, bool):
            raise ValueError("passive must be bool")
        ctx, _, _ = self._admit(signal_id)
        if signal_id is None and not passive:
            return self._recall_main(q, k, budget_tokens)
        qv = self.emb.embed([q])[0]  # 未准入的请求不会触发 embedding
        with self._lock:
            self._ensure_healthy()
            ids = self._causal_memory_ids(ctx.before)
            cfg = copy.copy(self.cfg)
            if k is not None:
                cfg.k = k
            cfg.defer_credit, cfg.shadow_credit = True, False
            view = MemoryEngine(cfg, self.emb, self.semantics)
            view.mems = copy.deepcopy({i: self.engine.mems[i] for i in ids})
            view.tensions = copy.deepcopy(self._causal_tensions(ids, ctx.before))
            # 沿用原排序/压制算法，但在筛选后的副本中运行；不改原记忆、
            # 不复活/记信用、不发主引擎信号，也不登记可被 feedback 的 rid。
            ret = view.retrieve(qv, Query(-1, q), self._t if ctx.before is None else min(self._t, ctx.before - 1))
            return self._recall_result(ret, None, budget_tokens)

    def _recall_main(self, q: str, k: int | None = None,
                     budget_tokens: int | None = None) -> dict:
        qv = self.emb.embed([q])[0]
        with self._lock:
            self._ensure_healthy()
            def mutate():
                if k is not None:
                    old_k, self.cfg.k = self.cfg.k, k
                    try:
                        ret = self.engine.retrieve(qv, Query(-1, q), self._t)
                    finally:
                        self.cfg.k = old_k
                else:
                    ret = self.engine.retrieve(qv, Query(-1, q), self._t)
                rid = self._next_retrieval
                self._next_retrieval += 1
                self._retrievals[rid] = ret
                while len(self._retrievals) > _RETRIEVAL_KEEP:
                    # 已持久接受的反馈不能因为后续检索挤出引用对象。
                    evictable = [i for i, r in self._retrievals.items()
                                 if not r.feedback_sent or r.credited]
                    if not evictable:
                        break
                    self._retrievals.pop(min(evictable))
                # /search 发生在回答前；/feedback 再关联上一轮。
                return self._recall_result(ret, rid, budget_tokens)

            out = self._commit_sidecar_effect(mutate)
            self._unit_wake.set()
            return out

    def _recall_result(self, ret: Retrieval, rid: int | None,
                       budget_tokens: int | None = None) -> dict:
        lines, kept, used = [], [], 0
        for line, memory in self._context_lines(ret):
            cost = approx_tokens(line) + (1 if lines else 0)
            if budget_tokens is not None and used + cost > budget_tokens:
                break
            lines.append(line)
            used += cost
            if memory is not None:
                kept.append(memory)
        # 延迟反馈只给实际送入上下文的记忆记账。
        ret.selected = kept
        ret.presented_texts = tuple(m.text for m in kept)
        return {"retrieval_id": rid, "context": "\n".join(lines),
                "n": len(kept), "tokens": used,
                "selected": [{"id": m.id, "text": m.text,
                              "birth": m.birth, "kind": m.kind,
                              "origin": m.origin, "src": sorted(m.src)}
                             for m in ret.selected]}

    def feedback(self, retrieval_id: int, question: str, answer: str,
                 request_id: str | None = None) -> dict:
        request_id = _validate_request_id(request_id)
        fingerprint = _capture_fingerprint({
            "retrieval_id": retrieval_id, "question": question, "answer": answer})
        with self._lock:
            self._ensure_healthy()
            ret = self._retrievals.get(retrieval_id)
            if request_id:
                old = self.tasks.read_capture(request_id)
                if old is not None:
                    if old["fingerprint"] != fingerprint:
                        raise CaptureConflict(f"request_id {request_id} 已绑定不同请求")
                    # 回执已存在就不再跑模型；检索对象后来被挤出也不影响这次回放。
                    return dict(old["response"], replayed=True, accepted=True,
                                request_id=request_id)
            if ret is None:
                return {"error": f"unknown retrieval_id {retrieval_id}"}
            if not ret.selected:
                response = {"n_useful": 0, "pending": False, "worker": {},
                            "accepted": True, "retrieval_id": retrieval_id}
                if request_id:
                    stored, replayed = self.tasks.remember_capture(
                        request_id, "feedback", fingerprint, response)
                    response = dict(stored, accepted=True, request_id=request_id)
                    if replayed:
                        response["replayed"] = True
                return response
            if ret.credited or ret.feedback_sent:
                # 同一次检索重复反馈（插件重试/多会话共用）：幂等拒绝，
                # 不让引擎的 RuntimeError 变成 500。accepted 表示效果已存在，
                # 不是邀请客户端换一个 request-id 再投。
                return {"error": f"retrieval_id {retrieval_id} already "
                                 f"credited", "n_useful": ret.n_useful,
                        "pending": ret.feedback_sent and not ret.credited,
                        "accepted": True}
            def mutate():
                self.engine.feedback(ret, question, answer, self._t)
                if self._last_turn is not None:
                    self._last_turn = {"user": question, "retrieval_id": retrieval_id}
                return {"n_useful": 0, "pending": True, "accepted": True,
                        "retrieval_id": retrieval_id,
                        **({"request_id": request_id} if request_id else {})}
            capture = ({"request_id": request_id, "kind": "feedback",
                        "fingerprint": fingerprint} if request_id else None)
            result = self._commit_sidecar_effect(mutate, capture=capture)
            if isinstance(result, dict) and result.get("replayed"):
                return result
            base = result if isinstance(result, dict) else {}
        self._unit_wake.set()
        try:
            wstats = self.process_semantic_tasks()  # 模型调用在服务锁外
        except Exception as exc:  # noqa: BLE001  效果已提交，不能把交付回执变成未接受
            wstats = {"error": f"{type(exc).__name__}: {exc}"}
        with self._lock:
            return {**base, "n_useful": ret.n_useful, "pending": not ret.credited,
                    "worker": wstats, "accepted": True,
                    **({"request_id": request_id} if request_id else {})}

    def report_miss(self, query: str, hint: str = "",
                    source: str = "agent_tool") -> dict:
        if source not in _MISS_SOURCES:
            source = "external"
        with self._lock:
            self._ensure_healthy()
            self.engine.report_miss(query, self._t, hint=hint[:300],
                                    source=source,
                                    entities=tuple(e for e, _ in entities_in(query)))
            self.n_missed += 1
            n = sum(self.tasks.queued_counts().values()) + len(self.engine.signals)
        self._kick()
        return {"queued": n, "t": self._t}

    def conflicts(self, *, signal_id: str | None = None) -> dict:
        with self._lock:
            ctx, _, _ = self._admit(signal_id)
            tensions = self.engine.tensions
            if signal_id is not None:
                tensions = self._causal_tensions(self._causal_memory_ids(ctx.before),
                                                 ctx.before)
            out = []
            for (left, right), tension in tensions.items():
                a, b = self.engine.mems.get(left), self.engine.mems.get(right)
                out.append({
                    "left": left, "right": right,
                    "left_text": a.text if a else None,
                    "right_text": b.text if b else None,
                    "first_seen": tension.first_seen,
                    "observations": tension.observations})
            return {"conflicts": out, "t": self._t}

    def resolve(self, left: int, right: int, verdict: str,
                entity_key: str = "", ensure_tension: bool = False, *,
                signal_id: str | None = None,
                _context: InvestigationContext | None = None,
                _checkpoint: bool = True) -> dict:
        """裁决回报。ensure_tension=True（调查员/主 agent 主动裁决两条此前
        没被判为张力的记忆）时先登记 tension 再消解；entity_key 回填到双方。"""
        if verdict not in _VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(_VERDICTS)}")
        with self._lock:
            ctx = _context if _context is not None else self._admit(signal_id)[0]
            if ctx.task_id is not None:
                request = {"action": "resolve", "pair": sorted((left, right)),
                           "verdict": verdict, "entity_key": entity_key[:120],
                           "ensure_tension": ensure_tension}
                return self._task_once(ctx, request, lambda: self.resolve(
                    left, right, verdict, entity_key, ensure_tension,
                    _context=replace(ctx, task_id=None, lease_token=None),
                    _checkpoint=False))
            if ctx.before is not None:
                eligible = self._causal_memory_ids(ctx.before)
                if left not in eligible or right not in eligible:
                    raise CausalViolation("unknown_or_future_memory")
            a, b = self.engine.mems.get(left), self.engine.mems.get(right)
            def mutate():
                if ensure_tension and a is not None and b is not None:
                    self.engine.add_tension(left, right, self._t)
                if entity_key:
                    for m in (a, b):
                        if m is not None and not m.entity:
                            m.entity = entity_key[:120]
                n = self.engine.submit_verdicts([(left, right, verdict)], self._t)
                return {"resolved": n, "t": self._t}
            # 任务回执事务已经包住这次调用；再开事务会嵌套 BEGIN。
            if _checkpoint:
                return self._commit_sidecar_effect(mutate)
            return mutate()

    # ================================================== 日志工具面
    def _admit(self, signal_id: str | None, before: int | None = None, *,
               window: bool = False, max_chars: int | None = None
               ) -> tuple[InvestigationContext, dict | None, int]:
        """同一临界区内校验存活、计调用、固定因果界，并预留回展额度。

        返回不可变上下文、该次预算对象和预留量。I/O 后只用这些对象，
        不再按 signal_id 二次查找，避免 close/reopen 丢失边界或串账。
        calls 统计尝试次数（含 429），window_used 只统计成功返回的原文字数。
        """
        if before is not None and (type(before) is not int or before < 0):
            raise ValueError("before must be a non-negative int")
        if max_chars is not None and (type(max_chars) is not int or max_chars <= 0):
            raise ValueError("max_chars must be a positive int")
        with self._lock:
            self._ensure_healthy()
            bud = None
            ctx = InvestigationContext(None, before)
            if signal_id is not None:
                bud = self._budgets.get(signal_id)
                if bud is None:
                    raise SignalClosed(f"signal {signal_id} 已关闭或不存在")
                bud["calls"] += 1
                if bud["calls"] > bud["tool_calls"]:
                    raise PermissionError(
                        f"该信号工具调用预算 {bud['tool_calls']} 已用尽，请立即汇总输出")
                base = bud["context"]
                if base.task_id is not None:
                    self.tasks.check_owned(base.task_id, base.lease_token)
                bound = base.before if before is None else min(before, base.before)
                ctx = replace(base, before=bound)
            cap = 0
            if window:
                remaining = (bud["window_chars"] - bud["window_used"]
                             - bud["window_reserved"] if bud is not None
                             else _MAIN_WINDOW_CAP)
                if remaining <= 0:
                    raise PermissionError("该信号回展预算已用尽（含在途预留）")
                cap = min(remaining, max_chars) if max_chars is not None else remaining
                if bud is not None:
                    bud["window_reserved"] += cap
            return ctx, bud, cap

    def log_search(self, query: str, *, before=None, scene=None, k=8,
                   signal_id: str | None = None) -> dict:
        ctx, _, _ = self._admit(signal_id, before)
        hits = self.log.search(query, before=ctx.before,
                               scene=scene or None, k=min(int(k), 20))
        return {"hits": hits, "n": len(hits)}

    def log_timeline(self, entity: str, *, before=None, limit=30,
                     signal_id: str | None = None) -> dict:
        ctx, _, _ = self._admit(signal_id, before)
        rows = self.log.timeline(entity, before=ctx.before,
                                 limit=min(int(limit), 100))
        return {"entity": entity, "timeline": rows, "n": len(rows)}

    def log_stats(self, group_by: str = "scene", *, before=None, limit=30,
                  signal_id: str | None = None) -> dict:
        ctx, _, _ = self._admit(signal_id, before)
        rows = self.log.stats(group_by, before=ctx.before, limit=min(int(limit), 200))
        return {"group_by": group_by, "rows": rows, "n": len(rows),
                "units_total": self.log.count(ctx.before)}

    def log_window(self, unit_ids, *, max_chars=None,
                   signal_id: str | None = None) -> dict:
        ctx, bud, cap = self._admit(signal_id, window=True, max_chars=max_chars)
        out = None
        try:
            out = self.log.window(unit_ids, max_chars=cap, before=ctx.before)
            return out
        finally:
            if bud is not None:
                with self._lock:
                    bud["window_reserved"] -= cap
                    # 失败退还整笔预留；成功只结算实际字数，未使用部分可继续使用。
                    if out is not None:
                        bud["window_used"] += out["chars"]
                        out["budget_left"] = (bud["window_chars"] - bud["window_used"]
                                              - bud["window_reserved"])

    def open_budget(self, signal_id: str, *, tool_calls: int,
                    window_chars: int, before: int,
                    origin: str | None = None, task_id: int | None = None,
                    lease_token: str | None = None) -> InvestigationContext:
        """打开一次调查并返回仅供进程内最终 JSON 使用的不可变上下文。
        HTTP 工具必须使用活跃 signal_id；不能提供此对象跳过计量。
        """
        if not isinstance(signal_id, str) or not signal_id.strip():
            raise ValueError("signal_id required")
        for name, value in (("tool_calls", tool_calls), ("window_chars", window_chars),
                            ("before", before)):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        ctx = InvestigationContext(signal_id, before,
                                   origin if origin in _ORIGINS else "agent", task_id, lease_token)
        with self._lock:
            if signal_id in self._budgets:
                raise ValueError(f"signal {signal_id} already open")
            self._budgets[signal_id] = {"tool_calls": tool_calls,
                                        "window_chars": window_chars,
                                        "calls": 0, "window_used": 0,
                                        "window_reserved": 0, "context": ctx,
                                        "opened": time.time()}
        return ctx

    def close_budget(self, signal_id: str) -> dict:
        with self._lock:
            bud = self._budgets.pop(signal_id, None)
            if bud is None:
                return {}
            return {"calls": bud["calls"], "window_used": bud["window_used"],
                    "window_reserved": bud["window_reserved"],
                    "elapsed_s": round(time.time() - bud["opened"], 1)}

    # ================================================== 操作面
    def _cited_text(self, unit_ids) -> str:
        parts = []
        for uid in unit_ids:
            row = self.log.get(uid)
            if row is None:
                continue
            parts.append(row["user_text"])
            parts.append(row["assistant_text"])
        return "\n".join(parts)

    def _validate_proposal(self, p: dict, before: int | None) -> tuple[Event, list[int]]:
        text = p.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ProposalRejected("empty_text")
        text = redact_secrets(text.strip())
        if len(text) > _MAX_PROPOSAL_CHARS:
            raise ProposalRejected(f"too_long>{_MAX_PROPOSAL_CHARS}")
        if _SELF_REF_RE.search(text):
            raise ProposalRejected("self_reference")
        src_raw = p.get("source_unit_ids") or p.get("src") or []
        src = parse_ids(src_raw)
        if not src:
            raise ProposalRejected("no_source")
        known = self.log.exists(src, before=before)
        bad = sorted(set(src) - set(known))
        if bad:
            raise ProposalRejected(f"unknown_or_future_source:{bad}")
        if not _content_grounded(text, self._cited_text(src)):
            raise ProposalRejected("ungrounded_content")
        ek = p.get("entity_key")
        sup = p.get("supersedes")
        if sup is None:
            sup = []
        if not isinstance(sup, list):
            raise ProposalRejected("supersedes_must_be_list")
        sup = parse_ids(sup)
        ev = Event(self.semantics.fingerprint(normalize(text)), normalize(text),
                   text, tuple(sorted(set(src))),
                   salience=parse_salience(p.get("salience")),
                   kind="fact", scene=self._scene,
                   entity=(ek.strip()[:120] if isinstance(ek, str) else ""))
        return ev, sup

    def propose(self, proposals: list, *, origin: str = "agent",
                signal_id: str | None = None, before: int | None = None,
                _context: InvestigationContext | None = None) -> dict:
        """agent 提议入库。逐条校验（溯源非空且存在、因果、脱敏、自指、长度），
        通过的走引擎同一条 ingest 回路；supersedes 经 update 裁决把旧条目
        取代。返回逐条结果。"""
        if not isinstance(proposals, list):
            raise ValueError("proposals must be a list")
        if len(proposals) > 50:
            raise ValueError("proposal batch exceeds limit 50; no items applied")
        accepted, new_ids, rejected = 0, [], []
        with self._lock:
            ctx = (_context if _context is not None
                   else self._admit(signal_id, before)[0])
            if ctx.task_id is not None:
                return self._durable_propose(proposals, ctx)
            bound = ctx.before
            if ctx.signal_id is not None:
                origin = ctx.origin
            if origin not in _ORIGINS:
                origin = "agent"
            t = self._t
            for i, p in enumerate(proposals):
                if not isinstance(p, dict):
                    rejected.append({"index": i, "reason": "not_an_object"})
                    continue
                try:
                    ev, sup = self._validate_proposal(p, bound)
                    if bound is not None and sup:
                        eligible = self._causal_memory_ids(bound)
                        if any(mid not in eligible for mid in sup):
                            raise ProposalRejected("unknown_or_future_supersedes")
                except ProposalRejected as exc:
                    rejected.append({"index": i, "reason": str(exc)})
                    self.n_rejected += 1
                    continue
                ev.origin = origin
                ids = self.engine.propose([ev], t)
                accepted += 1
                self.n_proposals += 1
                new_ids.extend(ids)
                if ids and sup:
                    new = ids[-1]
                    for old in sup:
                        if old in self.engine.mems and old != new:
                            self.engine.add_tension(new, old, t)
                            self.engine.submit_verdicts([(new, old, "update")], t)
            pool = self.engine.pool_sizes()
        return {"accepted": accepted, "new_ids": new_ids,
                "merged": accepted - len(new_ids), "rejected": rejected,
                "origin": origin, "pool": pool, "t": t}

    def diagnose(self, miss_type: str, note: str = "", *,
                 signal_id: str | None = None, kind: str = "",
                 usage: dict | None = None,
                 _context: InvestigationContext | None = None, _audit=True) -> dict:
        from .agent.investigator import MISS_TYPES
        if miss_type not in MISS_TYPES:
            raise ValueError(f"miss_type must be one of {MISS_TYPES}")
        with self._lock:
            ctx = _context if _context is not None else self._admit(signal_id)[0]
            if ctx.task_id is not None:
                return self._task_once(ctx, {"action": "diagnose", "miss_type": miss_type,
                                             "note": (note or "").strip()[:500]},
                    lambda: self.diagnose(miss_type, note, kind=kind, usage=usage,
                        _context=replace(ctx, task_id=None, lease_token=None), _audit=False))
            signal_id = ctx.signal_id
            self.miss_counts[miss_type] = self.miss_counts.get(miss_type, 0) + 1
            counts = dict(self.miss_counts)
        if _audit and self.state_path is not None:
            rec = {"ts": round(time.time(), 1), "t": self._t,
                   "signal_id": signal_id, "kind": kind,
                   "miss_type": miss_type, "note": (note or "")[:500],
                   "usage": usage or {}}
            try:
                with open(self.state_path.parent / "diagnoses.jsonl", "a",
                          encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError:
                pass
        return {"miss_counts": counts}

    def signals(self) -> dict:
        with self._lock:
            q = self.engine.signals
            return {"queued": self.tasks.queued_counts() | q.peek_kinds(), "n_emitted": q.n_emitted,
                    "n_dropped": q.n_dropped,
                    "open_budgets": sorted(self._budgets),
                    "tasks": self.tasks.stats(), "semantic": self.tasks.semantic_stats(),
                    "checkpoint_fault": self._checkpoint_fault,
                    "missed": self.n_missed, "proposals": self.n_proposals,
                    "rejected": self.n_rejected,
                    "candgen_fail": self.n_candgen_fail,
                    "miss_counts": dict(self.miss_counts),
                    "log_units": self.log.count(), "units": self.log.work_stats(),
                    "agent": self.agent.stats() if self.agent else None,
                    "t": self._t}

    # ================================================== 持久化
    def _state(self):
        return {
                "mems": self.engine.mems, "tensions": self.engine.tensions,
                "next_id": self.engine._next_id,
                "consolidation_pending": self.engine._consolidation_pending,
                "consolidation_deferred": self.engine._consolidation_deferred,
                "counters": {k: getattr(self.engine, k) for k in _COUNTERS},
                "shadow_pending": list(self.engine._shadow_pending),
                "retrievals": self._retrievals,
                "next_retrieval": self._next_retrieval,
                "miss_counts": dict(self.miss_counts),
                "service_counters": {k: getattr(self, k) for k in _SERVICE_COUNTERS},
                "t": self._t, "unit_id": self._unit_id, "scene": self._scene,
                "scene_t": self._scene_t}

    def _dump_state(self):
        self._ensure_healthy()
        return pickle.dumps(self._state(), protocol=4)

    def save(self) -> dict:
        if self.state_path is None:
            return {"saved": False, "reason": "no state_dir"}
        with self._lock:
            state = self._dump_state()
            if self._checkpoint_revision or self.tasks.checkpoint()[0]:
                revision = self._checkpoint_revision
                try:
                    self._checkpoint_revision = self.tasks.save_checkpoint(state, revision)
                except BaseException:
                    self._check_checkpoint_error(revision)
                    raise
            tmp = self.state_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                f.write(state)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
            if not self._snapshot_quarantined:
                self._snapshot_status = "loaded"
        return {"saved": True, "mems": len(self.engine.mems)}

    def _load(self, checkpoint: bytes | None = None) -> None:
        if checkpoint is None:
            with open(self.state_path, "rb") as f:
                state = _RestrictedUnpickler(f).load()
        else:
            state = _RestrictedUnpickler(io.BytesIO(checkpoint)).load()
        if not isinstance(state, dict):
            raise ValueError(f"state.pkl 顶层类型异常: {type(state).__name__}")
        missing = _STATE_KEYS - state.keys()
        if missing:
            raise ValueError(f"state.pkl 缺字段: {sorted(missing)}")
        # 先校验容器/对象类型及游标、计数器，再发布到服务；否则末尾字段损坏会留下
        # mems 已恢复、next_id/t 尚未恢复的半个引擎。兼容旧档缺少可选字段。
        state.setdefault("retrievals", {})
        state.setdefault("next_retrieval", 0)
        state.setdefault("miss_counts", {})
        state.setdefault("service_counters", {})

        def nonnegative_int(value):
            return type(value) is int and value >= 0

        for key in ("next_id", "next_retrieval", "t", "unit_id"):
            if not nonnegative_int(state[key]):
                raise ValueError(f"state.pkl 的 {key} 必须是非负整数")
        for key in ("mems", "tensions", "consolidation_deferred", "counters",
                    "retrievals", "miss_counts", "service_counters"):
            if not isinstance(state[key], dict):
                raise ValueError(f"state.pkl 的 {key} 必须是 dict")
        if not isinstance(state["scene"], str):
            raise ValueError("state.pkl 的 scene 必须是字符串")
        if (type(state.get("scene_t", state["t"] - 1)) is not int
                or state.get("scene_t", state["t"] - 1) < -1):
            raise ValueError("state.pkl 的 scene_t 必须是整数")
        if (not isinstance(state["consolidation_pending"], set)
                or not all(nonnegative_int(i) for i in state["consolidation_pending"])):
            raise ValueError("state.pkl 的 consolidation_pending 必须是 id 集合")
        if any(not isinstance(k, str) or not isinstance(v, frozenset)
               or not all(nonnegative_int(i) for i in v)
               for k, v in state["consolidation_deferred"].items()):
            raise ValueError("state.pkl 的 consolidation_deferred 格式异常")
        pending = state.get("shadow_pending", [])
        if not _valid_shadow_pending(pending):
            raise ValueError("state.pkl 的 shadow_pending 格式异常")
        if any(not nonnegative_int(i) or not isinstance(m, Memory)
               or m.id != i or not isinstance(m.pool, Pool)
               for i, m in state["mems"].items()):
            raise ValueError("state.pkl 的 mems 格式异常")
        if any(not isinstance(k, tuple) or len(k) != 2
               or not all(nonnegative_int(i) for i in k) or not isinstance(v, Tension)
               for k, v in state["tensions"].items()):
            raise ValueError("state.pkl 的 tensions 格式异常")
        if any(not nonnegative_int(i) or not isinstance(r, Retrieval)
               for i, r in state["retrievals"].items()):
            raise ValueError("state.pkl 的 retrievals 格式异常")
        for key, allowed in (("counters", _COUNTERS),
                             ("service_counters", _SERVICE_COUNTERS)):
            if any(k not in allowed or not nonnegative_int(v)
                   for k, v in state[key].items()):
                raise ValueError(f"state.pkl 的 {key} 含未知或非法计数器")
        if any(not isinstance(k, str) or not nonnegative_int(v)
               for k, v in state["miss_counts"].items()):
            raise ValueError("state.pkl 的 miss_counts 格式异常")
        for m in state["mems"].values():
            for k, v in _MEMORY_FIELD_DEFAULTS.items():
                if k not in m.__dict__:
                    setattr(m, k, v)

        eng = self.engine
        eng.mems = state["mems"]
        eng.tensions = state["tensions"]
        eng._next_id = max(state["next_id"], max(eng.mems, default=-1) + 1)
        eng._consolidation_pending = state["consolidation_pending"]
        eng._consolidation_deferred = state["consolidation_deferred"]
        eng._shadow_pending = [_shadow_entry(item) for item in pending]
        for k, v in state["counters"].items():
            setattr(eng, k, v)
        self._retrievals = state["retrievals"]
        self._next_retrieval = max(state["next_retrieval"],
                                   max(self._retrievals, default=-1) + 1)
        self.miss_counts = state["miss_counts"]
        for k, v in state["service_counters"].items():
            setattr(self, k, v)
        self._t = state["t"]
        self._unit_id = state["unit_id"]
        self._scene = state["scene"]
        self._scene_t = state.get("scene_t", state["t"] - 1)


# ============================ HTTP ============================

_SIGNAL_PATHS = {"/recall", "/search", "/conflicts", "/resolve", "/propose",
                 "/diagnose", "/log/search", "/log/timeline", "/log/stats", "/log/window"}

_MAX_BODY = 4 * 1024 * 1024          # 请求体上限 4MiB
_GET_PATHS = {"/recall", "/conflicts", "/signals"}   # /health 单列免鉴权
_POST_PATHS = {"/observe", "/feedback", "/resolve", "/human-reviews", "/human-review", "/search", "/save",
               "/miss", "/log/search", "/log/timeline", "/log/stats",
               "/log/window", "/propose", "/diagnose"}


class _HttpError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._:-]{8,80}")


def _validate_request_id(value):
    if value is None:
        return None
    if not isinstance(value, str) or _REQUEST_ID_RE.fullmatch(value) is None:
        raise ValueError("request_id must be 8–80 characters of [A-Za-z0-9._:-]")
    return value


def _capture_fingerprint(fields: dict) -> str:
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _content_grounded(proposal, source: str) -> bool:
    """正文至少有一个可核对片段出现在所引原文中。

    可核对片段是连续两个汉字，或长度 ≥ 4 的 ASCII/数字串。长度 ≥ 8 的标识
    （脱敏占位 REDACTED 除外）必须全部出现，不能靠一个真片段夹带假标识。
    没有任何可核对片段时拒绝：无法区分空话和编造。
    """
    if not isinstance(proposal, str) or not isinstance(source, str):
        return False
    prop = "".join(proposal.split())
    src = "".join(source.split())
    src_l = src.lower()
    matched = False
    for i in range(len(prop) - 1):
        a, b = prop[i], prop[i + 1]
        if "\u4e00" <= a <= "\u9fff" and "\u4e00" <= b <= "\u9fff" and prop[i:i + 2] in src:
            matched = True
            break
    # 标识按原文切分。先去空白会把 “handler.ts cannot” 粘成一个假长标识。
    tokens = re.findall(r"[A-Za-z0-9_]{4,}", proposal)
    long = [tok for tok in tokens if len(tok) >= 8 and tok.lower() != "redacted"]
    if any(tok.lower() not in src_l for tok in long):
        return False
    if any(tok.lower() in src_l for tok in tokens if tok.lower() != "redacted"):
        matched = True
    return matched


def _valid_shadow_pending(pending) -> bool:
    if not isinstance(pending, list):
        return False
    for item in pending:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            return False
        key, mid, t_ret, rel = item
        if not isinstance(key, (list, tuple)) or len(key) != 2:
            return False
        if any(type(i) is not int or i < 0 for i in (*key, mid, t_ret)):
            return False
        if not isinstance(rel, bool):
            return False
    return True


def _shadow_entry(item) -> tuple:
    key, mid, t_ret, rel = item
    return (tuple(key), mid, t_ret, rel)


def _annotate_observe(body: dict, unit_id: int, *, replayed: bool,
                      request_id: str | None) -> dict:
    out = {k: v for k, v in body.items() if k != "next_memory_id"}
    out["accepted"] = True
    out["unit_id"] = unit_id
    if replayed:
        out["replayed"] = True
    if request_id:
        out["request_id"] = request_id
    return out


def _opt_int(body: dict, key: str, *, positive: bool = False):
    v = body.get(key)
    if v is None:
        return None
    if type(v) is not int or not -(2**63) <= v < 2**63:
        raise _HttpError(400, f"{key} must be a 64-bit int")
    if positive and v <= 0:
        raise _HttpError(400, f"{key} must be positive")
    return v


def _req_str(body: dict, key: str) -> str:
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise _HttpError(400, f"{key} required")
    return v


class _Handler(BaseHTTPRequestHandler):
    service: MemoryService

    def log_message(self, *args) -> None:   # 静默访问日志
        pass

    def _reply(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return secrets.compare_digest(
            (self.headers.get("Authorization") or "").encode("utf-8"),
            f"Bearer {self.service.token}".encode("utf-8"))

    def _body(self) -> dict:
        ct = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ct != "application/json":
            raise _HttpError(415, "Content-Type must be application/json")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise _HttpError(400, "bad Content-Length")
        if n < 0:
            raise _HttpError(400, "bad Content-Length")
        if n > _MAX_BODY:
            raise _HttpError(413, "body too large")
        if not n:
            return {}
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            raise _HttpError(400, "malformed JSON body")
        if not isinstance(body, dict):
            raise _HttpError(400, "body must be a JSON object")
        return body

    def _dispatch(self, path: str, q: dict, body: dict) -> None:
        svc = self.service
        raw_sid = self.headers.get("X-Signal-Id")
        sid = raw_sid.strip() if raw_sid is not None else None
        # /health 是插件启动时使用的公开探针，不计工具预算，也不返回原文。
        if sid is not None and path != "/health" and path not in _SIGNAL_PATHS:
            raise SignalClosed(f"调查员不允许访问 {path}")
        if path == "/health":
            body = svc.health_view()
            self._reply(503 if not body["ok"] else 200, body)
        elif path == "/recall":
            try:
                k = int(q["k"]) if q.get("k") else None
            except ValueError:
                raise _HttpError(400, "k must be int")
            if k is not None and k <= 0:
                raise _HttpError(400, "k must be positive")
            query = q.get("q", "")
            if not query:
                raise _HttpError(400, "q required")
            budget = q.get("budget_tokens")
            if budget is not None:
                try:
                    budget = int(budget)
                except ValueError:
                    raise _HttpError(400, "budget_tokens must be int")
            self._reply(200, svc.recall(query, k, signal_id=sid,
                                       budget_tokens=budget,
                                       passive=q.get("passive", "") in ("1", "true")))
        elif path == "/conflicts":
            self._reply(200, svc.conflicts(signal_id=sid))
        elif path == "/signals":
            self._reply(200, svc.signals())
        elif path == "/observe":
            user = body.get("user_text", "")
            assistant = body.get("assistant_text", "")
            if not isinstance(user, str) or not isinstance(assistant, str):
                raise _HttpError(400, "user_text/assistant_text must be strings")
            if not user.strip() and not assistant.strip():
                raise _HttpError(400, "empty turn")
            self._reply(200, svc.observe(user, assistant, request_id=self._capture_id(body)))
        elif path == "/feedback":
            rid = _opt_int(body, "retrieval_id")
            if rid is None:
                raise _HttpError(400, "retrieval_id required")
            question, answer = body.get("question", ""), body.get("answer", "")
            if not isinstance(question, str) or not isinstance(answer, str):
                raise _HttpError(400, "question/answer must be strings")
            out = svc.feedback(rid, question, answer, request_id=self._capture_id(body))
            if "error" in out:
                if "already" in out["error"]:
                    self._reply(409, out)
                    return
                raise _HttpError(404, out["error"])
            self._reply(200, out)
        elif path == "/human-reviews":
            self._reply(200, {"reviews": svc.human_reviews()})
        elif path == "/human-review":
            rid = _opt_int(body, "review_id")
            if rid is None:
                raise _HttpError(400, "review_id required")
            self._reply(200, svc.decide_human_review(
                rid, str(body.get("decision", "")),
                self.headers.get("X-Human-Review-Token", "")))
        elif path == "/resolve":
            if svc.trio_mode:
                raise _HttpError(403, "direct resolution disabled; human review is required")
            left, right = _opt_int(body, "left"), _opt_int(body, "right")
            if left is None or right is None:
                raise _HttpError(400, "left/right required")
            ensure = body.get("ensure_tension", False)
            if not isinstance(ensure, bool):
                raise _HttpError(400, "ensure_tension must be bool")
            verdict = str(body.get("verdict", "pending"))
            if verdict not in _VERDICTS:
                raise _HttpError(400, f"verdict must be one of "
                                      f"{sorted(_VERDICTS)}")
            ek = body.get("entity_key", "")
            self._reply(200, svc.resolve(
                left, right, verdict,
                entity_key=ek if isinstance(ek, str) else "",
                ensure_tension=ensure, signal_id=sid))
        elif path == "/search":
            k = _opt_int(body, "k", positive=True)
            query = body.get("query", "")
            if not isinstance(query, str) or not query:
                raise _HttpError(400, "query required")
            self._reply(200, svc.recall(query, k, signal_id=sid,
                                       budget_tokens=_opt_int(body, "budget_tokens"),
                                       passive=body.get("passive", False)))
        elif path == "/miss":
            query = _req_str(body, "query")
            hint = body.get("hint", "")
            source = body.get("source", "agent_tool")
            self._reply(200, svc.report_miss(
                query, hint if isinstance(hint, str) else "",
                source if isinstance(source, str) else "agent_tool"))
        elif path == "/log/search":
            query = _req_str(body, "query")
            scene = body.get("scene")
            self._reply(200, svc.log_search(
                query, before=_opt_int(body, "before"),
                scene=scene if isinstance(scene, str) else None,
                k=_opt_int(body, "k", positive=True) or 8, signal_id=sid))
        elif path == "/log/timeline":
            entity = _req_str(body, "entity")
            self._reply(200, svc.log_timeline(
                entity, before=_opt_int(body, "before"),
                limit=_opt_int(body, "limit", positive=True) or 30,
                signal_id=sid))
        elif path == "/log/stats":
            gb = body.get("group_by", "scene")
            if gb not in ("scene", "entity", "week"):
                raise _HttpError(400, "group_by must be scene | entity | week")
            self._reply(200, svc.log_stats(
                gb, before=_opt_int(body, "before"),
                limit=_opt_int(body, "limit", positive=True) or 30,
                signal_id=sid))
        elif path == "/log/window":
            ids = body.get("unit_ids")
            if (not isinstance(ids, list) or not ids or len(ids) > 20
                    or not all(type(i) is int and 0 <= i < 2**63 for i in ids)):
                raise _HttpError(400, "unit_ids must be a non-empty int list (≤20)")
            self._reply(200, svc.log_window(
                ids, max_chars=_opt_int(body, "max_chars", positive=True),
                signal_id=sid))
        elif path == "/propose":
            if svc.trio_mode:
                raise _HttpError(403, "direct proposals disabled; use Hauler and Selector")
            props = body.get("proposals")
            if not isinstance(props, list):
                raise _HttpError(400, "proposals must be a list")
            origin = body.get("origin", "agent")
            self._reply(200, svc.propose(
                props, origin=origin if isinstance(origin, str) else "agent",
                signal_id=sid, before=_opt_int(body, "before")))
        elif path == "/diagnose":
            if svc.trio_mode:
                raise _HttpError(403, "direct diagnosis disabled; Reviewer owns this work")
            mt = _req_str(body, "miss_type")
            note = body.get("note", "")
            try:
                self._reply(200, svc.diagnose(
                    mt, note if isinstance(note, str) else "", signal_id=sid,
                    kind=str(body.get("kind", ""))))
            except ValueError as exc:
                raise _HttpError(400, str(exc))
        elif path == "/save":
            self._reply(200, svc.save())
        else:
            self._reply(404, {"error": f"no such path: {path}"})

    def _capture_id(self, body: dict) -> str | None:
        header = self.headers.get("X-Request-Id")
        if header is not None:
            header = header.strip()
        if header == "":
            raise _HttpError(400, "X-Request-Id must not be empty")
        if "request_id" in body and not isinstance(body.get("request_id"), str):
            raise _HttpError(400, "request_id must be a string")
        body_id = body.get("request_id")
        if body_id == "":
            raise _HttpError(400, "request_id must not be empty")
        if header and body_id and header != body_id:
            raise _HttpError(400, "X-Request-Id and request_id disagree")
        chosen = body_id or header or None
        if chosen is None:
            return None
        try:
            return _validate_request_id(chosen)
        except ValueError as exc:
            raise _HttpError(400, str(exc)) from exc

    def _run(self, path: str, q: dict, body: dict) -> None:
        try:
            self._dispatch(path, q, body)
        except _HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
        except CaptureConflict as exc:
            self._reply(409, {"error": str(exc)})
        except (TaskQueueFull, CheckpointConflict) as exc:
            payload = {"error": str(exc)}
            if getattr(exc, "accepted", False):
                payload.update(accepted=True, pending=True, unit_id=exc.unit_id)
                if getattr(exc, "request_id", None):
                    payload["request_id"] = exc.request_id
            self._reply(503, payload)
        except PermissionError as exc:          # 预算用尽
            self._reply(429, {"error": str(exc)})
        except (SignalClosed, CausalViolation) as exc:             # 信号号无效/已关闭
            self._reply(403, {"error": str(exc)})
        except ValueError as exc:
            self._reply(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self) -> None:    # noqa: N802
        u = urlparse(self.path)
        if u.path == "/health":
            self._run(u.path, {}, {})
            return
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        if u.path not in _GET_PATHS:
            self._reply(405, {"error": f"{u.path} requires POST"})
            return
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self._run(u.path, q, {})

    def do_POST(self) -> None:   # noqa: N802
        u = urlparse(self.path)
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        if u.path not in _POST_PATHS:
            self._reply(405, {"error": f"{u.path} requires GET"})
            return
        try:
            body = self._body()
        except _HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
            return
        self._run(u.path, {}, body)


def serve(service: MemoryService, port: int,
          host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = type("_BoundHandler", (_Handler,), {"service": service})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd


# ============================ 默认组装 ============================

_TOKEN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


def approx_tokens(text: str) -> int:
    """与 TIDE 平台一致的近似 token 计数：CJK 单字 = 1，ASCII 词 = 1，
    其余非空白符号 = 1。只用于预算截断，不追求与具体 tokenizer 对齐。"""
    return len(_TOKEN_RE.findall(text))



def _load_env_key(project_dir: Path) -> str | None:
    key = os.environ.get("ZAI_API_KEY")
    if key:
        return key
    for env_file in (Path(project_dir) / ".env",
                     Path(__file__).resolve().parents[1] / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ZAI_API_KEY="):
                    val = (line.split("=", 1)[1].strip()
                           .strip('"').strip("'"))
                    if val:
                        return val
    return None


def build_default_service(project_dir: str | Path,
                          model: str = "glm-5.3-flash",
                          embed_log: bool = True, task_capacity: int = 4096) -> MemoryService:
    from .embed.cache import SqliteEmbeddingCache
    from .embed.zhipu import ZhipuEmbedder

    mem_dir = Path(project_dir) / ".opencode" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    # 目录内含 bearer token + 全量记忆语料 + 原始日志：用户项目里通常没有
    # gitignore 覆盖它——自己写一个，防 `git add .` 把 token/state/日志提交进库
    gi = mem_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    key = _load_env_key(Path(project_dir))

    def chat_fn(system: str, user: str) -> str:
        return chat(api_key=key, model=model, system=system, user=user,
                    cache_dir=mem_dir / "chat-cache")

    emb = ZhipuEmbedder(api_key=key,
                        cache=SqliteEmbeddingCache(mem_dir / "emb.sqlite3"))
    semantics = LLMSemantics(None, chat_fn=chat_fn, model=model)
    cfg = Cfg(theta=0.35, cap_m=8, k=5, tau_dup=0.85, tau_sim=0.78,
              useful_hit=True, defer_credit=True)
    log = LogStore(mem_dir / "log.sqlite", embedder=emb if embed_log else None)
    return MemoryService(cfg, emb, semantics, ChatGenerator(chat_fn),
                         state_dir=mem_dir, logstore=log, task_capacity=task_capacity)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=17872)
    ap.add_argument("--project", default=".")
    ap.add_argument("--model", default="glm-5.3-flash")
    # 插件拉起 sidecar 时不传参，调查员相关配置允许走环境变量
    ap.add_argument("--agent-model",
                    default=os.environ.get("MEMORY_AGENT_MODEL", "glm-5.3-flash"),
                    help="进程内调查员模型（兼容 provider/model）")
    ap.add_argument("--no-agent", action="store_true",
                    default=os.environ.get("MEMORY_AGENT", "").lower()
                    in ("off", "0", "false"),
                    help="不启动后台 agent（任务留在 SQLite）；环境变量 MEMORY_AGENT=off 等价")
    ap.add_argument("--agent-daily-cap", type=int,
                    default=int(os.environ.get("MEMORY_AGENT_DAILY_CAP", "200")))
    ap.add_argument("--agent-tool-calls", type=int, default=8)
    ap.add_argument("--agent-window-chars", type=int, default=4000)
    ap.add_argument("--task-queue-cap", type=int, default=4096,
                    help="未结束调查任务上限；满时拒绝新任务，不逐出已接受任务")
    ap.add_argument("--agent-retry-delay", type=float, default=2.0,
                    help="调查/应用失败的指数退避起点（秒，上限 300 秒）")
    args = ap.parse_args()
    if args.task_queue_cap < 1:
        ap.error("--task-queue-cap must be positive")
    if not math.isfinite(args.agent_retry_delay) or args.agent_retry_delay < 0:
        ap.error("--agent-retry-delay must be finite and non-negative")

    service = build_default_service(args.project, model=args.model, task_capacity=args.task_queue_cap)
    service.trio_mode = os.environ.get("MEMORY_PIPELINE", "opencode").lower() != "legacy"
    service.start_unit_recovery()  # 即使 --no-agent，已提交 L0 也必须能恢复
    httpd = serve(service, args.port)
    port = httpd.server_address[1]

    agent = None
    if not args.no_agent and not service.trio_mode:
        from .agent.inline import InlineInvestigator
        from .agent.investigator import Budget
        from .agent.loop import AgentWorker
        key = _load_env_key(Path(args.project))
        if not key:
            print("[memory-sidecar] 调查员未启动: ZAI_API_KEY 未设置",
                  file=sys.stderr, flush=True)
        else:
            # 进程内 function-calling 循环，不经 HTTP
            inv = InlineInvestigator(service, model=args.agent_model, api_key=key)
            agent = AgentWorker(service, inv, daily_cap=args.agent_daily_cap,
                                retry_delay_s=args.agent_retry_delay,
                                budget=Budget(tool_calls=args.agent_tool_calls,
                                              window_chars=args.agent_window_chars))
            service.attach_agent(agent)
            agent.start()

    trio = None
    if service.trio_mode and not args.no_agent:
        from .agent.trio import TrioWorker, OpenCodeRunner
        trio = TrioWorker(service, OpenCodeRunner(Path(args.project)))
        service.trio_worker = trio
        trio.start()

    view = service.health_view()
    print(f"[memory-sidecar] http://127.0.0.1:{port} "
          f"project={Path(args.project).resolve()} "
          f"mems={len(service.engine.mems)} log_units={service.log.count()} "
          f"snapshot={view['snapshot']} units_pending={view['units_pending']} "
          f"validation={view['validation']} "
          f"agent={'on' if agent or trio else 'off'}", flush=True)

    def _term(*_):          # 插件 kill 发 SIGTERM：走 finally 存盘
        raise SystemExit(0)

    _signal.signal(_signal.SIGTERM, _term)
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        service.stop_unit_recovery()
        if agent is not None:
            agent.stop()
        if trio is not None:
            trio.stop()
        service.save()
        httpd.server_close()


if __name__ == "__main__":
    main()
