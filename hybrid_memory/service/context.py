"""调查调用的不可变因果上下文；不依赖 HTTP 或 agent runtime。"""
from dataclasses import dataclass


_ORIGINS = {"repair", "extract", "mining", "agent", "user_confirmed"}


@dataclass(frozen=True, slots=True)
class InvestigationContext:
    signal_id: str | None
    before: int | None
    origin: str = "agent"
    task_id: int | None = None
    lease_token: str | None = None


class SignalClosed(Exception):
    """调查已关闭、不存在，或该端点不允许调查调用（HTTP 403）。"""


class CausalViolation(Exception):
    """操作指向未知或因果上界外的记忆（HTTP 403）。"""
