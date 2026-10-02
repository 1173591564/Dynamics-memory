"""Three-agent protocol, using a fake OpenCode boundary (not a live OpenCode test)."""
import json

import pytest

from hybrid_memory.agent.trio import TrioWorker, OpenCodeRunner
from test_ouroboros import _svc


def drain(worker, n=6):
    for _ in range(n):
        if not worker.process_once():
            break


def test_hauler_selector_create_exist_and_overlapping_window(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    calls = []

    def fake(name, payload):
        calls.append((name, payload))
        if name == "hauler":
            assert payload["window"][-1]["unit_id"] == payload["unit_id"]
            return {"candidates": [{"text": "项目统一使用 bun 工具", "source_unit_ids": [payload["unit_id"]]}]}
        assert name == "selector"
        assert payload["candidates"][0]["source_unit_ids"] == [payload["unit_id"]]
        if payload["memories"]:
            return {"decisions": [{"candidate_index": 0, "action": "EXIST", "target_id": 0}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}

    worker = TrioWorker(svc, fake)
    try:
        svc.observe("以后统一用 bun", "好的")
        assert len(svc.engine.mems) == 0  # no implicit single-turn candgen write
        drain(worker)
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].src == {0}
        svc.observe("以后还是统一用 bun", "明白")
        drain(worker)
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].src == {0, 1}
        assert svc.engine.mems[0].evid == 2
        assert calls[-2][1]["window"][-2]["unit_id"] == 0
        assert calls[-1][0] == "selector"
        # A duplicate source delivered again by a window cannot inflate evidence.
        svc.observe("再看一下上轮", "好的")
        assert worker.process_once() == 1
        pending = svc.tasks.list_tasks(states=("pending",), kinds={"selector_due"})
        # Input remains explicitly grounded to its source rather than window identity.
        assert pending[-1]["payload"]["candidates"][0]["source_unit_ids"] == [2]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_reviewer_writes_rules_for_later_agent_inputs(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    seen = []

    def fake(name, payload):
        seen.append((name, payload))
        if name == "reviewer":
            return {"diagnosis": "hauler overlooked an explicit decision",
                    "rules": [{"target": "hauler", "instruction": "Pay attention to explicit user decisions."}],
                    "repair_candidates": []}
        if name == "hauler":
            return {"candidates": []}
        raise AssertionError(name)

    worker = TrioWorker(svc, fake)
    try:
        svc.observe("这个事情我之前明明讲过", "抱歉")
        drain(worker)
        assert svc.tasks.rules_for("hauler") == ["Pay attention to explicit user decisions."]
        svc.observe("再看一遍", "好的")
        drain(worker)
        assert any(name == "hauler" and p["unit_id"] == 1
                   and [r["instruction"] for r in p["rules"]] == ["Pay attention to explicit user decisions."] for name, p in seen)
    finally:
        svc.tasks.close()
        svc.log.close()


def test_opencode_runner_parses_json_stream_and_rejects_missing_cli(tmp_path, monkeypatch):
    runner = OpenCodeRunner(tmp_path, executable="definitely-not-installed-opencode")
    with pytest.raises(RuntimeError, match="not installed"):
        runner("hauler", {})
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps({"type": "text", "part": {"text": '{"candidates":[]}'}}) + "\n"
    monkeypatch.setattr("hybrid_memory.agent.trio.shutil.which", lambda x: x)
    def run(cmd, **kwargs):
        assert cmd[0:5] == ["definitely-not-installed-opencode", "run", "--pure", "--agent", "hauler"]
        assert kwargs["env"]["DYNAMICS_MEMORY_INTERNAL_AGENT"] == "1"
        return Result()
    monkeypatch.setattr("hybrid_memory.agent.trio.subprocess.run", run)
    assert runner("hauler", {}) == {"candidates": []}


def test_stored_agent_result_survives_restart_without_rerunning_model(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    calls = []

    def fake(name, p):
        calls.append(name)
        if name == "hauler":
            return {"candidates": [{"text": "项目统一使用 bun 工具",
                                    "source_unit_ids": [p["unit_id"]]}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}

    svc.observe("项目统一使用 bun 工具", "好的")
    row = svc.tasks.list_tasks(states=("pending",), kinds={"hauler_due"})[0]
    owned = svc.tasks.claim(row["id"], expected_version=row["version"])
    svc.tasks.store_result(row["id"], owned["token"], fake("hauler", {"unit_id": 0}))
    svc.tasks.close()
    svc.log.close()
    fresh = _svc(tmp_path)
    fresh.trio_mode = True
    try:
        drain(TrioWorker(fresh, fake))
        assert calls == ["hauler", "selector"]  # stored Hauler output was replayed
        assert fresh.engine.mems[0].text == "项目统一使用 bun 工具"
        assert len(fresh.tasks.list_tasks(states=("done",), kinds={"hauler_due", "selector_due"})) == 2
        drain(TrioWorker(fresh, fake))
        assert len(fresh.engine.mems) == 1
    finally:
        fresh.tasks.close()
        fresh.log.close()


def test_bad_reviewer_source_does_not_install_rule_or_handoff(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    svc.observe("这个事情我之前明明讲过", "抱歉")
    def fake(name, p):
        if name == "hauler":
            return {"candidates": []}
        return {"rules": [{"target": "selector", "instruction": "unsafe instruction"}],
                "repair_candidates": [{"text": "fake", "source_unit_ids": [999]}]}
    try:
        TrioWorker(svc, fake).process_once()
        assert svc.tasks.rules_for("selector") == []
        assert not svc.tasks.list_tasks(states=("pending",), kinds={"selector_due"})
        assert any(x["kind"] == "reviewer_due" and x["state"] == "pending"
                   for x in svc.tasks.list_tasks(kinds={"reviewer_due"}))
    finally:
        svc.tasks.close()
        svc.log.close()


def test_exact_duplicate_create_cannot_inflate_overlapping_source(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def fake(name, p):
        if name == "hauler":
            return {"candidates": [{"text": "项目统一使用 bun 工具", "source_unit_ids": [0]}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
    try:
        svc.observe("项目统一使用 bun 工具", "好的")
        drain(TrioWorker(svc, fake))
        before = svc.engine.mems[0].evid
        svc.observe("还是上面的决定", "好的")
        drain(TrioWorker(svc, fake))
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].evid == before
    finally:
        svc.tasks.close()
        svc.log.close()


def test_reviewer_sees_committed_handoffs_and_captured_prior_retrieval(tmp_path):
    from hybrid_memory import triggers
    assert triggers.is_dissatisfaction("这个端口我之前明明讲过")
    assert triggers.is_dissatisfaction("我对长期记忆很不满意")
    assert not triggers.is_correction("这个端口我之前明明讲过")  # cannot authorize UPDATE
    svc = _svc(tmp_path)
    svc.trio_mode = True
    seen = []

    def fake(name, p):
        if name == "hauler":
            return {"candidates": ([{"text": "端口现在是 8080", "source_unit_ids": [0]}]
                                    if p["unit_id"] == 0 else [])}
        if name == "selector":
            return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
        seen.append(p)
        return {"diagnosis": "not enough evidence to blame extraction",
                "rules": [], "repair_candidates": []}

    try:
        svc.observe("端口现在是 8080", "收到")
        drain(TrioWorker(svc, fake))
        ret = svc.recall("端口现在是 8080")
        svc.feedback(ret["retrieval_id"], "端口现在是 8080", "8080")
        svc.observe("这个端口我之前明明讲过", "抱歉")
        drain(TrioWorker(svc, fake))
        assert len(seen) == 1
        review = seen[0]
        assert review["previous_retrieval"]["previous_user"] == "端口现在是 8080"
        assert [m["id"] for m in review["previous_retrieval"]["retrieved"]] == [0]
        assert {x["kind"] for x in review["handoffs"]} == {"hauler_due", "selector_due"}
        selector = next(x for x in review["handoffs"] if x["kind"] == "selector_due")
        assert selector["agent_output"]["decisions"][0]["action"] == "CREATE"
        assert selector["committed_effect"]["outcomes"][0]["new_ids"] == [0]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_scoped_rule_usage_is_audited_and_human_can_disable_it(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    seen = []

    def fake(name, p):
        if name == "reviewer":
            return {"diagnosis": "a missed port rule", "rules": [{
                "target": "hauler", "scope": "entity:8080",
                "instruction": "Check explicit port decisions."}], "repair_candidates": []}
        seen.append(p)
        return {"candidates": []}

    try:
        svc.observe("我之前明明讲过端口 8080", "抱歉")
        drain(TrioWorker(svc, fake))
        rid = svc.tasks.rule_report()[0]["id"]
        assert svc.tasks.rule_report()[0]["uses"] == 0
        svc.observe("端口 8080", "好的")
        drain(TrioWorker(svc, fake))
        assert [r["id"] for r in seen[-1]["rules"]] == [rid]
        svc.observe("这是别的事情", "好的")
        drain(TrioWorker(svc, fake))
        assert seen[-1]["rules"] == []  # overlap does not broaden a rule's scope
        assert svc.tasks.rule_report()[0]["uses"] == 1
        assert svc.tasks.disable_rule(rid)
        assert not svc.tasks.disable_rule(rid)
        svc.observe("端口 8080", "好的")
        drain(TrioWorker(svc, fake))
        assert seen[-1]["rules"] == []
        assert svc.tasks.rule_report()[0]["enabled"] == 0
    finally:
        svc.tasks.close()
        svc.log.close()


def test_reviewer_does_not_confuse_late_hauler_completion_with_prior_decision(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    seen = []

    def fake(name, p):
        if name == "hauler":
            return {"candidates": []}
        assert name == "reviewer"
        seen.append(p)
        return {"diagnosis": "pending extraction at complaint", "rules": [], "repair_candidates": []}

    try:
        svc.observe("端口现在是 8080", "好")  # Hauler not run yet
        svc.observe("这个端口我之前明明讲过", "抱歉")
        drain(TrioWorker(svc, fake))
        first = next(x for x in seen[0]["handoffs"] if x["unit_id"] == 0)
        assert first["state"] == "pending_at_complaint"
        assert "agent_output" not in first
    finally:
        svc.tasks.close()
        svc.log.close()


def test_direct_agent_mutations_denied_in_trio_http_mode(tmp_path):
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from hybrid_memory.server import serve
    svc = _svc(tmp_path)
    svc.trio_mode = True
    httpd = serve(svc, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        for path in ("/propose", "/resolve", "/diagnose"):
            req = Request(f"http://127.0.0.1:{httpd.server_address[1]}{path}",
                          data=b"{}", method="POST", headers={
                              "Authorization": "Bearer " + svc.token,
                              "Content-Type": "application/json"})
            with pytest.raises(HTTPError) as exc:
                urlopen(req, timeout=4)
            assert exc.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)
        svc.tasks.close()
        svc.log.close()


def test_existing_agent_rules_table_is_migrated_without_disabling_rules(tmp_path):
    import sqlite3
    from hybrid_memory.store.tasks import TaskStore
    path = tmp_path / "tasks.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE agent_rules (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                 "source_task INTEGER NOT NULL, target TEXT NOT NULL,"
                 "instruction TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,"
                 "created_at REAL NOT NULL, UNIQUE(source_task,target,instruction))")
    conn.execute("INSERT INTO agent_rules(source_task,target,instruction,created_at) "
                 "VALUES(1,'hauler','Existing rule',1)")
    conn.commit()
    conn.close()
    store = TaskStore(path)
    try:
        assert store.rule_snapshot("hauler", "any context")[0]["scope"] == "project"
        assert store.disable_rule(1)
        assert not store.rule_snapshot("hauler", "any context")
    finally:
        store.close()


def test_reviewer_can_assess_used_rule_and_atomically_roll_it_back(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def fake(name, p):
        if name == "hauler":
            return {"candidates": []}
        assert name == "reviewer"
        if p["complaint"]["id"] == 0:
            return {"diagnosis": "missed a port decision", "rules": [{
                "target": "hauler", "scope": "entity:8080", "instruction": "Check port."}],
                "repair_candidates": []}
        used = [rid for task in p["handoffs"] for rid in task.get("rule_ids", [])]
        assert used
        return {"diagnosis": "rule did not fix the observed complaint",
                "rules": [], "repair_candidates": [], "rule_reviews": [{
                    "rule_id": used[0], "assessment": "ineffective",
                    "reason": "same omission after applying this rule"}]}
    try:
        svc.observe("我之前明明讲过端口8080", "好")
        drain(TrioWorker(svc, fake))
        rule = svc.tasks.rule_report()[0]
        svc.observe("端口8080", "收到")
        drain(TrioWorker(svc, fake))
        assert svc.tasks.rule_report()[0]["uses"] == 1
        svc.observe("这个端口我之前明明讲过", "抱歉")
        drain(TrioWorker(svc, fake))
        assert svc.tasks.rule_report()[0]["enabled"] == 0
        with svc.tasks._lock:
            assert svc.tasks._conn.execute(
                "SELECT assessment FROM agent_rule_feedback WHERE rule_id=?",
                (rule["id"],)).fetchone()[0] == "ineffective"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_reviewer_cannot_disable_rule_not_observed_in_handoff(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    svc.observe("我之前明明讲过端口8080", "抱歉")
    def fake(name, p):
        if name == "hauler":
            return {"candidates": []}
        return {"diagnosis": "guess", "rules": [], "repair_candidates": [],
                "rule_reviews": [{"rule_id": 123, "assessment": "ineffective",
                                  "reason": "not observed"}]}
    try:
        TrioWorker(svc, fake).process_once()
        assert not svc.tasks.rule_report()
        assert svc.tasks.list_tasks(kinds={"reviewer_due"})[0]["state"] == "pending"
    finally:
        svc.tasks.close()
        svc.log.close()


def test_archived_equivalent_is_reactivated_not_duplicated(tmp_path):
    from hybrid_memory.core.types import Pool
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def fake(name, p):
        if name == "hauler":
            return {"candidates": [{"text": "项目统一使用 bun 工具",
                                    "source_unit_ids": [p["unit_id"]]}]}
        if p["unit_id"] == 1:
            assert p["memories"][0]["pool"] == "A"
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
    try:
        svc.observe("项目统一使用 bun 工具", "好的")
        drain(TrioWorker(svc, fake))
        svc.engine.mems[0].pool = Pool.ARCHIVE
        svc.observe("项目统一使用 bun 工具", "好的")
        drain(TrioWorker(svc, fake))
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].pool is not Pool.ARCHIVE
        assert svc.engine.mems[0].src == {0, 1}
    finally:
        svc.tasks.close()
        svc.log.close()
