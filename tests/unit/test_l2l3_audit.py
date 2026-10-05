from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval.l2l3 import audit, export, gen_l2, run_audit_chain, sidecar
from test_ouroboros import _svc


def _run(tmp_path, name, action="CREATE", state="done", *, probes=()):
    path = tmp_path / name
    path.mkdir()
    (path / "run.json").write_text(json.dumps({
        "corpus_kind": "l2", "probe_records": list(probes),
        "drain": {"drained": True}}), encoding="utf-8")
    (path / "export.json").write_text(json.dumps({
        "units": [{"unit_id": 0, "user_text": name, "assistant_text": "ok"}],
        "mems": [{"id": 0, "text": "same claim", "src": [0], "kind": "fact",
                  "pool": "CANDIDATE", "v": 0.5}],
        "tasks": [{"id": 1, "kind": "selector_due", "state": state,
                   "payload_candidates": ["same claim"],
                   "result": {"decisions": [{"candidate_index": 0,
                                              "action": action}]}}]}), encoding="utf-8")
    return path


def _scores(tmp_path):
    key = tmp_path / "key.json"
    filled = tmp_path / "filled.jsonl"
    key.write_text(json.dumps({"one": {"chain": "l2", "run": "r", "mem_id": 0}}),
                   encoding="utf-8")
    row = {"audit_id": "one", "memory_text": "test", "has_reflection": False,
           "verdicts": {q: "pass" for q in audit.QUESTIONS if q != "reflection"}}
    filled.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return key, filled, row


def test_worksheet_keeps_decisions_with_their_run(tmp_path):
    first = _run(tmp_path, "a", "CREATE")
    second = _run(tmp_path, "b", "CONFLICT")
    worksheet, key = tmp_path / "worksheet", tmp_path / "key"
    audit.build_worksheet([str(first), str(second)], str(worksheet), str(key), n=2)
    mapping = json.loads(key.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in worksheet.read_text(encoding="utf-8").splitlines()]
    actual = {mapping[r["audit_id"]]["run"]: r["selector_decision"]["action"] for r in rows}
    assert actual == {"a": "CREATE", "b": "CONFLICT"}


def test_worksheet_does_not_attribute_dead_decisions(tmp_path):
    run = _run(tmp_path, "dead", state="dead")
    worksheet = tmp_path / "worksheet"
    audit.build_worksheet([str(run)], str(worksheet), str(tmp_path / "key"))
    assert json.loads(worksheet.read_text(encoding="utf-8"))["selector_decision"] is None


def test_worksheet_uses_committed_origin_not_later_reuse(tmp_path):
    run = _run(tmp_path, "origin")
    path = run / "export.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tasks"][0]["committed_effect"] = {"outcomes": [{"index": 0, "action": "CREATE", "new_ids": [0]}]}
    data["tasks"].append({"id": 2, "kind": "selector_due", "state": "done",
                          "payload_candidates": ["same claim"],
                          "result": {"decisions": [{"candidate_index": 0, "action": "EXIST", "target_id": 0}]},
                          "committed_effect": {"outcomes": [{"index": 0, "action": "EXIST", "target_id": 0}]}})
    path.write_text(json.dumps(data), encoding="utf-8")
    worksheet = tmp_path / "worksheet"
    audit.build_worksheet([str(run)], str(worksheet), str(tmp_path / "key"))
    decision = json.loads(worksheet.read_text(encoding="utf-8"))["selector_decision"]
    assert decision["task_id"] == 1
    assert decision["applied_action"] == "CREATE"


def test_aggregate_keeps_all_runs_and_first_pass_probes(tmp_path):
    first = _run(tmp_path, "R")
    second = _run(tmp_path, "F", probes=[{"stream": "F", "probe": "f", "dimension": "F", "S": 1, "H": 0, "u": 1}])
    (first / "run.json.first-pass").write_text(json.dumps({"probe_records": [
        {"stream": "R", "probe": "r", "dimension": "R", "S": 0, "H": 0, "u": 0}]}), encoding="utf-8")
    key, filled, _ = _scores(tmp_path)
    result = audit.aggregate(str(filled), str(key), [str(first), str(second)], str(tmp_path / "report"))
    assert result["auto"]["l2"]["probes"] == 2
    assert result["auto"]["l2"]["S"] == 0.5
    assert set(result["auto"]["l2"]["dimensions"]) == {"R", "F"}


@pytest.mark.parametrize("bad", ["empty", "missing", "duplicate", "unknown", "partial", "invalid"])
def test_aggregate_rejects_invalid_scores(tmp_path, bad):
    key, filled, row = _scores(tmp_path)
    rows = [row]
    if bad == "empty":
        rows = []
    elif bad == "missing":
        row["verdicts"] = {}
    elif bad == "duplicate":
        rows.append(row)
    elif bad == "unknown":
        row["audit_id"] = "unknown"
    elif bad == "partial":
        key.write_text(json.dumps({"one": {"chain": "l2"}, "two": {"chain": "l2"}}), encoding="utf-8")
    else:
        row["verdicts"]["grounded"] = "probably"
    filled.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        audit.aggregate(str(filled), str(key), [], str(tmp_path / "report"))


def test_export_preserves_candidate_indexes_and_errors():
    row = {"id": 1, "kind": "selector_due", "state": "dead", "attempts": 5,
           "apply_attempts": 0, "last_error": "lease expired",
           "payload": {"parent_task": 0, "candidates": [None, {"text": "second", "src": [0]}]},
           "result": None}
    out = export._task_row(row)
    assert out["payload_candidates"] == ["", "second"]
    assert out["last_error"] == "lease expired" and out["attempts"] == 5


def test_retraction_rewrite_does_not_require_withdrawn_value(monkeypatch):
    turn = SimpleNamespace(facts=["f"], op="retract", user="撤回日志级别", assistant="收到")
    fact = SimpleNamespace(value="old-1234", supersedes=None)
    llm = SimpleNamespace(chat_messages=lambda *a, **k: {"content": json.dumps({"user": "日志级别不再生效，请撤回", "assistant": "好的，撤回了"})})
    monkeypatch.setattr(gen_l2.time, "sleep", lambda _: None)
    out = gen_l2._rewrite_turn(llm, None, turn, {"f": fact})
    assert out["rewritten"] is True
    assert "old-1234" not in out["user"] + out["assistant"]


def test_retraction_rewrite_rejects_reintroduced_old_value(monkeypatch):
    turn = SimpleNamespace(facts=["f"], op="retract", user="撤回日志级别", assistant="收到")
    llm = SimpleNamespace(chat_messages=lambda *a, **k: {"content": json.dumps({"user": "撤回日志级别 old-1234", "assistant": "收到"})})
    monkeypatch.setattr(gen_l2.time, "sleep", lambda _: None)
    out = gen_l2._rewrite_turn(llm, None, turn, {"f": SimpleNamespace(value="old-1234", supersedes=None)})
    assert out["rewritten"] is False and out["user"] == turn.user


def test_empty_context_is_not_serialized_response():
    assert export._served_text({"context": "", "selected": [], "tokens": 0}) == ""


def test_run_chain_default_env_and_resume_preserve_probes(tmp_path, monkeypatch):
    class Stub:
        def __init__(self, *a, **kw): pass
        def start(self): return self
        def drain(self, **kw): return {"drained": True}
        def close(self): return ""
    monkeypatch.setattr(sidecar, "Sidecar", Stub)
    monkeypatch.setattr(export, "export_run", lambda *a: {"mems": [], "units": [], "tasks": []})
    project, out = tmp_path / "project", tmp_path / "out"
    run_audit_chain.run_chain({"kind": "l3", "turns": []}, str(project), str(out))
    memory = project / ".opencode" / "memory"
    memory.mkdir(parents=True)
    (memory / "tasks.sqlite").touch()
    previous = json.loads((out / "run.json").read_text(encoding="utf-8"))
    previous["probe_records"] = [{"probe": "before-restart"}]
    (out / "run.json").write_text(json.dumps(previous), encoding="utf-8")
    result = run_audit_chain.run_chain({"kind": "l3", "turns": []}, str(project), str(out), resume=True)
    assert result["probe_records"] == previous["probe_records"]


def test_export_is_offline_and_does_not_change_project(tmp_path, monkeypatch):
    project = tmp_path / "project"
    state_dir = project / ".opencode" / "memory"
    svc = _svc(state_dir)
    try:
        svc.observe("项目改用 bun 构建", "好的")
        svc.propose([{"text": "项目用 bun 构建", "src": [0]}])
    finally:
        svc.tasks.close()
        svc.log.close()
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in state_dir.iterdir() if p.is_file()}
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.setattr("hybrid_memory.transport.bootstrap.build_default_service", lambda *a, **k: pytest.fail("export must not bootstrap"))
    data = export.export_run(str(Path(__file__).resolve().parents[2]), str(project), str(tmp_path / "export.json"))
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in state_dir.iterdir() if p.is_file()}
    assert before == after
    assert len(data["units"]) == 1 and len(data["mems"]) == 1


def test_export_reads_committed_wal_without_touching_source(tmp_path):
    import sqlite3

    db = tmp_path / "tasks.sqlite"
    writer = sqlite3.connect(db)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE sample(value INTEGER)")
        writer.execute("INSERT INTO sample VALUES(7)")
        writer.commit()
        before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        with export._readonly_db(db) as conn:
            assert conn.execute("SELECT value FROM sample").fetchone()[0] == 7
        assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    finally:
        writer.close()


def test_probe_barrier_preserves_pre_ingest_gold_and_terminal_boundary(tmp_path, monkeypatch):
    events = []
    class Stub:
        def __init__(self, *a, **kw): pass
        def start(self): return self
        def observe(self, user, assistant, request_id):
            events.append(user)
            return 200, {"unit_id": len(events)}
        def drain(self, **kw):
            events.append("drain")
            return {"drained": True}
        def search(self, query, **kw):
            events.append(query)
            return 200, {"context": "old-1234" if query == "before-update" else "new-5678", "n": 1}
        def close(self): return ""
    monkeypatch.setattr(sidecar, "Sidecar", Stub)
    monkeypatch.setattr(export, "read_snapshot", lambda *a: {"revision": 1, "mems": [
        {"id": 0, "text": "old-1234", "visible": True},
        {"id": 1, "text": "new-5678", "visible": True}], "tasks": []}, raising=False)
    monkeypatch.setattr(export, "export_run", lambda *a: {"mems": [], "units": [], "tasks": []})
    corpus = {"kind": "l2", "streams": [{"id": "test-stream", "turns": [
        {"t": 0, "user": "set-old", "assistant": "ok"},
        {"t": 1, "user": "set-new", "assistant": "ok"}], "probes": [
        {"id": "p1", "t": 1, "dimension": "V", "knob": 0, "query": "before-update", "gold": ["old-1234"], "harmful": []},
        {"id": "p2", "t": 2, "dimension": "V", "knob": 1, "query": "after-update", "gold": ["new-5678"], "harmful": ["old-1234"]}]}]}
    result = run_audit_chain.run_chain(corpus, str(tmp_path / "proj"), str(tmp_path / "out"))
    assert events[:6] == ["set-old", "drain", "before-update", "set-new", "drain", "after-update"]
    assert len(result["probe_records"]) == 2
    assert all(p["eligible"] and p["S"] == 1 for p in result["probe_records"])
    assert result["probe_validity"] == "causal-barrier"


def test_probe_timeout_stops_future_feeding(tmp_path, monkeypatch):
    fed = []
    class Stub:
        def __init__(self, *a, **kw): pass
        def start(self): return self
        def observe(self, user, assistant, request_id):
            fed.append(user)
            return 200, {"unit_id": 0}
        def drain(self, **kw): return {"drained": False, "active": {"running": 1}}
        def search(self, *a, **kw): pytest.fail("unready probe must not search")
        def close(self): return ""
    monkeypatch.setattr(sidecar, "Sidecar", Stub)
    monkeypatch.setattr(export, "read_snapshot", lambda *a: {"revision": 1, "mems": [], "tasks": []}, raising=False)
    monkeypatch.setattr(export, "export_run", lambda *a: {"mems": [], "units": [], "tasks": []})
    corpus = {"kind": "l2", "streams": [{"id": "test-stream", "turns": [
        {"t": 0, "user": "current", "assistant": "ok"},
        {"t": 1, "user": "future", "assistant": "ok"}], "probes": [
        {"id": "p", "t": 1, "dimension": "R", "knob": 1, "query": "q", "gold": ["old-1234"], "harmful": []}]}]}
    result = run_audit_chain.run_chain(corpus, str(tmp_path / "proj"), str(tmp_path / "out"))
    assert fed == ["current"]
    assert result["status"] == "barrier_timeout"
    assert result["probe_records"][0]["pipeline_status"] == "not_ready"
    assert result["probe_records"][0]["eligible"] is False


@pytest.mark.parametrize("mems,tasks,seen,ctx,gold,harmful,pipeline,retrieval,eligible", [
    ([], [{"id": 1, "state": "dead", "unit_id": 0}], set(), "", ["a-1234"], [], "write_failed", "not_testable", False),
    ([], [], set(), "", ["a-1234"], [], "not_distilled", "not_testable", False),
    ([{"id": 0, "text": "a-1234", "visible": True}], [], set(), "", ["a-1234"], [], "ready", "miss", True),
    ([{"id": 0, "text": "a-1234", "visible": True}], [], set(), "a-1234", ["a-1234"], [], "ready", "hit", True),
    ([], [], set(), "", [], ["a-1234"], "unexercised_retraction", "not_testable", False),
    ([], [], {"a-1234"}, "", [], ["a-1234"], "ready", "clean", True),
    ([{"id": 0, "text": "a-1234", "visible": True}], [], {"a-1234"}, "a-1234", [], ["a-1234"], "ready", "harmful", True),
])
def test_probe_diagnostics(mems, tasks, seen, ctx, gold, harmful, pipeline, retrieval, eligible):
    probe = {"id": "p", "t": 1, "dimension": "F", "knob": 0, "gold": gold, "harmful": harmful}
    rec = run_audit_chain._probe_record("st", probe, {"drained": True},
        {"revision": 1, "mems": mems, "tasks": tasks}, seen, {0}, 200, {"context": ctx})
    assert rec["pipeline_status"] == pipeline
    assert rec["retrieval_status"] == retrieval
    assert rec["eligible"] is eligible
    failed = any(t["state"] == "dead" and t.get("unit_id") in {0} for t in tasks)
    assert rec["end_to_end_pass"] is (pipeline == "ready" and retrieval in ("hit", "clean") and not failed)


def test_probe_needs_human_and_uncertain_end_to_end(tmp_path):
    probe = {"id": "p", "t": 1, "dimension": "C", "knob": 0, "gold": ["flag-8000", "flag-8100"],
             "harmful": [], "expect_uncertain": True}
    snapshot = {"revision": 2, "mems": [{"id": 0, "text": "开关是 flag-8000", "visible": True}],
                "tasks": [], "reviews": [{"id": 1, "target_id": 0}]}
    ctx = "- [待人审冲突] 开关是 flag-8000\n- [待人审提案，非当前事实] 开关是 flag-8100"
    rec = run_audit_chain._probe_record("st", probe, {"drained": True}, snapshot, set(), {0}, 200,
                                        {"context": ctx})
    assert rec["pipeline_status"] == "needs_human"
    assert rec["eligible"] is False
    assert rec["end_to_end_pass"] is True
    missing = run_audit_chain._probe_record("st", probe, {"drained": True}, snapshot, set(), {0}, 200,
                                            {"context": "- [待人审冲突] 开关是 flag-8000"})
    assert missing["end_to_end_pass"] is False


def test_convergence_summary_reports_identity_and_future_sources():
    export = {"mems": [
        {"id": 0, "claim_key": ["网关", "端口"], "claim_value": "gate-1", "pending_review": False,
         "superseded_by": None, "aggregated_into": None, "withdrawn_at": None},
        {"id": 1, "claim_key": ["网关", "端口"], "claim_value": "gate-1", "pending_review": False,
         "superseded_by": None, "aggregated_into": None, "withdrawn_at": None},
        {"id": 2, "claim_key": [], "claim_value": "", "pending_review": False,
         "superseded_by": None, "aggregated_into": None, "withdrawn_at": None}],
        "tasks": [{"state": "done", "committed_effect": {"outcomes": [{"action": "UPDATE"}]}},
                  {"state": "dead", "id": 9, "committed_effect": None}],
        "units": [{"unit_id": 0, "t": 0}], "tensions": [], "human_reviews": [],
        "pool_sizes": {"C": 2, "M": 0, "A": 1}}
    probes = [{"probe": "p0", "http": 200, "end_to_end_pass": True, "pipeline_status": "ready",
               "retrieval_status": "hit", "response": {"selected": [{"src": [0]}]}}]
    summary = run_audit_chain.convergence_summary(export, probes, 1)
    assert summary["duplicate_current_claims"] == 1
    assert summary["unknown_identity_current"] == 1
    assert summary["committed_actions"] == {"UPDATE": 1}
    assert summary["dead_tasks"] == [9]
    assert summary["future_sources"] == [] and summary["end_to_end_rate"] == 1.0
    later = [{"probe": "p0", "t": 0, "http": 200, "end_to_end_pass": True,
              "pipeline_status": "ready", "retrieval_status": "hit",
              "response": {"selected": [{"src": [0]}]}}]
    assert run_audit_chain.convergence_summary(export, later, 1)["future_sources"] == [
        {"probe": "p0", "source": 0}]


def test_convergence_summary_counts_inflight_duplicates_and_stale_versions():
    export = {"mems": [], "tasks": [], "units": [], "tensions": [], "human_reviews": []}
    probes = [
        {"probe": "p0", "http": 200, "gold": ["gate-1"], "harmful": [], "memory_matches": {"gate-1": [4, 7]}},
        {"probe": "p1", "http": 200, "gold": ["gate-2"], "harmful": ["gate-1"],
         "memory_matches": {"gate-2": [8], "gate-1": [4]}},
        {"probe": "p2", "http": 200, "gold": [], "harmful": ["gate-1", "gate-2"],
         "memory_matches": {"gate-1": [], "gate-2": []}},
        {"probe": "legacy", "http": 200, "gold": ["x"], "harmful": []}]
    summary = run_audit_chain.convergence_summary(export, probes, 4)
    assert summary["inflight_duplicates"] == 1
    assert summary["inflight_stale_retrievable"] == 1
    assert summary["inflight_unmeasured"] == 1


def test_kernel_corpus_live_slot_is_append_only_and_ends_unretracted():
    base = gen_l2.kernel_convergence(3)["streams"][0]
    live = gen_l2.kernel_convergence(3, live=True)["streams"][0]
    assert len(base["turns"]) == len(base["probes"]) == 21
    assert live["turns"][:21] == base["turns"] and live["probes"][:21] == base["probes"]
    extra_turns, extra_probes = live["turns"][21:], live["probes"][21:]
    assert len(extra_turns) == len(extra_probes) == 4
    assert [p["id"] for p in live["probes"]] == [f"kernel-s3-p{i}" for i in range(25)]
    assert all(p["t"] == i + 22 for i, p in enumerate(extra_probes))
    assert not any("作废" in t["user"] for t in extra_turns)
    final = extra_probes[-1]
    assert final["gold"] and not final["expect_uncertain"] and final["harmful"] == extra_probes[-2]["harmful"]
    assert not set(final["gold"]) & set(final["harmful"])


def test_drain_waits_for_pending_l0_and_treats_skipped_as_terminal(monkeypatch):
    sc = sidecar.Sidecar("repo", "project")
    monkeypatch.setattr(sc, "signals", lambda: {"tasks": {"done": 1, "skipped": 1}, "units": {"pending": 1}})
    assert sc.active_tasks()["units_pending"] == 1
    assert sc.drain(timeout=0.01, quiet_s=0)["drained"] is False


def test_live_probe_snapshot_does_not_change_database(tmp_path):
    project = tmp_path / "project"
    svc = _svc(project / ".opencode" / "memory")
    try:
        svc.observe("项目改用 bun 构建", "好的")
        svc.propose([{"text": "项目用 bun 构建", "src": [0]}])
        before = svc.tasks.checkpoint()
        snapshot = export.read_snapshot(str(project))
        assert snapshot["mems"][0]["visible"]
        assert svc.tasks.checkpoint() == before
    finally:
        svc.tasks.close()
        svc.log.close()


def test_retrieval_smoke_has_positive_precondition_and_non_configuration_probes():
    corpus = gen_l2.retrieval_smoke()
    st = corpus["streams"][0]
    assert {p["scenario"] for p in st["probes"]} >= {"mechanism", "preference", "scope", "retraction"}
    retract = next(p for p in st["probes"] if p["dimension"] == "F")
    assert any(p["t"] < retract["t"] and p["gold"] == retract["harmful"] for p in st["probes"])


def test_passive_probe_does_not_append_log_or_mutate_memory_checkpoint(tmp_path):
    svc = _svc(tmp_path / ".opencode" / "memory")
    try:
        svc.observe("网关模块的端口定为 gate-4100。", "收到。")
        svc.propose([{"text": "网关模块的端口定为 gate-4100。", "src": [0]}])
        before_state = svc._dump_state()
        before_checkpoint = svc.tasks.checkpoint()
        before_tasks = svc.tasks.stats()
        before_time = svc._t
        result = svc.recall("网关模块的端口定为 gate-4100。", passive=True)
        assert result["n"] > 0 and result["retrieval_id"] is None
        assert svc.log.count() == 1
        assert svc._t == before_time
        assert svc._dump_state() == before_state
        assert svc.tasks.checkpoint() == before_checkpoint
        assert svc.tasks.stats() == before_tasks
    finally:
        svc.tasks.close()
        svc.log.close()


def test_probe_summary_excludes_vacuous_scores_but_keeps_raw_evidence():
    records = [{"S": 1, "H": 0, "u": 1, "eligible": False},
               {"S": 0, "H": 0, "u": 0, "eligible": True}]
    summary = audit._probe_summary(records)
    assert summary["eligible_probes"] == 1
    assert summary["S"] == 0
    assert summary["raw"]["S"] == 0.5


def test_silent_sidecar_boot_timeout_is_bounded(tmp_path, monkeypatch):
    import subprocess
    import sys
    import threading

    popen = subprocess.Popen
    monkeypatch.setattr(sidecar.subprocess, "Popen", lambda argv, **kw: popen(
        [sys.executable, "-c", "import time; time.sleep(30)"] if "-m" in argv else argv, **kw))
    sc = sidecar.Sidecar(str(tmp_path), str(tmp_path / "project"), boot_timeout=0.05)
    errors = []

    def start():
        try:
            sc.start()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=start, daemon=True)
    try:
        thread.start()
        thread.join(5)
        bounded = not thread.is_alive()
    finally:
        sc.close()
        thread.join(5)
    assert bounded and errors and isinstance(errors[0], RuntimeError)
