"""进程启动组装（P5 从 server.py 迁入）：嵌入/语义/日志/服务/HTTP/agent 接线。

唯一行为无关替换：请求身份改调 config.load_env_key（canonical 实现，
与旧 server._load_env_key 同逻辑）。
"""
from __future__ import annotations

import argparse
import math
import os
import signal as _signal
import sys
from pathlib import Path

from ..llm import chat
from ..config import Cfg, load_env_key, resolve_pipeline
from ..legacy.candgen import ChatGenerator
from ..logstore import LogStore
from ..semantics.llm import LLMSemantics
from ..service.service import MemoryService
from .http import serve


def build_default_service(project_dir: str | Path,
                          model: str = "glm-5.3-flash",
                          embed_log: bool = True, task_capacity: int = 4096) -> MemoryService:
    from ..embed.cache import SqliteEmbeddingCache
    from ..embed.zhipu import ZhipuEmbedder

    mem_dir = Path(project_dir) / ".opencode" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    # 目录内含 bearer token + 全量记忆语料 + 原始日志：用户项目里通常没有
    # gitignore 覆盖它——自己写一个，防 `git add .` 把 token/state/日志提交进库
    gi = mem_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    key = load_env_key(Path(project_dir))

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
        from ..legacy import warn_once  # P1：§2.11 legacy 启动提示（唯一新增行，行为不变）
        warn_once()
    service.start_unit_recovery()  # 即使 --no-agent，已提交 L0 也必须能恢复
    httpd = serve(service, args.port)
    port = httpd.server_address[1]

    agent = None
    if not args.no_agent and not service.trio_mode:
        from ..legacy.inline import InlineInvestigator
        from ..legacy.investigator import Budget
        from ..legacy.loop import AgentWorker
        key = load_env_key(Path(args.project))
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
        from ..agents.opencode import OpenCodeRunner
        from ..dispatch.worker import DispatchWorker
        trio = DispatchWorker(service, OpenCodeRunner(Path(args.project)))
        service.attach_dispatch(trio)
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
