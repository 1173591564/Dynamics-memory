"""冒烟测试：每回路基本不变量。直接 python tests/test_smoke.py 跑。"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Memory, Pool, Query, Retrieval
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.metrics import QueryCounts
from hybrid_memory.sim.world import StreamGen


def make(seed=0, cfg=None, **world_kwargs):
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed, **world_kwargs)
    return emb, world, MemoryEngine(cfg or Cfg(), emb, world)


def test_ingest_dedup_pools_evidence():
    emb, world, eng = make()
    b = next(iter(world.beliefs.values()))
    ev = Event(b.id, b.value, b.phrasings[b.value][0])
    for _ in range(3):
        eng.observe([ev], 0)
    assert len(eng.mems) == 1, "同 belief 同值重复生成应 dedup 成一条"
    assert eng.mems[0].evid == 3


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
    assert challenger_memory.d_shadow == 1.0
    assert challenger_memory.last_hit == 1
    before = challenger_memory.v
    eng.step(1)
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
