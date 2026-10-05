"""Three-agent protocol, using a fake OpenCode boundary (not a live OpenCode test)."""
import json

import pytest

from hybrid_memory.agents.opencode import OpenCodeRunner
from hybrid_memory.dispatch.worker import DispatchWorker
from test_ouroboros import _svc


def drain(worker, n=6):
    for _ in range(n):
        if not worker.process_once():
            break


def _claim_agent(name, payload, action="CREATE"):
    if name == "reviewer":
        return {"diagnosis": "来源已交服务校验", "rules": [], "repair_candidates": [], "rule_reviews": []}
    if name == "hauler":
        unit = payload["window"][-1]
        return {"candidates": [{"text": unit["user_text"], "source_unit_ids": [unit["unit_id"]]}]}
    target = payload["memories"][0]["id"] if payload["memories"] else None
    return {"decisions": [{"candidate_index": i,
                          "action": action if target is not None else "CREATE",
                          **({"target_id": target, "verified_correction": True} if target is not None else {})}
                         for i in range(len(payload["candidates"]))]}


@pytest.mark.parametrize("action", ["CREATE", "CONFLICT", "UPDATE"])
def test_authorized_user_change_converges_independent_of_model_disposition(tmp_path, action):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    worker = DispatchWorker(svc, lambda name, p: _claim_agent(name, p, action))
    try:
        svc.observe("网关模块的端口定为 gate-4100。", "好的")
        drain(worker)
        svc.observe("网关模块的端口由 gate-4100 改为 gate-4200。", "好的")
        drain(worker)
        old = svc.engine.mems[0]
        assert old.superseded_by is not None
        current = svc.engine.mems[old.superseded_by]
        assert current.claim_key == ("网关模块", "端口")
        assert current.claim_value == "gate-4200"
        assert "gate-4100" not in current.text
        assert not svc.human_reviews()
        assert "gate-4100" not in svc.recall("网关模块的端口现在是多少？", passive=True)["context"]
    finally:
        svc.tasks.close()
        svc.log.close()


@pytest.mark.parametrize("user,assistant", [
    ("如果网关模块的端口改为 gate-4200，会怎样？", "可以考虑"),
    ("建议网关模块的端口改为 gate-4200。", "还没决定"),
    ("网关模块的端口不改为 gate-4200。", "好的"),
    ("不对，我引用文档：‘网关模块的端口是 gate-4200’。", "仅引用"),
    ("你觉得呢？", "网关模块的端口改为 gate-4200。")])
def test_model_proof_cannot_authorize_speculation_or_quoted_evidence(tmp_path, user, assistant):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "hauler" and payload["unit_id"] == 1:
            return {"candidates": [{"text": "网关模块的端口是 gate-4200。", "source_unit_ids": [1]}]}
        return _claim_agent(name, payload, "UPDATE")
    worker = DispatchWorker(svc, runner)
    try:
        svc.observe("网关模块的端口定为 gate-4100。", "好的")
        drain(worker)
        svc.observe(user, assistant)
        drain(worker)
        assert svc.engine.mems[0].superseded_by is None
        assert len(svc.engine.mems) == 1
        assert len(svc.human_reviews()) == 1
    finally:
        svc.tasks.close()
        svc.log.close()


def test_fresh_user_reinstatement_after_retraction_creates_new_version(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    worker = DispatchWorker(svc, _claim_agent)
    try:
        svc.observe("日志级别定为 trace-6100。", "好的")
        drain(worker)
        svc.observe("日志级别设定 trace-6100 作废，先别用它。", "好的")
        drain(worker)
        assert svc.engine.mems[0].withdrawn_at is not None
        svc.observe("日志级别定为 trace-6100。", "好的")
        drain(worker)
        current = [m for m in svc.engine.mems.values()
                   if m.withdrawn_at is None and m.superseded_by is None and m.claim_value == "trace-6100"]
        assert len(current) == 1 and current[0].id != 0
        assert svc.engine.mems[0].withdrawn_at is not None
        assert "trace-6100" in svc.recall("日志级别现在是什么？", passive=True)["context"]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_scope_filter_keeps_unscoped_memories_for_mixed_queries(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "selector":
            return {"decisions": [{"candidate_index": i, "action": "CREATE"}
                                  for i in range(len(payload["candidates"]))]}
        return _claim_agent(name, payload)
    worker = DispatchWorker(svc, runner)
    try:
        for text in ("网关模块的端口定为 gate-4100。", "部署模块的端口定为 deploy-5100。",
                     "写 PR 描述请保持简洁，先写动机。"):
            svc.observe(text, "好的")
            drain(worker)
        gateway = svc.recall("网关模块的端口现在是什么？", passive=True)["context"]
        assert "gate-4100" in gateway and "deploy-5100" not in gateway
        preference = svc.recall("写 PR 描述请保持简洁，先写动机。", passive=True)["context"]
        assert "动机" in preference
        mixed = svc.recall("网关模块的端口是什么？另外 PR 描述有什么偏好？", passive=True)["context"]
        assert "gate-4100" in mixed and "deploy-5100" not in mixed
    finally:
        svc.tasks.close()
        svc.log.close()


def test_rollback_restores_external_pins(tmp_path):
    svc = _svc(tmp_path)
    try:
        svc.engine._external_pins = frozenset({7})
        try:
            with svc._rollback_effect():
                svc.engine._external_pins = frozenset({7, 8, 9})
                raise RuntimeError("forced")
        except RuntimeError:
            pass
        assert svc.engine._external_pins == frozenset({7})
    finally:
        svc.tasks.close()
        svc.log.close()


def test_authorized_retraction_is_not_cold_archive_and_cannot_revive(tmp_path):
    from hybrid_memory.core.types import Pool
    svc = _svc(tmp_path)
    svc.trio_mode = True
    worker = DispatchWorker(svc, _claim_agent)
    try:
        svc.observe("日志级别定为 trace-6100。", "好的")
        drain(worker)
        svc.observe("之前的日志级别设定 trace-6100 作废，先别用它。", "好的")
        drain(worker)
        old = svc.engine.mems[0]
        assert old.withdrawn_at is not None
        assert old.pool is Pool.ARCHIVE
        assert 1 in old.src
        result = svc.recall("日志级别现在是多少？", passive=True)
        assert "trace-6100" not in result["context"]
        assert not svc.engine.credit_shown([0], [True], svc._t)
        assert old.pool is Pool.ARCHIVE
    finally:
        svc.tasks.close()
        svc.log.close()


def test_known_user_setting_is_reconciled_even_when_hauler_omits_it(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "hauler" and payload["unit_id"]:
            return {"candidates": []}
        return _claim_agent(name, payload)
    worker = DispatchWorker(svc, runner)
    try:
        svc.observe("网关模块的端口定为 gate-4100。", "好的")
        drain(worker)
        svc.observe("网关模块的端口改成 gate-4200 了。", "好的")
        drain(worker)
        assert svc.engine.mems[0].superseded_by is not None
        assert "gate-4200" in svc.recall("网关模块的端口现在是什么？", passive=True)["context"]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_single_value_scope_filter_and_pending_freeze(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "selector":
            return {"decisions": [{"candidate_index": i, "action": "CREATE"} for i in range(len(payload["candidates"]))]}
        return _claim_agent(name, payload)
    worker = DispatchWorker(svc, runner)
    try:
        for text in ("网关模块的端口定为 gate-4100。", "部署模块的端口定为 deploy-5100。"):
            svc.observe(text, "好的")
            drain(worker)
        view = svc.recall("部署模块的端口现在是什么？", passive=True)
        assert "deploy-5100" in view["context"] and "gate-4100" not in view["context"]
        svc.observe("网关模块的端口是 gate-4200。", "只是另一份记录")
        drain(worker)
        assert svc.engine.mems[0].pending_review
        svc.observe("网关模块的端口改成 gate-4200 了。", "好的")
        drain(worker)
        assert svc.engine.mems[0].superseded_by is None
        assert len(svc.human_reviews()) == 1
        assert all(m.claim_value != "gate-4200" for m in svc.engine.mems.values())
    finally:
        svc.tasks.close()
        svc.log.close()


def test_ungrounded_candidate_is_rejected_per_item_and_valid_sibling_survives(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "hauler" and payload["unit_id"] == 1:
            return {"candidates": [
                {"text": "The log level setting was voided by the user.",
                 "source_unit_ids": [1]},
                {"text": "日志级别设定 trace-6100 作废，先不使用。",
                 "source_unit_ids": [1]}]}
        return _claim_agent(name, payload)
    worker = DispatchWorker(svc, runner)
    try:
        svc.observe("日志级别定为 trace-6100。", "好的")
        drain(worker)
        before = svc.n_ungrounded
        svc.observe("日志级别设定 trace-6100 作废，先不使用。", "好的")
        drain(worker)
        assert svc.n_ungrounded == before + 1
        rows = svc.tasks.list_tasks(kinds={"selector_due"})
        assert rows and all(row["state"] == "done" for row in rows)
        effect = next(row for row in svc.tasks.list_tasks(kinds={"hauler_due"})
                      if row["id"] == rows[-1]["payload"]["parent_task"])["result"]
        assert effect is not None
        assert svc.engine.mems[0].withdrawn_at is not None
        assert not svc.human_reviews()
    finally:
        svc.tasks.close()
        svc.log.close()


@pytest.mark.parametrize("translated_updates", [False, True])
def test_translated_initial_claim_keeps_source_identity_through_update_and_withdrawal(tmp_path, translated_updates):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        uid = payload["unit_id"]
        if name == "hauler" and (uid == 0 or translated_updates and uid in (1, 2)):
            value = "gate-7301" if uid == 2 else "gate-7300"
            return {"candidates": [{"text": f"The gateway module's port is set to {value}.",
                                     "source_unit_ids": [uid]}]}
        return _claim_agent(name, payload, "EXIST")
    worker = DispatchWorker(svc, runner)
    try:
        svc.observe("网关模块的端口定为 gate-7300。", "好的")
        drain(worker)
        old = svc.engine.mems[0]
        assert old.claim_key == ("网关模块", "端口") and old.claim_unit == 0
        assert old.text == "网关模块的端口定为 gate-7300"
        svc.observe("网关模块的端口是 gate-7300。", "好的")
        drain(worker)
        assert len(svc.engine.mems) == 1 and old.evid == 2
        svc.observe("网关模块的端口改为 gate-7301。", "好的")
        drain(worker)
        assert old.superseded_by is not None
        current = svc.engine.mems[old.superseded_by]
        assert current.claim_key == old.claim_key and current.claim_value == "gate-7301"
        svc.observe("网关模块的端口设定 gate-7301 作废。", "好的")
        drain(worker)
        assert current.withdrawn_at is not None
        assert not svc.recall("网关模块的端口现在是什么？", passive=True)["context"]
        assert all(t["state"] == "done" for t in svc.tasks.list_tasks(kinds={"selector_due"}))
    finally:
        svc.tasks.close()
        svc.log.close()


def test_model_authority_annotation_does_not_split_review_or_authorize_update(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "hauler" and payload["unit_id"] == 2:
            return {"candidates": [{"text": "审计模块的开关定为 flag-8100（最新授权值，覆盖早前的 flag-8000）。",
                                     "source_unit_ids": [1, 2]}]}
        return _claim_agent(name, payload, "UPDATE")
    worker = DispatchWorker(svc, runner)
    try:
        for text in ("审计模块的开关定为 flag-8000。", "审计模块的开关是 flag-8100。",
                     "审计模块的开关是 flag-8100。"):
            svc.observe(text, "好的")
            drain(worker)
        reviews = svc.human_reviews()
        assert len(reviews) == 1
        candidate = json.loads(reviews[0]["candidate"])
        assert set(candidate["source_unit_ids"]) == {1, 2}
        assert "最新授权" not in candidate["text"]
        assert svc.engine.mems[0].superseded_by is None and len(svc.engine.mems) == 1
    finally:
        svc.tasks.close()
        svc.log.close()


def test_candidate_parenthesis_cannot_strip_source_condition_to_authorize_update(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "hauler" and payload["unit_id"] == 1:
            return {"candidates": [{"text": "审计模块的开关定为 flag-8100（最新授权值）。",
                                     "source_unit_ids": [1]}]}
        return _claim_agent(name, payload, "UPDATE")
    worker = DispatchWorker(svc, runner)
    try:
        svc.observe("审计模块的开关定为 flag-8000。", "好的")
        drain(worker)
        svc.observe("不对，审计模块的开关定为 flag-8100（暂不执行）。", "待确定")
        drain(worker)
        assert svc.engine.mems[0].superseded_by is None
        assert len(svc.engine.mems) == 1 and len(svc.human_reviews()) == 1
    finally:
        svc.tasks.close()
        svc.log.close()


def test_translated_claim_with_multiple_source_slots_does_not_guess_identity(tmp_path):
    from hybrid_memory.errors import ProposalRejected
    svc = _svc(tmp_path)
    try:
        svc.observe("网关模块的端口定为 gate-7300。部署模块的端口定为 gate-7300。", "好的")
        with pytest.raises(ProposalRejected, match="ambiguous_claim_source"):
            svc._validate_proposal({"text": "The module's port is set to gate-7300.",
                                    "source_unit_ids": [0]}, None)
        event, _ = svc._validate_proposal({"text": "网关模块的端口是 gate-7300。",
                                          "source_unit_ids": [0]}, None)
        assert event.claim_key == ("网关模块", "端口")
    finally:
        svc.tasks.close()
        svc.log.close()


def test_hauler_selector_create_exist_and_overlapping_window(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    calls = []

    def fake(name, payload):
        calls.append((name, payload))
        if name == "hauler":
            unit = payload["window"][-1]
            assert unit["unit_id"] == payload["unit_id"]
            return {"candidates": [{"text": unit["user_text"],
                                    "source_unit_ids": [payload["unit_id"]]}]}
        assert name == "selector"
        assert payload["candidates"][0]["source_unit_ids"] == [payload["unit_id"]]
        if payload["memories"]:
            return {"decisions": [{"candidate_index": 0, "action": "EXIST", "target_id": 0}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}

    worker = DispatchWorker(svc, fake)
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

    worker = DispatchWorker(svc, fake)
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
    monkeypatch.setattr("hybrid_memory.agents.opencode.shutil.which", lambda x: x)
    # N48 serve+attach（显式模式，N50 后非 Windows 默认 bootstrap）：
    # 跳过真实 serve 拉起，直接挂到既定 url
    runner.mode = "serve+attach"
    monkeypatch.setattr(runner, "_ensure_server", lambda: None)
    runner._server_url = "http://127.0.0.1:1"

    def run(cmd, **kwargs):
        assert cmd[0] == "definitely-not-installed-opencode"
        assert cmd[1:3] == ["run", "--pure"]
        assert cmd[cmd.index("--attach") + 1] == "http://127.0.0.1:1"
        assert cmd[cmd.index("--agent") + 1] == "hauler"
        assert kwargs["env"]["DYNAMICS_MEMORY_INTERNAL_AGENT"] == "1"
        return Result()
    monkeypatch.setattr("hybrid_memory.agents.opencode.subprocess.run", run)
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
        drain(DispatchWorker(fresh, fake))
        assert calls == ["hauler", "selector"]  # stored Hauler output was replayed
        assert fresh.engine.mems[0].text == "项目统一使用 bun 工具"
        assert len(fresh.tasks.list_tasks(states=("done",), kinds={"hauler_due", "selector_due"})) == 2
        drain(DispatchWorker(fresh, fake))
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
        DispatchWorker(svc, fake).process_once()
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
        drain(DispatchWorker(svc, fake))
        before = svc.engine.mems[0].evid
        svc.observe("还是上面的决定", "好的")
        drain(DispatchWorker(svc, fake))
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
        drain(DispatchWorker(svc, fake))
        ret = svc.recall("端口现在是 8080")
        svc.feedback(ret["retrieval_id"], "端口现在是 8080", "8080")
        svc.observe("这个端口我之前明明讲过", "抱歉")
        drain(DispatchWorker(svc, fake))
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
        drain(DispatchWorker(svc, fake))
        rid = svc.tasks.rule_report()[0]["id"]
        assert svc.tasks.rule_report()[0]["uses"] == 0
        svc.observe("端口 8080", "好的")
        drain(DispatchWorker(svc, fake))
        assert [r["id"] for r in seen[-1]["rules"]] == [rid]
        svc.observe("这是别的事情", "好的")
        drain(DispatchWorker(svc, fake))
        assert seen[-1]["rules"] == []  # overlap does not broaden a rule's scope
        assert svc.tasks.rule_report()[0]["uses"] == 1
        assert svc.tasks.disable_rule(rid)
        assert not svc.tasks.disable_rule(rid)
        svc.observe("端口 8080", "好的")
        drain(DispatchWorker(svc, fake))
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
        drain(DispatchWorker(svc, fake))
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
        drain(DispatchWorker(svc, fake))
        rule = svc.tasks.rule_report()[0]
        svc.observe("端口8080", "收到")
        drain(DispatchWorker(svc, fake))
        assert svc.tasks.rule_report()[0]["uses"] == 1
        svc.observe("这个端口我之前明明讲过", "抱歉")
        drain(DispatchWorker(svc, fake))
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
        DispatchWorker(svc, fake).process_once()
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
        drain(DispatchWorker(svc, fake))
        svc.engine.mems[0].pool = Pool.ARCHIVE
        svc.observe("项目统一使用 bun 工具", "好的")
        drain(DispatchWorker(svc, fake))
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].pool is not Pool.ARCHIVE
        assert svc.engine.mems[0].src == {0, 1}
    finally:
        svc.tasks.close()
        svc.log.close()


def test_workflow_attempt_bound_matches_policy():
    """H8 锁死：agents 侧 MAX_ATTEMPTS 与 KindPolicy 同值。"""
    from hybrid_memory.agents.protocol import MAX_ATTEMPTS
    from hybrid_memory.dispatch.policy import POLICIES
    assert MAX_ATTEMPTS == POLICIES["hauler_due"].max_attempts == 5
