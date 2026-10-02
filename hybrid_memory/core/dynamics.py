"""池容量策略（H11/H12，P4）：纯函数，无 I/O，不碰 store/telemetry。

- C 满 → V 最低者迁往 A（pinned 跳过）；
- A 满 → archived_at 最旧者删除（旧快照缺该字段视为最旧）；
- M 满 → 拒绝新晋升（maintenance 晋升循环内联执行，此处只给判定依据）。

与 §2.2 的一处偏差：`overflow_policy` 返回按动作分组的 dict 而非扁平
`list[int]`——扁平列表表达不了"迁往 A"和"删除"两种动作（P4 隐形决策）。
"""
from __future__ import annotations

from .types import Memory, Pool


def pinned_ids(engine) -> frozenset[int]:
    """淘汰保护：未决 tension 两端 ∪ 待裁决聚合体 ∪ 其成员 id。

    只读引擎内存态；人审队（tasks 侧 target_id）引用的条目若被迁往 A，
    台账仍可解析（archived，非删除），故正确性不依赖 tasks 侧并集——
    该并集随 H14 conflict_ledger 在 P5 补齐。
    """
    pins: set[int] = set()
    for left, right in engine.tensions:
        pins.add(left)
        pins.add(right)
    for m in engine.mems.values():
        if m.pending_review:
            pins.add(m.id)
            pins.update(m.agg_members)
    return frozenset(pins)


def evictable(pool: Pool, mems: dict[int, Memory], cfg,
              pinned: frozenset[int]) -> list[int]:
    """纯函数：给出该池应迁出/删除的 id（按优先级排序），不删。

    C：按 (V, last_hit|birth, id) 取最低者（键与 M backstop 同哲学）；
    A：按 (archived_at, id) 取最旧者；
    M：恒为空——M 溢出走"拒收晋升"（H12），不迁出任何人。
    """
    if pool is Pool.MEMORY:
        return []
    if pool is Pool.CANDIDATE:
        over = [m for m in mems.values() if m.pool is Pool.CANDIDATE]
        over.sort(key=lambda m: (m.v, m.last_hit if m.last_hit is not None
                                 else m.birth, m.id))
        return [m.id for m in over if m.id not in pinned][:max(0, len(over) - cfg.cap_c)]
    if pool is Pool.ARCHIVE:
        over = [m for m in mems.values() if m.pool is Pool.ARCHIVE]
        over.sort(key=lambda m: (m.archived_at if m.archived_at is not None
                                 else -1, m.id))
        return [m.id for m in over][:max(0, len(over) - cfg.cap_a)]
    raise ValueError(f"unknown pool {pool!r}")


def overflow_policy(mems: dict[int, Memory], cfg,
                    pinned: frozenset[int]) -> dict[str, list[int]]:
    """C/A 溢出裁决。返回 {"archive": [...], "delete": [...]}。"""
    return {"archive": evictable(Pool.CANDIDATE, mems, cfg, pinned),
            "delete": evictable(Pool.ARCHIVE, mems, cfg, pinned)}
