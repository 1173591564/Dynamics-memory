"""外部基准适配：LoCoMo / LongMemEval → 统一 BenchInstance。

产出复用 InteractionUnit（build_interaction_windows / serialize_window
不用改）：units 是有序单元流，queries 在流结束后统一提问。
unit_sources[i] = 单元 i 的来源 id（LoCoMo: dia_id；LME: session_id），
用于把 evidence 标注映射回单元做检索级 recall。

泄漏纪律：LoCoMo 的 observation/session_summary/event_summary 是官方
预计算蒸馏结果，一律不读。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .real_chat import InteractionUnit


@dataclass(frozen=True)
class BenchQuery:
    id: str
    question: str
    answer: str
    qtype: str
    evidence_units: frozenset[int] = frozenset()
    abstention: bool = False


@dataclass(frozen=True)
class BenchInstance:
    id: str
    units: tuple[InteractionUnit, ...]
    unit_sources: tuple[tuple[str, ...], ...]
    queries: tuple[BenchQuery, ...]


def load_locomo(path: str | Path) -> list[BenchInstance]:
    """locomo10.json：双说话人对称对话，每个 turn = 一个 unit。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for sample in data:
        conv = sample["conversation"]
        sess_idx = sorted(int(k.split("_")[1]) for k in conv
                          if re.fullmatch(r"session_\d+", k))
        units, sources, dia2uid = [], [], {}
        for si in sess_idx:
            for turn in conv[f"session_{si}"]:
                uid = len(units)
                dia = turn.get("dia_id", "")
                if dia:
                    dia2uid[dia] = uid
                units.append(InteractionUnit(
                    id=uid, start_time=uid, end_time=uid,
                    user_text=f"{turn['speaker']}: {turn['text']}",
                    assistant_text="", assistant_turns=0))
                sources.append((dia,) if dia else ())
        queries = []
        for i, qa in enumerate(sample.get("qa", [])):
            ev = qa.get("evidence") or []
            if isinstance(ev, str):
                ev = re.findall(r"D\d+:\d+", ev)
            ev_units = frozenset(dia2uid[d] for d in ev if d in dia2uid)
            cat = str(qa.get("category", ""))
            if cat == "5":
                # 对抗题：无 answer，adversarial_answer 是合理但错误的诱导项
                ans = ("UNANSWERABLE (refuse; adversarial trap answer: "
                       + str(qa.get("adversarial_answer", "")) + ")")
            else:
                ans = str(qa.get("answer", ""))
            queries.append(BenchQuery(
                id=f"{sample['sample_id']}-q{i}", question=qa["question"],
                answer=ans, qtype=cat, evidence_units=ev_units,
                abstention=(cat == "5")))
        out.append(BenchInstance(
            id=sample["sample_id"], units=tuple(units),
            unit_sources=tuple(sources), queries=tuple(queries)))
    return out


def load_longmemeval(path: str | Path) -> list[BenchInstance]:
    """longmemeval_*.json：session 内 user/assistant 交替 → unit 归并（不跨 session）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for inst in data:
        units, sources = [], []
        sess_ids = inst["haystack_session_ids"]
        for si, sess in enumerate(inst["haystack_sessions"]):
            cur_u, parts, n_a = None, [], 0
            for turn in sess:
                if turn["role"] == "user":
                    if cur_u is not None:
                        uid = len(units)
                        units.append(InteractionUnit(
                            id=uid, start_time=si, end_time=si,
                            user_text=cur_u,
                            assistant_text="\n\n".join(parts),
                            assistant_turns=n_a))
                        sources.append((sess_ids[si],))
                    cur_u, parts, n_a = turn["content"], [], 0
                elif cur_u is not None and turn.get("content"):
                    parts.append(turn["content"])
                    n_a += 1
            if cur_u is not None:
                uid = len(units)
                units.append(InteractionUnit(
                    id=uid, start_time=si, end_time=si, user_text=cur_u,
                    assistant_text="\n\n".join(parts), assistant_turns=n_a))
                sources.append((sess_ids[si],))
        ev_sessions = set(inst.get("answer_session_ids") or [])
        ev_units = frozenset(
            u.id for u in units if ev_sessions & set(sources[u.id]))
        ans = inst["answer"]
        ans_str = str(ans)
        out.append(BenchInstance(
            id=inst["question_id"], units=tuple(units),
            unit_sources=tuple(sources),
            queries=(BenchQuery(
                id=inst["question_id"], question=inst["question"],
                answer=ans_str, qtype=inst["question_type"],
                evidence_units=ev_units,
                abstention=("unanswer" in ans_str.lower()
                            or "not mentioned" in ans_str.lower())),)))
    return out
