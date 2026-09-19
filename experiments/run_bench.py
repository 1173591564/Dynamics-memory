"""外部基准驱动：LoCoMo / LongMemEval → cand-gen → engine → retrieve → reader 答题。

因果协议：逐 unit 流入（窗口完成后 observe，step 维护），全部流完后
对每个 BenchQuery 独立 retrieve(top-K) → reader LLM 答题 → LLM judge 评分。
检索级 recall 用 selected 记忆的 src（source_unit_ids）∩ evidence_units 度量。

用法：
    python -m experiments.run_bench --dataset locomo --limit 1
    python -m experiments.run_bench --dataset lme --offset 0 --limit 5
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np

from experiments import paths as P
from experiments.real_embedding import load_dotenv_key
from hybrid_memory.candgen import (OpencodeCliGenerator,
                                   priority_to_salience, redact_secrets)
from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Query
from hybrid_memory.datasets.bench import (BenchInstance, load_locomo,
                                          load_longmemeval)
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder
from hybrid_memory.llm import chat
from hybrid_memory.semantics import RealChatSemantics, normalize
from hybrid_memory.datasets.real_chat import build_interaction_windows
from hybrid_memory.worker import SignalWorker

CG_DIR = P.CANDGEN_DIR / "bench-candgen"
DOTENV = Path(".env")

READER_SYS = ("You are answering questions using long-term memory. "
              "Answer concisely based ONLY on the provided memories. "
              "If the memories do not contain the answer, say \"I don't know\".")
JUDGE_SYS = ("You are grading a QA answer. Reply with exactly one word: "
             "CORRECT or WRONG. The prediction is correct if it conveys "
             "the gold answer's meaning; refuse-markers are correct only "
             "when the gold answer is unanswerable/unknown.")


def _gen_or_load(inst: BenchInstance, size: int, stride: int,
                 gen: OpencodeCliGenerator) -> dict[int, list[dict]]:
    """每实例 candgen 缓存：bench-candgen/{ds}-{iid}.jsonl，缺窗才调用 LLM。"""
    windows = build_interaction_windows(list(inst.units), size=size,
                                        stride=stride)
    path = CG_DIR / f"{inst.id}-k{size}.jsonl"
    done: dict[int, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["window_id"]] = rec
    prev_scene = ""
    with path.open("a", encoding="utf-8") as f:
        for w in windows:
            rec = done.get(w.id)
            if rec is None or "error" in rec:
                try:
                    t1 = time.time()
                    g = gen.generate(w, prev_scene)
                    rec = {"window_id": w.id, "scene_name": g.scene_name,
                           "candidates": [{"text": redact_secrets(c.text),
                                           "type": c.type,
                                           "priority": c.priority,
                                           "salience": c.salience,
                                           "source_unit_ids": list(c.source_unit_ids)}
                                          for c in g.candidates]}
                except Exception as exc:  # noqa: BLE001
                    rec = {"window_id": w.id, "error": str(exc)[:300]}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            prev_scene = rec.get("scene_name") or prev_scene
            done[w.id] = rec
    cands = {}
    for w in windows:
        rec = done.get(w.id, {})
        if "error" not in rec:
            scene = str(rec.get("scene_name", ""))
            cands[w.id] = [dict(c, scene=c.get("scene") or scene)
                           for c in rec["candidates"]]
    return cands, windows


def _judge_answer(question: str, gold: str, pred: str, key: str,
                  model: str, cache_dir=None) -> bool:
    if pred is None:
        return False
    try:
        out = chat(api_key=key, model=model, system=JUDGE_SYS,
                   user=f"Question: {question}\nGold answer: {gold}\n"
                        f"Predicted: {pred}\nCorrect?", cache_dir=cache_dir)
        return out.strip().upper().startswith("CORRECT")
    except Exception:  # noqa: BLE001
        return False


def run_instance(inst: BenchInstance, args, emb, key: str,
                 gen: OpencodeCliGenerator) -> dict:
    cands, windows = _gen_or_load(inst, args.size, args.stride, gen)
    semantics = RealChatSemantics(None)
    eng = MemoryEngine(
        Cfg(theta=args.theta, cap_m=args.cap_m, k=args.k,
            tau_dup=args.tau_dup, tau_sim=args.tau_sim, useful_hit=False),
        emb, semantics)
    worker = SignalWorker(eng, semantics)
    n_units = len(inst.units)
    by_avail: dict[int, list] = {}
    for w, rec_c in zip(windows, (cands.get(w.id) for w in windows)):
        if rec_c is None:
            continue
        by_avail.setdefault(w.end_unit_id + 1, []).append(rec_c)

    def _cand_salience(c: dict) -> float:
        sal = c.get("salience")
        if isinstance(sal, bool) or not isinstance(sal, (int, float)):
            return priority_to_salience(c.get("priority"))
        return max(0.0, min(1.0, float(sal)))

    def _observe(rec_c, t):
        evs = [Event(eng.semantics.fingerprint(normalize(c["text"])),
                     normalize(c["text"]), c["text"],
                     tuple(c.get("source_unit_ids") or ()),
                     salience=_cand_salience(c), scene=c.get("scene", ""))
               for c in rec_c]
        eng.observe(evs, t)

    t0 = time.time()
    for t in range(n_units):
        for rec_c in by_avail.get(t, []):
            _observe(rec_c, t)
        eng.step(t)
        worker.process(t)
    # 最后一个窗口恰好在流尾完成：问题在 t=n_units 提出，此时它已可用
    for tt in sorted(k for k in by_avail if k >= n_units):
        for rec_c in by_avail[tt]:
            _observe(rec_c, n_units)
    eng.step(n_units)
    worker.process(n_units)

    qres = []
    for q in inst.queries:
        qv = emb.embed([q.question])[0]
        ret = eng.retrieve(qv, Query(-1, q.question), n_units)
        mems = [m.text for m in ret.selected]
        pred = None
        if not args.no_reader and mems:
            pred = chat(api_key=key, model=args.reader_model,
                        system=READER_SYS,
                        user="Memories:\n" + "\n".join(f"- {m}" for m in mems)
                             + f"\n\nQuestion: {q.question}")
        ev_hit = frozenset().union(*(m.src for m in ret.selected)) \
            & q.evidence_units if ret.selected else frozenset()
        qres.append({
            "qid": q.id, "qtype": q.qtype, "abstention": q.abstention,
            "n_mem": len(mems), "pred": pred,
            "correct": _judge_answer(q.question, q.answer, pred, key,
                                     args.reader_model),
            "evidence_recall": (len(ev_hit) / len(q.evidence_units)
                                if q.evidence_units else None)})

    by_type: dict[str, list[int]] = {}
    for r in qres:
        by_type.setdefault(r["qtype"], []).append(int(r["correct"]))
    return {
        "instance": inst.id, "n_units": n_units, "n_windows": len(windows),
        "n_candidates": sum(len(v) for v in cands.values()),
        "pool_final": eng.pool_sizes(), "tensions_pending": len(eng.tensions),
        "acc": round(np.mean([r["correct"] for r in qres]), 4),
        "acc_by_type": {k: round(float(np.mean(v)), 4)
                        for k, v in by_type.items()},
        "evidence_recall_mean": round(float(np.mean(
            [r["evidence_recall"] for r in qres
             if r["evidence_recall"] is not None])), 4)
            if any(r["evidence_recall"] is not None for r in qres) else None,
        "elapsed_s": round(time.time() - t0, 1),
        "queries": qres,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["locomo", "lme"], required=True)
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--stride", type=int, default=None)
    ap.add_argument("--theta", type=float, default=0.35)
    ap.add_argument("--tau-dup", type=float, default=0.85)
    ap.add_argument("--tau-sim", type=float, default=0.78)
    ap.add_argument("--cap-m", type=int, default=8)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--model", default="zhipu-env/glm-5.3-flash")
    ap.add_argument("--reader-model", default="glm-5.3-flash")
    ap.add_argument("--no-reader", action="store_true")
    ap.add_argument("--max-units", type=int, default=None,
                    help="调试用：截断实例前 N 个 unit")
    ap.add_argument("--dotenv", type=Path, default=DOTENV)
    ap.add_argument("--out-prefix", default=None)
    args = ap.parse_args()

    if args.dataset == "locomo":
        path = args.data or Path("data/bench/locomo10.json")
        insts = load_locomo(path)
        default_k = 15        # turn 级单元小，窗口放大到约一个 session
    else:
        path = args.data or Path("data/bench/longmemeval_s.json")
        insts = load_longmemeval(path)
        default_k = 3
    size = args.size or default_k
    stride = args.stride or size
    args.size, args.stride = size, stride
    selected = insts[args.offset:args.offset + args.limit]

    key = load_dotenv_key(args.dotenv)
    emb = ZhipuEmbedder(api_key=key, cache=SqliteEmbeddingCache(
        P.EMB_CACHE))
    CG_DIR.mkdir(parents=True, exist_ok=True)
    gen = OpencodeCliGenerator(model=args.model,
                               scratch_dir=P.SCRATCH,
                               env_extra={"ZAI_API_KEY": key})

    results = []
    for inst in selected:
        if args.max_units:
            inst = BenchInstance(inst.id, inst.units[:args.max_units],
                                 inst.unit_sources[:args.max_units],
                                 inst.queries)
        r = run_instance(inst, args, emb, key, gen)
        results.append(r)
        print(f"[{inst.id}] acc={r['acc']} by_type={r['acc_by_type']} "
              f"ev_recall={r['evidence_recall_mean']} pools={r['pool_final']}")

    prefix = args.out_prefix or f"bench-{args.dataset}"
    summary = {"dataset": args.dataset, "n_instances": len(results),
               "size": size, "stride": stride,
               "cfg": {"theta": args.theta, "tau_dup": args.tau_dup,
                       "tau_sim": args.tau_sim, "cap_m": args.cap_m,
                       "k": args.k},
               "acc_mean": round(float(np.mean(
                   [r["acc"] for r in results])), 4),
               "results": results}
    out_path = P.BENCH / f"{prefix}-summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
