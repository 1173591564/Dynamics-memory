"""读取回路：统一分 → θ 门 → 带内压制 → 填 K → 三档记账。

score = s(m,q) + π_pool + α·e^(−λ(t−birth))
记账：selected（全额）/ shadow（过线但被压制，η_s 部分增益）/ shortlisted（仅统计）。
压制对全部进 tension backlog 待裁决；入选记忆带未决 tension 时对手版本
一并端出（contested），冲突在检索时自然暴露；归档项被选中 → 复活回 C。
"""
from __future__ import annotations

import math

import numpy as np

from ..core.types import Memory, Pool, Query, Retrieval
from ..embed.base import cosine


def _prior(m: Memory, cfg) -> float:
    if m.pool is Pool.MEMORY:
        return cfg.pi_m if cfg.two_pool else 0.0
    if m.pool is Pool.ARCHIVE:
        return cfg.pi_a
    return 0.0


def run_retrieve(eng, q_emb: np.ndarray, q: Query, t: int) -> Retrieval:
    cfg = eng.cfg
    ret = Retrieval()

    scored = []
    for m in eng.mems.values():
        if (m.superseded_by is not None or m.aggregated_into is not None
                or (m.pool is Pool.ARCHIVE and not cfg.archive_retrieval)):
            continue
        s = cosine(q_emb, m.emb)
        quality = s + _prior(m, cfg)
        fresh = cfg.fresh_alpha * math.exp(-cfg.lam * (t - m.birth))
        scored.append((quality + fresh, quality, s, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    shortlist = scored[: cfg.shortlist_n]

    selected: list[Memory] = []
    for _, quality, s, m in shortlist:
        if len(selected) == cfg.k:
            break
        if quality < cfg.theta:
            m.shortlisted += 1
            continue
        rival = max(selected, key=lambda r: cosine(m.emb, r.emb), default=None)
        rsim = cosine(m.emb, rival.emb) if rival else 0.0
        if (cfg.suppression_on and rival is not None and rsim > cfg.tau_sim
                and m.niche_pair != rival.id):
            ret.suppressed.append((m.id, rival.id))
            verdict = eng.semantics.judge(
                m.belief_id, m.value, rival.belief_id, rival.value)
            eng.add_tension(m.id, rival.id, t)   # 压制对全部进 tension 待裁决
            m.suppressed_by = rival.id
            m.shadow_hits += 1
            if (cfg.shadow_credit
                    and verdict != "synonym"
                    and eng.semantics.relevant(m.belief_id, m.value, q, t)):
                m.d_shadow += 1.0
                m.last_hit = t
                if m.pool is Pool.ARCHIVE:
                    m.pool = Pool.CANDIDATE if cfg.two_pool else Pool.MEMORY
                    eng.n_revive += 1
            continue
        selected.append(m)

    for m in selected:
        is_relevant = eng.semantics.relevant(m.belief_id, m.value, q, t)
        if is_relevant:
            ret.n_useful += 1
        if is_relevant or not cfg.useful_hit:
            m.last_hit = t
            if m.pool is Pool.ARCHIVE:
                m.pool = Pool.CANDIDATE if cfg.two_pool else Pool.MEMORY
                eng.n_revive += 1
            m.hits += 1
            m.d_hit += 1.0

    # 入选记忆若有未决 tension，对手版本一并端出（带时间戳给下游裁决语境），
    # 冲突在检索时自然暴露，不单独自信出场
    sel_ids = {m.id for m in selected}
    for key in eng.tensions:
        a, b = eng.mems.get(key[0]), eng.mems.get(key[1])
        if a is None or b is None:
            continue
        for m, rival in ((a, b), (b, a)):
            if (m.id in sel_ids and rival.id not in sel_ids
                    and rival.superseded_by is None
                    and rival.aggregated_into is None
                    and rival.pool is not Pool.ARCHIVE):
                ret.contested.append((m, rival))

    ret.selected = selected
    ret.n_shortlisted = len(shortlist)
    return ret
