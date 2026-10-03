"""语义服务提供者包装（H27/N15/N22）：显式化双语义通路与健康可观测性。"""
from __future__ import annotations

from pathlib import Path

from ..core.types import Event
from .llm import LLMSemantics
from .real import RealChatSemantics


class SemanticsProvider:
    """双语义通路提供者：封装 judge、relevant_set、consolidate 并提供 health()。"""

    _MEMORY_SEMANTICS_METHODS = ("judge", "relevant", "valid",
                                 "embedding_key", "scope", "fingerprint")

    def __init__(self, delegate: RealChatSemantics | None = None, *,
                 provider: str = "zhipu", model: str = "glm-5.3-flash"):
        self.delegate = delegate or LLMSemantics(model=model)
        # 运行时检查：MemorySemantics 是 Protocol（不可 runtime_checkable），
        # 包装层显式验证委托具备写路径全部方法——启动即失败，不让第一条
        # observe 在写入途中 AttributeError。
        missing = [m for m in self._MEMORY_SEMANTICS_METHODS
                   if not callable(getattr(self.delegate, m, None))]
        if missing:
            raise ValueError(
                f"SemanticsProvider delegate lacks MemorySemantics methods: "
                f"{', '.join(missing)}")
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

    def relevant_set(self, texts: list[str], question: str,
                     answer: str) -> list[bool] | None:
        """实际展示记忆归因包装；委托缺失该能力时返回 None（能力缺失
        不是错误，不计失败——worker 按缺失语义退化全记）。"""
        fn = getattr(self.delegate, "relevant_set", None)
        if fn is None:
            return None
        self.calls += 1
        try:
            return fn(texts, question, answer)
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def consolidate(self, memories, t: int) -> Event | None:
        """reflection 语义包装；委托缺失该能力时返回 None（缺失语义：
        该回路不产 reflection，不算失败）。"""
        fn = getattr(self.delegate, "consolidate", None)
        if fn is None:
            return None
        self.calls += 1
        try:
            return fn(memories, t)
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    # ---- MemorySemantics 写路径委托（引擎/检索经包装层调用） ----

    def judge(self, a_bid: int, a_val: str, b_bid: int, b_val: str) -> str:
        """存量张力关系判定包装（计数走 provider，降级可观测）。"""
        self.calls += 1
        try:
            return self.delegate.judge(a_bid, a_val, b_bid, b_val)
        except Exception as exc:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return "pending"

    def relevant(self, belief_id: int, value: str, query, t: int) -> bool:
        return self.delegate.relevant(belief_id, value, query, t)

    def valid(self, belief_id: int, value: str, t: int) -> bool:
        return self.delegate.valid(belief_id, value, t)

    def embedding_key(self, belief_id: int, value: str) -> tuple:
        return self.delegate.embedding_key(belief_id, value)

    def fingerprint(self, text: str) -> int:
        return self.delegate.fingerprint(text)

    def scope(self, belief_id: int):
        return self.delegate.scope(belief_id)
