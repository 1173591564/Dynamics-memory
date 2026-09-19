"""opencode CLI 后端：candgen 跑在 `opencode run` 会话壳里。

--pure 关插件，--dir 把 agent 工作目录锁在 scratch；instruction+窗口写进附件
（opencode.cmd 批处理不吃多行 argv）。`env_extra` 注入 provider 密钥；
`config_path` 经 OPENCODE_CONFIG 指到自定义 provider 配置，不动全局 auth store。
subprocess/事件流解析复用 hybrid_memory.agent.opencode.OpencodeRunner。
"""
from __future__ import annotations

from pathlib import Path

from ..agent.opencode import OpencodeRunner
from ..datasets.real_chat import InteractionWindow
from ..llm import ZhipuChatError
from .base import CandidateGeneration
from .prompt import INSTRUCTION, parse_generation, serialize_window

_CLI_INSTRUCTION = "读取附件，按其中说明完成情境切分与记忆提取，只输出 JSON 对象。"


class OpencodeCliGenerator:
    def __init__(self, model: str = "zhipu-env/glm-5.3-flash",
                 scratch_dir: str | Path = "experiments/out/_candgen_scratch",
                 timeout_s: int = 300, env_extra: dict | None = None,
                 config_path: str | Path | None = None):
        self._runner = OpencodeRunner(
            model=model, scratch_dir=scratch_dir, timeout_s=timeout_s,
            env_extra=env_extra, config_path=config_path)

    def generate(self, window: InteractionWindow,
                 prev_scene: str = "") -> CandidateGeneration:
        try:
            reply = self._runner.run(
                system=INSTRUCTION,
                user=serialize_window(window, prev_scene),
                instruction=_CLI_INSTRUCTION,
                agent="candgen")   # 锁定 agent：不可信窗口文本不碰工具
        except ZhipuChatError as exc:
            raise RuntimeError(f"opencode candgen failed: {exc}") from exc
        return parse_generation(reply)
