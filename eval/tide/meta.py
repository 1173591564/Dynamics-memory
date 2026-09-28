"""基准自检（元评测）：用已知缺陷验证 TIDE 量到的正是它声称要量的东西。

1. 锚点：none 的 NTU=0，oracle 的 NTU=1，理想抽取 parsed 的 NTU≥0.99。
2. 干预 × 能力特异性矩阵：每种缺陷只应伤到预期维度（Δu < −0.2），
   其余维度保持不变（|Δu| < 0.05）；"any" 格有据可查地不作判定。
3. 剂量-反应：amnesic 在 R 上、fuzzy 在 I 上，随应力旋钮单调不增，且最高档明显低于最低档。
"""
from __future__ import annotations

from .ledger import DIMENSIONS
from .runner import run
from .score import aggregate
from .systems.reference import DEFECTS, NoMemory, Oracle, Parsed

DROP, HOLD = -0.2, 0.05

# 预期被伤的维度；ANY = 允许变化、不判定（附理由）
EXPECT = {
    "stale": {"V", "P"},
    "noscope": {"C"},
    "nocascade": {"P"},
    "noretract": {"F"},
    "hoard": {"V", "P", "F"},
    "amnesic": {"R"},
    "fuzzy": {"I"},
}
ANY = {
    # 头词模糊匹配会把同一主体的其他作用域一起端出，预算紧时挤掉目标——
    # 作用域冲突本身就是一种相似项干扰，不算特异性违例。
    ("fuzzy", "C"): "同主体异作用域 = 相似项干扰",
}
DOSE = {"amnesic": "R", "fuzzy": "I"}


def run_meta(streams, budget: int = 64) -> dict:
    systems = [NoMemory(), Oracle(), Parsed()] + [Parsed(d) for d in DEFECTS]
    recs = []
    for s in systems:
        recs += run(s, streams, [budget])
    agg = {s.name: aggregate(recs, s.name, budget, n_boot=200) for s in systems}
    base = agg["parsed"]["dims"]
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    check("anchor none NTU=0", abs(agg["none"]["ntu"]) < 1e-9, f"{agg['none']['ntu']:.3f}")
    check("anchor oracle NTU=1", abs(agg["oracle"]["ntu"] - 1) < 1e-9, f"{agg['oracle']['ntu']:.3f}")
    check("ideal parsed NTU≥0.99", agg["parsed"]["ntu"] >= 0.99, f"{agg['parsed']['ntu']:.3f}")

    matrix = {}
    for d in DEFECTS:
        row = {}
        for dim in DIMENSIONS:
            if dim not in base:
                continue
            delta = agg[f"parsed-{d}"]["dims"][dim]["u"] - base[dim]["u"]
            if (d, dim) in ANY:
                verdict, ok = "any", True
            elif dim in EXPECT[d]:
                verdict, ok = "drop", delta < DROP
            else:
                verdict, ok = "hold", abs(delta) < HOLD
            row[dim] = {"delta": round(delta, 3), "expect": verdict, "pass": ok}
            check(f"specificity {d}×{dim} ({verdict})", ok, f"Δu={delta:+.3f}")
        matrix[d] = row

    for d, dim in DOSE.items():
        curve = agg[f"parsed-{d}"]["dims"][dim]["curve"]
        us = [curve[k]["u"] for k in sorted(curve)]
        mono = all(b <= a + 1e-9 for a, b in zip(us, us[1:]))
        check(f"dose-response {d}×{dim}", mono and us[0] - us[-1] > 0.5,
              " → ".join(f"{k}:{curve[k]['u']:.2f}" for k in sorted(curve)))

    return {"budget": budget, "checks": checks, "matrix": matrix,
            "ntu": {k: v["ntu"] for k, v in agg.items()},
            "pass": all(c["pass"] for c in checks)}


def format_meta(res: dict) -> str:
    dims = [d for d in DIMENSIONS if any(d in r for r in res["matrix"].values())]
    out = [f"## 元评测（B={res['budget']}）：{'PASS' if res['pass'] else 'FAIL'}", "",
           "### 干预 × 能力特异性矩阵（Δu 相对理想抽取；✓ 符合预期，✗ 违例）", "",
           "| 缺陷 | " + " | ".join(dims) + " |",
           "|---|" + "---|" * len(dims)]
    for d, row in res["matrix"].items():
        cells = []
        for dim in dims:
            c = row[dim]
            mark = {"drop": "▼", "hold": "·", "any": "~"}[c["expect"]]
            cells.append(f"{mark}{c['delta']:+.2f}{'✓' if c['pass'] else '✗'}")
        out.append(f"| {d} | " + " | ".join(cells) + " |")
    out += ["", "▼ 预期下降（Δu<−0.2）· 预期不变（|Δu|<0.05）~ 不判定", "",
            "### 全部检查", ""]
    out += [f"- {'✓' if c['pass'] else '✗'} {c['check']}：{c['detail']}" for c in res["checks"]]
    return "\n".join(out) + "\n"
