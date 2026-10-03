"""HTTP 服务端（P5 从 server.py 迁入）：Handler + ROUTES + serve + 错误映射。

路由由 ROUTES 声明式表驱动；trio 下三入口经 TRIO_DISABLED 集中禁用
（H35，403 文案与旧内联检查逐字一致）；异常→状态码映射见 _run（H24）。
"""
from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..errors import Degraded, Rejected, http_status
from ..service.context import CausalViolation, SignalClosed
from ..service.operate import VERDICTS
from ..service.service import MemoryService
from ..store.tasks import CaptureConflict, CheckpointConflict, TaskQueueFull
from . import auth, dto
from .dto import HttpError

TRIO_DISABLED = {
    "/resolve": "direct resolution disabled; human review is required",
    "/propose": "direct proposals disabled; use Hauler and Selector",
    "/diagnose": "direct diagnosis disabled; Reviewer owns this work",
    "/miss": "miss reporting disabled; Trio pipeline does not consume recall_miss",
}

ROUTES = {
    "/health": "handle_health",
    "/recall": "handle_recall",
    "/conflicts": "handle_conflicts",
    "/signals": "handle_signals",
    "/observe": "handle_observe",
    "/feedback": "handle_feedback",
    "/human-reviews": "handle_human_reviews",
    "/human-review": "handle_human_review",
    "/resolve": "handle_resolve",
    "/search": "handle_search",
    "/miss": "handle_miss",
    "/log/search": "handle_log_search",
    "/log/timeline": "handle_log_timeline",
    "/log/stats": "handle_log_stats",
    "/log/window": "handle_log_window",
    "/propose": "handle_propose",
    "/diagnose": "handle_diagnose",
    "/save": "handle_save",
}


class Handler(BaseHTTPRequestHandler):
    service: MemoryService

    def log_message(self, *args) -> None:   # 静默访问日志
        pass

    def _reply(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_health(self, q, body, sid) -> None:
        svc = self.service
        body = svc.health_view()
        self._reply(503 if not body["ok"] else 200, body)

    def handle_recall(self, q, body, sid) -> None:
        svc = self.service
        try:
            k = int(q["k"]) if q.get("k") else None
        except ValueError:
            raise HttpError(400, "k must be int")
        if k is not None and k <= 0:
            raise HttpError(400, "k must be positive")
        query = q.get("q", "")
        if not query:
            raise HttpError(400, "q required")
        budget = q.get("budget_tokens")
        if budget is not None:
            try:
                budget = int(budget)
            except ValueError:
                raise HttpError(400, "budget_tokens must be int")
        self._reply(200, svc.recall(query, k, signal_id=sid,
                                    budget_tokens=budget,
                                    passive=q.get("passive", "") in ("1", "true")))

    def handle_conflicts(self, q, body, sid) -> None:
        self._reply(200, self.service.conflicts(signal_id=sid))

    def handle_signals(self, q, body, sid) -> None:
        self._reply(200, self.service.signals())

    def handle_observe(self, q, body, sid) -> None:
        p = dto.observe_payload(body, self.headers)
        self._reply(200, self.service.observe(p["user_text"], p["assistant_text"],
                                              request_id=p["request_id"]))

    def handle_feedback(self, q, body, sid) -> None:
        p = dto.feedback_payload(body, self.headers)
        out = self.service.feedback(p["retrieval_id"], p["question"], p["answer"],
                                    request_id=p["request_id"])
        if "error" in out:
            # N42：机器码优先（memory-bridge.ts 检查 code === "already_credited"），
            # 文本 "already" 仅兜底旧服务。
            if out.get("code") == "already_credited" or "already" in out["error"]:
                self._reply(409, out)
                return
            raise HttpError(404, out["error"], "not_found")
        self._reply(200, out)

    def handle_human_reviews(self, q, body, sid) -> None:
        self._reply(200, {"reviews": self.service.human_reviews()})

    def handle_human_review(self, q, body, sid) -> None:
        rid = dto.opt_int(body, "review_id")
        if rid is None:
            raise HttpError(400, "review_id required")
        cap = self.headers.get("X-Human-Review-Token", "")
        if not secrets.compare_digest(cap, self.service.human_review_token):
            raise HttpError(403, "human review capability required", "forbidden")
        try:
            out = self.service.decide_human_review(rid, str(body.get("decision", "")), cap)
        except ValueError as exc:
            if "not found" in str(exc):
                raise HttpError(404, str(exc), "not_found") from exc
            if "changed" in str(exc) or "conflicting" in str(exc):
                raise HttpError(409, str(exc), "conflict") from exc
            raise HttpError(400, str(exc), "bad_request") from exc
        self._reply(200, out)

    def handle_resolve(self, q, body, sid) -> None:
        svc = self.service
        left, right = dto.opt_int(body, "left"), dto.opt_int(body, "right")
        if left is None or right is None:
            raise HttpError(400, "left/right required")
        ensure = body.get("ensure_tension", False)
        if not isinstance(ensure, bool):
            raise HttpError(400, "ensure_tension must be bool")
        verdict = str(body.get("verdict", "pending"))
        if verdict not in VERDICTS:
            raise HttpError(400, f"verdict must be one of "
                                 f"{sorted(VERDICTS)}")
        ek = body.get("entity_key", "")
        self._reply(200, svc.resolve(
            left, right, verdict,
            entity_key=ek if isinstance(ek, str) else "",
            ensure_tension=ensure, signal_id=sid))

    def handle_search(self, q, body, sid) -> None:
        k = dto.opt_int(body, "k", positive=True)
        query = body.get("query", "")
        if not isinstance(query, str) or not query:
            raise HttpError(400, "query required")
        self._reply(200, self.service.recall(query, k, signal_id=sid,
                                             budget_tokens=dto.opt_int(body, "budget_tokens"),
                                             passive=body.get("passive", False)))

    def handle_miss(self, q, body, sid) -> None:
        query = dto.req_str(body, "query")
        hint = body.get("hint", "")
        source = body.get("source", "agent_tool")
        self._reply(200, self.service.report_miss(
            query, hint if isinstance(hint, str) else "",
            source if isinstance(source, str) else "agent_tool"))

    def handle_log_search(self, q, body, sid) -> None:
        query = dto.req_str(body, "query")
        scene = body.get("scene")
        self._reply(200, self.service.log_search(
            query, before=dto.opt_int(body, "before"),
            scene=scene if isinstance(scene, str) else None,
            k=dto.opt_int(body, "k", positive=True) or 8, signal_id=sid))

    def handle_log_timeline(self, q, body, sid) -> None:
        entity = dto.req_str(body, "entity")
        self._reply(200, self.service.log_timeline(
            entity, before=dto.opt_int(body, "before"),
            limit=dto.opt_int(body, "limit", positive=True) or 30,
            signal_id=sid))

    def handle_log_stats(self, q, body, sid) -> None:
        gb = body.get("group_by", "scene")
        if gb not in ("scene", "entity", "week"):
            raise HttpError(400, "group_by must be scene | entity | week")
        self._reply(200, self.service.log_stats(
            gb, before=dto.opt_int(body, "before"),
            limit=dto.opt_int(body, "limit", positive=True) or 30,
            signal_id=sid))

    def handle_log_window(self, q, body, sid) -> None:
        ids = body.get("unit_ids")
        if (not isinstance(ids, list) or not ids or len(ids) > 20
                or not all(type(i) is int and 0 <= i < 2**63 for i in ids)):
            raise HttpError(400, "unit_ids must be a non-empty int list (≤20)")
        self._reply(200, self.service.log_window(
            ids, max_chars=dto.opt_int(body, "max_chars", positive=True),
            signal_id=sid))

    def handle_propose(self, q, body, sid) -> None:
        props = body.get("proposals")
        if not isinstance(props, list):
            raise HttpError(400, "proposals must be a list")
        origin = body.get("origin", "agent")
        self._reply(200, self.service.propose(
            props, origin=origin if isinstance(origin, str) else "agent",
            signal_id=sid, before=dto.opt_int(body, "before")))

    def handle_diagnose(self, q, body, sid) -> None:
        svc = self.service
        mt = dto.req_str(body, "miss_type")
        note = body.get("note", "")
        try:
            self._reply(200, svc.diagnose(
                mt, note if isinstance(note, str) else "", signal_id=sid,
                kind=str(body.get("kind", ""))))
        except ValueError as exc:
            raise HttpError(400, str(exc))

    def handle_save(self, q, body, sid) -> None:
        self._reply(200, self.service.save())

    def _dispatch(self, path: str, q: dict, body: dict) -> None:
        svc = self.service
        raw_sid = self.headers.get("X-Signal-Id")
        sid = raw_sid.strip() if raw_sid is not None else None
        # /health 是插件启动时使用的公开探针，不计工具预算，也不返回原文。
        if sid is not None and path != "/health" and path not in dto.SIGNAL_PATHS:
            raise SignalClosed(f"调查员不允许访问 {path}")
        if svc.trio_mode and path in TRIO_DISABLED:
            raise HttpError(403, TRIO_DISABLED[path], "direct_write_disabled")
        handler = ROUTES.get(path)
        if handler is None:
            self._reply(404, {"error": f"no such path: {path}",
                              "code": "not_found"})
            return
        getattr(self, handler)(q, body, sid)

    def _run(self, path: str, q: dict, body: dict) -> None:
        try:
            self._dispatch(path, q, body)
        except Rejected as exc:
            self._reply(http_status(exc.code), {"error": str(exc), "code": exc.code})
        except Degraded as exc:
            self._reply(http_status(exc.code), {"error": str(exc), "code": exc.code})
        except HttpError as exc:
            self._reply(exc.code, {"error": str(exc), "code": exc.mcode})
        except CaptureConflict as exc:
            self._reply(409, {"error": str(exc), "code": "conflict"})
        except TaskQueueFull as exc:
            payload = {"error": str(exc), "code": "queue_full"}
            if getattr(exc, "accepted", False):
                payload.update(accepted=True, pending=True, unit_id=exc.unit_id)
                if getattr(exc, "request_id", None):
                    payload["request_id"] = exc.request_id
            self._reply(503, payload)
        except CheckpointConflict as exc:
            self._reply(503, {"error": str(exc), "code": "checkpoint_conflict"})
        except PermissionError as exc:          # 预算用尽
            self._reply(429, {"error": str(exc), "code": "rate_limited"})
        except SignalClosed as exc:             # 信号号无效/已关闭
            self._reply(403, {"error": str(exc), "code": "signal_closed"})
        except CausalViolation as exc:          # 因果界违规
            self._reply(403, {"error": str(exc), "code": "causal_violation"})
        except ValueError as exc:
            self._reply(400, {"error": str(exc), "code": "bad_request"})
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"error": f"{type(exc).__name__}: {exc}",
                              "code": "internal"})

    def do_GET(self) -> None:    # noqa: N802
        u = urlparse(self.path)
        if u.path == "/health":
            self._run(u.path, {}, {})
            return
        if not auth.authorized(self.headers, self.service.token):
            self._reply(401, {"error": "unauthorized", "code": "unauthorized"})
            return
        if u.path not in dto.GET_PATHS:
            self._reply(405, {"error": f"{u.path} requires POST",
                              "code": "method_not_allowed"})
            return
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self._run(u.path, q, {})

    def do_POST(self) -> None:   # noqa: N802
        u = urlparse(self.path)
        if not auth.authorized(self.headers, self.service.token):
            self._reply(401, {"error": "unauthorized", "code": "unauthorized"})
            return
        if u.path not in dto.POST_PATHS:
            self._reply(405, {"error": f"{u.path} requires GET",
                              "code": "method_not_allowed"})
            return
        try:
            body = dto.parse_body(self.headers, self.rfile)
        except HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
            return
        self._run(u.path, {}, body)


def serve(service: MemoryService, port: int,
          host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = type("_BoundHandler", (Handler,), {"service": service})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd
