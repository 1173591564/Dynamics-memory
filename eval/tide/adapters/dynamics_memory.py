"""Dynamics-memory 适配器：只走 HTTP，不 import 引擎。

每条流拉起一个全新 sidecar 进程（临时项目目录、--port 0、--no-agent），
等 /health，读 <proj>/.opencode/memory/.memory-token，然后：
  ingest → POST /observe {user_text, assistant_text}
  serve  → POST /search  {query, budget_tokens, passive: true}
LLM / 嵌入端点由环境变量决定（ZAI_BASE_URL / ZAI_API_KEY），平台不关心。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

from ..protocol import Capabilities, MemorySystem


class DynamicsMemory(MemorySystem):
    caps = Capabilities(passive=True)

    def __init__(self, repo: str, python: str = "python", name: str = "dynamics-memory",
                 env: dict | None = None, extra_args: list[str] | None = None,
                 timeout: float = 120.0):
        self.repo = str(Path(repo).resolve())
        self.python, self.name = python, name
        self.env = {**os.environ, **(env or {})}
        self.env["PYTHONPATH"] = self.repo + os.pathsep + self.env.get("PYTHONPATH", "")
        self.extra = extra_args or []
        self.timeout = timeout
        self.proc = self.tmp = self.base = self.token = None
        self._calls = 0

    # ---- 进程管理 ----
    def _start(self):
        self.tmp = tempfile.mkdtemp(prefix="tide-dm-")
        self.proc = subprocess.Popen(
            [self.python, "-m", "hybrid_memory.server", "--port", "0",
             "--project", self.tmp, "--no-agent", *self.extra],
            cwd=self.repo, env=self.env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + self.timeout
        port = None
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"sidecar exited rc={self.proc.returncode}")
                continue
            if m := re.search(r"http://127\.0\.0\.1:(\d+)", line):
                port = int(m.group(1))
                break
        if port is None:
            raise RuntimeError("sidecar did not announce a port")
        self.base = f"http://127.0.0.1:{port}"
        self._get("/health")
        tok = Path(self.tmp) / ".opencode" / "memory" / ".memory-token"
        self.token = tok.read_text(encoding="utf-8").strip()

    def close(self):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None

    # ---- HTTP ----
    def _get(self, path):
        with urlopen(self.base + path, timeout=self.timeout) as r:
            return json.loads(r.read())

    def _post(self, path, body):
        req = Request(self.base + path, data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {self.token}"})
        with urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    # ---- 协议 ----
    def reset(self, stream_id):
        self.close()
        self._start()

    def ingest(self, user, assistant, t):
        self._post("/observe", {"user_text": user, "assistant_text": assistant})
        self._calls += 1

    def serve(self, query, t, budget_tokens, passive=True, probe=None):
        out = self._post("/search", {"query": query, "budget_tokens": budget_tokens,
                                     "passive": bool(passive)})
        return out.get("context", "")

    def cost(self):
        return {"observe_calls": self._calls}
