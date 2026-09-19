"""连续工作流续话评测：用 log 中真实发生的后续提问做因果约束测试。

协议：因果回放到时点 t，用该 unit 的真实 user_text 当考题——
  memory 组：retrieve top-K → reader 作答
  flat  组：raw unit 文本向量检索 top-K → reader 作答
  none  组：只有问题本身 → reader 作答
judge 以该 unit 的真实助理回复为参照，按"项目状态感知"rubric 打 1-5 分。

度量的是"新对话里用户要重建多少上下文"：memory 组若工作正常，
应表现出知道进度、不问已解决的事、不编造状态——而非复述细节。

用法：
    python -m experiments.qa_continuity --allow-remote
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from experiments import paths as P
from experiments.dynamics_v3 import FEATURE_SETS, configure, diagnostics
from experiments.qa_real import _load_candgen
from experiments.real_embedding import load_dotenv_key
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Query
from hybrid_memory.datasets.real_chat import (build_interaction_windows,
                                              load_interaction_units)
from hybrid_memory.embed.base import cosine
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder
from hybrid_memory.llm import chat
from hybrid_memory.semantics import RealChatSemantics, normalize
from hybrid_memory.semantics.llm import LLMSemantics
from hybrid_memory.semantics.opencode import OpencodeSemantics

DATA = P.DATA_REAL
CANDGEN = P.CANDGEN_DIR / "real-candgen-k3-s3-v2.jsonl"
CHAT_CACHE = P.CHAT_CACHE
DOTENV = Path(".env")

READER_SYS = ("你在协助一个进行中的工程项目。根据给出的记忆回答问题。"
              "标为[未确认]的条目只能作为线索，不得作为确定结论；"
              "未决冲突必须同时说明版本与时间，不得擅自裁决。"
              "不知道的事不要编造，可以说不确定。用中文简洁回答。")
JUDGE_SYS = (
    "你在评测一个 agent 对项目历史/状态的感知能力。给定用户的真实问题、"
    "当时真实助理的回复（参照，代表该时点可知的信息），以及待评回答。"
    "按 1-5 打分：\n"
    "5=完全展现了正确的项目状态感知（知道进度/不提已解决问题/不编造）；\n"
    "4=基本正确，小遗漏；3=部分感知但含含糊或一处事实错误；\n"
    "2=几乎无项目感知（泛泛而谈/要求用户提供已说过的信息）；\n"
    "1=编造了与事实冲突的项目状态。\n"
    "只回复一行：SCORE:<数字>，可跟一句简短理由。")

_NOISE = {"继续", "开工", "看看", "嗯", "好", "可以"}


def _unit_text(u) -> str:
    return u.user_text + "\n" + u.assistant_text


def _pick_eval_points(units, start: int, stride: int) -> list[int]:
    pts = []
    for i, u in enumerate(units):
        if i < start or (i - start) % stride:
            continue
        txt = u.user_text.strip()
        if len(txt) < 20 or txt in _NOISE:
            continue
        pts.append(i)
    return pts


def _judge(question: str, reference: str, pred: str, key: str,
           model: str) -> tuple[int | None, str]:
    try:
        out = chat(api_key=key, model=model, system=JUDGE_SYS,
                   cache_dir=CHAT_CACHE,
                   user=f"用户问题：{question}\n\n"
                        f"参照（当时真实助理回复，截断）：\n{reference[:1200]}\n\n"
                        f"待评回答：\n{pred or '(空)'}")
        m = re.search(r"(?:SCORE|得分|评分|分数)[:：]?\s*([1-5])", out,
                      re.IGNORECASE)
        if m is None:
            m = re.search(r"\b([1-5])\s*[/分]", out)
        return (int(m.group(1)) if m else None), out.strip()[:200]
    except Exception as exc:  # noqa: BLE001
        return None, f"judge-error: {exc}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--candgen", type=Path, default=CANDGEN)
    ap.add_argument("--labels", type=Path, default=P.QA / "tension_labels.jsonl")
    ap.add_argument("--dotenv", type=Path, default=DOTENV)
    ap.add_argument("--theta", type=float, default=0.35)
    ap.add_argument("--cap-m", type=int, default=8)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--tau-dup", type=float, default=0.85)
    ap.add_argument("--tau-sim", type=float, default=0.78)
    ap.add_argument("--lex-weight", type=float, default=0.0,
                    help="词法召回通道权重（LongMemEval key-expansion 等价物）")
    ap.add_argument("--reader-model", default="glm-5.3-flash")
    ap.add_argument("--eval-start", type=int, default=25)
    ap.add_argument("--eval-stride", type=int, default=5)
    ap.add_argument("--max-units", type=int, default=0,
                    help="只回放前 N 个 unit（0=全部；端到端冒烟用）")
    ap.add_argument("--size", type=int, default=3, help="窗口大小（须与 candgen 一致）")
    ap.add_argument("--stride", type=int, default=3, help="窗口步长（须与 candgen 一致）")
    ap.add_argument("--groups", default="memory,flat,none")
    ap.add_argument("--flat-chars", type=int, default=400)
    ap.add_argument("--llm-judge", action="store_true",
                    help="tension 裁决走 LLM")
    ap.add_argument("--opencode", action="store_true",
                    help="LLM 裁判走 opencode agent 壳（需 --llm-judge）")
    ap.add_argument("--opencode-model", default="zhipu-env/glm-5.3-flash",
                    help="opencode 侧模型（provider/model 格式）")
    ap.add_argument("--opencode-strict", action="store_true",
                    help="opencode 裁判失败即中止（默认降级并计数）")
    ap.add_argument("--feedback", action="store_true",
                    help="延迟记账：recognizer 按回答判 useful-hit")
    ap.add_argument("--feature-set", choices=tuple(FEATURE_SETS), default="p01")
    ap.add_argument("--allow-remote", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out-prefix", default="qa-continuity")
    args = ap.parse_args()
    if args.allow_remote == args.offline:
        raise SystemExit("choose exactly one of --allow-remote or --offline")
    if args.feature_set == "r1234_full" and not args.llm_judge:
        raise SystemExit("r1234_full requires --llm-judge for consolidation")
    if args.feedback and not args.llm_judge:
        raise SystemExit(
            "--feedback requires --llm-judge（否则 recognizer 缺失，"
            "静默退化为 selected-hit 全记，strict 记账失效）")
    if args.opencode and not args.llm_judge:
        raise SystemExit("--opencode requires --llm-judge")
    if args.opencode and args.offline:
        raise SystemExit("--opencode 无法离线运行（CLI 需要远端）")

    units = load_interaction_units(args.data)
    if args.max_units:
        units = units[: args.max_units]
    windows = build_interaction_windows(units, size=args.size,
                                        stride=args.stride)
    candgen = _load_candgen(args.candgen)
    eval_pts = _pick_eval_points(units, args.eval_start, args.eval_stride)
    groups = args.groups.split(",")

    key = None if args.offline else load_dotenv_key(args.dotenv)
    emb = ZhipuEmbedder(api_key=key, cache=SqliteEmbeddingCache(
        P.EMB_CACHE), offline=args.offline)
    if args.llm_judge and args.opencode:
        semantics = OpencodeSemantics(
            args.labels, model=args.opencode_model, cache_dir=CHAT_CACHE,
            env_extra={"ZAI_API_KEY": key}, strict=args.opencode_strict)
    elif args.llm_judge:
        semantics = LLMSemantics(args.labels, model=args.reader_model,
                                 cache_dir=CHAT_CACHE, api_key=key)
    else:
        semantics = RealChatSemantics(args.labels)
    cfg = configure(
        Cfg(theta=args.theta, cap_m=args.cap_m, k=args.k,
            tau_dup=args.tau_dup, tau_sim=args.tau_sim,
            lex_weight=args.lex_weight,
            useful_hit=args.feedback, defer_credit=args.feedback),
        args.feature_set)
    eng = MemoryEngine(cfg, emb, semantics)

    by_avail: dict[int, list] = defaultdict(list)
    for w in windows:
        if w.id in candgen:
            by_avail[w.end_unit_id + 1].append(w.id)

    def _observe(wid: int, t: int) -> None:
        evs = [Event(eng.semantics.fingerprint(normalize(c["text"])),
                     normalize(c["text"]), c["text"], c["src"],
                     salience=c["salience"], scene=c["scene"])
               for c in candgen[wid]]
        eng.observe(evs, t)

    # flat 基线：raw unit 截断文本的向量检索（只检索 t 之前的 unit）
    flat_texts = [_unit_text(u)[: args.flat_chars] for u in units]
    flat_embs = emb.embed(flat_texts) if "flat" in groups else None

    def _ask(question: str, context: str | None) -> str:
        user = ((f"记忆/上下文：\n{context}\n\n" if context else "")
                + f"问题：{question}")
        return chat(api_key=key, model=args.reader_model,
                    system=READER_SYS, user=user, cache_dir=CHAT_CACHE)

    # 回放阶段只采集各组 context（reader/judge 事后并行打）
    jobs = []   # (t, group, question, context, reference)
    t0 = time.time()
    for t in range(len(units)):
        for wid in by_avail.get(t, []):
            _observe(wid, t)
        qv = emb.embed([units[t].user_text])[0]
        ret = eng.retrieve(qv, Query(-1, units[t].user_text), t)
        pred_mem = None
        if t in eval_pts:
            ref = units[t].assistant_text
            for g in groups:
                if g == "memory":
                    prov_ids = {m.id for m in ret.provisional}
                    lines = [f"- {'[未确认] ' if m.id in prov_ids else ''}"
                             f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
                             f"[t={m.birth}] {m.text}" for m in ret.selected]
                    for m, rv in ret.contested:
                        lines.append(f"- ⚠️未决冲突：[t={rv.birth}] {rv.text}"
                                     f"（与 t={m.birth} 条目冲突）")
                    ctx = "\n".join(lines) if lines else None
                    if args.feedback:
                        # eval 点就地作答，答案回喂 recognizer 保持因果序
                        pred_mem = _ask(units[t].user_text, ctx)
                elif g == "flat":
                    sims = [(cosine(qv, flat_embs[j]), j)
                            for j in range(t)]
                    sims.sort(reverse=True)
                    ctx = "\n---\n".join(
                        flat_texts[j] for _, j in sims[: args.k])
                else:
                    ctx = None
                jobs.append({"t": t, "unit_id": units[t].id,
                             "question": units[t].user_text[:200],
                             "group": g, "ctx": ctx, "ref": ref,
                             "n_mem": len(ret.selected),
                             "n_contested": len(ret.contested),
                             "n_provisional": len(ret.provisional),
                             "n_reflection": sum(
                                 m.kind == "reflection" for m in ret.selected),
                             "pred_inline": (pred_mem if g == "memory"
                                             else None)})
        if args.feedback:
            # 每个 unit 的真实助理回复 = 隐式回答，喂 recognizer；
            # eval 点用就地作答的 pred（feedback 只记一次）
            eng.feedback(ret, units[t].user_text,
                         pred_mem or units[t].assistant_text, t)
        eng.step(t)
    print(f"replay done, {len(jobs)} reader+judge jobs",
          flush=True)

    def _work(job):
        pred = job.get("pred_inline")
        if pred is None:
            try:
                pred = _ask(job["question_full"], job["ctx"])
            except Exception as exc:  # noqa: BLE001
                pred, job["note"] = None, f"reader-error: {exc}"
                job["pred"], job["score"] = pred, None
                return job
        score, note = _judge(job["question_full"], job["ref"], pred,
                             key, args.reader_model)
        job["pred"] = pred
        job["score"] = score
        job["note"] = note
        return job

    for job in jobs:
        job["question_full"] = units[job["t"]].user_text
    with ThreadPoolExecutor(max_workers=8) as ex:
        done = list(ex.map(_work, jobs))
        for job in done:
            print(f"[t={job['t']}] {job['group']}={job['score']}",
                  flush=True)

    # 每行 = (t, group)；结果文件按 t 聚合
    results = []
    by_t: dict[int, dict] = {}
    for job in jobs:
        row = by_t.setdefault(job["t"], {
            "t": job["t"], "unit_id": job["unit_id"],
            "question": job["question"], "n_mem": job["n_mem"],
            "n_contested": job["n_contested"],
            "n_provisional": job["n_provisional"],
            "n_reflection": job["n_reflection"]})
        row[job["group"]] = {"pred": job["pred"], "score": job["score"],
                             "note": job["note"],
                             "ctx": job["ctx"]}
    results = [by_t[t] for t in sorted(by_t)]

    agg = {}
    for g in groups:
        ss = [r[g]["score"] for r in results if r[g]["score"] is not None]
        agg[g] = {"n": len(ss), "mean": round(float(np.mean(ss)), 3),
                  "ge4": round(sum(1 for s in ss if s >= 4)
                               / max(len(ss), 1), 3)}
    summary = {"eval_points": len(results), "groups": agg,
               "pool_final": eng.pool_sizes(),
               "memory_diagnostics": diagnostics(eng),
               "elapsed_s": round(time.time() - t0, 1),
               "feature_set": args.feature_set,
               "features": list(FEATURE_SETS[args.feature_set]),
               "opencode": {"enabled": bool(args.opencode),
                            "failed": getattr(semantics, "n_failed", 0)},
               "cfg": {"theta": args.theta, "cap_m": args.cap_m,
                       "k": args.k}}
    out = P.QA / f"{args.out_prefix}-summary.json"
    out.write_text(json.dumps({"summary": summary, "results": results},
                              ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    n_failed = getattr(semantics, "n_failed", 0)
    if n_failed:
        print(f"⚠ opencode 裁判失败 {n_failed} 次（已走降级路径）——"
              f"本轮结果不可用于质量对比", flush=True)


if __name__ == "__main__":
    main()
