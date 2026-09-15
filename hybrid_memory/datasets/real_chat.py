"""真实对话 JSONL → InteractionUnit 流 + 定长滑动 InteractionWindow。

每行一个 {role, time, text} object；user 开新 unit，其后非空 assistant text
用 \\n\\n 拼成 assistant_text，直到下一个 user。坏行抛 ValueError("invalid row N")。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


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


def load_interaction_units(path: str | Path) -> list[InteractionUnit]:
    units: list[InteractionUnit] = []
    query: str | None = None
    start_time = 0
    end_time = 0
    parts: list[str] = []

    def flush() -> None:
        if query and parts:
            units.append(InteractionUnit(
                id=len(units), start_time=start_time, end_time=end_time,
                user_text=query, assistant_text="\n\n".join(parts),
                assistant_turns=len(parts)))

    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid row {line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"invalid row {line_no}")
            role = row.get("role")
            time_value = row.get("time")
            text = row.get("text")
            if (role not in ("user", "assistant")
                    or not isinstance(time_value, (int, float))
                    or not isinstance(text, str)):
                raise ValueError(f"invalid row {line_no}")
            if role == "user":
                flush()
                query = text
                start_time = int(time_value)
                parts = []
            elif query is not None and text:
                end_time = int(time_value)
                parts.append(text)
        flush()
    return units


def build_interaction_windows(
    units: list[InteractionUnit], size: int, stride: int
) -> list[InteractionWindow]:
    if size < 1 or stride < 1:
        raise ValueError("size and stride must be >= 1")
    windows: list[InteractionWindow] = []
    for start in range(0, len(units) - size + 1, stride):
        group = units[start:start + size]
        windows.append(InteractionWindow(
            id=len(windows),
            start_unit_id=group[0].id,
            end_unit_id=group[-1].id,
            start_time=group[0].start_time,
            end_time=group[-1].end_time,
            units=tuple(group)))
    return windows
