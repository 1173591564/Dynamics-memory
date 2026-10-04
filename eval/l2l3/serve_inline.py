"""L2/L3 抽检用的 sidecar 组装入口（进程内 agent runner 版）。

与 transport/bootstrap.py 的组装保持逐段对照（build_default_service →
resolve_pipeline/Fatal → trio_mode → start_unit_recovery → DispatchWorker
→ transport.http.serve → 打印端口行）；差异仅一处：trio runner 用
InlineAgentRunner（协议等价、无 CLI 子进程；理由见 inline_runner.py 模块
docstring 与 N50）。bootstrap 变更时必须同步对照本文件。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("MEMORY_PROJECT", "."))
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--model", default=os.environ.get("MEMORY_AGENT_MODEL",
                                                      "glm-5.3-flash"))
    ap.add_argument("--task-queue-cap", type=int, default=4096)
    args = ap.parse_args()

    from hybrid_memory.config import resolve_pipeline
    from hybrid_memory.dispatch.worker import DispatchWorker
    from hybrid_memory.errors import Fatal
    from hybrid_memory.transport.bootstrap import build_default_service
    from hybrid_memory.transport.http import serve

    service = build_default_service(args.project, model=args.model,
                                    task_capacity=args.task_queue_cap)
    try:
        pipeline = resolve_pipeline()
    except ValueError as exc:
        raise Fatal(str(exc)) from exc
    service.trio_mode = pipeline != "legacy"
    service.start_unit_recovery()
    trio = None
    if service.trio_mode:
        from eval.l2l3.inline_runner import InlineAgentRunner
        trio = DispatchWorker(service, InlineAgentRunner(model=args.model))
        service.attach_dispatch(trio)
        trio.start()
    httpd = serve(service, args.port)
    port = httpd.server_address[1]
    view = service.health_view()
    print(f"[memory-sidecar] http://127.0.0.1:{port} "
          f"project={Path(args.project).resolve()} "
          f"mems={len(service.engine.mems)} log_units={service.log.count()} "
          f"trio=inline-ok={view['ok']} pid={os.getpid()} ", flush=True)

    def _term(*_):            # 与 bootstrap 同：SIGTERM 走 finally 存盘
        raise SystemExit(0)

    import signal as _signal
    _signal.signal(_signal.SIGTERM, _term)
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        service.stop_unit_recovery()
        if trio is not None:
            trio.stop()
        service.save()
        httpd.server_close()


if __name__ == "__main__":
    main()
