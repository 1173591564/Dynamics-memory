"""L0 日志存储：原始交互单元的不可变冷层 + 可操作的索引面。

日志不是记忆——它不进池、不参与动力学；但它是记忆的证据，agent 要能
**操作**它而不是整段读它。本模块提供的就是那组操作：

    search(query, before, scene, k)   FTS5 trigram（CJK 子串可查）+ 可选向量，
                                      RRF 融合；只返回片段，不返回全文
    timeline(entity, before)          某实体的全部提及按时间排列（mentions 表
                                      命中优先，否则回退 FTS）
    stats(group_by, before)           只给聚合计数，不给原文——mining 的入口
    window(unit_ids, max_chars)       唯一回展原文的通道，按字符预算截断
    entities_in(text)                 确定性实体抽取（路径/PR#/hash/版本/
                                      标识符/环境变量/URL），零 LLM

`before=t` 是因果约束：只看 unit.t < before 的单元。回放评测里把它当
硬参数传，agent 物理上查不到未来。

线程：单连接 + RLock（sidecar 的 HTTP 是多线程的）。path=None → 内存库。
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Iterable

import numpy as np

from .embed.base import cosine
from .taskstore import CaptureConflict

# ---------------------------------------------------------------- 实体正则
# 顺序即优先级；全部只覆盖 ASCII 类"硬实体"——这些在项目日志里最稳定、
# 最值得建时间线（CJK 概念实体由 agent 提议时以 entity_key 回填）。
_ENTITY_PATTERNS = (
    ("url", re.compile(r"https?://[^\s<>\"')\]]+")),
    ("path", re.compile(
        r"(?<![\w/])(?:[\w.-]+/)+[\w.-]+"                    # a/b/c.ext
        r"|(?<![\w/])[\w-]+\.(?:py|ts|tsx|js|jsx|mjs|json|jsonc|md|ya?ml|toml"
        r"|sh|ps1|go|rs|java|kt|cpp|cc|c|h|hpp|sql|proto|env|lock|txt|csv)\b")),
    ("pr", re.compile(r"(?:\bPR\s*#?|\bissue\s*#?|(?<![\w&])#)(\d{1,6})\b",
                      re.IGNORECASE)),
    ("hash", re.compile(r"\b[0-9a-f]{7,40}\b")),
    ("version", re.compile(r"\bv?\d+\.\d+(?:\.\d+)+(?:[-+][\w.]+)?\b")),
    ("envvar", re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")),
    ("ident", re.compile(
        r"(?<!\w)_*[A-Za-z][\w]*(?:[_.][A-Za-z][\w]*)+\b"    # snake.dot idents
        r"|(?<!\w)_*[a-z]+(?:[A-Z][a-z0-9]+)+\b"             # camelCase
        r"|(?<!\w)[A-Za-z][\w]*-[\w-]+\b")),                # kebab-case
)
_STOP_IDENT = {"e.g", "i.e", "vs.", "etc."}


def entities_in(text: str, limit: int = 64) -> list[tuple[str, str]]:
    """→ [(entity, kind)]，去重、保序、小写化（URL 保留原样去尾标点）。"""
    if not text:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, pat in _ENTITY_PATTERNS:
        for m in pat.finditer(text):
            ent = m.group(1) if (kind == "pr") else m.group(0)
            if kind == "pr":
                ent = f"#{ent}"
            elif kind == "url":
                ent = ent.rstrip(".,;:!?)")
            else:
                ent = ent.lower()
            if kind == "hash" and not any(c.isdigit() for c in ent):
                continue           # 纯字母 7+ 位不是 hash（如 "default"）
            if kind == "hash" and not any(c.isalpha() for c in ent):
                continue           # 纯数字长串按数量看，不当 hash
            if kind == "envvar" and len(ent) < 5:
                continue
            if ent in _STOP_IDENT or len(ent) < 3:
                continue
            if ent in seen:
                continue
            seen.add(ent)
            out.append((ent, kind))
            if len(out) >= limit:
                return out
    return out


# ---------------------------------------------------------------- 存储
_SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY,
    t INTEGER NOT NULL,
    ts REAL NOT NULL,
    scene TEXT NOT NULL DEFAULT '',
    user_text TEXT NOT NULL,
    assistant_text TEXT NOT NULL,
    assistant_turns INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS units_t ON units(t);
CREATE VIRTUAL TABLE IF NOT EXISTS units_fts USING fts5(
    user_text, assistant_text, content='units', content_rowid='id',
    tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS units_ai AFTER INSERT ON units BEGIN
    INSERT INTO units_fts(rowid, user_text, assistant_text)
    VALUES (new.id, new.user_text, new.assistant_text);
END;
CREATE TABLE IF NOT EXISTS mentions (
    entity TEXT NOT NULL,
    kind TEXT NOT NULL,
    unit_id INTEGER NOT NULL,
    PRIMARY KEY (entity, unit_id)
);
CREATE INDEX IF NOT EXISTS mentions_unit ON mentions(unit_id);
CREATE TABLE IF NOT EXISTS unit_emb (
    unit_id INTEGER PRIMARY KEY,
    dims INTEGER NOT NULL,
    vec BLOB NOT NULL
);
-- Only online append creates a row. Legacy units are deliberately not replayed.
CREATE TABLE IF NOT EXISTS unit_work (
    unit_id INTEGER PRIMARY KEY REFERENCES units(id),
    state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','done')),
    result TEXT, context TEXT NOT NULL DEFAULT '{}', attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '', next_run_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS unit_work_order ON unit_work(state,unit_id);
CREATE TABLE IF NOT EXISTS capture_receipts (
    request_id TEXT PRIMARY KEY,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    fingerprint TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""

_TOKEN_RE = re.compile(r"[A-Za-z0-9_#./+-]{2,}|[\u4e00-\u9fff]+")
_MAX_EMBED_CHARS = 1800


def _tokens(query: str) -> list[str]:
    """查询切词：ASCII 串按空白/标点，CJK 连续串整段（trigram 需 ≥3 字符，
    短于 3 的丢弃——否则 FTS 返回空集）。"""
    toks = []
    for tok in _TOKEN_RE.findall(query):
        tok = tok.strip(".,;:")
        if len(tok) >= 3 and tok not in toks:
            toks.append(tok)
    return toks


def _fts_expr(tokens: list[str]) -> str:
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def _snippet(text: str, tokens: list[str], width: int) -> str:
    low = text.lower()
    pos = -1
    for tok in tokens:
        i = low.find(tok.lower())
        if i >= 0 and (pos < 0 or i < pos):
            pos = i
    if pos < 0:
        pos = 0
    start = max(0, pos - width // 2)
    end = min(len(text), start + width)
    piece = text[start:end].replace("\n", " ")
    return ("…" if start > 0 else "") + piece + ("…" if end < len(text) else "")


class LogStore:
    def __init__(self, path: str | Path | None = None, embedder=None):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path) if self.path else ":memory:",
                                     check_same_thread=False)
        if self.path:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        if "context" not in {r[1] for r in self._conn.execute("PRAGMA table_info(unit_work)")}:
            self._conn.execute("ALTER TABLE unit_work ADD COLUMN context TEXT NOT NULL DEFAULT '{}'")
        self._lock = threading.RLock()
        self._embedder = embedder
        self.n_embed_fail = 0

    # ---- 写 ----
    def next_position(self) -> tuple[int, int]:
        """L0 的下一编号/逻辑时间；启动对齐用，写入时仍需在事务内重新读取。"""
        with self._lock:
            # 两个独立 MAX 各走对应索引，避免每轮扫描整张日志表。
            uid, t = self._conn.execute(
                "SELECT COALESCE((SELECT MAX(id) FROM units), -1) + 1,"
                " COALESCE((SELECT MAX(t) FROM units), -1) + 1").fetchone()
        return max(0, uid), max(0, t)

    def append_unit(self, t: int, *, user_text: str, assistant_text: str,
                    scene: str = "", assistant_turns: int = 1,
                    ts: float | None = None, min_unit_id: int = 0,
                    work_context: dict | None = None,
                    capture_id: str | None = None,
                    capture_fingerprint: str | None = None) -> dict:
        """在线追加：数据库在写事务内分配 id/t，快照只提供不能回退的下界。
        返回 unit_id/t/entities/new_entities。原文和确定性索引一起提交，
        可选 embedding 在提交后执行。不同连接追加也不会复用已提交编号。
        capture_id 与单元、待办在同一事务绑定；重放返回 replayed，不新分配 id。
        """
        return self.add_unit(None, t, user_text=user_text,
                             assistant_text=assistant_text, scene=scene,
                             assistant_turns=assistant_turns, ts=ts,
                             min_unit_id=min_unit_id, track_work=True,
                             work_context=work_context, capture_id=capture_id,
                             capture_fingerprint=capture_fingerprint)

    def add_unit(self, unit_id: int | None, t: int, *, user_text: str,
                 assistant_text: str, scene: str = "",
                 assistant_turns: int = 1, ts: float | None = None,
                 min_unit_id: int = 0, track_work: bool = False,
                 work_context: dict | None = None,
                 capture_id: str | None = None,
                 capture_fingerprint: str | None = None) -> dict:
        """导入指定 id/t；在线 append 在同一事务内登记待处理工作。

        证据不可覆盖：同 id 同内容的重放为 no-op，不重建索引/向量、不重发
        new_entities；同 id 不同内容（含 t/scene/显式 ts）抛 ValueError。
        未显式给 ts 的重放保留首次提交时间，不把重试时刻当成新证据。
        """
        t, assistant_turns = int(t), int(assistant_turns)
        user_text, assistant_text, scene = user_text or "", assistant_text or "", scene or ""
        ents = entities_in(user_text + "\n" + assistant_text)
        with self._lock, self._conn:
            # RLock 只保护本连接；BEGIN IMMEDIATE 同时串行化跨连接的
            # 读游标/查重/插入，不能先在事务外取 MAX 再 INSERT。
            self._conn.execute("BEGIN IMMEDIATE")
            if capture_id:
                bound = self._conn.execute(
                    "SELECT unit_id, fingerprint FROM capture_receipts WHERE request_id=?",
                    (capture_id,)).fetchone()
                if bound is not None:
                    if bound[1] != capture_fingerprint:
                        raise CaptureConflict(f"request_id {capture_id} 已绑定不同交互")
                    existing_t = self._conn.execute(
                        "SELECT t FROM units WHERE id=?", (bound[0],)).fetchone()
                    return {"unit_id": bound[0], "t": existing_t[0], "replayed": True,
                            "entities": [], "new_entities": []}
            if unit_id is None:
                next_id, next_t = self.next_position()
                unit_id = max(next_id, int(min_unit_id))
                t = max(t, next_t)
            else:
                unit_id = int(unit_id)
                existing = self._conn.execute(
                    "SELECT t, scene, user_text, assistant_text, assistant_turns, ts"
                    " FROM units WHERE id=?", (unit_id,)).fetchone()
                if existing is not None:
                    if (existing[:5] != (t, scene, user_text, assistant_text, assistant_turns)
                            or (ts is not None and existing[5] != float(ts))):
                        raise ValueError(f"unit {unit_id} already exists with different evidence")
                    return {"unit_id": unit_id, "t": t,
                            "entities": [e for e, _ in ents], "new_entities": []}
            self._conn.execute(
                "INSERT INTO units"
                " (id, t, ts, scene, user_text, assistant_text, assistant_turns)"
                " VALUES (?,?,?,?,?,?,?)",
                (unit_id, t, float(ts if ts is not None else time.time()),
                 scene, user_text, assistant_text, assistant_turns))
            new = []
            for ent, kind in ents:
                seen = self._conn.execute(
                    "SELECT 1 FROM mentions WHERE entity=? LIMIT 1",
                    (ent,)).fetchone()
                if seen is None:
                    new.append(ent)
                self._conn.execute(
                    "INSERT INTO mentions(entity, kind, unit_id)"
                    " VALUES (?,?,?)", (ent, kind, unit_id))
            if track_work:
                self._conn.execute("INSERT INTO unit_work(unit_id,context) VALUES(?,?)",
                                   (unit_id, json.dumps(work_context or {}, ensure_ascii=False)))
            if capture_id:
                self._conn.execute(
                    "INSERT INTO capture_receipts(request_id, unit_id, fingerprint, created_at)"
                    " VALUES(?,?,?,?)",
                    (capture_id, unit_id, capture_fingerprint, time.time()))
        self._embed(unit_id, user_text, assistant_text)
        return {"unit_id": unit_id, "t": t,
                "entities": [e for e, _ in ents], "new_entities": new}

    def _embed(self, unit_id: int, user_text: str, assistant_text: str) -> None:
        if self._embedder is None:
            return
        text = (user_text[:600] + "\n" + assistant_text)[:_MAX_EMBED_CHARS]
        try:
            vec = np.asarray(self._embedder.embed([text])[0], dtype="<f4")
        except Exception:      # noqa: BLE001  向量只是加分项，失败不阻塞写入
            self.n_embed_fail += 1
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO unit_emb(unit_id, dims, vec) VALUES (?,?,?)",
                (int(unit_id), int(vec.size), vec.tobytes()))

    # ---- 在线单元工作日志（与 L0 同库；不回填升级前历史单元）----
    def capture_receipt(self, request_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT request_id, unit_id, fingerprint, created_at FROM capture_receipts"
                " WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            return None
        return {"request_id": row[0], "unit_id": row[1], "fingerprint": row[2],
                "created_at": row[3]}

    def work(self, unit_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT unit_id,state,result,context,attempts,last_error,next_run_at "
                "FROM unit_work WHERE unit_id=?", (unit_id,)).fetchone()
        if row is None:
            return None
        return {"unit_id": row[0], "state": row[1], "result": row[2],
                "context": json.loads(row[3]), "attempts": row[4],
                "last_error": row[5], "next_run_at": row[6]}

    def pending_units(self, limit: int = 8) -> list[int]:
        # 不跳过退避中的较早单元，否则新单元可能先推进引擎时间和场景。
        with self._lock:
            return [r[0] for r in self._conn.execute(
                "SELECT unit_id FROM unit_work WHERE state='pending' "
                "ORDER BY unit_id LIMIT ?", (limit,))]

    def work_stats(self) -> dict:
        with self._lock:
            pending, ready, failed, done = self._conn.execute(
                "SELECT COUNT(*) FILTER (WHERE state='pending'), "
                "COUNT(*) FILTER (WHERE state='pending' AND result IS NOT NULL), "
                "COUNT(*) FILTER (WHERE state='pending' AND last_error<>''), "
                "COUNT(*) FILTER (WHERE state='done') FROM unit_work").fetchone()
        return {"pending": pending, "result_saved": ready, "failed": failed, "done": done}

    def unit_context(self, unit_id: int) -> dict:
        """按原单元时间恢复首次出现的实体及上一轮原文，不使用当前时钟。"""
        unit = self.get(unit_id)
        if unit is None:
            raise ValueError(f"pending unit {unit_id} 缺失 L0 原文")
        ents = entities_in(unit["user_text"] + "\n" + unit["assistant_text"])
        with self._lock:
            first = [ent for ent, _ in ents if not self._conn.execute(
                "SELECT 1 FROM mentions m JOIN units u ON u.id=m.unit_id "
                "WHERE m.entity=? AND u.t<? LIMIT 1", (ent, unit["t"])).fetchone()]
            previous = self._conn.execute(
                "SELECT user_text FROM units WHERE t<? ORDER BY t DESC LIMIT 1",
                (unit["t"],)).fetchone()
        return {"unit": unit, "entities": [e for e, _ in ents],
                "new_entities": first, "previous_user": previous[0] if previous else ""}

    def save_work_result(self, unit_id: int, result: str) -> None:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE unit_work SET result=?,last_error='',next_run_at=0 "
                "WHERE unit_id=? AND state='pending' AND result IS NULL", (result, unit_id))
            if cursor.rowcount != 1:
                raise RuntimeError(f"unit {unit_id} 结果不可写（已完成或重复）")

    def fail_work(self, unit_id: int, error: Exception) -> None:
        with self._lock, self._conn:
            row = self._conn.execute("SELECT attempts FROM unit_work WHERE unit_id=? AND state='pending'",
                                     (unit_id,)).fetchone()
            if row is None:
                return
            delay = min(300, 2 * (2 ** min(row[0], 8)))
            self._conn.execute(
                "UPDATE unit_work SET attempts=attempts+1,last_error=?,next_run_at=? "
                "WHERE unit_id=? AND state='pending'",
                (f"{type(error).__name__}: {error}"[:500], time.time() + delay, unit_id))

    def finish_work(self, unit_id: int) -> None:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE unit_work SET state='done',last_error='',next_run_at=0 "
                "WHERE unit_id=? AND state='pending'", (unit_id,))
            if cursor.rowcount != 1:
                row = self.work(unit_id)
                if row is None or row["state"] != "done":
                    raise RuntimeError(f"unit {unit_id} 无待确认工作")

    # ---- 读 ----
    def get(self, unit_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, t, ts, scene, user_text, assistant_text,"
                " assistant_turns FROM units WHERE id=?",
                (int(unit_id),)).fetchone()
        return self._row(row) if row else None

    def count(self, before: int | None = None) -> int:
        with self._lock:
            if before is None:
                return self._conn.execute("SELECT count(*) FROM units").fetchone()[0]
            return self._conn.execute(
                "SELECT count(*) FROM units WHERE t<?", (int(before),)).fetchone()[0]

    def exists(self, unit_ids: Iterable[int], before: int | None = None) -> dict:
        """→ {unit_id: t}，只含存在（且满足 before）的。"""
        ids = [int(i) for i in unit_ids]
        if not ids:
            return {}
        q = f"SELECT id, t FROM units WHERE id IN ({','.join('?' * len(ids))})"
        args: list = ids
        if before is not None:
            q += " AND t<?"
            args = ids + [int(before)]
        with self._lock:
            return {r[0]: r[1] for r in self._conn.execute(q, args).fetchall()}

    def search(self, query: str, *, before: int | None = None,
               scene: str | None = None, k: int = 8,
               snippet: int = 160) -> list[dict]:
        """混合检索 → [{unit_id, t, scene, snippet, score}]。
        词法路：FTS5 trigram，bm25 排序；向量路：有 embedder 且有缓存向量时；
        两路 RRF 融合。永远不返回全文。"""
        k = max(1, int(k))
        toks = _tokens(query)
        lex: list[int] = []
        with self._lock:
            if toks:
                sql = ("SELECT u.id FROM units_fts f JOIN units u ON u.id=f.rowid"
                       " WHERE units_fts MATCH ?")
                args: list = [_fts_expr(toks)]
                if before is not None:
                    sql += " AND u.t<?"
                    args.append(int(before))
                if scene:
                    sql += " AND u.scene=?"
                    args.append(scene)
                sql += " ORDER BY bm25(units_fts) LIMIT ?"
                args.append(k * 4)
                try:
                    lex = [r[0] for r in self._conn.execute(sql, args).fetchall()]
                except sqlite3.OperationalError:
                    lex = []
            if not lex and query.strip():
                # 无 ≥3 字符 token（如 "PR 7"）或 FTS 语法异常 → LIKE 兜底
                like = f"%{query.strip()}%"
                sql = ("SELECT id FROM units WHERE (user_text LIKE ? OR"
                       " assistant_text LIKE ?)")
                args = [like, like]
                if before is not None:
                    sql += " AND t<?"
                    args.append(int(before))
                if scene:
                    sql += " AND scene=?"
                    args.append(scene)
                sql += " ORDER BY t DESC LIMIT ?"
                args.append(k * 4)
                lex = [r[0] for r in self._conn.execute(sql, args).fetchall()]
        sem = self._vector_rank(query, before=before, scene=scene, k=k * 4)
        fused: dict[int, float] = {}
        for rank, uid in enumerate(lex):
            fused[uid] = fused.get(uid, 0.0) + 1.0 / (60 + rank)
        for rank, uid in enumerate(sem):
            fused[uid] = fused.get(uid, 0.0) + 1.0 / (60 + rank)
        top = sorted(fused.items(), key=lambda x: (-x[1], x[0]))[:k]
        out = []
        for uid, score in top:
            row = self.get(uid)
            if row is None:
                continue
            text = row["user_text"] + "\n" + row["assistant_text"]
            out.append({"unit_id": uid, "t": row["t"], "scene": row["scene"],
                        "snippet": _snippet(text, toks or [query], snippet),
                        "score": round(score, 5)})
        return out

    def _vector_rank(self, query: str, *, before, scene, k: int) -> list[int]:
        if self._embedder is None:
            return []
        with self._lock:
            sql = "SELECT e.unit_id, e.vec FROM unit_emb e JOIN units u ON u.id=e.unit_id"
            conds, args = [], []
            if before is not None:
                conds.append("u.t<?")
                args.append(int(before))
            if scene:
                conds.append("u.scene=?")
                args.append(scene)
            if conds:
                sql += " WHERE " + " AND ".join(conds)
            rows = self._conn.execute(sql, args).fetchall()
        if not rows:
            return []
        try:
            qv = np.asarray(self._embedder.embed([query])[0], dtype="<f4")
        except Exception:      # noqa: BLE001
            self.n_embed_fail += 1
            return []
        scored = []
        for uid, blob in rows:
            vec = np.frombuffer(blob, dtype="<f4")
            if vec.size != qv.size:
                continue
            scored.append((cosine(qv, vec), uid))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [uid for _, uid in scored[:k]]

    def timeline(self, entity: str, *, before: int | None = None,
                 limit: int = 50, snippet: int = 160) -> list[dict]:
        """实体时间线 → [{unit_id, t, scene, snippet}]（按 t 升序）。
        mentions 精确命中优先；没有（如 CJK 概念）则回退 FTS/LIKE。"""
        ent = entity.strip()
        if not ent:
            return []
        key = ent.lower() if not ent.startswith("http") else ent
        with self._lock:
            sql = ("SELECT u.id FROM mentions m JOIN units u ON u.id=m.unit_id"
                   " WHERE m.entity=?")
            args: list = [key]
            if before is not None:
                sql += " AND u.t<?"
                args.append(int(before))
            sql += " ORDER BY u.t ASC, u.id ASC LIMIT ?"
            args.append(int(limit))
            ids = [r[0] for r in self._conn.execute(sql, args).fetchall()]
        if not ids:
            hits = self.search(ent, before=before, k=limit, snippet=snippet)
            hits.sort(key=lambda h: (h["t"], h["unit_id"]))
            return [{k2: h[k2] for k2 in ("unit_id", "t", "scene", "snippet")}
                    for h in hits]
        out = []
        for uid in ids:
            row = self.get(uid)
            if row is None:
                continue
            text = row["user_text"] + "\n" + row["assistant_text"]
            out.append({"unit_id": uid, "t": row["t"], "scene": row["scene"],
                        "snippet": _snippet(text, [ent], snippet)})
        return out

    def mention_counts(self, entities: Iterable[str],
                       before: int | None = None) -> dict[str, int]:
        out = {}
        with self._lock:
            for ent in entities:
                sql = ("SELECT count(*) FROM mentions m JOIN units u ON u.id=m.unit_id"
                       " WHERE m.entity=?")
                args: list = [ent.lower() if not ent.startswith("http") else ent]
                if before is not None:
                    sql += " AND u.t<?"
                    args.append(int(before))
                out[ent] = self._conn.execute(sql, args).fetchone()[0]
        return out

    def stats(self, group_by: str = "scene", *, before: int | None = None,
              limit: int = 50) -> list[dict]:
        """聚合视图（不含原文）。group_by ∈ scene | entity | week。"""
        cond = " WHERE u.t<?" if before is not None else ""
        args: list = [int(before)] if before is not None else []
        with self._lock:
            if group_by == "scene":
                rows = self._conn.execute(
                    f"SELECT u.scene, count(*), min(u.t), max(u.t) FROM units u{cond}"
                    " GROUP BY u.scene ORDER BY count(*) DESC, max(u.t) DESC LIMIT ?",
                    args + [int(limit)]).fetchall()
                return [{"scene": r[0], "units": r[1], "first_t": r[2],
                         "last_t": r[3]} for r in rows]
            if group_by == "entity":
                rows = self._conn.execute(
                    "SELECT m.entity, m.kind, count(*), min(u.t), max(u.t)"
                    f" FROM mentions m JOIN units u ON u.id=m.unit_id{cond}"
                    " GROUP BY m.entity ORDER BY count(*) DESC, max(u.t) DESC LIMIT ?",
                    args + [int(limit)]).fetchall()
                return [{"entity": r[0], "kind": r[1], "mentions": r[2],
                         "first_t": r[3], "last_t": r[4]} for r in rows]
            if group_by == "week":
                rows = self._conn.execute(
                    f"SELECT u.ts, u.t FROM units u{cond}", args).fetchall()
                buckets: dict[str, dict] = {}
                for ts, t in rows:
                    iso = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isocalendar()
                    wk = f"{iso[0]}-W{iso[1]:02d}"
                    b = buckets.setdefault(wk, {"week": wk, "units": 0,
                                                "first_t": t, "last_t": t})
                    b["units"] += 1
                    b["first_t"] = min(b["first_t"], t)
                    b["last_t"] = max(b["last_t"], t)
                return sorted(buckets.values(), key=lambda b: b["week"])[:limit]
        raise ValueError("group_by must be scene | entity | week")

    def window(self, unit_ids: Iterable[int], *, max_chars: int = 2000,
               before: int | None = None) -> dict:
        """按需回展原文——唯一返回全文的通道。按给定顺序拼接，超预算截断，
        返回 {units:[{unit_id,t,scene,user_text,assistant_text,truncated}],
        chars, truncated, missing}。"""
        budget = max(0, int(max_chars))
        out, used, missing, omitted = [], 0, [], []
        truncated_any = False
        for uid in unit_ids:
            row = self.get(int(uid))
            if row is None or (before is not None and row["t"] >= before):
                missing.append(int(uid))
                continue
            remain = budget - used
            if remain <= 0:
                truncated_any = True
                omitted.append(int(uid))
                continue
            u, a = row["user_text"], row["assistant_text"]
            tr = False
            if len(u) + len(a) > remain:
                tr = truncated_any = True
                if len(u) >= remain:
                    u, a = u[:remain], ""
                else:
                    a = a[:remain - len(u)]
            used += len(u) + len(a)
            out.append({"unit_id": row["id"], "t": row["t"], "scene": row["scene"],
                        "user_text": u, "assistant_text": a, "truncated": tr})
        return {"units": out, "chars": used, "truncated": truncated_any,
                "missing": missing, "omitted": omitted}

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row(row) -> dict:
        return {"id": row[0], "t": row[1], "ts": row[2], "scene": row[3],
                "user_text": row[4], "assistant_text": row[5],
                "assistant_turns": row[6]}
