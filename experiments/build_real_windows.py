"""按 BasicUnit 个数构建真实 memory-generation window 清单。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.datasets.real_chat import build_interaction_windows, load_interaction_units

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_DATA = ROOT / "data" / "l0-tencent-consistency-check.jsonl"
DEFAULT_OUT = HERE / "out" / "runs"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--size", type=int, default=3)
    parser.add_argument("--stride", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    units = load_interaction_units(args.data)
    windows = build_interaction_windows(units, size=args.size, stride=args.stride)
    if not windows:
        raise SystemExit("no complete windows")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for window in windows:
        rows.append({
            "window_id": window.id,
            "start_unit_id": window.start_unit_id,
            "end_unit_id": window.end_unit_id,
            "unit_ids": " ".join(str(unit.id) for unit in window.units),
            "unit_count": len(window.units),
            "start_time": window.start_time,
            "end_time": window.end_time,
            "user_chars": sum(len(unit.user_text) for unit in window.units),
            "assistant_chars": sum(len(unit.assistant_text) for unit in window.units),
            "assistant_turns": sum(unit.assistant_turns for unit in window.units),
        })

    manifest_path = args.out_dir / f"real-windows-k{args.size}-s{args.stride}.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    chars = [row["user_chars"] + row["assistant_chars"] for row in rows]
    turns = [row["assistant_turns"] for row in rows]
    covered = {unit.id for window in windows for unit in window.units}
    summary = {
        "dataset_sha256": file_sha256(args.data),
        "interaction_units": len(units),
        "window_size": args.size,
        "window_stride": args.stride,
        "windows": len(windows),
        "covered_units": len(covered),
        "dropped_units": len(units) - len(covered),
        "characters": {
            "mean": mean(chars),
            "median": median(chars),
            "max": max(chars),
        },
        "assistant_turns": {
            "mean": mean(turns),
            "median": median(turns),
            "max": max(turns),
        },
    }
    summary_path = args.out_dir / f"real-windows-k{args.size}-s{args.stride}-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**summary, "manifest": str(manifest_path),
                      "summary": str(summary_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
