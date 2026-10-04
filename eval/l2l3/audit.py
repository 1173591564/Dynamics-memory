"""抽检工作台：盲序抽样 → 评分表 → 解盲结算。

六问评分（每问 pass/fail，可附 note；reflection 类记忆免答 relevant 之外的
部分问题，见各行 has_reflection 标记）：
  grounded    有据：记忆的主张能在其引用的 L0 原文中找到依据；
  atomic      原子：一条一个自足主张，未混装多件事；
  faithful    忠实：用户拍板与助手推测区分正确（推测未被写成事实）；
  disposition 裁决：Selector 的处置正确（该 EXIST 的没 CREATE、该 CONFLICT
              的没静默、UPDATE 有据）；
  relevant    相关：与项目记忆库的定位相关，非闲聊/系统噪音；
  reflection  反思（仅 kind=reflection）：蒸馏是提炼还是噪音。

盲法：worksheet 不含链路标签；audit_id→链路映射单独存 key.json，结算时
解盲。抽样：每链 ≤n 条（不足取全），L3 语料内 verbatim 轮产物优先。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

QUESTIONS = ("grounded", "atomic", "faithful", "disposition", "relevant",
             "reflection")


def _load_export(run_path: str) -> dict:
    rp = Path(run_path)
    export = json.loads((rp / "export.json").read_text(encoding="utf-8"))
    run = json.loads((rp / "run.json").read_text(encoding="utf-8"))
    return {"run": run, "export": export, "dir": rp}


def _decision_map(exps: list[dict]) -> dict[tuple, dict]:
    """(run 绝对路径, memory_id) → 已提交 Selector 裁决。

    优先沿提交回执的 new_ids 定位创建任务；旧导出只允许本 run 唯一文本
    匹配。dead/未提交产物和多重匹配不冒充记忆的创建裁决。
    """
    from hybrid_memory.service.operate import redact_secrets
    out = {}
    for e in exps:
        run = str(e["dir"].resolve())
        texts = {}
        for sel in e["export"]["tasks"]:
            if sel["kind"] != "selector_due" or sel.get("state") != "done":
                continue
            cands = sel.get("payload_candidates") or []
            outcomes = {o["index"]: o for o in (sel.get("committed_effect") or {}).get("outcomes", [])}
            for d in (sel.get("result") or {}).get("decisions", []):
                idx = d.get("candidate_index")
                if type(idx) is not int or not 0 <= idx < len(cands) or not cands[idx]:
                    continue
                effect = outcomes.get(idx, {})
                info = {"action": d.get("action"), "target_id": d.get("target_id"),
                        "reason": (d.get("reason") or "")[:200],
                        "task_id": sel["id"], "candidate_index": idx,
                        "applied_action": effect.get("action")}
                for mid in effect.get("new_ids", []):
                    out.setdefault((run, mid), info)
                for text in {cands[idx], redact_secrets(cands[idx])}:
                    texts.setdefault(text, []).append(info)
        for m in e["export"]["mems"]:
            candidates = texts.get(m["text"], [])
            if len(candidates) == 1:
                out.setdefault((run, m["id"]), candidates[0])
    return out


def build_worksheet(run_paths: list[str], out: str, key_out: str, *,
                    n: int = 50, seed: int = 7) -> dict:
    """按链路预算抽样：同链路（corpus_kind）的多个 run 目录合并记忆池后
    抽 n 条——L2 四流并行时各目录是同一链路的分片，不是独立链路。"""
    exps = [_load_export(p) for p in run_paths]
    if n < 1 or not exps or len({e["dir"].name for e in exps}) != len(exps):
        raise ValueError("positive sample budget and unique run names required")
    dmap = _decision_map(exps)
    units_by_id = {e["dir"].name: {u["unit_id"]: u for u in e["export"]["units"]}
                   for e in exps}
    rows, key = [], {}
    # 记忆 id 只在 run 目录内唯一：合并池必须携带来源目录（e, m) 成对流动，
    # 任何以 (chain, mem_id) 为键的映射都会跨目录碰撞（2026-10-04 实跑抓出）。
    by_chain: dict[str, list] = {}
    for e in exps:
        for m in e["export"]["mems"]:
            by_chain.setdefault(e["run"]["corpus_kind"], []).append((e, m))
    picked_counts: dict[str, int] = {}
    for chain, pool in by_chain.items():
        random.Random(seed).shuffle(pool)
        picked = pool[:n]
        picked_counts[chain] = len(picked)
        for e, m in picked:
            run_name = e["dir"].name
            nonce = f"{seed}:{chain}:{run_name}:{m['id']}"
            aid = hashlib.sha256(nonce.encode()).hexdigest()[:12]
            srcs = []
            for uid in m["src"]:
                u = units_by_id[run_name].get(uid)
                if u:
                    srcs.append(f"[unit {uid}] 用户：{u['user_text'][:300]}\n"
                                f"助手：{u['assistant_text'][:300]}")
            rows.append({
                "audit_id": aid,
                "memory_text": m["text"], "memory_kind": m["kind"],
                "memory_pool": m["pool"], "memory_v": m["v"],
                "selector_decision": dmap.get((str(e["dir"].resolve()), m["id"])),
                "src_unit_ids": m["src"],
                "src_texts": "\n---\n".join(srcs)[:1200] or "（无引用）",
                "has_reflection": m["kind"] == "reflection",
                "verdicts": {}, "note": ""})
            key[aid] = {"chain": chain, "run": run_name,
                        "mem_id": m["id"]}
    random.Random(seed + 1).shuffle(rows)          # 盲序：链路交错且不可辨识
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    Path(key_out).write_text(json.dumps(key, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return {"rows": len(rows), "per_chain": picked_counts,
            "key_entries": len(key)}


def aggregate(filled_path: str, key_path: str, run_paths: list[str],
              out_path: str) -> dict:
    key = json.loads(Path(key_path).read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in
            Path(filled_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = [r.get("audit_id") for r in rows]
    if not rows or len(set(ids)) != len(ids) or set(ids) != set(key):
        raise ValueError("scores must cover each audit_id exactly once")
    for r in rows:
        applicable = QUESTIONS if r.get("has_reflection") else QUESTIONS[:-1]
        if any((r.get("verdicts") or {}).get(q) not in ("pass", "fail") for q in applicable):
            raise ValueError(f"incomplete or invalid verdicts: {r['audit_id']}")
    stats: dict = {}
    defects = []
    for r in rows:
        meta = key[r["audit_id"]]
        chain = meta["chain"]
        st = stats.setdefault(chain, {"n": 0, **{q: [0, 0] for q in QUESTIONS}})
        st["n"] += 1
        for q in QUESTIONS:
            if q == "reflection" and not r.get("has_reflection"):
                continue                      # 非反思记忆不答反思题
            v = (r.get("verdicts") or {}).get(q)
            if v in ("pass", "fail"):
                st[q][0] += (v == "pass")
                st[q][1] += 1
                if v == "fail":
                    defects.append({"chain": chain, "audit_id": r["audit_id"],
                                    "q": q, "memory": r["memory_text"][:120],
                                    "note": (r.get("note") or "")[:200]})
    # L2 自动指标（探针判分均值）
    auto, grouped = {}, {}
    for p in run_paths:
        rp = Path(p)
        run = json.loads((rp / "run.json").read_text(encoding="utf-8"))
        recs = run.get("probe_records") or []
        first_pass = rp / "run.json.first-pass"
        if not recs and first_pass.exists():
            recs = json.loads(first_pass.read_text(encoding="utf-8")).get("probe_records") or []
        grouped.setdefault(run["corpus_kind"], []).extend(recs)
    for chain, recs in grouped.items():
        if not recs:
            continue
        dims = {}
        for dim in {r.get("dimension", "unknown") for r in recs}:
            subset = [r for r in recs if r.get("dimension", "unknown") == dim]
            dims[dim] = _probe_summary(subset)
        auto[chain] = {**_probe_summary(recs), "dimensions": dims,
                       "validity": "pre-drain-unverified"}

    def rate(st, q):
        p, t = st[q]
        return (p / t) if t else None

    lines = ["# L2/L3 抽检结算", ""]
    for chain, st in stats.items():
        lines.append(f"## 链路 {chain}（n={st['n']}）")
        lines.append("")
        lines.append("| 问题 | 合格率 | 样本 |")
        lines.append("|---|---|---|")
        overall_p = overall_t = 0
        for q in QUESTIONS:
            p, t = st[q]
            overall_p += p
            overall_t += t
            lines.append(f"| {q} | {rate(st, q):.2%} | {t} |" if t
                         else f"| {q} | —（无适用样本） | 0 |")
        lines.append(f"| **总合格率** | **{overall_p / overall_t:.2%}** | {overall_t} |")
        lines.append("")
    if auto:
        lines.append(f"## L2 自动指标（探针均值）：{auto}")
        lines.append("")
    if defects:
        lines.append("## 缺陷清单")
        lines.append("")
        lines.append("| 链路 | audit_id | 问题 | 记忆 | 备注 |")
        lines.append("|---|---|---|---|---|")
        for d in defects:
            lines.append(f"| {d['chain']} | {d['audit_id']} | {d['q']} |"
                         f" {d['memory']} | {d['note']} |")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return {"rows": len(rows), "defects": len(defects), "stats": stats, "auto": auto}


def _probe_summary(records: list[dict]) -> dict:
    """同一来源集合的探针计数及原始均值；不推断能力有效性。"""
    return {"probes": len(records),
            **{f: round(sum(r[f] for r in records) / len(records), 4)
               for f in ("S", "H", "u") if all(f in r for r in records)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worksheet")
    w.add_argument("--runs", nargs="+", required=True)
    w.add_argument("--n", type=int, default=50)
    w.add_argument("--seed", type=int, default=7)
    w.add_argument("--out", required=True)
    w.add_argument("--key-out", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("--filled", required=True)
    a.add_argument("--key", required=True)
    a.add_argument("--runs", nargs="+", required=True)
    a.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "worksheet":
        print(build_worksheet(args.runs, args.out, args.key_out,
                              n=args.n, seed=args.seed))
    else:
        print(aggregate(args.filled, args.key, args.runs, args.out))


if __name__ == "__main__":
    main()
