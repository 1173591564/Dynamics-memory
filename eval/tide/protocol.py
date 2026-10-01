"""被测系统协议。平台只通过这几个方法与系统交互；真值不越界。

HTTP 版（给独立进程的系统）：
  POST /reset   {stream_id}
  POST /ingest  {turn: {user, assistant}, t, ts}
  POST /serve   {query, t, ts, budget_tokens, passive} → {context}
  GET  /cost    → {llm_calls, tokens}
进程内参照系统直接实现下面的抽象类；外部系统各写一个薄适配器
（见 tide/adapters/）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    passive: bool = True       # serve(passive=True) 保证不改状态；否则平台逐探针重放
    privileged: bool = False   # 只有 Oracle 可见探针真值（参照上界，不参赛）


class MemorySystem(ABC):
    name: str = "system"
    caps: Capabilities = Capabilities()

    @abstractmethod
    def reset(self, stream_id: str) -> None: ...

    @abstractmethod
    def ingest(self, user: str, assistant: str, t: int) -> None: ...

    @abstractmethod
    def serve(self, query: str, t: int, budget_tokens: int, passive: bool = True,
              probe=None) -> str:
        """probe 仅在 caps.privileged 时由平台传入。"""

    def cost(self) -> dict:
        return {"llm_calls": 0, "tokens": 0}

    def close(self) -> None:
        pass
