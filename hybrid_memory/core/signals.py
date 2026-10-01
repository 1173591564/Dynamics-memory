"""引擎信号的有界内存队列，支持可选的持久化发射回调。

裸引擎仍是易失队列；sidecar 为调查信号注入 SQLite journal，先持久化后发布。
此时队列中的调查信号只是有界镜像，逐出不删除持久任务；其他语义信号仍易失。
同 (kind, key) 在内存中去重合并。持久任务是否可合并由 journal 自己判断。
"""
from __future__ import annotations

from collections import deque
import copy
from dataclasses import dataclass


@dataclass
class Signal:
    kind: str
    payload: object
    t: int
    key: str = ""
    id: int = 0
    task_id: int | None = None


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
        # 服务可注入 durable outbox：成功持久化后才发布到易失的有界队列。
        task_id = (self.on_emit(kind, copy.deepcopy(payload), t, key, merge)
                   if self.on_emit is not None else None)
        self.n_emitted += 1
        if key:
            exist = self._by_key.get((kind, key))
            if exist is not None:
                exist.payload = (merge(exist.payload, payload)
                                 if merge else payload)
                exist.t = t
                exist.task_id = task_id
                return exist
        sig = Signal(kind=kind, payload=payload, t=t, key=key,
                     id=self._next_id, task_id=task_id)
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

        多消费者共用一个队列时用它而不是 drain+回队：语义 worker 拿
        conflict/feedback/maintenance，agent worker 拿 recall_miss/extract_due，
        互不干扰、不重排。"""
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

    def mirror(self, kinds, signals) -> None:
        """恢复持久任务的有界显示镜像；不再次发射、不触发持久化回调。
        镜像可被逐出，真实任务仍由 SQLite 持有。调用方持服务锁。
        """
        self.take(kinds)
        for sig in signals:
            self._items.append(sig)
        while len(self._items) > self.cap:
            self._items.popleft()
        self._by_key = {(s.kind, s.key): s for s in self._items if s.key}
