"""绘制 embedding-3 真实对话弱监督检索结果。"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from hybrid_memory.datasets.real_chat import load_interaction_units

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out" / "runs"
DATA = ROOT / "data" / "l0-tencent-consistency-check.jsonl"
RANKS = OUT / "real-embedding-3-2048-ranks.csv"


def load_ranks() -> list[dict]:
    with RANKS.open(newline="", encoding="utf-8") as f:
        return [{
            "unit_id": int(row["unit_id"]),
            "rank": int(row["rank"]),
            "target_similarity": float(row["target_similarity"]),
            "hard_negative_similarity": float(row["hard_negative_similarity"]),
        } for row in csv.DictReader(f)]


def grouped_recall(values: list[tuple[str, int]], order: list[str]) -> tuple[list[float], list[float]]:
    r1 = []
    r5 = []
    for label in order:
        ranks = [rank for group, rank in values if group == label]
        r1.append(sum(rank <= 1 for rank in ranks) / len(ranks))
        r5.append(sum(rank <= 5 for rank in ranks) / len(ranks))
    return r1, r5


def main() -> None:
    units = load_interaction_units(DATA)
    rows = load_ranks()
    ranks = np.array([row["rank"] for row in rows])
    positives = np.array([row["target_similarity"] for row in rows])
    negatives = np.array([row["hard_negative_similarity"] for row in rows])

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    fig.suptitle("Zhipu embedding-3 — interaction-unit user→assistant retrieval", fontsize=15)

    ax = axes[0, 0]
    k = np.arange(1, 31)
    ax.plot(k, [(ranks <= value).mean() for value in k], linewidth=1.8)
    ax.set(title="Cumulative Recall@K", xlabel="K (retrieved interaction units)",
           ylabel="Queries with target retrieved (fraction)", xlim=(1, 30), ylim=(0, 1.03))
    ax.grid(True, color="0.9", linewidth=0.6)

    ax = axes[0, 1]
    bins = np.linspace(min(positives.min(), negatives.min()),
                       max(positives.max(), negatives.max()), 20)
    ax.hist(positives, bins=bins, alpha=0.65, label="Paired assistant text", density=True)
    ax.hist(negatives, bins=bins, alpha=0.65, label="Hardest non-paired assistant text", density=True)
    ax.set(title="Cosine-similarity overlap", xlabel="Cosine similarity",
           ylabel="Density")
    ax.legend()
    ax.grid(True, color="0.9", linewidth=0.6)

    query_order = ["≤10", "11–30", "31–100", "101–500", ">500"]
    query_groups = []
    for unit, row in zip(units, rows):
        length = len(unit.user_text)
        label = ("≤10" if length <= 10 else "11–30" if length <= 30
                 else "31–100" if length <= 100 else "101–500" if length <= 500
                 else ">500")
        query_groups.append((label, row["rank"]))
    r1, r5 = grouped_recall(query_groups, query_order)
    x = np.arange(len(query_order))
    width = 0.36
    ax = axes[1, 0]
    ax.bar(x - width / 2, r1, width, label="Recall@1")
    ax.bar(x + width / 2, r5, width, label="Recall@5")
    ax.set(title="Retrieval by user-query length", xlabel="Query length (characters)",
           ylabel="Target retrieved (fraction)", xticks=x, xticklabels=query_order,
           ylim=(0, 1.03))
    ax.legend()
    ax.grid(True, axis="y", color="0.9", linewidth=0.6)

    turn_order = ["1", "2–3", "4–10", ">10"]
    turn_groups = []
    for unit, row in zip(units, rows):
        turns = unit.assistant_turns
        label = "1" if turns == 1 else "2–3" if turns <= 3 else "4–10" if turns <= 10 else ">10"
        turn_groups.append((label, row["rank"]))
    r1, r5 = grouped_recall(turn_groups, turn_order)
    x = np.arange(len(turn_order))
    ax = axes[1, 1]
    ax.bar(x - width / 2, r1, width, label="Recall@1")
    ax.bar(x + width / 2, r5, width, label="Recall@5")
    ax.set(title="Retrieval by assistant-turn count", xlabel="Assistant turns in target unit",
           ylabel="Target retrieved (fraction)", xticks=x, xticklabels=turn_order,
           ylim=(0, 1.03))
    ax.legend()
    ax.grid(True, axis="y", color="0.9", linewidth=0.6)

    fig.text(0.5, -0.01,
             "Source: l0-tencent-consistency-check.jsonl · 106 basic interaction units · "
             "embedding-3, 2048 dimensions · weak supervision: the unit's assistant text is the target.",
             ha="center", fontsize=8, color="0.35")
    path = OUT / "real-embedding-3-2048.png"
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(path)


if __name__ == "__main__":
    main()
