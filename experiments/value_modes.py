"""受控价值模式实验：高价值低频、普通高频、低价值低频与状态更新。"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from experiments import paths as P
from experiments.dynamics_v3 import FEATURE_SETS, configure
from hybrid_memory.config import Cfg
from hybrid_memory.core.confidence import projected
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Pool, Query
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen
from hybrid_memory.worker import SignalWorker

SETS = ("p01", "r1_confidence", "r12_salience", "r123_novelty")
SEEDS = tuple(range(20))
T = 151


def _query(eng, emb, world, belief, t: int):
    q = Query(belief.id, f"what is {belief.scope} now?")
    key = world.embedding_key(belief.id, belief.value)
    return eng.retrieve(emb.embed([q.text], keys=[key])[0], q, t)


def run_one(feature_set: str, seed: int) -> dict:
    cfg = configure(Cfg(
        cap_m=8, archive_retrieval=False, suppression_on=False,
        tension_delay=0, fresh_alpha=0.0), feature_set)
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed, n_stable=0, t_drift=1000,
                      t_noise=1000, noise_end=1001, t_conflict=1000,
                      query_rate=0.0)
    eng = MemoryEngine(cfg, emb, world)
    worker = SignalWorker(eng, world)
    high = world._spawn("critical", 0, 0, birth=0)
    low = world._spawn("minor", 0, 0, birth=0)
    flow = world._spawn("routine", 0, 0, birth=0)
    status = world._spawn("old", 0, 0, birth=0)
    old_status_value = status.value
    flow_promoted_at = None
    observations = {
        high.id: (1.0, high.phrasings[high.value][0]),
        low.id: (0.0, low.phrasings[low.value][0]),
        flow.id: (0.3, flow.phrasings[flow.value][0]),
        status.id: (0.9, status.phrasings[status.value][0]),
    }
    late = {}
    update = {}

    for t in range(T):
        if t == 0:
            eng.observe([
                Event(b.id, b.value, observations[b.id][1], (), observations[b.id][0])
                for b in (high, low, flow, status)
            ], t)
        if t and t <= 100 and t % 4 == 0:
            eng.observe([Event(flow.id, flow.value,
                               flow.phrasings[flow.value][t // 4 % 4], (), 0.3)], t)
            _query(eng, emb, world, flow, t)
        if t in (30, 60):
            eng.observe([Event(status.id, status.value,
                               status.phrasings[status.value][t // 30], (), 0.9)], t)
        if t == 80:
            new_value = "new"
            status.phrasings[new_value] = [p + "'" for p in status.phrasings[old_status_value]]
            status.value = new_value
            eng.observe([Event(status.id, new_value,
                               status.phrasings[new_value][0], (), 0.9)], t)
        if t == 81:
            ret = _query(eng, emb, world, status, t)
            update = {
                "latest_selected": any(m.belief_id == status.id and
                                       m.value == status.value for m in ret.selected),
                "stale_selected": any(m.belief_id == status.id and
                                      m.value == old_status_value for m in ret.selected),
            }
        if t == 120:
            high_mem = max(
                (m for m in eng.mems.values()
                 if m.belief_id == high.id and m.superseded_by is None),
                key=lambda m: (m.pool is not Pool.ARCHIVE, m.birth, m.id))
            ret = _query(eng, emb, world, high, t)
            late.update({
                "active_t120": high_mem.pool is not Pool.ARCHIVE,
                "selected_t120": high_mem in ret.selected,
                "provisional_t120": high_mem in ret.provisional,
                "confidence_t120": (projected(high_mem, cfg)
                                    if cfg.confidence_on else None),
                "low_active_t120": any(
                    m.belief_id == low.id and m.pool is not Pool.ARCHIVE
                    for m in eng.mems.values()),
            })
        if t == 130:
            eng.observe([Event(high.id, high.value,
                               high.phrasings[high.value][1], (), 1.0)], t)
        if t == 131:
            high_mem = max(
                (m for m in eng.mems.values()
                 if m.belief_id == high.id and m.superseded_by is None),
                key=lambda m: (m.pool is not Pool.ARCHIVE, m.birth, m.id))
            ret = _query(eng, emb, world, high, t)
            late.update({
                "active_t131": high_mem.pool is not Pool.ARCHIVE,
                "selected_t131": high_mem in ret.selected,
                "provisional_t131": high_mem in ret.provisional,
                "confidence_t131": (projected(high_mem, cfg)
                                    if cfg.confidence_on else None),
            })
        eng.step(t)
        worker.process(t)
        if flow_promoted_at is None and any(
                m.belief_id == flow.id and m.pool is Pool.MEMORY
                for m in eng.mems.values()):
            flow_promoted_at = t

    return {
        "feature_set": feature_set,
        "features": list(FEATURE_SETS[feature_set]),
        "seed": seed,
        **late,
        **update,
        "flow_promoted_at": flow_promoted_at,
        "pool_final": eng.pool_sizes(),
    }


def _rate(rows, key: str) -> float:
    return round(float(np.mean([bool(r[key]) for r in rows])), 4)


def main() -> None:
    rows = [run_one(name, seed) for name in SETS for seed in SEEDS]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["feature_set"]].append(row)
    summary = []
    for name in SETS:
        rs = grouped[name]
        promotions = [r["flow_promoted_at"] for r in rs
                      if r["flow_promoted_at"] is not None]
        conf120 = [r["confidence_t120"] for r in rs
                   if r["confidence_t120"] is not None]
        conf131 = [r["confidence_t131"] for r in rs
                   if r["confidence_t131"] is not None]
        summary.append({
            "feature_set": name,
            "high_active_t120": _rate(rs, "active_t120"),
            "high_selected_t120": _rate(rs, "selected_t120"),
            "high_provisional_t120": _rate(rs, "provisional_t120"),
            "high_trusted_t131": round(float(np.mean([
                r["selected_t131"] and not r["provisional_t131"] for r in rs])), 4),
            "low_active_t120": _rate(rs, "low_active_t120"),
            "latest_update_selected": _rate(rs, "latest_selected"),
            "stale_update_selected": _rate(rs, "stale_selected"),
            "flow_promoted_at_mean": (round(float(np.mean(promotions)), 2)
                                      if promotions else None),
            "confidence_t120_mean": (round(float(np.mean(conf120)), 4)
                                     if conf120 else None),
            "confidence_t131_mean": (round(float(np.mean(conf131)), 4)
                                     if conf131 else None),
        })
    out = P.RUNS / "value-modes-v3.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
