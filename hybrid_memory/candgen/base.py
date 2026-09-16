"""cand-gen 契约：窗口进，原子 memory 候选出；支持跨窗情境携带。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..datasets.real_chat import InteractionWindow


@dataclass(frozen=True)
class MemoryCandidate:
    text: str
    type: str = ""                        # work_fact/task/method/artifact/…
    priority: int | None = None           # 仅元数据，不进 V
    source_unit_ids: tuple[int, ...] = ()
    salience: float = 0.5                 # 缺失代价，不进 V/置信


@dataclass(frozen=True)
class CandidateGeneration:
    """一次窗口抽取的完整产物：候选 + 供下一窗携带的情境名。"""
    candidates: tuple[MemoryCandidate, ...]
    scene_name: str = ""


class CandidateGenerator(Protocol):
    def generate(self, window: InteractionWindow,
                 prev_scene: str = "") -> CandidateGeneration: ...
