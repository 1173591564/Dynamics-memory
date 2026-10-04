"""sidecar 子进程驾驭：拉起原版 `python -m hybrid_memory.server`，等健康、
喂轮次、判排空、优雅关闭。跑链走真实产品路径（bootstrap 完整接线：
trio 探测、DispatchWorker、语义任务），评测只经 HTTP 黑盒驱动。"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_INACTIVE_STATES = {"done", "dead", "operations", "cancelled"}


class Sidecar:
    """一个 sidecar 进程 = 一次链路运行（每链一进程，状态互不污染）。"""

    def __init__(self, repo: str, project: str, *, env: dict | None = None,
                 no_agent: bool = False, boot_timeout: float = 90.0,
                 module: str = "hybrid_memory.server"):
        self.repo = str(repo)
        self.project = str(project)
        self.extra_env = dict(env or {})
        self.no_agent = no_agent
        self.boot_timeout = boot_timeout
        # module：启动入口。默认真实 bootstrap；"eval.l2l3.serve_inline"
        # 为抽检用的进程内 runner 组装（协议等价，见其 docstring）。
        self.module = module
        self.proc: subprocess.Popen | None = None
        self.base: str | None = None
        self.token = ""
        self._tail: list[str] = []
        self._lines = queue.Queue(maxsize=200)
        self._reader = None

    def _read_output(self, stream) -> None:
        """持续排空子进程输出，启动线程仅以有界队列等端口声明。"""
        for line in stream:
            self._tail.append(line[-400:])
            self._tail = self._tail[-60:]
            try:
                self._lines.put_nowait(line)
            except queue.Full:
                pass

    # ---- 生命周期 ----
    def start(self) -> "Sidecar":
        env = {**os.environ, **self.extra_env}
        env["PYTHONUNBUFFERED"], env["PYTHONIOENCODING"] = "1", "utf-8"
        env["PYTHONPATH"] = self.repo + os.pathsep + env.get("PYTHONPATH", "")
        argv = [sys.executable, "-m", self.module,
                "--port", "0", "--project", self.project]
        if self.no_agent:
            argv.append("--no-agent")
        self.proc = subprocess.Popen(argv, cwd=self.repo, env=env,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace")
        self._reader = threading.Thread(target=self._read_output,
                                        args=(self.proc.stdout,), daemon=True)
        self._reader.start()
        deadline = time.monotonic() + self.boot_timeout
        while time.monotonic() < deadline:
            try:
                line = self._lines.get(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
            except queue.Empty:
                line = ""
            if m := re.search(r"http://127\.0\.0\.1:(\d+)", line):
                self.base = f"http://127.0.0.1:{m.group(1)}"
                break
            if self.proc is None or self.proc.poll() is not None:
                code = self.proc.returncode if self.proc else None
                self.close()
                raise RuntimeError(f"sidecar exited rc={code}; tail=\n" + "".join(self._tail))
        if self.base is None:
            self.close()
            raise RuntimeError("sidecar did not announce a port; tail=\n"
                               + "".join(self._tail))
        # 健康等待（含 trio verify_channel 的 serve 拉起时间）
        hdeadline = time.time() + self.boot_timeout
        while time.time() < hdeadline:
            try:
                st, body = self.get("/health")
                if st == 200:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            self.close()
            raise RuntimeError("sidecar never became healthy; tail=\n"
                               + "".join(self._tail))
        tok = (Path(self.project) / ".opencode" / "memory"
               / ".memory-token").read_text(encoding="utf-8").strip()
        self.token = tok
        return self

    def close_silent(self) -> str:
        """同 close，但尽力等待清理完成（评测收尾用）。"""
        return self.close()

    def close(self) -> str:
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False)
            else:
                proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(10)
        if self._reader is not None:
            try:
                self._reader.join(2)
            except Exception:  # noqa: BLE001  诊断读取尽力而为
                pass
        if proc is not None and proc.stdout:
            proc.stdout.close()
        return "".join(self._tail[-60:])

    # ---- HTTP ----
    def _req(self, method: str, path: str, body=None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, method=method, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"})
        try:
            with urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read() or b"{}")
        except HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def get(self, path: str) -> tuple[int, dict]:
        return self._req("GET", path)

    def post(self, path: str, body) -> tuple[int, dict]:
        return self._req("POST", path, body)

    # ---- 驾驭 ----
    def observe(self, user: str, assistant: str, request_id: str) -> tuple[int, dict]:
        return self.post("/observe", {"user_text": user,
                                      "assistant_text": assistant,
                                      "request_id": request_id})

    def search(self, query: str, *, budget_tokens: int = 128,
               passive: bool = True) -> tuple[int, dict]:
        return self.post("/search", {"query": query,
                                     "budget_tokens": budget_tokens,
                                     "passive": passive})

    def signals(self) -> dict:
        st, body = self.get("/signals")
        if st != 200:
            raise RuntimeError(f"/signals -> {st}: {body}")
        return body

    def active_tasks(self) -> dict:
        sig = self.signals()
        counts = dict(sig.get("tasks") or {})
        queued = {k: v for k, v in (sig.get("queued") or {}).items() if v}
        active = {k: v for k, v in counts.items()
                  if v and k not in _INACTIVE_STATES}
        return {"active": active, "queued": queued}

    def drain(self, timeout: float = 1800.0, quiet_s: float = 20.0) -> dict:
        """等任务机排空：无 active 态且队列计数全 0，且连续 quiet_s 秒保持。"""
        deadline = time.time() + timeout
        quiet_since: float | None = None
        last: dict = {}
        while time.time() < deadline:
            last = self.active_tasks()
            if not last["active"] and not last["queued"]:
                if quiet_since is None:
                    quiet_since = time.time()
                if time.time() - quiet_since >= quiet_s:
                    return {"drained": True, **last}
            else:
                quiet_since = None
            time.sleep(2.0)
        return {"drained": False, **last}
