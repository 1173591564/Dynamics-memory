"""针对 shadow starvation 与持续迁入稳态的独立压力协议。"""
from __future__ import annotations

import csv
import os
import sys
from dataclasses import replace
from statistics import mean, median

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.run import PRESETS
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Pool, Query
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen
from hybrid_memory.worker import SignalWorker

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "runs")
SHADOW_T = 100
STREAM_T = 400
SHADOW_SEEDS = tuple(range(20))
STREAM_SEEDS = tuple(range(5))
SHADOW_BASE = Cfg(cap_m=4, pi_m=0.15, fresh_alpha=0.0, tension_delay=50,
                  idle_p=30, archive_retrieval=False)


def query(eng, emb, world, belief, t: int):
    item = Query(belief.id, f"what is {belief.scope}?")
    key = world.embedding_key(belief.id, belief.value)
    return eng.retrieve(emb.embed([item.text], keys=[key])[0], item, t)


def run_shadow(seed: int, shadow_credit: bool) -> tuple[list[dict], int | None]:
    cfg = replace(SHADOW_BASE, shadow_credit=shadow_credit)
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed, n_stable=0, t_drift=1000,
                      t_noise=1000, noise_end=1001, t_conflict=1000)
    eng = MemoryEngine(cfg, emb, world)
    worker = SignalWorker(eng, world)
    incumbent = world._spawn("like", 0, 0, entity=0, scope="work", birth=0)
    challenger = None
    promoted_at = None
    rows = []

    for t in range(SHADOW_T):
        if t == 10:
            challenger = world._spawn("dislike", 0, 0, entity=0,
                                      scope="casual", birth=t)
        beliefs = [incumbent] + ([challenger] if challenger else [])
        eng.observe([Event(b.id, b.value, b.phrasings[b.value][0]) for b in beliefs], t)
        query(eng, emb, world, incumbent, t)
        challenger_recall = float("nan")
        if challenger is not None:
            challenger_recall = float(query(eng, emb, world, challenger, t).n_useful > 0)
        eng.step(t)
        worker.process(t)
        challenger_memories = ([m for m in eng.mems.values()
                                if challenger is not None and m.belief_id == challenger.id]
                               if challenger is not None else [])
        in_m = int(any(m.pool is Pool.MEMORY for m in challenger_memories))
        if in_m and promoted_at is None:
            promoted_at = t
        rows.append({
            "scenario": "shadow_starvation",
            "preset": "shadow_on" if shadow_credit else "shadow_off",
            "seed": seed,
            "t": t,
            "recall": challenger_recall,
            "active": sum(m.pool is not Pool.ARCHIVE for m in eng.mems.values()),
            "n_c": sum(m.pool is Pool.CANDIDATE for m in eng.mems.values()),
            "n_m": sum(m.pool is Pool.MEMORY for m in eng.mems.values()),
            "n_a": sum(m.pool is Pool.ARCHIVE for m in eng.mems.values()),
            "challenger_in_m": in_m,
            "tension_depth": len(eng.tensions),
            "queries": int(challenger is not None),
            "query_hits": int(challenger_recall == 1.0),
            "selected": 0,
            "unique_relevant": 0,
            "pollution_m": float("nan"),
        })
    return rows, promoted_at


def run_stream(name: str, seed: int) -> list[dict]:
    cfg = PRESETS[name]
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(emb, seed=seed, t_drift=STREAM_T + 1, t_noise=0,
                      noise_end=STREAM_T, t_conflict=STREAM_T + 1,
                      noise_rate=6.0, query_rate=2.0)
    eng = MemoryEngine(cfg, emb, world)
    worker = SignalWorker(eng, world)
    rows = []

    for t in range(STREAM_T):
        events, queries = world.step(t)
        eng.observe(events, t)
        hits = selected = unique_relevant = 0
        for item in queries:
            belief = world.beliefs[item.target]
            result = query(eng, emb, world, belief, t)
            hits += int(result.n_useful > 0)
            selected += len(result.selected)
            unique_relevant += int(result.n_useful > 0)
        eng.step(t)
        worker.process(t)
        active = [m for m in eng.mems.values() if m.pool is not Pool.ARCHIVE]
        in_m = [m for m in active if m.pool is Pool.MEMORY]
        pollution_m = (sum(not world.valid(m.belief_id, m.value, t) for m in in_m) / len(in_m)
                       if in_m else float("nan"))
        rows.append({
            "scenario": "continuous_immigration",
            "preset": name,
            "seed": seed,
            "t": t,
            "recall": hits / len(queries) if queries else float("nan"),
            "active": len(active),
            "n_c": sum(m.pool is Pool.CANDIDATE for m in active),
            "n_m": len(in_m),
            "n_a": sum(m.pool is Pool.ARCHIVE for m in eng.mems.values()),
            "challenger_in_m": 0,
            "tension_depth": len(eng.tensions),
            "queries": len(queries),
            "query_hits": hits,
            "selected": selected,
            "unique_relevant": unique_relevant,
            "pollution_m": pollution_m,
        })
    return rows


def slope(rows: list[dict], field: str) -> float:
    tail = rows[-100:]
    return float(np.polyfit(np.arange(len(tail)), [row[field] for row in tail], 1)[0])


def finite_mean(values) -> float:
    values = [value for value in values if np.isfinite(value)]
    return mean(values) if values else float("nan")


def summarize_shadow(all_rows: list[dict], preset: str,
                     promotions: list[int | None]) -> dict:
    rows = [row for row in all_rows if row["preset"] == preset]
    before = [row["recall"] for row in rows if 10 <= row["t"] < 60]
    after = [row["recall"] for row in rows if 60 <= row["t"] < SHADOW_T]
    promoted = [value for value in promotions if value is not None]
    return {
        "scenario": "shadow_starvation",
        "preset": preset,
        "seeds": len(promotions),
        "recall_before_resolution": finite_mean(before),
        "recall_after_resolution": finite_mean(after),
        "promotion_rate": len(promoted) / len(promotions),
        "median_promotion_t": median(promoted) if promoted else float("nan"),
        "recall": float("nan"),
        "context_efficiency": float("nan"),
        "active_last100": float("nan"),
        "active_slope_last100": float("nan"),
        "archive_last100": float("nan"),
        "archive_slope_last100": float("nan"),
        "pollution_m_last100": float("nan"),
    }


def summarize_stream(all_rows: list[dict], preset: str) -> dict:
    by_seed = [[row for row in all_rows if row["preset"] == preset and row["seed"] == seed]
               for seed in STREAM_SEEDS]
    rows = [row for group in by_seed for row in group]
    queries = sum(row["queries"] for row in rows)
    selected = sum(row["selected"] for row in rows)
    return {
        "scenario": "continuous_immigration",
        "preset": preset,
        "seeds": len(by_seed),
        "recall_before_resolution": float("nan"),
        "recall_after_resolution": float("nan"),
        "promotion_rate": float("nan"),
        "median_promotion_t": float("nan"),
        "recall": sum(row["query_hits"] for row in rows) / queries,
        "context_efficiency": sum(row["unique_relevant"] for row in rows) / selected,
        "active_last100": mean(mean(row["active"] for row in group[-100:]) for group in by_seed),
        "active_slope_last100": mean(slope(group, "active") for group in by_seed),
        "archive_last100": mean(mean(row["n_a"] for row in group[-100:]) for group in by_seed),
        "archive_slope_last100": mean(slope(group, "n_a") for group in by_seed),
        "pollution_m_last100": finite_mean(
            row["pollution_m"] for group in by_seed for row in group[-100:]),
    }


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    trajectories = []
    summaries = []

    for enabled, preset in ((True, "shadow_on"), (False, "shadow_off")):
        promotions = []
        for seed in SHADOW_SEEDS:
            rows, promoted_at = run_shadow(seed, enabled)
            trajectories.extend(rows)
            promotions.append(promoted_at)
        summaries.append(summarize_shadow(trajectories, preset, promotions))

    stream_rows = []
    for preset in ("ours", "sfams_style", "flat"):
        for seed in STREAM_SEEDS:
            stream_rows.extend(run_stream(preset, seed))
        summaries.append(summarize_stream(stream_rows, preset))
    trajectories.extend(stream_rows)

    write_csv(os.path.join(OUT, "stress_trajectory.csv"), trajectories)
    write_csv(os.path.join(OUT, "stress_summary.csv"), summaries)
    for row in summaries:
        if row["scenario"] == "shadow_starvation":
            print(f'{row["preset"]:12s} pre={row["recall_before_resolution"]:.3f} '
                  f'post={row["recall_after_resolution"]:.3f} '
                  f'promote={row["promotion_rate"]:.3f}')
        else:
            print(f'{row["preset"]:12s} active={row["active_last100"]:.1f} '
                  f'd_active/dt={row["active_slope_last100"]:.3f} '
                  f'd_archive/dt={row["archive_slope_last100"]:.3f} '
                  f'recall={row["recall"]:.3f}')


if __name__ == "__main__":
    main()
