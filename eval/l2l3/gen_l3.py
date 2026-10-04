"""L3 真实轨迹语料装配：本地 jsonl（不入库）→ 跑链语料。

jsonl 每行：{"t": int, "user": str, "assistant": str, "provenance": str}
provenance ∈ {verbatim-session（逐字真实轮次）, devlog-quote（开发日志引述）,
other-real（其他真实来源）}——抽检时逐字轮次为一级样本，其余打标降级。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_PROV = {"verbatim-session", "devlog-quote", "other-real"}


def build(in_path: str, out_path: str) -> dict:
    rows = []
    bad = 0
    for i, line in enumerate(Path(in_path).read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            assert isinstance(r["user"], str) and isinstance(r["assistant"], str)
            assert r.get("provenance") in _PROV
            rows.append({"t": int(r.get("t", i)), "user": r["user"],
                         "assistant": r["assistant"],
                         "provenance": r["provenance"]})
        except (KeyError, ValueError, AssertionError, TypeError):
            bad += 1
            print(f"[l3] 第 {i + 1} 行不合法，已跳过", flush=True)
    rows.sort(key=lambda r: r["t"])
    for j, r in enumerate(rows):          # t 重排为连续轮次
        r["t"] = j
    corpus = {"kind": "l3", "source": str(in_path), "turns": rows,
              "provenance_counts": {p: sum(1 for r in rows if r["provenance"] == p)
                                    for p in _PROV}}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(corpus, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    return corpus


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    c = build(args.inp, args.out)
    print(f"[l3] 装配 {len(c['turns'])} 轮：{c['provenance_counts']}")


if __name__ == "__main__":
    main()
