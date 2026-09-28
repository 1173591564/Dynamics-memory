"""对话单元与窗口：candgen 的输入类型（sidecar 每轮 observe 构造一个单元窗口）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InteractionUnit:
    id: int
    start_time: int
    end_time: int
    user_text: str
    assistant_text: str
    assistant_turns: int


@dataclass(frozen=True)
class InteractionWindow:
    id: int
    start_unit_id: int
    end_unit_id: int
    start_time: int
    end_time: int
    units: tuple[InteractionUnit, ...]
