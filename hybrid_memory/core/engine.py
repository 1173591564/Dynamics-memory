"""MemoryEngine 门面：agent runtime 视角是 observe / retrieve / step。

信号化（P1 影子模式）：引擎在有活可干时向 SignalQueue 发射信号
（conflict_pending / feedback_pending / maintenance_due / thin_recall），
并暴露操作面（submit_relevance / submit_verdicts / add_reflection）供
后续 LLM worker 回报。P1 阶段同步 semantics 调用照旧，行为不变。
内部三回路拆在 ingest / retrieval / maintenance 模块。
"""
from __future__ import annotations

import numpy as np

from ..config import Cfg
from ..core.signals import SignalQueue
from ..core.types import (Event, FeedbackSemantics, Memory,
                          MemorySemantics, Pool, Query, Retrieval, Tension)
from ..embed.base import Embedder
from . import consolidation, ingest, maintenance, retrieval


class MemoryEngine:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics: MemorySemantics):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.mems: dict[int, Memory] = {}
        self.tensions: dict[tuple[int, int], Tension] = {}
        self._consolidation_pending: set[int] = set()
        self._consolidation_deferred: dict[str, frozenset[int]] = {}
        self._shadow_pending: list[tuple] = []   # (pair_key, m_id, t_ret, rel)
        self.n_shadow_dropped = 0
        self.signals = SignalQueue(cfg.signal_queue_cap)
        self._next_id = 0
        # 事件计数（metrics 用）
        self.n_promote = 0
        self.n_demote = 0
        self.n_evict = 0
        self.n_archive = 0
        self.n_revive = 0
        self.n_merge = 0
        self.n_collision = 0
        self.n_tension = 0
        self.n_resolve = 0
        self.n_agg = 0
        self.n_consolidate = 0

    def next_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    def add_tension(self, left: int, right: int, t: int) -> None:
        if not self.cfg.tension_on or left == right:
            return
        key = tuple(sorted((left, right)))
        tension = self.tensions.get(key)
        if tension is None:
            self.tensions[key] = Tension(key[0], key[1], t, t)
            self.n_tension += 1
            self.signals.emit("conflict_pending", [key], t,
                              key="conflict", merge=lambda o, n: o + n)
        else:
            tension.last_seen = t
            tension.observations += 1

    def observe(self, events: list[Event], t: int) -> None:
        ingest.run_ingest(self, events, t)

    def retrieve(self, q_emb: np.ndarray, q: Query, t: int) -> Retrieval:
        return retrieval.run_retrieve(self, q_emb, q, t)

    def step(self, t: int) -> None:
        maintenance.run_maintenance(self, t)

    def feedback(self, ret: Retrieval, question: str, answer: str,
                 t: int) -> int:
        """response-level 记账：recognizer 判哪些入选记忆真被答案用上，
        只给它们发 useful-hit。semantics 不满足 FeedbackSemantics 时
        退化为 selected-hit（全记）。仅应在 cfg.defer_credit=True 时
        调用、且每次 retrieve 至多调一次。返回实际入账条数。"""
        if not ret.selected:
            return 0
        if ret.credited:
            raise RuntimeError(
                "feedback 重复记账：该 Retrieval 已结清"
                "（defer_credit=False 时 retrieve 就地结算，不应再调 feedback）")
        fn = (self.semantics.relevant_set
              if isinstance(self.semantics, FeedbackSemantics) else None)
        used = (fn([m.text for m in ret.selected], question, answer)
                if fn else [True] * len(ret.selected))
        if len(used) != len(ret.selected):
            raise RuntimeError(
                f"relevant_set 返回长度 {len(used)} != selected {len(ret.selected)}")
        return self.submit_relevance(ret, used, t)

    def submit_relevance(self, ret: Retrieval, used: list, t: int) -> int:
        """操作面：worker 回报 recognizer 结果（哪些入选记忆真被用上），
        发 useful-hit。语义与 feedback 的应用部分完全一致。"""
        if not ret.selected:
            return 0
        if ret.credited:
            raise RuntimeError(
                "relevance 重复记账：该 Retrieval 已结清"
                "（defer_credit=False 时 retrieve 就地结算，不应再回报）")
        n = 0
        for m, u in zip(ret.selected, used):
            if not u:
                continue
            m.last_hit = t
            if m.pool is Pool.ARCHIVE:
                m.pool = Pool.CANDIDATE if self.cfg.two_pool else Pool.MEMORY
                self.n_revive += 1
            m.hits += 1
            m.d_hit += 1.0
            n += 1
        ret.n_useful = n
        ret.credited = True
        return n

    # ---- shadow 延迟记账（shadow_defer=True 时启用）----
    def _record_shadow_pending(self, m: Memory, rival: Memory, t: int,
                               rel: bool) -> None:
        key = tuple(sorted((m.id, rival.id)))
        self._shadow_pending.append((key, m.id, t, bool(rel)))
        if len(self._shadow_pending) > self.cfg.shadow_pending_cap:
            self._shadow_pending.pop(0)
            self.n_shadow_dropped += 1

    def _issue_shadow_credit(self, m: Memory, t_ret: int) -> None:
        m.d_shadow += 1.0
        m.last_hit = t_ret
        if m.pool is Pool.ARCHIVE:
            m.pool = Pool.CANDIDATE if self.cfg.two_pool else Pool.MEMORY
            self.n_revive += 1

    def _settle_shadow(self, pair_key: tuple, verdict: str) -> int:
        """首个 verdict 到达时结算该对全部待结算 shadow 信用
        （含 verdict=="pending"——与原同步语义一致：只要非 synonym 就发）。
        返回实际结算条数。"""
        n = 0
        keep = []
        for entry in self._shadow_pending:
            key, mid, t_ret, rel = entry
            if key != pair_key:
                keep.append(entry)
                continue
            m = self.mems.get(mid)
            if verdict != "synonym" and rel and m is not None:
                self._issue_shadow_credit(m, t_ret)
                n += 1
        self._shadow_pending = keep
        return n

    def submit_verdicts(self, verdicts, t: int) -> int:
        """操作面：worker 回报批量 tension 裁决 [(left, right, verdict)]。
        verdict=="pending" 保持 backlog 不消解。返回实际消解条数。"""
        n = 0
        for left, right, verdict in verdicts:
            key = tuple(sorted((left, right)))
            self._settle_shadow(key, verdict)
            if key not in self.tensions:
                continue
            a, b = self.mems.get(key[0]), self.mems.get(key[1])
            if a is None or b is None:
                del self.tensions[key]
                continue
            a = maintenance.follow_chain(self, a)
            b = maintenance.follow_chain(self, b)
            if a.id == b.id:
                del self.tensions[key]
                continue
            if verdict == "pending":
                continue
            del self.tensions[key]
            self.n_resolve += 1
            maintenance.apply_resolution(self, a, b, verdict, t)
            n += 1
        return n

    def add_reflection(self, event: Event, derived_from, t: int) -> Memory:
        """操作面：worker 回报 consolidation 产物（reflection 记忆入库）。
        derived_from 为源记忆 id 列表；语义与同步回调路径一致。"""
        chosen = sorted((self.mems[i] for i in derived_from
                         if i in self.mems), key=lambda m: (m.birth, m.id))
        return consolidation.admit_reflection(self, event, chosen, t)

    def drain_signals(self) -> list:
        """worker 拉取待处理信号（清空队列）。"""
        return self.signals.drain()

    # ---- metrics 辅助 ----
    def pool_sizes(self) -> dict[str, int]:
        out = {p.value: 0 for p in Pool}
        for m in self.mems.values():
            out[m.pool.value] += 1
        return out
