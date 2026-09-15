"""智谱 embedding-3 在基本交互单元上的 user→assistant 弱监督 embedding 诊断。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid_memory.datasets.real_chat import load_interaction_units
from hybrid_memory.embed.cache import SqliteEmbeddingCache
from hybrid_memory.embed.zhipu import ZhipuEmbedder

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_DATA = ROOT / "data" / "l0-tencent-consistency-check.jsonl"
DEFAULT_OUT = HERE / "out" / "runs"
DEFAULT_CACHE = HERE / "out" / "cache"
DEFAULT_DOTENV = ROOT / ".env"


def load_dotenv_key(path: Path, key: str = "ZAI_API_KEY") -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"dotenv file unavailable: {path}") from exc
    found = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        if not separator or name.strip() != key:
            continue
        if found is not None:
            raise RuntimeError(f"duplicate {key} in dotenv")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not value:
            raise RuntimeError(f"{key} is empty in dotenv")
        found = value
    if found is None:
        raise RuntimeError(f"{key} is missing from dotenv")
    return found


def evaluate(query_vectors: np.ndarray, response_vectors: np.ndarray) -> tuple[dict, list[dict]]:
    if query_vectors.ndim != 2 or response_vectors.ndim != 2:
        raise ValueError("vectors must be 2D")
    if query_vectors.shape != response_vectors.shape or len(query_vectors) < 2:
        raise ValueError("query and response vectors must have equal shape with at least two rows")
    scores = query_vectors @ response_vectors.T
    n = len(scores)
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty(n, dtype=np.int64)
    for index in range(n):
        ranks[index] = int(np.flatnonzero(order[index] == index)[0]) + 1
    positives = np.diag(scores)
    negatives = scores.copy()
    np.fill_diagonal(negatives, -np.inf)
    hard_negative_ids = negatives.argmax(axis=1)
    hard_negatives = negatives[np.arange(n), hard_negative_ids]
    margins = positives - hard_negatives

    def quantiles(values: np.ndarray) -> dict:
        return {
            "p10": float(np.quantile(values, 0.10)),
            "p50": float(np.quantile(values, 0.50)),
            "p90": float(np.quantile(values, 0.90)),
        }

    summary = {
        "units": n,
        "recall_at_1": float(np.mean(ranks <= 1)),
        "recall_at_5": float(np.mean(ranks <= 5)),
        "recall_at_10": float(np.mean(ranks <= 10)),
        "mrr": float(np.mean(1.0 / ranks)),
        "positive_beats_hard_negative": float(np.mean(margins > 0)),
        "positive_similarity": quantiles(positives),
        "hard_negative_similarity": quantiles(hard_negatives),
        "positive_margin": quantiles(margins),
    }
    rows = [{
        "unit_id": index,
        "rank": int(ranks[index]),
        "target_similarity": float(positives[index]),
        "hard_negative_id": int(hard_negative_ids[index]),
        "hard_negative_similarity": float(hard_negatives[index]),
        "margin": float(margins[index]),
        "top_5_ids": " ".join(str(item) for item in order[index, :5]),
    } for index in range(n)]
    return summary, rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--dotenv", type=Path, default=DEFAULT_DOTENV)
    parser.add_argument("--dimensions", type=int, choices=(256, 512, 1024, 2048), default=2048)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-chars", type=int, default=2000)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.allow_remote == args.offline:
        raise SystemExit("choose exactly one of --allow-remote or --offline")
    units = load_interaction_units(args.data)
    if args.limit < 0:
        raise SystemExit("--limit must be >= 0")
    if args.limit:
        units = units[:args.limit]
    if len(units) < 2:
        raise SystemExit("at least two complete interaction units are required")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = args.cache or \
        DEFAULT_CACHE / f"zhipu-embedding-3-{args.dimensions}.sqlite3"
    api_key = None if args.offline else load_dotenv_key(args.dotenv)
    embedder = ZhipuEmbedder(
        api_key=api_key,
        dimensions=args.dimensions,
        batch_size=args.batch_size,
        max_chars=args.max_chars,
        cache=SqliteEmbeddingCache(cache_path),
        offline=args.offline,
    )
    query_vectors = embedder.embed([unit.user_text for unit in units])
    prompt_tokens = embedder.last_prompt_tokens
    response_vectors = embedder.embed([unit.assistant_text for unit in units])
    prompt_tokens += embedder.last_prompt_tokens
    metrics, rows = evaluate(query_vectors, response_vectors)

    suffix = f"embedding-3-{args.dimensions}"
    if args.limit:
        suffix += f"-first-{args.limit}"
    summary = {
        "dataset_sha256": file_sha256(args.data),
        "model": embedder.model,
        "dimensions": args.dimensions,
        "batch_size": args.batch_size,
        "max_chars": args.max_chars,
        "prompt_tokens_requested": prompt_tokens,
        **metrics,
    }
    summary_path = args.out_dir / f"real-{suffix}-summary.json"
    ranks_path = args.out_dir / f"real-{suffix}-ranks.csv"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(ranks_path, rows)
    print(json.dumps({
        "units": summary["units"],
        "recall_at_1": summary["recall_at_1"],
        "recall_at_5": summary["recall_at_5"],
        "recall_at_10": summary["recall_at_10"],
        "mrr": summary["mrr"],
        "positive_beats_hard_negative": summary["positive_beats_hard_negative"],
        "prompt_tokens_requested": prompt_tokens,
        "summary": str(summary_path),
        "ranks": str(ranks_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
