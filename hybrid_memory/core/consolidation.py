"""巩固回路：salience 预算触发的 reflection 生成。

pending 池累积普通 fact 的 id；按 scene 分组，组内 clamped salience 之和
达到预算且数量达标时，回调 semantics.consolidate 合成一条
kind="reflection" 的高层状态记忆（来源仍可检索，不取代不归档）。
回调编程错误向上抛；回调返回 None → 该 scene 以当前输入签名记入
deferred，同签名输入不再重复调用，新源加入后签名变化自动恢复重试。
"""
from __future__ import annotations

from ..core.types import (ConsolidationSemantics, Memory, Pool,
                          is_visible)
from ..embed.base import cosine


def maybe_consolidate(eng, t: int) -> None:
    cfg = eng.cfg
    if not cfg.consolidation_on:
        return

    pending = eng._consolidation_pending
    for mid in list(pending):
        m = eng.mems.get(mid)
        if (m is None or m.pool is Pool.ARCHIVE
                or m.superseded_by is not None
                or m.aggregated_into is not None
                or m.pending_review or m.kind != "fact"):
            pending.discard(mid)

    eligible = [eng.mems[i] for i in pending]
    groups: dict[str, list] = {}
    for m in eligible:
        groups.setdefault(m.scene, []).append(m)   # "" 兜底组，不与具名组混

    def _budget(items) -> float:
        return sum(max(0.0, min(1.0, m.salience)) for m in items)

    deferred = eng._consolidation_deferred
    for scene in list(deferred):
        if scene not in groups:
            del deferred[scene]

    ready = [(scene, items, frozenset(m.id for m in items))
             for scene, items in groups.items()
             if len(items) >= cfg.consolidation_min_items
             and _budget(items) >= cfg.consolidation_salience_budget
             and deferred.get(scene) != frozenset(m.id for m in items)]

    # 信号发射：有可巩固的组就广播（worker 可批量处理；P1 影子模式下
    # 同步回调照旧）。按 scene 合并，只保留最新输入签名。
    for scene, items, _sig in ready:
        eng.signals.emit("maintenance_due",
                         {"scene": scene, "ids": [m.id for m in items]}, t,
                         key=f"maint:{scene}", merge=lambda o, n: n)

    if not isinstance(eng.semantics, ConsolidationSemantics):
        return
    fn = eng.semantics.consolidate
    if not ready:
        return

    # 每步至多一次：取最近有更新、预算最高、scene 字典序决胜的组
    scene, items, signature = max(
        ready,
        key=lambda r: (max(m.last_seen for m in r[1]), _budget(r[1]), r[0]))
    ranked = sorted(items,
                    key=lambda m: (m.salience, m.last_seen, m.birth, m.id),
                    reverse=True)[: cfg.consolidation_max_items]
    chosen = sorted(ranked, key=lambda m: (m.birth, m.id))

    event = fn(chosen, t)           # 回调编程错误向上抛；LLM 失败在内部归 None
    if event is None:
        deferred[scene] = signature   # 同输入不重复尝试，等新源进来
        return
    admit_reflection(eng, event, chosen, t)
    deferred.pop(scene, None)   # 组名与 event.scene 不一致时也清组签名


def admit_reflection(eng, event, chosen, t: int) -> Memory:
    """reflection 入库：嵌入、novelty 计算、建档、清理 pending/deferred。
    同步回调路径与操作面 add_reflection 共用。"""
    cfg = eng.cfg
    key = eng.semantics.embedding_key(event.belief_id, event.value)
    vec = eng.emb.embed([event.text], keys=[key])[0]
    active = [m for m in eng.mems.values() if is_visible(m)]
    nearest = max((cosine(vec, m.emb) for m in active), default=None)
    novelty = 1.0 if nearest is None else max(0.0, min(1.0, 1.0 - nearest))
    m = Memory(
        id=eng.next_id(), belief_id=event.belief_id, value=event.value,
        text=event.text, emb=vec,
        v=cfg.v_init + (cfg.novelty_bonus * novelty
                        if cfg.novelty_on else 0.0),
        pool=Pool.CANDIDATE if cfg.two_pool else Pool.MEMORY,
        birth=t, last_seen=t,
        src=frozenset(event.src) | frozenset().union(
            *(c.src for c in chosen)),
        conf_pos=(max(0.0, event.conf_pos) if cfg.confidence_on
                  and event.conf_pos is not None else 0.0),
        conf_neg=(max(0.0, event.conf_neg) if cfg.confidence_on
                  and event.conf_neg is not None else 0.0),
        conf_updated_at=t,
        salience=max(0.0, min(1.0, event.salience)),
        novelty=novelty,
        kind="reflection",
        derived_from=tuple(c.id for c in chosen),
        scene=event.scene)
    eng.mems[m.id] = m
    for c in chosen:
        eng._consolidation_pending.discard(c.id)
    eng._consolidation_deferred.pop(m.scene, None)
    eng.n_consolidate += 1
    return m
