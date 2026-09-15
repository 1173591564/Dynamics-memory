"""cand-gen 解析/脱敏 + RealChatSemantics pending 裁判路径测试。全程无网络。"""
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.candgen.prompt import (parse_candidates, parse_generation,
                                          redact_secrets, serialize_window)
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Pool
from hybrid_memory.datasets.real_chat import (InteractionUnit,
                                              InteractionWindow)
from hybrid_memory.semantics import RealChatSemantics, normalize


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
    """真实 judge 未标注时，tension 过 delay 也不消解。"""
    sem = RealChatSemantics()
    v_same = np.array([1.0, 0.0], dtype=np.float32)
    table = {"事实A措辞": v_same, "事实A另一措辞": v_same}
    emb = _StubEmbedder(table)
    eng = MemoryEngine(Cfg(tension_delay=2), emb, sem)
    # 两条规范化不同但向量相同的候选 → ingest 近重复 → tension
    eng.observe([Event(sem.fingerprint("事实A措辞"), normalize("事实A措辞"),
                       "事实A措辞")], 0)
    eng.observe([Event(sem.fingerprint("事实A另一措辞"),
                       normalize("事实A另一措辞"), "事实A另一措辞")], 0)
    assert len(eng.mems) == 2 and len(eng.tensions) == 1
    for t in range(1, 6):
        eng.step(t)
    assert len(eng.tensions) == 1, "pending verdict 不应消解"
    assert eng.n_resolve == 0
    # 补上标注后再 step 应消解
    key = next(iter(eng.tensions))
    a, b = eng.mems[key[0]], eng.mems[key[1]]
    sem.labels[tuple(sorted((a.value, b.value)))] = "synonym"
    eng.step(6)
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
