"""协议等价的进程内 agent runner（L2/L3 抽检专用）。

与 OpenCodeRunner 的差异**仅在模型调用不经 CLI 子进程**：
- prompt 真源同 `.opencode/agent/*.md`（frontmatter 之后的正文）；
- payload 同封存形状（调用方 build_payload 组装）；
- 返回协议 JSON 的解析复用 `OpenCodeRunner._parse_text`（同一套拒收规则）。

为什么存在：2GB 沙箱下单次 `opencode run`（bun 运行时+会话）RSS 实测
≈514MB，与系统基线叠加后 attach/自举均被 OOM killer 以 SIGKILL 打杀
（exited -9，重试耗尽成批 dead，N50 轮实测）。真实 CLI 通道已由 N48
（Windows 首验）与本沙箱冒烟覆盖；抽检目标是记忆质量（六问），故采用
本进程内 runner 保真协议、省去子进程内存。此为评测资产，不替代生产
OpenCodeRunner；限制在抽检报告中如实标注。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ROLES = ("hauler", "selector", "reviewer")


def _agent_prompt(name: str) -> str:
    txt = (_REPO / ".opencode" / "agent" / f"{name}.md").read_text(
        encoding="utf-8")
    return txt.split("---", 2)[2].strip() if txt.startswith("---") else txt


# 2026-10-04 四链冻结事件：API 偶发“连接建立但状态行永不到达”，
# urllib socket 超时在 ssl 阻塞读上不触发（实测挂 24min+）。
# 墙钟硬上限把“链路永久冻结”降级为“一次失败调用”，由 worker 重试兜底。
_WALL_CLOCK_CAP = 300.0  # 单次调用墙钟上限（max 档 hauler 实测 30-90s，3×+ 余量）


class InlineAgentRunner:
    """DispatchWorker 兼容 runner：run_agent(name, payload) -> dict。"""

    def __init__(self, model: str = "glm-5.3-flash", api_key: str | None = None):
        self.model = model
        self.api_key = api_key
        self.prompts = {n: _agent_prompt(n) for n in _ROLES}

    def available(self) -> bool:
        return True

    def verify_channel(self) -> bool:
        prompts = all(self.prompts.values())
        if not prompts:
            raise RuntimeError("agent prompt 缺失：.opencode/agent/*.md")
        return True

    def close(self) -> None:
        return None

    def run_agent(self, name: str, payload: dict) -> dict:
        if name not in self.prompts:
            raise ValueError(f"unknown agent {name!r}")
        from hybrid_memory.agents.opencode import OpenCodeRunner
        resp = self._chat(
            [{"role": "system", "content": self.prompts[name]},
             {"role": "user",
              "content": "Protocol message:\n"
                         + json.dumps(payload, ensure_ascii=False)}])
        text = resp.get("content") if isinstance(resp, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"inline agent {name} 空回复")
        return OpenCodeRunner._parse_text(text, name)

    def _chat(self, messages: list) -> dict:
        """直连智谱 chat/completions。

        与生产 llm.chat_messages 等价（同端点/模型/温度；实测 glm-5.3-flash
        始终思考，单次 hauler 调用 60-90s，时间预算见抽检报告）。
        """
        import threading
        import urllib.request
        from hybrid_memory.llm.client import BASE_URL
        key = self.api_key or os.environ.get("ZAI_API_KEY", "")
        if not key:
            raise RuntimeError("ZAI_API_KEY is not set")
        body = json.dumps({"model": self.model, "messages": messages,
                           "temperature": 0.0},
                          ensure_ascii=False).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"})
        box: dict = {}

        def _do() -> None:
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    box["out"] = json.loads(r.read())
            except BaseException as e:  # 只读 HTTP、无共享状态；传回主线程
                box["err"] = e

        t = threading.Thread(target=_do, daemon=True)
        t.start()
        t.join(_WALL_CLOCK_CAP)
        if t.is_alive():
            raise RuntimeError(
                f"inline agent 调用超过墙钟上限 {_WALL_CLOCK_CAP}s（API 无响应）")
        if "err" in box:
            raise box["err"]
        return box["out"]["choices"][0]["message"]

    def __call__(self, name: str, payload: dict) -> dict:
        return self.run_agent(name, payload)
