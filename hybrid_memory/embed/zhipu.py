"""智谱 embedding-3 零依赖 REST adapter（标准库 urllib），带 SQLite chunk 缓存。"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

from .base import Embedder
from .cache import SqliteEmbeddingCache


class ZhipuEmbeddingError(RuntimeError):
    pass


class ZhipuEmbedder(Embedder):
    ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/embeddings"
    _DIMENSIONS = (256, 512, 1024, 2048)

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "embedding-3",
        dimensions: int = 2048,
        batch_size: int = 64,
        max_chars: int = 2000,
        timeout: float = 60.0,
        max_retries: int = 2,
        cache: SqliteEmbeddingCache | None = None,
        offline: bool = False,
        http_post: Callable[[Request, float], bytes] | None = None,
    ):
        if dimensions not in self._DIMENSIONS:
            raise ValueError(f"dimensions must be one of {self._DIMENSIONS}")
        if not 1 <= batch_size <= 64:
            raise ValueError("batch_size must be in 1..64")
        if max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_chars = max_chars
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache = cache
        self.offline = offline
        self._http_post = http_post if http_post is not None else self._default_post
        self.last_prompt_tokens = 0
        if api_key is None:
            api_key = os.environ.get("ZAI_API_KEY", "")
        if not api_key and http_post is None and not offline:
            raise RuntimeError("ZAI_API_KEY is not set")
        self._api_key = api_key

    def embed(self, texts: list[str], keys: list | None = None) -> np.ndarray:
        self.last_prompt_tokens = 0
        dim = self.dimensions
        if not texts:
            return np.zeros((0, dim), dtype=np.float32)
        for text in texts:
            if not isinstance(text, str) or not text:
                raise ValueError("each text must be a non-empty string")

        chunks: list[str] = []
        spans: list[tuple[int, int]] = []
        for i, text in enumerate(texts):
            for start in range(0, len(text), self.max_chars):
                chunk = text[start:start + self.max_chars]
                chunks.append(chunk)
                spans.append((i, len(chunk)))

        vectors: list[np.ndarray | None] = [None] * len(chunks)
        key_to_indices: dict[str, list[int]] = {}
        for idx, chunk in enumerate(chunks):
            key = self._cache_key(chunk)
            hit = self.cache.get(key) if self.cache is not None else None
            if hit is not None:
                norm = np.linalg.norm(hit)
                if (hit.shape == (dim,) and np.isfinite(hit).all() and norm > 0):
                    vectors[idx] = (hit / norm).astype(np.float32)
                else:
                    hit = None
            if hit is None:
                key_to_indices.setdefault(key, []).append(idx)

        pending = [(key, chunks[idxs[0]])
                   for key, idxs in key_to_indices.items()]
        if pending and self.offline:
            raise ZhipuEmbeddingError("embedding cache miss in offline mode")
        for start in range(0, len(pending), self.batch_size):
            batch = pending[start:start + self.batch_size]
            body = json.dumps({"model": self.model,
                               "input": [chunk for _, chunk in batch],
                               "dimensions": dim}).encode("utf-8")
            parsed = self._request(body, len(batch))
            for (key, _), vec in zip(batch, parsed):
                if self.cache is not None:
                    self.cache.put(key, vec)
                for idx in key_to_indices[key]:
                    vectors[idx] = vec

        out = np.zeros((len(texts), dim), dtype=np.float64)
        for (text_idx, length), vec in zip(spans, vectors):
            out[text_idx] += length * vec
        out /= np.linalg.norm(out, axis=1)[:, None]
        return out.astype(np.float32)

    def _cache_key(self, text: str) -> str:
        raw = f"{self.model}\0{self.dimensions}\0{text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _default_post(self, request: Request, timeout: float) -> bytes:
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    def _request(self, body: bytes, n: int) -> list[np.ndarray]:
        request = Request(self.ENDPOINT, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        })
        raw = b""
        for attempt in range(self.max_retries + 1):
            try:
                raw = self._http_post(request, self.timeout)
                break
            except HTTPError as exc:
                status = exc.code
                retryable = status == 429 or status >= 500
                if retryable and attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise ZhipuEmbeddingError(f"HTTP {status}") from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise ZhipuEmbeddingError(
                    f"transport error: {type(exc).__name__}") from exc
        return self._parse(raw, n)

    def _parse(self, raw: bytes, n: int) -> list[np.ndarray]:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ZhipuEmbeddingError("invalid JSON response") from exc
        if not isinstance(payload, dict):
            raise ZhipuEmbeddingError("invalid response payload")
        usage = payload.get("usage")
        if isinstance(usage, dict):
            tokens = usage.get("prompt_tokens")
            if isinstance(tokens, (int, float)):
                self.last_prompt_tokens += int(tokens)
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != n:
            raise ZhipuEmbeddingError("invalid response data")
        seen: set[int] = set()
        items: list[tuple[int, np.ndarray]] = []
        for entry in data:
            if not isinstance(entry, dict):
                raise ZhipuEmbeddingError("invalid data item")
            index = entry.get("index")
            embedding = entry.get("embedding")
            if not isinstance(index, int) or index in seen:
                raise ZhipuEmbeddingError("invalid data index")
            seen.add(index)
            if not isinstance(embedding, list):
                raise ZhipuEmbeddingError("invalid embedding")
            try:
                vec = np.asarray(embedding, dtype=np.float64)
            except (TypeError, ValueError) as exc:
                raise ZhipuEmbeddingError("invalid embedding") from exc
            if vec.shape != (self.dimensions,):
                raise ZhipuEmbeddingError("invalid embedding dimensions")
            if not np.isfinite(vec).all():
                raise ZhipuEmbeddingError("non-finite embedding")
            norm = np.linalg.norm(vec)
            if norm == 0:
                raise ZhipuEmbeddingError("zero embedding")
            items.append((index, (vec / norm).astype(np.float32)))
        if seen != set(range(n)):
            raise ZhipuEmbeddingError("non-contiguous data index")
        items.sort(key=lambda item: item[0])
        return [vec for _, vec in items]
