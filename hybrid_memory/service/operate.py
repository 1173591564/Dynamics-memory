"""agent 操作面（P5 从 service.py 原样迁入）：propose/resolve/diagnose/report_miss。

validate_proposal/durable_propose 为 §2.7 具名函数；_cited_text/_task_once
是本模块内 helper。VERDICTS 公开给 transport/http（路由预检）。
效果提交走 dispatch.effects.effect_transaction（I5 唯一入口）。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import replace

from ..core.types import Event
from ..dispatch import effects
from ..errors import ProposalRejected
from ..guards.grounding import content_grounded as _content_grounded
from ..guards.redact import redact_secrets
from ..legacy.prompt import parse_ids, parse_salience
from ..logstore import entities_in
from ..semantics import normalize
from .context import _ORIGINS, CausalViolation, InvestigationContext

# 自指：记忆系统自身的操作过程不是项目事实（candgen prompt 已禁，
# 这里是操作面的第二道闸）
_SELF_REF_RE = re.compile(
    r"(?:memory_(?:search|propose|resolve|diagnose|conflicts)|"
    r"log_(?:search|timeline|stats|window)|relevant-memories|"
    r"(?:我|已|刚|调查员|系统)(?:已经)?(?:检索|查询|查阅|回展|裁决|合并|归档|提议|"
    r"调查)了?(?:一下|一遍|相关)?(?:记忆|日志|冲突)|"
    r"(?:记忆|日志)(?:里|中)(?:没有|未)(?:找到|查到|记录)|"
    r"(?:signal_id|recall_miss|extract_due))", re.IGNORECASE)
_MAX_PROPOSAL_CHARS = 1200
VERDICTS = {"synonym", "update", "contradiction", "collision", "pending"}
_MISS_SOURCES = {"recognizer_none", "correction", "agent_tool", "thin",
                 "external"}


def _cited_text(svc, unit_ids) -> str:
    parts = []
    for uid in unit_ids:
        row = svc.log.get(uid)
        if row is None:
            continue
        parts.append(row["user_text"])
        parts.append(row["assistant_text"])
    return "\n".join(parts)


def validate_proposal(svc, p: dict, before: int | None) -> tuple[Event, list[int]]:
    text = p.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ProposalRejected("empty_text")
    text = redact_secrets(text.strip())
    if len(text) > _MAX_PROPOSAL_CHARS:
        raise ProposalRejected(f"too_long>{_MAX_PROPOSAL_CHARS}")
    if _SELF_REF_RE.search(text):
        raise ProposalRejected("self_reference")
    src_raw = p.get("source_unit_ids") or p.get("src") or []
    src = parse_ids(src_raw)
    if not src:
        raise ProposalRejected("no_source")
    known = svc.log.exists(src, before=before)
    bad = sorted(set(src) - set(known))
    if bad:
        raise ProposalRejected(f"unknown_or_future_source:{bad}")
    if not _content_grounded(text, _cited_text(svc, src)):
        raise ProposalRejected("ungrounded_content")
    ek = p.get("entity_key")
    sup = p.get("supersedes")
    if sup is None:
        sup = []
    if not isinstance(sup, list):
        raise ProposalRejected("supersedes_must_be_list")
    sup = parse_ids(sup)
    ev = Event(svc.semantics.fingerprint(normalize(text)), normalize(text),
               text, tuple(sorted(set(src))),
               salience=parse_salience(p.get("salience")),
               kind="fact", scene=svc._scene,
               entity=(ek.strip()[:120] if isinstance(ek, str) else ""))
    return ev, sup


def _task_once(svc, ctx, request, mutate):
    """调用方持服务锁；操作、checkpoint、回执同事务。"""
    with svc._rollback_effect():
        out, next_revision, replayed = svc.tasks.apply_operation(
            ctx.task_id, ctx.lease_token, request, mutate,
            svc._dump_state, svc._checkpoint_revision)
        svc._checkpoint_revision = next_revision
        return dict(out, replayed=replayed)


def durable_propose(svc, proposals, ctx):
    accepted, ids, rejected, replayed, applied = 0, [], [], 0, 0
    plain = replace(ctx, task_id=None, lease_token=None)
    for i, proposal in enumerate(proposals):
        # 用实际 ingest 字段规整签名，消除 HTTP 与最终 JSON 的默认值差异。
        # supersedes 的因果检查留在 receipt 查询之后：成功更新后的旧链可能
        # 已指向本任务刚创建的新条目，不能把合法重放误判成未来访问。
        try:
            ev, sup = validate_proposal(svc, proposal, ctx.before)
            canonical = {"text": ev.text, "src": list(ev.src), "salience": ev.salience,
                         "entity_key": ev.entity, "supersedes": sorted(set(sup))}
        except (ProposalRejected, AttributeError):
            canonical = proposal
        out = _task_once(svc, ctx, {"action": "propose", "proposal": canonical},
                         lambda: propose(svc, [proposal], _context=plain))
        accepted += out["accepted"]
        ids.extend(out["new_ids"])
        replayed += int(out["replayed"])
        applied += out["accepted"] if not out["replayed"] else 0
        rejected.extend(dict(r, index=i) for r in out["rejected"])
    return {"accepted": accepted, "new_ids": ids, "merged": accepted - len(ids),
            "rejected": rejected, "replayed": replayed, "applied": applied, "origin": ctx.origin,
            "pool": svc.engine.pool_sizes(), "t": svc._t}


def report_miss(svc, query: str, hint: str = "",
                source: str = "agent_tool") -> dict:
    if source not in _MISS_SOURCES:
        source = "external"
    with svc._lock:
        svc._ensure_healthy()
        svc.engine.report_miss(query, svc._t, hint=hint[:300],
                               source=source,
                               entities=tuple(e for e, _ in entities_in(query)))
        svc.n_missed += 1
        n = sum(svc.tasks.queued_counts().values()) + len(svc.engine.signals)
    svc._kick()
    return {"queued": n, "t": svc._t}


def resolve(svc, left: int, right: int, verdict: str,
            entity_key: str = "", ensure_tension: bool = False, *,
            signal_id: str | None = None,
            _context: InvestigationContext | None = None,
            _checkpoint: bool = True) -> dict:
    """裁决回报。ensure_tension=True（调查员/主 agent 主动裁决两条此前
    没被判为张力的记忆）时先登记 tension 再消解；entity_key 回填到双方。"""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
    with svc._lock:
        ctx = _context if _context is not None else svc._admit(signal_id)[0]
        if ctx.task_id is not None:
            request = {"action": "resolve", "pair": sorted((left, right)),
                       "verdict": verdict, "entity_key": entity_key[:120],
                       "ensure_tension": ensure_tension}
            return _task_once(svc, ctx, request, lambda: resolve(
                svc, left, right, verdict, entity_key, ensure_tension,
                _context=replace(ctx, task_id=None, lease_token=None),
                _checkpoint=False))
        if ctx.before is not None:
            eligible = svc._causal_memory_ids(ctx.before)
            if left not in eligible or right not in eligible:
                raise CausalViolation("unknown_or_future_memory")
        a, b = svc.engine.mems.get(left), svc.engine.mems.get(right)

        def mutate():
            if ensure_tension and a is not None and b is not None:
                svc.engine.add_tension(left, right, svc._t)
            if entity_key:
                for m in (a, b):
                    if m is not None and not m.entity:
                        m.entity = entity_key[:120]
            n = svc.engine.submit_verdicts([(left, right, verdict)], svc._t)
            return {"resolved": n, "t": svc._t}
        # 任务回执事务已经包住这次调用；再开事务会嵌套 BEGIN。
        if _checkpoint:
            return effects.effect_transaction(svc, mutate)
        return mutate()


def propose(svc, proposals: list, *, origin: str = "agent",
            signal_id: str | None = None, before: int | None = None,
            _context: InvestigationContext | None = None) -> dict:
    """agent 提议入库。逐条校验（溯源非空且存在、因果、脱敏、自指、长度），
    通过的走引擎同一条 ingest 回路；supersedes 经 update 裁决把旧条目
    取代。返回逐条结果。"""
    if not isinstance(proposals, list):
        raise ValueError("proposals must be a list")
    if len(proposals) > 50:
        raise ValueError("proposal batch exceeds limit 50; no items applied")
    accepted, new_ids, rejected = 0, [], []
    with svc._lock:
        ctx = (_context if _context is not None
               else svc._admit(signal_id, before)[0])
        if ctx.task_id is not None:
            return durable_propose(svc, proposals, ctx)
        bound = ctx.before
        if ctx.signal_id is not None:
            origin = ctx.origin
        if origin not in _ORIGINS:
            origin = "agent"
        t = svc._t
        for i, p in enumerate(proposals):
            if not isinstance(p, dict):
                rejected.append({"index": i, "reason": "not_an_object"})
                continue
            try:
                ev, sup = validate_proposal(svc, p, bound)
                if bound is not None and sup:
                    eligible = svc._causal_memory_ids(bound)
                    if any(mid not in eligible for mid in sup):
                        raise ProposalRejected("unknown_or_future_supersedes")
            except ProposalRejected as exc:
                rejected.append({"index": i, "reason": str(exc)})
                svc.n_rejected += 1
                continue
            ev.origin = origin
            ids = svc.engine.propose([ev], t)
            accepted += 1
            svc.n_proposals += 1
            new_ids.extend(ids)
            if ids and sup:
                new = ids[-1]
                for old in sup:
                    if old in svc.engine.mems and old != new:
                        svc.engine.add_tension(new, old, t)
                        svc.engine.submit_verdicts([(new, old, "update")], t)
        pool = svc.engine.pool_sizes()
    return {"accepted": accepted, "new_ids": new_ids,
            "merged": accepted - len(new_ids), "rejected": rejected,
            "origin": origin, "pool": pool, "t": t}


def diagnose(svc, miss_type: str, note: str = "", *,
             signal_id: str | None = None, kind: str = "",
             usage: dict | None = None,
             _context: InvestigationContext | None = None, _audit=True) -> dict:
    from ..legacy.investigator import MISS_TYPES
    if miss_type not in MISS_TYPES:
        raise ValueError(f"miss_type must be one of {MISS_TYPES}")
    with svc._lock:
        ctx = _context if _context is not None else svc._admit(signal_id)[0]
        if ctx.task_id is not None:
            return _task_once(svc, ctx, {"action": "diagnose", "miss_type": miss_type,
                                         "note": (note or "").strip()[:500]},
                              lambda: diagnose(svc, miss_type, note, kind=kind, usage=usage,
                                               _context=replace(ctx, task_id=None, lease_token=None),
                                               _audit=False))
        signal_id = ctx.signal_id
        svc.miss_counts[miss_type] = svc.miss_counts.get(miss_type, 0) + 1
        counts = dict(svc.miss_counts)
    if _audit and svc.state_path is not None:
        rec = {"ts": round(time.time(), 1), "t": svc._t,
               "signal_id": signal_id, "kind": kind,
               "miss_type": miss_type, "note": (note or "")[:500],
               "usage": usage or {}}
        try:
            with open(svc.state_path.parent / "diagnoses.jsonl", "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return {"miss_counts": counts}
