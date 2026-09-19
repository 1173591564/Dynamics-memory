"""冒烟测试：每回路基本不变量。直接 python tests/test_smoke.py 跑。"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.config import Cfg
from hybrid_memory.core.confidence import discount_to, projected
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Memory, Pool, Query, Retrieval
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.metrics import QueryCounts
from hybrid_memory.sim.world import StreamGen
from hybrid_memory.worker import SignalWorker


def make(seed=0, cfg=None, **world_kwargs):
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed, **world_kwargs)
    return emb, world, MemoryEngine(cfg or Cfg(), emb, world)


class _TableEmbedder:
    """按 text 查表给向量，用于精确控制 ingest 余弦。"""

    def __init__(self, table):
        self.table = table

    def embed(self, texts, keys=None):
        return np.array([self.table[t] for t in texts], dtype=np.float32)


def _stub_engine(cfg, table):
    emb = SyntheticEmbedder(seed=0)
    world = StreamGen(emb, seed=0)
    return world, MemoryEngine(cfg, _TableEmbedder(table), world)


class _Consolidatable:
    """StreamGen 委托 + 可注入 consolidate 回调（out 原样返回）。"""

    def __init__(self, world, out):
        self._world = world
        self._out = out
        self.calls = []

    def __getattr__(self, name):
        return getattr(self._world, name)

    def consolidate(self, memories, t):
        self.calls.append([m.id for m in memories])
        out = self._out(memories) if callable(self._out) else self._out
        if isinstance(out, Exception):
            raise out
        return out


class _JudgeSpy:
    """包装 semantics：judge 计数/注入 verdict；fail=True 时被调即炸。"""

    def __init__(self, inner, verdict="synonym", fail=False):
        self._inner = inner
        self._verdict = verdict
        self._fail = fail
        self.calls = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def judge(self, *args):
        if self._fail:
            raise AssertionError("不该调用 judge")
        self.calls.append(args)
        return self._verdict


def test_ingest_dedup_pools_evidence():
    emb, world, eng = make()
    b = next(iter(world.beliefs.values()))
    ev = Event(b.id, b.value, b.phrasings[b.value][0])
    for _ in range(3):
        eng.observe([ev], 0)
    assert len(eng.mems) == 1, "同 belief 同值重复生成应 dedup 成一条"
    assert eng.mems[0].evid == 3


def test_ingest_low_sim_never_calls_judge():
    table = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    world, eng = _stub_engine(Cfg(), table)
    eng.semantics = _JudgeSpy(world, fail=True)
    eng.observe([Event(0, "va", "a")], 0)
    eng.observe([Event(1, "vb", "b")], 1)    # sim=0<τ_dup → 不判
    assert len(eng.mems) == 2
    assert not eng.tensions


def test_ingest_high_sim_verbatim_dedup_needs_no_judge():
    # 同 belief_id + 同 value 是确定性 verbatim：内联合并，不走语义裁决
    table = {"a": [1.0, 0.0], "a2": [1.0, 0.0]}
    world, eng = _stub_engine(Cfg(), table)
    eng.semantics = _JudgeSpy(world, verdict="synonym", fail=True)
    eng.observe([Event(0, "va", "a")], 0)
    eng.observe([Event(0, "va", "a2")], 1)
    assert len(eng.mems) == 1 and eng.mems[0].evid == 2
    assert not eng.tensions


def test_ingest_near_dup_resolves_via_worker():
    # 非 verbatim 近重复：各立条目 + tension，verdict 由 worker 回报后合并
    table = {"a": [1.0, 0.0], "a2": [1.0, 0.0]}
    world, eng = _stub_engine(Cfg(tension_delay=0), table)
    spy = _JudgeSpy(world, verdict="synonym")
    eng.observe([Event(0, "va", "a")], 0)
    eng.observe([Event(0, "vb", "a2")], 1)
    assert len(eng.mems) == 2 and len(eng.tensions) == 1
    assert len(spy.calls) == 0               # 引擎不判
    eng.step(1)                              # 老化发 conflict_pending
    stats = SignalWorker(eng, spy).process(1)
    assert stats["resolved"] == 1 and len(spy.calls) == 1
    assert eng.mems[0].evid == 2 and eng.mems[1].pool is Pool.ARCHIVE
    assert not eng.tensions


def test_ingest_dedup_off_high_sim_no_judge_still_tension():
    table = {"a": [1.0, 0.0], "a2": [1.0, 0.0]}
    world, eng = _stub_engine(Cfg(ingest_dedup=False), table)
    eng.semantics = _JudgeSpy(world, fail=True)
    eng.observe([Event(0, "va", "a")], 0)
    eng.observe([Event(0, "va", "a2")], 1)
    assert len(eng.mems) == 2
    assert len(eng.tensions) == 1   # 高 sim 仍经 add_tension 记冲突


def test_promotion_and_demotion():
    emb, world, eng = make()
    b = next(iter(world.beliefs.values()))
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    m = eng.mems[0]
    m.v = eng.cfg.theta_p + 0.1
    eng.step(1)
    assert m.pool is Pool.MEMORY
    m.v = eng.cfg.theta_d - 0.1
    eng.step(2)
    assert m.pool is Pool.CANDIDATE


def test_archive_on_idle():
    emb, world, eng = make()
    b = next(iter(world.beliefs.values()))
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    eng.step(eng.cfg.idle_p + 1)
    assert eng.mems[0].pool is Pool.ARCHIVE


def test_capacity_eviction():
    emb, world, eng = make()
    cfg = eng.cfg
    for i in range(cfg.cap_m + 5):
        m_b = world._spawn(f"x{i}", 0, 0)
        eng.observe([Event(m_b.id, m_b.value, m_b.phrasings[m_b.value][0])], 0)
    for m in eng.mems.values():
        m.pool = Pool.MEMORY
        m.v = 1.0
    eng.step(1)
    assert sum(1 for m in eng.mems.values() if m.pool is Pool.MEMORY) <= cfg.cap_m
    assert eng.n_evict == 5
    assert sum(1 for m in eng.mems.values() if m.pool is Pool.CANDIDATE) == 5


def test_retrieve_returns_topk():
    emb, world, eng = make()
    events, queries = world.step(0)
    eng.observe(events, 0)
    if queries:
        q = queries[0]
        b = world.beliefs[q.target]
        r = eng.retrieve(emb.vec_for(b.entity, b.id, b.value), q, 0)
        assert len(r.selected) <= eng.cfg.k


def test_relevance_is_query_specific():
    cfg = Cfg(k=5, suppression_on=False)
    emb, world, eng = make(cfg=cfg)
    target = world.beliefs[0]
    distractor = world._spawn("other", 0, 0, entity=target.entity, scope="other")
    eng.observe([
        Event(target.id, target.value, target.phrasings[target.value][0]),
        Event(distractor.id, distractor.value, distractor.phrasings[distractor.value][0]),
    ], 0)
    query = Query(target.id, "target")
    q_emb = emb.embed([query.text], keys=[world.embedding_key(target.id, target.value)])[0]
    result = eng.retrieve(q_emb, query, 0)
    assert len(result.selected) == 2
    assert result.n_useful == 1


def test_irrelevant_selection_does_not_extend_idle_life():
    cfg = Cfg(suppression_on=False)
    emb, world, eng = make(cfg=cfg)
    target = world.beliefs[0]
    distractor = world._spawn("other", 0, 0, entity=target.entity, scope="other")
    eng.observe([Event(distractor.id, distractor.value,
                       distractor.phrasings[distractor.value][0])], 0)
    query = Query(target.id, "target")
    q_emb = eng.mems[0].emb.copy()
    result = eng.retrieve(q_emb, query, cfg.idle_p)
    assert result.selected == [eng.mems[0]]
    assert result.n_useful == 0
    assert eng.mems[0].last_hit is None
    eng.step(cfg.idle_p + 1)
    assert eng.mems[0].pool is Pool.ARCHIVE


def test_late_candidate_gets_full_idle_window():
    emb, world, eng = make()
    belief = world._spawn("late", 0, 0, birth=100)
    eng.observe([Event(belief.id, belief.value, belief.phrasings[belief.value][0])], 100)
    eng.step(100)
    assert eng.mems[0].pool is Pool.CANDIDATE
    eng.step(150)
    assert eng.mems[0].pool is Pool.CANDIDATE
    eng.step(151)
    assert eng.mems[0].pool is Pool.ARCHIVE


def test_archive_revival():
    emb, world, eng = make()
    belief = world.beliefs[0]
    eng.observe([Event(belief.id, belief.value, belief.phrasings[belief.value][0])], 0)
    eng.step(eng.cfg.idle_p + 1)
    query = Query(belief.id, "target")
    q_emb = emb.embed([query.text], keys=[world.embedding_key(belief.id, belief.value)])[0]
    result = eng.retrieve(q_emb, query, eng.cfg.idle_p + 2)
    assert result.selected == [eng.mems[0]]
    assert eng.mems[0].pool is Pool.CANDIDATE
    assert eng.n_revive == 1


def test_archive_retrieval_can_be_disabled():
    cfg = Cfg(archive_retrieval=False)
    emb, world, eng = make(cfg=cfg)
    belief = world.beliefs[0]
    eng.observe([Event(belief.id, belief.value, belief.phrasings[belief.value][0])], 0)
    eng.mems[0].pool = Pool.ARCHIVE
    query = Query(belief.id, "target")
    q_emb = emb.embed([query.text], keys=[world.embedding_key(belief.id, belief.value)])[0]
    assert not eng.retrieve(q_emb, query, 1).selected


def test_archive_prior_affects_quality_gate():
    cfg = Cfg(fresh_alpha=0.0)
    emb, world, eng = make(cfg=cfg)
    belief = world.beliefs[0]
    query = Query(belief.id, "target")
    memory = Memory(0, belief.id, belief.value, "archived",
                    np.array([0.4, math.sqrt(0.84)]), pool=Pool.ARCHIVE)
    eng.mems[memory.id] = memory
    q_emb = np.array([1.0, 0.0])
    assert cfg.theta < 0.4
    assert 0.4 + cfg.pi_a < cfg.theta
    assert not eng.retrieve(q_emb, query, 100).selected


def test_freshness_does_not_bypass_quality_gate():
    cfg = Cfg(fresh_alpha=0.1)
    emb, world, eng = make(cfg=cfg)
    belief = world.beliefs[0]
    query = Query(belief.id, "target")
    memory = Memory(0, belief.id, belief.value, "fresh",
                    np.array([0.3, math.sqrt(0.91)]), birth=100)
    eng.mems[memory.id] = memory
    q_emb = np.array([1.0, 0.0])
    assert 0.3 < cfg.theta
    assert 0.3 + cfg.fresh_alpha > cfg.theta
    assert not eng.retrieve(q_emb, query, 100).selected


def test_delayed_tension_scope_resolution():
    cfg = Cfg(tension_delay=3)
    emb, world, eng = make(cfg=cfg)
    left = world._spawn("like", 0, 0, entity=100, scope="work")
    right = world._spawn("dislike", 0, 0, entity=100, scope="casual")
    eng.observe([
        Event(left.id, left.value, left.phrasings[left.value][0]),
        Event(right.id, right.value, right.phrasings[right.value][0]),
    ], 0)
    assert len(eng.tensions) == 1
    eng.step(0)
    eng.step(2)
    assert len(eng.tensions) == 1
    eng.step(3)
    SignalWorker(eng, world).process(3)
    assert not eng.tensions
    # 异 scope 矛盾 → 条件化聚合 memory，成员收编退居幕后
    agg = next(m for m in eng.mems.values() if m.agg_members)
    assert agg.agg_members == (0, 1)
    assert not agg.pending_review
    assert eng.mems[0].aggregated_into == agg.id
    assert eng.mems[1].aggregated_into == agg.id


def test_shadow_credit_reaches_relevant_challenger():
    cfg = Cfg(tension_delay=10)
    emb, world, eng = make(cfg=cfg)
    incumbent = world._spawn("like", 0, 0, entity=100, scope="work")
    challenger = world._spawn("dislike", 0, 0, entity=100, scope="casual", birth=1)
    eng.observe([Event(incumbent.id, incumbent.value,
                       incumbent.phrasings[incumbent.value][0])], 0)
    eng.observe([Event(challenger.id, challenger.value,
                       challenger.phrasings[challenger.value][0])], 1)
    incumbent_memory, challenger_memory = eng.mems[0], eng.mems[1]
    incumbent_memory.pool = Pool.MEMORY
    challenger_memory.emb = incumbent_memory.emb.copy()
    query = Query(challenger.id, "target")
    q_emb = challenger_memory.emb.copy()
    result = eng.retrieve(q_emb, query, 1)
    assert result.selected == [incumbent_memory]
    assert result.suppressed == [(challenger_memory.id, incumbent_memory.id)]
    # 恒延迟：verdict 到达前 shadow 不结算
    assert challenger_memory.d_shadow == 0.0
    eng.step(11)   # tension_delay=10，first_seen=1 → 老化发信号
    SignalWorker(eng, world).process(11)   # contradiction → 结算 shadow
    assert challenger_memory.d_shadow == 1.0
    assert challenger_memory.last_hit == 1   # 结算用原检索时刻
    before = challenger_memory.v
    eng.step(12)
    assert challenger_memory.v > before


def test_drift_supersedes_old_value_after_delay():
    cfg = Cfg(tension_delay=0)
    emb, world, eng = make(cfg=cfg)
    belief = world.beliefs[0]
    old_value = belief.value
    eng.observe([Event(belief.id, old_value, belief.phrasings[old_value][0])], 0)
    new_value = old_value + "'"
    belief.phrasings[new_value] = [p + "'" for p in belief.phrasings[old_value]]
    belief.value = new_value
    eng.observe([Event(belief.id, new_value, belief.phrasings[new_value][0])], 1)
    eng.step(1)
    SignalWorker(eng, world).process(1)   # 信号通路裁决 update → 新替旧
    old_memory = next(m for m in eng.mems.values() if m.value == old_value)
    new_memory = next(m for m in eng.mems.values() if m.value == new_value)
    assert old_memory.pool is Pool.ARCHIVE
    assert old_memory.superseded_by == new_memory.id
    assert world.valid(new_memory.belief_id, new_memory.value, 1)
    assert not world.valid(old_memory.belief_id, old_memory.value, 1)


def test_noise_burst_never_promotes_and_expires():
    emb, world, eng = make(t_noise=0, noise_end=1, noise_rate=20.0)
    events, _ = world.step(0)
    eng.observe(events, 0)
    eng.step(0)
    noise = [m for m in eng.mems.values() if world.beliefs[m.belief_id].noise]
    assert noise
    assert all(m.pool is Pool.CANDIDATE for m in noise)
    eng.step(eng.cfg.idle_p + 1)
    assert all(m.pool is Pool.ARCHIVE for m in noise)


def test_deferred_credit_only_rewards_recognized():
    cfg = Cfg(suppression_on=False, defer_credit=True)
    emb, world, eng = make(cfg=cfg)
    target = world.beliefs[0]
    other = world._spawn("other", 0, 0, entity=target.entity, scope="o")
    eng.observe([
        Event(target.id, target.value, target.phrasings[target.value][0]),
        Event(other.id, other.value, other.phrasings[other.value][0]),
    ], 0)
    query = Query(target.id, "q")
    q_emb = emb.embed([query.text], keys=[
        world.embedding_key(target.id, target.value)])[0]
    ret = eng.retrieve(q_emb, query, 0)
    assert len(ret.selected) == 2
    assert all(m.last_hit is None and m.d_hit == 0 for m in ret.selected)

    class Recog:
        def __getattr__(self, k):
            return getattr(world, k)

        def relevant_set(self, texts, q, a):
            return [True, False]

    eng2 = MemoryEngine(cfg, emb, Recog())
    eng2.observe([
        Event(target.id, target.value, target.phrasings[target.value][0]),
        Event(other.id, other.value, other.phrasings[other.value][0]),
    ], 0)
    ret2 = eng2.retrieve(q_emb, query, 0)
    eng2.feedback(ret2, "q", "answer", 0)          # 发 feedback_pending
    SignalWorker(eng2, Recog()).process(0)          # worker 判 relevant_set
    assert ret2.n_useful == 1
    assert ret2.selected[0].d_hit == 1.0
    assert ret2.selected[1].d_hit == 0.0


def test_llm_semantics_parse_with_fake_chat():
    from hybrid_memory.semantics.llm import LLMSemantics
    verdicts = iter(["update", "是 update。", "garbage"])
    sem = LLMSemantics(None, chat_fn=lambda s, u: next(verdicts))
    assert sem.judge(1, "a", 2, "b") == "update"
    assert sem.judge(3, "c", 4, "d") == "update"   # 前后有杂字也解析
    assert sem.judge(5, "e", 6, "f") == "pending"  # 解析失败→留在 backlog
    assert sem.judge(7, "g", 7, "g") == "synonym"  # verbatim 短路

    sem2 = LLMSemantics(None, chat_fn=lambda s, u: "1,3")
    assert sem2.relevant_set(["x", "y", "z"], "q", "a") == \
        [True, False, True]
    sem3 = LLMSemantics(None, chat_fn=lambda s, u: "NONE")
    assert sem3.relevant_set(["x", "y"], "q", "a") == [False, False]
    # "NONE." 尾部标点仍是 NONE——否则判成失败 → worker 退化全记，
    # "一条没用上"反而全记，指标直接反过来
    sem3b = LLMSemantics(None, chat_fn=lambda s, u: "NONE.")
    assert sem3b.relevant_set(["x", "y"], "q", "a") == [False, False]
    sem4 = LLMSemantics(None, chat_fn=lambda s, u: "??")
    assert sem4.relevant_set(["x"], "q", "a") is None  # 失败→None，worker 计数退化


def test_confidence_write_and_confirm_evidence():
    cfg = Cfg(confidence_on=True)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    ev = Event(b.id, b.value, b.phrasings[b.value][0])
    eng.observe([ev], 0)
    m = eng.mems[0]
    assert abs(projected(m, cfg) - 2 / 3) < 1e-9
    eng.observe([ev], 0)
    assert abs(projected(m, cfg) - 3 / 4) < 1e-9


def test_confidence_discount_half_life_idempotent():
    cfg = Cfg(confidence_on=True, conf_half_life=1.0)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    m = eng.mems[0]
    eng.step(1)
    assert abs(m.conf_pos - 0.5) < 1e-9
    assert abs(projected(m, cfg) - 0.6) < 1e-9
    eng.step(1)
    discount_to(m, 1, cfg)
    assert abs(m.conf_pos - 0.5) < 1e-9


def test_low_confidence_excluded_without_margin():
    cfg = Cfg(confidence_on=True, suppression_on=False, fresh_alpha=0.0)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    trusted = Memory(0, b.id, b.value, "trusted",
                     np.array([0.8, 0.6]), conf_pos=5.0)
    low = Memory(1, b.id, b.value, "low",
                 np.array([0.7, math.sqrt(0.51)]), conf_pos=0.0)
    eng.mems[0] = trusted
    eng.mems[1] = low
    result = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    assert result.selected == [trusted]
    assert not result.provisional


def test_lone_low_confidence_served_as_provisional():
    cfg = Cfg(confidence_on=True, fresh_alpha=0.0)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    low = Memory(0, b.id, b.value, "low",
                 np.array([0.9, math.sqrt(0.19)]), conf_pos=0.0)
    eng.mems[0] = low
    result = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    assert result.selected == [low]
    assert result.provisional == [low]


def test_low_confidence_co_served_when_margin_exceeded():
    cfg = Cfg(confidence_on=True, suppression_on=False, fresh_alpha=0.0)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    trusted = Memory(0, b.id, b.value, "trusted",
                     np.array([0.5, math.sqrt(0.75)]), conf_pos=5.0)
    low = Memory(1, b.id, b.value, "low",
                 np.array([0.95, math.sqrt(0.0975)]), conf_pos=0.0)
    eng.mems[0] = trusted
    eng.mems[1] = low
    result = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    assert result.selected == [trusted, low]
    assert result.provisional == [low]


def test_provisional_k_counts_admitted_not_attempted():
    # low1 靠 fresh 排在 low2 前但质量不过 margin；provisional_k=1
    # 时旧实现只尝试 low1 → 零入场，新实现应跳过它录取 low2
    cfg = Cfg(confidence_on=True, suppression_on=False, fresh_alpha=0.5,
              provisional_k=1)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    trusted = Memory(0, b.id, b.value, "trusted",
                     np.array([0.5, math.sqrt(0.75)]), conf_pos=5.0,
                     birth=0)
    low1 = Memory(1, b.id, b.value, "low1",
                  np.array([0.45, math.sqrt(0.7975)]), conf_pos=0.0,
                  birth=30)
    low2 = Memory(2, b.id, b.value, "low2",
                  np.array([0.65, math.sqrt(0.5775)]), conf_pos=0.0,
                  birth=0)
    for m in (trusted, low1, low2):
        eng.mems[m.id] = m
    result = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 30)
    assert result.selected == [trusted, low2]
    assert result.provisional == [low2]


def test_feedback_on_provisional_does_not_change_confidence():
    cfg = Cfg(confidence_on=True, fresh_alpha=0.0, defer_credit=True)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    low = Memory(0, b.id, b.value, "low",
                 np.array([0.9, math.sqrt(0.19)]), conf_pos=0.0)
    eng.mems[0] = low
    result = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    assert result.provisional == [low]
    eng.feedback(result, "q", "a", 0)
    SignalWorker(eng, world).process(0)   # world 无 relevant_set → 全记
    assert result.n_useful == 1
    assert low.hits == 1 and low.d_hit == 1.0
    assert low.conf_pos == 0.0 and low.conf_neg == 0.0


def test_contradiction_scoped_no_negative_evidence():
    cfg = Cfg(confidence_on=True, tension_delay=0)
    emb, world, eng = make(cfg=cfg)
    left = world._spawn("like", 0, 0, entity=100, scope="work")
    right = world._spawn("dislike", 0, 0, entity=100, scope="casual")
    eng.observe([
        Event(left.id, left.value, left.phrasings[left.value][0]),
        Event(right.id, right.value, right.phrasings[right.value][0]),
    ], 0)
    eng.step(0)
    SignalWorker(eng, world).process(0)
    a, b = eng.mems[0], eng.mems[1]
    agg = next(m for m in eng.mems.values() if m.agg_members)
    assert not agg.pending_review
    assert a.conf_neg == 0.0 and b.conf_neg == 0.0
    assert agg.conf_neg == 0.0
    assert agg.conf_pos == cfg.conf_write_evidence
    assert abs(projected(agg, cfg) - 2 / 3) < 1e-9


def test_contradiction_unscoped_adds_negative_evidence():
    cfg = Cfg(confidence_on=True, tension_delay=0)
    emb = SyntheticEmbedder(seed=0)
    world = StreamGen(emb, seed=0)

    class Unscoped:
        def __getattr__(self, name):
            return getattr(world, name)

        def judge(self, a_bid, a_val, b_bid, b_val):
            return "contradiction"

        def scope(self, belief_id):
            return ""

    eng = MemoryEngine(cfg, emb, Unscoped())
    left = world._spawn("like", 0, 0, entity=100, scope="work")
    right = world._spawn("dislike", 0, 0, entity=100, scope="casual")
    eng.observe([
        Event(left.id, left.value, left.phrasings[left.value][0]),
        Event(right.id, right.value, right.phrasings[right.value][0]),
    ], 0)
    eng.step(0)
    SignalWorker(eng, Unscoped()).process(0)
    a, b = eng.mems[0], eng.mems[1]
    agg = next(m for m in eng.mems.values() if m.agg_members)
    assert agg.pending_review
    assert a.conf_neg == cfg.conf_negative_evidence
    assert b.conf_neg == cfg.conf_negative_evidence
    assert agg.conf_pos == min(a.conf_pos, b.conf_pos)
    assert agg.conf_neg == max(a.conf_neg, b.conf_neg)


def test_salience_off_ignores_event_and_decays_identically():
    cfg = Cfg(salience_on=False, salience_default=0.4)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    ph = b.phrasings[b.value][0]
    eng.observe([Event(b.id, b.value, ph, (), 0.0)], 0)
    eng.observe([Event(b.id, b.value, ph, (), 1.0)], 0)
    m = eng.mems[0]
    assert m.salience == cfg.salience_default
    a = Memory(1, 0, "x", "a", np.array([1.0, 0.0]), salience=0.0)
    c = Memory(2, 0, "x", "c", np.array([0.0, 1.0]), salience=1.0)
    eng.mems[1] = a
    eng.mems[2] = c
    eng.step(1)
    assert a.v == c.v


def test_salience_on_exponential_decay():
    cfg = Cfg(salience_on=True, salience_retention_weight=3.0)
    emb, world, eng = make(cfg=cfg)
    a = Memory(0, 0, "x", "a", np.array([1.0, 0.0]), salience=0.0)
    b = Memory(1, 0, "x", "b", np.array([0.0, 1.0]), salience=1.0)
    eng.mems[0] = a
    eng.mems[1] = b
    assert a.v == cfg.v_init and b.v == cfg.v_init   # salience 不进初始 V
    eng.step(1)
    assert abs(a.v - cfg.v_init * math.exp(-cfg.lam)) < 1e-9
    assert abs(b.v - cfg.v_init * math.exp(-cfg.lam / 4.0)) < 1e-9


def test_salience_on_linear_decay():
    cfg = Cfg(salience_on=True, salience_retention_weight=3.0,
              decay_mode="linear")
    emb, world, eng = make(cfg=cfg)
    a = Memory(0, 0, "x", "a", np.array([1.0, 0.0]), salience=0.0)
    b = Memory(1, 0, "x", "b", np.array([0.0, 1.0]), salience=1.0)
    eng.mems[0] = a
    eng.mems[1] = b
    eng.step(1)
    assert abs(a.v - (cfg.v_init - cfg.lam)) < 1e-9
    assert abs(b.v - (cfg.v_init - cfg.lam / 4.0)) < 1e-9


def test_retention_scale_floor():
    from hybrid_memory.core.maintenance import _retention_scale
    m = Memory(0, 0, "x", "a", np.array([1.0, 0.0]))
    off = Cfg(salience_on=False)
    m.salience = 1.0
    assert _retention_scale(m, off) == 1.0
    cfg = Cfg(salience_on=True)
    for s, want in ((0.0, 1.0), (0.5, 1.0), (0.75, 2.5), (1.0, 4.0)):
        m.salience = s
        assert abs(_retention_scale(m, cfg) - want) < 1e-9


def test_salience_extends_idle_horizon_not_immortal():
    cfg = Cfg(salience_on=True, salience_retention_weight=3.0)
    emb, world, eng = make(cfg=cfg)
    a = Memory(0, 0, "x", "a", np.array([1.0, 0.0]), salience=0.0)
    b = Memory(1, 0, "x", "b", np.array([0.0, 1.0]), salience=1.0)
    n = Memory(2, 0, "x", "n", np.array([1.0, 1.0]), salience=0.5)
    eng.mems[0] = a
    eng.mems[1] = b
    eng.mems[2] = n
    eng.step(cfg.idle_p + 1)
    assert a.pool is Pool.ARCHIVE
    assert n.pool is Pool.ARCHIVE      # 中性 salience 不延期
    assert b.pool is Pool.CANDIDATE
    eng.step(cfg.idle_p * 4 + 1)
    assert b.pool is Pool.ARCHIVE


def test_salience_does_not_couple_confidence_discount():
    cfg = Cfg(confidence_on=True, salience_on=True, conf_half_life=10.0)
    emb, world, eng = make(cfg=cfg)
    a = Memory(0, 0, "x", "a", np.array([1.0, 0.0]),
               conf_pos=2.0, salience=0.0)
    b = Memory(1, 0, "x", "b", np.array([0.0, 1.0]),
               conf_pos=2.0, salience=1.0)
    eng.mems[0] = a
    eng.mems[1] = b
    eng.step(10)
    assert abs(a.conf_pos - 1.0) < 1e-9
    assert a.conf_pos == b.conf_pos


def test_salience_on_ingest_clamps_and_dedup_takes_max():
    cfg = Cfg(salience_on=True)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    ph = b.phrasings[b.value][0]
    eng.observe([Event(b.id, b.value, ph, (), 0.3)], 0)
    m = eng.mems[0]
    assert m.salience == 0.3
    assert m.v == cfg.v_init
    eng.observe([Event(b.id, b.value, ph, (), 0.9)], 0)
    assert m.salience == 0.9
    eng.observe([Event(b.id, b.value, ph, (), 0.1)], 0)
    assert m.salience == 0.9
    eng.observe([Event(b.id, b.value, ph, (), 1.7)], 0)
    assert m.salience == 1.0


def test_salience_propagates_on_merge_update_aggregate():
    cfg = Cfg(salience_on=True, tension_delay=0)
    emb, world, eng = make(cfg=cfg)
    b0 = world.beliefs[0]
    # synonym merge → keep 取双方 max salience，保自己 birth novelty
    m1 = Memory(0, b0.id, b0.value, "a", np.array([1.0, 0.0]),
                salience=0.2, novelty=0.95)
    m2 = Memory(1, b0.id, b0.value, "b", np.array([1.0, 0.0]),
                salience=0.9, novelty=0.5)
    eng.mems[0] = m1
    eng.mems[1] = m2
    eng.add_tension(0, 1, 0)
    eng.step(0)
    SignalWorker(eng, world).process(0)
    keep = m1 if m1.superseded_by is None else m2
    assert keep is m2      # m2 salience 高衰减慢 → v 高者留
    assert keep.salience == 0.9
    assert keep.novelty == 0.5   # 幸存者自己的 birth novelty，不取 max
    # update → 较新 keep 取双方 max
    m3 = Memory(10, b0.id, "old", "c", np.array([0.0, 1.0]),
                birth=0, salience=0.9, novelty=0.9)
    m4 = Memory(11, b0.id, "new", "d", np.array([0.0, 1.0]),
                birth=5, salience=0.1, novelty=0.1)
    eng.mems[10] = m3
    eng.mems[11] = m4
    eng.add_tension(10, 11, 5)
    eng.step(5)
    SignalWorker(eng, world).process(5)
    assert m3.superseded_by == m4.id
    assert m4.salience == 0.9
    assert m4.novelty == 0.1
    # contradiction aggregate → max
    left = world._spawn("like", 0, 0, entity=200, scope="work")
    right = world._spawn("dislike", 0, 0, entity=200, scope="casual")
    m5 = Memory(20, left.id, left.value, "e", np.array([1.0, 1.0]),
                salience=0.3, novelty=0.3, scene="s1")
    m6 = Memory(21, right.id, right.value, "f", np.array([1.0, 1.0]),
                salience=0.8, novelty=0.8, scene="s2")
    eng.mems[20] = m5
    eng.mems[21] = m6
    eng.add_tension(20, 21, 5)
    eng.step(5)
    SignalWorker(eng, world).process(5)
    agg = next(m for m in eng.mems.values() if m.agg_members == (20, 21))
    assert agg.salience == 0.8
    assert agg.novelty == 0.8
    assert agg.scene == ""            # 异 scene 聚合不带场景


def test_novelty_off_records_metadata_without_v_change():
    world, eng = _stub_engine(
        Cfg(novelty_on=False),
        {"t1": np.array([1.0, 0.0]), "t2": np.array([1.0, 0.0])})
    b0 = world.beliefs[0]
    eng.observe([Event(b0.id, b0.value, "t1")], 0)
    eng.observe([Event(b0.id, "other", "t2")], 0)   # 同 belief 异值 → update
    m1, m2 = eng.mems[0], eng.mems[1]
    assert m1.novelty == 1.0 and m2.novelty == 0.0
    assert m1.v == eng.cfg.v_init and m2.v == eng.cfg.v_init


def test_novelty_on_bonus_scales_initial_v():
    world, eng = _stub_engine(
        Cfg(novelty_on=True),
        {"t1": np.array([1.0, 0.0]), "t2": np.array([1.0, 0.0])})
    b0 = world.beliefs[0]
    eng.observe([Event(b0.id, b0.value, "t1")], 0)
    eng.observe([Event(b0.id, "other", "t2")], 0)
    m1, m2 = eng.mems[0], eng.mems[1]
    assert m1.v == eng.cfg.v_init + eng.cfg.novelty_bonus
    assert m2.v == eng.cfg.v_init


def test_novelty_clamps_negative_and_identical_cosine():
    world, eng = _stub_engine(
        Cfg(),
        {"p": np.array([1.0, 0.0]), "n": np.array([-1.0, 0.0]),
         "same": np.array([1.0, 0.0])})
    ba, bb = world.beliefs[0], world.beliefs[1]
    eng.observe([Event(ba.id, ba.value, "p")], 0)
    eng.observe([Event(bb.id, bb.value, "n")], 0)     # 异实体 → collision
    assert eng.mems[1].novelty == 1.0                 # 1-(-1) 钳到 1
    eng.observe([Event(bb.id, bb.value + "x", "same")], 0)
    assert eng.mems[2].novelty == 0.0                 # sim=1 → 0


def test_low_novelty_update_still_admitted_with_tension():
    world, eng = _stub_engine(
        Cfg(novelty_on=True),
        {"t1": np.array([1.0, 0.0]), "t2": np.array([1.0, 0.0])})
    b0 = world.beliefs[0]
    eng.observe([Event(b0.id, b0.value, "t1")], 0)
    eng.observe([Event(b0.id, "newer", "t2")], 0)
    assert len(eng.mems) == 2
    assert len(eng.tensions) == 1
    assert eng.mems[1].novelty == 0.0


def test_novelty_leaves_confidence_and_salience_unchanged():
    cfg = Cfg(novelty_on=True, confidence_on=True, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0], (), 0.9)], 0)
    m = eng.mems[0]
    assert m.novelty == 1.0
    assert m.v == cfg.v_init + cfg.novelty_bonus
    assert m.conf_pos == cfg.conf_write_evidence and m.conf_neg == 0.0
    assert m.salience == 0.9


def test_novelty_bonus_alone_never_promotes_and_decays():
    cfg = Cfg(novelty_on=True)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    m = eng.mems[0]
    assert m.v == cfg.v_init + cfg.novelty_bonus
    assert m.v < cfg.theta_p
    eng.step(1)
    assert m.pool is Pool.CANDIDATE
    assert m.v < cfg.v_init + cfg.novelty_bonus


def test_aggregate_novelty_max_without_extra_v_bonus():
    cfg = Cfg(novelty_on=True, tension_delay=0)
    emb, world, eng = make(cfg=cfg)
    left = world._spawn("like", 0, 0, entity=200, scope="work")
    right = world._spawn("dislike", 0, 0, entity=200, scope="casual")
    a = Memory(0, left.id, left.value, "a", np.array([1.0, 0.0]), novelty=0.2)
    b = Memory(1, right.id, right.value, "b", np.array([1.0, 0.0]),
               novelty=0.8)
    eng.mems[0] = a
    eng.mems[1] = b
    eng.add_tension(0, 1, 0)
    eng.step(0)
    SignalWorker(eng, world).process(0)
    agg = next(m for m in eng.mems.values() if m.agg_members == (0, 1))
    assert not agg.pending_review
    assert agg.novelty == 0.8
    assert agg.v == max(a.v, b.v)   # 无二次 novelty 加成


def test_consolidation_below_budget_not_called():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=6.0,
              consolidation_min_items=5)
    emb, world, eng = make(cfg=cfg)
    sem = _Consolidatable(world, Event(0, "v", "refl"))
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0], (), 0.5)], 0)
    eng.step(0)
    worker.process(0)
    assert sem.calls == []
    assert eng.n_consolidate == 0
    assert all(m.kind == "fact" for m in eng.mems.values())


def test_consolidation_threshold_creates_reflection_once():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=3.5,
              consolidation_min_items=3, consolidation_max_items=3,
              confidence_on=True, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    rb = world._spawn("state", 0, 0)
    out = Event(rb.id, rb.value, "当前状态：A完成B进行中",
                salience=0.7, kind="reflection",
                conf_pos=2.0, conf_neg=1.0)
    sem = _Consolidatable(world, out)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    for i in range(4):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (i,), 1.0)], i)
    eng.step(5)
    worker.process(5)
    # 4 条合格 fact，预算 4.0>=3.5、数 4>=3 → 取 top-3 (salience,last_seen,…)
    # 全同 salience → last_seen 降序取 id 1,2,3 → 回调按 (birth,id) 时序
    assert sem.calls == [[1, 2, 3]]
    assert eng.n_consolidate == 1
    refl = next(m for m in eng.mems.values() if m.kind == "reflection")
    assert refl.derived_from == (1, 2, 3)
    assert refl.src == frozenset({1, 2, 3})
    assert refl.salience == 0.7
    assert refl.conf_pos == 2.0 and refl.conf_neg == 1.0
    assert refl.conf_updated_at == 5
    assert refl.pool is Pool.CANDIDATE and refl.birth == 5
    sims = [float(np.dot(refl.emb, eng.mems[i].emb) /
                  (np.linalg.norm(refl.emb) * np.linalg.norm(eng.mems[i].emb)))
            for i in (1, 2, 3)]
    assert abs(refl.novelty - max(0.0, min(1.0, 1.0 - max(sims)))) < 1e-6
    # 源 fact 保持活跃可检索，未被取代/收编
    for i in range(4):
        src = eng.mems[i]
        assert src.superseded_by is None and src.aggregated_into is None
        assert src.pool is Pool.CANDIDATE
    # 恰好移除 chosen；reflection 不进 pending；下一步不级联
    assert eng._consolidation_pending == {0}
    eng.step(6)
    worker.process(6)
    assert sem.calls == [[1, 2, 3]]
    assert eng.n_consolidate == 1


def test_consolidation_none_callback_leaves_pending():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=1.0,
              consolidation_min_items=2)
    emb, world, eng = make(cfg=cfg)
    sem = _Consolidatable(world, None)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    for i in range(3):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (), 1.0)], 0)
    eng.step(0)
    worker.process(0)
    assert sem.calls == [[0, 1, 2]]
    assert eng.n_consolidate == 0
    assert eng._consolidation_pending == {0, 1, 2}


def test_consolidation_prunes_ineligible_pending():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=10.0,
              consolidation_min_items=5)
    emb, world, eng = make(cfg=cfg)
    sem = _Consolidatable(world, None)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    for i in range(4):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (), 1.0)], 0)
    eng.mems[0].pool = Pool.ARCHIVE
    eng.mems[1].superseded_by = 99
    eng.mems[2].aggregated_into = 99
    eng.mems[3].pending_review = True
    ghost = Memory(50, world.beliefs[0].id, "x", "ghost",
                   np.array([1.0, 0.0]), kind="reflection")
    eng.mems[50] = ghost
    eng._consolidation_pending.update({50, 77})   # 非 fact + 不存在
    eng.step(0)
    SignalWorker(eng, sem).process(0)
    assert eng._consolidation_pending == set()
    assert sem.calls == []
    assert eng.n_consolidate == 0


def test_lineage_suppression_creates_no_tension():
    cfg = Cfg(suppression_on=True)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]

    class NoJudge:
        def __getattr__(self, name):
            return getattr(world, name)

        def judge(self, *a):
            raise AssertionError("judge must not be called")

    eng.semantics = NoJudge()
    src = Memory(0, b.id, b.value, "src", np.array([1.0, 0.0]),
                 pool=Pool.MEMORY)
    refl = Memory(1, b.id, "v2", "refl",
                  np.array([0.95, math.sqrt(0.0975)]),
                  kind="reflection", derived_from=(0,))
    eng.mems[0] = src
    eng.mems[1] = refl
    ret = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    assert ret.selected == [src]
    assert ret.suppressed == [(1, 0)]
    assert refl.suppressed_by == 0
    assert refl.shadow_hits == 1
    assert refl.d_shadow == 0.0
    assert not eng.tensions


def test_consolidation_reflection_gets_no_write_evidence():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=1.0,
              consolidation_min_items=1, confidence_on=True,
              salience_on=True)   # 预算按入库 salience 计，off 时全落 default
    emb, world, eng = make(cfg=cfg)
    rb = world._spawn("state", 0, 0)
    out = Event(rb.id, rb.value, "状态反射", kind="reflection")
    sem = _Consolidatable(world, out)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0], (), 1.0)], 0)
    eng.step(0)
    worker.process(0)
    refl = next(m for m in eng.mems.values() if m.kind == "reflection")
    # Event 未带证据 → 0，不是 conf_write_evidence 的独立证据
    assert refl.conf_pos == 0.0 and refl.conf_neg == 0.0


def test_llm_consolidate_payload_event_and_fallbacks():
    from hybrid_memory.llm import ZhipuChatError
    from hybrid_memory.semantics.llm import LLMSemantics
    from hybrid_memory.semantics.real import normalize
    seen = []

    def fake(sys_prompt, user):
        seen.append(user)
        return " 当前状态：A 已完成，B 进行中 "

    sem = LLMSemantics(None, chat_fn=fake)
    src_a = Memory(0, 0, "va", "先做A", np.array([1.0, 0.0]),
                   birth=2, salience=0.4, conf_pos=3.0, conf_neg=1.0,
                   src=(5,), scene="项目X")
    src_b = Memory(1, 0, "vb", "再做B", np.array([0.0, 1.0]),
                   birth=1, salience=0.9, conf_pos=1.0, conf_neg=2.0,
                   src=(3, 7), scene="项目X")
    ev = sem.consolidate([src_b, src_a], 10)   # 调用方已按 (birth,id) 时序
    lines = seen[0].splitlines()
    assert lines[0] == "[memory_id=1 | t=1 | scene=项目X] 再做B"
    assert lines[1] == "[memory_id=0 | t=2 | scene=项目X] 先做A"
    assert ev.text == "当前状态：A 已完成，B 进行中"
    assert ev.belief_id == sem.fingerprint(ev.text)
    assert ev.value == normalize(ev.text)
    assert ev.src == (3, 5, 7)
    assert ev.salience == 0.9
    assert ev.kind == "reflection"
    assert ev.derived_from == (1, 0)
    assert ev.conf_pos == 1.0 and ev.conf_neg == 2.0
    assert ev.scene == "项目X"
    # NONE / 空 / 异常回落
    assert LLMSemantics(None, chat_fn=lambda s, u: "NONE").consolidate(
        [src_a], 0) is None
    assert LLMSemantics(None, chat_fn=lambda s, u: " none ").consolidate(
        [src_a], 0) is None
    assert LLMSemantics(None, chat_fn=lambda s, u: "  ").consolidate(
        [src_a], 0) is None

    def boom(s, u):
        raise ZhipuChatError("HTTP 500")
    assert LLMSemantics(None, chat_fn=boom).consolidate([src_a], 0) is None
    # 输出过脱敏层
    ev2 = LLMSemantics(
        None, chat_fn=lambda s, u: "key 是 sk-abc123def456ghi789"
    ).consolidate([src_a], 0)
    assert "[REDACTED]" in ev2.text and "sk-" not in ev2.text


def test_llm_semantics_passes_api_key_to_chat(monkeypatch):
    import hybrid_memory.semantics.llm as llm_sem
    calls = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return "1"

    monkeypatch.setattr(llm_sem, "chat", fake_chat)
    sem = llm_sem.LLMSemantics(api_key="sentinel", model="m",
                               cache_dir="cd")
    assert sem.relevant_set(["t1"], "q", "a") == [True]
    assert calls == [{
        "api_key": "sentinel", "model": "m",
        "system": llm_sem._RECOG_SYS,
        "user": "用户问题: q\n助手回答: a\n注入记忆:\n[1] t1",
        "cache_dir": "cd"}]

    # 注入 chat_fn：仍只收 (system, user)，不触达默认 chat
    calls.clear()
    seen = []
    sem2 = llm_sem.LLMSemantics(
        api_key="sentinel", chat_fn=lambda s, u: seen.append((s, u)) or "1")
    assert sem2.relevant_set(["x"], "q", "a") == [True]
    assert calls == []
    assert len(seen) == 1 and seen[0][0] == llm_sem._RECOG_SYS


def test_event_scene_threads_to_memory():
    emb, world, eng = make()
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0], (), 0.5,
                       scene="在围绕X做Y")], 0)
    assert eng.mems[0].scene == "在围绕X做Y"


def test_consolidation_scene_groups_no_cross_budget():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=3.0,
              consolidation_min_items=2, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    sem = _Consolidatable(world, None)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    # 每组各自预算 2.0 < 3.0，全局 4.0 ≥ 3.0 → 不得触发
    for i, scene in ((0, "A"), (1, "A"), (2, "B"), (3, "B")):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (), 1.0, scene=scene)], 0)
    eng.step(0)
    worker.process(0)
    assert sem.calls == []
    assert eng.n_consolidate == 0


def test_consolidation_ready_scene_only():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=2.5,
              consolidation_min_items=2, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    rb = world._spawn("state", 0, 0)
    out = Event(rb.id, rb.value, "A组状态", kind="reflection", scene="A")
    sem = _Consolidatable(world, out)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    for i, scene in ((0, "A"), (1, "A"), (2, "A"), (3, "B"), (4, "B")):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (), 1.0, scene=scene)], i)
    eng.step(5)
    worker.process(5)
    assert sem.calls == [[0, 1, 2]]          # 只有 ready 的 A 组
    refl = next(m for m in eng.mems.values() if m.kind == "reflection")
    assert refl.derived_from == (0, 1, 2)
    assert refl.scene == "A"
    assert eng._consolidation_pending == {3, 4}


def test_consolidation_picks_most_recent_scene_first():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=2.5,
              consolidation_min_items=2, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    rb = world._spawn("state", 0, 0)
    out = Event(rb.id, rb.value, "状态", kind="reflection", scene="B")
    sem = _Consolidatable(world, out)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    for i, t, scene in ((0, 0, "A"), (1, 1, "A"), (2, 2, "A"),
                        (3, 5, "B"), (4, 6, "B"), (5, 7, "B")):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (), 1.0, scene=scene)], t)
    eng.step(7)
    worker.process(7)
    # 两组都 ready：B 的 max last_seen=7 > A 的 2 → 先 B
    assert sem.calls == [[3, 4, 5]]
    assert eng._consolidation_pending == {0, 1, 2}
    eng.step(8)
    worker.process(8)
    assert sem.calls == [[3, 4, 5], [0, 1, 2]]
    assert eng.n_consolidate == 2


def test_consolidation_none_defers_signature_no_starvation():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=2.5,
              consolidation_min_items=2, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    rb = world._spawn("state", 0, 0)
    good = Event(rb.id, rb.value, "A状态", kind="reflection", scene="A")
    # B 永远 None、A 成功
    sem = _Consolidatable(
        world, lambda mems: None if mems[0].scene == "B" else good)
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    for i, t, scene in ((0, 0, "A"), (1, 1, "A"), (2, 2, "A"),
                        (3, 5, "B"), (4, 6, "B"), (5, 7, "B")):
        b = world.beliefs[i]
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                           (), 1.0, scene=scene)], t)
    eng.step(7)
    worker.process(7)
    # B 更新近 → 先试；None → 记签名、pending 不动
    assert sem.calls == [[3, 4, 5]]
    assert eng._consolidation_deferred["B"] == frozenset({3, 4, 5})
    assert eng.n_consolidate == 0
    eng.step(8)
    worker.process(8)
    # B 同签名跳过，不再饿死 A
    assert sem.calls == [[3, 4, 5], [0, 1, 2]]
    assert eng.n_consolidate == 1
    # 新 B 源改变签名 → 下一步重试 B（仍 None，签名更新）
    b = world.beliefs[6]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0],
                       (), 1.0, scene="B")], 9)
    eng.step(9)
    worker.process(9)
    new_id = eng._consolidation_pending - {3, 4, 5}
    assert len(new_id) == 1
    assert sem.calls[-1] == [3, 4, 5] + sorted(new_id)  # 时序尾部
    assert eng._consolidation_deferred["B"] == \
        frozenset({3, 4, 5} | new_id)


def test_consolidation_callback_error_contained():
    cfg = Cfg(consolidation_on=True, consolidation_salience_budget=1.0,
              consolidation_min_items=1, salience_on=True)
    emb, world, eng = make(cfg=cfg)
    sem = _Consolidatable(world, RuntimeError("bug"))
    eng.semantics = sem
    worker = SignalWorker(eng, sem)
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0], (), 1.0)], 0)
    eng.step(0)                              # 只发信号，不回调
    stats = worker.process(0)                # 回调编程错误被隔离：计数+回队，
    assert stats["errors"] == 1              # 不拖垮同批其他信号
    assert eng._consolidation_pending == {0}
    assert eng.n_consolidate == 0
    assert eng._consolidation_deferred[""] == frozenset({0})  # 发射即记签名
    assert [s.kind for s in eng.drain_signals()] == ["maintenance_due"]


def test_consolidation_novelty_ignores_hidden_members():
    world, eng = _stub_engine(
        Cfg(consolidation_on=True, consolidation_salience_budget=1.0,
            consolidation_min_items=1, salience_on=True),
        {"src text": np.array([0.0, 1.0]),
         "refl text": np.array([1.0, 0.0])})
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, "src text", (), 1.0)], 0)
    # 与 reflection 同向量的隐藏成员（被收编）不得参与 novelty 近邻
    eng.mems[1] = Memory(1, b.id, "old", "hidden", np.array([1.0, 0.0]),
                         aggregated_into=99)
    rb = world._spawn("state", 0, 0)
    out = Event(rb.id, rb.value, "refl text", kind="reflection")
    sem = _Consolidatable(world, out)
    eng.semantics = sem
    eng.step(0)
    SignalWorker(eng, sem).process(0)
    refl = next(m for m in eng.mems.values() if m.kind == "reflection")
    # 可见邻居 src 的 sim=0 → novelty=1；若隐藏成员被计入则为 0
    assert refl.novelty == 1.0


def test_lexical_channel_surfaces_token_match():
    # 两条记忆与 query 的向量相似度相同；只有含稀有词的那条该被词法通道顶上来
    world, eng = _stub_engine(
        Cfg(k=1, theta=-1.0, suppression_on=False, useful_hit=False,
            lex_weight=0.5),
        {"含 PR #1215 的条目": np.array([1.0, 0.0]),
         "不含的条目": np.array([1.0, 0.0]),
         "为什么 PR #1215 这么多 commit": np.array([1.0, 0.0])})
    b = world.beliefs[0]
    eng.observe([Event(b.id, "v1", "含 PR #1215 的条目"),
                 Event(b.id, "v2", "不含的条目")], 0)
    qv = eng.mems[0].emb.copy()
    ret = eng.retrieve(qv, Query(-1, "为什么 PR #1215 这么多 commit"), 0)
    assert ret.selected[0].text == "含 PR #1215 的条目"
    # lex_weight=0 时两条打平按插入序——先插"不含"则它赢，证明词法通道改变了排序
    world2, eng2 = _stub_engine(
        Cfg(k=1, theta=-1.0, suppression_on=False, useful_hit=False),
        {"含 PR #1215 的条目": np.array([1.0, 0.0]),
         "不含的条目": np.array([1.0, 0.0]),
         "为什么 PR #1215 这么多 commit": np.array([1.0, 0.0])})
    eng2.observe([Event(b.id, "v2", "不含的条目"),
                  Event(b.id, "v1", "含 PR #1215 的条目")], 0)
    ret2 = eng2.retrieve(qv, Query(-1, "为什么 PR #1215 这么多 commit"), 0)
    assert ret2.selected[0].text == "不含的条目"


def test_feedback_double_credit_raises():
    cfg = Cfg(suppression_on=False, defer_credit=True, useful_hit=False)
    emb, world, eng = make(cfg=cfg)
    target = world.beliefs[0]
    eng.observe([Event(target.id, target.value,
                       target.phrasings[target.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(target.entity, target.id, target.value),
                       Query(target.id, "target"), 0)
    eng.feedback(ret, "q", "a", 0)
    with pytest.raises(RuntimeError):
        eng.feedback(ret, "q", "a", 0)


def test_feedback_without_defer_credit_raises():
    cfg = Cfg(suppression_on=False, defer_credit=False, useful_hit=False)
    emb, world, eng = make(cfg=cfg)
    target = world.beliefs[0]
    eng.observe([Event(target.id, target.value,
                       target.phrasings[target.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(target.entity, target.id, target.value),
                       Query(target.id, "target"), 0)
    # defer_credit=False → retrieve 就地结清 → feedback 必须报错而非双计
    with pytest.raises(RuntimeError):
        eng.feedback(ret, "q", "a", 0)


def test_ingest_dedup_ignores_hidden_members():
    # 被聚合收编的成员不是活跃记忆：新事件应独立成条，
    # 既不把证据记进隐藏成员，也不与之挂幽灵 tension
    world, eng = _stub_engine(Cfg(), {"dup text": np.array([1.0, 0.0])})
    b = world.beliefs[0]
    hidden = Memory(0, b.id, b.value, "dup text",
                    np.array([1.0, 0.0]), aggregated_into=42)
    eng.mems[0] = hidden
    eng._next_id = 1
    eng.observe([Event(b.id, b.value, "dup text")], 0)
    assert hidden.evid == 1
    assert len(eng.mems) == 2
    assert not eng.tensions


def test_lex_scores_skip_hidden_members():
    from hybrid_memory.core.retrieval import _lexical_scores
    world, eng = _stub_engine(Cfg(), {})
    b = world.beliefs[0]
    vis = Memory(0, b.id, b.value, "alpha beta",
                 np.array([1.0, 0.0]))
    hid = Memory(1, b.id, b.value, "alpha gamma",
                 np.array([1.0, 0.0]), aggregated_into=9)
    eng.mems[0] = vis
    eng.mems[1] = hid
    scores = _lexical_scores(eng, Query(b.id, "alpha"))
    assert 0 in scores and 1 not in scores


def test_consolidation_pending_pruned_without_callback():
    # semantics 无 consolidate 回调时 early-return 也要先修剪 pending，
    # 否则死条目无界堆积
    from hybrid_memory.core.consolidation import maybe_consolidate
    cfg = Cfg(consolidation_on=True)
    world, eng = _stub_engine(cfg, {})
    b = world.beliefs[0]
    eng.mems[0] = Memory(0, b.id, b.value, "x",
                         np.array([1.0, 0.0]), pool=Pool.ARCHIVE)
    eng._consolidation_pending.update({0, 42})   # 0=已归档，42=不存在
    maybe_consolidate(eng, 0)
    assert eng._consolidation_pending == set()


def test_context_efficiency_counts_unique_facts():
    emb = np.ones(4)
    first = Memory(0, 0, "v", "a", emb)
    second = Memory(1, 0, "v", "b", emb)
    counts = QueryCounts()
    counts.add(Retrieval(selected=[first, second], n_useful=2))
    assert counts.selected == 2
    assert counts.relevant == 2
    assert counts.unique_selected == 1
    assert counts.unique_relevant == 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"{f.__name__} ok")
    print("all smoke tests passed")
