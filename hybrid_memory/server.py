"""记忆引擎 sidecar：把 MemoryEngine + L0 logstore HTTP 服务化，供 opencode
插件调用——既服务主 agent（消费记忆），也服务调查员 agent（生产记忆）。

端点（JSON，除 /health 外一律要求 `Authorization: Bearer <token>`；
token 持久化在 state_dir/.memory-token，插件侧同路径读取或经环境变量注入）：

  读记忆
  GET  /health              → 状态。ok 只表示没有 checkpoint fault；
                              snapshot/units_pending/validation 分开报告，免鉴权
  GET  /recall?q=..&k=..    → {retrieval_id, context, selected}
  POST /search              → {query, k} 同 /recall（CJK 长查询走 body）
  GET  /conflicts           → 未决 tension 列表
  GET  /signals             → 调查/语义任务及 L0 单元积压与 worker 遥测

  写记忆（主回路）
  POST /observe             → {user_text, assistant_text, request_id?}：先落 L0 并建索引，
                              触发扫描 → extract_due / recall_miss；再 candgen
                              蒸馏（失败不丢单元）；蒸馏产物进池。
                              可选 request_id 与 L0 同事务绑定；已接受但效果未完成时
                              仍返回 accepted/unit_id（容量不足为 503），不能无 id 重投。
  POST /feedback            → {retrieval_id, question, answer, request_id?} 延迟记账。
                              request_id 与效果同事务；响应丢失后重投返回原回执。
  POST /resolve             → {left, right, verdict, entity_key?} 裁决回报
  POST /miss                → {query, hint?, source?} 上报一次记忆缺失
                              （主 agent 用了 log_* 工具 = 记忆没接住）

  操作日志（agent 工具面；只给片段/聚合，原文只经 /log/window 计量回展）
  POST /log/search          → {query, before?, scene?, k?}
  POST /log/timeline        → {entity, before?, limit?}
  POST /log/stats           → {group_by, before?, limit?}
  POST /log/window          → {unit_ids, max_chars?}

  操作面（agent 产物回流；服务端校验溯源/因果/脱敏/自指）
  POST /propose             → {proposals:[{text, kind, salience,
                               source_unit_ids, entity_key?, supersedes?}],
                               origin?} → {accepted, new_ids, rejected}
  POST /diagnose            → {miss_type, note?}
  POST /save                → 落盘状态快照

进程内调查员直接传 signal_id；兼容 HTTP 调用可带 X-Signal-Id。
按信号计量工具调用与回展预算，统一施加 before 因果上界。
passive=True 在独立引擎视图上检索；budget_tokens 限制整行上下文。

状态：<project>/.opencode/memory/ 下 log.sqlite（L0）与 tasks.sqlite
（调查和语义任务/产物/回执/checkpoint）。有 SQLite checkpoint 时以它为准，否则兼容
state.pkl；/save 更新 checkpoint 并导出 state.pkl。pickle 反序列化仍走白名单。
依赖注入（cfg/emb/semantics/generator/logstore）便于测试。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import secrets
import signal as _signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import triggers
from .legacy.candgen import CandidateGenerator
from .legacy.candgen import ChatGenerator
from .legacy.prompt import parse_ids, parse_salience
from . import telemetry
from .guards.bounds import capture_fingerprint as _capture_fingerprint
from .guards.bounds import validate_request_id as _validate_request_id
from .guards.grounding import content_grounded as _content_grounded
from .guards.redact import redact_secrets
from .config import Cfg, resolve_pipeline
from .core.engine import MemoryEngine
from .core.types import Event, Memory, Pool, Query, Retrieval, Tension
from .core.interaction import InteractionUnit, InteractionWindow
from .core.types import Embedder
from .llm import chat
from .service import budgets, feedback, lifecycle, observe, recall, review
from .service.recall import approx_tokens
from .service.context import (_ORIGINS, CausalViolation, InvestigationContext,
                              SignalClosed)
from .logstore import LogStore, entities_in
from .semantics import normalize
from .semantics.llm import LLMSemantics
from .core import maintenance
from .core.types import FeedbackSemantics, ConsolidationSemantics, is_visible
from .store import state
from .store.state import _COUNTERS, _SERVICE_COUNTERS
from .store.state import RestrictedUnpickler as _RestrictedUnpickler
from .store.tasks import SEMANTIC_KINDS, WORKFLOW_KINDS, TaskLeaseLost
from .store.tasks import TaskStore, TaskQueueFull, CheckpointConflict, CaptureConflict, encode

from .service.service import MemoryService, ProposalRejected, _VERDICTS


# ============================ HTTP ============================

_SIGNAL_PATHS = {"/recall", "/search", "/conflicts", "/resolve", "/propose",
                 "/diagnose", "/log/search", "/log/timeline", "/log/stats", "/log/window"}

_MAX_BODY = 4 * 1024 * 1024          # 请求体上限 4MiB
_GET_PATHS = {"/recall", "/conflicts", "/signals"}   # /health 单列免鉴权
_POST_PATHS = {"/observe", "/feedback", "/resolve", "/human-reviews", "/human-review", "/search", "/save",
               "/miss", "/log/search", "/log/timeline", "/log/stats",
               "/log/window", "/propose", "/diagnose"}


class _HttpError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


def _opt_int(body: dict, key: str, *, positive: bool = False):
    v = body.get(key)
    if v is None:
        return None
    if type(v) is not int or not -(2**63) <= v < 2**63:
        raise _HttpError(400, f"{key} must be a 64-bit int")
    if positive and v <= 0:
        raise _HttpError(400, f"{key} must be positive")
    return v


def _req_str(body: dict, key: str) -> str:
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise _HttpError(400, f"{key} required")
    return v


class _Handler(BaseHTTPRequestHandler):
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

    def _authorized(self) -> bool:
        return secrets.compare_digest(
            (self.headers.get("Authorization") or "").encode("utf-8"),
            f"Bearer {self.service.token}".encode("utf-8"))

    def _body(self) -> dict:
        ct = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ct != "application/json":
            raise _HttpError(415, "Content-Type must be application/json")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise _HttpError(400, "bad Content-Length")
        if n < 0:
            raise _HttpError(400, "bad Content-Length")
        if n > _MAX_BODY:
            raise _HttpError(413, "body too large")
        if not n:
            return {}
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            raise _HttpError(400, "malformed JSON body")
        if not isinstance(body, dict):
            raise _HttpError(400, "body must be a JSON object")
        return body

    def _dispatch(self, path: str, q: dict, body: dict) -> None:
        svc = self.service
        raw_sid = self.headers.get("X-Signal-Id")
        sid = raw_sid.strip() if raw_sid is not None else None
        # /health 是插件启动时使用的公开探针，不计工具预算，也不返回原文。
        if sid is not None and path != "/health" and path not in _SIGNAL_PATHS:
            raise SignalClosed(f"调查员不允许访问 {path}")
        if path == "/health":
            body = svc.health_view()
            self._reply(503 if not body["ok"] else 200, body)
        elif path == "/recall":
            try:
                k = int(q["k"]) if q.get("k") else None
            except ValueError:
                raise _HttpError(400, "k must be int")
            if k is not None and k <= 0:
                raise _HttpError(400, "k must be positive")
            query = q.get("q", "")
            if not query:
                raise _HttpError(400, "q required")
            budget = q.get("budget_tokens")
            if budget is not None:
                try:
                    budget = int(budget)
                except ValueError:
                    raise _HttpError(400, "budget_tokens must be int")
            self._reply(200, svc.recall(query, k, signal_id=sid,
                                       budget_tokens=budget,
                                       passive=q.get("passive", "") in ("1", "true")))
        elif path == "/conflicts":
            self._reply(200, svc.conflicts(signal_id=sid))
        elif path == "/signals":
            self._reply(200, svc.signals())
        elif path == "/observe":
            user = body.get("user_text", "")
            assistant = body.get("assistant_text", "")
            if not isinstance(user, str) or not isinstance(assistant, str):
                raise _HttpError(400, "user_text/assistant_text must be strings")
            if not user.strip() and not assistant.strip():
                raise _HttpError(400, "empty turn")
            self._reply(200, svc.observe(user, assistant, request_id=self._capture_id(body)))
        elif path == "/feedback":
            rid = _opt_int(body, "retrieval_id")
            if rid is None:
                raise _HttpError(400, "retrieval_id required")
            question, answer = body.get("question", ""), body.get("answer", "")
            if not isinstance(question, str) or not isinstance(answer, str):
                raise _HttpError(400, "question/answer must be strings")
            out = svc.feedback(rid, question, answer, request_id=self._capture_id(body))
            if "error" in out:
                if "already" in out["error"]:
                    self._reply(409, out)
                    return
                raise _HttpError(404, out["error"])
            self._reply(200, out)
        elif path == "/human-reviews":
            self._reply(200, {"reviews": svc.human_reviews()})
        elif path == "/human-review":
            rid = _opt_int(body, "review_id")
            if rid is None:
                raise _HttpError(400, "review_id required")
            self._reply(200, svc.decide_human_review(
                rid, str(body.get("decision", "")),
                self.headers.get("X-Human-Review-Token", "")))
        elif path == "/resolve":
            if svc.trio_mode:
                raise _HttpError(403, "direct resolution disabled; human review is required")
            left, right = _opt_int(body, "left"), _opt_int(body, "right")
            if left is None or right is None:
                raise _HttpError(400, "left/right required")
            ensure = body.get("ensure_tension", False)
            if not isinstance(ensure, bool):
                raise _HttpError(400, "ensure_tension must be bool")
            verdict = str(body.get("verdict", "pending"))
            if verdict not in _VERDICTS:
                raise _HttpError(400, f"verdict must be one of "
                                      f"{sorted(_VERDICTS)}")
            ek = body.get("entity_key", "")
            self._reply(200, svc.resolve(
                left, right, verdict,
                entity_key=ek if isinstance(ek, str) else "",
                ensure_tension=ensure, signal_id=sid))
        elif path == "/search":
            k = _opt_int(body, "k", positive=True)
            query = body.get("query", "")
            if not isinstance(query, str) or not query:
                raise _HttpError(400, "query required")
            self._reply(200, svc.recall(query, k, signal_id=sid,
                                       budget_tokens=_opt_int(body, "budget_tokens"),
                                       passive=body.get("passive", False)))
        elif path == "/miss":
            query = _req_str(body, "query")
            hint = body.get("hint", "")
            source = body.get("source", "agent_tool")
            self._reply(200, svc.report_miss(
                query, hint if isinstance(hint, str) else "",
                source if isinstance(source, str) else "agent_tool"))
        elif path == "/log/search":
            query = _req_str(body, "query")
            scene = body.get("scene")
            self._reply(200, svc.log_search(
                query, before=_opt_int(body, "before"),
                scene=scene if isinstance(scene, str) else None,
                k=_opt_int(body, "k", positive=True) or 8, signal_id=sid))
        elif path == "/log/timeline":
            entity = _req_str(body, "entity")
            self._reply(200, svc.log_timeline(
                entity, before=_opt_int(body, "before"),
                limit=_opt_int(body, "limit", positive=True) or 30,
                signal_id=sid))
        elif path == "/log/stats":
            gb = body.get("group_by", "scene")
            if gb not in ("scene", "entity", "week"):
                raise _HttpError(400, "group_by must be scene | entity | week")
            self._reply(200, svc.log_stats(
                gb, before=_opt_int(body, "before"),
                limit=_opt_int(body, "limit", positive=True) or 30,
                signal_id=sid))
        elif path == "/log/window":
            ids = body.get("unit_ids")
            if (not isinstance(ids, list) or not ids or len(ids) > 20
                    or not all(type(i) is int and 0 <= i < 2**63 for i in ids)):
                raise _HttpError(400, "unit_ids must be a non-empty int list (≤20)")
            self._reply(200, svc.log_window(
                ids, max_chars=_opt_int(body, "max_chars", positive=True),
                signal_id=sid))
        elif path == "/propose":
            if svc.trio_mode:
                raise _HttpError(403, "direct proposals disabled; use Hauler and Selector")
            props = body.get("proposals")
            if not isinstance(props, list):
                raise _HttpError(400, "proposals must be a list")
            origin = body.get("origin", "agent")
            self._reply(200, svc.propose(
                props, origin=origin if isinstance(origin, str) else "agent",
                signal_id=sid, before=_opt_int(body, "before")))
        elif path == "/diagnose":
            if svc.trio_mode:
                raise _HttpError(403, "direct diagnosis disabled; Reviewer owns this work")
            mt = _req_str(body, "miss_type")
            note = body.get("note", "")
            try:
                self._reply(200, svc.diagnose(
                    mt, note if isinstance(note, str) else "", signal_id=sid,
                    kind=str(body.get("kind", ""))))
            except ValueError as exc:
                raise _HttpError(400, str(exc))
        elif path == "/save":
            self._reply(200, svc.save())
        else:
            self._reply(404, {"error": f"no such path: {path}"})

    def _capture_id(self, body: dict) -> str | None:
        header = self.headers.get("X-Request-Id")
        if header is not None:
            header = header.strip()
        if header == "":
            raise _HttpError(400, "X-Request-Id must not be empty")
        if "request_id" in body and not isinstance(body.get("request_id"), str):
            raise _HttpError(400, "request_id must be a string")
        body_id = body.get("request_id")
        if body_id == "":
            raise _HttpError(400, "request_id must not be empty")
        if header and body_id and header != body_id:
            raise _HttpError(400, "X-Request-Id and request_id disagree")
        chosen = body_id or header or None
        if chosen is None:
            return None
        try:
            return _validate_request_id(chosen)
        except ValueError as exc:
            raise _HttpError(400, str(exc)) from exc

    def _run(self, path: str, q: dict, body: dict) -> None:
        try:
            self._dispatch(path, q, body)
        except _HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
        except CaptureConflict as exc:
            self._reply(409, {"error": str(exc)})
        except (TaskQueueFull, CheckpointConflict) as exc:
            payload = {"error": str(exc)}
            if getattr(exc, "accepted", False):
                payload.update(accepted=True, pending=True, unit_id=exc.unit_id)
                if getattr(exc, "request_id", None):
                    payload["request_id"] = exc.request_id
            self._reply(503, payload)
        except PermissionError as exc:          # 预算用尽
            self._reply(429, {"error": str(exc)})
        except (SignalClosed, CausalViolation) as exc:             # 信号号无效/已关闭
            self._reply(403, {"error": str(exc)})
        except ValueError as exc:
            self._reply(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self) -> None:    # noqa: N802
        u = urlparse(self.path)
        if u.path == "/health":
            self._run(u.path, {}, {})
            return
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        if u.path not in _GET_PATHS:
            self._reply(405, {"error": f"{u.path} requires POST"})
            return
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self._run(u.path, q, {})

    def do_POST(self) -> None:   # noqa: N802
        u = urlparse(self.path)
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        if u.path not in _POST_PATHS:
            self._reply(405, {"error": f"{u.path} requires GET"})
            return
        try:
            body = self._body()
        except _HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
            return
        self._run(u.path, {}, body)


def serve(service: MemoryService, port: int,
          host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = type("_BoundHandler", (_Handler,), {"service": service})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd


# ============================ 默认组装 ============================

def _load_env_key(project_dir: Path) -> str | None:
    key = os.environ.get("ZAI_API_KEY")
    if key:
        return key
    for env_file in (Path(project_dir) / ".env",
                     Path(__file__).resolve().parents[1] / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ZAI_API_KEY="):
                    val = (line.split("=", 1)[1].strip()
                           .strip('"').strip("'"))
                    if val:
                        return val
    return None


def build_default_service(project_dir: str | Path,
                          model: str = "glm-5.3-flash",
                          embed_log: bool = True, task_capacity: int = 4096) -> MemoryService:
    from .embed.cache import SqliteEmbeddingCache
    from .embed.zhipu import ZhipuEmbedder

    mem_dir = Path(project_dir) / ".opencode" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    # 目录内含 bearer token + 全量记忆语料 + 原始日志：用户项目里通常没有
    # gitignore 覆盖它——自己写一个，防 `git add .` 把 token/state/日志提交进库
    gi = mem_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    key = _load_env_key(Path(project_dir))

    def chat_fn(system: str, user: str) -> str:
        return chat(api_key=key, model=model, system=system, user=user,
                    cache_dir=mem_dir / "chat-cache")

    emb = ZhipuEmbedder(api_key=key,
                        cache=SqliteEmbeddingCache(mem_dir / "emb.sqlite3"))
    semantics = LLMSemantics(None, chat_fn=chat_fn, model=model)
    cfg = Cfg(theta=0.35, cap_m=8, k=5, tau_dup=0.85, tau_sim=0.78,
              useful_hit=True, defer_credit=True)
    log = LogStore(mem_dir / "log.sqlite", embedder=emb if embed_log else None)
    return MemoryService(cfg, emb, semantics, ChatGenerator(chat_fn),
                         state_dir=mem_dir, logstore=log, task_capacity=task_capacity)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=17872)
    ap.add_argument("--project", default=".")
    ap.add_argument("--model", default="glm-5.3-flash")
    # 插件拉起 sidecar 时不传参，调查员相关配置允许走环境变量
    ap.add_argument("--agent-model",
                    default=os.environ.get("MEMORY_AGENT_MODEL", "glm-5.3-flash"),
                    help="进程内调查员模型（兼容 provider/model）")
    ap.add_argument("--no-agent", action="store_true",
                    default=os.environ.get("MEMORY_AGENT", "").lower()
                    in ("off", "0", "false"),
                    help="不启动后台 agent（任务留在 SQLite）；环境变量 MEMORY_AGENT=off 等价")
    ap.add_argument("--agent-daily-cap", type=int,
                    default=int(os.environ.get("MEMORY_AGENT_DAILY_CAP", "200")))
    ap.add_argument("--agent-tool-calls", type=int, default=8)
    ap.add_argument("--agent-window-chars", type=int, default=4000)
    ap.add_argument("--task-queue-cap", type=int, default=4096,
                    help="未结束调查任务上限；满时拒绝新任务，不逐出已接受任务")
    ap.add_argument("--agent-retry-delay", type=float, default=2.0,
                    help="调查/应用失败的指数退避起点（秒，上限 300 秒）")
    args = ap.parse_args()
    if args.task_queue_cap < 1:
        ap.error("--task-queue-cap must be positive")
    if not math.isfinite(args.agent_retry_delay) or args.agent_retry_delay < 0:
        ap.error("--agent-retry-delay must be finite and non-negative")

    service = build_default_service(args.project, model=args.model, task_capacity=args.task_queue_cap)
    service.trio_mode = resolve_pipeline() != "legacy"
    if not service.trio_mode:
        from .legacy import warn_once  # P1：§2.11 legacy 启动提示（唯一新增行，行为不变）
        warn_once()
    service.start_unit_recovery()  # 即使 --no-agent，已提交 L0 也必须能恢复
    httpd = serve(service, args.port)
    port = httpd.server_address[1]

    agent = None
    if not args.no_agent and not service.trio_mode:
        from .legacy.inline import InlineInvestigator
        from .legacy.investigator import Budget
        from .legacy.loop import AgentWorker
        key = _load_env_key(Path(args.project))
        if not key:
            print("[memory-sidecar] 调查员未启动: ZAI_API_KEY 未设置",
                  file=sys.stderr, flush=True)
        else:
            # 进程内 function-calling 循环，不经 HTTP
            inv = InlineInvestigator(service, model=args.agent_model, api_key=key)
            agent = AgentWorker(service, inv, daily_cap=args.agent_daily_cap,
                                retry_delay_s=args.agent_retry_delay,
                                budget=Budget(tool_calls=args.agent_tool_calls,
                                              window_chars=args.agent_window_chars))
            service.attach_agent(agent)
            agent.start()

    trio = None
    if service.trio_mode and not args.no_agent:
        from .agent.trio import TrioWorker, OpenCodeRunner
        trio = TrioWorker(service, OpenCodeRunner(Path(args.project)))
        service.trio_worker = trio
        trio.start()

    view = service.health_view()
    print(f"[memory-sidecar] http://127.0.0.1:{port} "
          f"project={Path(args.project).resolve()} "
          f"mems={len(service.engine.mems)} log_units={service.log.count()} "
          f"snapshot={view['snapshot']} units_pending={view['units_pending']} "
          f"validation={view['validation']} "
          f"agent={'on' if agent or trio else 'off'}", flush=True)

    def _term(*_):          # 插件 kill 发 SIGTERM：走 finally 存盘
        raise SystemExit(0)

    _signal.signal(_signal.SIGTERM, _term)
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        service.stop_unit_recovery()
        if agent is not None:
            agent.stop()
        if trio is not None:
            trio.stop()
        service.save()
        httpd.server_close()


if __name__ == "__main__":
    main()
