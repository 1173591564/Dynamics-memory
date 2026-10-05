"""Selector 校验（P6 从 agent/trio.py 拆出）：决定形状 + 目标门（应用前预检）。

预检只读：同事务内前序决定造成的状态漂移，由 applier 在写入时逐条复核；
任一失败整笔回滚——对外行为（异常类型/文案/重试）与预检无关。
UPDATE 门（未确认降 CONFLICT）不抛错，只活在 applier 内。
"""
from __future__ import annotations

from typing import TypedDict

from ..core import triggers
from . import hauler


class Decision(TypedDict, total=False):
    candidate_index: int
    action: str
    target_id: int
    verified_correction: bool
    reason: str
    requested_action: str
    proof_unit_id: int
    change_kind: str
    related_target_ids: list[int]
    equivalent_ids: list[int]


def authorized_change(svc, row, ev, old):
    anchor = svc.log.get(row["payload"]["unit_id"])
    previous = svc.log.get(old.claim_unit) if old.claim_unit is not None else None
    threshold = (previous["t"], old.claim_unit) if previous else (old.birth - 1, -1)
    threshold = max(threshold, getattr(old, "reviewed_after", None) or (-1, -1))
    proofs = []
    for uid in ev.src:
        source = svc.log.get(uid)
        if source is None or anchor is None or source["t"] > anchor["t"]:
            continue
        claims = [c for c in triggers.claims_in(source["user_text"], authoritative=True)
                  if c["key"] == ev.claim_key]
        if len({(c["value"], c["mode"] == "retract") for c in claims}) > 1:
            continue
        for claim in claims:
            if claim["mode"] == "retract":
                matches = ev.claim_mode == "retract" and claim["value"] in ("", old.claim_value)
            else:
                matches = (ev.claim_mode != "retract" and claim["value"] == ev.claim_value
                           and claim["mode"] in ("set", "change", "correction")
                           and claim["old_value"] in ("", old.claim_value))
            if matches and (source["t"], uid) > threshold:
                proofs.append((source["t"], uid))
    return max(proofs)[1] if proofs else None


def normalize_claim(svc, row, ev, decision):
    d = {k: v for k, v in decision.items()
         if k in Decision.__annotations__ and k not in (
             "requested_action", "proof_unit_id", "change_kind", "related_target_ids", "equivalent_ids")}
    d["requested_action"] = d["action"]
    if not ev.claim_key or d["action"] == "REJECT":
        target = svc.engine.mems.get(d.get("target_id"))
        if not ev.claim_key and d["action"] == "UPDATE" and target is not None and target.claim_key:
            return dict(d, action="CONFLICT", reason="known claim update requires source-grounded identity")
        return d
    current = [m for m in svc.engine.mems.values()
               if m.superseded_by is None and m.aggregated_into is None
               and m.withdrawn_at is None and m.claim_key == ev.claim_key]
    old = max(current, key=lambda m: (m.v, -m.id)) if current else None
    target = svc.engine.mems.get(d.get("target_id"))
    if target is not None and target.claim_key and target.claim_key != ev.claim_key:
        raise ValueError("Selector target belongs to a different claim scope")
    if old is None:
        if ev.claim_mode == "retract":
            return dict(d, action="REJECT", reason="no current version to retract")
        retired = [m for m in svc.engine.mems.values() if m.claim_key == ev.claim_key
                   and (m.withdrawn_at is not None or m.superseded_by is not None or m.aggregated_into is not None)]
        if retired:
            cutoff = max(m.withdrawn_at if m.withdrawn_at is not None else m.archived_at or m.birth for m in retired)
            fresh = any(source["t"] >= cutoff and any(
                claim["key"] == ev.claim_key and claim["value"] == ev.claim_value
                and claim["mode"] in ("set", "change", "correction")
                for claim in triggers.claims_in(source["user_text"], authoritative=True))
                for uid in ev.src if (source := svc.log.get(uid)) is not None)
            if not fresh:
                return dict(d, action="REJECT", reason="retired claim requires fresh user authorization")
        return d
    d["target_id"] = old.id
    if ev.claim_mode != "retract" and all(m.claim_value == ev.claim_value for m in current):
        if len(current) > 1 and not any(m.pending_review for m in current):
            d["equivalent_ids"] = [m.id for m in current if m.id != old.id]
        return dict(d, action="EXIST")
    if len(current) > 1:
        d["related_target_ids"] = sorted(m.id for m in current)
    previous = svc.log.get(old.claim_unit) if old.claim_unit is not None else None
    proofs = [authorized_change(svc, row, ev, memory) for memory in current]
    proof = proofs[0]
    if all(p is not None for p in proofs) and not any(m.pending_review for m in current):
        return dict(d, action="UPDATE", verified_correction=True,
                    proof_unit_id=proof, change_kind="retract" if ev.claim_mode == "retract" else "replace")
    if (ev.claim_mode != "retract" and ev.claim_unit is not None and previous is not None
            and (source := svc.log.get(ev.claim_unit)) is not None
            and (source["t"], ev.claim_unit) <= (previous["t"], old.claim_unit)):
        return dict(d, action="REJECT", reason="historical value cannot become a current version")
    return dict(d, action="CONFLICT", reason="human freeze or insufficient user authorization")


def validate(reply, row, svc) -> list[Decision]:
    """预检每候选恰一合法决定 + 目标存在且未退役；返回决定列表。"""
    decisions = reply.get("decisions")
    candidates = row["payload"]["candidates"]
    if (not isinstance(decisions, list) or len(decisions) != len(candidates)
            or any(not isinstance(d, dict) or type(d.get("candidate_index")) is not int for d in decisions)
            or sorted(d["candidate_index"] for d in decisions)
            != list(range(len(candidates)))):
        raise ValueError("Selector must return exactly one decision per candidate")
    uid = row["payload"]["unit_id"]
    sealed_window = hauler.sealed_window(svc, row)
    normalized = []
    for d in decisions:
        idx, action = d["candidate_index"], d.get("action")
        c = candidates[idx]
        if action not in {"CREATE", "EXIST", "UPDATE", "CONFLICT", "REJECT"}:
            raise ValueError("invalid Selector action")
        if action == "REJECT":
            normalized.append({"candidate_index": idx, "action": "REJECT", "requested_action": action})
            continue
        # The selector cannot widen a source boundary established by its parent.
        hauler.validate_sources(svc, [c], uid, sealed=sealed_window)
        # Treat even model-produced recommendations as untrusted input.
        ev, _ = svc._validate_proposal(c, None)
        ev.origin = "agent"
        target = d.get("target_id")
        old = svc.engine.mems.get(target) if type(target) is int and type(target) is not bool else None
        # Exact re-extraction from overlapping windows cannot yield a second
        # identical memory even when the model misclassifies it as CREATE.
        if action == "CREATE":
            same = next((m for m in svc.engine.mems.values()
                         if m.superseded_by is None and m.aggregated_into is None
                         and m.withdrawn_at is None and m.text == ev.text), None)
            if same is not None:
                action, old = "EXIST", same
        if action != "CREATE" and (old is None or old.superseded_by is not None
                                   or old.aggregated_into is not None or old.withdrawn_at is not None):
            raise ValueError("Selector target is retired or unknown")
        normalized.append(normalize_claim(svc, row, ev, d))
    return normalized
