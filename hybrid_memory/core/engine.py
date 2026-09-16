"""MemoryEngine 门面：对外只有 observe / retrieve / step 三个方法。

agent runtime 视角：write(event) 与 retrieve(q)→top-K。
内部三回路拆在 ingest / retrieval / maintenance 模块。
"""
from __future__ import annotations

import numpy as np

from ..config import Cfg
from ..core.types import (Event, FeedbackSemantics, Memory,
                          MemorySemantics, Pool, Query, Retrieval, Tension)
from ..embed.base import Embedder
from . import ingest, maintenance, retrieval


class MemoryEngine:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics: MemorySemantics):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.mems: dict[int, Memory] = {}
        self.tensions: dict[tuple[int, int], Tension] = {}
        self._consolidation_pending: set[int] = set()
        self._consolidation_deferred: dict[str, frozenset[int]] = {}
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

    # ---- metrics 辅助 ----
    def pool_sizes(self) -> dict[str, int]:
        out = {p.value: 0 for p in Pool}
        for m in self.mems.values():
            out[m.pool.value] += 1
        return out
