"""OpencodeRunner 传输层测试：命令构造、事件流解析、缓存、降级。
全程无网络：executor 注入假实现。"""
import json
import subprocess
from pathlib import Path

import pytest


from hybrid_memory.agent.opencode import OpencodeRunner
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
    return OpencodeRunner(exe="opencode-fake", workdir=tmp_path / "scratch",
                          executor=exec_impl, **kw)


def test_command_shape_and_payload_file(tmp_path):
    seen = {}

    class Exec:
        def __call__(self, cmd, env, timeout_s):
            seen["cmd"] = cmd
            # 附件在 exec 期间必须存在；run() 返回后即被清理
            ref = [c for c in cmd if c.startswith("--file=")][0]
            ref = ref[len("--file="):]
            p = Path(ref)
            if not p.is_absolute():
                p = Path(cmd[cmd.index("--dir") + 1]) / ref
            seen["payload"] = p.read_text(encoding="utf-8")
            return 0, _stream("hi"), ""

    r = _runner(tmp_path, Exec())
    out = r.run(system="SYS", user="USR")
    assert out == "hi"
    cmd = seen["cmd"]
    assert cmd[0] == "opencode-fake" and cmd[1] == "run"
    assert isinstance(cmd[2], str) and cmd[2]      # instruction
    assert "--pure" in cmd and "--format" in cmd
    assert "-m" in cmd and cmd[cmd.index("-m") + 1] == r.model
    assert cmd[cmd.index("--dir") + 1] == str(r.workdir)
    assert seen["payload"] == "SYS\n\n---\n\nUSR"
    # 附件含未脱敏全文：exec 结束即删，不留盘
    assert not list(r.payload_dir.glob("call_*.txt"))


def test_runner_ignores_non_text_and_junk(tmp_path):
    s = "not json\n" + _stream("a", "b") + "\n" + json.dumps({"type": "x"})
    assert _runner(tmp_path, _FakeExec(s)).chat("S", "U") == "ab"


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
    assert sem.relevant_set(["x"], "q", "a") is None    # 失败→None，worker 计数退化


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
    seen = {}

    class Exec:
        def __call__(self, cmd, env, timeout_s):
            seen["cmd"] = cmd
            ref = [c for c in cmd if c.startswith("--file=")][0]
            ref = ref[len("--file="):]
            seen["payload"] = (Path(cmd[cmd.index("--dir") + 1]) / ref) \
                .read_text(encoding="utf-8")
            return 0, _stream("ok"), ""

    wd = tmp_path / "proj"
    pd = wd / ".opencode" / "tmp"
    r = OpencodeRunner(exe="opencode-fake", workdir=wd, payload_dir=pd,
                       executor=Exec())
    r.chat("S", "U")
    cmd = seen["cmd"]
    assert cmd[cmd.index("--dir") + 1] == str(wd)
    assert seen["payload"] == "S\n\n---\n\nU"   # --file 相对 --dir 解析
    assert not list(pd.glob("call_*.txt"))      # 附件用完即删


def test_payload_deleted_on_failure_paths(tmp_path):
    # finally 的真正目的：失败路径（非零退出 / exec 抛异常）附件也不留盘
    fake = _FakeExec("garbage", code=1)
    r = _runner(tmp_path, fake)
    with pytest.raises(ZhipuChatError):
        r.run(system="S", user="U")
    assert not list(r.payload_dir.glob("call_*.txt"))

    r2 = _runner(tmp_path, _FakeExec(OSError("spawn fail")))
    with pytest.raises(OSError):
        r2.run(system="S", user="U")
    assert not list(r2.payload_dir.glob("call_*.txt"))


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
    assert sem.relevant_set(["x"], "q", "a") is None  # 失败→None，不静默全记
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


def test_partial_text_followed_by_error_is_not_cached(tmp_path):
    out = _stream('partial result') + '\n' + json.dumps({
        "type": "error", "error": {"data": {"message": "stream interrupted"}}})
    cache = tmp_path / "cache"
    runner = _runner(tmp_path, _FakeExec(out), cache_dir=cache)
    with pytest.raises(ZhipuChatError, match="stream interrupted"):
        runner.chat("S", "U")
    assert not list(cache.glob("*.json"))


def test_runner_ignores_non_object_events_and_malformed_text_parts(tmp_path):
    noise = [None, [], 42, "noise", {"type": "text", "part": "not an object"}]
    out = '\n'.join(json.dumps(x) for x in noise) + '\n' + _stream("valid")
    assert _runner(tmp_path, _FakeExec(out)).chat("S", "U") == "valid"


@pytest.mark.parametrize("error", [None, [], "failed", {"data": "failed"}])
def test_malformed_error_events_still_fail_closed(tmp_path, error):
    out = _stream("partial") + '\n' + json.dumps({"type": "error", "error": error})
    with pytest.raises(ZhipuChatError, match="opencode error"):
        _runner(tmp_path, _FakeExec(out)).chat("S", "U")


def test_candgen_discovers_agent_in_repo_not_payload_directory(tmp_path, monkeypatch):
    import hybrid_memory.agent.opencode as transport
    from hybrid_memory.candgen.opencode import OpencodeCliGenerator
    from hybrid_memory.datasets.real_chat import InteractionWindow

    calls = []

    def execute(cmd, env, timeout):
        calls.append(cmd)
        workdir = Path(cmd[cmd.index("--dir") + 1])
        agent = cmd[cmd.index("--agent") + 1]
        assert (workdir / ".opencode" / "agent" / f"{agent}.md").is_file()
        payload = next(arg.split("=", 1)[1] for arg in cmd if arg.startswith("--file="))
        assert (workdir / payload).is_file()
        assert Path(payload).parent == tmp_path
        return 0, _stream('{"scene_name":"s","memories":[]}'), ""

    monkeypatch.setattr(transport.shutil, "which", lambda _: "opencode-fake")
    monkeypatch.setattr(transport, "_default_executor", execute)
    gen = OpencodeCliGenerator(payload_dir=tmp_path)
    assert gen.generate(InteractionWindow(0, 0, 0, 0, 0, ())).scene_name == "s"
    assert len(calls) == 1 and "--pure" in calls[0]
    assert not list(tmp_path.glob("call_*.txt"))


def test_concurrent_calls_use_private_unique_payloads(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import os
    import stat
    import threading

    barrier = threading.Barrier(4)
    paths = []

    def execute(cmd, env, timeout):
        ref = next(arg.split("=", 1)[1] for arg in cmd if arg.startswith("--file="))
        payload = Path(cmd[cmd.index("--dir") + 1]) / ref
        paths.append(payload)
        if os.name == "posix":
            assert stat.S_IMODE(payload.stat().st_mode) == 0o600
        text = payload.read_text(encoding="utf-8")
        barrier.wait(timeout=5)
        return 0, _stream(text), ""

    runner = _runner(tmp_path, execute)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: runner.run(system="S", user=str(i)), range(4)))
    assert results == [f"S\n\n---\n\n{i}" for i in range(4)]
    assert len(set(paths)) == 4 and all(not path.exists() for path in paths)


def test_invalid_chat_cache_is_rebuilt_and_failed_replace_keeps_previous(tmp_path, monkeypatch):
    from hybrid_memory import llm
    cache = tmp_path / "cache"
    fake = _FakeExec(_stream("ok"))
    runner = _runner(tmp_path, fake, cache_dir=cache)
    assert runner.chat("s", "u") == "ok"
    path = next(cache.glob("*.json"))
    for broken in ('{"out":', '[]', 'null', '{"out":4}'):
        path.write_text(broken)
        assert runner.chat("s", "u") == "ok"
    assert len(fake.calls) == 5
    monkeypatch.setattr(llm.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        llm._cache_store(cache, path.stem, "new")
    assert llm._cache_lookup(cache, path.stem) == "ok"
    assert not list(cache.glob("*.tmp"))
