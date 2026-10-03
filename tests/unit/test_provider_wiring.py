"""SemanticsProvider 接线回归（P0-1.5 / H27/N15/N22）。

覆盖：
- provider 完整委托 MemorySemantics 写路径方法（embedding_key/valid/
  relevant/scope/fingerprint），引擎写路径不再 AttributeError；
- 缺失语义能力（delegate 无 relevant_set/consolidate）→ 返回 None 且
  不计失败（能力缺失不是错误）；
- delegate 缺 MemorySemantics 基本方法 → 构造即拒绝（运行时检查）；
- worker 语义路径解包 .delegate：isinstance 判定与调用都正确；judge 经
  provider 计数（降级可观测）；
- bootstrap 构建真实 provider（生产接线点）；
- health_view 增加 semantic_provider 段（A7 字段只增）。
"""
from __future__ import annotations

import pytest

from hybrid_memory.core.types import Event, Memory, Pool
from hybrid_memory.semantics.llm import LLMSemantics
from hybrid_memory.semantics.provider import SemanticsProvider
from hybrid_memory.semantics.real import RealChatSemantics
from test_ouroboros import _svc


class _FakeDelegate:
    """实现全部能力的假语义（可注入故障）。"""

    def __init__(self):
        self.judge_calls = 0
        self.relevant_calls = 0
        self.embedding_key_calls = 0
        self.valid_calls = 0
        self.fail_judge = False
        self.fail_relevant = False

    def fingerprint(self, text):
        return hash(text) % (2 ** 31)

    def scope(self, belief_id):
        return "project"

    def judge(self, a_bid, a_val, b_bid, b_val):
        self.judge_calls += 1
        if self.fail_judge:
            raise RuntimeError("judge down")
        return "synonym"

    def relevant(self, belief_id, value, query, t):
        self.relevant_calls += 1
        return True

    def valid(self, belief_id, value, t):
        self.valid_calls += 1
        return True

    def embedding_key(self, belief_id, value):
        self.embedding_key_calls += 1
        return (0, belief_id, value)

    def relevant_set(self, texts, question, answer):
        if self.fail_relevant:
            raise RuntimeError("recognizer down")
        return [True] + [False] * (len(texts) - 1)

    def consolidate(self, memories, t):
        return Event(1, "reflection", "巩固产物", tuple(m.id for m in memories),
                     kind="reflection")


class _BareDelegate:
    """只有 MemorySemantics 基本方法（无 relevant_set/consolidate）。"""

    def fingerprint(self, text):
        return 0

    def scope(self, belief_id):
        return "project"

    def judge(self, a_bid, a_val, b_bid, b_val):
        return "pending"

    def relevant(self, belief_id, value, query, t):
        return True

    def valid(self, belief_id, value, t):
        return True

    def embedding_key(self, belief_id, value):
        return (0, belief_id, value)


def test_provider_delegates_memory_semantics_write_path():
    d = _FakeDelegate()
    p = SemanticsProvider(d)
    assert p.embedding_key(1, "v") == (0, 1, "v")
    assert d.embedding_key_calls == 1
    assert p.valid(1, "v", 0) is True
    assert d.valid_calls == 1
    q = type("Q", (), {"target": 1, "text": "q"})()
    assert p.relevant(1, "v", q, 0) is True
    assert d.relevant_calls == 1
    assert p.scope(1) == "project"
    assert p.fingerprint("x") == d.fingerprint("x")


def test_provider_missing_capability_returns_none_without_failure():
    p = SemanticsProvider(_BareDelegate())
    assert p.relevant_set(["a"], "q", "ans") is None
    assert p.consolidate([], 0) is None
    h = p.health()
    assert h["calls"] == 0 and h["failures"] == 0, "能力缺失不是错误"


def test_provider_counts_judge_degradation():
    d = _FakeDelegate()
    p = SemanticsProvider(d)
    assert p.judge(1, "a", 2, "b") == "synonym"
    d.fail_judge = True
    assert p.judge(1, "a", 2, "b") == "pending", "异常降级 pending"
    h = p.health()
    assert h["calls"] == 2 and h["failures"] == 1
    assert "judge down" in h["last_error"]


def test_provider_rejects_delegate_without_memory_semantics():
    class _Broken:
        pass
    with pytest.raises(ValueError):
        SemanticsProvider(_Broken())


def test_worker_unwraps_provider_for_semantic_tasks(tmp_path):
    svc = _svc(tmp_path, consolidation_min_items=1)
    svc.trio_mode = True
    d = _FakeDelegate()
    p = SemanticsProvider(d)
    svc.semantics = p
    svc.engine.semantics = p
    try:
        # conflict：经 provider 计数 judge
        eng = svc.engine
        import numpy as np
        eng.mems[0] = Memory(id=0, belief_id=1, value="v0", text="甲",
                             emb=np.zeros(64), pool=Pool.CANDIDATE, v=0.5,
                             birth=0, last_seen=0)
        eng.mems[1] = Memory(id=1, belief_id=2, value="v1", text="乙",
                             emb=np.zeros(64), pool=Pool.CANDIDATE, v=0.5,
                             birth=0, last_seen=0)
        eng._next_id = 2
        eng.add_tension(0, 1, 0)
        eng.tensions[(0, 1)].verdicts = []   # 未裁决张力才派生 conflict 任务
        svc.tasks.enqueue("conflict_pending", [[0, 1]], 0)
        stats = svc.process_semantic_tasks()
        assert stats["judged"] == 1
        assert d.judge_calls == 1
        assert p.health()["calls"] >= 1, "judge 经 provider，降级可观测"

        # feedback：recognizer 生效（不再是全 True 兜底）
        from hybrid_memory.core.types import Retrieval
        eng.mems[2] = Memory(id=2, belief_id=3, value="v2", text="答案相关",
                             emb=np.zeros(64), pool=Pool.CANDIDATE, v=0.5,
                             birth=0, last_seen=0)
        eng._next_id = 3
        svc._retrievals[7] = Retrieval(selected=[eng.mems[2]],
                                       presented_texts=("答案相关",))
        from hybrid_memory.dispatch.worker import semantic_model
        result = semantic_model(svc, {
            "kind": "feedback_pending",
            "payload": {"retrieval_id": 7, "texts": ["答案相关"],
                        "selected": [2], "question": "q", "answer": "答案相关"},
            "t": 0, "result": None})
        assert result["used"] == [True], "recognizer 结果穿透包装"
        assert result["recog_fail"] is False

        # maintenance：consolidate 生效（BareDelegate 会跳过，Fake 走真分支）
        mems_src = [2]
        from hybrid_memory.dispatch.worker import semantic_model as _sm
        result2 = _sm(svc, {
            "kind": "maintenance_due", "payload": {"scene": "s", "ids": mems_src},
            "t": 1, "result": None})
        assert result2["event"] is not None, "consolidate 穿透包装"
        assert result2["event"]["text"] == "巩固产物"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_bootstrap_builds_real_provider(tmp_path):
    import os
    (tmp_path / ".env").write_text("ZAI_API_KEY=test-key-not-real\n",
                                   encoding="utf-8")
    old = os.environ.pop("ZAI_API_KEY", None)
    try:
        from hybrid_memory.transport.bootstrap import build_default_service
        svc = build_default_service(tmp_path, embed_log=False)
        try:
            assert isinstance(svc.semantics, SemanticsProvider)
            assert isinstance(svc.semantics.delegate, LLMSemantics)
            assert svc.engine.semantics is svc.semantics
            # 写路径委托可用（不触网）
            assert svc.semantics.embedding_key(1, "v") is not None
        finally:
            svc.tasks.close()
            svc.log.close()
    finally:
        if old is not None:
            os.environ["ZAI_API_KEY"] = old


def test_health_view_reports_provider_segment(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        from hybrid_memory import telemetry
        before = telemetry.health_view(svc)
        assert "semantic_provider" in before, "A7：health 只增字段"
        assert before["semantic_provider"] is None, "无 provider 时为 None"
        p = SemanticsProvider(_FakeDelegate())
        svc.semantics = p
        p.judge(1, "a", 2, "b")
        after = telemetry.health_view(svc)
        assert after["semantic_provider"]["calls"] == 1
    finally:
        svc.tasks.close()
        svc.log.close()
