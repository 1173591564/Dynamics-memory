"""引擎信号的有界内存队列，支持可选的持久化发射回调。

裸引擎仍是易失队列；sidecar 在引擎效果事务中持久交接调查与
feedback/conflict/maintenance 语义信号；thin_recall 遥测仍易失。
同 (kind, key) 在内存中去重合并。持久任务是否可合并由 journal 自己判断。
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Signal:
    kind: str
    payload: object
    t: int
    key: str = ""
    id: int = 0


class SignalQueue:
    def __init__(self, cap: int = 256, on_emit=None):
        self.cap = max(1, int(cap))
        self.on_emit = on_emit
        self._items: deque[Signal] = deque()
        self._by_key: dict[tuple[str, str], Signal] = {}
        self._next_id = 0
        self.n_emitted = 0
        self.n_dropped = 0

    def emit(self, kind: str, payload, t: int, key: str = "",
             merge=None) -> Signal:
        """key 非空且同类已存在 → merge(旧, 新) 原地更新并刷新 t；
        否则入队；队满丢最旧。"""
        # journal 同步序列化 payload（不修改原对象），返回任务 id 即接管。
        task_id = (self.on_emit(kind, payload, t, key, merge)
                   if self.on_emit is not None else None)
        self.n_emitted += 1
        if task_id is not None:
            return Signal(kind, payload, t, key, task_id)
        if key:
            exist = self._by_key.get((kind, key))
            if exist is not None:
                exist.payload = (merge(exist.payload, payload)
                                 if merge else payload)
                exist.t = t
                return exist
        sig = Signal(kind=kind, payload=payload, t=t, key=key,
                     id=self._next_id)
        self._next_id += 1
        self._items.append(sig)
        if key:
            self._by_key[(kind, key)] = sig
        while len(self._items) > self.cap:
            old = self._items.popleft()
            if old.key:
                self._by_key.pop((old.kind, old.key), None)
            self.n_dropped += 1
        return sig

    def drain(self) -> list[Signal]:
        out = list(self._items)
        self._items.clear()
        self._by_key.clear()
        return out

    def take(self, kinds) -> list[Signal]:
        """只摘走指定种类的信号，其余原位保留（顺序不变）。

        裸引擎多消费者共用队列时用它而不是 drain+回队；sidecar 的
        调查与语义 worker 都从 SQLite 领取，不消费这些持久信号的内存镜像。"""
        kinds = set(kinds)
        out, keep = [], deque()
        for sig in self._items:
            (out if sig.kind in kinds else keep).append(sig)
        self._items = keep
        for sig in out:
            if sig.key:
                self._by_key.pop((sig.kind, sig.key), None)
        return out

    def peek_kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for sig in self._items:
            counts[sig.kind] = counts.get(sig.kind, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._items)
