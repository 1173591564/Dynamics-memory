"""follow_chain 回归：id=0 作为链目标、环/断链防御、经 step 的端到端触发。"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.config import Cfg
from hybrid_memory.core import maintenance
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Memory
from sim_embed import SyntheticEmbedder
from sim_world import StreamGen


def _engine():
    emb = SyntheticEmbedder(seed=0)
    world = StreamGen(emb, seed=0)
    return MemoryEngine(Cfg(), emb, world)


def _mem(i, **kw):
    return Memory(id=i, belief_id=0, value="v", text=f"m{i}",
                  emb=np.array([1.0, 0.0]), **kw)


def test_chain_to_memory_id_zero_is_followed():
    # 曾经的写法 `m.superseded_by or m.aggregated_into` 在 superseded_by=0
    # 时短路成 None → eng.mems[None] KeyError
    eng = _engine()
    eng.mems = {0: _mem(0), 1: _mem(1, superseded_by=0)}
    assert maintenance.follow_chain(eng, eng.mems[1]) is eng.mems[0]
    assert eng.n_chain_broken == 0


def test_aggregated_into_zero_is_followed():
    eng = _engine()
    eng.mems = {0: _mem(0, agg_members=(1, 2)), 1: _mem(1, aggregated_into=0),
                2: _mem(2, aggregated_into=0)}
    assert maintenance.follow_chain(eng, eng.mems[2]) is eng.mems[0]


def test_multi_hop_chain_mixed_pointers():
    eng = _engine()
    eng.mems = {3: _mem(3), 2: _mem(2, aggregated_into=3),
                1: _mem(1, superseded_by=2), 0: _mem(0, superseded_by=1)}
    assert maintenance.follow_chain(eng, eng.mems[0]) is eng.mems[3]


def test_cycle_is_broken_not_infinite():
    eng = _engine()
    eng.mems = {0: _mem(0, superseded_by=1), 1: _mem(1, superseded_by=0)}
    out = maintenance.follow_chain(eng, eng.mems[0])
    assert out.id in (0, 1)
    assert eng.n_chain_broken == 1


def test_dangling_pointer_is_broken_not_keyerror():
    eng = _engine()
    eng.mems = {0: _mem(0, superseded_by=99)}
    assert maintenance.follow_chain(eng, eng.mems[0]) is eng.mems[0]
    assert eng.n_chain_broken == 1


def test_step_with_tension_on_zero_chain_does_not_crash():
    # 端到端：tension 一端已被 id=0 取代，maintenance 在 step 里追链
    eng = _engine()
    eng.mems = {0: _mem(0), 1: _mem(1, superseded_by=0), 2: _mem(2)}
    eng._next_id = 3
    eng.add_tension(1, 2, 0)
    eng.step(0)
    eng.step(eng.cfg.tension_delay + 1)
    kinds = [s.kind for s in eng.drain_signals()]
    assert "conflict_pending" in kinds


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_synthetic_sim_runs_end_to_end(seed):
    # 默认 Cfg 曾在此路径必现 KeyError（supersede 链 id=0）
    from hybrid_memory.worker import SignalWorker
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed)
    eng = MemoryEngine(Cfg(cap_m=8), emb, world)
    worker = SignalWorker(eng, world)
    for t in range(120):
        evs, qs = world.step(t)
        eng.observe(evs, t)
        for q in qs:
            belief = world.beliefs[q.target]
            key = world.embedding_key(q.target, belief.value)
            eng.retrieve(emb.embed([q.text], keys=[key])[0], q, t)
        eng.step(t)
        worker.process(t)
    assert eng.n_chain_broken == 0
