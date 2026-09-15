"""实验产物目录常量——所有脚本从这里取路径，不要各自硬编码。

    out/cache/   可重建缓存（embedding sqlite、chat-cache、candgen 窗口原文）
    out/candgen/ cand-gen LLM 产出（real-candgen-*.jsonl、bench-candgen/）
    out/runs/    回放/stress/embedding 扫描产物（csv、trajectory、memories、png）
    out/qa/      QA 评测结果 + tension 标注/待审清单
    out/bench/   外部 benchmark 结果
    out/tmp/     临时调试产物（_*.txt/_*.log，可随时清）
"""
from pathlib import Path

OUT = Path("experiments/out")
CACHE = OUT / "cache"
CANDGEN_DIR = OUT / "candgen"
RUNS = OUT / "runs"
QA = OUT / "qa"
BENCH = OUT / "bench"
TMP = OUT / "tmp"

DATA_REAL = Path("data/l0-tencent-consistency-check.jsonl")
EMB_CACHE = CACHE / "zhipu-embedding-3-2048.sqlite3"
CHAT_CACHE = CACHE / "chat-cache"
SCRATCH = CACHE / "_candgen_scratch"

for _d in (CACHE, CANDGEN_DIR, RUNS, QA, BENCH, TMP):
    _d.mkdir(parents=True, exist_ok=True)
