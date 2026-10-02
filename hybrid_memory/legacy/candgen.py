"""legacy 候选管线（冻结）：候选类型（re-export 自 `.prompt`，原 candgen/base.py）+ LLM 后端（原 candgen/chat.py）。

类型定义置于 prompt.py（唯一出处），本模块只 re-export：保持单向依赖
candgen → prompt，避免 base+chat 合并后出现循环导入。引用方一律从本模块
导入类型（`legacy.candgen.MemoryCandidate`），对象与 prompt 内一致。
"""
from __future__ import annotations

from ..core.interaction import InteractionWindow
from .prompt import (INSTRUCTION, CandidateGeneration, CandidateGenerator,
                     MemoryCandidate, parse_generation, serialize_window)

__all__ = ["CandidateGeneration", "CandidateGenerator", "ChatGenerator",
           "MemoryCandidate"]


class ChatGenerator:
    def __init__(self, chat_fn):
        self._chat = chat_fn

    def generate(self, window: InteractionWindow,
                 prev_scene: str = "") -> CandidateGeneration:
        out = self._chat(INSTRUCTION, serialize_window(window, prev_scene))
        return parse_generation(out)
