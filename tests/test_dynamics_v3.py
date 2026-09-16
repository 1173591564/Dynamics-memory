import numpy as np
import pytest

from experiments.dynamics_v3 import FEATURE_SETS, configure, diagnostics
from experiments.value_modes import run_one
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Memory, Pool
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen


def test_feature_sets_are_strictly_cumulative():
    base = Cfg()
    expected = {
        "p01": (False, False, False, False),
        "r1_confidence": (True, False, False, False),
        "r12_salience": (True, True, False, False),
        "r123_novelty": (True, True, True, False),
        "r1234_full": (True, True, True, True),
    }
    for name, flags in expected.items():
        cfg = configure(base, name)
        assert (cfg.confidence_on, cfg.salience_on, cfg.novelty_on,
                cfg.consolidation_on) == flags
    with pytest.raises(ValueError, match="unknown feature set"):
        configure(base, "unknown")
    assert tuple(FEATURE_SETS) == tuple(expected)


def test_diagnostics_excludes_hidden_members():
    cfg = configure(Cfg(), "r1234_full")
    emb = SyntheticEmbedder(seed=0)
    world = StreamGen(emb, seed=0)
    eng = MemoryEngine(cfg, emb, world)
    eng.mems[0] = Memory(0, 0, "v", "active", np.ones(2),
                         conf_pos=1.0, salience=0.8, novelty=0.7)
    eng.mems[1] = Memory(1, 0, "v", "archived", np.ones(2),
                         pool=Pool.ARCHIVE)
    eng.mems[2] = Memory(2, 0, "v", "hidden", np.ones(2),
                         aggregated_into=0)
    stats = diagnostics(eng)
    assert stats["active"] == 1
    assert stats["trusted_active"] == 1
    assert stats["reflections"] == 0


def test_controlled_value_modes_identify_each_mechanism():
    p01 = run_one("p01", 0)
    confidence = run_one("r1_confidence", 0)
    salience = run_one("r12_salience", 0)
    novelty = run_one("r123_novelty", 0)
    assert not p01["active_t120"] and not confidence["active_t120"]
    assert salience["active_t120"] and salience["provisional_t120"]
    assert salience["selected_t131"] and not salience["provisional_t131"]
    assert salience["confidence_t131"] > salience["confidence_t120"]
    assert novelty["flow_promoted_at"] < salience["flow_promoted_at"]
    for row in (p01, confidence, salience, novelty):
        assert row["latest_selected"] and not row["stale_selected"]
