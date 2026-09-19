"""opencode agent 壳版裁判：judge/recognizer/consolidate 跑在 agent 里。

角色提示词仍由 LLMSemantics 提供（与裸 API 传输单一来源）；
opencode agent 定义（.opencode/agent/*.md）只承载模型/温度/权限与工具面。
按提示词身份映射到对应 agent 壳；agent 参与缓存键，换定义即换缓存。
失败抛 ZhipuChatError，沿用 LLMSemantics 既有降级路径。
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..agent.opencode import OpencodeRunner
from ..llm import ZhipuChatError
from .llm import (_CONSOLIDATE_SYS, _JUDGE_SYS, _RECOG_SYS, LLMSemantics)

_PROJECT_DIR = Path(__file__).resolve().parents[2]

_ROLE_AGENT = {
    _JUDGE_SYS: "judge",
    _RECOG_SYS: "recognizer",
    _CONSOLIDATE_SYS: "consolidator",
}


class OpencodeSemantics(LLMSemantics):
    def __init__(self, labels_path: str | Path | None = None, *,
                 model: str = "zhipu-env/glm-5.3-flash",
                 cache_dir: Path | None = None,
                 env_extra: dict | None = None,
                 timeout_s: int = 300,
                 use_agents: bool = True,
                 strict: bool = False,
                 runner: OpencodeRunner | None = None):
        self._runner = runner or OpencodeRunner(
            model=model, workdir=_PROJECT_DIR,
            payload_dir=_PROJECT_DIR / ".opencode" / "tmp",
            timeout_s=timeout_s, env_extra=env_extra, cache_dir=cache_dir)
        self._use_agents = use_agents
        self.strict = strict
        self.n_failed = 0     # 调用失败计数：LLMSemantics 会静默降级，
                              # 这个计数是"降级发生过"的唯一痕迹，必须外显
        super().__init__(labels_path, chat_fn=self._chat_via_runner, model=model)

    def _chat_via_runner(self, system: str, user: str) -> str:
        agent = _ROLE_AGENT.get(system) if self._use_agents else None
        try:
            return self._runner.chat(system, user, agent=agent)
        except ZhipuChatError as exc:
            self.n_failed += 1
            if self.n_failed == 1:
                print(f"[opencode] 裁判调用失败（第 1 次），后续将降级: {exc}",
                      file=sys.stderr, flush=True)
            if self.strict:
                raise RuntimeError(
                    f"opencode 裁判失败（strict 模式中止）: {exc}") from exc
            raise
