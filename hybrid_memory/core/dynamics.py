"""池容量策略（H11/H12，P4）：纯函数，无 I/O，不碰 store/telemetry。

- C 满 → V 最低者迁往 A（pinned 跳过）；
- A 满 → archived_at 最旧者删除（旧快照缺该字段视为最旧）；
- M 满 → 拒绝新晋升（maintenance 晋升循环内联执行，此处只给判定依据）。

与 §2.2 的一处偏差：`overflow_policy` 返回按动作分组的 dict 而非扁平
`list[int]`——扁平列表表达不了"迁往 A"和"删除"两种动作（P4 隐形决策）。
"""
from __future__ import annotations

import math

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
        return [m.id for m in over if m.id not in pinned][:max(0, len(over) - cfg.cap_a)]
    raise ValueError(f"unknown pool {pool!r}")


def overflow_policy(mems: dict[int, Memory], cfg,
                    pinned: frozenset[int]) -> dict[str, list[int]]:
    """C/A 溢出裁决。返回 {"archive": [...], "delete": [...]}。"""
    return {"archive": evictable(Pool.CANDIDATE, mems, cfg, pinned),
            "delete": evictable(Pool.ARCHIVE, mems, cfg, pinned)}


def plan_capacity(mems: dict[int, Memory], cfg,
                  pinned: frozenset[int], t: int | None = None) -> dict[str, object]:
    """提交前容量收口模拟（N17/N12）：给出 archive/delete 计划与背压判定。

    - 模拟迁 A 的条目按"当前 t"打戳（t 缺省视为最新）：新迁入者绝不是
      FIFO 最旧——旧实现 None→-1 把刚迁入的当成最旧优先删除，方向反了；
      存量 A 快照缺 archived_at 仍按 H11 视为最旧。
    - cap_context：非退役版本总数（C+M+A，含归档；不计临时 candidate 与
      retired）。A 池溢出之外，还要为上下文上限按 FIFO 补删无保护的非
      退役 A；删除 retired 条目不减少上下文。纯函数，无 I/O、不衰减 V。
    """
    import math

    pinned = frozenset(pinned)
    c_mems = [m for m in mems.values() if m.pool is Pool.CANDIDATE]
    c_unpinned = [m for m in c_mems if m.id not in pinned]
    c_unpinned.sort(key=lambda m: (m.v, m.last_hit if m.last_hit is not None
                                   else m.birth, m.id))
    archive_count = max(0, len(c_mems) - cfg.cap_c)
    to_archive = [m.id for m in c_unpinned[:archive_count]]

    def _non_retired(m: Memory) -> bool:
        return m.superseded_by is None and m.aggregated_into is None

    # A 池 = 存量 A + 模拟迁入。新迁入的排序戳 = t（缺省按最新）。
    a_keys: dict[int, tuple[float, int]] = {
        m.id: (m.archived_at if m.archived_at is not None else -1, m.id)
        for m in mems.values() if m.pool is Pool.ARCHIVE}
    new_stamp = float(t) if t is not None else math.inf
    for mid in to_archive:
        a_keys[mid] = (new_stamp, mid)
    a_unpinned = sorted((mid for mid in a_keys if mid not in pinned),
                        key=lambda mid: a_keys[mid])
    delete_count = max(0, len(a_keys) - cfg.cap_a)
    to_delete = a_unpinned[:delete_count]

    accepted, reason = True, None
    if cfg.capacity_on:
        context = sum(1 for m in mems.values() if _non_retired(m))
        context -= sum(1 for mid in to_delete
                       if (m := mems.get(mid)) is not None and _non_retired(m))
        if context > cfg.cap_context:
            # 上下文超限：补删最旧的无保护非退役 A（FIFO）。
            extra = [mid for mid in a_unpinned[delete_count:]
                     if (m := mems.get(mid)) is not None and _non_retired(m)]
            need = context - cfg.cap_context
            to_delete = to_delete + extra[:need]
            context -= min(need, len(extra))
        rem_c = len(c_mems) - len(to_archive)
        rem_a = len(a_keys) - len(to_delete)
        if rem_c > cfg.cap_c or rem_a > cfg.cap_a or context > cfg.cap_context:
            accepted = False
            reason = "capacity backpressure: all items pinned or pool over limit"

    delete_set = set(to_delete)
    remaining = [mid for mid in mems if mid not in delete_set]

    return {
        "archive": to_archive,
        "delete": to_delete,
        "remaining": remaining,
        "accepted": accepted,
        "reason": reason,
    }
