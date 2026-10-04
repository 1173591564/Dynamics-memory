"""服务门面(P4:原 server.py 的 MemoryService 类整体迁入)。

组装依赖、持有 RLock；回路实现转发到 service/ 各模块，不放业务实现。
HTTP 与组装已迁入 transport/（P5），server.py 仅剩兼容垫片。
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import os
import secrets
import threading
from pathlib import Path

from ..errors import Degraded
from ..legacy.candgen import CandidateGenerator
from .. import telemetry
from . import observability
from ..config import Cfg
from ..core.engine import MemoryEngine
from ..core.types import Event, Retrieval
from ..core.types import Embedder
from . import budgets, feedback, lifecycle, observe, operate, recall, review, tools
from .context import InvestigationContext
from ..dispatch import effects, policy, worker
from .operate import ProposalRejected  # noqa: F401 — trio/review 经门面复用
from ..store.evidence import LogStore
from ..store import state
from ..store.state import _COUNTERS, _SERVICE_COUNTERS
from ..store.tasks import TaskStore


class MemoryService:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics, generator:
                 CandidateGenerator, state_dir: Path | None = None,
                 logstore: LogStore | None = None, task_capacity: int = 4096):
        policy.assert_consumers(effects.EFFECTS)  # H25：kind 缺消费者拒绝启动
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
        self._state_bytes = 0       # 最近一次引擎状态序列化字节数（N49 预算闸/水位）
        self._checkpoint_fault = False
        self._snapshot_status = "absent"
        self._snapshot_quarantined = False
        self.token = self._load_or_create_token()
        self.human_review_token = self._review_token()
        self.agent = None                 # legacy AgentWorker，attach_agent 挂上
        self.dispatch_worker = None       # DispatchWorker，attach_dispatch 挂上
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
        N49：telemetry 基础字段之外，并入 observability.capacity_status
        水位（pin 占用+checkpoint 预算，A7 只许加字段）。
        """
        out = telemetry.health_view(self)
        out.update(observability.capacity_status(self))
        return out

    def _ensure_healthy(self):
        lifecycle.ensure_healthy(self)

    def _check_checkpoint_error(self, revision):
        """提交确认丢失检测（N43）：只比较 durable revision 是否越过回滚前值。

        不复用启动校验器 TaskStore.checkpoint()——它在"durable 缺失但存在
        已领取任务"时抛错，会把干净回滚误判成 fault（首次提交前的失败、
        无 durable 的测试库都会触发，服务被砖死）。durable 缺失且内存
        revision 为 0 = 不可能有已提交但确认丢失的 checkpoint，回滚安全。
        """
        try:
            row = self.tasks.durable_revision()
        except Exception:
            self._checkpoint_fault = True
            return
        self._checkpoint_fault = (0 if row is None else row) != revision

    def _journal_signal(self, kind, payload, t, key, merge):
        return effects.journal_signal(self, kind, payload, t, key, merge)

    def _signal_payload(self, kind, payload):
        return effects.signal_payload(self, kind, payload)

    def _commit_sidecar_effect(self, mutate, *, capture=None):
        # I5 唯一入口 effects.effect_transaction 的兼容别名（P4 回路/测试在用）。
        return effects.effect_transaction(self, mutate, capture=capture)

    @contextmanager
    def _rollback_effect(self):
        """任务操作与单元效果共用的内存回滚；原 Memory/队列对象身份不变。"""
        self._ensure_healthy()
        # N49（PENDING-09）checkpoint 预算闸：最近一次已提交的引擎状态序列化
        # 超预算线时拒收新的效果提交（Degraded→503）。全量 pickle 的 O(N)
        # 写放大越过设计包线必须吵闹失败；闸门读已记账水位，零额外序列化。
        # save/恢复不受闸（持久化与读取不是写放大）；置闸于备份之前，无残局。
        if self._state_bytes > observability.CHECKPOINT_BUDGET_BYTES:
            raise Degraded(
                "checkpoint_over_budget",
                "engine state serialization exceeds budget; effect rejected",
                f"{self._state_bytes} > {observability.CHECKPOINT_BUDGET_BYTES} bytes "
                "(PENDING-09: segmented-pickle ADR required)")
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
        # 效果深度：>0 表示外层效果上下文（任务操作/apply_effect）已拥有
        # checkpoint 与回滚，内层直写只改内存、不再开嵌套事务（N47）。
        depth = getattr(self, "_effect_depth", 0) + 1
        self._effect_depth = depth
        try:
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
        finally:
            self._effect_depth = depth - 1

    # 供 AgentWorker 使用的最小接口
    @property
    def lock(self):
        return self._lock

    def current(self) -> tuple[int, str]:
        return self._t, self._scene

    def attach_agent(self, agent) -> None:
        self.agent = agent

    def attach_dispatch(self, worker) -> None:
        """挂后台循环（P6 最终形态；worker 只需有 notify()）。"""
        self.dispatch_worker = worker

    def notify(self) -> None:
        """唤醒后台循环早跑一轮（legacy agent 与 dispatch 二选一常设）。"""
        if self.dispatch_worker is not None:
            self.dispatch_worker.notify()
        if self.agent is not None:
            self.agent.notify()

    def _kick(self) -> None:
        self.notify()

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
        # 测试 seam：实例 stub 经此方法生效，worker 回调此处。
        return worker.semantic_model(self, row)

    def process_semantic_tasks(self, limit: int = 8) -> dict:
        return worker.run_semantic_tasks(self, limit)

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
        return operate.report_miss(self, query, hint, source)

    def conflicts(self, *, signal_id: str | None = None) -> dict:
        return tools.conflicts(self, signal_id=signal_id)

    def resolve(self, left: int, right: int, verdict: str,
                entity_key: str = "", ensure_tension: bool = False, *,
                signal_id: str | None = None,
                _context: InvestigationContext | None = None,
                _checkpoint: bool = True) -> dict:
        """裁决回报。ensure_tension=True（调查员/主 agent 主动裁决两条此前
        没被判为张力的记忆）时先登记 tension 再消解；entity_key 回填到双方。"""
        return operate.resolve(self, left, right, verdict, entity_key,
                               ensure_tension, signal_id=signal_id,
                               _context=_context, _checkpoint=_checkpoint)

    # ================================================== 日志工具面
    def _admit(self, signal_id: str | None, before: int | None = None, *,
               window: bool = False, max_chars: int | None = None
               ) -> tuple[InvestigationContext, dict | None, int]:
        return budgets.admit(self, signal_id, before, window=window,
                             max_chars=max_chars)

    def log_search(self, query: str, *, before=None, scene=None, k=8,
                   signal_id: str | None = None) -> dict:
        return tools.log_search(self, query, before=before, scene=scene, k=k,
                                signal_id=signal_id)

    def log_timeline(self, entity: str, *, before=None, limit=30,
                     signal_id: str | None = None) -> dict:
        return tools.log_timeline(self, entity, before=before, limit=limit,
                                  signal_id=signal_id)

    def log_stats(self, group_by: str = "scene", *, before=None, limit=30,
                  signal_id: str | None = None) -> dict:
        return tools.log_stats(self, group_by, before=before, limit=limit,
                               signal_id=signal_id)

    def log_window(self, unit_ids, *, max_chars=None,
                   signal_id: str | None = None) -> dict:
        return tools.log_window(self, unit_ids, max_chars=max_chars,
                                signal_id=signal_id)

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
    def _validate_proposal(self, p: dict, before: int | None) -> tuple[Event, list[int]]:
        return operate.validate_proposal(self, p, before)

    def propose(self, proposals: list, *, origin: str = "agent",
                signal_id: str | None = None, before: int | None = None,
                _context: InvestigationContext | None = None) -> dict:
        """agent 提议入库。逐条校验（溯源非空且存在、因果、脱敏、自指、长度），
        通过的走引擎同一条 ingest 回路；supersedes 经 update 裁决把旧条目
        取代。返回逐条结果。"""
        return operate.propose(self, proposals, origin=origin,
                                 signal_id=signal_id, before=before,
                                 _context=_context)

    def diagnose(self, miss_type: str, note: str = "", *,
                 signal_id: str | None = None, kind: str = "",
                 usage: dict | None = None,
                 _context: InvestigationContext | None = None, _audit=True) -> dict:
        return operate.diagnose(self, miss_type, note, signal_id=signal_id,
                                 kind=kind, usage=usage, _context=_context,
                                 _audit=_audit)

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
