"""Embedder 协议与相似度工具。"""
from __future__ import annotations

from typing import Protocol

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(a @ b / (na * nb))


class Embedder(Protocol):
    def embed(self, texts: list[str], keys: list | None = None) -> np.ndarray: ...
