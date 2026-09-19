"""sidecar 服务测试：端点逻辑、HTTP 往返、状态持久化。全程无网络。"""
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.candgen.base import CandidateGeneration, MemoryCandidate
from hybrid_memory.config import Cfg
from hybrid_memory.server import MemoryService, serve
from hybrid_memory.semantics import RealChatSemantics


class _TableEmbedder:
    def __init__(self, table, default=None):
        self.table = table
        self.default = default if default is not None else np.array([0.0, 1.0])

    def embed(self, texts, keys=None):
        return np.array([self.table.get(t, self.default) for t in texts],
                        dtype=np.float32)


class _FixedGenerator:
    def __init__(self, texts):
        self.texts = texts
        self.calls = 0

    def generate(self, window, prev_scene=""):
        self.calls += 1
        return CandidateGeneration(
            candidates=tuple(MemoryCandidate(text=t) for t in self.texts),
            scene_name="测试场景")


def _service(tmp_path=None, texts=("部署在 B 服务器",)):
    emb = _TableEmbedder({"部署在哪": np.array([1.0, 0.0]),
                          "部署在 B 服务器": np.array([0.99, 0.14])})
    cfg = Cfg(theta=0.35, suppression_on=False, defer_credit=True,
              useful_hit=True)
    svc = MemoryService(cfg, emb, RealChatSemantics(None),
                        _FixedGenerator(list(texts)), state_dir=tmp_path)
    return svc


def test_observe_ingests_candidates():
    svc = _service()
    out = svc.observe("部署在哪", "已改到 B 服务器")
    assert out["candidates"] == 1 and out["scene"] == "测试场景"
    assert svc.engine.pool_sizes()["C"] == 1
    assert svc._t == 1


def test_recall_returns_context_and_registry():
    svc = _service()
    svc.observe("部署在哪", "已改到 B 服务器")
    out = svc.recall("部署在哪")
    assert isinstance(out["retrieval_id"], int)
    assert "部署在 B 服务器" in out["context"]
    assert out["selected"][0]["text"] == "部署在 B 服务器"


def test_feedback_credits_and_guards_double_call():
    svc = _service()
    svc.observe("部署在哪", "已改到 B 服务器")
    rid = svc.recall("部署在哪")["retrieval_id"]
    assert svc.feedback(rid, "部署在哪", "在 B")["n_useful"] == 1
    with pytest.raises(RuntimeError):       # 双计防护穿过服务层
        svc.feedback(rid, "部署在哪", "在 B")


def test_conflicts_and_resolve():
    svc = _service()
    svc.observe("部署在哪", "已改到 B 服务器")
    svc.engine.add_tension(0, 1, 0)
    svc.engine.mems[1] = type(svc.engine.mems[0])(
        id=1, belief_id=svc.engine.mems[0].belief_id, value="v2",
        text="部署在 C 服务器", emb=np.array([0.0, 1.0], dtype=np.float32),
        birth=1)
    out = svc.conflicts()
    assert out["conflicts"][0]["left"] == 0
    assert svc.resolve(0, 1, "update")["resolved"] == 1
    assert svc.conflicts()["conflicts"] == []


def test_state_persists_across_restart(tmp_path):
    svc = _service(tmp_path)
    svc.observe("部署在哪", "已改到 B 服务器")
    assert svc.save()["saved"]
    assert (tmp_path / "state.pkl").exists()

    emb2 = _TableEmbedder({})
    cfg2 = Cfg(theta=0.35, suppression_on=False, defer_credit=True,
               useful_hit=True)
    svc2 = MemoryService(cfg2, emb2, RealChatSemantics(None),
                         _FixedGenerator([]), state_dir=tmp_path)
    assert len(svc2.engine.mems) == 1
    assert svc2._t == 1 and svc2._unit_id == 1
    assert svc2.engine.mems[0].text == "部署在 B 服务器"


def test_http_roundtrip(tmp_path):
    svc = _service(tmp_path)
    httpd = serve(svc, 0)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def post(path, obj):
        req = urllib.request.Request(
            base + path, data=json.dumps(obj).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        assert get("/health")["ok"] is True
        out = post("/observe", {"user_text": "部署在哪",
                                "assistant_text": "已改到 B 服务器"})
        assert out["candidates"] == 1
        rec = get("/recall?q=%E9%83%A8%E7%BD%B2%E5%9C%A8%E5%93%AA")
        assert "部署在 B 服务器" in rec["context"]
        assert post("/save", {})["saved"] is True
    finally:
        httpd.shutdown()
        httpd.server_close()
