"""语义服务提供者包装（H27/N15/N22）：显式化双语义通路与健康可观测性。"""
from __future__ import annotations

from pathlib import Path

from ..core.types import Event
from .llm import LLMSemantics
from .real import RealChatSemantics


class SemanticsProvider:
    """双语义通路提供者：封装 judge、relevant_set、consolidate 并提供 health()。"""

    def __init__(self, delegate: RealChatSemantics | None = None, *,
                 provider: str = "zhipu", model: str = "glm-5.3-flash"):
        self.delegate = delegate or LLMSemantics(model=model)
        self.provider = provider
        self.model = model
        self.calls = 0
        self.failures = 0
        self.last_error: str | None = None

    def health(self) -> dict:
        """双语义通路的可观测健康段。"""
        return {
            "provider": self.provider,
            "model": self.model,
            "calls": self.calls,
            "failures": self.failures,
            "last_error": self.last_error,
        }

    def judge(self, a_bid: int, a_val: str, b_bid: int, b_val: str) -> str:
        """存量张力关系判定包装。"""
        self.calls += 1
        try:
            return self.delegate.judge(a_bid, a_val, b_bid, b_val)
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return "pending"

    def relevant_set(self, texts: list[str], question: str,
                     answer: str) -> list[bool] | None:
        """实际展示记忆归因包装。"""
        self.calls += 1
        try:
            return self.delegate.relevant_set(texts, question, answer)
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def consolidate(self, memories, t: int) -> Event | None:
        """reflection 语义包装。"""
        self.calls += 1
        try:
            return self.delegate.consolidate(memories, t)
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def fingerprint(self, text: str) -> int:
        return self.delegate.fingerprint(text)

    def scope(self, belief_id: int):
        return self.delegate.scope(belief_id)
