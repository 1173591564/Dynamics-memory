"""把 trajectory.csv 聚合成可重复生成的动力学轨迹图。"""
from __future__ import annotations

import csv
import math
import os
from collections import defaultdict

import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "runs")
T_MAX = 219
WINDOW = 10
PHASE_LINES = ((60, "drift"), (100, "noise burst"),
               (140, "incumbent"), (160, "challenger"))


def load_rows(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for source in csv.DictReader(f):
            row = {"preset": source["preset"], "phase": source["phase"]}
            for key, value in source.items():
                if key not in row:
                    row[key] = float(value)
            rows.append(row)
    return rows


def finite_mean(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value)]
    return sum(values) / len(values) if values else float("nan")


def aggregate(rows: list[dict]) -> dict[str, dict[int, dict[str, float]]]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["preset"], int(row["t"]))].append(row)
    result = defaultdict(dict)
    mean_fields = (
        "pollution", "pollution_c", "pollution_m", "n_c", "n_m", "n_a",
        "tension_depth", "scissors_gap", "n_promote", "n_demote", "n_evict",
        "n_archive", "n_revive", "n_tension", "n_resolve",
    )
    for (preset, t), group in groups.items():
        queries = sum(row["n_queries"] for row in group)
        selected = sum(row["n_selected"] for row in group)
        unique_selected = sum(row["n_unique_selected"] for row in group)
        values = {
            "recall": (sum(row["n_query_hits"] for row in group) / queries
                       if queries else float("nan")),
            "efficiency": (sum(row["n_unique_relevant"] for row in group) / selected
                           if selected else float("nan")),
            "redundancy": (1.0 - unique_selected / selected
                           if selected else float("nan")),
        }
        values.update({field: finite_mean([row[field] for row in group])
                       for field in mean_fields})
        result[preset][t] = values
    return result


def trailing(values: list[float], window: int = WINDOW) -> list[float]:
    smoothed = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        smoothed.append(finite_mean(values[start:index + 1]))
    return smoothed


def series(data, preset: str, field: str) -> tuple[list[int], list[float]]:
    x = sorted(data[preset])
    return x, trailing([data[preset][t][field] for t in x])


def phase_lines(ax, labels: bool = False) -> None:
    for x, label in PHASE_LINES:
        ax.axvline(x, color="0.72", linewidth=0.8, linestyle="--")
        if labels:
            ax.text(x + 1, 0.98, label, transform=ax.get_xaxis_transform(),
                    fontsize=7, color="0.35", va="top")
    ax.set_xlim(0, T_MAX)
    ax.grid(True, color="0.9", linewidth=0.6)


def plot_line(ax, data, preset: str, field: str, label: str, **kwargs) -> None:
    x, y = series(data, preset, field)
    ax.plot(x, y, label=label, linewidth=1.6, **kwargs)


def plot_dynamics(data) -> str:
    fig, axes = plt.subplots(3, 2, figsize=(13, 11), constrained_layout=True)
    fig.suptitle("Hybrid memory dynamics — full design (10-seed mean)", fontsize=15)

    ax = axes[0, 0]
    plot_line(ax, data, "ours", "recall", "Recall@5")
    plot_line(ax, data, "ours", "efficiency", "Context efficiency")
    ax.set(title="Query quality (10-step trailing mean)", ylabel="Fraction")
    ax.set_ylim(0, 1.05)
    ax.legend()
    phase_lines(ax, labels=True)

    ax = axes[0, 1]
    plot_line(ax, data, "ours", "pollution", "Active pools")
    plot_line(ax, data, "ours", "pollution_c", "Candidate pool")
    plot_line(ax, data, "ours", "pollution_m", "Memory pool")
    ax.set(title="Invalid / stale / noise memory share", ylabel="Pollution fraction")
    ax.set_ylim(-0.03, 1.03)
    ax.legend()
    phase_lines(ax, labels=True)

    ax = axes[1, 0]
    x, c = series(data, "ours", "n_c")
    _, m = series(data, "ours", "n_m")
    _, a = series(data, "ours", "n_a")
    candidate_line = ax.plot(x, c, label="Candidate pool C", linewidth=1.6)[0]
    archive_line = ax.plot(x, a, label="Cold archive A", linewidth=1.6,
                           color="tab:purple")[0]
    ax.set(title="Pool population (archive is cold, not active)",
           ylabel="Candidate / archive entries (count)")
    twin = ax.twinx()
    memory_line = twin.plot(x, m, label="Memory pool M", linewidth=1.6,
                            color="tab:orange")[0]
    capacity_line = twin.axhline(8, label="M capacity = 8", linewidth=1.0,
                                 linestyle=":", color="0.35")
    twin.set_ylabel("Memory pool entries (count)")
    lines = (candidate_line, archive_line, memory_line, capacity_line)
    ax.legend(lines, [line.get_label() for line in lines])
    phase_lines(ax)

    ax = axes[1, 1]
    plot_line(ax, data, "ours", "tension_depth", "Backlog depth")
    plot_line(ax, data, "ours", "n_tension", "New tensions / seed / step")
    plot_line(ax, data, "ours", "n_resolve", "Resolved / seed / step")
    ax.set(title="Delayed contradiction-control loop", ylabel="Pairs or events (count)")
    ax.legend()
    phase_lines(ax)

    ax = axes[2, 0]
    for field, label in (("n_promote", "Promote"), ("n_demote", "Demote"),
                         ("n_evict", "Capacity evict"), ("n_revive", "Archive revive")):
        plot_line(ax, data, "ours", field, label)
    ax.set(title="Lifecycle control activity", xlabel="Simulation step t",
           ylabel="Events / seed / step")
    ax.legend(ncol=2)
    phase_lines(ax)

    ax = axes[2, 1]
    plot_line(ax, data, "ours", "scissors_gap", "Valid V − invalid V")
    ax.axhline(0, color="0.35", linewidth=0.9)
    ax.set(title="Vitality separation", xlabel="Simulation step t",
           ylabel="Mean vitality difference")
    ax.legend()
    phase_lines(ax)

    fig.text(0.5, -0.01,
             "Source: experiments/out/trajectory.csv · t=0–219 · 10 seeds · "
             "query ratios aggregated by counts; displayed lines use a 10-step trailing mean.",
             ha="center", fontsize=8, color="0.35")
    path = os.path.join(OUT, "dynamics.png")
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_ablations(data) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    fig.suptitle("Hybrid memory baseline and ablation trajectories (10-seed mean)", fontsize=15)

    ax = axes[0, 0]
    for preset, label in (("ours", "Full design"), ("abl_no_shadow", "No shadow credit"),
                          ("abl_no_tension", "No tension loop"),
                          ("sfams_style", "SF-AMS-style"), ("flat", "Flat cosine")):
        plot_line(ax, data, preset, "recall", label)
    ax.set(title="Recall@5 (10-step trailing mean)", ylabel="Queries covered (fraction)")
    ax.set_ylim(0, 1.05)
    ax.legend(ncol=2, fontsize=8)
    phase_lines(ax, labels=True)

    ax = axes[0, 1]
    for preset, label in (("ours", "Full design"), ("abl_no_shadow", "No shadow credit"),
                          ("abl_no_tension", "No tension loop"),
                          ("sfams_style", "SF-AMS-style"), ("flat", "Flat cosine")):
        plot_line(ax, data, preset, "efficiency", label)
    ax.set(title="Unique useful facts per context slot", ylabel="Context efficiency")
    ax.set_ylim(0, 1.05)
    ax.legend(ncol=2, fontsize=8)
    phase_lines(ax, labels=True)

    ax = axes[1, 0]
    for preset, label in (("ours", "Full design"),
                          ("abl_selected_credit", "Selected-hit credit"),
                          ("abl_no_tension", "No tension loop"),
                          ("sfams_style", "SF-AMS-style")):
        plot_line(ax, data, preset, "pollution_m", label)
    ax.set(title="Memory-pool pollution", xlabel="Simulation step t",
           ylabel="Invalid / stale / noise share")
    ax.set_ylim(-0.03, 1.03)
    ax.legend(fontsize=8)
    phase_lines(ax)

    ax = axes[1, 1]
    for preset, label in (("ours", "Full design"),
                          ("abl_no_capacity", "No capacity"),
                          ("abl_no_twopool", "Single pool"),
                          ("sfams_style", "SF-AMS-style")):
        plot_line(ax, data, preset, "n_m", label)
    ax.axhline(8, label="Configured capacity", linewidth=1.0,
               linestyle=":", color="0.35")
    ax.set(title="Memory-pool population", xlabel="Simulation step t",
           ylabel="Entries (count)")
    ax.legend(fontsize=8)
    phase_lines(ax)

    fig.text(0.5, -0.01,
             "Source: experiments/out/trajectory.csv · t=0–219 · 10 seeds · "
             "all displayed lines use a 10-step trailing mean.",
             ha="center", fontsize=8, color="0.35")
    path = os.path.join(OUT, "ablations.png")
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path


def load_stress_rows(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for source in csv.DictReader(f):
            row = {"scenario": source["scenario"], "preset": source["preset"]}
            for key, value in source.items():
                if key not in row:
                    row[key] = float(value)
            rows.append(row)
    return rows


def aggregate_stress(rows: list[dict]) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["scenario"], row["preset"], int(row["t"]))].append(row)
    result = defaultdict(lambda: defaultdict(dict))
    for (scenario, preset, t), group in groups.items():
        result[scenario][preset][t] = {
            field: finite_mean([row[field] for row in group])
            for field in ("recall", "active", "n_a", "challenger_in_m")
        }
    return result


def stress_series(data, scenario: str, preset: str, field: str,
                  window: int = 1) -> tuple[list[int], list[float]]:
    x = sorted(data[scenario][preset])
    values = [data[scenario][preset][t][field] for t in x]
    return x, trailing(values, window)


def plot_stress(data) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    fig.suptitle("Hybrid memory stress protocols", fontsize=15)

    ax = axes[0, 0]
    for preset, label in (("shadow_on", "Shadow credit on"),
                          ("shadow_off", "Shadow credit off")):
        x, y = stress_series(data, "shadow_starvation", preset, "recall", 5)
        ax.plot(x, y, label=label, linewidth=1.8)
    ax.axvline(10, color="0.72", linewidth=0.8, linestyle="--")
    ax.axvline(60, color="0.72", linewidth=0.8, linestyle="--")
    ax.text(11, 0.98, "challenger arrives", transform=ax.get_xaxis_transform(),
            fontsize=7, color="0.35", va="top")
    ax.text(61, 0.98, "tension resolves", transform=ax.get_xaxis_transform(),
            fontsize=7, color="0.35", va="top")
    ax.set(title="Starved challenger recall (5-step trailing mean)",
           ylabel="Queries covered (fraction)", xlim=(0, 99), ylim=(0, 1.05))
    ax.legend()
    ax.grid(True, color="0.9", linewidth=0.6)

    ax = axes[0, 1]
    for preset, label in (("shadow_on", "Shadow credit on"),
                          ("shadow_off", "Shadow credit off")):
        x, y = stress_series(data, "shadow_starvation", preset,
                             "challenger_in_m", 1)
        ax.plot(x, y, label=label, linewidth=1.8)
    ax.axvline(10, color="0.72", linewidth=0.8, linestyle="--")
    ax.axvline(60, color="0.72", linewidth=0.8, linestyle="--")
    ax.set(title="Seeds with challenger promoted to M",
           ylabel="Promotion probability", xlim=(0, 99), ylim=(0, 1.05))
    ax.legend()
    ax.grid(True, color="0.9", linewidth=0.6)

    ax = axes[1, 0]
    for preset, label in (("ours", "Full design"),
                          ("sfams_style", "SF-AMS-style"),
                          ("flat", "Flat cosine")):
        x, y = stress_series(data, "continuous_immigration", preset, "active", 10)
        ax.plot(x, y, label=label, linewidth=1.8)
    ax.set_yscale("symlog", linthresh=10)
    ax.set(title="Continuous noise immigration: active state",
           xlabel="Simulation step t", ylabel="Active entries (count, symlog)",
           xlim=(0, 399))
    ax.legend()
    ax.grid(True, color="0.9", linewidth=0.6)

    ax = axes[1, 1]
    for preset, label in (("ours", "Full design"),
                          ("sfams_style", "SF-AMS-style"),
                          ("flat", "Flat cosine")):
        x, y = stress_series(data, "continuous_immigration", preset, "n_a", 10)
        ax.plot(x, y, label=label, linewidth=1.8)
    ax.set(title="Continuous noise immigration: cold archive",
           xlabel="Simulation step t", ylabel="Archived entries (count)",
           xlim=(0, 399))
    ax.legend()
    ax.grid(True, color="0.9", linewidth=0.6)

    fig.text(0.5, -0.01,
             "Source: experiments/out/stress_trajectory.csv · shadow: 20 seeds, t=0–99 · "
             "continuous immigration: 5 seeds, t=0–399.",
             ha="center", fontsize=8, color="0.35")
    path = os.path.join(OUT, "stress.png")
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    data = aggregate(load_rows(os.path.join(OUT, "trajectory.csv")))
    print(plot_dynamics(data))
    print(plot_ablations(data))
    stress_path = os.path.join(OUT, "stress_trajectory.csv")
    if os.path.exists(stress_path):
        print(plot_stress(aggregate_stress(load_stress_rows(stress_path))))


if __name__ == "__main__":
    main()
