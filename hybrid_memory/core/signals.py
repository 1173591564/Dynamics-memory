"""引擎 → LLM 信号队列（P1 影子模式）。

引擎在"有活可干"的时刻发射信号，worker（后续实现）拉取信号、
自主调 LLM、再经引擎操作面回报。P1 阶段引擎照旧同步调用 semantics，
信号并行发射——用于验证信号面完备性，不改变任何现有行为。

有界：队满丢最旧 + n_dropped 计数，绝不静默。
合并：key 非空的信号按 (kind, key) 去重/合并（如 conflict_pending
累积成一批、maintenance_due 按 scene 只留最新签名）。
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
    def __init__(self, cap: int = 256):
        self.cap = max(1, int(cap))
        self._items: deque[Signal] = deque()
        self._by_key: dict[tuple[str, str], Signal] = {}
        self._next_id = 0
        self.n_emitted = 0
        self.n_dropped = 0

    def emit(self, kind: str, payload, t: int, key: str = "",
             merge=None) -> Signal:
        """key 非空且同类已存在 → merge(旧, 新) 原地更新并刷新 t；
        否则入队；队满丢最旧。"""
        self.n_emitted += 1
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

    def __len__(self) -> int:
        return len(self._items)
