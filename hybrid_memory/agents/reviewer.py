"""Reviewer 校验（P6 从 agent/trio.py 拆出）：诊断/规则/修复 + 作用域。"""
from __future__ import annotations

from . import hauler, payload


def scope_of(scope) -> str:
    """规则作用域：project 或 entity:<字面>；非法抛错。"""
    if (scope != "project" and (not isinstance(scope, str) or
            not scope.startswith("entity:") or
            not 0 < len(scope[7:].strip()) <= 120)):
        raise ValueError("rule scope must be project or entity:<literal>")
    return scope


def validate(reply, row, svc):
    """校验诊断/规则评审/新规则/修复候选；返回归一化 bundle。"""
    if not isinstance(reply.get("diagnosis"), str) or not reply["diagnosis"].strip():
        raise ValueError("Reviewer must supply a diagnosis")
    rule_reviews = reply.get("rule_reviews", [])
    if not isinstance(rule_reviews, list) or len(rule_reviews) > 10:
        raise ValueError("Reviewer rule reviews must be a list of at most 10")
    review_context = payload.build_payload("reviewer_due", svc, row)
    used = {rid for task in review_context["handoffs"]
            for rid in task.get("rule_ids", [])}
    seen = set()
    for rr in rule_reviews:
        if (not isinstance(rr, dict) or type(rr.get("rule_id")) is not int
            or rr["rule_id"] in seen or rr["rule_id"] not in used
            or rr.get("assessment") not in ("helpful", "ineffective", "uncertain")
            or not isinstance(rr.get("reason"), str)
            or not 0 < len(rr["reason"].strip()) <= 500):
            raise ValueError("rule assessment requires observed prior use and a reason")
        seen.add(rr["rule_id"])
    rules = reply.get("rules", [])
    if not isinstance(rules, list) or len(rules) > 10:
        raise ValueError("Reviewer rules must be a list of at most 10")
    for r in rules:
        if (not isinstance(r, dict) or r.get("target") not in ("hauler", "selector")
            or not isinstance(r.get("instruction"), str)
            or not 0 < len(r["instruction"].strip()) <= 500):
            raise ValueError("invalid Reviewer rule")
        scope_of(r.get("scope", "project"))
    candidates = reply.get("repair_candidates", [])
    if not isinstance(candidates, list) or len(candidates) > 20:
        raise ValueError("Reviewer repairs must be a list of at most 20")
    hauler.validate_sources(svc, candidates, row["payload"]["unit_id"])
    return {"diagnosis": reply["diagnosis"], "rules": rules,
            "rule_reviews": rule_reviews, "repair_candidates": candidates}
