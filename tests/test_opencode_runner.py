"""OpencodeRunner 传输层测试：命令构造、事件流解析、缓存、降级。
全程无网络：executor 注入假实现。"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.agent.opencode import OpencodeRunner, collect_text
from hybrid_memory.llm import ZhipuChatError
from hybrid_memory.semantics.llm import LLMSemantics


class _FakeExec:
    """记录调用、按脚本返回 (code, stdout, stderr)。"""

    def __init__(self, out="ok", code=0, stderr=""):
        self.out = out
        self.code = code
        self.stderr = stderr
        self.calls = []

    def __call__(self, cmd, env, timeout_s):
        self.calls.append({"cmd": cmd, "env": env, "timeout": timeout_s})
        if isinstance(self.out, Exception):
            raise self.out
        return self.code, self.out, self.stderr


def _stream(*texts):
    lines = []
    for i, t in enumerate(texts):
        lines.append(json.dumps(
            {"type": "step_start", "part": {"type": "step-start"}}))
        lines.append(json.dumps(
            {"type": "text", "part": {"type": "text", "text": t}}))
    lines.append(json.dumps({"type": "step_finish",
                             "part": {"type": "step-finish"}}))
    return "\n".join(lines)


def _runner(tmp_path, exec_impl, **kw):
    return OpencodeRunner(exe="opencode-fake", scratch_dir=tmp_path / "scratch",
                          executor=exec_impl, **kw)


def test_command_shape_and_payload_file(tmp_path):
    fake = _FakeExec(_stream("hi"))
    r = _runner(tmp_path, fake)
    out = r.run(system="SYS", user="USR")
    assert out == "hi"
    cmd = fake.calls[0]["cmd"]
    assert cmd[0] == "opencode-fake" and cmd[1] == "run"
    assert isinstance(cmd[2], str) and cmd[2]      # instruction
    assert "--pure" in cmd and "--format" in cmd
    assert "-m" in cmd and cmd[cmd.index("-m") + 1] == r.model
    assert cmd[cmd.index("--dir") + 1] == str(r.workdir)
    f = [c for c in cmd if c.startswith("--file=")][0]
    payload = (r.workdir / f[len("--file="):]).read_text(encoding="utf-8")
    assert payload == "SYS\n\n---\n\nUSR"


def test_collect_text_ignores_non_text_and_junk():
    s = "not json\n" + _stream("a", "b") + "\n" + json.dumps({"type": "x"})
    assert collect_text(s) == "ab"


def test_cache_hit_skips_executor(tmp_path):
    fake = _FakeExec(_stream("verdict"))
    r = _runner(tmp_path, fake, cache_dir=tmp_path / "cache")
    assert r.chat("S", "U") == "verdict"
    assert r.chat("S", "U") == "verdict"
    assert len(fake.calls) == 1              # 第二次命中缓存
    assert r.chat("S", "U2") == "verdict"
    assert len(fake.calls) == 2


def test_nonzero_exit_raises(tmp_path):
    fake = _FakeExec("", code=2, stderr="boom")
    r = _runner(tmp_path, fake)
    with pytest.raises(ZhipuChatError):
        r.chat("S", "U")


def test_empty_text_raises(tmp_path):
    fake = _FakeExec(_stream(""))
    r = _runner(tmp_path, fake)
    with pytest.raises(ZhipuChatError):
        r.chat("S", "U")


def test_timeout_raises_chat_error(tmp_path):
    fake = _FakeExec(subprocess.TimeoutExpired(cmd="opencode", timeout=1))
    r = _runner(tmp_path, fake)
    with pytest.raises(ZhipuChatError):
        r.chat("S", "U")


def test_llmsemantics_judge_via_opencode_chat_fn(tmp_path):
    fake = _FakeExec(_stream("update"))
    r = _runner(tmp_path, fake)
    sem = LLMSemantics(chat_fn=r.chat)
    assert sem.judge(1, "部署在A", 1, "部署在B") == "update"


def test_llmsemantics_relevant_set_via_opencode_chat_fn(tmp_path):
    fake = _FakeExec(_stream("1, 3"))
    r = _runner(tmp_path, fake)
    sem = LLMSemantics(chat_fn=r.chat)
    assert sem.relevant_set(["a", "b", "c"], "q", "ans") == [True, False, True]


def test_llmsemantics_degrades_on_opencode_failure(tmp_path):
    fake = _FakeExec("", code=1, stderr="down")
    r = _runner(tmp_path, fake)
    sem = LLMSemantics(chat_fn=r.chat)
    assert sem.judge(1, "a", 2, "b") == "pending"       # 降级
    assert sem.relevant_set(["x"], "q", "a") == [True]  # 退化 selected-hit


def test_agent_silent_fallback_raises(tmp_path):
    # opencode 对未知 agent 只打警告就回退默认壳 → 必须显式报错
    warn = '! agent "no-such" not found. Falling back to default agent'
    fake = _FakeExec(warn + "\n" + _stream("update"))
    r = _runner(tmp_path, fake)
    with pytest.raises(ZhipuChatError, match="静默回退"):
        r.chat("S", "U", agent="no-such")


def test_error_event_raises_with_message(tmp_path):
    # API 失败时 exit code=0，错误在事件流里 → 取 error 消息报错
    err = json.dumps({"type": "error",
                      "error": {"name": "APIError",
                                "data": {"message": "Insufficient balance"}}})
    fake = _FakeExec(err)
    r = _runner(tmp_path, fake)
    with pytest.raises(ZhipuChatError, match="Insufficient balance"):
        r.chat("S", "U")


def test_agent_flag_in_command(tmp_path):
    fake = _FakeExec(_stream("update"))
    r = _runner(tmp_path, fake)
    r.chat("S", "U", agent="judge")
    cmd = fake.calls[0]["cmd"]
    assert cmd[cmd.index("--agent") + 1] == "judge"


def test_agent_participates_in_cache_key(tmp_path):
    fake = _FakeExec(_stream("update"))
    r = _runner(tmp_path, fake, cache_dir=tmp_path / "cache")
    r.chat("S", "U", agent="judge")
    r.chat("S", "U", agent="recognizer")   # 换 agent → 不吃上一条缓存
    assert len(fake.calls) == 2


def test_workdir_payload_split(tmp_path):
    fake = _FakeExec(_stream("ok"))
    wd = tmp_path / "proj"
    pd = wd / ".opencode" / "tmp"
    r = OpencodeRunner(exe="opencode-fake", workdir=wd, payload_dir=pd,
                       executor=fake)
    r.chat("S", "U")
    cmd = fake.calls[0]["cmd"]
    assert cmd[cmd.index("--dir") + 1] == str(wd)
    ref = [c for c in cmd if c.startswith("--file=")][0][len("--file="):]
    assert (wd / ref).read_text(encoding="utf-8") == "S\n\n---\n\nU"  # 相对 --dir


class _FailRunner:
    """chat 恒抛 ZhipuChatError 的假 runner。"""

    def __init__(self):
        self.calls = 0

    def chat(self, system, user, agent=None):
        self.calls += 1
        raise ZhipuChatError("boom")


def test_semantics_counts_degradation(tmp_path, monkeypatch):
    from hybrid_memory.semantics import opencode as oc
    r = _FailRunner()
    monkeypatch.setattr(oc, "OpencodeRunner", lambda **kw: r)
    sem = oc.OpencodeSemantics(cache_dir=None)
    assert sem.judge(1, "a", 2, "b") == "pending"   # 降级但不崩
    assert sem.relevant_set(["x"], "q", "a") == [True]
    assert sem.n_failed == 2 and r.calls == 2


def test_semantics_strict_aborts(tmp_path, monkeypatch):
    from hybrid_memory.semantics import opencode as oc
    r = _FailRunner()
    monkeypatch.setattr(oc, "OpencodeRunner", lambda **kw: r)
    sem = oc.OpencodeSemantics(cache_dir=None, strict=True)
    with pytest.raises(RuntimeError, match="strict"):
        sem.judge(1, "a", 2, "b")
    assert sem.n_failed == 1


def test_opencode_semantics_maps_role_to_agent(tmp_path, monkeypatch):
    from hybrid_memory.semantics import opencode as oc
    fake = _FakeExec(_stream("update"))
    r = _runner(tmp_path, fake)
    monkeypatch.setattr(oc, "OpencodeRunner", lambda **kw: r)
    sem = oc.OpencodeSemantics(cache_dir=None)   # runner 已注入，不碰 PATH
    assert sem.judge(1, "a", 2, "b") == "update"
    sem.relevant_set(["x"], "q", "a")
    agents = [c["cmd"][c["cmd"].index("--agent") + 1] for c in fake.calls]
    assert agents == ["judge", "recognizer"]
