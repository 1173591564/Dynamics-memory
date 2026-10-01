"""Zhipu embedding-3 adapter / SQLite 缓存 / 对话窗口加载器测试。全程无网络。"""
import json
import math
import os
import sqlite3
import tempfile
from http.client import RemoteDisconnected
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import numpy as np


from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder, ZhipuEmbeddingError


def one_hot(pos: int, dims: int, scale: float = 1.0) -> list[float]:
    vec = [0.0] * dims
    vec[pos] = scale
    return vec


def respond(request, vectors) -> bytes:
    payload = json.loads(request.data.decode("utf-8"))
    dims = payload["dimensions"]
    data = [{"index": i, "embedding": vectors(text, dims)}
            for i, text in enumerate(payload["input"])]
    return json.dumps({"data": data,
                       "usage": {"prompt_tokens": len(payload["input"])}}
                      ).encode("utf-8")


def expect(exc_type, fn, contains: str = "") -> None:
    try:
        fn()
    except exc_type as exc:
        assert contains in str(exc)
    else:
        raise AssertionError(f"expected {exc_type.__name__}")


def test_missing_key_fails_without_transport():
    with patch.dict(os.environ, {"ZAI_API_KEY": ""}):
        expect(RuntimeError, ZhipuEmbedder, "ZAI_API_KEY")


def test_response_order_normalization_and_batching():
    texts = ["alpha", "beta", "gamma"]
    calls = []

    def post(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(len(payload["input"]))
        dims = payload["dimensions"]
        data = [{"index": i, "embedding": one_hot(texts.index(text), dims)}
                for i, text in enumerate(payload["input"])]
        data.reverse()
        return json.dumps({"data": data,
                           "usage": {"prompt_tokens": 7}}).encode("utf-8")

    emb = ZhipuEmbedder(dimensions=256, batch_size=2, http_post=post)
    out = emb.embed(texts)
    assert calls == [2, 1]
    assert out.shape == (3, 256)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    for i, row in enumerate(out):
        assert np.count_nonzero(row) == 1
        assert row[i] == 1.0
    assert emb.last_prompt_tokens == 14


def test_chunk_weighted_merge():
    def post(request, timeout):
        return respond(request,
                       lambda text, dims: one_hot(0 if text == "abc" else 1, dims))

    emb = ZhipuEmbedder(dimensions=256, max_chars=3, http_post=post)
    out = emb.embed(["abcdef"])
    assert out.shape == (1, 256)
    inv = 1.0 / math.sqrt(2)
    assert abs(out[0, 0] - inv) < 1e-6
    assert abs(out[0, 1] - inv) < 1e-6


def test_sqlite_cache_avoids_second_request():
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "emb.sqlite"
        calls = []

        def post(request, timeout):
            calls.append(1)
            return respond(request, lambda text, dims: one_hot(0, dims))

        first = ZhipuEmbedder(dimensions=256,
                              cache=SqliteEmbeddingCache(cache_path),
                              http_post=post)
        v1 = first.embed(["hello"])
        assert calls == [1]

        second = ZhipuEmbedder(dimensions=256,
                               cache=SqliteEmbeddingCache(cache_path),
                               offline=True)
        v2 = second.embed(["hello"])
        assert np.array_equal(v1, v2)
        expect(ZhipuEmbeddingError, lambda: second.embed(["new text"]),
               "offline mode")

        conn = sqlite3.connect(str(cache_path))
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(embeddings)")]
            assert cols == ["cache_key", "dimensions", "vector"]
            count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            assert count == 1
        finally:
            conn.close()


def test_invalid_response_rejected():
    def post(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        dims = payload["dimensions"]
        data = [{"index": 0, "embedding": one_hot(0, dims)}
                for _ in payload["input"]]
        return json.dumps({"data": data}).encode("utf-8")

    emb = ZhipuEmbedder(dimensions=256, http_post=post)
    expect(ZhipuEmbeddingError, lambda: emb.embed(["a", "b"]))


def test_retry_only_retryable_http_statuses():
    retry_calls = []

    def retry_post(request, timeout):
        retry_calls.append(1)
        if len(retry_calls) == 1:
            raise HTTPError(request.full_url, 429, "rate limit", None, None)
        return respond(request, lambda text, dims: one_hot(0, dims))

    with patch("hybrid_memory.embed.zhipu.time.sleep"):
        out = ZhipuEmbedder(dimensions=256, max_retries=1,
                            http_post=retry_post).embed(["retry"])
    assert retry_calls == [1, 1]
    assert out.shape == (1, 256)

    bad_calls = []

    def bad_post(request, timeout):
        bad_calls.append(1)
        raise HTTPError(request.full_url, 400, "bad request", None, None)

    emb = ZhipuEmbedder(dimensions=256, max_retries=2, http_post=bad_post)
    expect(ZhipuEmbeddingError, lambda: emb.embed(["bad"]), "HTTP 400")
    assert bad_calls == [1]


def test_chat_retries_remote_disconnected():
    from hybrid_memory.llm import ZhipuChatError, chat

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}]}).encode()

    calls = []

    def flaky(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise RemoteDisconnected("dropped")
        return Resp()

    with patch("hybrid_memory.llm.urlopen", side_effect=flaky), \
            patch("hybrid_memory.llm.time.sleep"):
        out = chat(api_key="test-key", system="s", user="u", max_retries=2)
    assert calls == [1, 1]
    assert out == "ok"

    calls.clear()
    with patch("hybrid_memory.llm.urlopen", side_effect=flaky), \
            patch("hybrid_memory.llm.time.sleep"):
        expect(ZhipuChatError,
               lambda: chat(api_key="test-key", system="s", user="u",
                            max_retries=0),
               "transport: RemoteDisconnected")
    assert calls == [1]


def test_extreme_embeddings_are_finite_unit_vectors_and_cancelled_chunks_fail(tmp_path):
    cache = SqliteEmbeddingCache(tmp_path / "emb.sqlite")
    for scale in (1e308, 1e-320):
        emb = ZhipuEmbedder(dimensions=256, http_post=lambda req, _: respond(
            req, lambda text, dims: one_hot(0, dims, scale)))
        assert emb.embed(["x"])[0, 0] == 1
    offline = ZhipuEmbedder(dimensions=256, cache=cache, offline=True)
    cache.put(offline._cache_key("x"), np.array(one_hot(0, 256, 1e38), dtype=np.float32))
    assert offline.embed(["x"])[0, 0] == 1
    emb = ZhipuEmbedder(dimensions=256, max_chars=1, http_post=lambda req, _: respond(
        req, lambda text, dims: one_hot(0, dims, 1 if text == "a" else -1)))
    expect(ZhipuEmbeddingError, lambda: emb.embed(["ab"]), "zero embedding")


def test_malformed_chat_response_uses_transport_error_contract():
    from hybrid_memory.llm import ZhipuChatError, chat
    from io import BytesIO
    for content in (None, 1, [], {}):
        raw = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        with patch("hybrid_memory.llm.urlopen", return_value=BytesIO(raw)):
            expect(ZhipuChatError, lambda: chat(api_key="test", max_retries=0), "invalid chat response")


def test_invalid_chat_cache_is_miss_and_failed_replace_keeps_previous(tmp_path, monkeypatch):
    import pytest
    from hybrid_memory import llm
    for broken in ('{"out":', '[]', 'null', '{"out":4}'):
        (tmp_path / "key.json").write_text(broken)
        assert llm._cache_lookup(tmp_path, "key") is None
    llm._cache_store(tmp_path, "key", "ok")
    def fail(*_):
        raise OSError("replace failed")
    monkeypatch.setattr(llm.os, "replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        llm._cache_store(tmp_path, "key", "new")
    assert llm._cache_lookup(tmp_path, "key") == "ok"
    assert not list(tmp_path.glob("*.tmp"))
