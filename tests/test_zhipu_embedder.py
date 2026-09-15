"""Zhipu embedding-3 adapter / SQLite 缓存 / 对话窗口加载器测试。全程无网络。"""
import json
import math
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.real_embedding import evaluate, load_dotenv_key
from hybrid_memory.datasets.real_chat import (InteractionUnit,
                                              build_interaction_windows,
                                              load_interaction_units)
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


def test_evaluate_known_retrieval_ranks():
    perfect = np.eye(3, dtype=np.float32)
    summary, rows = evaluate(perfect, perfect)
    assert summary["units"] == 3
    assert summary["recall_at_1"] == 1.0
    assert summary["mrr"] == 1.0
    assert [row["rank"] for row in rows] == [1, 1, 1]

    swapped = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    summary, rows = evaluate(np.eye(2, dtype=np.float32), swapped)
    assert summary["units"] == 2
    assert summary["recall_at_1"] == 0.0
    assert summary["recall_at_5"] == 1.0
    assert summary["mrr"] == 0.5
    assert [row["rank"] for row in rows] == [2, 2]
    assert [row["hard_negative_id"] for row in rows] == [1, 0]
    assert all(row["margin"] == -1.0 for row in rows)


def test_load_dotenv_key_without_disclosure():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ".env"
        path.write_text("IGNORED=x\nexport ZAI_API_KEY='dummy-test-key'\n", encoding="utf-8")
        assert load_dotenv_key(path) == "dummy-test-key"
        path.write_text("ZAI_API_KEY=a\nZAI_API_KEY=b\n", encoding="utf-8")
        expect(RuntimeError, lambda: load_dotenv_key(path), "duplicate ZAI_API_KEY")


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


def test_real_chat_loader_groups_assistant_turns():
    rows = [
        {"role": "user", "time": 10, "text": "q1"},
        {"role": "assistant", "time": 11, "text": "a1"},
        {"role": "assistant", "time": 11.5, "text": ""},
        {"role": "assistant", "time": 12, "text": "a2"},
        {"role": "user", "time": 20, "text": "q2"},
        {"role": "assistant", "time": 21, "text": "a3"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "chat.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        units = load_interaction_units(path)
    assert len(units) == 2
    first, second = units
    assert first.id == 0
    assert first.start_time == 10 and first.end_time == 12
    assert first.user_text == "q1"
    assert first.assistant_text == "a1\n\na2"
    assert first.assistant_turns == 2
    assert second.id == 1
    assert second.start_time == 20 and second.end_time == 21
    assert second.user_text == "q2"
    assert second.assistant_text == "a3"
    assert second.assistant_turns == 1


def test_build_interaction_windows_exact_k_and_stride():
    units = [InteractionUnit(id=i, start_time=i * 10, end_time=i * 10 + 5,
                             user_text=f"u{i}", assistant_text=f"a{i}",
                             assistant_turns=1)
             for i in range(5)]
    windows = build_interaction_windows(units, size=3, stride=1)
    assert len(windows) == 3
    assert [u.id for u in windows[0].units] == [0, 1, 2]
    assert windows[0].start_unit_id == 0 and windows[0].end_unit_id == 2
    assert [u.id for u in windows[-1].units] == [2, 3, 4]
    windows = build_interaction_windows(units, size=2, stride=2)
    assert len(windows) == 2
    assert [u.id for u in windows[-1].units] == [2, 3]
    assert not build_interaction_windows(units, size=6, stride=1)
    expect(ValueError, lambda: build_interaction_windows(units, 0, 1))
    expect(ValueError, lambda: build_interaction_windows(units, 1, 0))


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


def test_real_chat_loader_rejects_invalid_row():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.jsonl"
        path.write_text(json.dumps({"role": "user", "time": 1}),
                        encoding="utf-8")
        expect(ValueError, lambda: load_interaction_units(path),
               "invalid row 1")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"{f.__name__} ok")
    print("all zhipu embedder tests passed")
