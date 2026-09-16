"""要点级重评：对已有 qa-continuity summary 里的 pred 按 keypoint 覆盖率重打分。

不重放、不重检索——summary 里存了每题每组的 pred/ctx，这里只做：
  1) 从该时点真实助理回复（参照）抽 3-6 个可判定要点（缓存，跨组共享）；
  2) judge 逐要点判 covered/partial/missed + fabrication 标志；
  3) hit = (C + 0.5·P)/K 作为该题得分；fab=1 单独统计。

用法：
    python -m experiments.rejudge_kp --allow-remote \
        --summaries experiments/out/qa/qa-cont-v4-*-summary.json
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from experiments import paths as P
from hybrid_memory.datasets.real_chat import load_interaction_units
from experiments.real_embedding import load_dotenv_key
from hybrid_memory.llm import chat

DATA = P.DATA_REAL
CHAT_CACHE = P.CHAT_CACHE
DOTENV = Path(".env")

KP_EXTRACT_SYS = (
    "给定一个工程项目的某时刻真实助理回复。从中抽取 4-8 个"
    "「项目状态要点」——即一个后来者要正确感知当时项目状态必须知道的事实，"
    "例如：当前进度/已完成事项、未决问题与阻塞、已确认的原因或结论、"
    "明确的待办。每条要点只含一个可独立判定的原子事实，禁止复合句；"
    "不要泛泛而谈。格式：每行一条，不要编号以外的内容。")
KP_JUDGE_SYS = (
    "给定用户问题、该时点真实助理回复（参照，代表当时可知信息）、"
    "从中抽取的项目状态要点清单，以及一个待评回答。"
    "对每个要点判断待评回答是否覆盖：\n"
    "C=该要点的事实被正确表达（允许换说法）；"
    "P=部分覆盖/含糊其辞；M=未覆盖或表达错误。\n"
    "另外判断待评回答是否与参照冲突地编造项目状态："
    "FAB:1=陈述了参照中不存在且与参照矛盾的事实；"
    "FAB:0=未冲突（多说了参照外的内容不算编造）。\n"
    "输出格式：每个要点一行 `K<序号>:<C|P|M>`，最后一行 `FAB:<0|1>`。"
    "不要输出其他内容。")


def _extract_kps(question: str, reference: str, key: str,
                 model: str) -> list[str]:
    out = chat(api_key=key, model=model, system=KP_EXTRACT_SYS,
               cache_dir=CHAT_CACHE,
               user=f"用户问题：{question}\n\n"
                    f"当时真实助理回复（截断）：\n{reference[:1200]}\n\n"
                    "请抽取项目状态要点：")
    kps = []
    for ln in out.splitlines():
        ln = ln.strip().lstrip("0123456789.-、）) ")
        if len(ln) >= 6:
            kps.append(ln)
    return kps[:8]


def _judge_kp(question: str, kps: list[str], pred: str, ref: str,
              key: str, model: str) -> tuple[list[str], int | None, str]:
    kp_lines = "\n".join(f"K{i + 1}: {k}" for i, k in enumerate(kps))
    try:
        out = chat(api_key=key, model=model, system=KP_JUDGE_SYS,
                   cache_dir=CHAT_CACHE,
                   user=f"用户问题：{question}\n\n"
                        f"参照（当时真实助理回复，截断）：\n{ref[:1200]}\n\n"
                        f"要点清单：\n{kp_lines}\n\n"
                        f"待评回答：\n{pred or '(空)'}")
    except Exception as exc:  # noqa: BLE001
        return [], None, f"judge-error: {exc}"
    marks = ["M"] * len(kps)
    for i in range(len(kps)):
        m = re.search(rf"K{i + 1}\s*[:：]\s*([CPM])", out, re.IGNORECASE)
        if m:
            marks[i] = m.group(1).upper()
    fab_m = re.search(r"FAB\s*[:：]\s*([01])", out)
    fab = int(fab_m.group(1)) if fab_m else None
    return marks, fab, out.strip()[:300]


def _hit(marks: list[str]) -> float | None:
    if not marks:
        return None
    return (sum(1 for m in marks if m == "C")
            + 0.5 * sum(1 for m in marks if m == "P")) / len(marks)


def rejudge(summary_path: Path, units, key: str, model: str,
            groups: list[str]) -> dict:
    d = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = d["results"]
    by_t = {u.id: u for u in units}
    # 参照 = 该 unit 的真实助理回复（与原 _judge 一致取前 1200 字）
    for r in rows:
        u = by_t[r["unit_id"]]
        r["_question_full"] = u.user_text
        r["_ref"] = u.assistant_text
        r["_kps"] = _extract_kps(u.user_text, u.assistant_text, key, model)

    def _work(rg):
        r, g = rg
        cell = r.get(g)
        if not cell or not cell.get("pred"):
            return r, g, None, None, ""
        marks, fab, note = _judge_kp(r["_question_full"], r["_kps"],
                                     cell["pred"], r["_ref"], key, model)
        return r, g, marks, fab, note

    tasks = [(r, g) for r in rows for g in groups]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r, g, marks, fab, note in ex.map(_work, tasks):
            cell = r.setdefault(g, {})
            cell["kp_marks"] = marks
            cell["kp_hit"] = _hit(marks)
            cell["kp_fab"] = fab
            cell["kp_note"] = note

    agg = {}
    for g in groups:
        hits = [r[g]["kp_hit"] for r in rows
                if r.get(g, {}).get("kp_hit") is not None]
        fabs = [r[g]["kp_fab"] for r in rows
                if r.get(g, {}).get("kp_fab") is not None]
        agg[g] = {"n": len(hits),
                  "mean_hit": round(float(np.mean(hits)), 3) if hits else None,
                  "ge07": round(sum(1 for h in hits if h >= 0.7)
                                / max(len(hits), 1), 3),
                  "fab_rate": round(float(np.mean(fabs)), 3) if fabs else None}
    out = {"summary_file": summary_path.name,
           "feature_set": d["summary"].get("feature_set"),
           "kp_agg": agg,
           "old_agg": d["summary"]["groups"],
           "results": [{k: v for k, v in r.items() if not k.startswith("_")}
                       | {"kps": r["_kps"]} for r in rows]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summaries", nargs="+", required=True)
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--dotenv", type=Path, default=DOTENV)
    ap.add_argument("--reader-model", default="glm-5.3-flash")
    ap.add_argument("--groups", default="memory,flat,none")
    ap.add_argument("--allow-remote", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.allow_remote == args.offline:
        raise SystemExit("choose exactly one of --allow-remote or --offline")

    key = None if args.offline else load_dotenv_key(args.dotenv)
    units = load_interaction_units(args.data)
    groups = args.groups.split(",")

    paths = sorted(p for pat in args.summaries for p in glob.glob(pat))
    table = []
    for sp in paths:
        res = rejudge(Path(sp), units, key, args.reader_model, groups)
        tag = Path(sp).stem.replace("-summary", "")
        out = P.QA / f"{tag}-kp.json"
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        mem = res["kp_agg"].get("memory", {})
        old = res["old_agg"].get("memory", {})
        table.append((tag, old.get("mean"), mem.get("mean_hit"),
                      mem.get("ge07"), mem.get("fab_rate")))
        print(f"{tag}: old_mean={old.get('mean')} kp_hit="
              f"{mem.get('mean_hit')} ge07={mem.get('ge07')} "
              f"fab={mem.get('fab_rate')}  -> {out.name}", flush=True)
    print("\n== memory 组对照 ==")
    for row in table:
        print("  %-28s old=%s  kp_hit=%s  ge07=%s  fab=%s" % row)


if __name__ == "__main__":
    main()
