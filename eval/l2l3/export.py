"""跑链结束后的只读导出：以 mode=ro 读取停止后的 SQLite 和 durable
checkpoint，沿用受限快照校验；不启动服务、不调用模型、不写项目状态。
输出 L0、记忆、任务产物及提交回执，供抽检与结算。"""
from __future__ import annotations

from contextlib import closing, contextmanager
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


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
        if isinstance(v, str):
            return v
    raise ValueError("retrieval response has no context field")


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
            "agg_members": list(getattr(m, "agg_members", ()) or ()),
            "claim_key": list(m.claim_key), "claim_value": m.claim_value,
            "claim_unit": m.claim_unit, "withdrawn_at": m.withdrawn_at,
            "reviewed_after": m.reviewed_after,
            "hits": m.hits, "conf_pos": m.conf_pos, "conf_neg": m.conf_neg}


def _task_row(row) -> dict:
    r = row if isinstance(row, dict) else dict(row)
    out = {"id": r.get("id"), "kind": r.get("kind"), "state": r.get("state"),
           "retries": r.get("retries"), "attempts": r.get("attempts"),
           "apply_attempts": r.get("apply_attempts"), "last_error": r.get("last_error", "")}
    # selector 裁决对齐需要候选文本（decisions 按 candidate_index 引用本任务
    # 候选）；payload 本体含封存上下文不倾倒，只取候选文本（2026-10-04）。
    if r.get("kind") == "selector_due":
        pl = r.get("payload")
        if isinstance(pl, str):
            pl = json.loads(pl)
        if isinstance(pl, dict) and isinstance(pl.get("candidates"), list):
            out["parent_task"] = pl.get("parent_task")
            out["payload_candidates"] = [c.get("text", "") if isinstance(c, dict) else ""
                                         for c in pl["candidates"]]
            out["payload_sources"] = [c.get("src", []) if isinstance(c, dict) else []
                                      for c in pl["candidates"]]
    result = r.get("result")
    if isinstance(result, str):
        result = json.loads(result)
    if isinstance(result, dict):
        # 只保留裁决与诊断相关字段，避免倾倒整段封存上下文
        out["result"] = {k: result[k] for k in (
            "decisions", "candidates", "diagnosis", "rules", "repair_candidates",
            "rule_reviews", "usage", "verdicts", "action", "accepted", "new_ids", "replayed")
            if k in result}
    else:
        out["result"] = None
    return out


@contextmanager
def _readonly_db(path: Path):
    """读取已停止 sidecar 的快照；有 WAL 时仅在临时副本创建辅助文件。"""
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        with tempfile.TemporaryDirectory(prefix="l2l3-readonly-") as tmp:
            copied = Path(tmp) / path.name
            shutil.copyfile(path, copied)
            shutil.copyfile(wal, Path(str(copied) + "-wal"))
            with closing(sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True)) as conn:
                yield conn
    else:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            yield conn


def read_snapshot(project: str) -> dict:
    from hybrid_memory.core.types import is_visible
    from hybrid_memory.store.state import load_state

    memory = Path(project).resolve() / ".opencode" / "memory"
    svc = SimpleNamespace(engine=SimpleNamespace(), state_path=memory / "state.pkl")
    with closing(sqlite3.connect((memory / "tasks.sqlite").as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        checkpoint = conn.execute("SELECT revision,state FROM checkpoint WHERE id=1").fetchone()
        tasks = []
        for row in conn.execute("SELECT id,kind,state,payload,attempts,last_error FROM tasks ORDER BY id"):
            task = dict(row)
            payload = json.loads(task.pop("payload"))
            task["unit_id"] = payload.get("unit_id")
            tasks.append(task)
        if checkpoint is None:
            if any(t["attempts"] for t in tasks):
                raise ValueError("processed tasks have no durable checkpoint")
            return {"revision": 0, "mems": [], "tasks": tasks}
        load_state(svc, checkpoint["state"])
        reviews = [dict(row) for row in conn.execute("SELECT * FROM human_reviews WHERE status='pending'")]
        return {"revision": checkpoint["revision"], "tasks": tasks, "reviews": reviews,
                "mems": [dict(_mem_row(m), visible=is_visible(m),
                              retrievable=m.superseded_by is None and m.aggregated_into is None and m.withdrawn_at is None)
                         for m in svc.engine.mems.values()]}


def export_run(repo: str, project: str, out_path: str) -> dict:
    _repo_setup(repo)
    from hybrid_memory.core.types import Pool
    from hybrid_memory.store.state import load_state

    memory = Path(project).resolve() / ".opencode" / "memory"
    svc = SimpleNamespace(engine=SimpleNamespace(), state_path=memory / "state.pkl")
    dump = {"project": str(project)}
    with _readonly_db(memory / "tasks.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        checkpoint = conn.execute("SELECT revision,state FROM checkpoint WHERE id=1").fetchone()
        if checkpoint is None and (
                conn.execute("SELECT 1 FROM tasks WHERE attempts>0 LIMIT 1").fetchone()
                or conn.execute("SELECT 1 FROM operations LIMIT 1").fetchone()):
            raise ValueError("durable checkpoint missing for processed tasks")
        load_state(svc, checkpoint["state"] if checkpoint is not None else None)
        dump["checkpoint_revision"] = checkpoint["revision"] if checkpoint is not None else 0
        dump["mems"] = [_mem_row(m) for m in svc.engine.mems.values()]
        dump["tensions"] = [list(pair) for pair in svc.engine.tensions]
        try:
            dump["human_reviews"] = [dict(r) for r in conn.execute(
                "SELECT * FROM human_reviews WHERE status='pending' ORDER BY id")]
        except Exception as exc:  # noqa: BLE001  导出尽力而为，字段标注失败
            raise ValueError("human review export failed") from exc
        try:
            effects = {r["task_id"]: json.loads(r["response"]) for r in conn.execute(
                "SELECT task_id,response FROM operations WHERE op_key='semantic'")}
            dump["tasks"] = []
            for row in conn.execute("SELECT * FROM tasks ORDER BY id"):
                task = _task_row(row)
                task["committed_effect"] = effects.get(row["id"])
                dump["tasks"].append(task)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("task export failed") from exc
        dump["pool_sizes"] = {p.value: sum(m.pool is p for m in svc.engine.mems.values()) for p in Pool}
    with _readonly_db(memory / "log.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        dump["units"] = [{"unit_id": r["id"], "t": r["t"], "user_text": r["user_text"],
                          "assistant_text": r["assistant_text"]} for r in conn.execute(
                              "SELECT id,t,user_text,assistant_text FROM units ORDER BY id")]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    return dump
