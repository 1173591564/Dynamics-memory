"""latent belief 世界 + 观测/query 流生成。

四相位由时间边界控制：
  1 稳态建立  稳定 belief 按 Zipf 频率产生观测，query 按真实使用分布
  2 漂移      指定 belief 在 t_drift 换 current_value，旧措辞停用
  3 噪声爆发  [t_noise, noise_end) 大量一次性 belief（birth==death）
  4 矛盾对    t_conflict 起注入同实体异 scope 的 belief 对

judge() 用 ground truth 替代 NLI：
  同 belief 同值 → synonym；同 belief 异值 → update（新替旧）；
  同 entity 异 scope → contradiction；其余 → collision。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.types import Event, Query
from ..embed.base import Embedder


@dataclass
class Belief:
    id: int
    entity: int
    scope: str
    birth: int
    value: str
    obs_w: float = 1.0      # 观测频率权重
    qry_w: float = 1.0      # 查询频率权重
    death: int | None = None
    noise: bool = False
    phrasings: dict = field(default_factory=dict)  # value -> [phrasings]

    def alive(self, t: int) -> bool:
        return self.birth <= t and (self.death is None or t < self.death)


class StreamGen:
    def __init__(self, emb: Embedder, seed: int = 0,
                 n_stable: int = 20, t_drift: int = 60, t_noise: int = 100,
                 noise_end: int = 140, t_conflict: int = 140,
                 n_drift: int = 3, n_pairs: int = 3, noise_rate: float = 6.0,
                 query_rate: float = 2.0, conflict_gap: int = 20):
        self.emb = emb
        self.rng = np.random.default_rng(seed)
        self.t_drift, self.t_noise = t_drift, t_noise
        self.noise_end, self.t_conflict = noise_end, t_conflict
        self.n_drift, self.n_pairs = n_drift, n_pairs
        self.noise_rate = noise_rate
        self.query_rate = query_rate
        self.conflict_gap = conflict_gap
        self._conflict_entities: list[int] = []
        self.beliefs: dict[int, Belief] = {}
        self._next_id = 0
        self._next_entity = 0
        for i in range(n_stable):   # Zipf 式频率梯度
            w = 1.0 / (1 + i * 0.4)
            self._spawn(value=f"v{i}", obs_w=w, qry_w=w)

    def _spawn(self, value: str, obs_w: float, qry_w: float,
               entity: int | None = None, scope: str = "",
               death: int | None = None, noise: bool = False,
               birth: int = 0) -> Belief:
        e = entity if entity is not None else self._next_entity
        if entity is None:
            self._next_entity += 1
        b = Belief(id=self._next_id, entity=e, scope=scope or f"s{self._next_id}",
                   birth=birth, value=value, obs_w=obs_w, qry_w=qry_w,
                   death=death, noise=noise)
        b.phrasings[value] = [f"b{b.id}:{b.scope}={value}#{j}" for j in range(4)]
        self.beliefs[b.id] = b
        self._next_id += 1
        return b

    # ---- ground truth 判据（替代 NLI / useful-hit 代理）----
    def judge(self, a_bid: int, a_val: str, b_bid: int, b_val: str) -> str:
        if a_bid == b_bid:
            return "synonym" if a_val == b_val else "update"
        if self.beliefs[a_bid].entity == self.beliefs[b_bid].entity:
            return "contradiction"
        return "collision"

    def embedding_key(self, belief_id: int, value: str) -> tuple:
        b = self.beliefs[belief_id]
        return b.entity, b.id, value

    def scope(self, belief_id: int) -> str:
        return self.beliefs[belief_id].scope

    def valid(self, belief_id: int, value: str, t: int) -> bool:
        b = self.beliefs[belief_id]
        return b.alive(t) and not b.noise and b.value == value

    def relevant(self, belief_id: int, value: str, query: Query, t: int) -> bool:
        return belief_id == query.target and self.valid(belief_id, value, t)

    def useful(self, belief_id: int, value: str, t: int) -> bool:
        return self.valid(belief_id, value, t)

    def phase(self, t: int) -> str:
        if t < self.t_drift:
            return "stable"
        if t < self.t_noise:
            return "drift"
        if t < self.noise_end:
            return "noise"
        return "conflict"

    # ---- 相位事件 ----
    def _phase_events(self, t: int):
        if t == self.t_drift:
            stable = [b for b in self.beliefs.values() if not b.noise]
            for b in stable[: self.n_drift]:
                newv = b.value + "'"
                b.phrasings[newv] = [p + "'" for p in b.phrasings[b.value]]
                b.value = newv
        if t == self.t_conflict:
            for _ in range(self.n_pairs):
                entity = self._next_entity
                self._next_entity += 1
                self._conflict_entities.append(entity)
                self._spawn("like", 1.0, 3.0, entity=entity, scope="work", birth=t)
        if t == self.t_conflict + self.conflict_gap:
            for entity in self._conflict_entities:
                self._spawn("dislike", 1.0, 3.0, entity=entity,
                            scope="casual", birth=t)

    def step(self, t: int) -> tuple[list[Event], list[Query]]:
        self._phase_events(t)
        events: list[Event] = []
        queries: list[Query] = []

        if self.t_noise <= t < self.noise_end:  # 一次性噪声 belief
            for _ in range(self.rng.poisson(self.noise_rate)):
                b = self._spawn(f"noise{t}", 1.0, 0.0, death=t + 1,
                                noise=True, birth=t)
                events.append(Event(b.id, b.value, b.phrasings[b.value][0]))

        for b in self.beliefs.values():
            if b.noise or not b.alive(t):
                continue
            if self.rng.random() < b.obs_w * 0.25:
                ph = b.phrasings[b.value]
                events.append(Event(b.id, b.value, ph[int(self.rng.integers(len(ph)))]))

        alive = [b for b in self.beliefs.values()
                 if b.alive(t) and not b.noise and b.qry_w > 0]
        if alive:
            w = np.array([b.qry_w for b in alive])
            w = w / w.sum()
            for i in self.rng.choice(len(alive),
                                     size=min(self.rng.poisson(self.query_rate), len(alive)),
                                     replace=False, p=w):
                b = alive[int(i)]
                queries.append(Query(b.id, f"what is b{b.id}:{b.scope} now?"))
        return events, queries
