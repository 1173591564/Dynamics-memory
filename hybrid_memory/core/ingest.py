"""写入回路：Event → ingest dedup → 新条目进 C（单层模式直接进 M）。

dedup 语义：sim>τ_dup 且判为 synonym（同 belief 同值）→ evid++，不新增；
sim>τ_dup 但非同义（update/contradiction/collision）→ 新增 + tension 对。
"""
from __future__ import annotations

from ..core.confidence import discount_to
from ..core.types import Event, Memory, Pool, is_visible
from ..embed.base import cosine


def run_ingest(eng, events: list[Event], t: int) -> None:
    if not events:
        return
    cfg, semantics = eng.cfg, eng.semantics
    keys = [semantics.embedding_key(e.belief_id, e.value) for e in events]
    vecs = eng.emb.embed([e.text for e in events], keys=keys)
    active = [m for m in eng.mems.values() if is_visible(m)]

    for ev, vec in zip(events, vecs):
        best = max(active, key=lambda m: cosine(vec, m.emb), default=None)
        sim = cosine(vec, best.emb) if best else 0.0
        verdict = None
        if cfg.ingest_dedup and best is not None and sim > cfg.tau_dup:
            verdict = semantics.judge(ev.belief_id, ev.value,
                                      best.belief_id, best.value)

        novelty = 1.0 if best is None else max(0.0, min(1.0, 1.0 - sim))
        sal = max(0.0, min(1.0, ev.salience))
        if (cfg.ingest_dedup and best is not None
                and sim > cfg.tau_dup and verdict == "synonym"):
            discount_to(best, t, cfg)
            best.evid += 1          # 确认事件：证据汇聚，不新增
            best.last_seen = t
            best.src = best.src | frozenset(ev.src)
            if cfg.confidence_on:
                best.conf_pos += cfg.conf_confirm_evidence
            if cfg.salience_on:
                best.salience = max(best.salience, sal)
            continue

        initial_v = cfg.v_init + (
            cfg.novelty_bonus * novelty if cfg.novelty_on else 0.0)
        conf_pos = conf_neg = 0.0
        if cfg.confidence_on:
            conf_pos = (cfg.conf_write_evidence if ev.conf_pos is None
                        else max(0.0, ev.conf_pos))
            conf_neg = 0.0 if ev.conf_neg is None else max(0.0, ev.conf_neg)
        m = Memory(id=eng.next_id(), belief_id=ev.belief_id, value=ev.value,
                   text=ev.text, emb=vec, v=initial_v,
                   pool=Pool.CANDIDATE if cfg.two_pool else Pool.MEMORY,
                   birth=t, last_seen=t, src=frozenset(ev.src),
                   conf_pos=conf_pos, conf_neg=conf_neg,
                   conf_updated_at=t,
                   salience=sal if cfg.salience_on else cfg.salience_default,
                   novelty=novelty,
                   kind=ev.kind, derived_from=ev.derived_from,
                   scene=ev.scene)
        eng.mems[m.id] = m
        active.append(m)
        if cfg.consolidation_on and m.kind != "reflection":
            eng._consolidation_pending.add(m.id)

        if best is not None and sim > cfg.tau_dup:
            eng.add_tension(m.id, best.id, t)
