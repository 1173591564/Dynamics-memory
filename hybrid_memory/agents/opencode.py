"""唯一 OpenCode 实现（P6 从 agent/trio.py 拆出）：调真实 CLI 跑三 agent。

__call__ 保留为 run 的兼容委托：fake runner 与 DispatchWorker 统一按
run_agent(name, payload) 调用。stdin 关闭（防 CLI 继承 sidecar stdin 阻塞）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

from .protocol import AgentProtocolError, AgentTimeout


class OpenCodeRunner:
    """Run real OpenCode agents, not a local imitation of their reasoning loop."""

    def __init__(self, project: Path, executable: str | None = None, timeout: int = 300):
        self.project = Path(project)
        self.executable = executable or os.environ.get("MEMORY_OPENCODE_BIN", "opencode")
        self.timeout = timeout
        self.agent_root = Path(__file__).resolve().parents[2]

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def __call__(self, name: str, payload: dict) -> dict:
        return self.run(name, payload)

    def run(self, name: str, payload: dict) -> dict:
        if name not in {"hauler", "selector", "reviewer"}:
            raise ValueError("unknown agent")
        if not shutil.which(self.executable):
            raise RuntimeError(f"OpenCode CLI not installed: {self.executable}")
        prompt = ("Process this protocol message. Return exactly one JSON object. "
                  "Never claim to have read a source absent from the payload.\n"
                  + json.dumps(payload, ensure_ascii=False, sort_keys=True))
        env = dict(os.environ, DYNAMICS_MEMORY_INTERNAL_AGENT="1")
        # --pure loads local agent definitions but skips external plugins;
        # internal env guard is defence in depth against capturing worker text.
        try:
            done = subprocess.run(
                [self.executable, "run", "--pure", "--agent", name,
                 "--format", "json", prompt],
                cwd=self.agent_root, env=env, capture_output=True, text=True,
                stdin=subprocess.DEVNULL,
                timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AgentTimeout(f"OpenCode {name} timed out after {self.timeout}s") from exc
        if done.returncode:
            raise RuntimeError(f"OpenCode {name} exited {done.returncode}: {done.stderr[-500:]}")
        if f'agent "{name}" not found' in done.stdout + done.stderr:
            raise RuntimeError(f"OpenCode did not load the {name} agent")
        text = "\n".join(
            str(row.get("part", {}).get("text", ""))
            for line in done.stdout.splitlines()
            for row in _event(line) if row.get("type") == "text")
        return self._parse_text(text, name)

    @staticmethod
    def _parse_text(text: str, name: str = "agent") -> dict:
        if not text.strip():
            raise AgentProtocolError(f"OpenCode {name} returned no final text")
        try:
            obj = json.loads(text.strip())
        except ValueError as exc:
            raise AgentProtocolError(str(exc)) from exc
        if not isinstance(obj, dict):
            raise AgentProtocolError("agent result must be a JSON object")
        return obj


def _event(line):
    try:
        obj = json.loads(line)
    except ValueError:
        return ()
    return (obj,) if isinstance(obj, dict) else ()
