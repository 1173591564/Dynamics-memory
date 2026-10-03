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

from ..errors import Fatal
from .protocol import AgentProtocolError, AgentTimeout

# §3.7：短协议指令作为位置 message 参数；payload 走 --file 私有临时文件。
PROTOCOL_INSTRUCTION = (
    "Process this protocol message. Return exactly one JSON object. "
    "Never claim to have read a source absent from the payload.")


class OpenCodeRunner:
    """Run real OpenCode agents, not a local imitation of their reasoning loop."""

    def __init__(self, project: Path, executable: str | None = None, timeout: int = 300):
        self.project = Path(project)
        self.executable = executable or os.environ.get("MEMORY_OPENCODE_BIN", "opencode")
        self.timeout = timeout
        self.agent_root = Path(__file__).resolve().parents[2]
        self._server = None       # 长驻 `opencode serve` 子进程（N48）
        self._server_url = None
        self._serve_log = None    # serve stdout/stderr 落盘日志（诊断用）

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def _child_env(self) -> dict:
        """CLI 子进程环境：继承父环境 + 内部守卫 + PYTHONPATH 拼接。"""
        env = dict(os.environ, DYNAMICS_MEMORY_INTERNAL_AGENT="1")
        # Windows 兼容：PYTHONPATH 用 os.pathsep 拼接并继承父环境
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (str(self.agent_root), env.get("PYTHONPATH")) if p)
        return env

    def _ensure_server(self) -> None:
        """惰性拉起长驻 `opencode serve --pure`（N48：serve+attach 模式）。

        真实 CLI 每次 `run` 会自举一个临时 server；该自举路径在 Windows
        非 POSIX 父进程（CreateProcess）下必在 createUserMessage 抛
        UnknownError（Bun 运行时怪癖，bash 直跑正常、serve+attach 正常）。
        serve+attach 全平台行为一致，且省掉每次调用的 server bootstrap。
        存活判定 = TCP 可连；serve 输出落临时日志供诊断。"""
        if self._server is not None and self._server.poll() is None:
            return
        import atexit
        import socket
        import tempfile
        import time
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        fd, log_path = tempfile.mkstemp(prefix="dynmem-serve-", suffix=".log")
        try:
            with os.fdopen(fd, "ab") as log_f:
                proc = subprocess.Popen(
                    self._spawn_argv(["serve", "--pure", "--hostname",
                                      "127.0.0.1", "--port", str(port)]),
                    cwd=self.agent_root, env=self._child_env(),
                    stdin=subprocess.DEVNULL, stdout=log_f, stderr=log_f)
        except OSError as exc:
            raise Fatal(f"OpenCode serve spawn failed: {exc}") from exc
        self._serve_log = log_path
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise Fatal(
                    f"OpenCode serve exited {proc.returncode} at boot "
                    f"(log: {log_path})")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            proc.terminate()
            raise Fatal(f"OpenCode serve not listening after 30s (log: {log_path})")
        self._server = proc
        self._server_url = f"http://127.0.0.1:{port}"
        atexit.register(self.close)

    def close(self) -> None:
        """终止长驻 serve 进程（atexit 兜底；幂等）。"""
        proc, self._server = self._server, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _spawn_argv(self, argv: list[str]) -> list[str]:
        """实际执行的完整命令（executable 解析点；测试用子类注入包装）。

        Windows 上 CreateProcess 不做 PATHEXT 解析：裸名 "opencode" 找不到
        npm 的 opencode.cmd 垫片（WinError 2）。先经 shutil.which 解析成
        带扩展名的绝对路径再 exec；解析失败保留原名让错误照常冒出。"""
        resolved = shutil.which(self.executable)
        return [resolved or self.executable] + argv

    def verify_channel(self) -> bool:
        """能力探测（§3.7）：CLI 必须支持 --file 附件通道。

        探测只证明通道存在，不证明 provider/模型质量。缺失即拒绝启动
        （bootstrap 转 Fatal），不回退超长 argv（Windows 40k 字符已复现
        崩溃）。help 输出缺失/命令失败都视为无通道。
        """
        if not self.available():
            raise Fatal(f"OpenCode CLI not installed: {self.executable}")
        try:
            done = subprocess.run(
                self._spawn_argv(["run", "--help"]),
                cwd=self.agent_root, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Fatal(f"OpenCode channel probe failed: {exc}") from exc
        if done.returncode or "--file" not in (done.stdout + done.stderr):
            raise Fatal(
                f"OpenCode CLI {self.executable!r} lacks the --file attachment "
                "channel required by \u00a73.7; refusing to start (no long-argv "
                "fallback)")
        self._ensure_server()   # 深探：serve 能拉起且端口可连才算通道可用
        return True

    def __call__(self, name: str, payload: dict) -> dict:
        return self.run(name, payload)

    def run(self, name: str, payload: dict) -> dict:
        if name not in {"hauler", "selector", "reviewer"}:
            raise ValueError("unknown agent")
        if not shutil.which(self.executable):
            raise RuntimeError(f"OpenCode CLI not installed: {self.executable}")
        # --pure 在 serve 侧生效（插件装载发生在 serve 启动时）；
        # internal env guard is defence in depth against capturing worker text.
        # 短指令是位置参数；payload 经 --file 私有 0600 UTF-8 JSON 临时文件
        # 传递（不进 argv——Windows argv 上限 40k 字符会崩）。
        self._ensure_server()
        import tempfile
        fd, tmp_path = tempfile.mkstemp(prefix="dynmem-payload-", suffix=".json")
        try:
            os.fchmod(fd, 0o600)              # 私有：payload 只许本进程与 CLI 读
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            done = subprocess.run(
                self._spawn_argv(["run", "--pure", "--attach", self._server_url,
                                  "--dir", str(self.agent_root),
                                  "--agent", name,
                                  "--format", "json", PROTOCOL_INSTRUCTION,
                                  "--file", tmp_path]),
                cwd=self.agent_root, env=self._child_env(),
                capture_output=True, text=True,
                stdin=subprocess.DEVNULL,
                timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AgentTimeout(f"OpenCode {name} timed out after {self.timeout}s") from exc
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
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
