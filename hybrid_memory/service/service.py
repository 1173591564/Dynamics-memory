"""服务门面(P4:原 server.py 的 MemoryService 类整体迁入)。

组装依赖、持有 RLock；回路实现转发到 service/ 各模块，不放业务实现。
HTTP 与组装留在 hybrid_memory.server(P5 再拆 transport)。
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import asdict, replace
import json
import os
import re
import secrets
import sys
import threading
import time
from pathlib import Path

from ..legacy.candgen import CandidateGenerator
from ..legacy.prompt import parse_ids, parse_salience
from .. import telemetry
from ..guards.grounding import content_grounded as _content_grounded
from ..guards.redact import redact_secrets
from ..config import Cfg
from ..core.engine import MemoryEngine
from ..core.types import Event, Retrieval
from ..core.types import Embedder
from . import budgets, feedback, lifecycle, observe, recall, review
from .context import _ORIGINS, CausalViolation, InvestigationContext
from ..logstore import LogStore, entities_in
from ..semantics import normalize
from ..core import maintenance
from ..core.types import FeedbackSemantics, ConsolidationSemantics, is_visible
from ..store import state
from ..store.state import _COUNTERS, _SERVICE_COUNTERS
from ..store.tasks import SEMANTIC_KINDS, WORKFLOW_KINDS, TaskLeaseLost
from ..store.tasks import TaskStore


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
_VERDICTS = {"synonym", "update", "contradiction", "collision", "pending"}
_MISS_SOURCES = {"recognizer_none", "correction", "agent_tool", "thin",
                 "external"}


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
        lifecycle.recover_or_init(self)

    def _review_token(self) -> str:
        return review.review_token(self)

    def human_reviews(self) -> list[dict]:
        return review.human_reviews(self)

    def decide_human_review(self, review_id: int, decision: str, capability: str) -> dict:
        return review.decide_human_review(self, review_id, decision, capability)

    def _corrupt_file_exists(self) -> bool:
        return lifecycle.corrupt_file_exists(self)

    def health_view(self) -> dict:
        """进程在不在，和数据有没有干净恢复，是两件事。

        `ok` 只表示没有 checkpoint fault，插件据此复用进程。
        `validation` 固定为 unverified：本进程不能自称远程或 L3 已验证。
        """
        return telemetry.health_view(self)

    def _ensure_healthy(self):
        lifecycle.ensure_healthy(self)

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
        return observe.observe(self, user_text, assistant_text, request_id)

    def process_pending_units(self, limit: int = 8) -> dict[int, dict]:
        return observe.process_pending_units(self, limit)

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

                out, revision = self.tasks.complete(
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
            self.tasks.recover_expired(kinds=SEMANTIC_KINDS,
                                       reset_next_run_at=True)
            for item in self.tasks.list_tasks(states=("pending", "ready"), kinds=SEMANTIC_KINDS)[:limit]:
                row = None
                try:
                    with self._lock:
                        self._ensure_healthy()
                        row = self.tasks.claim(item["id"],
                                                       expected_version=item["version"])
                    if row is None:
                        continue
                    if row["state"] == "running":
                        result = self._semantic_model(row)
                        if row["kind"] == "conflict_pending":
                            stats["judged"] += len(result["verdicts"])
                        self.tasks.store_result(row["id"], row["token"], result)
                        with self._lock:
                            self._ensure_healthy()
                            row = self.tasks.claim(row["id"],
                                                           expected_version=row["version"])
                        if row is None:
                            continue
                    out = self._apply_semantic(row)
                    for key in ("resolved", "credited", "reflected", "recog_fail"):
                        stats[key] += out.get(key, 0)
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    if row is not None:
                        try:
                            self.tasks.retry(row["id"], row["token"], exc)
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
        lifecycle.start_unit_recovery(self)

    def stop_unit_recovery(self, timeout: float = 5.0) -> None:
        lifecycle.stop_unit_recovery(self, timeout)

    def _causal_memory_ids(self, before: int | None) -> set[int]:
        return recall.causal_memory_ids(self, before)

    def _causal_tensions(self, ids: set[int], before: int | None) -> dict:
        return recall.causal_tensions(self, ids, before)

    def recall(self, q: str, k: int | None = None, *,
               signal_id: str | None = None, budget_tokens: int | None = None,
               passive: bool = False) -> dict:
        return recall.recall(self, q, k, signal_id=signal_id,
                             budget_tokens=budget_tokens, passive=passive)

    def feedback(self, retrieval_id: int, question: str, answer: str,
                 request_id: str | None = None) -> dict:
        return feedback.feedback(self, retrieval_id, question, answer, request_id)

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
        return budgets.admit(self, signal_id, before, window=window,
                             max_chars=max_chars)

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
        return budgets.open_budget(self, signal_id, tool_calls=tool_calls,
                                   window_chars=window_chars, before=before,
                                   origin=origin, task_id=task_id,
                                   lease_token=lease_token)

    def close_budget(self, signal_id: str) -> dict:
        return budgets.close_budget(self, signal_id)

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
        from ..legacy.investigator import MISS_TYPES
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
        return telemetry.signals_view(self)

    # ================================================== 持久化
    def _state(self):
        return state._state(self)

    def _dump_state(self):
        return state.dump_state(self)

    def save(self) -> dict:
        return lifecycle.save(self)

    def _load(self, checkpoint: bytes | None = None) -> None:
        state.load_state(self, checkpoint)
