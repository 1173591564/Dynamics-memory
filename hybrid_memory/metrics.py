"""每步度量采集。全部指标有 ground truth 精确值。"""
from __future__ import annotations

import csv
from dataclasses import dataclass

from .core.types import Pool, Retrieval


@dataclass
class QueryCounts:
    queries: int = 0
    hits: int = 0
    selected: int = 0
    relevant: int = 0
    unique_selected: int = 0
    unique_relevant: int = 0

    def add(self, retrieval: Retrieval) -> None:
        self.queries += 1
        self.hits += int(retrieval.n_useful > 0)
        self.selected += len(retrieval.selected)
        self.relevant += retrieval.n_useful
        self.unique_selected += len({(m.belief_id, m.value) for m in retrieval.selected})
        self.unique_relevant += int(retrieval.n_useful > 0)


@dataclass
class StepMetrics:
    t: int
    phase: str = ""
    n_queries: int = 0
    n_query_hits: int = 0
    n_selected: int = 0
    n_relevant: int = 0
    n_unique_selected: int = 0
    n_unique_relevant: int = 0
    recall_at_k: float = 0.0     # query 目标被 selected 覆盖的比例
    precision_at_k: float = 0.0  # selected 中属于 query 目标且值有效的比例
    context_efficiency: float = 0.0
    redundancy: float = 0.0
    pollution: float = 0.0       # 活跃池中死 belief/噪声/旧值占比
    pollution_c: float = 0.0
    pollution_m: float = 0.0
    n_c: int = 0
    n_m: int = 0
    n_a: int = 0
    displacement: int = 0        # 本步容量驱逐次数
    tension_depth: int = 0
    scissors_gap: float = 0.0    # 有效组均 V − 污染组均 V
    n_promote: int = 0
    n_demote: int = 0
    n_merge: int = 0
    n_evict: int = 0
    n_archive: int = 0
    n_revive: int = 0
    n_tension: int = 0
    n_resolve: int = 0


class Recorder:
    def __init__(self):
        self.rows: list[StepMetrics] = []

    def record(self, eng, t: int, phase: str, queries: QueryCounts) -> None:
        active = [m for m in eng.mems.values() if m.pool is not Pool.ARCHIVE]
        in_c = [m for m in active if m.pool is Pool.CANDIDATE]
        in_m = [m for m in active if m.pool is Pool.MEMORY]

        def pollution(items) -> float:
            if not items:
                return float("nan")
            dead = sum(not eng.semantics.valid(m.belief_id, m.value, t) for m in items)
            return dead / len(items)

        valid_v = [m.v for m in active if eng.semantics.valid(m.belief_id, m.value, t)]
        invalid_v = [m.v for m in active if not eng.semantics.valid(m.belief_id, m.value, t)]
        gap = (sum(valid_v) / len(valid_v) - sum(invalid_v) / len(invalid_v)
               if valid_v and invalid_v else float("nan"))
        sizes = eng.pool_sizes()
        recall = queries.hits / queries.queries if queries.queries else float("nan")
        precision = (queries.relevant / queries.selected if queries.selected
                     else (0.0 if queries.queries else float("nan")))
        efficiency = (queries.unique_relevant / queries.selected if queries.selected
                      else (0.0 if queries.queries else float("nan")))
        redundancy = (1.0 - queries.unique_selected / queries.selected
                      if queries.selected else (0.0 if queries.queries else float("nan")))
        self.rows.append(StepMetrics(
            t=t,
            phase=phase,
            n_queries=queries.queries,
            n_query_hits=queries.hits,
            n_selected=queries.selected,
            n_relevant=queries.relevant,
            n_unique_selected=queries.unique_selected,
            n_unique_relevant=queries.unique_relevant,
            recall_at_k=recall,
            precision_at_k=precision,
            context_efficiency=efficiency,
            redundancy=redundancy,
            pollution=pollution(active),
            pollution_c=pollution(in_c),
            pollution_m=pollution(in_m),
            n_c=sizes["C"], n_m=sizes["M"], n_a=sizes["A"],
            displacement=eng.n_evict,
            tension_depth=len(eng.tensions),
            scissors_gap=gap,
            n_promote=eng.n_promote,
            n_demote=eng.n_demote,
            n_merge=eng.n_merge,
            n_evict=eng.n_evict,
            n_archive=eng.n_archive,
            n_revive=eng.n_revive,
            n_tension=eng.n_tension,
            n_resolve=eng.n_resolve,
        ))
        for name in ("n_promote", "n_demote", "n_merge", "n_evict", "n_archive",
                     "n_revive", "n_tension", "n_resolve"):
            setattr(eng, name, 0)

    def to_csv(self, path: str) -> None:
        if not self.rows:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(StepMetrics.__dataclass_fields__))
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row.__dict__)
