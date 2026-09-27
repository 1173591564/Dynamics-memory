"""衔尾蛇回路测试：信号（recall_miss / extract_due）→ 调查员 → 提议入库。

调查员用假实现（不碰 LLM/opencode），只验证引擎—服务—worker 之间的契约：
去重与合并、消费者隔离、载荷形状、解析鲁棒性、失败重试与放弃、日预算、
提议校验与来源标签。全程无网络。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.agent.investigator import (Budget, Investigation,
                                              build_payload,
                                              parse_investigation)
from hybrid_memory.agent.loop import AgentWorker
from hybrid_memory.candgen.base import CandidateGeneration
from hybrid_memory.config import Cfg
from hybrid_memory.core.signals import SignalQueue
from hybrid_memory.core.types import Event
from hybrid_memory.semantics import RealChatSemantics
from hybrid_memory.server import MemoryService


# ---------------------------------------------------------------- 夹具
class _HashEmbedder:
    """字符哈希词袋：确定、无网络，相近文本余弦相近。"""
    def embed(self, texts, keys=None):
        out = []
        for t in texts:
            v = np.zeros(64)
            for ch in t:
                v[hash(ch) % 64] += 1
            out.append(v / (np.linalg.norm(v) or 1.0))
        return np.array(out, dtype=np.float32)


class _NoCandGen:
    """被动抽取什么都不抽——模拟漏记，让修复回路有事可做。"""
    def generate(self, window, prev_scene=""):
        return CandidateGeneration(candidates=(), scene_name="接入")


class _BoomCandGen:
    def generate(self, window, prev_scene=""):
        raise RuntimeError("LLM down")


def _svc(tmp_path=None, generator=None, **cfg):
    base = dict(theta=0.2, suppression_on=False, defer_credit=True,
                useful_hit=True)
    base.update(cfg)
    return MemoryService(Cfg(**base), _HashEmbedder(), RealChatSemantics(None),
                         generator or _NoCandGen(), state_dir=tmp_path)


def _ev(text, t=0, origin="repair", src=(0,)):
    return Event(text, text, text, tuple(src), origin=origin)


# ---------------------------------------------------------------- 调查员：载荷与解析
def test_build_payload_shapes():
    q = SignalQueue()
    miss = q.emit("recall_miss", {"q": "端口?", "hints": ["h"], "sources": ["correction"],
                                  "retrieved": [{"id": 1}] * 10,
                                  "entities": ["a.ts"]}, 5, key="miss:端口?")
    p = build_payload(miss, signal_id="s1", t=6, scene="接入", budget=Budget(3, 999),
                      entity_hints={"a.ts": 2})
    assert p["kind"] == "recall_miss" and p["q"] == "端口?" and p["before"] == 6
    assert len(p["retrieved"]) == 8 and p["budget"] == {"tool_calls": 3, "window_chars": 999}
    assert p["entity_mentions"] == {"a.ts": 2}
    due = q.emit("extract_due", {"unit_id": 4, "reasons": ["quant"], "entities": [],
                                 "scene": "x"}, 5, key="unit:4")
    p = build_payload(due, signal_id="s2", t=6, scene="接入", budget=Budget())
    assert p["unit_id"] == 4 and p["reasons"] == ["quant"] and "entity_mentions" not in p


def test_parse_investigation_tolerates_noise_and_validates_items():
    text = ('调查完毕。\n```json\n{"proposals":[{"text":"端口是 8080","kind":"weird",'
            '"salience":7,"source_unit_ids":[1,"2",true,2.0]},{"text":"  "},"junk"],'
            '"verdicts":[{"left":1,"right":1,"verdict":"update"},'
            '{"left":2,"right":3,"verdict":"UPDATE"},{"left":"x"}],'
            '"diagnosis":{"miss_type":"dropped_by_candgen","note":"漏了"}}\n```')
    inv = parse_investigation(text)
    assert inv is not None
    assert len(inv.proposals) == 1
    p = inv.proposals[0]
    assert p["kind"] == "work_fact" and p["salience"] == 1.0
    assert p["source_unit_ids"] == [1, 2, 2]
    assert inv.verdicts == [(2, 3, "update")]
    assert inv.diagnosis == {"miss_type": "dropped_by_candgen", "note": "漏了"}


def test_parse_investigation_rejects_garbage():
    assert parse_investigation("") is None
    assert parse_investigation("没有 JSON") is None
    assert parse_investigation('{"foo": 1}') is None          # 不是调查结果对象
    inv = parse_investigation('{"diagnosis":{"miss_type":"nonsense"}}')
    assert inv is not None and inv.diagnosis is None


# ---------------------------------------------------------------- AgentWorker 回路
def _fake(proposals=(), diagnosis=None, verdicts=()):
    calls = []

    def investigate(payload):
        calls.append(payload)
        return Investigation(proposals=list(proposals), verdicts=list(verdicts),
                             diagnosis=diagnosis)
    investigate.calls = calls
    return investigate


def test_correction_triggers_repair_and_recall_improves():
    svc = _svc()
    svc.observe("proxy 的 handler.ts 里 hermes 是什么类型？",
                "header-only：_headerOnlyAgents 硬编码包含 hermes。")
    r1 = svc.recall("hermes 是什么类型的 agent")
    assert r1["n"] == 0                                    # 被动抽取漏了
    svc.observe("不对，后来把 hermes 移出 _headerOnlyAgents 了", "收到，改为 form agent。")
    assert svc.engine.signals.peek_kinds()["recall_miss"] == 1

    fake = _fake(proposals=[{"text": "hermes 在 proxy/handler.ts 里已移出 _headerOnlyAgents，现为 form agent。",
                             "kind": "work_fact", "salience": 0.8,
                             "source_unit_ids": [0, 1], "entity_key": "hermes"}],
                 diagnosis={"miss_type": "dropped_by_candgen", "note": "同窗口漏抽"})
    agent = AgentWorker(svc, fake, idle_s=0.01)
    svc.attach_agent(agent)
    stats = agent.process_once()
    assert stats["run"] == stats["taken"] >= 1 and stats["failed"] == 0
    miss_payload = [c for c in fake.calls if c["kind"] == "recall_miss"][0]
    assert miss_payload["q"].startswith("proxy 的 handler.ts")
    assert miss_payload["sources"] == ["correction"]
    assert miss_payload["entity_mentions"]["handler.ts"] >= 1
    assert miss_payload["before"] == 2                     # 纠正那一轮（t=1）可见

    mems = list(svc.engine.mems.values())
    assert len(mems) == 1 and mems[0].origin == "repair" and mems[0].entity == "hermes"
    assert svc.recall("hermes 是什么类型的 agent")["n"] == 1
    assert svc.miss_counts == {"dropped_by_candgen": len(fake.calls)}
    assert svc.engine.signals.peek_kinds().get("recall_miss") is None


def test_extract_due_uses_extract_origin_and_causal_bound():
    svc = _svc()
    svc.observe("以后统一用 bun 跑脚本", "好的")            # decision → extract_due
    fake = _fake(proposals=[
        {"text": "脚本统一用 bun 跑。", "source_unit_ids": [0]},
        {"text": "来自未来的事实", "source_unit_ids": [5]},
        {"text": "我检索了日志，没有发现相关记录", "source_unit_ids": [0]},
        {"text": "没有来源", "source_unit_ids": []},
    ])
    agent = AgentWorker(svc, fake)
    stats = agent.process_once()
    assert stats["run"] == 1 and stats["accepted"] == 1
    assert fake.calls[0]["kind"] == "extract_due" and fake.calls[0]["reasons"] == ["decision"]
    mem = next(iter(svc.engine.mems.values()))
    assert mem.origin == "extract" and mem.text == "脚本统一用 bun 跑。"
    assert svc.n_rejected == 3


def test_investigator_failure_requeues_then_gives_up(capsys):
    svc = _svc()
    svc.report_miss("端口是多少", source="external")
    calls = []

    def flaky(payload):
        calls.append(payload)
        return None                                        # 解析失败/异常都走这里
    agent = AgentWorker(svc, flaky, max_attempts=2)
    s1 = agent.process_once()
    assert s1["failed"] == 1 and svc.engine.signals.peek_kinds() == {"recall_miss": 1}
    s2 = agent.process_once()
    assert s2["failed"] == 1 and agent.n_gave_up == 1
    assert svc.engine.signals.peek_kinds() == {}          # 放弃，不再重排
    assert len(calls) == 2
    assert "放弃" in capsys.readouterr().err


def test_investigator_exception_is_contained():
    svc = _svc()
    svc.report_miss("端口是多少", source="external")

    def boom(payload):
        raise RuntimeError("opencode exploded")
    agent = AgentWorker(svc, boom, max_attempts=1)
    stats = agent.process_once()
    assert stats["failed"] == 1 and agent.n_gave_up == 1
    assert svc.signals()["open_budgets"] == []             # 预算已关


def test_daily_cap_pauses_and_keeps_signals():
    svc = _svc()
    svc.report_miss("a", source="external")
    svc.report_miss("b", source="external")
    svc.report_miss("c", source="external")
    fake = _fake(diagnosis={"miss_type": "no_miss"})
    agent = AgentWorker(svc, fake, daily_cap=2)
    stats = agent.process_once()
    assert stats["run"] == 2 and stats["deferred"] == 1
    assert agent.paused_until and svc.engine.signals.peek_kinds() == {"recall_miss": 1}
    assert agent.process_once()["run"] == 0               # 仍在暂停


def test_recent_dedupe_skips_same_question():
    svc = _svc()
    fake = _fake(diagnosis={"miss_type": "never_logged"})
    agent = AgentWorker(svc, fake, dedupe_ttl_s=3600)
    svc.report_miss("端口是多少", source="external")
    agent.process_once()
    svc.report_miss("端口是多少", source="external")       # 24h 内同问题
    stats = agent.process_once()
    assert stats["skipped"] == 1 and stats["run"] == 0 and len(fake.calls) == 1


def test_max_signals_defers_rest():
    svc = _svc()
    for q in ("a", "b", "c"):
        svc.report_miss(q, source="external")
    agent = AgentWorker(svc, _fake(diagnosis={"miss_type": "no_miss"}))
    stats = agent.process_once(max_signals=1)
    assert stats["run"] == 1 and stats["deferred"] == 2
    assert svc.engine.signals.peek_kinds() == {"recall_miss": 2}


def test_verdicts_from_investigator_are_applied():
    svc = _svc()
    a = svc.engine.propose([_ev("部署在 A 服务器", origin="extract")], 0)[0]
    b = svc.engine.propose([_ev("部署在 B 服务器", origin="extract")], 0)[0]
    svc.report_miss("部署在哪", source="external")
    agent = AgentWorker(svc, _fake(verdicts=[(b, a, "update")],
                                   diagnosis={"miss_type": "too_coarse"}))
    stats = agent.process_once()
    assert stats["verdicts"] == 1
    assert svc.engine.mems[a].superseded_by == b


def test_candgen_failure_keeps_unit_and_flags_extract_due():
    svc = _svc(generator=_BoomCandGen())
    out = svc.observe("在吗", "在的")                      # 闲聊：原本不会触发
    assert out["candidates"] == 0 and "candgen_failed" in out["reasons"]
    assert svc.n_candgen_fail == 1 and svc.log.count() == 1
    assert svc.engine.signals.peek_kinds() == {"extract_due": 1}


def test_agent_worker_thread_start_stop():
    svc = _svc()
    fake = _fake(diagnosis={"miss_type": "no_miss"})
    agent = AgentWorker(svc, fake, idle_s=0.05)
    svc.attach_agent(agent)
    agent.start()
    try:
        svc.report_miss("线程里的问题", source="external")
        import time
        for _ in range(100):
            if fake.calls:
                break
            time.sleep(0.02)
        assert fake.calls and agent.stats()["alive"]
    finally:
        agent.stop()
    assert not agent.stats()["alive"]


# ---------------------------------------------------------------- 状态持久化
def test_repair_memories_survive_restart(tmp_path):
    svc = _svc(tmp_path)
    svc.observe("端口是多少", "8080")
    svc.propose([{"text": "服务端口是 8080。", "source_unit_ids": [0], "entity_key": "port"}],
                origin="repair")
    svc.diagnose("dropped_by_candgen", "x")
    svc.save()
    svc2 = _svc(tmp_path)
    m = next(iter(svc2.engine.mems.values()))
    assert m.origin == "repair" and m.entity == "port"
    assert svc2.miss_counts == {"dropped_by_candgen": 1}
    assert svc2.log.count() == 1                         # L0 也在
    lines = (tmp_path / "diagnoses.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["miss_type"] == "dropped_by_candgen"


# ---------------------------------------------------------------- OpencodeInvestigator 传输层（假 runner）
def test_opencode_investigator_wires_role_env_and_parses():
    from hybrid_memory.agent.investigator import OpencodeInvestigator
    from hybrid_memory.llm import ZhipuChatError

    class _Runner:
        def __init__(self):
            self.calls = []
            self.reply = '{"proposals":[],"diagnosis":{"miss_type":"no_miss"}}'

        def run(self, *, system, user, instruction=None, agent=None, env_extra=None):
            self.calls.append({"system": system, "user": user, "agent": agent,
                               "env_extra": env_extra})
            if self.reply is None:
                raise ZhipuChatError("opencode timeout")
            return self.reply

    r = _Runner()
    inv = OpencodeInvestigator(port=1, token="tok", runner=r)
    out = inv({"signal_id": "sig-9", "kind": "recall_miss", "q": "端口?"})
    assert out is not None and out.diagnosis == {"miss_type": "no_miss", "note": ""}
    call = r.calls[0]
    assert call["agent"] == "investigator"
    assert call["env_extra"] == {"MEMORY_BRIDGE_SIGNAL": "sig-9"}   # 每信号一个号
    assert json.loads(call["user"])["q"] == "端口?"
    assert "log_window" in call["system"] and "memory_propose" in call["system"]
    r.reply = "不是 JSON"
    assert inv({"signal_id": "s2"}) is None and inv.n_failed == 1
    r.reply = None
    assert inv({"signal_id": "s3"}) is None and inv.n_failed == 2
    assert inv.n_calls == 3


def test_opencode_investigator_runner_is_non_pure_worker(monkeypatch, tmp_path):
    """真 runner 构造：pure=False（要插件工具）+ worker 角色/端口/令牌环境。"""
    from hybrid_memory.agent import investigator as mod
    captured = {}

    class _FakeRunner:
        def __init__(self, **kw):
            captured.update(kw)
    monkeypatch.setattr(mod, "OpencodeRunner", _FakeRunner)
    mod.OpencodeInvestigator(port=17872, token="abc", model="m/x",
                             env_extra={"ZAI_API_KEY": "k"}, workdir=tmp_path)
    assert captured["pure"] is False and captured["model"] == "m/x"
    env = captured["env_extra"]
    assert env["MEMORY_BRIDGE_ROLE"] == "worker"
    assert env["MEMORY_BRIDGE_PORT"] == "17872" and env["MEMORY_BRIDGE_TOKEN"] == "abc"
    assert env["ZAI_API_KEY"] == "k"
