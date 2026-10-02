"""观察回路（P4 从 server.py 原样迁入）：observe/待办扫描/单单元交付。

先落 L0 幂等，再扫描，再三 agent 交接；legacy 才走 candgen。
_annotate_observe 是 observe 内用的回执整形（非 §2.7 具名函数）。
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict

from ..core import triggers
from ..core.interaction import InteractionUnit, InteractionWindow
from ..core.types import Event
from ..guards.bounds import capture_fingerprint as _capture_fingerprint
from ..guards.bounds import validate_request_id as _validate_request_id
from ..guards.grounding import content_grounded as _content_grounded
from ..logstore import entities_in
from ..semantics import normalize
from ..store.tasks import (SEMANTIC_KINDS, WORKFLOW_KINDS, CheckpointConflict,
                           TaskQueueFull, encode)


def _annotate_observe(body: dict, unit_id: int, *, replayed: bool,
                      request_id: str | None) -> dict:
    out = {k: v for k, v in body.items() if k != "next_memory_id"}
    out["accepted"] = True
    out["unit_id"] = unit_id
    if replayed:
        out["replayed"] = True
    if request_id:
        out["request_id"] = request_id
    return out


def observe(svc, user_text: str, assistant_text: str,
            request_id: str | None = None) -> dict:
    request_id = _validate_request_id(request_id)
    fingerprint = _capture_fingerprint(
        {"user_text": user_text, "assistant_text": assistant_text})
    with svc._lock:
        svc._ensure_healthy()
        prev = svc._last_turn
        context = {}
        if triggers.is_dissatisfaction(user_text) and prev:
            ret = svc._retrievals.get(prev.get("retrieval_id", -1))
            context = {"previous_user": prev["user"],
                       "retrieved": [{"id": m.id, "t": m.birth, "text": m.text}
                                     for m in (ret.selected if ret else [])]}
        scene = svc._scene
        idx = svc.log.append_unit(
            svc._t, min_unit_id=svc._unit_id, user_text=user_text,
            assistant_text=assistant_text, scene=scene, work_context=context,
            capture_id=request_id, capture_fingerprint=fingerprint)
        uid, t = idx["unit_id"], idx["t"]
        replayed = bool(idx.get("replayed"))
        # 重放不得推进时钟或覆盖更新一轮的 last_turn。
        if not replayed:
            svc._unit_id, svc._t = uid + 1, t
            svc._last_turn = {"user": user_text, "retrieval_id": None}
    # 新单元已与 L0 待办同事务接受；即使其他处理器忙，也不会消失。
    svc._unit_wake.set()
    try:
        completed = svc.process_pending_units()
    except (TaskQueueFull, CheckpointConflict) as exc:
        # L0 已提交。保留原异常类型，让直接调用方的既有 except 仍能匹配，
        # HTTP 层据此附上 accepted/unit_id，避免客户端换成新请求再投一条。
        exc.accepted = True
        exc.unit_id = uid
        exc.request_id = request_id
        raise
    if uid in completed:
        body = completed[uid]
    elif (receipt := svc.tasks.unit_receipt(uid)) is not None:
        body = receipt
    else:
        with svc._lock:
            body = {"unit_id": uid, "pending": True, "candidates": 0,
                    "scene": scene, "reasons": [],
                    "pool": svc.engine.pool_sizes(), "t": svc._t, "worker": {}}
    return _annotate_observe(body, uid, replayed=replayed, request_id=request_id)


def process_pending_units(svc, limit: int = 8) -> dict[int, dict]:
    """按原 L0 顺序处理；同服务仅一个处理器。不得越过退避中的旧单元。"""
    if not svc._unit_busy.acquire(blocking=False):
        return {}
    completed = {}
    try:
        with svc._lock:
            svc._ensure_healthy()
        for uid in svc.log.pending_units(limit):
            work = svc.log.work(uid)
            if work["next_run_at"] > time.time() and svc.tasks.unit_receipt(uid) is None:
                break
            try:
                completed[uid] = process_unit(svc, uid, work)
            except Exception as exc:
                svc.log.fail_work(uid, exc)
                raise
    finally:
        svc._unit_busy.release()
    return completed


def process_unit(svc, uid: int, work: dict) -> dict:
    ctx = svc.log.unit_context(uid)
    unit = ctx["unit"]
    t = unit["t"]
    if work["result"] is None and svc.tasks.unit_receipt(uid) is None:
        reasons = triggers.scan_unit(unit["user_text"], unit["assistant_text"],
                                     ctx["new_entities"])
        u = InteractionUnit(uid, t, t, unit["user_text"], unit["assistant_text"],
                            unit["assistant_turns"])
        window = InteractionWindow(uid, uid, uid, t, t, (u,))
        try:
            if svc.trio_mode:
                cands, scene, failure = [], unit["scene"], ""
            else:
                gen = svc.generator.generate(window, unit["scene"])
                cands, scene, failure = [asdict(c) for c in gen.candidates], gen.scene_name, ""
        except Exception as exc:  # noqa: BLE001  可恢复补抽，而非伪装合法空候选
            cands, scene = [], ""
            failure = f"{type(exc).__name__}: {exc}"[:500]
            reasons = list(dict.fromkeys([*reasons, "candgen_failed"]))
            print(f"[memory-sidecar] candgen 失败（unit {uid}，已留 L0，交调查员补抽）: "
                  f"{failure}", file=sys.stderr, flush=True)
        svc.log.save_work_result(uid, encode({"candidates": cands, "scene": scene,
                                               "reasons": reasons, "failure": failure}))
        work = svc.log.work(uid)
    result = json.loads(work["result"]) if work["result"] is not None else None
    handoffs = []
    with svc._lock:
        svc._ensure_healthy()
        with svc._rollback_effect():
            old_emit = svc.engine.signals.on_emit

            def collect(kind, payload, at, key, merge):
                if kind in SEMANTIC_KINDS | WORKFLOW_KINDS or kind in ("recall_miss", "extract_due"):
                    handoffs.append((kind, svc._signal_payload(kind, payload), at, key, merge))
                    return -1  # 同任务库事务交接，不进易失队列
                return old_emit(kind, payload, at, key, merge)

            def mutate():
                svc._unit_id = max(svc._unit_id, uid + 1)
                svc._t = max(svc._t, t)
                # 每个单元只在一次 checkpoint 中落地；不让旧单元覆盖较新场景。
                scene = (result["scene"] or svc._scene) if result else svc._scene
                if t >= svc._scene_t:
                    svc._scene, svc._scene_t = scene, t
                previous = work["context"].get("previous_user") or ctx["previous_user"]
                if not svc.trio_mode and triggers.is_correction(unit["user_text"]) and previous:
                    svc.engine.report_miss(
                        previous, t, hint=unit["user_text"][:300], source="correction",
                        retrieved=work["context"].get("retrieved", []),
                        entities=tuple(e for e, _ in entities_in(previous)))
                    svc.n_missed += 1
                reasons = result["reasons"] if result else []
                if svc.trio_mode:
                    svc.engine.signals.emit("hauler_due", {"unit_id": uid}, t,
                                             key=f"hauler:{uid}")
                    if triggers.is_dissatisfaction(unit["user_text"]):
                        svc.engine.signals.emit("reviewer_due", {"unit_id": uid}, t,
                                                 key=f"reviewer:{uid}")
                elif reasons:
                    svc.engine.report_unit(uid, t, scene=svc._scene,
                                            reasons=tuple(reasons),
                                            entities=tuple(ctx["entities"][:12]))
                blob = f"{unit['user_text']}\n{unit['assistant_text']}"
                grounded = []
                for cand in (result["candidates"] if result else []):
                    if _content_grounded(cand.get("text", ""), blob):
                        grounded.append(cand)
                    else:
                        svc.n_ungrounded += 1
                evs = [Event(svc.semantics.fingerprint(normalize(c["text"])),
                             normalize(c["text"]), c["text"], (uid,),
                             salience=c["salience"], scene=svc._scene)
                       for c in grounded]
                if evs:
                    svc.engine.observe(evs, t)
                svc.engine.step(t)
                svc._t = max(svc._t, t + 1)
                if result and result["failure"]:
                    svc.n_candgen_fail += 1
                return {"unit_id": uid, "candidates": len(evs),
                        "scene": svc._scene, "reasons": list(reasons),
                        "pool": svc.engine.pool_sizes(), "t": svc._t,
                        "next_memory_id": svc.engine._next_id}

            svc.engine.signals.on_emit = collect
            try:
                response, revision, replayed = svc.tasks.apply_unit(
                    uid, mutate, svc._dump_state, handoffs, svc._checkpoint_revision)
                svc._checkpoint_revision = revision
            finally:
                svc.engine.signals.on_emit = old_emit
    # 回执先于跨库确认；确认失败则仍是 pending，重试只读回执。
    svc.log.finish_work(uid)
    if replayed:
        return {k: v for k, v in response.items() if k != "next_memory_id"} | {"worker": {}}
    wstats = svc.process_semantic_tasks()
    svc._kick()
    return {k: v for k, v in response.items() if k != "next_memory_id"} | {"worker": wstats}
