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


def _decision_map(exps: list[dict]) -> dict[str, dict]:
    """candidate_text → selector 裁决。

    decisions 按 candidate_index 引用本任务候选（export 的
    payload_candidates）；键同时收录 redact 后的变体——应用层
    redact_secrets 会改写入库正文，记忆文本与候选原文可能不同
    （2026-10-04：原"最近 hauler"启发式对齐在实跑中全部失配）。
    """
    from hybrid_memory.service.operate import redact_secrets
    out: dict[str, dict] = {}
    for e in exps:
        for sel in (t for t in e["export"]["tasks"]
                    if t["kind"] == "selector_due"):
            decisions = (sel.get("result") or {}).get("decisions") or []
            cands = sel.get("payload_candidates") or []
            if not decisions:
                continue
            for d in decisions:
                idx = d.get("candidate_index")
                if isinstance(idx, int) and 0 <= idx < len(cands) and cands[idx]:
                    info = {"action": d.get("action"),
                            "target_id": d.get("target_id"),
                            "reason": (d.get("reason") or "")[:200]}
                    out.setdefault(cands[idx], info)
                    red = redact_secrets(cands[idx])
                    if red != cands[idx]:
                        out.setdefault(red, info)
    return out


def build_worksheet(run_paths: list[str], out: str, key_out: str, *,
                    n: int = 50, seed: int = 7) -> dict:
    """按链路预算抽样：同链路（corpus_kind）的多个 run 目录合并记忆池后
    抽 n 条——L2 四流并行时各目录是同一链路的分片，不是独立链路。"""
    exps = [_load_export(p) for p in run_paths]
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
                "selector_decision": dmap.get(m["text"]),
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
    stats: dict = {}
    defects = []
    for r in rows:
        meta = key.get(r["audit_id"])
        if meta is None:
            continue
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
    auto = {}
    for p in run_paths:
        rp = Path(p)
        run = json.loads((rp / "run.json").read_text(encoding="utf-8"))
        recs = run.get("probe_records") or []
        if recs:
            k = "S" if "S" in recs[0] else None
            auto[run["corpus_kind"]] = {
                "probes": len(recs),
                **{f: round(sum(r.get(f, 0) for r in recs) / len(recs), 4)
                   for f in (("S", "H", "u") if k else ())}}

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
    return {"rows": len(rows), "defects": len(defects)}


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
