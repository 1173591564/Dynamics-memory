"""OpenCode spawn 模式自适应回归（N50/§3.7）。

N48 把全平台切到 serve+attach（Windows 自举崩溃的正解），但常驻 serve
在非 Windows 小内存环境实测不稳：attach 会话期间 serve 被 OOM 杀（无声
SIGKILL、日志无栈）、CLI 1.18.34 在 Linux 下 attach 间歇性 Session not
found / socket closed；自举薄调用单进程、用完即退，是非 Windows 平台的
历史验证形态（N44 起即在 Linux 验证通过）。

N50 定案：默认按平台选择（win32→serve+attach，其余→bootstrap）；
OPENCODE_SPAWN_MODE 环境变量覆盖平台默认；显式 mode= 参数最高（测试
与特殊环境用）。非法值 Fatal（拒绝启动，不静默回退）。
"""
from __future__ import annotations

import json
import sys

import pytest

from hybrid_memory.agents.opencode import OpenCodeRunner
from hybrid_memory.errors import Fatal


class _RunResult:
    returncode = 0
    stderr = ""
    stdout = json.dumps({"type": "text",
                         "part": {"text": '{"candidates":[]}'}}) + "\n"


class _HelpResult:
    returncode = 0
    stderr = ""
    stdout = "Usage: opencode run [options] [message..]\n  --file <path>\n"


def test_default_mode_follows_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    assert OpenCodeRunner(tmp_path).mode == "bootstrap"
    monkeypatch.setattr(sys, "platform", "win32")
    assert OpenCodeRunner(tmp_path).mode == "serve+attach"


def test_env_and_explicit_mode_override(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("OPENCODE_SPAWN_MODE", "bootstrap")
    assert OpenCodeRunner(tmp_path).mode == "bootstrap"
    monkeypatch.delenv("OPENCODE_SPAWN_MODE")
    assert (OpenCodeRunner(tmp_path, mode="serve+attach").mode
            == "serve+attach")
    with pytest.raises(Fatal):
        OpenCodeRunner(tmp_path, mode="nonsense")


def test_bootstrap_run_argv_has_no_attach_nor_dir(monkeypatch, tmp_path):
    runner = OpenCodeRunner(tmp_path, mode="bootstrap")
    sink: list = []
    monkeypatch.setattr("hybrid_memory.agents.opencode.shutil.which", lambda x: x)

    def run(cmd, **kwargs):
        sink.append(cmd)
        assert kwargs["env"]["DYNAMICS_MEMORY_INTERNAL_AGENT"] == "1"
        return _RunResult()
    monkeypatch.setattr("hybrid_memory.agents.opencode.subprocess.run", run)
    assert runner("hauler", {}) == {"candidates": []}
    cmd = sink[-1]
    assert cmd[1:3] == ["run", "--pure"]
    assert "--attach" not in cmd, "bootstrap 模式不挂 serve"
    assert "--dir" not in cmd
    assert cmd[cmd.index("--agent") + 1] == "hauler"
    assert cmd[cmd.index("--format") + 1] == "json"
    # 位置协议指令在 --format 之后、--file 之前（N44 顺序约束保持）
    assert cmd[cmd.index("json") + 1].startswith("Process this protocol")
    assert cmd.index("--file") == cmd.index("json") + 2
    assert runner._server is None


def test_bootstrap_verify_channel_never_spawns_serve(monkeypatch, tmp_path):
    runner = OpenCodeRunner(tmp_path, mode="bootstrap")
    monkeypatch.setattr("hybrid_memory.agents.opencode.shutil.which", lambda x: x)
    sink: list = []

    def run(cmd, **kwargs):
        sink.append(cmd)
        return _HelpResult()
    monkeypatch.setattr("hybrid_memory.agents.opencode.subprocess.run", run)
    assert runner.verify_channel() is True
    assert sink and all(c[1] != "serve" for c in sink), \
        "bootstrap 模式深探不得拉起常驻 serve"


def test_serve_attach_mode_keeps_n48_shape(monkeypatch, tmp_path):
    """显式 serve+attach 模式保留 N48 形状（Windows 正解不受 N50 影响）。"""
    runner = OpenCodeRunner(tmp_path, mode="serve+attach")
    monkeypatch.setattr("hybrid_memory.agents.opencode.shutil.which", lambda x: x)
    monkeypatch.setattr(runner, "_ensure_server", lambda: None)
    runner._server_url = "http://127.0.0.1:1"
    sink: list = []

    def run(cmd, **kwargs):
        sink.append(cmd)
        return _RunResult()
    monkeypatch.setattr("hybrid_memory.agents.opencode.subprocess.run", run)
    runner("hauler", {})
    cmd = sink[-1]
    assert cmd[cmd.index("--attach") + 1] == "http://127.0.0.1:1"
    assert cmd[cmd.index("--dir") + 1] == str(runner.agent_root)
