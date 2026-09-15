"""写入回路：Event → ingest dedup → 新条目进 C（单层模式直接进 M）。

dedup 语义：sim>τ_dup 且判为 synonym（同 belief 同值）→ evid++，不新增；
sim>τ_dup 但非同义（update/contradiction/collision）→ 新增 + tension 对。
"""
from __future__ import annotations

from ..core.types import Event, Memory, Pool
from ..embed.base import cosine


def run_ingest(eng, events: list[Event], t: int) -> None:
    if not events:
        return
    cfg, semantics = eng.cfg, eng.semantics
    keys = [semantics.embedding_key(e.belief_id, e.value) for e in events]
    vecs = eng.emb.embed([e.text for e in events], keys=keys)
    active = [m for m in eng.mems.values() if m.pool is not Pool.ARCHIVE]

    for ev, vec in zip(events, vecs):
        best = max(active, key=lambda m: cosine(vec, m.emb), default=None)
        sim = cosine(vec, best.emb) if best else 0.0
        verdict = semantics.judge(ev.belief_id, ev.value,
                                  best.belief_id, best.value) if best else None

        if (cfg.ingest_dedup and best is not None
                and sim > cfg.tau_dup and verdict == "synonym"):
            best.evid += 1          # 确认事件：证据汇聚，不新增
            best.last_seen = t
            best.src = best.src | frozenset(ev.src)
            continue

        m = Memory(id=eng.next_id(), belief_id=ev.belief_id, value=ev.value,
                   text=ev.text, emb=vec, v=cfg.v_init,
                   pool=Pool.CANDIDATE if cfg.two_pool else Pool.MEMORY,
                   birth=t, last_seen=t, src=frozenset(ev.src))
        eng.mems[m.id] = m
        active.append(m)

        if best is not None and sim > cfg.tau_dup:
            eng.add_tension(m.id, best.id, t)
