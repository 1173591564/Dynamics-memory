"""读取回路：统一分 → θ 门 → 带内压制 → 填 K → 三档记账。

score = s(m,q) + π_pool + α·e^(−λ(t−birth))
记账：selected（全额）/ shadow（过线但被压制，η_s 部分增益）/ shortlisted（仅统计）。
压制对全部进 tension backlog 待裁决；入选记忆带未决 tension 时对手版本
一并端出（contested），冲突在检索时自然暴露；归档项被选中 → 复活回 C。
"""
from __future__ import annotations

import math
import re

import numpy as np

from ..core.confidence import discount_to, projected
from ..core.types import Memory, Pool, Query, Retrieval, is_visible
from ..embed.base import cosine

_ASCII_TOK = re.compile(r"[a-z0-9_#.+-]{2,}")
_CJK_RUN = re.compile(r"[一-鿿]{2,}")


def _lex_tokens(text: str) -> set[str]:
    text = text.lower()
    toks = set(_ASCII_TOK.findall(text))
    for run in _CJK_RUN.findall(text):
        toks.update(run[i:i + 2] for i in range(len(run) - 1))
    return toks


def _lexical_scores(eng, q: Query) -> dict[int, float]:
    """IDF 加权的 query 项覆盖率：记忆包含的稀有 query 词越多分越高。

    ASCII 标识符（PR号/hash/文件名）与中文 bigram 各占一路；
    权重 = log((N+1)/(df+0.5))，分母为 query 全部 token 的权重和。
    """
    qtok = _lex_tokens(q.text)
    if not qtok:
        return {}
    toks_by_id: dict[int, set[str]] = {}
    df: dict[str, int] = {}
    for m in eng.mems.values():
        if not is_visible(m):
            continue   # 死/隐藏记忆不进 DF，否则压 IDF 抬门槛
        mt = _lex_tokens(m.text)
        toks_by_id[m.id] = mt
        for tok in mt:
            df[tok] = df.get(tok, 0) + 1
    n = max(len(toks_by_id), 1)
    # 稀有词门控：query 没有低 df token 时整条通道关闭——
    # 泛化 query（"进度怎么样"）下 lex 是纯噪音，不能稀释语义分
    if not any(df.get(tok, 0) <= max(3, int(0.15 * n)) for tok in qtok):
        return {}

    def idf(tok: str) -> float:
        return math.log((n + 1) / (df.get(tok, 0) + 0.5))

    denom = sum(idf(t) for t in qtok) or 1.0
    return {mid: sum(idf(t) for t in (qtok & mt)) / denom
            for mid, mt in toks_by_id.items() if qtok & mt}


def _prior(m: Memory, cfg) -> float:
    if m.pool is Pool.MEMORY:
        return cfg.pi_m if cfg.two_pool else 0.0
    if m.pool is Pool.ARCHIVE:
        return cfg.pi_a
    return 0.0


def run_retrieve(eng, q_emb: np.ndarray, q: Query, t: int) -> Retrieval:
    cfg = eng.cfg
    ret = Retrieval()

    lex = _lexical_scores(eng, q) if cfg.lex_weight > 0 else {}
    scored = []
    for m in eng.mems.values():
        if (not is_visible(m)
                and not (cfg.archive_retrieval and m.pool is Pool.ARCHIVE)):
            continue
        discount_to(m, t, cfg)
        s = cosine(q_emb, m.emb)
        if lex:
            s += cfg.lex_weight * lex.get(m.id, 0.0)
        quality = s + _prior(m, cfg)
        fresh = cfg.fresh_alpha * math.exp(-cfg.lam * (t - m.birth))
        scored.append((quality + fresh, quality, s, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    shortlist = scored[: cfg.shortlist_n]

    selected: list[Memory] = []

    def _try_select(m: Memory) -> bool:
        rival = max(selected, key=lambda r: cosine(m.emb, r.emb), default=None)
        rsim = cosine(m.emb, rival.emb) if rival else 0.0
        if (cfg.suppression_on and rival is not None and rsim > cfg.tau_sim
                and m.niche_pair != rival.id):
            ret.suppressed.append((m.id, rival.id))
            m.suppressed_by = rival.id
            m.shadow_hits += 1
            if m.id in rival.derived_from or rival.id in m.derived_from:
                return False   # 派生血缘：不裁判、不进 backlog、不发 shadow 信用
            if cfg.shadow_credit:
                # 恒延迟记账：压制路径不裁判（引擎无 LLM），本地谓词先算，
                # verdict 经 submit_verdicts 到达时结算 shadow 信用
                rel = eng.semantics.relevant(m.belief_id, m.value, q, t)
                eng._record_shadow_pending(m, rival, t, rel)
                if not cfg.tension_on:
                    # tension 关闭时该对不进 backlog，直接发信号求 verdict
                    # 供 shadow 结算（merge 去重防 payload 膨胀）
                    eng.signals.emit(
                        "conflict_pending", [tuple(sorted((m.id, rival.id)))],
                        t, key="conflict",
                        merge=lambda o, n: o + [p for p in n if p not in o])
            eng.add_tension(m.id, rival.id, t)   # 压制对全部进 tension 待裁决
            return False
        return True

    # 质量门内分行：trusted（confidence 关或 projected>=θ_conf）先行压制/填 K；
    # 低置信行只能以 provisional 进场——至多 provisional_k 条、selected 有位、
    # 且无 trusted 入选或其质量 ≥ 最佳 trusted 质量 + provisional_margin。
    # 置信门控本身不是负面证据，不发 shadow credit。
    low_conf: list[tuple[float, Memory]] = []
    best_trusted_quality: float | None = None
    for _, quality, s, m in shortlist:
        if len(selected) == cfg.k:
            break
        if quality < cfg.theta:
            m.shortlisted += 1
            continue
        if cfg.confidence_on and projected(m, cfg) < cfg.theta_conf:
            low_conf.append((quality, m))
            continue
        if _try_select(m):
            selected.append(m)
            if best_trusted_quality is None or quality > best_trusted_quality:
                best_trusted_quality = quality

    n_prov = 0
    for quality, m in low_conf:
        if len(selected) == cfg.k or n_prov == cfg.provisional_k:
            break
        if (best_trusted_quality is not None
                and quality < best_trusted_quality + cfg.provisional_margin):
            continue
        if _try_select(m):
            selected.append(m)
            ret.provisional.append(m)
            n_prov += 1

    if not cfg.defer_credit:
        ret.credited = True
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
                    and is_visible(rival)):
                ret.contested.append((m, rival))

    ret.selected = selected
    ret.n_shortlisted = len(shortlist)

    # ---- 信号发射：thin_recall 在此发；feedback_pending 由 engine.feedback
    # 携带 question/answer 发射（retrieve 时还没有答案，无法归因）----
    if len(selected) < cfg.k:
        eng.signals.emit("thin_recall",
                         {"q": q.text, "n_selected": len(selected)}, t,
                         key=f"thin:{t}", merge=lambda o, n: o)
    return ret
