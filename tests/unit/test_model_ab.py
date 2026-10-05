from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.l2l3 import model_ab
from test_ouroboros import _svc


def _case(tmp_path, role="hauler"):
    svc = _svc()
    try:
        svc.observe("网关端口定为 gate-4100。", "收到。")
        from hybrid_memory.agents.payload import build_payload
        pl = {"unit_id": 0}
        if role == "selector":
            pl["candidates"] = [{"text": "网关端口是 gate-4100", "source_unit_ids": [0]}]
        task_id = svc.tasks.enqueue(role + "_due", pl, 0)
        row = svc.tasks.get(task_id)
        payload = build_payload(role + "_due", svc, row)
        return model_ab.freeze_case(role, payload, svc, str(tmp_path))
    finally:
        svc.tasks.close()
        svc.log.close()


def test_freeze_keeps_exact_payload_prompt_and_integrity(tmp_path):
    path = _case(tmp_path)
    case = model_ab.load_cases([path])[0]
    assert case["payload"]["window"][0]["user_text"] == "网关端口定为 gate-4100。"
    assert case["prompt"] == model_ab._agent_prompt("hauler")
    case["payload"]["unit_id"] = 99
    Path(path).write_text(json.dumps(case), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        model_ab.load_cases([path])


@pytest.mark.parametrize("role,reply", [
    ("hauler", {"candidates": [{"text": "网关端口是 gate-4100", "source_unit_ids": [0]}]}),
    ("selector", {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}),
    ("reviewer", {"diagnosis": "检查网关端口", "rules": [], "repair_candidates": [], "rule_reviews": []}),
])
def test_three_roles_use_production_validators(tmp_path, role, reply):
    case = model_ab.load_cases([_case(tmp_path, role)])[0]
    result = model_ab.validate_reply(case, reply)
    assert result["validator_pass"] is True
    if role == "selector":
        with pytest.raises(ValueError):
            model_ab.validate_reply(case, {"decisions": []})
    if role == "reviewer":
        with pytest.raises(ValueError):
            model_ab.validate_reply(case, {"diagnosis": "ok", "rules": [{"target": "selector", "instruction": "test", "scope": "global"}]})


def test_grounding_and_source_coverage_do_not_reward_empty_output(tmp_path):
    case = model_ab.load_cases([_case(tmp_path)])[0]
    bad = model_ab.validate_reply(case, {"candidates": [{"text": "网关端口是 fabricatedidentifier-9999", "source_unit_ids": [0]}]})
    assert bad["grounded"] == 0
    assert bad["candidate_count"] == 1
    empty = model_ab.validate_reply(case, {"candidates": []})
    assert empty["grounding_rate"] is None
    assert empty["source_coverage"] == 0


def test_deepseek_high_request_does_not_change_glm_or_payload(tmp_path, monkeypatch):
    case = model_ab.load_cases([_case(tmp_path)])[0]
    seen = []
    def request(url, key, body, timeout):
        seen.append((url, body))
        return {"model": body["model"], "choices": [{"message": {"content": '{"candidates": []}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                          "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40,
                          "completion_tokens_details": {"reasoning_tokens": 10}}}
    monkeypatch.setattr(model_ab, "_request", request)
    glm = model_ab.call_case(case, "glm", "test", max_attempts=1)
    ds = model_ab.call_case(case, "deepseek", "test", max_attempts=1)
    assert seen[0][1]["messages"] == seen[1][1]["messages"]
    assert seen[0][1]["reasoning_effort"] == "max"
    assert seen[1][1]["reasoning_effort"] == "high"
    assert seen[1][1]["model"] == "deepseek-flash"
    assert ds["reasoning_tokens"] == 10
    assert ds["cache_hit_tokens"] == 60
    assert ds["cost_usd"] is None and glm["ttft_s"] is None


def test_retry_usage_and_cost_include_failed_protocol_response(tmp_path, monkeypatch):
    case = model_ab.load_cases([_case(tmp_path)])[0]
    replies = ["bad json", '{"candidates": []}']
    monkeypatch.setattr(model_ab, "_request", lambda url, key, body, timeout: {
        "model": body["model"], "choices": [{"message": {"content": replies.pop(0)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    result = model_ab.call_case(case, "glm", "test", max_attempts=2,
                                rates={"input": 1.0, "output": 2.0, "cached_input": 1.0})
    assert result["retries"] == 1
    assert result["prompt_tokens"] == 200
    assert result["completion_tokens"] == 40
    assert result["cost_usd"] == pytest.approx(0.00028)


def test_request_socket_uses_the_configured_wall_budget(monkeypatch):
    from types import SimpleNamespace
    observed = []
    def open_response(request, timeout):
        observed.append(timeout)
        return SimpleNamespace(read=lambda: b"{}", close=lambda: None)
    monkeypatch.setattr(model_ab, "urlopen", open_response)
    assert model_ab._request("https://example.com/chat/completions", "test", {}, 180) == {}
    assert observed == [180]


def test_rejected_response_keeps_redacted_validation_diagnostics(tmp_path, monkeypatch):
    case = model_ab.load_cases([_case(tmp_path)])[0]
    reply = {"candidates": [{"text": "网关端口是 gate-4100", "source_unit_ids": [99]}]}
    monkeypatch.setattr(model_ab, "_request", lambda url, key, body, timeout: {
        "model": body["model"], "choices": [{"message": {"content": json.dumps(reply, ensure_ascii=False)}}]})
    result = model_ab.call_case(case, "glm", "private-test-key")
    attempt = result["attempts"][0]
    assert result["accepted"] is False
    assert "supplied window" in attempt["error_detail"]
    assert attempt["rejected_response"] == reply
    assert "private-test-key" not in json.dumps(result)


def test_missing_key_preflight_does_not_call_either_model(tmp_path, monkeypatch):
    case = _case(tmp_path)
    monkeypatch.setattr(model_ab, "load_env_key", lambda *a: "test")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(model_ab, "_REPO", tmp_path)
    monkeypatch.setattr(model_ab, "_request", lambda *a: pytest.fail("must preflight both keys"))
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        model_ab.run_ab([case], str(tmp_path / "out"))


def test_blind_output_hides_provider_and_quality_gate_stays_pending(tmp_path, monkeypatch):
    case = _case(tmp_path)
    monkeypatch.setattr(model_ab, "load_env_key", lambda *a: "test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr(model_ab, "_request", lambda url, key, body, timeout: {
        "model": body["model"], "choices": [{"message": {"content": '{"candidates": []}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    summary = model_ab.run_ab([case], str(tmp_path / "out"))
    assert summary["decision"] == "awaiting_blind_review_and_real_chain"
    worksheet = (tmp_path / "out" / "blind.jsonl").read_text(encoding="utf-8")
    assert "glm-5.3" not in worksheet and "deepseek" not in worksheet
    assert len(worksheet.splitlines()) == 2


def test_deepseek_reads_repo_dotenv_without_exposing_or_changing_glm(tmp_path, monkeypatch):
    monkeypatch.setattr(model_ab, "_REPO", tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env").write_text('ZAI_API_KEY=glm-test\nDEEPSEEK_API_KEY="ds-test"\n', encoding="utf-8")
    assert model_ab.load_key("deepseek") == "ds-test"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "override")
    assert model_ab.load_key("deepseek") == "override"
    assert model_ab.PROVIDERS["glm"]["effort"] == "max"
    assert model_ab.PROVIDERS["deepseek"]["effort"] == "high"


def test_blind_settlement_rejects_partial_and_never_approves_missing_roles(tmp_path, monkeypatch):
    case = _case(tmp_path)
    monkeypatch.setattr(model_ab, "load_key", lambda _: "test")
    monkeypatch.setattr(model_ab, "_request", lambda url, key, body, timeout: {
        "model": body["model"], "choices": [{"message": {"content": '{"candidates": []}'}}]})
    out = tmp_path / "out"
    model_ab.run_ab([case], str(out))
    rows = [json.loads(line) for line in (out / "blind.jsonl").read_text(encoding="utf-8").splitlines()]
    filled = tmp_path / "filled.jsonl"
    filled.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        model_ab.settle(str(filled), str(out))
    for row in rows:
        row["verdicts"] = {q: "pass" for q in row["verdicts"]}
    filled.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = model_ab.settle(str(filled), str(out))
    assert result["decision"] == "ab_thresholds_not_met"
    assert any("selector" in reason for reason in result["threshold_failures"])


def test_measured_runner_three_roles_reach_real_worker_effects(tmp_path, monkeypatch):
    from hybrid_memory.dispatch.worker import DispatchWorker
    svc = _svc()
    svc.trio_mode = True
    monkeypatch.setattr(model_ab, "load_key", lambda _: "test")
    def request(url, key, body, timeout):
        built = json.loads(body["messages"][1]["content"].split("\n", 1)[1])
        if built["kind"] == "hauler_due":
            reply = {"candidates": [{"text": "网关端口是 gate-4100", "source_unit_ids": [0]}]}
        elif built["kind"] == "selector_due":
            reply = {"decisions": [{"candidate_index": i, "action": "CREATE"} for i in range(len(built["candidates"]))]}
        else:
            reply = {"diagnosis": "区分实体，不改网关端口", "rules": [], "repair_candidates": [], "rule_reviews": []}
        return {"model": body["model"], "choices": [{"message": {"content": json.dumps(reply, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    monkeypatch.setattr(model_ab, "_request", request)
    runner = model_ab.MeasuredRunner(svc, "glm", str(tmp_path))
    worker = DispatchWorker(svc, runner)
    try:
        svc.observe("网关端口定为 gate-4100。", "收到。")
        for _ in range(6):
            worker.process_once()
        assert any("gate-4100" in m.text for m in svc.engine.mems.values())
        svc.observe("不对，你记错了，不要把部署与网关混淆，网关端口仍是 gate-4100。", "收到。")
        for _ in range(6):
            worker.process_once()
        cases = model_ab.load_cases([str(tmp_path)])
        assert {c["role"] for c in cases} == {"hauler", "selector", "reviewer"}
        records = [json.loads(line) for line in (tmp_path / "chain-calls.jsonl").read_text(encoding="utf-8").splitlines()]
        assert all(r["accepted"] and r["reasoning_effort"] == "max" for r in records)
        assert all(t["state"] == "done" for t in svc.tasks.list_tasks(kinds=("hauler_due", "selector_due", "reviewer_due")))
    finally:
        svc.tasks.close()
        svc.log.close()


def test_capture_runner_is_callable_on_real_dispatch_path(tmp_path):
    from hybrid_memory.agents.payload import build_payload
    svc = _svc()
    try:
        svc.observe("网关端口定为 gate-4100。", "收到。")
        task_id = svc.tasks.enqueue("hauler_due", {"unit_id": 0}, 0)
        built = build_payload("hauler_due", svc, svc.tasks.get(task_id))
        class Runner:
            def run_agent(self, name, payload): return {"candidates": []}
        runner = model_ab.CapturingRunner(Runner(), svc, str(tmp_path))
        assert runner("hauler", built) == {"candidates": []}
        assert len(model_ab.load_cases([str(tmp_path)])) == 1
    finally:
        svc.tasks.close()
        svc.log.close()
