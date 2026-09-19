"""cand-gen 解析/脱敏 + RealChatSemantics pending 裁判路径测试。全程无网络。"""
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.candgen.prompt import (parse_candidates, parse_generation,
                                          priority_to_salience, redact_secrets,
                                          serialize_window)
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Pool
from hybrid_memory.datasets.real_chat import (InteractionUnit,
                                              InteractionWindow)
from hybrid_memory.semantics import RealChatSemantics, normalize
from hybrid_memory.worker import SignalWorker


class _StubEmbedder:
    def __init__(self, table):
        self.table = table

    def embed(self, texts, keys=None):
        return np.array([self.table[t] for t in texts], dtype=np.float32)


def _unit(i):
    return InteractionUnit(id=i, start_time=i, end_time=i,
                           user_text=f"q{i}", assistant_text=f"a{i}",
                           assistant_turns=1)


def test_normalize_strips_case_ws_punct():
    assert normalize("  用户 喜欢 Dark-Mode。 ") == normalize("用户喜欢dark mode")
    assert normalize("A！B？") == normalize("ab")


def test_redact_secrets():
    assert "sk-" not in redact_secrets("key 是 sk-abc123def456ghi789")
    assert "[REDACTED]" in redact_secrets("api_key = \"0123456789abcdefZZ\"")
    assert redact_secrets("普通事实") == "普通事实"
    # 新增分支：带横杠新格式 key / gh[x]_ / JWT / 赋值式 / PEM 整块
    assert "sk-proj" not in redact_secrets("sk-proj-AbC123def456")
    assert "ghp_" not in redact_secrets("token ghp_A1b2C3d4E5f6G7h8I9j0")
    assert "github_pat_" not in redact_secrets(
        "github_pat_11ABCDEFG0abcdefghijklmn")
    assert "eyJ" not in redact_secrets(
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.dGVzdHNpZw")
    assert "[REDACTED]" in redact_secrets("password=hunter2xyz")
    pem = ("-----BEGIN RSA PRIVATE KEY-----\n"
           "MIIEpAIBAAKCAQEA7blahblahkeymaterial\n"
           "-----END RSA PRIVATE KEY-----")
    out = redact_secrets(f"配置 {pem} 完毕")
    assert "blahblah" not in out and "PRIVATE KEY" not in out


def test_parse_candidates_json_array_and_redact():
    out = parse_candidates('前言 [{"text":" 记住这个 "},'
                           ' {"text":"key sk-1234567890abcd"},'
                           ' {"no_text":1}] 后记')
    assert [c.text for c in out] == ["记住这个", "key [REDACTED]"]
    assert parse_candidates("没有数组") == []
    assert parse_candidates('```json\n[{"text":"x"}]\n```')[0].text == "x"


def test_parse_generation_v2_envelope_and_v1_fallback():
    g = parse_generation('{"scene_name":"在围绕X做Y","memories":'
                         '[{"content":"结论A","type":"work_fact","priority":85,'
                         '"source_unit_ids":[3,4]}]}')
    assert g.scene_name == "在围绕X做Y"
    assert g.candidates[0].text == "结论A"
    assert g.candidates[0].type == "work_fact"
    assert g.candidates[0].source_unit_ids == (3, 4)
    g2 = parse_generation('[{"text":"旧格式"}]')
    assert g2.scene_name == "" and g2.candidates[0].text == "旧格式"


def test_priority_to_salience_mapping():
    assert priority_to_salience(60) == 0.0
    assert priority_to_salience(80) == 0.5
    assert priority_to_salience(100) == 1.0
    assert priority_to_salience(None) == 0.5
    assert priority_to_salience("high") == 0.5
    assert priority_to_salience(True) == 0.5
    assert priority_to_salience(True, default=0.7) == 0.7


def test_parse_generation_salience_clamp_and_fallback():
    g = parse_generation('{"scene_name":"s","memories":['
                         '{"content":"a","salience":0.9},'
                         '{"content":"b","salience":1.7},'
                         '{"content":"c","salience":-2},'
                         '{"content":"d","priority":100},'
                         '{"content":"e","salience":true}]}')
    sals = [c.salience for c in g.candidates]
    assert sals == [0.9, 1.0, 0.0, 1.0, 0.5]
    assert g.candidates[3].priority == 100   # priority 保留为 legacy 元数据


def test_load_candgen_salience_explicit_and_fallback():
    from experiments.qa_real import _load_candgen
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "candgen.jsonl"
        p.write_text(json.dumps({"window_id": 0, "scene_name": "在围绕X做Y",
                                 "candidates": [
            {"text": "explicit", "salience": 1.4, "source_unit_ids": [1]},
            {"text": "prio", "priority": 100},
            {"text": "bare"},
        ]}, ensure_ascii=False) + "\n", encoding="utf-8")
        cands = _load_candgen(p)
    got = cands[0]
    assert got[0]["salience"] == 1.0
    assert got[0]["src"] == (1,)
    assert got[0]["scene"] == "在围绕X做Y"
    assert got[1]["salience"] == 1.0
    assert got[2]["salience"] == 0.5


def test_serialize_window_carries_prev_scene():
    w = InteractionWindow(id=0, start_unit_id=0, end_unit_id=1,
                          start_time=0, end_time=1,
                          units=(_unit(0), _unit(1)))
    s = serialize_window(w, prev_scene="在围绕A做B")
    assert "【上一个情境】：在围绕A做B" in s and "### Unit 0" in s


def test_serialize_window_role_structure():
    w = InteractionWindow(id=0, start_unit_id=0, end_unit_id=1,
                          start_time=0, end_time=1,
                          units=(_unit(0), _unit(1)))
    s = serialize_window(w)
    assert "### Unit 0" in s and "[user]" in s and "[assistant]" in s


def test_real_semantics_judge_levels():
    sem = RealChatSemantics()
    assert sem.judge(0, "same", 0, "same") == "synonym"
    assert sem.judge(1, "a", 2, "b") == "pending"
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "labels.jsonl"
        p.write_text(json.dumps({"a": "记住A", "b": "记住B",
                                 "verdict": "contradiction"},
                                ensure_ascii=False) + "\n",
                     encoding="utf-8")
        sem2 = RealChatSemantics(p)
        assert sem2.judge(1, normalize("记住A"), 2,
                          normalize("记住B")) == "contradiction"


def test_pending_tension_stays_in_backlog():
    """真实 judge 未标注时，worker 回报 pending，tension 不消解。"""
    sem = RealChatSemantics()
    v_same = np.array([1.0, 0.0], dtype=np.float32)
    table = {"事实A措辞": v_same, "事实A另一措辞": v_same}
    emb = _StubEmbedder(table)
    eng = MemoryEngine(Cfg(tension_delay=2), emb, sem)
    worker = SignalWorker(eng, sem)
    # 两条规范化不同但向量相同的候选 → ingest 近重复 → tension
    eng.observe([Event(sem.fingerprint("事实A措辞"), normalize("事实A措辞"),
                       "事实A措辞")], 0)
    eng.observe([Event(sem.fingerprint("事实A另一措辞"),
                       normalize("事实A另一措辞"), "事实A另一措辞")], 0)
    assert len(eng.mems) == 2 and len(eng.tensions) == 1
    for t in range(1, 6):
        eng.step(t)
        worker.process(t)
    assert len(eng.tensions) == 1, "pending verdict 不应消解"
    assert eng.n_resolve == 0
    # 补上标注后 worker 再判应消解
    key = next(iter(eng.tensions))
    a, b = eng.mems[key[0]], eng.mems[key[1]]
    sem.labels[tuple(sorted((a.value, b.value)))] = "synonym"
    eng.step(6)
    worker.process(6)
    assert len(eng.tensions) == 0 and eng.n_merge == 1


def run_all():
    fns = [v for k, v in list(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")


if __name__ == "__main__":
    run_all()
