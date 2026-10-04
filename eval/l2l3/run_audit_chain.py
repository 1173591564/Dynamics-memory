"""跑链编排：语料 → 原版 sidecar 子进程（真实产品路径）→ 探针判分 →
任务排空 → 只读导出。一条链一次进程，互不污染。

用法（真实跑）：
  ZAI_API_KEY=sk-... PATH=/path/to/opencode-bin:$PATH \
    python -m eval.l2l3.run_audit_chain --corpus l2_corpus.json \
      --project /home/user/l2l3-data/proj-l2 --out-dir /home/user/l2l3-data/runs/l2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_REPO = str(Path(__file__).resolve().parents[2])
_EVAL = str(Path(__file__).resolve().parents[1])
for _p in (_REPO, _EVAL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

def _iter_turns(corpus: dict):
    """L2 按流分组保序；L3 单序列。产出 (request_id, user, assistant)。"""
    if corpus.get("kind") == "l2":
        for st in corpus["streams"]:
            for turn in st["turns"]:
                yield f"{st['id']}:t{turn['t']}", turn["user"], turn["assistant"]
    else:
        for turn in corpus["turns"]:
            # request_id 守卫要求 8–80 字符的 [A-Za-z0-9._:-]
            yield f"l3-turn-{turn['t']:04d}", turn["user"], turn["assistant"]


def run_chain(corpus: dict, project: str, out_dir: str, *,
              env_extra: dict | None = None, drain_timeout: float = 1800.0,
              with_probes: bool = True, budget: int = 128,
              resume: bool = False) -> dict:
    from eval.l2l3.export import _served_text, export_run
    from eval.l2l3.sidecar import Sidecar
    from tide.score import score_context

    project_p = Path(project)
    if resume:
        # 续跑：目录必须已有状态（L0 落库、任务在库），跳过喂轮直接排空。
        if not (project_p / ".opencode" / "memory" / "tasks.sqlite").exists():
            raise RuntimeError(f"resume 需要既有项目目录：{project}")
    else:
        if project_p.exists() and any(project_p.iterdir()):
            raise RuntimeError(f"project 目录非空：{project}（每链一次干净运行；"
                               "续跑用 --resume）")
        project_p.mkdir(parents=True, exist_ok=True)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    env_extra = dict(env_extra or {})
    module = ("eval.l2l3.serve_inline" if env_extra.pop(
        "_use_inline", False) else "hybrid_memory.server")
    t0 = time.time()
    sc = Sidecar(_REPO, str(project_p), env=env_extra,
                 module=module).start()
    boot_s = round(time.time() - t0, 1)
    probe_records: list[dict] = []
    if resume:
        for name in ("run.json", "run.json.first-pass"):
            previous = out / name
            if previous.exists():
                probe_records = json.loads(previous.read_text(encoding="utf-8")).get("probe_records") or []
                if probe_records:
                    break
    try:
        n_fed = 0
        if resume:
            pass            # 续跑：不喂轮（L0 幂等，任务已在库）
        # L2：按流喂；流内第 t 轮喂入前先放该时点的探针（passive /search）
        elif corpus.get("kind") == "l2" and with_probes:
            for st in corpus["streams"]:
                by_t: dict[int, list] = {}
                for p in st["probes"]:
                    by_t.setdefault(p["t"], []).append(p)
                for turn in st["turns"]:
                    for p in by_t.get(turn["t"], []):
                        st_code, resp = sc.search(
                            p["query"], budget_tokens=budget, passive=True)
                        ctx = _served_text(resp)
                        rec = {"stream": st["id"], "probe": p["id"],
                               "dimension": p["dimension"], "knob": p["knob"],
                               "http": st_code, "context": ctx[:600]}
                        rec.update(score_context(ctx, p["gold"], p["harmful"]))
                        probe_records.append(rec)
                    code, body = sc.observe(
                        turn["user"], turn["assistant"],
                        request_id=f"{st['id']}:t{turn['t']}")
                    assert code == 200, f"observe -> {code}: {body}"
                    n_fed += 1
        else:
            for rid, user, assistant in _iter_turns(corpus):
                code, body = sc.observe(user, assistant, request_id=rid)
                assert code == 200, f"observe -> {code}: {body}"
                n_fed += 1
        drain = sc.drain(timeout=drain_timeout)
    finally:
        tail = sc.close()
    (out / "sidecar_tail.log").write_text(tail, encoding="utf-8")

    # export 在评测进程内原位重开服务（ZhipuEmbedder 等仍按环境取端点/密钥），
    # 与 sidecar 同一套 env，避免 mock/真实端点在导出期漂移。
    _saved_env = {k: os.environ[k] for k in env_extra if k in os.environ}
    os.environ.update(env_extra or {})
    try:
        export = export_run(_REPO, str(project_p), out / "export.json")
    finally:
        for k, v in _saved_env.items():
            os.environ[k] = v
        for k in (env_extra or {}):
            if k not in _saved_env:
                os.environ.pop(k, None)
    run = {"corpus_kind": corpus.get("kind"), "project": str(project_p),
           "fed_turns": n_fed, "boot_s": boot_s,
           "runner": "inline" if module.endswith("serve_inline") else "opencode",
           "probe_validity": "pre-drain-unverified",
           "drain": drain, "probe_records": probe_records,
           "mems": len(export["mems"]), "units": len(export["units"]),
           "selector_done": sum(1 for t in export["tasks"]
                                if t["kind"] == "selector_due"
                                and t["state"] == "done")}
    (out / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    return run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--drain-timeout", type=float, default=1800.0)
    ap.add_argument("--budget", type=int, default=128)
    ap.add_argument("--no-probes", action="store_true")
    ap.add_argument("--inline", action="store_true",
                    help="进程内 agent runner（协议等价；小内存沙箱用，"
                         "真实 CLI 通道由 N48/冒烟覆盖）")
    ap.add_argument("--resume", action="store_true",
                    help="续跑既有项目目录：跳过喂轮，直接排空剩余任务")
    ap.add_argument("--stream-id", action="append", default=None,
                    help="只跑指定流（可多次）；按流并行时每进程一条流")
    args = ap.parse_args()
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if args.stream_id and corpus.get("kind") == "l2":
        want = set(args.stream_id)
        corpus["streams"] = [st for st in corpus["streams"] if st["id"] in want]
    env_extra = {}
    if args.inline:
        env_extra["_use_inline"] = True
    if os.environ.get("L2L3_PATH_PREPEND"):
        pp = os.environ["L2L3_PATH_PREPEND"]
        env_extra["PATH"] = pp + os.pathsep + os.environ.get("PATH", "")
    run = run_chain(corpus, args.project, args.out_dir,
                    env_extra=env_extra or None,
                    drain_timeout=args.drain_timeout,
                    with_probes=not args.no_probes, budget=args.budget,
                    resume=args.resume)
    print(json.dumps(run, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
