"""opencode CLI 传输层：一次问答 → `opencode run` 执行。

与 llm.chat 同形（system+user → 文本），可直接作为 LLMSemantics 的
chat_fn 注入——裁判/识别器/巩固器因此跑在 opencode 会话壳里（后续可
挂工具与 agent 定义）。事件流解析、磁盘缓存（回放确定性）、超时处理
收在这一处；失败抛 ZhipuChatError，沿用 LLMSemantics 既有降级路径。

缓存键带 "opencode" 前缀命名空间，与 llm.chat 的裸 API 缓存互不覆盖
（同一 prompt 两种传输各自的输出都留档，可对比）。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..llm import ZhipuChatError

_CLI_INSTRUCTION = "读取附件，按附件中的说明完成任务，只输出结果，不要任何解释。"


def _default_executor(cmd, env, timeout_s):
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_s, encoding="utf-8",
                          errors="replace", env=env)
    return proc.returncode, proc.stdout, proc.stderr


_FALLBACK_MARKER = "Falling back to default agent"


def _parse_events(stdout: str):
    """→ (text, errors, fallback)。opencode 对未知 agent 静默回退（仅打一行
    警告），API 失败时 exit code 仍为 0 而事件流里带 type=="error"——
    两者都必须显式识别，否则裁判在错误配置下悄悄跑默认壳。"""
    texts, errors, fallback = [], [], False
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if _FALLBACK_MARKER in line:
            fallback = True
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "text":
            part = ev.get("part") or {}
            if isinstance(part.get("text"), str):
                texts.append(part["text"])
        elif ev.get("type") == "error":
            err = ev.get("error") or {}
            data = err.get("data") or {}
            errors.append(str(data.get("message") or err.get("name") or "error"))
    return "".join(texts), errors, fallback


def collect_text(stdout: str) -> str:
    """从 opencode JSON 事件流里收集 type=="text" 的 part 文本。"""
    return _parse_events(stdout)[0]


class OpencodeRunner:
    def __init__(self, model: str = "zhipu-env/glm-5.3-flash", *,
                 exe: str | None = None, scratch_dir=None,
                 timeout_s: int = 300, env_extra: dict | None = None,
                 config_path=None, cache_dir=None, executor=None,
                 workdir=None, payload_dir=None):
        self.model = model
        self.timeout_s = timeout_s
        self._exe = exe or shutil.which("opencode")
        if self._exe is None:
            raise RuntimeError("opencode CLI not found on PATH")
        # workdir = --dir（agent 定义从 <workdir>/.opencode/agent/ 发现）；
        # payload_dir = 附件落盘处（默认同 workdir）
        self.workdir = (Path(workdir) if workdir else
                        Path(scratch_dir) if scratch_dir else
                        Path(tempfile.gettempdir()) / "hybrid_memory_opencode")
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.payload_dir = Path(payload_dir) if payload_dir else self.workdir
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, **(env_extra or {})}
        cfg = Path(config_path) if config_path else (
            Path(__file__).resolve().parents[2] / "opencode.json")
        if cfg.exists():
            env["OPENCODE_CONFIG"] = str(cfg.resolve())
        self._env = env
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._exec = executor or _default_executor
        self._tag = os.urandom(3).hex()
        self._seq = 0

    def chat(self, system: str, user: str, *,
             agent: str | None = None) -> str:
        """与 llm.chat 同形；cache_dir 非空时按 (agent, model, system, user)
        磁盘缓存。agent 参与缓存键——换 agent 定义即换缓存命名空间。"""
        key = None
        if self.cache_dir is not None:
            raw = (f"opencode\0{agent or ''}\0{self.model}\0{system}\0{user}"
                   .encode("utf-8"))
            key = hashlib.sha256(raw).hexdigest()
            path = self.cache_dir / f"{key}.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))["out"]
        out = self.run(system=system, user=user, agent=agent)
        if key is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(
                json.dumps({"out": out}, ensure_ascii=False), encoding="utf-8")
        return out

    def run(self, *, system: str, user: str, instruction: str | None = None,
            agent: str | None = None) -> str:
        self._seq += 1
        payload = self.payload_dir / f"call_{self._tag}_{self._seq}.txt"
        payload.write_text(system + "\n\n---\n\n" + user, encoding="utf-8")
        try:    # --file 相对 --dir 解析；payload 在 workdir 内时给相对路径
            ref = str(payload.relative_to(self.workdir))
        except ValueError:
            ref = str(payload)
        cmd = [self._exe, "run", instruction or _CLI_INSTRUCTION,
               "--format", "json", "--pure",
               "-m", self.model,
               "--dir", str(self.workdir),
               f"--file={ref}"]
        if agent:
            cmd += ["--agent", agent]
        try:
            code, stdout, stderr = self._exec(cmd, self._env, self.timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise ZhipuChatError(f"opencode timeout after {self.timeout_s}s") from exc
        if code != 0:
            raise ZhipuChatError(
                f"opencode exited {code}: {(stderr or '')[-500:]}")
        reply, errors, fallback = _parse_events(stdout)
        if fallback or _FALLBACK_MARKER in (stderr or ""):
            raise ZhipuChatError(
                f"opencode agent 未找到，已静默回退默认壳: {agent!r}")
        if not reply.strip():
            if errors:
                raise ZhipuChatError(f"opencode error: {errors[0]}")
            raise ZhipuChatError("opencode returned no text part")
        return reply
