import json

import pytest

from tide.gen_l1 import generate
from tide.ledger import Stream, load_streams, save_streams
from tide.meta import run_meta
from tide.runner import run
from tide.score import aggregate, classify_answer, score_context
from tide.systems.reference import BM25, NoMemory, Oracle, Parsed, Recency
from tide.text import approx_tokens, has_token, truncate_lines


@pytest.fixture(scope="module")
def streams():
    return generate(seeds=2)


def test_deterministic():
    a = [s.to_json() for s in generate(seeds=1)]
    b = [s.to_json() for s in generate(seeds=1)]
    assert json.dumps(a) == json.dumps(b)


def test_roundtrip(tmp_path, streams):
    save_streams(streams, tmp_path)
    back = load_streams(tmp_path)
    assert [s.to_json() for s in back] == [s.to_json() for s in sorted(streams, key=lambda s: s.id)]


def test_tokens_unique_and_isolated(streams):
    for s in streams:
        vals = [f.value for f in s.facts]
        assert len(vals) == len(set(vals))
        for p in s.probes:
            assert p.t <= len(s.turns)
            # 探针问题不泄露答案
            assert not any(has_token(p.query, v) for v in vals)
        # 更新/撤回话术不复述旧值：update 轮只含新值，retract 轮不含任何值
        facts = {f.id: f for f in s.facts}
        for t in s.turns:
            present = {v for v in vals if has_token(t.user + t.assistant, v)}
            if t.op == "update":
                assert present == {facts[t.facts[0]].value}
            elif t.op == "retract":
                assert not present


def test_text_utils():
    assert approx_tokens("日志级别定为 bidemi-4629。") == 6 + 1 + 1 + 1 + 1
    assert has_token("x bidemi-4629。", "bidemi-4629")
    assert not has_token("bidemi-46290", "bidemi-4629")
    txt, used, cut = truncate_lines("一二三\n四五六\n七八九", 7)
    assert txt == "一二三\n四五六" and used == 7 and cut


def test_score_and_classify(streams):
    p = next(p for s in streams for p in s.probes if s.dimension == "V" and p.knob > 1)
    assert score_context(p.oracle_context, p.gold, p.harmful) == {"S": 1.0, "H": 0.0, "u": 1.0}
    assert score_context(p.harmful[0], p.gold, p.harmful)["u"] == -1.0
    assert classify_answer(f"是 {p.gold[0]}", p) == "current"
    assert classify_answer(f"是 {p.harmful[0]}", p) == "stale"
    assert classify_answer(f"{p.gold[0]} 或 {p.harmful[0]}", p) == "stale"


def test_anchors(streams):
    recs = []
    for sysm in (NoMemory(), Oracle(), Parsed(), Recency(), BM25()):
        recs += run(sysm, streams, [64])
    assert all(r["tokens"] <= 64 for r in recs)
    o = [r for r in recs if r["system"] == "oracle"]
    assert all(r["S"] == 1 and r["H"] == 0 for r in o)
    n = [r for r in recs if r["system"] == "none"]
    assert all(r["S"] == (0 if r["dimension"] != "F" else 1) for r in n)
    assert aggregate(recs, "parsed", 64, n_boot=50)["ntu"] > 0.99


def test_non_passive_replay_equivalent(streams):
    class NP(Parsed):
        from tide.protocol import Capabilities
        caps = Capabilities(passive=False)
    s = [x for x in streams if x.dimension == "P"][:1]
    a = [(r["probe"], r["u"]) for r in run(Parsed(), s, [64])]
    b = [(r["probe"], r["u"]) for r in run(NP(), s, [64])]
    assert a == b


def test_meta_passes(streams):
    assert run_meta(streams, budget=64)["pass"]
