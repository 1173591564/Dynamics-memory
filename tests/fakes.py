"""引擎单测夹具：确定性的假世界（MemorySemantics）+ 可控相似度的合成嵌入。

只提供 belief 登记表与真值谓词，没有流生成器、相位、随机查询——
这里不是评测，评测在独立的 TIDE 平台。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hybrid_memory.core.types import Event, Query
from hybrid_memory.embed.base import Embedder


@dataclass
class Belief:
    id: int
    entity: int
    scope: str
    birth: int
    value: str
    death: int | None = None
    noise: bool = False
    phrasings: dict = field(default_factory=dict)  # value -> [phrasings]

    def alive(self, t: int) -> bool:
        return self.birth <= t and (self.death is None or t < self.death)


class FakeWorld:
    """预置 n 个互不相关的 belief（v0..v{n-1}）；其余按用例 spawn。"""

    def __init__(self, n: int = 20):
        self.beliefs: dict[int, Belief] = {}
        self._next_id = 0
        self._next_entity = 0
        for i in range(n):
            self.spawn(f"v{i}")

    def spawn(self, value: str, *, entity: int | None = None, scope: str = "",
              birth: int = 0, death: int | None = None,
              noise: bool = False) -> Belief:
        e = entity if entity is not None else self._next_entity
        if entity is None:
            self._next_entity += 1
        b = Belief(id=self._next_id, entity=e, scope=scope or f"s{self._next_id}",
                   birth=birth, value=value, death=death, noise=noise)
        b.phrasings[value] = [f"b{b.id}:{b.scope}={value}#{j}" for j in range(4)]
        self.beliefs[b.id] = b
        self._next_id += 1
        return b

    def set_value(self, belief_id: int, value: str) -> None:
        """belief 换值（旧措辞加撇号派生新措辞）。"""
        b = self.beliefs[belief_id]
        b.phrasings[value] = [p + "'" for p in b.phrasings[b.value]]
        b.value = value

    def event(self, belief_id: int, j: int = 0) -> Event:
        b = self.beliefs[belief_id]
        return Event(b.id, b.value, b.phrasings[b.value][j])

    def query(self, belief_id: int) -> Query:
        b = self.beliefs[belief_id]
        return Query(b.id, f"what is b{b.id}:{b.scope} now?")

    # ---- MemorySemantics ----
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


class SyntheticEmbedder(Embedder):
    """把相似度结构捏在手里：entity 中心 → belief 偏移（同实体异 scope 的高相似对）
    → value 偏移 → 观测加噪。同 (belief, value) 高余弦（dedup 区）；同 entity
    异 belief 在 τ_dup 带附近（压制区）；异 entity 低相似。"""

    def __init__(self, dim: int = 64, scope_off: float = 0.12,
                 value_off: float = 0.06, noise: float = 0.15, seed: int = 0):
        self.dim = dim
        self.scope_off = scope_off
        self.value_off = value_off
        self.noise = noise
        self._rng = np.random.default_rng(seed)
        self._entity: dict = {}
        self._belief: dict = {}
        self._value: dict = {}

    def _unit(self) -> np.ndarray:
        g = self._rng.standard_normal(self.dim)
        return g / np.linalg.norm(g)

    def _center(self, cache: dict, key, scale: float, base=None) -> np.ndarray:
        if key not in cache:
            v = self._unit() if base is None else base + scale * self._unit()
            cache[key] = v / np.linalg.norm(v)
        return cache[key]

    def vec_for(self, entity_id: int, belief_id: int, value: str) -> np.ndarray:
        e = self._center(self._entity, ("e", entity_id), 0)
        b = self._center(self._belief, ("b", belief_id), self.scope_off, e)
        v = self._center(self._value, ("v", belief_id, value), self.value_off, b)
        obs = v + self.noise * self._unit()
        return obs / np.linalg.norm(obs)

    def embed(self, texts: list[str], keys: list | None = None) -> np.ndarray:
        if keys is None:
            return np.stack([self._center({}, ("t", t), 0) for t in texts])
        return np.stack([self.vec_for(*k) for k in keys])
