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
import math
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


def _probe_record(stream, probe, barrier, snapshot, seen, relevant_units, code, response):
    from eval.l2l3.export import _served_text
    from tide.score import score_context
    from tide.text import has_token

    ctx = _served_text(response) if code == 200 else ""
    gold, harmful = probe["gold"], probe["harmful"]
    visible = [m for m in snapshot["mems"] if m["visible"]]
    present = {v: [m["id"] for m in visible if has_token(m["text"], v)] for v in gold + harmful}
    missing = [v for v in gold if not present[v]]
    failed = [t for t in snapshot["tasks"] if t["state"] == "dead" and t.get("unit_id") in relevant_units]
    if not barrier.get("drained"):
        pipeline = "not_ready"
    elif missing:
        pipeline = "write_failed" if failed else "not_distilled"
    elif not gold and (not harmful or not all(v in seen for v in harmful)):
        pipeline = "unexercised_retraction"
    else:
        pipeline = "ready"
    eligible = pipeline == "ready" and code == 200
    score = score_context(ctx, gold, harmful) if code == 200 else {}
    retrieval = ("http_error" if code is not None and code != 200 else "not_testable")
    if eligible:
        retrieval = ("harmful" if score["H"] else "clean" if not gold
                     else "hit" if score["S"] == 1 else "miss")
    return {"stream": stream, "probe": probe["id"], "t": probe["t"],
            "dimension": probe["dimension"], "knob": probe["knob"],
            "scenario": probe.get("scenario", "configuration"),
            "http": code, "context": ctx, "response": response,
            "gold": gold, "harmful": harmful, "barrier": barrier,
            "snapshot_revision": snapshot["revision"], "memory_matches": present,
            "missing_gold": missing, "failed_tasks": failed,
            "harmful_previously_visible": sorted(set(harmful) & seen),
            "pipeline_status": pipeline, "retrieval_status": retrieval,
            "eligible": eligible, **score}


def run_chain(corpus: dict, project: str, out_dir: str, *,
              env_extra: dict | None = None, drain_timeout: float = 1800.0,
              with_probes: bool = True, budget: int = 128,
              resume: bool = False, quiet_s: float = 0.5) -> dict:
    from eval.l2l3.export import export_run, read_snapshot
    from eval.l2l3.sidecar import Sidecar
    from tide.text import has_token

    if not math.isfinite(drain_timeout) or drain_timeout <= 0 or not math.isfinite(quiet_s) or quiet_s < 0:
        raise ValueError("invalid barrier timeout or quiet interval")
    if corpus.get("kind") == "l2":
        for st in corpus["streams"]:
            if [t["t"] for t in st["turns"]] != list(range(len(st["turns"]))):
                raise ValueError("L2 turns must be consecutive from zero")
            if any(type(p["t"]) is not int or not 0 <= p["t"] <= len(st["turns"]) for p in st["probes"]):
                raise ValueError("probe boundary outside stream")
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
    if not resume and out.exists() and any(out.iterdir()):
        raise ValueError("output directory must be empty; old evidence cannot be overwritten")
    out.mkdir(parents=True, exist_ok=True)

    env_extra = dict(env_extra or {})
    module = ("eval.l2l3.serve_inline" if env_extra.pop(
        "_use_inline", False) else "hybrid_memory.server")
    t0 = time.time()
    sc = Sidecar(_REPO, str(project_p), env=env_extra,
                 module=module).start()
    boot_s = round(time.time() - t0, 1)
    probe_records: list[dict] = []
    barriers: list[dict] = []
    status = "drained"
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
                seen: set[str] = set()
                fed: list[tuple[int, str]] = []
                values = {v for p in st["probes"] for v in p["gold"] + p["harmful"]}
                for p in st["probes"]:
                    by_t.setdefault(p["t"], []).append(p)
                barrier = {"drained": True}
                snapshot = {"revision": 0, "mems": [], "tasks": []}
                for boundary in range(len(st["turns"]) + 1):
                    for p in by_t.get(boundary, []):
                        relevant = {uid for uid, text in fed if any(has_token(text, v) for v in p["gold"] + p["harmful"])}
                        code, resp = sc.search(p["query"], budget_tokens=budget, passive=True) if barrier["drained"] else (None, {})
                        probe_records.append(_probe_record(st["id"], p, barrier, snapshot, seen, relevant, code, resp))
                    seen.update(v for v in values if any(m["visible"] and has_token(m["text"], v) for m in snapshot["mems"]))
                    (out / "run.json").write_text(json.dumps({
                        "corpus_kind": corpus["kind"], "fed_turns": n_fed,
                        "probe_validity": "causal-barrier", "probe_records": probe_records,
                        "barriers": barriers, "status": "running" if barrier["drained"] else "barrier_timeout",
                        "drain": barrier}, ensure_ascii=False, indent=1), encoding="utf-8")
                    if not barrier["drained"]:
                        status = "barrier_timeout"
                        break
                    if boundary == len(st["turns"]):
                        break
                    turn = st["turns"][boundary]
                    code, body = sc.observe(turn["user"], turn["assistant"], request_id=f"{st['id']}:t{turn['t']}")
                    assert code == 200, f"observe -> {code}: {body}"
                    n_fed += 1
                    fed.append((body["unit_id"], turn["user"] + "\n" + turn["assistant"]))
                    started = time.monotonic()
                    barrier = sc.drain(timeout=drain_timeout, quiet_s=quiet_s)
                    snapshot = read_snapshot(str(project_p))
                    barriers.append({"stream": st["id"], "after_t": boundary,
                                     "unit_id": body["unit_id"], "wait_s": time.monotonic() - started,
                                     "snapshot_revision": snapshot["revision"], **barrier})
                if status == "barrier_timeout":
                    break
        else:
            for rid, user, assistant in _iter_turns(corpus):
                code, body = sc.observe(user, assistant, request_id=rid)
                assert code == 200, f"observe -> {code}: {body}"
                n_fed += 1
        drain = barriers[-1] if barriers else sc.drain(timeout=drain_timeout)
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
           "probe_validity": "resume-preserved" if resume else "causal-barrier" if barriers else "not-probed",
           "status": status if drain.get("drained") else "barrier_timeout",
           "barriers": barriers, "drain": drain, "probe_records": probe_records,
           "unissued_probes": [{"stream": st["id"], "probe": p["id"], "t": p["t"]}
                               for st in corpus.get("streams", []) for p in st["probes"]
                               if with_probes and not any(r.get("stream") == st["id"] and r.get("probe") == p["id"] for r in probe_records)],
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
    ap.add_argument("--quiet-seconds", type=float, default=0.5)
    ap.add_argument("--no-probes", action="store_true")
    ap.add_argument("--agent-provider", choices=("glm", "deepseek"))
    ap.add_argument("--capture-dir")
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
    if args.inline or args.agent_provider:
        env_extra["_use_inline"] = True
    if args.agent_provider:
        env_extra["L2L3_AGENT_PROVIDER"] = args.agent_provider
    if args.capture_dir:
        env_extra["L2L3_CAPTURE_DIR"] = str(Path(args.capture_dir).resolve())
    if os.environ.get("L2L3_PATH_PREPEND"):
        pp = os.environ["L2L3_PATH_PREPEND"]
        env_extra["PATH"] = pp + os.pathsep + os.environ.get("PATH", "")
    run = run_chain(corpus, args.project, args.out_dir,
                    env_extra=env_extra or None,
                    drain_timeout=args.drain_timeout,
                    with_probes=not args.no_probes, budget=args.budget,
                    resume=args.resume, quiet_s=args.quiet_seconds)
    print(json.dumps(run, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
