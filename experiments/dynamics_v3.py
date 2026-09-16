"""v3 累积消融配置与统一诊断口径。"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from hybrid_memory.config import Cfg
from hybrid_memory.core.confidence import projected
from hybrid_memory.core.types import Pool

FEATURE_SETS = {
    "p01": (),
    "r1_confidence": ("confidence",),
    "r12_salience": ("confidence", "salience"),
    "r123_novelty": ("confidence", "salience", "novelty"),
    "r1234_full": ("confidence", "salience", "novelty", "consolidation"),
}


def configure(cfg: Cfg, name: str) -> Cfg:
    if name not in FEATURE_SETS:
        raise ValueError(f"unknown feature set: {name}")
    enabled = set(FEATURE_SETS[name])
    return replace(
        cfg,
        confidence_on="confidence" in enabled,
        salience_on="salience" in enabled,
        novelty_on="novelty" in enabled,
        consolidation_on="consolidation" in enabled,
    )


def diagnostics(eng) -> dict:
    cfg = eng.cfg
    active = [m for m in eng.mems.values()
              if m.pool is not Pool.ARCHIVE
              and m.superseded_by is None
              and m.aggregated_into is None]
    conf = [projected(m, cfg) for m in active] if cfg.confidence_on else []
    salience = [m.salience for m in active]
    novelty = [m.novelty for m in active]
    return {
        "active": len(active),
        "trusted_active": (sum(c >= cfg.theta_conf for c in conf)
                           if conf else None),
        "low_conf_active": (sum(c < cfg.theta_conf for c in conf)
                            if conf else None),
        "mean_confidence": (round(float(np.mean(conf)), 4) if conf else None),
        "mean_salience": (round(float(np.mean(salience)), 4)
                          if salience else None),
        "mean_novelty": (round(float(np.mean(novelty)), 4)
                         if novelty else None),
        "reflections": sum(m.kind == "reflection" for m in eng.mems.values()),
        "active_reflections": sum(m.kind == "reflection" for m in active),
        "consolidation_pending": len(eng._consolidation_pending),
        "n_consolidate": eng.n_consolidate,
    }
