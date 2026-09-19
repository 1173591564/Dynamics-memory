"""candgen 裸 LLM 后端：单窗口进，候选出。chat_fn 可注入（测试/换传输）。

在线场景（sidecar）用这条：不为每轮抽取再套一层 opencode CLI（插件本身
就跑在 opencode 里，避免递归）；prompt/解析与 opencode 后端完全共用。
"""
from __future__ import annotations

from ..datasets.real_chat import InteractionWindow
from .base import CandidateGeneration
from .prompt import INSTRUCTION, parse_generation, serialize_window


class ChatGenerator:
    def __init__(self, chat_fn, model: str = "glm-5.3-flash"):
        self._chat = chat_fn
        self.model = model

    def generate(self, window: InteractionWindow,
                 prev_scene: str = "") -> CandidateGeneration:
        out = self._chat(INSTRUCTION, serialize_window(window, prev_scene))
        return parse_generation(out)
