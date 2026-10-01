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

from ..llm import ZhipuChatError, _cache_lookup, _cache_store

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
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "text":
            part = ev.get("part")
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
        elif ev.get("type") == "error":
            err = ev.get("error")
            data = err.get("data") if isinstance(err, dict) else None
            message = data.get("message") if isinstance(data, dict) else None
            name = err.get("name") if isinstance(err, dict) else None
            errors.append(str(message or name or "error"))
    return "".join(texts), errors, fallback


class OpencodeRunner:
    def __init__(self, model: str = "zhipu-env/glm-5.3-flash", *,
                 exe: str | None = None,
                 timeout_s: int = 300, env_extra: dict | None = None,
                 config_path=None, cache_dir=None, executor=None,
                 workdir=None, payload_dir=None, pure: bool = True):
        self.model = model
        self.timeout_s = timeout_s
        # pure=True：--pure 不加载插件（裁判/抽取器等无工具角色，防插件递归
        # 捕获）；pure=False：加载插件——调查员需要插件提供的 log_*/memory_*
        # 工具，此时靠 MEMORY_BRIDGE_ROLE=worker 让插件只注册工具、不挂钩子
        self.pure = pure
        self._exe = exe or shutil.which("opencode")
        if self._exe is None:
            raise RuntimeError("opencode CLI not found on PATH")
        # workdir = --dir（agent 定义从 <workdir>/.opencode/agent/ 发现）；
        # payload_dir = 附件落盘处（默认 workdir/.opencode/tmp）；不得反过来改变 agent 发现目录
        self.workdir = Path(workdir) if workdir else Path(__file__).resolve().parents[2]
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.payload_dir = Path(payload_dir) if payload_dir else self.workdir / ".opencode" / "tmp"
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, **(env_extra or {})}
        cfg = Path(config_path) if config_path else (
            Path(__file__).resolve().parents[2] / "opencode.json")
        if cfg.exists():
            env["OPENCODE_CONFIG"] = str(cfg.resolve())
        self._env = env
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._exec = executor or _default_executor

    def chat(self, system: str, user: str, *,
             agent: str | None = None) -> str:
        """与 llm.chat 同形；cache_dir 非空时按 (agent, model, system, user)
        磁盘缓存。只包含 agent 名称，不跟踪定义文件；改定义后须清理缓存。"""
        key = None
        if self.cache_dir is not None:
            raw = (f"opencode\0{agent or ''}\0{self.model}\0{system}\0{user}"
                   .encode("utf-8"))
            key = hashlib.sha256(raw).hexdigest()
            hit = _cache_lookup(self.cache_dir, key)
            if hit is not None:
                return hit
        out = self.run(system=system, user=user, agent=agent)
        if key is not None:
            _cache_store(self.cache_dir, key, out)
        return out

    def run(self, *, system: str, user: str, instruction: str | None = None,
            agent: str | None = None, env_extra: dict | None = None) -> str:
        """env_extra：本次调用追加的环境变量（如每信号的 MEMORY_BRIDGE_SIGNAL）。"""
        fd, name = tempfile.mkstemp(prefix="call_", suffix=".txt", dir=self.payload_dir)
        payload = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(system + "\n\n---\n\n" + user)
            try:    # --file 相对 --dir 解析；payload 在 workdir 内时给相对路径
                ref = str(payload.relative_to(self.workdir))
            except ValueError:
                ref = str(payload)
            cmd = [self._exe, "run", instruction or _CLI_INSTRUCTION,
                   "--format", "json",
                   *(["--pure"] if self.pure else []),
                   "-m", self.model,
                   "--dir", str(self.workdir),
                   f"--file={ref}"]
            if agent:
                cmd += ["--agent", agent]
            env = {**self._env, **(env_extra or {})} if env_extra else self._env
            try:
                code, stdout, stderr = self._exec(cmd, env, self.timeout_s)
            except subprocess.TimeoutExpired as exc:
                raise ZhipuChatError(
                    f"opencode timeout after {self.timeout_s}s") from exc
        finally:
            try:
                # 附件含未脱敏全文，不留盘；文件被占（杀毒/将死子进程）时
                # 清理失败不能掩盖真正的业务异常
                payload.unlink(missing_ok=True)
            except OSError:
                pass
        if code != 0:
            raise ZhipuChatError(
                f"opencode exited {code}: {(stderr or '')[-500:]}")
        reply, errors, fallback = _parse_events(stdout)
        if fallback or _FALLBACK_MARKER in (stderr or ""):
            raise ZhipuChatError(
                f"opencode agent 未找到，已静默回退默认壳: {agent!r}")
        if errors:
            raise ZhipuChatError(f"opencode error: {errors[0]}")
        if not reply.strip():
            raise ZhipuChatError("opencode returned no text part")
        return reply
