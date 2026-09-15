"""all-MiniLM-L6-v2 实现（可选依赖，装了 sentence-transformers 才可用）。"""
from __future__ import annotations

import numpy as np

from .base import Embedder


class MiniLMEmbedder(Embedder):
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self._m = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, texts: list[str], keys: list | None = None) -> np.ndarray:
        return np.asarray(self._m.encode(texts, normalize_embeddings=True))
