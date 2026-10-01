"""TIDE 命令行。

  python -m tide gen    --out data/l1 [--seeds 5]
  python -m tide meta   [--data data/l1] [--budget 64]
  python -m tide bench  --data data/l1 --systems none,oracle,recency,bm25,parsed \
                        [--budgets 64,256] [--dims R,V] [--max-streams-per-dim N] \
                        [--dm-repo PATH] --out runs/x
  python -m tide report --run runs/x
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .gen_l1 import generate
from .ledger import DIM_NAMES, DIMENSIONS, KNOB_NAMES, load_streams, save_streams
from .meta import format_meta, run_meta
from .runner import run
from .score import aggregate
from .systems.reference import DEFECTS, BM25, NoMemory, Oracle, Parsed, Recency


def _streams(args):
    if args.data and Path(args.data).exists():
        ss = load_streams(args.data)
    else:
        ss = generate(seeds=args.seeds)
    if getattr(args, "dims", None):
        keep = set(args.dims.split(","))
        ss = [s for s in ss if s.dimension in keep]
    n = getattr(args, "max_streams_per_dim", None)
    if n:
        cnt, out = {}, []
        for s in ss:
            if cnt.get(s.dimension, 0) < n:
                out.append(s)
                cnt[s.dimension] = cnt.get(s.dimension, 0) + 1
        ss = out
    return ss


def _system(name, args):
    table = {"none": NoMemory, "oracle": Oracle, "recency": Recency, "bm25": BM25,
             "parsed": Parsed}
    if name in table:
        return table[name]()
    if name.startswith("parsed-") and name[7:] in DEFECTS:
        return Parsed(name[7:])
    if name == "dynamics-memory":
        from .adapters.dynamics_memory import DynamicsMemory
        if not args.dm_repo:
            raise SystemExit("--dm-repo required for dynamics-memory")
        return DynamicsMemory(args.dm_repo)
    raise SystemExit(f"unknown system {name}")


def _fmt(x, ci=None):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    s = f"{x:.2f}"
    if ci and not any(math.isnan(c) for c in ci):
        s += f" [{ci[0]:.2f}, {ci[1]:.2f}]"
    return s


def render_report(summary: dict) -> str:
    out = ["# TIDE L1 报告", "",
           f"- 流 {summary['n_streams']} 条，探针 {summary['n_probes']} 个；"
           f"预算 {summary['budgets']}；检索层判分（账本 token 精确匹配）",
           "- NTU = (U − U_none) / (U_oracle − U_none)，方括号为按流聚类 bootstrap 95% CI",
           "- u = S − H：S 为现值 token 命中率，H 为上下文含失效值（有害注入）", ""]
    for B in summary["budgets"]:
        rows = [a for a in summary["agg"] if a and a["budget"] == B]
        dims = [d for d in DIMENSIONS if any(d in a["dims"] for a in rows)]
        out += [f"## 预算 B = {B}", "",
                "| 系统 | NTU | " + " | ".join(dims) + " | H 率 |",
                "|---|---|" + "---|" * len(dims) + "---|"]
        for a in rows:
            hs = [a["dims"][d]["H"] * a["dims"][d]["n"] for d in dims if d in a["dims"]]
            ns = [a["dims"][d]["n"] for d in dims if d in a["dims"]]
            cells = [_fmt(a["dims"][d]["ntu"]) if d in a["dims"] else "—" for d in dims]
            out.append(f"| {a['system']} | {_fmt(a['ntu'], a['ntu_ci'])} | "
                       + " | ".join(cells) + f" | {sum(hs) / max(1, sum(ns)):.2f} |")
        out += ["", "F 维 none 与 oracle 同分（不服务即不犯错），维度 NTU 无定义，"
                "看 H 率与 u；它仍计入合并 NTU。", ""]
        out += ["### 应力曲线（u 按旋钮档位）", ""]
        for d in dims:
            out.append(f"**{d} · {DIM_NAMES[d]}**（{KNOB_NAMES[d]}）")
            out.append("")
            knobs = sorted({k for a in rows if d in a["dims"] for k in a["dims"][d]["curve"]})
            out.append("| 系统 | " + " | ".join(str(k) for k in knobs) + " |")
            out.append("|---|" + "---|" * len(knobs))
            for a in rows:
                if d in a["dims"]:
                    c = a["dims"][d]["curve"]
                    out.append(f"| {a['system']} | " + " | ".join(
                        f"{c[k]['u']:+.2f}" if k in c else "—" for k in knobs) + " |")
            out.append("")
    return "\n".join(out)


def cmd_gen(args):
    ss = generate(seeds=args.seeds)
    save_streams(ss, args.out)
    print(f"wrote {len(ss)} streams / {sum(len(s.probes) for s in ss)} probes → {args.out}")


def cmd_meta(args):
    res = run_meta(_streams(args), budget=args.budget)
    txt = format_meta(res)
    print(txt)
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "meta.md").write_text(txt, encoding="utf-8")
        (Path(args.out) / "meta.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    raise SystemExit(0 if res["pass"] else 1)


def cmd_bench(args):
    ss = _streams(args)
    budgets = [int(b) for b in args.budgets.split(",")]
    names = args.systems.split(",")
    for req in ("none", "oracle"):
        if req not in names:
            names.insert(0, req)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    recs = []
    for n in names:
        sysm = _system(n, args)
        try:
            recs += run(sysm, ss, budgets, progress=args.progress)
        finally:
            sysm.close()
    with open(out / "records.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {"budgets": budgets, "n_streams": len(ss),
               "n_probes": sum(len(s.probes) for s in ss),
               "agg": [aggregate(recs, n, B) for B in budgets for n in names]}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (out / "report.md").write_text(render_report(summary), encoding="utf-8")
    print(render_report(summary))


def cmd_report(args):
    summary = json.loads((Path(args.run) / "summary.json").read_text())
    print(render_report(summary))


def main():
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="tide")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen"); g.add_argument("--out", required=True)
    g.add_argument("--seeds", type=int, default=5); g.set_defaults(fn=cmd_gen)
    for name, fn in (("meta", cmd_meta), ("bench", cmd_bench)):
        p = sub.add_parser(name)
        p.add_argument("--data"); p.add_argument("--seeds", type=int, default=5)
        p.add_argument("--dims"); p.add_argument("--max-streams-per-dim", type=int)
        p.add_argument("--out", required=(name == "bench")); p.set_defaults(fn=fn)
    sub.choices["meta"].add_argument("--budget", type=int, default=64)
    b = sub.choices["bench"]
    b.add_argument("--systems", default="none,oracle,recency,bm25,parsed")
    b.add_argument("--budgets", default="64,256")
    b.add_argument("--dm-repo"); b.add_argument("--progress", action="store_true")
    r = sub.add_parser("report"); r.add_argument("--run", required=True)
    r.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
