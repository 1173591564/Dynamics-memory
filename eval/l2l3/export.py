"""跑链结束后的只读导出：在已完成的项目目录上原位重开服务（recover_or_init
从 durable checkpoint 恢复最新状态），倾倒 L0 单元、引擎记忆、任务回执
（含 Selector 裁决）、张力与人审队列，供抽检与结算。不写任何状态。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_setup(repo: str) -> None:
    repo = str(Path(repo).resolve())
    if repo not in sys.path:
        sys.path.insert(0, repo)


def _served_text(resp: dict) -> str:
    """/recall 返回体 → 判分用纯文本上下文（TIDE score_context 的输入）。"""
    if not isinstance(resp, dict):
        return str(resp or "")
    for key in ("texts", "context", "blocks", "lines"):
        v = resp.get(key)
        if isinstance(v, list):
            return "\n".join(str(x) for x in v)
        if isinstance(v, str) and v.strip():
            return v
    return json.dumps(resp, ensure_ascii=False)


def _mem_row(m) -> dict:
    return {"id": m.id, "belief_id": m.belief_id, "value": m.value,
            "text": m.text, "pool": getattr(m.pool, "name", str(m.pool)),
            "v": round(float(m.v), 4), "birth": m.birth,
            "last_seen": m.last_seen, "src": list(m.src),
            "kind": m.kind, "derived_from": list(m.derived_from or ()),
            "scene": m.scene, "origin": m.origin,
            "pending_review": bool(m.pending_review),
            "superseded_by": m.superseded_by,
            "aggregated_into": m.aggregated_into,
            "evid": getattr(m, "evid", None),
            "agg_members": list(getattr(m, "agg_members", ()) or ())}


def _task_row(row) -> dict:
    r = row if isinstance(row, dict) else dict(row)
    out = {"id": r.get("id"), "kind": r.get("kind"), "state": r.get("state"),
           "retries": r.get("retries")}
    # selector 裁决对齐需要候选文本（decisions 按 candidate_index 引用本任务
    # 候选）；payload 本体含封存上下文不倾倒，只取候选文本（2026-10-04）。
    if r.get("kind") == "selector_due":
        pl = r.get("payload")
        if isinstance(pl, str):
            try:
                pl = json.loads(pl)
            except ValueError:
                pl = None
        if isinstance(pl, dict) and isinstance(pl.get("candidates"), list):
            out["payload_candidates"] = [c.get("text", "")
                                         for c in pl["candidates"]
                                         if isinstance(c, dict)]
    result = r.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = None
    if isinstance(result, dict):
        # 只保留裁决与诊断相关字段，避免倾倒整段封存上下文
        keep = {}
        for k in ("decisions", "candidates", "diagnosis", "rules",
                  "repair_candidates", "rule_reviews", "usage", "verdicts",
                  "action", "accepted", "new_ids", "replayed"):
            if k in result:
                keep[k] = result[k]
        out["result"] = keep
    else:
        out["result"] = None
    return out


def export_run(repo: str, project: str, out_path: str) -> dict:
    _repo_setup(repo)
    from hybrid_memory.transport.bootstrap import build_default_service

    svc = build_default_service(project)
    dump: dict = {"project": str(project)}
    try:
        n = svc.log.count()
        units = []
        for uid in range(n):
            row = svc.log.get(uid)
            if row is None:
                continue
            units.append({"unit_id": uid, "t": row["t"],
                          "user_text": row["user_text"],
                          "assistant_text": row["assistant_text"]})
        dump["units"] = units
        dump["mems"] = [_mem_row(m) for m in svc.engine.mems.values()]
        dump["tensions"] = [list(pair) for pair in svc.engine.tensions]
        try:
            dump["human_reviews"] = svc.human_reviews()
        except Exception as exc:  # noqa: BLE001  导出尽力而为，字段标注失败
            dump["human_reviews"] = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            dump["tasks"] = [_task_row(r) for r in svc.tasks.list_tasks()]
        except Exception as exc:  # noqa: BLE001
            dump["tasks"] = [{"error": f"{type(exc).__name__}: {exc}"}]
        dump["pool_sizes"] = svc.engine.pool_sizes()
    finally:
        svc.tasks.close()
        svc.log.close()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dump, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return dump
