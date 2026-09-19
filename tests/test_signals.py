"""信号层（P1 影子模式）测试：发射点、队列有界/合并、操作面等价性。"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.signals import SignalQueue
from hybrid_memory.core.types import Event, Memory, Pool, Query
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen


def make(seed=0, cfg=None):
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed)
    return emb, world, MemoryEngine(cfg or Cfg(), emb, world)


class _Judge:
    """judge 固定 verdict（或 fail=True 被调即炸），其余委托 StreamGen。"""

    def __init__(self, inner, verdict="synonym", fail=False):
        self._inner = inner
        self._verdict = verdict
        self._fail = fail

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def judge(self, *args):
        if self._fail:
            raise AssertionError("defer 模式下不应调用 judge")
        return self._verdict


def _suppression_setup(cfg, verdict=None, fail=False):
    """构造压制场景：rival 先入选，m 与 rival 相似度 0.99 > tau_sim。
    verdict/fail 在检索前注入 judge stub。"""
    emb, world, eng = make(cfg=cfg)
    if verdict is not None or fail:
        eng.semantics = _Judge(world, verdict=verdict or "synonym",
                               fail=fail)
    b = world.beliefs[0]
    rival = Memory(0, b.id, b.value, "rival", np.array([1.0, 0.0]), v=0.6)
    m = Memory(1, b.id, b.value, "suppressed",
               np.array([0.99, math.sqrt(1 - 0.99 ** 2)]), v=0.5)
    eng.mems[0], eng.mems[1] = rival, m
    eng._next_id = 2
    ret = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    return eng, ret, rival, m


def test_queue_bound_and_drop_counter():
    q = SignalQueue(cap=3)
    for i in range(5):
        q.emit("feedback_pending", {"i": i}, t=i)
    assert len(q) == 3
    assert q.n_dropped == 2
    sigs = q.drain()
    assert [s.payload["i"] for s in sigs] == [2, 3, 4]   # 丢最旧
    assert len(q) == 0


def test_conflict_signal_coalesces_pairs():
    emb, world, eng = make()
    eng.add_tension(0, 1, 0)
    eng.add_tension(1, 2, 0)
    sigs = eng.drain_signals()
    assert [s.kind for s in sigs] == ["conflict_pending"]
    assert sigs[0].payload == [(0, 1), (1, 2)]
    # 同一对再次出现（observations++）不再发射
    eng.add_tension(0, 1, 1)
    assert eng.drain_signals() == []


def test_thin_recall_deduped_per_step():
    emb, world, eng = make()
    q = Query(-1, "anything")
    qv = emb.embed(["anything"])[0]
    eng.retrieve(qv, q, 0)
    eng.retrieve(qv, q, 0)
    eng.retrieve(qv, q, 1)
    kinds = [s.kind for s in eng.drain_signals()]
    assert kinds.count("thin_recall") == 2   # t=0 合并成一条，t=1 一条


def test_feedback_pending_emitted_only_under_defer():
    emb, world, eng = make(cfg=Cfg(defer_credit=True))
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(b.entity, b.id, b.value),
                       Query(b.id, "q"), 0)
    sigs = [s for s in eng.drain_signals() if s.kind == "feedback_pending"]
    assert len(sigs) == 1 and sigs[0].payload["retrieval"] is ret
    # defer 关闭：不发 feedback_pending
    emb2, world2, eng2 = make(cfg=Cfg(defer_credit=False))
    eng2.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    eng2.retrieve(emb2.vec_for(b.entity, b.id, b.value), Query(b.id, "q"), 0)
    assert not [s for s in eng2.drain_signals()
                if s.kind == "feedback_pending"]


def test_submit_relevance_matches_feedback_effects():
    emb, world, eng = make(cfg=Cfg(defer_credit=True, suppression_on=False))
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(b.entity, b.id, b.value),
                       Query(b.id, "q"), 0)
    n = eng.submit_relevance(ret, [True] * len(ret.selected), 0)
    assert n == 1
    assert ret.selected[0].hits == 1 and ret.selected[0].d_hit == 1.0
    assert ret.credited
    with pytest.raises(RuntimeError):
        eng.submit_relevance(ret, [True], 0)


def test_submit_verdicts_synonym_matches_sync_path():
    def _setup(seed):
        emb, world, eng = make(seed=seed, cfg=Cfg(tension_delay=0))
        b = world.beliefs[0]
        a = Memory(0, b.id, b.value, "a", np.array([1.0, 0.0]), v=0.6)
        bb = Memory(1, b.id, b.value, "b", np.array([0.0, 1.0]), v=0.4)
        eng.mems[0], eng.mems[1] = a, bb
        eng._next_id = 2
        eng.add_tension(0, 1, 0)
        return eng, a, bb

    eng_sync, a1, b1 = _setup(0)
    eng_sync.semantics = _Judge(eng_sync.semantics)
    eng_sync.step(0)
    eng_op, a2, b2 = _setup(0)
    n = eng_op.submit_verdicts([(0, 1, "synonym")], 0)

    assert n == 1
    for eng, a, b in ((eng_sync, a1, b1), (eng_op, a2, b2)):
        assert b.superseded_by == a.id and b.pool is Pool.ARCHIVE
        assert a.evid == 1 + 1
        assert eng.n_merge == 1 and eng.n_resolve == 1
        assert not eng.tensions


def test_submit_verdicts_pending_keeps_backlog():
    emb, world, eng = make(cfg=Cfg(tension_delay=0))
    b = world.beliefs[0]
    eng.mems[0] = Memory(0, b.id, b.value, "a", np.array([1.0, 0.0]))
    eng.mems[1] = Memory(1, b.id, b.value, "b", np.array([0.0, 1.0]))
    eng._next_id = 2
    eng.add_tension(0, 1, 0)
    n = eng.submit_verdicts([(0, 1, "pending")], 0)
    assert n == 0
    assert (0, 1) in eng.tensions and eng.n_resolve == 0


def test_submit_verdicts_stale_pair_dropped():
    emb, world, eng = make()
    eng.mems[0] = Memory(0, world.beliefs[0].id, world.beliefs[0].value,
                         "a", np.array([1.0, 0.0]))
    eng.add_tension(0, 1, 0)
    n = eng.submit_verdicts([(0, 1, "synonym")], 0)   # 1 不存在
    assert n == 0 and not eng.tensions


def test_maintenance_due_emitted_without_callback():
    cfg = Cfg(consolidation_on=True, consolidation_min_items=2,
              consolidation_salience_budget=1.0)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    for i in range(2):
        eng.mems[i] = Memory(i, b.id, b.value, f"m{i}",
                             np.array([1.0, 0.0]), salience=0.8, scene="s1")
    eng._next_id = 2
    eng._consolidation_pending = {0, 1}
    eng.step(0)   # StreamGen 无 consolidate 回调，信号仍应发射
    sigs = eng.drain_signals()
    assert [s.kind for s in sigs] == ["maintenance_due"]
    assert sigs[0].payload["scene"] == "s1"
    assert sorted(sigs[0].payload["ids"]) == [0, 1]


def test_add_reflection_admits_memory():
    emb, world, eng = make()
    b = world.beliefs[0]
    ev = Event(b.id, b.value, "scene 汇总：进行到 X")
    m = eng.add_reflection(ev, [], 0)
    assert m.kind == "reflection" and eng.mems[m.id] is m
    assert eng.n_consolidate == 1
    assert m.derived_from == ()


def test_shadow_sync_mode_credits_immediately():
    eng, ret, rival, m = _suppression_setup(Cfg(), verdict="update")
    assert m.d_shadow == 1.0 and m.last_hit == 0      # 同步模式即时记账
    assert eng._shadow_pending == []
    assert (0, 1) in eng.tensions


def test_shadow_defer_records_without_judge():
    eng, ret, rival, m = _suppression_setup(
        Cfg(shadow_defer=True), fail=True)            # judge 被调即炸
    assert m.d_shadow == 0.0                          # 未结算
    assert len(eng._shadow_pending) == 1
    key, mid, t_ret, rel = eng._shadow_pending[0]
    assert key == (0, 1) and mid == 1 and t_ret == 0 and rel
    assert eng.tensions                              # backlog 照常


def test_shadow_defer_settles_on_update_verdict():
    eng, ret, rival, m = _suppression_setup(Cfg(shadow_defer=True))
    n = eng.submit_verdicts([(1, 0, "update")], 5)
    assert n == 1 and eng._shadow_pending == []
    assert m.d_shadow == 1.0 and m.last_hit == 0      # 结算用检索时刻
    assert m.superseded_by == 0 and m.pool is Pool.ARCHIVE


def test_shadow_defer_synonym_no_credit():
    eng, ret, rival, m = _suppression_setup(Cfg(shadow_defer=True))
    eng.submit_verdicts([(1, 0, "synonym")], 5)
    assert m.d_shadow == 0.0 and eng._shadow_pending == []


def test_shadow_defer_pending_verdict_credits_keeps_backlog():
    eng, ret, rival, m = _suppression_setup(Cfg(shadow_defer=True))
    n = eng.submit_verdicts([(1, 0, "pending")], 5)
    assert n == 0
    assert m.d_shadow == 1.0                          # 非 synonym → 发信用
    assert eng._shadow_pending == []
    assert (0, 1) in eng.tensions                     # backlog 保留


def test_shadow_defer_settles_via_sync_maintenance():
    eng, ret, rival, m = _suppression_setup(
        Cfg(shadow_defer=True, tension_delay=0))
    eng.semantics = _Judge(eng.semantics, verdict="update")
    eng.step(0)
    assert m.d_shadow == 1.0 and eng._shadow_pending == []
    assert eng.n_resolve == 1 and not eng.tensions


def test_shadow_pending_bounded():
    eng, ret, rival, m = _suppression_setup(
        Cfg(shadow_defer=True, shadow_pending_cap=1))
    eng._record_shadow_pending(m, rival, 5, True)
    assert len(eng._shadow_pending) == 1 and eng.n_shadow_dropped == 1


def test_worker_absent_system_operates_and_queue_bounded():
    emb, world, eng = make(cfg=Cfg(defer_credit=True, signal_queue_cap=8))
    for t in range(30):
        b = world.beliefs[t % len(world.beliefs)]
        eng.observe([Event(b.id, b.value,
                           b.phrasings[b.value][0])], t)
        qv = emb.vec_for(b.entity, b.id, b.value)
        eng.retrieve(qv, Query(b.id, "q"), t)
        eng.step(t)
    assert len(eng.signals) <= 8
    assert eng.signals.n_dropped > 0            # 无人消费 → 有界丢弃计数
    assert eng.pool_sizes()["M"] >= 0           # 引擎照常运转
