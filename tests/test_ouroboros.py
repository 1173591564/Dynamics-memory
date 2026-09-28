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


# ---------------------------------------------------------------- InlineInvestigator（进程内调查员，假 LLM）
def _tool_msg(name, args, cid="c1"):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"id": cid, "type": "function",
                            "function": {"name": name,
                                         "arguments": json.dumps(args, ensure_ascii=False)}}]}


def test_inline_investigator_tool_loop_end_to_end(tmp_path):
    """recall_miss → AgentWorker → 进程内 function-calling 循环：
    log_search 真的打到服务层（按 signal_id 记账）→ 最终 JSON → propose 入库。
    调查过程不产生任何 observe（火墙天然成立）。"""
    from hybrid_memory.agent.inline import TOOLS, InlineInvestigator
    svc = _svc(tmp_path)
    svc.observe("端口改了吗", "服务端口从 8080 改成了 9090。")
    svc.report_miss("服务端口是多少", source="correction")
    seen = []

    def fake_chat(messages, tools):
        seen.append((messages, tools))
        if len(seen) == 1:
            assert {t["function"]["name"] for t in tools} == {
                "log_search", "log_timeline", "log_stats", "log_window",
                "memory_search", "memory_conflicts"}          # 只读工具面
            payload = messages[1]["content"]
            assert "服务端口是多少" in payload and '"signal_id"' in payload
            return _tool_msg("log_search", {"query": "端口"})
        tool_out = messages[-1]
        assert tool_out["role"] == "tool" and "unit 0" in tool_out["content"]
        return {"role": "assistant", "content": json.dumps({
            "proposals": [{"text": "服务端口已从 8080 改为 9090。",
                           "source_unit_ids": [0], "entity_key": "port"}],
            "diagnosis": {"miss_type": "dropped_by_candgen", "note": "漏抽"}},
            ensure_ascii=False)}

    inv = InlineInvestigator(svc, chat_fn=fake_chat)
    w = AgentWorker(svc, inv, kinds=("recall_miss",), budget=Budget(tool_calls=4))
    n_units = svc.log.count()
    st = w.process_once()
    assert st["run"] == 1 and st["accepted"] == 1 and st["diagnosed"] == 1
    assert svc.log.count() == n_units                     # 调查没被 observe
    m = [m for m in svc.engine.mems.values() if m.origin == "repair"]
    assert len(m) == 1 and "9090" in m[0].text and m[0].entity == "port"
    diag = json.loads((tmp_path / "diagnoses.jsonl").read_text(
        encoding="utf-8").splitlines()[-1])
    assert diag["usage"]["calls"] == 1                    # 服务端按信号计量


def test_inline_investigator_budget_and_turn_cap():
    """工具预算用尽 → PermissionError 作为工具结果回给模型；
    模型一直要工具 → 轮数上限后最后一轮不给工具、再不收尾就判失败。"""
    from hybrid_memory.agent.inline import InlineInvestigator
    svc = _svc()
    svc.observe("a", "b")
    sid = "recall_miss-x-1"
    svc.open_budget(sid, tool_calls=1, window_chars=100, before=None)
    calls = []

    def greedy(messages, tools):
        calls.append(tools)
        return _tool_msg("log_search", {"query": "a"}, cid=str(len(calls)))

    inv = InlineInvestigator(svc, chat_fn=greedy)
    out = inv({"signal_id": sid, "budget": {"tool_calls": 1}})
    assert out is None and inv.n_failed == 1
    assert len(calls) == 3 and calls[-1] is None          # 1+2 轮，末轮无工具
    assert svc.close_budget(sid)["calls"] == 2            # 第 2 次已超预算被拒

    def bad_json(messages, tools):
        return {"role": "assistant", "content": "不是 JSON"}
    inv2 = InlineInvestigator(svc, chat_fn=bad_json)
    assert inv2({"signal_id": "s"}) is None and inv2.n_failed == 1


def test_inline_investigator_llm_error_and_model_compat():
    from hybrid_memory.agent.inline import InlineInvestigator
    from hybrid_memory.llm import ZhipuChatError

    def down(messages, tools):
        raise ZhipuChatError("HTTP 401")
    inv = InlineInvestigator(_svc(), chat_fn=down, model="zhipu-env/glm-5.3-flash")
    assert inv({"signal_id": "s"}) is None and inv.n_failed == 1
    assert inv.model == "glm-5.3-flash"                   # 兼容旧 provider/model 写法
