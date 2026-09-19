"""维护回路 + tension 消解。

V ← V·e^(−λ) + η·hit + η_s·shadow（可选 Ψ_div 冗余门乘在 η 项上）
→ promote/demote（滞回 θ_p>θ_d）→ 容量驱逐 → 闲置归档
→ tension 消解：synonym→merge（V=η_c·和）、update→新替旧、
  contradiction→异 scope 互免压制 / 同 scope 双方降权、collision→留痕。
"""
from __future__ import annotations

import math

import numpy as np

from ..core.confidence import discount_to
from ..core.consolidation import maybe_consolidate
from ..core.types import Memory, Pool


def _retention_scale(m, cfg) -> float:
    if not cfg.salience_on:
        return 1.0
    floor = max(0.0, min(0.999999, cfg.salience_retention_floor))
    salience = max(0.0, min(1.0, m.salience))
    excess = max(0.0, (salience - floor) / (1.0 - floor))
    return 1.0 + cfg.salience_retention_weight * excess


def run_maintenance(eng, t: int) -> None:
    cfg = eng.cfg
    active = [m for m in eng.mems.values() if m.pool is not Pool.ARCHIVE]

    div = {}
    if cfg.div_gate and len(active) > 1:
        E = np.stack([m.emb for m in active])
        n = np.linalg.norm(E, axis=1)
        S = E @ E.T / np.outer(n, n)
        np.fill_diagonal(S, -1)
        for m, row in zip(active, S):
            div[m.id] = 1 + cfg.alpha_div * math.tanh(
                cfg.beta_div * (cfg.tau_div - float(row.max())))

    for m in eng.mems.values():
        discount_to(m, t, cfg)
        gain = cfg.eta * m.d_hit
        if m.id in div:
            gain *= div[m.id]
        if cfg.shadow_credit:
            gain += cfg.eta_shadow * m.d_shadow
        scale = _retention_scale(m, cfg)
        if cfg.decay_mode == "linear":
            m.v = max(0.0, m.v + gain - cfg.lam / scale)
        else:
            m.v = m.v * math.exp(-cfg.lam / scale) + gain
        m.d_hit = m.d_shadow = 0.0

    if cfg.two_pool:
        for m in eng.mems.values():
            if m.pool is Pool.CANDIDATE and m.v > cfg.theta_p:
                m.pool = Pool.MEMORY
                eng.n_promote += 1
            elif m.pool is Pool.MEMORY and m.v < cfg.theta_d:
                m.pool = Pool.CANDIDATE
                eng.n_demote += 1

    if cfg.capacity_on:
        in_m = [m for m in eng.mems.values() if m.pool is Pool.MEMORY]
        while len(in_m) > cfg.cap_m:
            weakest = min(in_m, key=lambda m: (m.v, m.last_hit if m.last_hit is not None else m.birth, m.id))
            weakest.pool = Pool.CANDIDATE if cfg.two_pool else Pool.ARCHIVE
            in_m.remove(weakest)
            eng.n_evict += 1

    for m in eng.mems.values():
        idle_since = m.last_hit if m.last_hit is not None else m.birth
        horizon = cfg.idle_p * _retention_scale(m, cfg)
        if m.pool is Pool.CANDIDATE and t - idle_since > horizon:
            m.pool = Pool.ARCHIVE
            eng.n_archive += 1

    _emit_pending_conflicts(eng, t)
    maybe_consolidate(eng, t)


def _emit_pending_conflicts(eng, t: int) -> None:
    """tension 维护：剪掉死对/链塌缩对，把到达 tension_delay 的未决对
    以 conflict_pending 信号交给 worker 裁决（引擎不做语义判定）。
    verdict 经 submit_verdicts 回报后由 apply_resolution 消解。"""
    cfg = eng.cfg
    aged: list[tuple[int, int]] = []
    for key, tension in list(eng.tensions.items()):
        if tension.left not in eng.mems or tension.right not in eng.mems:
            del eng.tensions[key]
            continue
        a = follow_chain(eng, eng.mems[tension.left])
        b = follow_chain(eng, eng.mems[tension.right])
        if a.id == b.id:
            del eng.tensions[key]
            continue
        if t - tension.first_seen >= cfg.tension_delay:
            aged.append(key)
    if aged:
        eng.signals.emit("conflict_pending", aged, t, key="conflict",
                         merge=lambda o, n: o + [p for p in n if p not in o])


def follow_chain(eng, m: Memory) -> Memory:
    """沿 superseded/aggregated 指针追到当前代表条目。"""
    while m.superseded_by is not None or m.aggregated_into is not None:
        m = eng.mems[m.superseded_by or m.aggregated_into]
    return m


def apply_resolution(eng, a: Memory, b: Memory, verdict: str, t: int) -> None:
    """对已裁决的 (a, b) 施加消解动作。tension 的摘除与计数由调用方负责。"""
    cfg = eng.cfg
    if verdict == "synonym":
        keep, drop = (a, b) if a.v >= b.v else (b, a)
        keep.v = cfg.eta_c * (a.v + b.v)
        keep.evid += drop.evid
        keep.hits += drop.hits
        keep.src = keep.src | drop.src
        keep.last_seen = max(keep.last_seen, drop.last_seen)
        keep.conf_pos += drop.conf_pos
        keep.conf_neg += drop.conf_neg
        keep.conf_updated_at = t
        keep.salience = max(a.salience, b.salience)
        drop.superseded_by = keep.id
        drop.pool = Pool.ARCHIVE
        eng.n_merge += 1
    elif verdict == "update":
        keep, drop = (a, b) if a.birth >= b.birth else (b, a)
        keep.evid += 1
        keep.src = keep.src | drop.src
        keep.salience = max(a.salience, b.salience)
        drop.superseded_by = keep.id
        drop.pool = Pool.ARCHIVE
        eng.n_merge += 1
    elif verdict == "contradiction":
        pa = eng.semantics.scope(a.belief_id)
        pb = eng.semantics.scope(b.belief_id)
        if pa and pb and pa != pb:
            # 找到作用域 → 条件化合并表述（异 scope 可条件同真，不加负证据）
            text = (f"冲突版本（按作用域条件化）:\n"
                    f"- [{pa} | t={a.birth}] {a.text}\n"
                    f"- [{pb} | t={b.birth}] {b.text}")
            _make_aggregate(eng, a, b, t, text, pending=False)
        else:
            # 找不到作用域 → 双方降权让衰减自然裁决，
            # 同时收进聚合 memory 等人工终裁
            if cfg.confidence_on:
                a.conf_neg += cfg.conf_negative_evidence
                b.conf_neg += cfg.conf_negative_evidence
            a.v *= 0.5
            b.v *= 0.5
            text = (f"冲突版本（待裁决）:\n"
                    f"- [t={a.birth}] {a.text}\n"
                    f"- [t={b.birth}] {b.text}")
            _make_aggregate(eng, a, b, t, text, pending=True)
    else:
        eng.n_collision += 1


def _make_aggregate(eng, a, b, t: int, text: str, pending: bool) -> None:
    """同实体矛盾收编为聚合 memory：成员退居幕后（aggregated_into），
    聚合体带全部版本+时间戳出场。pending=True 表示冲突未裁决。"""
    emb = a.emb + b.emb
    n = float(np.linalg.norm(emb))
    if n > 0:
        emb = emb / n
    agg = Memory(id=eng.next_id(), belief_id=a.belief_id,
                 value=f"agg:{a.id}+{b.id}", text=text, emb=emb,
                 pool=Pool.CANDIDATE, v=max(a.v, b.v),
                 hits=a.hits + b.hits, evid=a.evid + b.evid,
                 birth=t, last_seen=t,
                 agg_members=(a.id, b.id), pending_review=pending,
                 src=a.src | b.src,
                 conf_pos=min(a.conf_pos, b.conf_pos),
                 conf_neg=max(a.conf_neg, b.conf_neg),
                 conf_updated_at=t,
                 salience=max(a.salience, b.salience),
                 novelty=max(a.novelty, b.novelty),
                 scene=a.scene if a.scene == b.scene else "")
    eng.mems[agg.id] = agg
    a.aggregated_into = agg.id
    b.aggregated_into = agg.id
    eng.n_agg += 1
