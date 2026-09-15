"""MemoryEngine 门面：对外只有 observe / retrieve / step 三个方法。

agent runtime 视角：write(event) 与 retrieve(q)→top-K。
内部三回路拆在 ingest / retrieval / maintenance 模块。
"""
from __future__ import annotations

import numpy as np

from ..config import Cfg
from ..core.types import (Event, Memory, MemorySemantics, Pool, Query,
                          Retrieval, Tension)
from ..embed.base import Embedder
from . import ingest, maintenance, retrieval


class MemoryEngine:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics: MemorySemantics):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.mems: dict[int, Memory] = {}
        self.tensions: dict[tuple[int, int], Tension] = {}
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

    # ---- metrics 辅助 ----
    def pool_sizes(self) -> dict[str, int]:
        out = {p.value: 0 for p in Pool}
        for m in self.mems.values():
            out[m.pool.value] += 1
        return out
