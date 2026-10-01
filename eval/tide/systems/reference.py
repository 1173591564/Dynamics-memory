"""参照系统。

下界/上界：none（NTU=0）、oracle（NTU=1，唯一可见探针真值的特权系统）。
朴素基线：recency（最近 B token 原始日志）、bm25（原始日志检索塞满预算）。
健全性系统：parsed = 理想抽取（解析 L1 模板）+ 可选的已知缺陷。它们不参赛，
用来验证基准本身（已知组效度、干预 × 能力特异性矩阵）。
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..protocol import Capabilities, MemorySystem
from ..text import (RE_ASK, RE_DERIVE, RE_RETRACT, RE_SET, RE_UPDATE,
                    approx_tokens)


def _line(t: int, user: str, assistant: str) -> str:
    return f"[t={t}] 用户：{user} 助手：{assistant}"


def _pack(lines: list[str], budget: int) -> list[str]:
    kept, used = [], 0
    for ln in lines:
        cost = approx_tokens(ln) + (1 if kept else 0)
        if used + cost > budget:
            break
        kept.append(ln)
        used += cost
    return kept


class NoMemory(MemorySystem):
    name = "none"

    def reset(self, stream_id): pass
    def ingest(self, user, assistant, t): pass
    def serve(self, query, t, budget_tokens, passive=True, probe=None): return ""


class Oracle(MemorySystem):
    name = "oracle"
    caps = Capabilities(passive=True, privileged=True)

    def reset(self, stream_id): pass
    def ingest(self, user, assistant, t): pass

    def serve(self, query, t, budget_tokens, passive=True, probe=None):
        return probe.oracle_context if probe is not None else ""


class Recency(MemorySystem):
    name = "recency"

    def reset(self, stream_id):
        self.turns = []

    def ingest(self, user, assistant, t):
        self.turns.append(_line(t, user, assistant))

    def serve(self, query, t, budget_tokens, passive=True, probe=None):
        kept = _pack(list(reversed(self.turns)), budget_tokens)
        return "\n".join(reversed(kept))


def _terms(text: str) -> list[str]:
    cjk = re.findall(r"[\u3400-\u9fff]+", text)
    out = [w.lower() for w in re.findall(r"[A-Za-z0-9_\-]+", text)]
    for run in cjk:
        out += [run[i:i + 2] for i in range(len(run) - 1)] or [run]
    return out


class BM25(MemorySystem):
    """原始日志逐轮建索引，按 BM25 取最相关的轮塞满预算，输出按时间排序。"""
    name = "bm25"

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b

    def reset(self, stream_id):
        self.docs, self.tf, self.df = [], [], Counter()

    def ingest(self, user, assistant, t):
        line = _line(t, user, assistant)
        tf = Counter(_terms(user + " " + assistant))
        self.docs.append(line)
        self.tf.append(tf)
        self.df.update(tf.keys())

    def serve(self, query, t, budget_tokens, passive=True, probe=None):
        n = len(self.docs)
        if not n:
            return ""
        avg = sum(sum(tf.values()) for tf in self.tf) / n
        q = set(_terms(query))
        scored = []
        for i, tf in enumerate(self.tf):
            dl = sum(tf.values())
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if f:
                    idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        kept = _pack([self.docs[i] for _, i in scored], budget_tokens)
        order = {ln: i for i, ln in enumerate(self.docs)}
        return "\n".join(sorted(kept, key=order.get))


DEFECTS = ("stale", "noscope", "nocascade", "noretract", "hoard", "amnesic", "fuzzy")


class Parsed(MemorySystem):
    """理想抽取（解析 L1 模板）+ 当前状态表。defect 注入一种已知缺陷：

    stale      忽略更新，永远保留首个值          → 预期伤 V、P
    noscope    作用域被丢弃，同主体后写覆盖前写  → 预期伤 C
    nocascade  上游变更不让派生值失效            → 预期伤 P
    noretract  撤回被忽略                        → 预期伤 F
    hoard      服务该主体的全部历史陈述          → 预期伤 V、P、F（有害注入）
    amnesic    只记最近 k 轮                     → 预期伤 R（大 Δ）
    fuzzy      按头词模糊匹配，端出所有同族主体  → 预期伤 I
    """

    def __init__(self, defect: str | None = None, amnesic_k: int = 48):
        if defect is not None and defect not in DEFECTS:
            raise ValueError(f"unknown defect {defect}")
        self.defect = defect
        self.k = amnesic_k
        self.name = f"parsed-{defect}" if defect else "parsed"

    def reset(self, stream_id):
        self.state = {}      # key -> {"val", "t", "text", "dep", "dep_val"} | None(撤回)
        self.history = {}    # key -> [(t, text)]
        self.retract_text = {}

    def _key(self, scope, subj):
        return subj if self.defect == "noscope" else (scope or "", subj)

    def ingest(self, user, assistant, t):
        text = f"[t={t}] {user}"
        if m := RE_DERIVE.match(user):
            up_subj, up_val, subj, val = m.groups()
            key = self._key("", subj)
            self.state[key] = {"val": val, "t": t, "text": text,
                               "dep": self._key("", up_subj), "dep_val": up_val}
        elif m := RE_UPDATE.match(user):
            scope, subj, val = m.groups()
            key = self._key(scope, subj)
            if self.defect == "stale" and self.state.get(key):
                pass
            else:
                self.state[key] = {"val": val, "t": t, "text": text}
        elif m := RE_RETRACT.match(user):
            scope, subj = m.groups()
            key = self._key(scope, subj)
            if self.defect != "noretract":
                self.state[key] = None
                self.retract_text[key] = text
        elif m := RE_SET.match(user):
            scope, subj, val = m.groups()
            key = self._key(scope, subj)
            self.state[key] = {"val": val, "t": t, "text": text}
        else:
            return
        self.history.setdefault(key, []).append((t, text))

    def _visible(self, rec, now):
        return self.defect != "amnesic" or now - rec["t"] <= self.k

    def _stale_root(self, key, seen=()):
        """沿依赖链上溯：任何一环的上游值与派生时记下的不一致 → 返回失效的根。"""
        rec = self.state.get(key)
        if not rec or rec.get("dep") is None or key in seen:
            return None
        dep = rec["dep"]
        up = self.state.get(dep)
        if up is None or up["val"] != rec["dep_val"]:
            return dep
        return self._stale_root(dep, seen + (key,))

    def _lines_for(self, key, now):
        if self.defect == "hoard":
            return [txt for _, txt in reversed(self.history.get(key, []))]
        if key not in self.state:
            return []
        rec = self.state[key]
        if rec is None:
            return [self.retract_text[key]]
        if self.defect != "nocascade":
            root = self._stale_root(key)
            if root is not None:
                # 派生值已失效：改为端出失效源头的现状（其本身也可能是派生的）
                while (nxt := self._stale_root(root)) is not None:
                    root = nxt
                return self._lines_for(root, now) if root in self.state else []
        if not self._visible(rec, now):
            return []
        return [rec["text"]]

    def serve(self, query, t, budget_tokens, passive=True, probe=None):
        m = RE_ASK.match(query)
        if not m:
            return ""
        scope, subj = m.groups()
        if self.defect == "fuzzy":
            head = subj[:2]
            keys = [k for k in self.state
                    if (k if isinstance(k, str) else k[1]).startswith(head)]
            recs = sorted(keys, key=lambda k: -(self.state[k] or {"t": -1})["t"])
            lines = [ln for k in recs for ln in self._lines_for(k, t)]
        else:
            lines = self._lines_for(self._key(scope, subj), t)
        return "\n".join(_pack(lines, budget_tokens))


def reference_systems() -> dict:
    return {"none": NoMemory, "oracle": Oracle, "recency": Recency, "bm25": BM25,
            "parsed": Parsed}
