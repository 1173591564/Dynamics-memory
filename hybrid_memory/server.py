"""记忆引擎 sidecar：把 MemoryEngine HTTP 服务化，供 opencode 插件调用。

端点（JSON）：
  GET  /health              → 状态（池规模/时间步）
  POST /observe             → {user_text, assistant_text} 捕获一轮交互
                              （先 candgen 蒸馏，仅蒸馏产物进池）
  GET  /recall?q=..&k=..    → {retrieval_id, context, selected}
  POST /feedback            → {retrieval_id, question, answer} 延迟记账
  GET  /conflicts           → 未决 tension 列表
  POST /resolve             → {left, right, verdict} 裁决回报
  POST /search              → {query, k} 主动检索（工具通道）
  POST /save                → 落盘状态快照

状态：内存引擎 + <project>/.opencode/memory/state.pkl 快照（启动加载、
/save 与退出时保存）。依赖注入（cfg/emb/semantics/generator）便于测试。
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .candgen.base import CandidateGenerator
from .candgen.chat import ChatGenerator
from .config import Cfg
from .core.engine import MemoryEngine
from .core.types import Event, Query, Retrieval
from .datasets.real_chat import InteractionUnit, InteractionWindow
from .embed.base import Embedder
from .llm import chat
from .semantics import normalize
from .semantics.llm import LLMSemantics
from .worker import SignalWorker

_RETRIEVAL_KEEP = 512   # retrieval 注册表上限（feedback 用，防无界增长）

_COUNTERS = ("n_promote", "n_demote", "n_evict", "n_archive", "n_revive",
             "n_merge", "n_collision", "n_tension", "n_resolve", "n_agg",
             "n_consolidate")


class MemoryService:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics, generator:
                 CandidateGenerator, state_dir: Path | None = None):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.generator = generator
        self.engine = MemoryEngine(cfg, emb, semantics)
        self.worker = SignalWorker(self.engine, semantics)
        self.state_path = (Path(state_dir) / "state.pkl"
                           if state_dir else None)
        self._lock = threading.RLock()
        self._t = 0
        self._unit_id = 0
        self._scene = ""
        self._retrievals: dict[int, Retrieval] = {}
        self._next_retrieval = 0
        if self.state_path and self.state_path.exists():
            self._load()

    # ---- 引擎操作 ----
    def observe(self, user_text: str, assistant_text: str) -> dict:
        unit = InteractionUnit(id=self._unit_id, start_time=self._t,
                               end_time=self._t, user_text=user_text,
                               assistant_text=assistant_text,
                               assistant_turns=1)
        window = InteractionWindow(id=self._unit_id, start_unit_id=self._unit_id,
                                   end_unit_id=self._unit_id,
                                   start_time=self._t, end_time=self._t,
                                   units=(unit,))
        self._unit_id += 1
        gen = self.generator.generate(window, self._scene)
        self._scene = gen.scene_name or self._scene
        evs = [Event(self.semantics.fingerprint(normalize(c.text)),
                     normalize(c.text), c.text, c.source_unit_ids,
                     salience=c.salience, scene=self._scene)
               for c in gen.candidates]
        with self._lock:
            if evs:
                self.engine.observe(evs, self._t)
            self.engine.step(self._t)
            wstats = self.worker.process(self._t)
            self._t += 1
            pool = self.engine.pool_sizes()
        return {"candidates": len(evs), "scene": self._scene, "pool": pool,
                "t": self._t, "worker": wstats}

    def _format_context(self, ret: Retrieval) -> str:
        prov_ids = {m.id for m in ret.provisional}
        lines = []
        for m in ret.selected:
            lines.append(
                f"- {'[未确认] ' if m.id in prov_ids else ''}"
                f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
                f"[t={m.birth}] {m.text}")
        for m, rival in ret.contested:
            lines.append(f"- ⚠️未决冲突：[t={rival.birth}] {rival.text}"
                         f"（与 t={m.birth} 条目冲突）")
        return "\n".join(lines)

    def recall(self, q: str, k: int | None = None) -> dict:
        qv = self.emb.embed([q])[0]
        with self._lock:
            if k is not None:
                old_k, self.cfg.k = self.cfg.k, k
                try:
                    ret = self.engine.retrieve(qv, Query(-1, q), self._t)
                finally:
                    self.cfg.k = old_k
            else:
                ret = self.engine.retrieve(qv, Query(-1, q), self._t)
            rid = self._next_retrieval
            self._next_retrieval += 1
            self._retrievals[rid] = ret
            while len(self._retrievals) > _RETRIEVAL_KEEP:
                self._retrievals.pop(min(self._retrievals))
            return {"retrieval_id": rid, "context": self._format_context(ret),
                    "n": len(ret.selected),
                    "selected": [{"id": m.id, "text": m.text,
                                  "birth": m.birth, "kind": m.kind}
                                 for m in ret.selected]}

    def feedback(self, retrieval_id: int, question: str, answer: str) -> dict:
        with self._lock:
            ret = self._retrievals.get(retrieval_id)
            if ret is None:
                return {"error": f"unknown retrieval_id {retrieval_id}"}
            self.engine.feedback(ret, question, answer, self._t)
            self.worker.process(self._t)   # 排空 feedback_pending 等信号
            return {"n_useful": ret.n_useful}

    def conflicts(self) -> dict:
        with self._lock:
            out = []
            for (left, right), tension in self.engine.tensions.items():
                a, b = self.engine.mems.get(left), self.engine.mems.get(right)
                out.append({
                    "left": left, "right": right,
                    "left_text": a.text if a else None,
                    "right_text": b.text if b else None,
                    "first_seen": tension.first_seen,
                    "observations": tension.observations})
            return {"conflicts": out, "t": self._t}

    def resolve(self, left: int, right: int, verdict: str) -> dict:
        with self._lock:
            n = self.engine.submit_verdicts([(left, right, verdict)], self._t)
            return {"resolved": n, "t": self._t}

    def save(self) -> dict:
        if self.state_path is None:
            return {"saved": False, "reason": "no state_dir"}
        state = {
            "mems": self.engine.mems, "tensions": self.engine.tensions,
            "next_id": self.engine._next_id,
            "consolidation_pending": self.engine._consolidation_pending,
            "consolidation_deferred": self.engine._consolidation_deferred,
            "counters": {k: getattr(self.engine, k) for k in _COUNTERS},
            "t": self._t, "unit_id": self._unit_id, "scene": self._scene}
        with self._lock:
            tmp = self.state_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump(state, f)
            os.replace(tmp, self.state_path)
        return {"saved": True, "mems": len(self.engine.mems)}

    def _load(self) -> None:
        with open(self.state_path, "rb") as f:
            state = pickle.load(f)
        eng = self.engine
        eng.mems = state["mems"]
        eng.tensions = state["tensions"]
        eng._next_id = state["next_id"]
        eng._consolidation_pending = state["consolidation_pending"]
        eng._consolidation_deferred = state["consolidation_deferred"]
        for k, v in state["counters"].items():
            setattr(eng, k, v)
        self._t = state["t"]
        self._unit_id = state["unit_id"]
        self._scene = state["scene"]


# ============================ HTTP ============================

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

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _dispatch(self, path: str, q: dict, body: dict) -> None:
        svc = self.service
        if path == "/health":
            self._reply(200, {"ok": True, "t": svc._t,
                              "mems": svc.engine.pool_sizes(),
                              "tensions": len(svc.engine.tensions)})
        elif path == "/recall":
            self._reply(200, svc.recall(q.get("q", ""),
                                        int(q["k"]) if q.get("k") else None))
        elif path == "/conflicts":
            self._reply(200, svc.conflicts())
        elif path == "/observe":
            self._reply(200, svc.observe(body.get("user_text", ""),
                                         body.get("assistant_text", "")))
        elif path == "/feedback":
            self._reply(200, svc.feedback(int(body.get("retrieval_id", -1)),
                                          body.get("question", ""),
                                          body.get("answer", "")))
        elif path == "/resolve":
            self._reply(200, svc.resolve(int(body.get("left", -1)),
                                         int(body.get("right", -1)),
                                         str(body.get("verdict", "pending"))))
        elif path == "/search":
            self._reply(200, svc.recall(body.get("query", ""),
                                        body.get("k")))
        elif path == "/save":
            self._reply(200, svc.save())
        else:
            self._reply(404, {"error": f"no such path: {path}"})

    def do_GET(self) -> None:    # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            self._dispatch(u.path, q, {})
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self) -> None:   # noqa: N802
        u = urlparse(self.path)
        try:
            self._dispatch(u.path, {}, self._body())
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})


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
    env_file = project_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ZAI_API_KEY="):
                return (line.split("=", 1)[1].strip()
                        .strip('"').strip("'") or None)
    return None


def build_default_service(project_dir: str | Path,
                          model: str = "glm-5.3-flash") -> MemoryService:
    from .embed.cache import SqliteEmbeddingCache
    from .embed.zhipu import ZhipuEmbedder

    mem_dir = Path(project_dir) / ".opencode" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    key = _load_env_key(Path(project_dir))

    def chat_fn(system: str, user: str) -> str:
        return chat(api_key=key, model=model, system=system, user=user,
                    cache_dir=mem_dir / "chat-cache")

    emb = ZhipuEmbedder(api_key=key,
                        cache=SqliteEmbeddingCache(mem_dir / "emb.sqlite3"))
    semantics = LLMSemantics(None, chat_fn=chat_fn, model=model)
    cfg = Cfg(theta=0.35, cap_m=8, k=5, tau_dup=0.85, tau_sim=0.78,
              useful_hit=True, defer_credit=True)
    return MemoryService(cfg, emb, semantics, ChatGenerator(chat_fn),
                         state_dir=mem_dir)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=17872)
    ap.add_argument("--project", default=".")
    ap.add_argument("--model", default="glm-5.3-flash")
    args = ap.parse_args()

    service = build_default_service(args.project, model=args.model)
    httpd = serve(service, args.port)
    print(f"[memory-sidecar] http://127.0.0.1:{args.port} "
          f"project={Path(args.project).resolve()} "
          f"mems={len(service.engine.mems)}", flush=True)
    try:
        httpd.serve_forever()
    finally:
        service.save()
        httpd.server_close()


if __name__ == "__main__":
    main()
