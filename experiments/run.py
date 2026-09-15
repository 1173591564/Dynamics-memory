"""实验入口：预设 × 相位流 → 逐步轨迹与分相位汇总。

用法：python -m experiments.run            （在 mvp/ 目录下）
预设：
  ours        完整设计（双池+滞回+shadow+dedup+useful-hit+容量）
  sfams_style SF-AMS 生存方程风格基线：单池、入选即强化、Ψ_div、线性衰减
  flat        纯 cosine top-K，无动力学、压制或合并
  decay_only  只衰减无强化（时间驱动基线）
  abl_*       从同一 ours 配置逐项关一个开关
"""
from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import replace
from statistics import stdev

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.metrics import QueryCounts, Recorder, StepMetrics
from hybrid_memory.sim.world import StreamGen

T = 220
SEEDS = tuple(range(10))
BASE = Cfg(cap_m=8)

PRESETS: dict[str, Cfg] = {
    "ours": BASE,
    "sfams_style": replace(
        BASE, two_pool=False, useful_hit=False, ingest_dedup=False,
        shadow_credit=False, suppression_on=False, tension_on=False,
        archive_retrieval=False, div_gate=True, decay_mode="linear", fresh_alpha=0.0,
    ),
    "flat": replace(
        BASE, two_pool=False, useful_hit=False, ingest_dedup=False,
        shadow_credit=False, suppression_on=False, tension_on=False,
        lam=0.0, eta=0.0, eta_shadow=0.0, fresh_alpha=0.0,
        pi_m=0.0, capacity_on=False, idle_p=10**9,
    ),
    "decay_only": replace(BASE, eta=0.0, eta_shadow=0.0, shadow_credit=False),
    "abl_no_twopool": replace(BASE, two_pool=False),
    "abl_no_shadow": replace(BASE, shadow_credit=False),
    "abl_no_dedup": replace(BASE, ingest_dedup=False),
    "abl_selected_credit": replace(BASE, useful_hit=False),
    "abl_no_capacity": replace(BASE, capacity_on=False),
    "abl_no_tension": replace(BASE, tension_on=False),
}


def run_one(name: str, cfg: Cfg, seed: int = 0) -> Recorder:
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed)
    eng = MemoryEngine(cfg, emb, world)
    recorder = Recorder()

    for t in range(T):
        events, queries = world.step(t)
        eng.observe(events, t)
        counts = QueryCounts()
        for query in queries:
            belief = world.beliefs[query.target]
            key = world.embedding_key(query.target, belief.value)
            q_emb = emb.embed([query.text], keys=[key])[0]
            counts.add(eng.retrieve(q_emb, query, t))
        eng.step(t)
        recorder.record(eng, t, world.phase(t), counts)
    return recorder


def _finite_mean(rows: list[StepMetrics], field: str) -> float:
    values = [getattr(row, field) for row in rows]
    values = [value for value in values if math.isfinite(value)]
    return sum(values) / len(values) if values else float("nan")


def _sample_sd(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value)]
    return stdev(values) if len(values) > 1 else float("nan")


def summarize(name: str, recorders: list[Recorder], phase: str) -> dict:
    grouped = [[row for row in recorder.rows if phase == "all" or row.phase == phase]
               for recorder in recorders]
    rows = [row for group in grouped for row in group]
    queries = sum(row.n_queries for row in rows)
    query_hits = sum(row.n_query_hits for row in rows)
    selected = sum(row.n_selected for row in rows)
    relevant = sum(row.n_relevant for row in rows)
    unique_selected = sum(row.n_unique_selected for row in rows)
    unique_relevant = sum(row.n_unique_relevant for row in rows)
    seed_recall = [sum(row.n_query_hits for row in group) / sum(row.n_queries for row in group)
                   for group in grouped if sum(row.n_queries for row in group)]
    seed_efficiency = [
        sum(row.n_unique_relevant for row in group) / sum(row.n_selected for row in group)
        for group in grouped if sum(row.n_selected for row in group)
    ]
    seed_pollution_m = [_finite_mean(group, "pollution_m") for group in grouped]
    seed_max_m = [max((row.n_m for row in group), default=0) for group in grouped]
    return {
        "preset": name,
        "phase": phase,
        "seeds": len(recorders),
        "queries": queries,
        "recall_at_k": query_hits / queries if queries else float("nan"),
        "recall_seed_sd": _sample_sd(seed_recall),
        "precision_at_k": relevant / selected if selected else float("nan"),
        "context_efficiency": unique_relevant / selected if selected else float("nan"),
        "context_efficiency_seed_sd": _sample_sd(seed_efficiency),
        "redundancy": 1.0 - unique_selected / selected if selected else float("nan"),
        "pollution": _finite_mean(rows, "pollution"),
        "pollution_c": _finite_mean(rows, "pollution_c"),
        "pollution_m": _finite_mean(rows, "pollution_m"),
        "pollution_m_seed_sd": _sample_sd(seed_pollution_m),
        "mean_c": _finite_mean(rows, "n_c"),
        "mean_m": _finite_mean(rows, "n_m"),
        "max_m": max((row.n_m for row in rows), default=0),
        "max_m_seed_sd": _sample_sd(seed_max_m),
        "mean_tension_depth": _finite_mean(rows, "tension_depth"),
        "scissors_gap": _finite_mean(rows, "scissors_gap"),
        "n_promote": sum(row.n_promote for row in rows),
        "n_demote": sum(row.n_demote for row in rows),
        "n_merge": sum(row.n_merge for row in rows),
        "n_evict": sum(row.n_evict for row in rows),
        "n_archive": sum(row.n_archive for row in rows),
        "n_revive": sum(row.n_revive for row in rows),
        "n_tension": sum(row.n_tension for row in rows),
        "n_resolve": sum(row.n_resolve for row in rows),
    }


def _write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "out", "runs")
    os.makedirs(out_dir, exist_ok=True)
    trajectories: list[dict] = []
    summaries: list[dict] = []

    for name, cfg in PRESETS.items():
        recorders = [run_one(name, cfg, seed) for seed in SEEDS]
        for seed, recorder in zip(SEEDS, recorders):
            for row in recorder.rows:
                trajectories.append({"preset": name, "seed": seed, **row.__dict__})
        for phase in ("all", "stable", "drift", "noise", "conflict"):
            summaries.append(summarize(name, recorders, phase))

    _write_csv(os.path.join(out_dir, "trajectory.csv"), trajectories)
    _write_csv(os.path.join(out_dir, "summary.csv"), summaries)
    for row in summaries:
        if row["phase"] != "all":
            continue
        print(f'{row["preset"]:22s} recall={row["recall_at_k"]:.3f} '
              f'eff={row["context_efficiency"]:.3f} red={row["redundancy"]:.3f} '
              f'pollM={row["pollution_m"]:.3f} maxM={row["max_m"]:d} '
              f'evict={row["n_evict"]:d} gap={row["scissors_gap"]:.3f}')


if __name__ == "__main__":
    main()
