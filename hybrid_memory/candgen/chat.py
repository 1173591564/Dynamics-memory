"""candgen 的 LLM 后端：单窗口进，候选出。chat_fn 可注入（测试/换传输）。"""
from __future__ import annotations

from ..interaction import InteractionWindow
from .base import CandidateGeneration
from .prompt import INSTRUCTION, parse_generation, serialize_window


class ChatGenerator:
    def __init__(self, chat_fn):
        self._chat = chat_fn

    def generate(self, window: InteractionWindow,
                 prev_scene: str = "") -> CandidateGeneration:
        out = self._chat(INSTRUCTION, serialize_window(window, prev_scene))
        return parse_generation(out)
