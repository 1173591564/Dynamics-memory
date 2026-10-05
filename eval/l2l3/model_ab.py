from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import random
import threading
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hybrid_memory.agents import hauler, payload as agent_payload, reviewer, selector
from hybrid_memory.agents.opencode import OpenCodeRunner
from hybrid_memory.config import load_env_key
from hybrid_memory.guards.redact import redact_secrets
from hybrid_memory.semantics import RealChatSemantics
from hybrid_memory.service.operate import validate_proposal
from eval.l2l3.inline_runner import _agent_prompt, _REPO

REVIEW_QUESTIONS = {
    "hauler": ("grounded", "atomic", "faithful", "relevant", "coverage"),
    "selector": ("faithful", "disposition", "scope", "coverage"),
    "reviewer": ("diagnosis", "rule_scope", "repair_grounding", "repair_quality", "coverage"),
}

PROVIDERS = {
    "glm": {"model": "glm-5.3-flash", "effort": "max", "key_env": "ZAI_API_KEY",
            "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    "deepseek": {"model": "deepseek-flash", "effort": "high", "key_env": "DEEPSEEK_API_KEY",
                 "url": "https://api.deepseek.com/chat/completions"},
}


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def load_key(provider: str) -> str | None:
    name = PROVIDERS[provider]["key_env"]
    if os.environ.get(name):
        return os.environ[name]
    if provider == "glm":
        return load_env_key(_REPO)
    env_file = _REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key == name:
                return value.strip().strip('"').strip("'") or None
    return None


def freeze_case(name: str, payload: dict, svc, directory: str) -> str:
    if name not in ("hauler", "selector", "reviewer"):
        raise ValueError("unknown role")
    prompt = _agent_prompt(name)
    with svc.lock:
        uid = payload.get("unit_id", (payload.get("complaint") or {}).get("id"))
        row = svc.tasks.get(payload["task_id"])
        seal = svc.tasks.call_context(payload["task_id"]) or {}
        window = payload.get("window")
        if window is None:
            unit = svc.log.get(uid)
            ids = hauler.sealed_window(svc, row) if row else None
            supplied = svc.log.window(ids if ids is not None else svc.log.recent_ids(uid, limit=6),
                                      max_chars=12000, before=unit["t"] + 1)
            if supplied["truncated"]:
                raise ValueError("frozen grounding window exceeds production bound")
            window = supplied["units"]
        case = {"version": 1, "role": name, "payload": payload,
                "prompt": prompt, "window": window,
                "snapshot_revision": seal.get("snapshot_revision", svc._checkpoint_revision),
                "task_id": payload["task_id"], "origin_task_attempt": row["attempts"] if row else None,
                "origin": "captured-runtime-payload"}
    case = json.loads(json.dumps(case, ensure_ascii=False, allow_nan=False))
    serialized = json.dumps(case, ensure_ascii=False)
    if redact_secrets(serialized) != serialized:
        raise ValueError("payload contains redactable content; frozen artifact refused")
    case["payload_sha256"], case["prompt_sha256"] = _hash(case["payload"]), _hash(case["prompt"])
    case["case_sha256"] = _hash(case)
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}-{case['task_id']}-{case['case_sha256'][:12]}.json"
    encoded = json.dumps(case, ensure_ascii=False, indent=1)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError("frozen artifact collision")
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(encoded)
    return str(path)


class CapturingRunner:
    def __init__(self, runner, service, directory):
        self.runner, self.service, self.directory = runner, service, directory

    def available(self):
        return self.runner.available()

    def verify_channel(self):
        return self.runner.verify_channel()

    def run_agent(self, name, payload):
        freeze_case(name, payload, self.service, self.directory)
        return self.runner.run_agent(name, payload)

    def close(self):
        return self.runner.close()

    def __call__(self, name, payload):
        return self.run_agent(name, payload)


def load_cases(paths: list[str]) -> list[dict]:
    cases = []
    for name in paths:
        path = Path(name)
        files = sorted(path.glob("*.json")) if path.is_dir() else [path]
        for file in files:
            case = json.loads(file.read_text(encoding="utf-8"))
            digest = case.pop("case_sha256")
            if digest != _hash(case) or case["payload_sha256"] != _hash(case["payload"]) or case["prompt_sha256"] != _hash(case["prompt"]):
                raise ValueError("frozen case hash mismatch")
            case["case_sha256"] = digest
            if case["version"] != 1 or case["role"] not in ("hauler", "selector", "reviewer"):
                raise ValueError("unsupported frozen case")
            cases.append(case)
    if not cases or len({c["case_sha256"] for c in cases}) != len(cases):
        raise ValueError("empty or duplicate frozen cases")
    return cases


class FrozenLog:
    def __init__(self, window):
        self.units = {u["unit_id"]: u for u in window}

    def get(self, uid):
        return self.units.get(uid)

    def exists(self, ids, before=None):
        return [uid for uid in ids if uid in self.units and (before is None or self.units[uid]["t"] < before)]


def validate_reply(case: dict, reply: dict) -> dict:
    role, built = case["role"], case["payload"]
    kind = role + "_due"
    seal = agent_payload.seal_context(kind, built, case["snapshot_revision"])
    seal["window_ids"] = [u["unit_id"] for u in case["window"]]
    svc = SimpleNamespace(log=FrozenLog(case["window"]), _scene="",
        semantics=RealChatSemantics(None),
        tasks=SimpleNamespace(call_context=lambda _: seal),
        engine=SimpleNamespace(mems={m["id"]: SimpleNamespace(**dict(
            {"claim_key": (), "claim_value": "", "claim_unit": None, "withdrawn_at": None,
             "pending_review": False, "reviewed_after": None, "v": 0.5, "birth": 0}, **m, superseded_by=None, aggregated_into=None))
                                     for m in built.get("memories", [])}))
    for memory in svc.engine.mems.values():
        memory.claim_key = tuple(memory.claim_key)
        if memory.reviewed_after is not None:
            memory.reviewed_after = tuple(memory.reviewed_after)
    svc._validate_proposal = lambda proposal, before: validate_proposal(svc, proposal, before)
    uid = built.get("unit_id", (built.get("complaint") or {}).get("id"))
    row = {"id": built["task_id"], "kind": kind, "payload": dict(built, unit_id=uid)}
    normalized = {"hauler": hauler.validate, "selector": selector.validate, "reviewer": reviewer.validate}[role](reply, row, svc)
    candidates = (normalized if role == "hauler" else normalized["repair_candidates"] if role == "reviewer" else built["candidates"])
    ground = []
    for candidate in candidates:
        try:
            validate_proposal(svc, candidate, None)
        except ValueError:
            ground.append(False)
        else:
            ground.append(True)
    cited = {uid for candidate in candidates for uid in candidate.get("source_unit_ids", candidate.get("src", []))}
    window_ids = set(svc.log.units)
    return {"validator_pass": True, "candidate_count": len(candidates), "grounded": sum(ground),
            "grounding_rate": sum(ground) / len(ground) if ground else None,
            "source_coverage": len(cited & window_ids) / len(window_ids) if window_ids else None,
            "output_density": sum(len(c["text"]) for c in candidates) / max(1, sum(len(u["user_text"] + u["assistant_text"]) for u in case["window"])),
            "decision_coverage": len(normalized) / len(candidates) if role == "selector" and candidates else None,
            "normalized": normalized}


def _request(url, key, body, timeout):
    request = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    box = {}
    def send():
        try:
            with closing(urlopen(request, timeout=timeout)) as response:
                box["response"] = json.loads(response.read())
        except Exception as exc:
            box["error"] = exc
    thread = threading.Thread(target=send, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("model request wall-clock limit exceeded")
    if "error" in box:
        raise box["error"]
    return box["response"]


def _cost(usage, rates):
    if not rates or type(usage.get("prompt_tokens")) is not int or type(usage.get("completion_tokens")) is not int:
        return None
    hit = usage.get("prompt_cache_hit_tokens", (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0))
    miss = usage.get("prompt_cache_miss_tokens", usage["prompt_tokens"] - hit)
    if hit and rates.get("cached_input") is None:
        return None
    if rates.get("input") is None or rates.get("output") is None:
        return None
    return (miss * rates["input"] + hit * (rates.get("cached_input") or 0) + usage["completion_tokens"] * rates["output"]) / 1_000_000


def call_case(case, provider, key, *, max_attempts=1, timeout=300.0, rates=None):
    if type(max_attempts) is not int or not 1 <= max_attempts <= 5 or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid bounded request limits")
    if rates and any(v is not None and (not math.isfinite(v) or v < 0) for v in rates.values()):
        raise ValueError("rates must be finite and nonnegative")
    cfg = PROVIDERS[provider]
    body = {"model": cfg["model"], "reasoning_effort": cfg["effort"],
            "messages": [{"role": "system", "content": case["prompt"]},
                         {"role": "user", "content": "Protocol message:\n" + json.dumps(case["payload"], ensure_ascii=False)}]}
    if provider == "glm":
        body["temperature"] = 0.0
    attempts = []
    reply, validation = None, None
    started = time.monotonic()
    for attempt in range(max_attempts):
        request_started = time.time()
        tick = time.monotonic()
        rec = {"attempt": attempt + 1, "request_at": request_started, "usage": {}, "cost_usd": None}
        try:
            response = _request(cfg["url"], key, body, timeout)
            rec["usage"] = response.get("usage") or {}
            rec["actual_model"] = response.get("model")
            rec["cost_usd"] = _cost(rec["usage"], rates)
            text = response["choices"][0]["message"]["content"]
            reply = OpenCodeRunner._parse_text(text, case["role"])
            validation = validate_reply(case, reply)
            rec["accepted"] = True
        except Exception as exc:
            rec["accepted"] = False
            rec["error_type"] = type(exc).__name__
            rec["error_detail"] = redact_secrets(str(exc)).replace(key, "[REDACTED]")
            if reply is not None:
                rec["rejected_response"] = json.loads(redact_secrets(json.dumps(reply, ensure_ascii=False)).replace(key, "[REDACTED]"))
            rec["http_status"] = exc.code if isinstance(exc, HTTPError) else None
            reply, validation = None, None
            stop = isinstance(exc, TimeoutError) or rec["http_status"] in (401, 403)
        rec["wall_s"], rec["response_at"] = time.monotonic() - tick, time.time()
        attempts.append(rec)
        if rec["accepted"] or stop:
            break
    usages = [a["usage"] for a in attempts]
    def total(field):
        return sum(u[field] for u in usages) if all(type(u.get(field)) is int for u in usages) else None
    def detail(field, parent):
        values = [(u.get(parent) or {}).get(field) for u in usages]
        return sum(values) if all(type(v) is int for v in values) else None
    return {"provider": provider, "role": case["role"], "case_sha256": case["case_sha256"],
            "task_id": case["task_id"], "origin_task_attempt": case.get("origin_task_attempt"),
            "payload_sha256": case["payload_sha256"], "prompt_sha256": case["prompt_sha256"],
            "requested_model": cfg["model"], "actual_models": [a.get("actual_model") for a in attempts],
            "reasoning_effort": cfg["effort"], "effort_verified": False,
            "api_url": cfg["url"], "transport": "inline-chat-completions",
            "ttft_s": None, "ttft_status": "not_measured_nonstreaming", "wall_s": time.monotonic() - started,
            "attempts": attempts, "retries": len(attempts) - 1, "accepted": bool(validation),
            "prompt_tokens": total("prompt_tokens"), "completion_tokens": total("completion_tokens"),
            "reasoning_tokens": detail("reasoning_tokens", "completion_tokens_details"),
            "cache_hit_tokens": total("prompt_cache_hit_tokens") if all("prompt_cache_hit_tokens" in u for u in usages) else detail("cached_tokens", "prompt_tokens_details"),
            "cache_miss_tokens": total("prompt_cache_miss_tokens"),
            "cost_usd": sum(a["cost_usd"] for a in attempts) if all(a["cost_usd"] is not None for a in attempts) else None,
            "cost_basis": "configured_USD_per_million_usage_estimate_not_invoice" if rates and rates.get("input") is not None and rates.get("output") is not None else "rates_not_configured",
            "response": reply, "validation": validation}


class MeasuredRunner:
    def __init__(self, service, provider, directory):
        self.service, self.provider, self.directory = service, provider, directory
        self.key = load_key(provider)

    def available(self):
        return bool(self.key)

    def verify_channel(self):
        if not self.key:
            raise RuntimeError("missing " + PROVIDERS[self.provider]["key_env"])
        if not all(_agent_prompt(role) for role in ("hauler", "selector", "reviewer")):
            raise RuntimeError("agent prompt missing")
        return True

    def run_agent(self, name, payload):
        path = freeze_case(name, payload, self.service, self.directory)
        case = load_cases([path])[0]
        record = call_case(case, self.provider, self.key)
        with open(Path(self.directory) / "chain-calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if not record["accepted"]:
            raise RuntimeError("evaluation model call failed: " + record["attempts"][-1]["error_type"])
        return record["response"]

    def __call__(self, name, payload):
        return self.run_agent(name, payload)

    def close(self):
        return None


def summarize(records):
    roles = {}
    for role in ("hauler", "selector", "reviewer"):
        group = [r for r in records if r["role"] == role]
        if not group:
            continue
        roles[role] = {}
        for provider in PROVIDERS:
            rows = [r for r in group if r["provider"] == provider]
            if rows:
                count = sum((r["validation"] or {}).get("candidate_count", 0) for r in rows)
                ground = sum((r["validation"] or {}).get("grounded", 0) for r in rows)
                roles[role][provider] = {"calls": len(rows), "accepted": sum(r["accepted"] for r in rows),
                    "mean_wall_s": sum(r["wall_s"] for r in rows) / len(rows),
                    "candidate_count": count, "grounding_rate": ground / count if count else None,
                    "retries": sum(r["retries"] for r in rows),
                    "cost_usd": sum(r["cost_usd"] for r in rows) if all(r["cost_usd"] is not None for r in rows) else None}
        if all(p in roles[role] for p in PROVIDERS):
            ratio = roles[role]["deepseek"]["mean_wall_s"] / max(1e-9, roles[role]["glm"]["mean_wall_s"])
            roles[role]["deepseek_to_glm_wall_ratio"] = ratio
    return {"roles": roles, "decision": "awaiting_blind_review_and_real_chain",
            "required_roles_present": set(roles) == {"hauler", "selector", "reviewer"},
            "limits": ["grounding is not semantic entailment", "source coverage is not fact recall",
                       "Selector disposition and Reviewer diagnosis require blind review",
                       "requested effort is explicit; provider execution effort cannot be inferred from usage",
                       "inline comparison does not verify OpenCode provider compatibility or task leases"]}


def run_ab(paths, out_dir, *, repeats=1, max_attempts=1, timeout=300.0, rates=None):
    cases = load_cases(paths)
    keys = {p: load_key(p) for p in PROVIDERS}
    missing = [PROVIDERS[p]["key_env"] for p in PROVIDERS if not keys[p]]
    if missing:
        raise RuntimeError("missing credentials: " + ", ".join(missing))
    if repeats < 1 or max_attempts < 1 or max_attempts > 5 or timeout <= 0:
        raise ValueError("invalid bounded experiment limits")
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("A/B output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    records = []
    with open(out / "records.jsonl", "x", encoding="utf-8") as f:
        for repeat in range(repeats):
            for index, case in enumerate(cases):
                providers = list(PROVIDERS)
                if (repeat + index) % 2:
                    providers.reverse()
                for provider in providers:
                    record = call_case(case, provider, keys[provider], max_attempts=max_attempts,
                                       timeout=timeout, rates=(rates or {}).get(provider))
                    record["repeat"] = repeat
                    records.append(record)
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    f.flush()
                    if any(a.get("http_status") in (401, 403) for a in record["attempts"]):
                        raise RuntimeError("provider authentication failed; records preserved")
    order = list(range(len(records)))
    random.Random(7).shuffle(order)
    case_by_hash = {c["case_sha256"]: c for c in cases}
    key = {}
    with open(out / "blind.jsonl", "x", encoding="utf-8") as f:
        for i, idx in enumerate(order):
            r = records[idx]
            audit_id = f"blind-{i:04d}"
            case = case_by_hash[r["case_sha256"]]
            key[audit_id] = {"record_index": idx, "provider": r["provider"], "role": r["role"], "case_sha256": r["case_sha256"]}
            f.write(json.dumps({"audit_id": audit_id, "role": r["role"], "payload": case["payload"],
                                "window": case["window"], "response": r["response"],
                                "verdicts": {q: None for q in REVIEW_QUESTIONS[r["role"]]}}, ensure_ascii=False) + "\n")
    (out / "blind.key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = summarize(records)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def settle(filled_path, run_dir):
    root = Path(run_dir)
    key = json.loads((root / "blind.key.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in (root / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [json.loads(line) for line in Path(filled_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r.get("audit_id") for r in rows]
    if not rows or len(set(ids)) != len(ids) or set(ids) != set(key):
        raise ValueError("blind scores must cover each audit_id exactly once")
    scores = {}
    for row in rows:
        item = key[row["audit_id"]]
        record = records[item["record_index"]]
        if record["case_sha256"] != item["case_sha256"] or record["provider"] != item["provider"] or record["role"] != item["role"]:
            raise ValueError("blind mapping does not match records")
        role, provider = item["role"], item["provider"]
        verdicts = row.get("verdicts") or {}
        if set(verdicts) != set(REVIEW_QUESTIONS[role]) or any(v not in ("pass", "fail", "na") for v in verdicts.values()):
            raise ValueError("missing or invalid role-specific verdicts")
        optional = {"repair_grounding", "repair_quality"} if role == "reviewer" and not (record.get("response") or {}).get("repair_candidates") else set()
        if any(verdicts[q] == "na" and q not in optional for q in verdicts):
            raise ValueError("core review questions cannot be marked not applicable")
        for question, verdict in verdicts.items():
            if verdict == "na":
                continue
            counter = scores.setdefault(role, {}).setdefault(provider, {}).setdefault(question, [0, 0])
            counter[0] += verdict == "pass"
            counter[1] += 1
    summary = summarize(records)
    summary["blind_scores"] = scores
    reasons = []
    for role in REVIEW_QUESTIONS:
        group = [r for r in records if r["role"] == role]
        if not group or any(not r["accepted"] for r in group):
            reasons.append(role + ": missing or invalid model outputs")
            continue
        data = summary["roles"][role]
        if data.get("deepseek_to_glm_wall_ratio", 1) > 0.5:
            reasons.append(role + ": latency threshold not reached")
        if role == "hauler" and (data["deepseek"]["grounding_rate"] is None or data["deepseek"]["grounding_rate"] < 0.95):
            reasons.append(role + ": grounding threshold not reached")
        for question in REVIEW_QUESTIONS[role]:
            glm = scores.get(role, {}).get("glm", {}).get(question)
            ds = scores.get(role, {}).get("deepseek", {}).get(question)
            if glm and ds and ds[0] / ds[1] < glm[0] / glm[1]:
                reasons.append(role + ": quality regression on " + question)
            elif bool(glm) != bool(ds):
                reasons.append(role + ": incomparable applicability on " + question)
    summary["threshold_failures"] = reasons
    summary["decision"] = "ab_thresholds_not_met" if reasons else "eligible_for_real_chain_not_production_switch"
    (root / "reviewed-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+")
    ap.add_argument("--filled")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--max-attempts", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=300.0)
    for provider in PROVIDERS:
        for kind in ("input", "output", "cached-input"):
            ap.add_argument(f"--{provider}-{kind}-rate", type=float)
    args = ap.parse_args()
    if args.filled:
        print(json.dumps(settle(args.filled, args.out_dir), ensure_ascii=False, indent=1))
        return
    if not args.cases:
        ap.error("--cases or --filled is required")
    rates = {p: {k: getattr(args, f"{p}_{k}_rate") for k in ("input", "output", "cached_input")} for p in PROVIDERS}
    print(json.dumps(run_ab(args.cases, args.out_dir, repeats=args.repeats,
                           max_attempts=args.max_attempts, timeout=args.timeout, rates=rates), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
