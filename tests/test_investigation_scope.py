"""调查工具共用的因果/预算契约；使用真实服务、SQLite/HTTP 与确定性并发屏障。"""
from concurrent.futures import ThreadPoolExecutor
import pickle
import threading
from urllib.parse import quote

import numpy as np
import pytest

from hybrid_memory.agent.investigator import Budget, Investigation
from hybrid_memory.agent.loop import AgentWorker
from hybrid_memory.core.types import Memory, Tension
from hybrid_memory.server import SignalClosed
from test_server import _http, _service


def _seed(svc):
    svc.log.add_unit(0, 0, user_text="handler.ts old " * 10, assistant_text="old")
    svc.log.add_unit(1, 8, user_text="handler.ts future " * 10, assistant_text="future")
    for mid, text, birth, seen, src in (
        (0, "部署在 B 服务器", 0, 0, (0,)),
        (1, "FUTURE birth", 8, 8, (1,)),
        (2, "FUTURE revised", 0, 8, (0,)),
        (3, "FUTURE source", 0, 0, (1,)),
        (4, "过去的另一个版本", 0, 0, (0,)),
    ):
        svc.engine.mems[mid] = Memory(
            mid, mid, text, text, np.array([0.99, 0.14], dtype=np.float32),
            birth=birth, last_seen=seen, src=frozenset(src))
    svc.engine._next_id = 5
    svc.engine.tensions = {(0, 1): Tension(0, 1, 0, 0),
                           (0, 4): Tension(0, 4, 0, 0)}
    svc._t = 9


def _open(svc, calls=20, chars=10):
    return svc.open_budget("s", tool_calls=calls, window_chars=chars,
                           before=1, origin="repair")


@pytest.mark.parametrize("state,expected", [("unknown", 403), ("closed", 403),
                                           ("exhausted", 429)])
def test_all_investigation_http_tools_share_admission(state, expected):
    svc = _service(texts=())
    _seed(svc)
    if state != "unknown":
        _open(svc, calls=0)
    if state == "closed":
        svc.close_budget("s")
    try:
        with _http(svc) as (post, get, _):
            headers = {"X-Signal-Id": "s"}
            before = pickle.dumps(svc.engine.mems)
            requests = [
                ("/search", {"query": "部署在哪"}),
                ("/resolve", {"left": 0, "right": 4, "verdict": "update"}),
                ("/propose", {"proposals": [{"text": "past fact", "source_unit_ids": [0]}]}),
                ("/diagnose", {"miss_type": "no_miss"}),
                ("/log/search", {"query": "handler.ts"}),
                ("/log/timeline", {"entity": "handler.ts"}),
                ("/log/stats", {"group_by": "scene"}),
                ("/log/window", {"unit_ids": [0]}),
            ]
            for path, body in requests:
                assert post(path, body, headers)[0] == expected, path
            for path in ("/recall?q=test", "/conflicts"):
                assert get(path, headers)[0] == expected, path
            assert pickle.dumps(svc.engine.mems) == before
            assert not svc._retrievals and not svc.miss_counts
    finally:
        svc.log.close()


def test_search_filters_before_top_k_and_never_leaks_contested_future():
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    svc.cfg.k = 10
    before = pickle.dumps((svc.engine.mems, svc.engine.tensions))
    out = svc.recall("部署在哪", signal_id="s")
    assert {m["id"] for m in out["selected"]} == {0, 4}
    assert "FUTURE" not in out["context"]
    assert out["retrieval_id"] is None  # 调查检索不进主 agent 的反馈登记
    assert pickle.dumps((svc.engine.mems, svc.engine.tensions)) == before
    assert not svc._retrievals and len(svc.engine.signals) == 0
    svc.cfg.k = 1
    svc.engine.mems[0].emb = np.array([0.8, 0.6], dtype=np.float32)
    svc.engine.mems[4].emb = np.array([0.8, 0.6], dtype=np.float32)
    assert svc.recall("部署在哪", signal_id="s")["n"] == 1
    assert svc.close_budget("s")["calls"] == 2


@pytest.mark.parametrize("target", [1, 2, 3, 999])
def test_conflicts_resolve_and_supersedes_obey_same_bound(target):
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    try:
        with _http(svc) as (post, get, _):
            h = {"X-Signal-Id": "s"}
            status, out = get("/conflicts", h)
            assert status == 200 and len(out["conflicts"]) == 1
            assert out["conflicts"][0]["right"] == 4
            before = pickle.dumps((svc.engine.mems, svc.engine.tensions))
            assert post("/resolve", {"left": 0, "right": target, "verdict": "update",
                                     "ensure_tension": True, "entity_key": "injected"}, h)[0] == 403
            assert pickle.dumps((svc.engine.mems, svc.engine.tensions)) == before
            status, out = post("/propose", {"proposals": [
                {"text": "handler.ts cannot replace a future memory", "source_unit_ids": [0],
                 "supersedes": [target]}]}, h)
            assert status == 200 and out["accepted"] == 0
            assert "future" in out["rejected"][0]["reason"]
            assert pickle.dumps((svc.engine.mems, svc.engine.tensions)) == before
            assert post("/resolve", {"left": 0, "right": 4, "verdict": "collision"}, h)[0] == 200
            assert svc.close_budget("s")["calls"] == 4
    finally:
        svc.log.close()


def test_stats_keeps_one_bound_even_if_closed_mid_read(monkeypatch):
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    original = svc.log.stats

    def close_then_read(*args, **kwargs):
        svc.close_budget("s")
        return original(*args, **kwargs)

    monkeypatch.setattr(svc.log, "stats", close_then_read)
    out = svc.log_stats(signal_id="s")
    assert out["units_total"] == 1
    assert sum(row["units"] for row in out["rows"]) == 1
    with pytest.raises(SignalClosed):
        svc.log_search("handler.ts", signal_id="s")


def test_window_reserves_before_unlocked_io(monkeypatch):
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    entered, release = threading.Event(), threading.Event()
    original = svc.log.window

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(svc.log, "window", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(svc.log_window, [0], signal_id="s")
        assert entered.wait(5)
        second = pool.submit(svc.log_window, [0], signal_id="s")
        try:
            with pytest.raises(PermissionError):
                second.result(timeout=2)
        finally:
            release.set()
        assert first.result(timeout=5)["chars"] == 10
    assert svc.close_budget("s")["window_used"] == 10


def test_window_refunds_unused_reservation_and_failure(monkeypatch):
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    assert svc.log_window([1], signal_id="s")["budget_left"] == 10
    original = svc.log.window

    def boom(*args, **kwargs):
        raise RuntimeError("read failed")

    monkeypatch.setattr(svc.log, "window", boom)
    with pytest.raises(RuntimeError):
        svc.log_window([0], signal_id="s")
    monkeypatch.setattr(svc.log, "window", original)
    assert svc.log_window([0], max_chars=4, signal_id="s")["budget_left"] == 6
    assert svc.log_window([0], signal_id="s")["chars"] == 6


def test_worker_final_json_after_budget_exhaustion_keeps_causality_and_origin():
    svc = _service(texts=())
    _seed(svc)
    svc._t = 0
    svc.report_miss("部署在哪")

    def investigate(payload):
        sid = payload["signal_id"]
        with pytest.raises(PermissionError):
            svc.log_search("handler.ts", signal_id=sid)
        return Investigation(proposals=[
            {"text": "从历史证据修复 handler.ts", "source_unit_ids": [0]},
            {"text": "不该接受的 future 证据", "source_unit_ids": [1]}],
            verdicts=[(0, 1, "update")], diagnosis={"miss_type": "too_coarse"})

    agent = AgentWorker(svc, investigate, budget=Budget(tool_calls=0))
    stats = agent.process_once()
    assert stats["accepted"] == 1 and stats["diagnosed"] == 1
    assert stats["verdicts"] == 0
    assert svc.engine.mems[1].superseded_by is None
    assert svc.engine.mems[5].origin == "repair"
    assert svc.signals()["open_budgets"] == []


def test_worker_retry_uses_fresh_signal_handle():
    svc = _service(texts=())
    svc.report_miss("retry")
    handles, checked = [], []

    def investigate(payload):
        handles.append(payload["signal_id"])
        if len(handles) > 1:
            with pytest.raises(SignalClosed):
                svc.log_stats(signal_id=handles[0])
            checked.append(True)
        else:
            # 模拟重启/编号重用：下一次排队的 signal id 与旧轮相同。
            svc.engine.signals._next_id = 0
        return None

    agent = AgentWorker(svc, investigate)
    agent.process_once()
    agent.process_once()
    assert len(handles) == 2 and handles[0] != handles[1]
    assert checked == [True]


@pytest.mark.parametrize("pointer", ["superseded_by", "aggregated_into"])
def test_resolve_cannot_follow_an_old_id_to_future_representative(pointer):
    svc = _service(texts=())
    _seed(svc)
    setattr(svc.engine.mems[0], pointer, 1)
    _open(svc)
    try:
        with _http(svc) as (post, get, _):
            before = pickle.dumps(svc.engine.mems)
            status, _ = post("/resolve", {"left": 0, "right": 4, "verdict": "update",
                                          "ensure_tension": True}, {"X-Signal-Id": "s"})
            assert status == 403
            assert pickle.dumps(svc.engine.mems) == before
    finally:
        svc.log.close()


def test_blank_signal_header_is_not_a_main_agent_request():
    svc = _service(texts=())
    try:
        with _http(svc) as (post, get, _):
            assert post("/search", {"query": "test"}, {"X-Signal-Id": " "})[0] == 403
    finally:
        svc.log.close()


def test_inflight_window_retains_bound_and_never_charges_reopened_budget(monkeypatch):
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    entered, release = threading.Event(), threading.Event()
    original = svc.log.window

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(svc.log, "window", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(svc.log_window, [1, 0], signal_id="s")
        try:
            assert entered.wait(5)
            usage = svc.close_budget("s")
            assert usage["window_reserved"] == 10
            # open_budget 是进程内 API；即使管理员显式复用名字，也不能串账。
            svc.open_budget("s", tool_calls=20, window_chars=20, before=20)
        finally:
            release.set()
        out = pending.result(timeout=5)
    assert [u["unit_id"] for u in out["units"]] == [0]
    assert out["chars"] == 10 and out["budget_left"] == 0
    fresh = svc.close_budget("s")
    assert fresh["window_used"] == fresh["window_reserved"] == fresh["calls"] == 0


def test_concurrent_calls_share_one_call_allowance():
    svc = _service(texts=())
    _seed(svc)
    _open(svc, calls=1)
    barrier = threading.Barrier(4)

    def request(_):
        barrier.wait(timeout=5)
        try:
            svc.log_search("handler.ts", signal_id="s")
            return True
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(request, range(4))) == 1
    assert svc.close_budget("s")["calls"] == 4


def test_signal_requests_cannot_use_main_only_endpoints_or_forge_context():
    svc = _service(texts=())
    _open(svc)
    try:
        with _http(svc) as (post, get, _):
            h = {"X-Signal-Id": "s"}
            for path, body in (("/observe", {"user_text": "x"}),
                               ("/feedback", {"retrieval_id": 0}),
                               ("/miss", {"query": "x"}), ("/save", {})):
                assert post(path, body, h)[0] == 403
            assert get("/signals", h)[0] == 403
            assert get("/health", h)[0] == 200  # 插件启动探针保持兼容
            assert svc.close_budget("s")["calls"] == 0
            assert post("/propose", {"proposals": [], "_context": {
                "before": 999, "origin": "user_confirmed"}}, h)[0] == 403
            assert svc.log.count() == 0 and svc.n_missed == 0
    finally:
        svc.log.close()


def test_all_tools_draw_from_the_same_call_budget():
    svc = _service(texts=())
    _seed(svc)
    _open(svc, calls=6)
    try:
        with _http(svc) as (post, get, _):
            h = {"X-Signal-Id": "s"}
            assert post("/search", {"query": "部署在哪"}, h)[0] == 200
            assert get("/conflicts", h)[0] == 200
            assert post("/log/stats", {}, h)[0] == 200
            assert post("/resolve", {"left": 0, "right": 4, "verdict": "pending"}, h)[0] == 200
            assert post("/propose", {"proposals": []}, h)[0] == 200
            assert post("/diagnose", {"miss_type": "no_miss"}, h)[0] == 200
            assert post("/log/search", {"query": "handler.ts"}, h)[0] == 429
            assert svc.close_budget("s")["calls"] == 7
    finally:
        svc.log.close()


@pytest.mark.parametrize("before,expected", [(100, 1), (0, 0)])
def test_request_bound_can_only_tighten_context(before, expected):
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    assert svc.log_stats(before=before, signal_id="s")["units_total"] == expected
    assert svc.log_search("handler.ts", before=before, signal_id="s")["n"] == expected
    assert svc.log_timeline("handler.ts", before=before, signal_id="s")["n"] == expected


def test_denied_search_never_calls_embedding(monkeypatch):
    svc = _service(texts=())
    _open(svc, calls=0)
    calls = []
    monkeypatch.setattr(svc.emb, "embed", lambda *a, **kw: calls.append(True))
    with pytest.raises(PermissionError):
        svc.recall("test", signal_id="s")
    with pytest.raises(SignalClosed):
        svc.recall("test", signal_id="missing")
    assert calls == []


def test_context_is_immutable_and_active_budget_cannot_be_reset():
    from dataclasses import FrozenInstanceError

    svc = _service(texts=())
    context = _open(svc)
    with pytest.raises(FrozenInstanceError):
        context.before = 100
    with pytest.raises(ValueError, match="already open"):
        _open(svc, calls=999)
    assert svc.log_stats(signal_id="s")["units_total"] == 0
    assert svc.close_budget("s")["calls"] == 1


def test_investigator_search_does_not_revive_or_credit_even_with_eager_config():
    from hybrid_memory.core.types import Pool

    svc = _service(texts=())
    _seed(svc)
    svc.engine.mems[0].pool = Pool.ARCHIVE
    svc.cfg.archive_retrieval = True
    svc.cfg.defer_credit = False
    svc.cfg.shadow_credit = True
    svc.cfg.confidence_on = True
    svc.cfg.theta_conf = 0.0
    svc.cfg.theta = -1.0
    svc.cfg.k = 10
    _open(svc)
    before = pickle.dumps((svc.engine.mems, svc.engine.tensions))
    out = svc.recall("部署在哪", signal_id="s")
    assert 0 in {m["id"] for m in out["selected"]}
    assert pickle.dumps((svc.engine.mems, svc.engine.tensions)) == before
    assert svc.engine.n_revive == 0 and not svc.engine._shadow_pending
    assert not svc._retrievals and not len(svc.engine.signals)
    assert svc.cfg.defer_credit is False and svc.cfg.shadow_credit is True


def test_active_http_search_and_recall_are_bounded_but_main_search_is_unchanged():
    svc = _service(texts=())
    _seed(svc)
    svc.cfg.k = 10
    _open(svc)
    try:
        with _http(svc) as (post, get, _):
            h = {"X-Signal-Id": "s"}
            for status, out in (post("/search", {"query": "部署在哪"}, h),
                                get("/recall?q=" + quote("部署在哪"), h)):
                assert status == 200 and "FUTURE" not in out["context"]
                assert {m["id"] for m in out["selected"]} == {0, 4}
                assert out["retrieval_id"] is None
            status, out = post("/search", {"query": "部署在哪"})
            assert status == 200 and "FUTURE" in out["context"]
            assert isinstance(out["retrieval_id"], int)
            assert svc.close_budget("s")["calls"] == 2
    finally:
        svc.log.close()


def test_invalid_budget_or_window_size_cannot_manufacture_allowance():
    svc = _service(texts=())
    for kwargs in ({"tool_calls": -1}, {"window_chars": -1}, {"before": None},
                   {"before": True}):
        args = dict(tool_calls=2, window_chars=10, before=1)
        args.update(kwargs)
        with pytest.raises(ValueError):
            svc.open_budget("s", **args)
    assert svc.signals()["open_budgets"] == []
    _open(svc)
    for cap in (-1, 0, True):
        with pytest.raises(ValueError):
            svc.log_window([0], max_chars=cap, signal_id="s")
    usage = svc.close_budget("s")
    assert usage["window_used"] == usage["window_reserved"] == usage["calls"] == 0


@pytest.mark.parametrize("name,args", [("memory_search", {"query": "部署在哪"}),
                                       ("memory_conflicts", {})])
def test_inline_memory_tools_use_causal_readonly_admission(name, args):
    from hybrid_memory.agent.inline import InlineInvestigator
    svc = _service(texts=())
    _seed(svc)
    _open(svc)
    before = pickle.dumps(svc._state())
    inv = InlineInvestigator(svc, chat_fn=lambda *_: {})
    output = inv._tool(name, args, "s")
    assert "FUTURE" not in output and "过去" in output
    assert pickle.dumps(svc._state()) == before
    assert svc.close_budget("s")["calls"] == 1
    with pytest.raises(SignalClosed):
        inv._tool(name, args, "s")
    for invalid in ([1.5], True, [0] * 21, [2**100]):
        with pytest.raises(ValueError):
            inv._tool("log_window", {"unit_ids": invalid}, "s")
    with pytest.raises(ValueError):
        inv._tool("log_search", {"query": "x", "k": 1.5}, "s")
