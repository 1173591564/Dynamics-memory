"""快照（P4 从 server.py 原样迁入）：STATE_KEYS / MEMORY_FIELD_DEFAULTS /
受限反序列化 / dump/load。只依赖 core + 标准库。

is_corrupt/quarantine 未单列成函数（§2.3 愿望）：现状是"load 抛错 →
lifecycle.recover_or_init 隔离"的内联流程，无独立等价物；行为保留，
落点在 lifecycle（见提交信息）。
"""
from __future__ import annotations

import io
import pickle

from ..core.types import Memory, Pool, Retrieval, Tension

_COUNTERS = ("n_promote", "n_demote", "n_evict", "n_archive", "n_revive",
             "n_merge", "n_collision", "n_tension", "n_resolve", "n_agg",
             "n_consolidate", "n_shadow_dropped", "n_chain_broken",
             "n_pool_truncated", "n_promote_rejected")

_SERVICE_COUNTERS = ("n_candgen_fail", "n_missed", "n_proposals", "n_rejected",
                     "n_ungrounded")

STATE_KEYS = {"mems", "tensions", "next_id", "consolidation_pending",
              "consolidation_deferred", "counters", "t", "unit_id", "scene"}

# Memory 后加字段：旧 state.pkl 反序列化出来的对象没有这些属性，
# 加载时按默认值补齐（dataclass 的 __dict__ 直接落盘，不会走 __init__）
MEMORY_FIELD_DEFAULTS = {"origin": "passive", "entity": "",
                         "archived_at": None}

# state.pkl 受限反序列化白名单：state 只含内置容器/标量 + Memory/Tension/
# Pool + numpy 数组重建函数，其余 global 一律拒绝（pickle RCE 防线）
_PICKLE_SAFE = {
    ("builtins", n) for n in
    ("dict", "list", "tuple", "set", "frozenset", "bytes", "bytearray",
     "str", "int", "float", "bool", "complex", "slice", "range",
     "NoneType", "object")
} | {
    ("collections", "OrderedDict"), ("collections", "defaultdict"),
    ("collections", "Counter"),
    ("hybrid_memory.core.types", "Memory"),
    ("hybrid_memory.core.types", "Tension"),
    ("hybrid_memory.core.types", "Pool"),
    ("hybrid_memory.core.types", "Retrieval"),
    ("numpy._core.multiarray", "_reconstruct"),
    ("numpy.core.multiarray", "_reconstruct"),   # numpy<2 兼容
    ("numpy", "dtype"), ("numpy", "ndarray"),
}


def _legacy_pool_member(cls, name):
    """只兼容旧 Enum 的 getattr(Pool, 成员名)，绝不开放通用 getattr。"""
    if cls is Pool and type(name) is str and name in Pool.__members__:
        return Pool.__members__[name]
    raise pickle.UnpicklingError("state.pkl 含非法的 Pool 成员访问")


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if module in ("builtins", "__builtin__") and name == "getattr":
            return _legacy_pool_member
        if (module, name) in _PICKLE_SAFE:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"state.pkl 含未授权 global: {module}.{name}")


def _valid_shadow_pending(pending) -> bool:
    if not isinstance(pending, list):
        return False
    for item in pending:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            return False
        key, mid, t_ret, rel = item
        if not isinstance(key, (list, tuple)) or len(key) != 2:
            return False
        if any(type(i) is not int or i < 0 for i in (*key, mid, t_ret)):
            return False
        if not isinstance(rel, bool):
            return False
    return True


def _shadow_entry(item) -> tuple:
    key, mid, t_ret, rel = item
    return (tuple(key), mid, t_ret, rel)


def _state(svc):
    return {
            "mems": svc.engine.mems, "tensions": svc.engine.tensions,
            "next_id": svc.engine._next_id,
            "consolidation_pending": svc.engine._consolidation_pending,
            "consolidation_deferred": svc.engine._consolidation_deferred,
            "counters": {k: getattr(svc.engine, k) for k in _COUNTERS},
            "shadow_pending": list(svc.engine._shadow_pending),
            "retrievals": svc._retrievals,
            "next_retrieval": svc._next_retrieval,
            "miss_counts": dict(svc.miss_counts),
            "service_counters": {k: getattr(svc, k) for k in _SERVICE_COUNTERS},
            "t": svc._t, "unit_id": svc._unit_id, "scene": svc._scene,
            "scene_t": svc._scene_t}


def dump_state(svc):
    svc._ensure_healthy()
    data = pickle.dumps(_state(svc), protocol=4)
    # N49：预算闸与 health 水位的真源（最近一次序列化大小，顺带记账零开销）。
    svc._state_bytes = len(data)
    return data


def load_state(svc, checkpoint: bytes | None = None) -> None:
    if checkpoint is None:
        with open(svc.state_path, "rb") as f:
            state = RestrictedUnpickler(f).load()
    else:
        state = RestrictedUnpickler(io.BytesIO(checkpoint)).load()
    if not isinstance(state, dict):
        raise ValueError(f"state.pkl 顶层类型异常: {type(state).__name__}")
    missing = STATE_KEYS - state.keys()
    if missing:
        raise ValueError(f"state.pkl 缺字段: {sorted(missing)}")
    # 先校验容器/对象类型及游标、计数器，再发布到服务；否则末尾字段损坏会留下
    # mems 已恢复、next_id/t 尚未恢复的半个引擎。兼容旧档缺少可选字段。
    state.setdefault("retrievals", {})
    state.setdefault("next_retrieval", 0)
    state.setdefault("miss_counts", {})
    state.setdefault("service_counters", {})

    def nonnegative_int(value):
        return type(value) is int and value >= 0

    for key in ("next_id", "next_retrieval", "t", "unit_id"):
        if not nonnegative_int(state[key]):
            raise ValueError(f"state.pkl 的 {key} 必须是非负整数")
    for key in ("mems", "tensions", "consolidation_deferred", "counters",
                "retrievals", "miss_counts", "service_counters"):
        if not isinstance(state[key], dict):
            raise ValueError(f"state.pkl 的 {key} 必须是 dict")
    if not isinstance(state["scene"], str):
        raise ValueError("state.pkl 的 scene 必须是字符串")
    if (type(state.get("scene_t", state["t"] - 1)) is not int
            or state.get("scene_t", state["t"] - 1) < -1):
        raise ValueError("state.pkl 的 scene_t 必须是整数")
    if (not isinstance(state["consolidation_pending"], set)
            or not all(nonnegative_int(i) for i in state["consolidation_pending"])):
        raise ValueError("state.pkl 的 consolidation_pending 必须是 id 集合")
    if any(not isinstance(k, str) or not isinstance(v, frozenset)
           or not all(nonnegative_int(i) for i in v)
           for k, v in state["consolidation_deferred"].items()):
        raise ValueError("state.pkl 的 consolidation_deferred 格式异常")
    pending = state.get("shadow_pending", [])
    if not _valid_shadow_pending(pending):
        raise ValueError("state.pkl 的 shadow_pending 格式异常")
    if any(not nonnegative_int(i) or not isinstance(m, Memory)
           or m.id != i or not isinstance(m.pool, Pool)
           for i, m in state["mems"].items()):
        raise ValueError("state.pkl 的 mems 格式异常")
    if any(not isinstance(k, tuple) or len(k) != 2
           or not all(nonnegative_int(i) for i in k) or not isinstance(v, Tension)
           for k, v in state["tensions"].items()):
        raise ValueError("state.pkl 的 tensions 格式异常")
    if any(not nonnegative_int(i) or not isinstance(r, Retrieval)
           for i, r in state["retrievals"].items()):
        raise ValueError("state.pkl 的 retrievals 格式异常")
    for key, allowed in (("counters", _COUNTERS),
                         ("service_counters", _SERVICE_COUNTERS)):
        if any(k not in allowed or not nonnegative_int(v)
               for k, v in state[key].items()):
            raise ValueError(f"state.pkl 的 {key} 含未知或非法计数器")
    if any(not isinstance(k, str) or not nonnegative_int(v)
           for k, v in state["miss_counts"].items()):
        raise ValueError("state.pkl 的 miss_counts 格式异常")
    for m in state["mems"].values():
        for k, v in MEMORY_FIELD_DEFAULTS.items():
            if k not in m.__dict__:
                setattr(m, k, v)

    eng = svc.engine
    eng.mems = state["mems"]
    eng.tensions = state["tensions"]
    eng._next_id = max(state["next_id"], max(eng.mems, default=-1) + 1)
    eng._consolidation_pending = state["consolidation_pending"]
    eng._consolidation_deferred = state["consolidation_deferred"]
    eng._shadow_pending = [_shadow_entry(item) for item in pending]
    for k, v in state["counters"].items():
        setattr(eng, k, v)
    svc._retrievals = state["retrievals"]
    svc._next_retrieval = max(state["next_retrieval"],
                              max(svc._retrievals, default=-1) + 1)
    svc.miss_counts = state["miss_counts"]
    for k, v in state["service_counters"].items():
        setattr(svc, k, v)
    svc._t = state["t"]
    svc._unit_id = state["unit_id"]
    svc._scene = state["scene"]
    svc._scene_t = state.get("scene_t", state["t"] - 1)
