"""运行器契约（P6 从 agent/trio.py 拆出）：三 agent 共用的调用形状。

AgentProtocolError 继承 ValueError：协议错与旧 ValueError 同属"模型/输入错"，
store.retry 的 retry_model 整轮重开语义不变。
"""
from __future__ import annotations

from typing import Protocol


MAX_ATTEMPTS = 5  # H8：与 KindPolicy(_WORKFLOW).max_attempts 同值；DispatchWorker 显式传入


class AgentProtocolError(ValueError):
    """Agent 返回不可解析/非对象：协议错（可重试整轮）。"""


class AgentTimeout(Exception):
    """Agent CLI 超时（非输入错，不重开整轮）。"""


class AgentRunner(Protocol):
    """OpenCode 运行器形状：run 主调，available 探活。fake runner 只需可调用。"""

    def run(self, name: str, payload: dict) -> dict:
        ...

    def available(self) -> bool:
        ...
