"""真实数据 cand-gen 驱动：K=3 窗口 → opencode(deepseek-v4-flash) → MemoryCandidate。

用法：
    python -m experiments.candgen_real --start 0 --limit 1   # 试点
    python -m experiments.candgen_real                        # 全部 35 窗

输出 out/candgen/real-candgen-k3-s3.jsonl：每窗一条记录，含候选文本、耗时、错误。
原始窗口文本落在 out/cache/_candgen_scratch/（已 gitignore），不进清单。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from experiments import paths as P
from experiments.real_embedding import load_dotenv_key
from hybrid_memory.candgen import OpencodeCliGenerator
from hybrid_memory.datasets.real_chat import (build_interaction_windows,
                                              load_interaction_units)

DATA = P.DATA_REAL
SCRATCH = P.SCRATCH
DOTENV = Path(".env")
# 覆盖 models.dev zhipuai provider 可能读取的几种环境变量名
ZHIPU_ENV_NAMES = ("ZAI_API_KEY", "ZHIPUAI_API_KEY", "ZHIPU_API_KEY")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--size", type=int, default=3)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default="zhipu-env/glm-5.3-flash")
    ap.add_argument("--dotenv", type=Path, default=DOTENV)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    key = load_dotenv_key(args.dotenv)
    env_extra = {name: key for name in ZHIPU_ENV_NAMES}

    units = load_interaction_units(args.data)
    windows = build_interaction_windows(units, args.size, args.stride)
    end = len(windows) if args.limit is None else min(len(windows), args.start + args.limit)
    selected = windows[args.start:end]

    gen = OpencodeCliGenerator(model=args.model, scratch_dir=SCRATCH,
                               env_extra=env_extra)
    out_path = Path(args.out) if args.out else \
        P.CANDGEN_DIR / f"real-candgen-k{args.size}-s{args.stride}.jsonl"
    n_ok = n_err = n_cand = 0
    t0 = time.time()
    prev_scene = ""
    if args.start > 0 and out_path.exists():   # 续跑时接上前一窗情境
        for line in out_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("window_id") == args.start - 1 and r.get("scene_name"):
                prev_scene = r["scene_name"]

    with out_path.open("a", encoding="utf-8") as f:
        for w in selected:
            rec = {"window_id": w.id, "start_unit_id": w.start_unit_id,
                   "end_unit_id": w.end_unit_id, "model": args.model,
                   "prev_scene": prev_scene}
            try:
                t1 = time.time()
                gen_out = gen.generate(w, prev_scene)
                prev_scene = gen_out.scene_name or prev_scene
                rec.update(
                    scene_name=gen_out.scene_name,
                    candidates=[{"text": c.text, "type": c.type,
                                 "priority": c.priority,
                                 "salience": c.salience,
                                 "source_unit_ids": list(c.source_unit_ids)}
                                for c in gen_out.candidates],
                    n_candidates=len(gen_out.candidates),
                    elapsed_s=round(time.time() - t1, 2))
                n_ok += 1
                n_cand += len(gen_out.candidates)
            except Exception as exc:  # noqa: BLE001 — 记录失败继续跑
                rec.update(error=str(exc)[:300], n_candidates=0)
                n_err += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"window {w.id}: {rec.get('n_candidates')} cand, "
                  f"{rec.get('elapsed_s', '-')}s"
                  + (f" ERROR {rec['error'][:80]}" if "error" in rec else ""))

    summary = {
        "windows_attempted": len(selected), "windows_ok": n_ok,
        "windows_error": n_err, "candidates_total": n_cand,
        "elapsed_s": round(time.time() - t0, 2), "model": args.model,
        "size": args.size, "stride": args.stride, "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
