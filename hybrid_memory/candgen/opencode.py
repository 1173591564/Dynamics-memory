"""opencode CLI 后端：`opencode run <单行指令> --format json --file=<附件>`。

--pure 关插件，--dir 把 agent 工作目录锁在 scratch；instruction+窗口写进附件
（opencode.cmd 批处理不吃多行 argv）。`env_extra` 注入 provider 密钥；
`config_path` 经 OPENCODE_CONFIG 指到自定义 provider 配置，不动全局 auth store。
stdout 是 JSON 事件流，收集 type=="text" 的 part 文本再解析。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from ..datasets.real_chat import InteractionWindow
from .base import CandidateGeneration
from .prompt import INSTRUCTION, parse_generation, serialize_window


class OpencodeCliGenerator:
    def __init__(self, model: str = "zhipu-env/glm-5.3-flash",
                 scratch_dir: str | Path = "experiments/out/_candgen_scratch",
                 timeout_s: int = 300, env_extra: dict | None = None,
                 config_path: str | Path | None = None):
        self.model = model
        self.scratch_dir = Path(scratch_dir)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        env = {**os.environ, **(env_extra or {})}
        cfg = Path(config_path) if config_path else (
            Path(__file__).resolve().parents[2] / "opencode.json")
        if cfg.exists():
            env["OPENCODE_CONFIG"] = str(cfg.resolve())
        self._env = env
        exe = shutil.which("opencode")
        if exe is None:
            raise RuntimeError("opencode CLI not found on PATH")
        self._exe = exe

    def generate(self, window: InteractionWindow,
                 prev_scene: str = "") -> CandidateGeneration:
        payload = self.scratch_dir / f"window_{window.id}.txt"
        payload.write_text(
            INSTRUCTION + "\n\n---\n\n" + serialize_window(window, prev_scene),
            encoding="utf-8")
        cmd = [
            self._exe, "run",
            "读取附件，按其中说明完成情境切分与记忆提取，只输出 JSON 对象。",
            "--format", "json", "--pure",
            "-m", self.model,
            "--dir", str(self.scratch_dir.resolve()),
            f"--file={payload.name}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=self.timeout_s, encoding="utf-8",
                              errors="replace", env=self._env)
        if proc.returncode != 0:
            raise RuntimeError(
                f"opencode exited {proc.returncode}\n"
                f"stderr: {proc.stderr[-2000:]}\n"
                f"stdout: {proc.stdout[-500:]}")
        reply = "".join(
            part["text"]
            for line in proc.stdout.splitlines()
            if line.strip()
            for ev in [json.loads(line)]
            if ev.get("type") == "text"
            for part in [ev.get("part", {})]
            if isinstance(part.get("text"), str)
        )
        if not reply.strip():
            raise RuntimeError("opencode returned no text part")
        return parse_generation(reply)
