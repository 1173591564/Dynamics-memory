"""人工复核队列（P4 从 server.py 原样迁入）：token/列表/裁决。"""
from __future__ import annotations

import json
import os
import secrets

from ..core.types import Pool
from ..dispatch.effects import close_retired_relations, enforce_capacity, protected_ids, review_stamp


def review_token(svc) -> str:
    """Separate capability: ordinary plugin and agent bearer cannot approve conflicts."""
    if not svc.state_path:
        return secrets.token_hex(24)
    p = svc.state_path.parent / ".human-review-token"
    if not p.exists():
        p.write_text(secrets.token_hex(24), encoding="utf-8")
        os.chmod(p, 0o600)
    token = p.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("human-review-token is empty")
    return token


def human_reviews(svc) -> list[dict]:
    # The reviewer must see both sides and their provenance before choosing.
    with svc._lock:
        reviews = svc.tasks.pending_reviews()
        for review in reviews:
            old = svc.engine.mems.get(review["target_id"])
            review["existing"] = ({"text": old.text, "source_unit_ids": sorted(old.src),
                                       "pool": old.pool.value} if old else None)
        return reviews


def decide_human_review(svc, review_id: int, decision: str, capability: str) -> dict:
    """An explicitly authenticated human decision, effect and receipt in one DB commit."""
    if not secrets.compare_digest(capability, svc.human_review_token):
        raise PermissionError("human review capability required")
    if decision not in ("accept_new", "keep_old"):
        raise ValueError("decision must be accept_new or keep_old")
    with svc._lock, svc._rollback_effect():
        with svc.tasks.transaction() as conn:
            row = conn.execute("SELECT * FROM human_reviews WHERE id=?", (review_id,)).fetchone()
            if row is None:
                raise ValueError("review not found")
            if row["status"] != "pending":
                if row["decision"] != decision:
                    raise ValueError("conflicting review decision")
                return {"review_id": review_id, "decision": decision, "replayed": True}
            old = svc.engine.mems.get(row["target_id"])
            if (old is None or old.superseded_by is not None or old.aggregated_into is not None
                    or old.withdrawn_at is not None or (row["target_stamp"]
                        and json.loads(row["target_stamp"]) != review_stamp(old))):
                raise ValueError("review target changed; submit a fresh review")
            proposal = json.loads(row["candidate"])
            peers = [old]
            for reference in proposal.get("_related_targets", []) if row["review_key"] else []:
                member = svc.engine.mems.get(reference["id"])
                if (member is None or review_stamp(member) != reference["stamp"]
                        or (old.claim_key and member.claim_key != old.claim_key)):
                    raise ValueError("related review target changed; submit a fresh review")
                peers.append(member)
            ids, selected = [], old
            if decision == "accept_new" or old.agg_members:
                if decision == "keep_old":
                    member = min((svc.engine.mems[i] for i in old.agg_members), key=lambda m: (m.birth, m.id))
                    proposal = {"text": member.text, "source_unit_ids": sorted(member.src)}
                ev, _ = svc._validate_proposal(proposal, None)
                if old.claim_key and ev.claim_key and old.claim_key != ev.claim_key:
                    raise ValueError("review candidate belongs to a different claim scope")
                ev.origin = "user_confirmed"
                selected = next((m for m in peers if m.text == ev.text or
                                 (ev.claim_key and m.claim_key == ev.claim_key and m.claim_value == ev.claim_value)), None)
                if ev.claim_mode == "retract":
                    selected = None
                    for member in peers:
                        member.withdrawn_at = member.archived_at = svc._t
                        member.pool = Pool.ARCHIVE
                        member.src |= frozenset(ev.src)
                elif selected is None:
                    ids = svc.engine.propose([ev], svc._t)
                    if not ids:
                        raise ValueError("accepted candidate did not create a distinct version")
                    selected = svc.engine.mems[ids[-1]]
                if selected is not None:
                    added = set(ev.src) - set(selected.src)
                    selected.src |= frozenset(ev.src)
                    selected.evid += len(added)
            if selected is not None:
                selected.reviewed_after = (svc._t, svc._unit_id - 1)
                for member in peers:
                    if member.id != selected.id:
                        member.superseded_by = selected.id
                        member.archived_at = svc._t
                        member.pool = Pool.ARCHIVE
                        svc.engine.n_merge += 1
            if decision == "accept_new":
                # Other proposals against this now-retired version must be
                # reconsidered against the new version, never left actionable.
                conn.execute("UPDATE human_reviews SET status='stale' WHERE target_id=? "
                             "AND id<>? AND status='pending'", (old.id, review_id))
            remaining = conn.execute("SELECT COUNT(*) FROM human_reviews WHERE target_id=? "
                "AND id<>? AND status='pending'", (old.id, review_id)).fetchone()[0]
            old.pending_review = bool(remaining)
            conn.execute("UPDATE human_reviews SET status='done',decision=? WHERE id=?",
                         (decision, review_id))
            # 人审新增（accept_new）与其他新增一样在 commit 前收口（N17）；
            # 全 pin 时拒绝并回滚，不静默超限。
            close_retired_relations(svc, conn)
            if selected is not None:
                selected.pending_review = bool(conn.execute("SELECT 1 FROM human_reviews WHERE target_id=? "
                                                           "AND status='pending' LIMIT 1", (selected.id,)).fetchone())
                if decision == "accept_new" and selected.pool is Pool.ARCHIVE:
                    selected.pool = Pool.CANDIDATE
            enforce_capacity(svc, fresh=ids)
            revision = svc.tasks._write_checkpoint(conn, svc._dump_state(), svc._checkpoint_revision)
        svc._checkpoint_revision = revision
        return {"review_id": review_id, "decision": decision, "new_ids": ids,
                "selected_id": selected.id if selected is not None else None}


_MAX_LEDGER_CONFLICTS = 200    # 冲突行输出上界（超出标 truncated，不静默截断）
_MAX_LEDGER_REVIEWS = 512      # 待审行输出上界（对齐 pending 人审 ≤512 的不变量）
_MAX_LEDGER_AGGREGATES = 200   # 聚合容器+成员输出上界


def conflict_ledger(svc, before: int | None = None) -> dict:
    """冲突统一读模型（N14/N20）：只读汇总 conflicts/tensions/pending_reviews/
    aggregates/pin_roots/truncated，不触发裁决或人审。

    - aggregates＝待裁决聚合容器（pending_review 且 agg_members）及其成员，
      不是 kind=="reflection"；
    - 各列表有界，超界置 truncated=True（不静默截断、不隐藏 stale）；
    - 正文片段 ≤200 字符，不泄超界正文。
    """
    with svc._lock:
        tensions = [
            (left, right) for left, right in svc.engine.tensions
            if before is None or (left < before and right < before)
        ]
        tension_rows = [svc.engine.tensions[t] for t in tensions]
        conflicts, truncated = [], False
        for (left, right), tension in zip(tensions, tension_rows):
            lm = svc.engine.mems.get(left)
            rm = svc.engine.mems.get(right)
            conflicts.append({
                "left": left, "right": right,
                "left_text": (lm.text[:200] if lm else ""),
                "right_text": (rm.text[:200] if rm else ""),
                "first_seen": tension.first_seen,
                "observations": tension.observations,
                "stale": lm is None or rm is None,
            })
            if len(conflicts) >= _MAX_LEDGER_CONFLICTS:
                truncated = len(tensions) > _MAX_LEDGER_CONFLICTS
                break
        if len(tensions) > _MAX_LEDGER_CONFLICTS:
            truncated = True

        reviews, review_rows = [], []
        for r in svc.tasks.pending_reviews():
            old = svc.engine.mems.get(r["target_id"])
            review_rows.append({
                "id": r["id"],
                "target_id": r["target_id"],
                "candidate": r["candidate"],
                "reason": r["reason"],
                "stale": old is None or old.superseded_by is not None or old.aggregated_into is not None
                         or old.withdrawn_at is not None,
            })
            if len(review_rows) >= _MAX_LEDGER_REVIEWS:
                truncated = True
                break
        reviews = review_rows

        agg_ids: set[int] = set()
        for m in svc.engine.mems.values():
            if m.pending_review and m.agg_members:
                agg_ids.add(m.id)
                agg_ids.update(m.agg_members)
        aggregates = sorted(agg_ids)
        if len(aggregates) > _MAX_LEDGER_AGGREGATES:
            aggregates = aggregates[:_MAX_LEDGER_AGGREGATES]
            truncated = True

        pin_roots = sorted(protected_ids(svc))
        return {
            "conflicts": conflicts,
            "tensions": tensions,
            "pending_reviews": reviews,
            "aggregates": aggregates,
            "pin_roots": pin_roots,
            "truncated": truncated,
        }
