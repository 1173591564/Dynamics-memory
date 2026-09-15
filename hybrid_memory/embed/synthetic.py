"""合成 embedder：把相似度结构捏在手里。

entity 中心（共享） → belief 偏移（同实体异 scope 的高相似对）
→ value 偏移 → 观测/query 加噪。

- 同 (belief, value)：高余弦（τ_dup 区，dedup 目标）
- 同 entity 异 belief（矛盾对）：τ_dup 带附近（压制目标）
- 异 entity：低相似（噪声）
"""
from __future__ import annotations

import numpy as np

from .base import Embedder


class SyntheticEmbedder(Embedder):
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
