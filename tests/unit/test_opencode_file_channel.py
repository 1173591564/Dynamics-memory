"""OpenCode 文件通道回归（P0-2 / §3.7 / N44）。

覆盖：
- 短协议指令是位置参数（不是 --message 旗标），payload 经 --file 私有
  UTF-8 JSON 临时文件传递（文件内容即 payload JSON，0600，用后删除）；
- 子进程环境继承父环境；PYTHONPATH 用 os.pathsep 拼接（Windows 兼容）；
- verify_channel 能力探测：CLI 无 --file 通道 → 拒绝（bootstrap 转 Fatal
  不进 HTTP）；无长 argv 回退；
- 不 log 原始 prompt/凭据。
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from hybrid_memory.agents.opencode import OpenCodeRunner
from hybrid_memory.errors import Fatal

# 假 CLI：把观测（argv/env/文件内容与权限）写入 $FAKE_OC_OUT，
# 并输出 opencode 风格的 JSON 事件行。
FAKE_CLI = "#!/usr/bin/env python3\n" + r'''
import json, os, stat, sys
out = os.environ["FAKE_OC_OUT"]
obs = {"argv": sys.argv[1:], "env": {
    "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    "PATH_SET": "PATH" in os.environ,
    "GUARD": os.environ.get("DYNAMICS_MEMORY_INTERNAL_AGENT", ""),
    "HOME": os.environ.get("HOME", ""),
}}
if "--file" in sys.argv:
    p = sys.argv[sys.argv.index("--file") + 1]
    st = os.stat(p)
    obs["file_text"] = open(p, encoding="utf-8").read()
    obs["file_mode"] = oct(stat.S_IMODE(st.st_mode))
    obs["file_exists_after"] = None
with open(out, "w", encoding="utf-8") as f:
    json.dump(obs, f)
reply = json.dumps({"candidates": [{"text": "项目统一使用 bun 工具",
                                    "source_unit_ids": [0]}]})
if sys.argv[1:3] == ["run", "--help"]:
    print("Usage: opencode run [options] [message..]")
    print("  --file <path>   attach file")
    print("  --agent <name>")
    sys.exit(0)
print(json.dumps({"type": "text", "part": {"text": reply}}))
sys.exit(0)
'''

FAKE_CLI_NO_FILE = "#!/usr/bin/env python3\n" + r'''
import sys
if sys.argv[1:3] == ["run", "--help"]:
    print("Usage: opencode run [options]")
    print("  --agent <name>")
    sys.exit(0)
sys.exit(2)
'''


def _make_cli(tmp_path, body, name):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    p.chmod(0o755)
    return p


def test_file_channel_shape_and_permissions(tmp_path, monkeypatch):
    cli = _make_cli(tmp_path, FAKE_CLI, "fake_oc.py")
    obs = tmp_path / "obs.json"
    monkeypatch.setenv("FAKE_OC_OUT", str(obs))

    runner = OpenCodeRunner(tmp_path, executable=str(cli))
    payload = {"unit_id": 0, "candidates": [{"text": "x" * 50000,
                                             "source_unit_ids": [0]}]}
    out = runner.run("hauler", payload)
    assert out["candidates"][0]["text"] == "项目统一使用 bun 工具"
    data = json.loads(obs.read_text(encoding="utf-8"))
    argv = data["argv"]
    # 短协议指令是位置参数：紧跟在 --format json 之后、--file 之前
    assert "--message" not in argv, "指令不得走 --message 旗标"
    i_fmt = argv.index("--format")
    assert argv[i_fmt + 2] == "Process this protocol message. " \
        "Return exactly one JSON object. Never claim to have read a " \
        "source absent from the payload."
    # payload 在文件里，不在 argv 里（无长 argv 回退）
    assert "--file" in argv
    file_idx = argv.index("--file") + 1
    assert "x" * 100 not in " ".join(argv), "payload 不得进 argv"
    # 文件内容 = payload JSON；0600；用后删除
    assert json.loads(data["file_text"]) == payload
    assert data["file_mode"] == "0o600", f"临时文件必须 0600，实际 {data['file_mode']}"
    assert not Path(argv[file_idx]).exists(), "临时文件必须清理"
    # 环境继承 + os.pathsep + 守卫
    assert data["env"]["PATH_SET"] is True
    assert data["env"]["HOME"] != ""
    assert data["env"]["GUARD"] == "1"
    assert str(runner.agent_root) in data["env"]["PYTHONPATH"].split(os.pathsep)


def test_verify_channel_accepts_file_capable_cli(tmp_path, monkeypatch):
    cli = _make_cli(tmp_path, FAKE_CLI, "fake_oc2.py")
    monkeypatch.setenv("FAKE_OC_OUT", str(tmp_path / "obs2.json"))

    runner = OpenCodeRunner(tmp_path, executable=str(cli))
    assert runner.verify_channel() is True


def test_verify_channel_refuses_cli_without_file(tmp_path, monkeypatch):
    cli = _make_cli(tmp_path, FAKE_CLI_NO_FILE, "fake_old_oc.py")
    monkeypatch.setenv("FAKE_OC_OUT", str(tmp_path / "obs3.json"))

    runner = OpenCodeRunner(tmp_path, executable=str(cli))
    with pytest.raises(Fatal, match="--file"):
        runner.verify_channel()


def test_bootstrap_refuses_startup_without_channel(tmp_path):
    """端到端：CLI 缺 --file 通道 → bootstrap.main 在 serve 前 Fatal。"""
    import subprocess
    cli = _make_cli(tmp_path, FAKE_CLI_NO_FILE, "fake_old_oc2.py")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".env").write_text("ZAI_API_KEY=test-key\n", encoding="utf-8")
    env = {"MEMORY_PIPELINE": "opencode", "MEMORY_OPENCODE_BIN": str(cli),
           "PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}
    out = subprocess.run(
        [sys.executable, "-c",
         "from hybrid_memory.transport.bootstrap import main; main()",
         "--project", str(proj), "--port", "0"],
        cwd=Path(__file__).resolve().parents[2], env=env,
        capture_output=True, text=True, timeout=120)
    assert out.returncode != 0, "缺通道必须拒绝启动"
    assert "--file" in out.stderr and "Fatal" in out.stderr
