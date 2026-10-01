"""L1 受控程序化层：先有账本、后有文本。

每条流只考一个维度，流内覆盖该维度应力旋钮的全部档位（便于画曲线、
按流聚类做统计）。事实值是唯一伪词 token（如 zorvex-4821）：上下文里有没有
现值 / 旧值 / 派生值，对任何黑箱系统都能用字符串精确判定。

话术约束（保证 token 判分无歧义）：更新与撤回的话术**不复述旧值**，
所以上下文里出现旧值 token = 系统服务了一条失效记忆。
"""
from __future__ import annotations

import numpy as np

from .ledger import DIMENSIONS, Fact, Probe, Stream, Turn
from .text import (FILLER, ask, say_derive, say_retract, say_set, say_update)

HEADS = ["日志", "缓存", "构建", "部署", "数据库", "鉴权", "监控", "队列",
         "测试", "镜像", "网关", "存储", "告警", "配置"]
SUFFIXES = ["级别", "目录", "格式", "保留天数", "方案", "版本", "地址", "端口",
            "超时", "上限", "前缀", "策略", "工具", "平台", "区域", "账号",
            "路径", "模式", "频率", "阈值"]
SCOPES = ["web", "api", "docs", "worker", "mobile"]
_CONS = "bdfgklmnprstvz"
_VOW = "aeiou"

LEVELS = {"R": [1, 4, 16, 64, 256], "V": [1, 2, 4, 8], "P": [1, 2, 3],
          "C": [2, 3, 4], "F": [1, 8, 32, 128], "I": [0, 4, 16, 64]}
PER_LEVEL = {"R": 4, "V": 3, "P": 3, "C": 3, "F": 4, "I": 3}
LENGTH = {"R": 360, "V": 300, "P": 300, "C": 240, "F": 300, "I": 480}


class _Builder:
    def __init__(self, dim: str, seed: int):
        self.dim, self.seed = dim, seed
        self.id = f"L1-{dim}-s{seed}"
        self.T = LENGTH[dim]
        self.rng = np.random.default_rng(seed * 1000 + DIMENSIONS.index(dim))
        self.slots: dict[int, Turn] = {}
        self.facts: dict[str, Fact] = {}
        self.probes: list[Probe] = []
        self._tokens: set[str] = set()
        self._subjects: set[str] = set()
        self._heads_used: set[str] = set()

    # ---- 资源 ----
    def token(self) -> str:
        while True:
            n = int(self.rng.integers(2, 4))
            word = "".join(self.rng.choice(list(_CONS)) + self.rng.choice(list(_VOW))
                           for _ in range(n))
            tok = f"{word}-{int(self.rng.integers(1000, 10000))}"
            if tok not in self._tokens:
                self._tokens.add(tok)
                return tok

    def subject(self, head: str | None = None) -> str:
        heads = [head] if head else HEADS
        for _ in range(500):
            s = str(self.rng.choice(heads)) + str(self.rng.choice(SUFFIXES))
            if s not in self._subjects:
                self._subjects.add(s)
                return s
        raise RuntimeError("主体用尽")

    def fresh_head(self) -> str:
        free = [h for h in HEADS if h not in self._heads_used]
        h = str(self.rng.choice(free))
        self._heads_used.add(h)
        return h

    def fact(self, subj: str, scope: str, val: str, t: int, **kw) -> Fact:
        f = Fact(id=f"F{len(self.facts)}", subject=subj, scope=scope, value=val,
                 t_valid=[t, None], **kw)
        self.facts[f.id] = f
        return f

    # ---- 排程 ----
    def place(self, t_pref: int, utter: tuple[str, str], op: str,
              facts: list[str]) -> int:
        t = max(0, int(t_pref))
        while t in self.slots:
            t += 1
        if t >= self.T:
            raise RuntimeError(f"{self.id}: 排程溢出（t={t_pref}）")
        self.slots[t] = Turn(t=t, user=utter[0], assistant=utter[1], op=op, facts=facts)
        return t

    def probe(self, t: int, knob: int, query: str, gold: list, harmful: list,
              oracle: str, candidates: dict) -> None:
        if t > self.T:
            raise RuntimeError(f"{self.id}: 探针越界 t={t}")
        self.probes.append(Probe(id=f"{self.id}-p{len(self.probes)}", t=t,
                                 dimension=self.dim, knob=knob, query=query,
                                 gold=gold, harmful=harmful, oracle_context=oracle,
                                 candidates=candidates))

    def place_in(self, lo: int, hi: int, utter: tuple[str, str], op: str,
                 facts: list[str]) -> int:
        """在 [lo, hi) 的空位里随机放一轮（干扰项必须落在提问之前）。"""
        free = [x for x in range(max(0, lo), min(hi, self.T)) if x not in self.slots]
        if not free:
            raise RuntimeError(f"{self.id}: [{lo},{hi}) 没有空位")
        t = int(self.rng.choice(free))
        self.slots[t] = Turn(t=t, user=utter[0], assistant=utter[1], op=op, facts=facts)
        return t

    def free_t(self, lo: int, hi: int) -> int:
        """[lo, hi) 里随机一个起点（place 会顺延到空位）。"""
        return int(self.rng.integers(lo, max(lo + 1, hi)))

    def build(self) -> Stream:
        getattr(self, f"_build_{self.dim}")()
        turns = []
        for t in range(self.T):
            if t in self.slots:
                turns.append(self.slots[t])
            else:
                u, a = FILLER[int(self.rng.integers(len(FILLER)))]
                turns.append(Turn(t=t, user=u, assistant=a))
        self.probes.sort(key=lambda p: (p.t, p.id))
        return Stream(id=self.id, dimension=self.dim, seed=self.seed, turns=turns,
                      probes=self.probes, facts=list(self.facts.values()))

    # ---- 各维度 ----
    def _build_R(self):
        for lag in LEVELS["R"]:
            for _ in range(PER_LEVEL["R"]):
                subj, val = self.subject(), self.token()
                f = self.fact(subj, "", val, 0)
                t = self.place(self.free_t(0, self.T - lag - 8), say_set(subj, "", val),
                               "set", [f.id])
                f.t_valid[0] = t
                u, _ = say_set(subj, "", val)
                self.probe(t + lag, lag, ask(subj), [val], [],
                           f"[t={t}] {u}", {val: "current"})

    def _build_V(self):
        gap = 6
        for k in LEVELS["V"]:
            for _ in range(PER_LEVEL["V"]):
                subj = self.subject()
                vals = [self.token() for _ in range(k + 1)]
                t = self.place(self.free_t(0, self.T - gap * k - 20),
                               say_set(subj, "", vals[0]), "set", [])
                prev = self.fact(subj, "", vals[0], t)
                self.slots[t].facts = [prev.id]
                for v in vals[1:]:
                    t = self.place(t + gap, say_update(subj, "", v), "update", [])
                    f = self.fact(subj, "", v, t, supersedes=prev.id)
                    prev.t_valid[1], prev.status = t, "superseded"
                    self.slots[t].facts = [f.id]
                    prev = f
                u, _ = say_update(subj, "", vals[-1])
                cands = {v: "stale" for v in vals[:-1]} | {vals[-1]: "current"}
                self.probe(t + 10, k, ask(subj), [vals[-1]], vals[:-1],
                           f"[t={t}] {u}", cands)

    def _build_P(self):
        for d in LEVELS["P"]:
            for _ in range(PER_LEVEL["P"]):
                subjs = [self.subject() for _ in range(d + 1)]
                vals = [self.token() for _ in range(d + 1)]
                new_up = self.token()
                t0 = self.free_t(0, self.T - 3 * d - 40)
                t = self.place(t0, say_set(subjs[0], "", vals[0]), "set", [])
                up = self.fact(subjs[0], "", vals[0], t)
                self.slots[t].facts = [up.id]
                chain = [up]
                for i in range(1, d + 1):
                    t = self.place(t + 3, say_derive(subjs[i - 1], vals[i - 1],
                                                     subjs[i], vals[i]), "derive", [])
                    f = self.fact(subjs[i], "", vals[i], t, kind="derived",
                                  depends_on=chain[-1].id)
                    self.slots[t].facts = [f.id]
                    chain.append(f)
                t = self.place(t + 20, say_update(subjs[0], "", new_up), "update", [])
                nf = self.fact(subjs[0], "", new_up, t, supersedes=up.id)
                up.t_valid[1], up.status = t, "superseded"
                for f in chain[1:]:
                    f.t_valid[1], f.status = t, "invalidated"
                self.slots[t].facts = [nf.id]
                u, _ = say_update(subjs[0], "", new_up)
                self.probe(t + 10, d, ask(subjs[d]), [new_up], [vals[d]],
                           f"[t={t}] {u}",
                           {vals[d]: "stale", new_up: "current"})

    def _build_C(self):
        for n in LEVELS["C"]:
            for _ in range(PER_LEVEL["C"]):
                subj = self.subject()
                scopes = list(self.rng.choice(SCOPES, size=n, replace=False))
                vals = [self.token() for _ in scopes]
                t = self.free_t(0, self.T - 3 * n - 30)
                stmts = {}
                for sc, v in zip(scopes, vals):
                    t = self.place(t + 2, say_set(subj, sc, v), "set", [])
                    f = self.fact(subj, sc, v, t)
                    self.slots[t].facts = [f.id]
                    stmts[sc] = f"[t={t}] {say_set(subj, sc, v)[0]}"
                i = int(self.rng.integers(n))
                target, gold = scopes[i], vals[i]
                cands = {v: "conflated" for v in vals} | {gold: "current"}
                self.probe(t + 15, n, ask(subj, target), [gold], [],
                           stmts[target], cands)

    def _build_F(self):
        for gap in LEVELS["F"]:
            for _ in range(PER_LEVEL["F"]):
                subj, val = self.subject(), self.token()
                t = self.place(self.free_t(0, self.T - gap - 20),
                               say_set(subj, "", val), "set", [])
                f = self.fact(subj, "", val, t)
                self.slots[t].facts = [f.id]
                t = self.place(t + 5, say_retract(subj, ""), "retract", [f.id])
                f.t_valid[1], f.status = t, "retracted"
                self.probe(t + gap, gap, ask(subj), [], [val],
                           f"[t={t}] {say_retract(subj, '')[0]}",
                           {val: "stale", "__ABSENT__": "abstain-ok"})

    def _build_I(self):
        lag = 40
        for m in LEVELS["I"]:
            for _ in range(PER_LEVEL["I"]):
                head = self.fresh_head()
                subj, val = self.subject(head), self.token()
                t = self.place(self.free_t(260, self.T - lag - 5),
                               say_set(subj, "", val), "set", [])
                f = self.fact(subj, "", val, t)
                self.slots[t].facts = [f.id]
                pt = t + lag
                # 同头词、不同后缀的相似事实（部分带作用域以凑足数量），都排在提问之前
                pool = [(s, sc) for s in (head + x for x in SUFFIXES) if s != subj
                        for sc in [""] + SCOPES]
                self.rng.shuffle(pool)
                for s, sc in pool[:m]:
                    dv = self.token()
                    dt = self.place_in(0, pt, say_set(s, sc, dv), "distractor", [])
                    df = self.fact(s, sc, dv, dt)
                    self.slots[dt].facts = [df.id]
                u, _ = say_set(subj, "", val)
                self.probe(pt, m, ask(subj), [val], [], f"[t={t}] {u}",
                           {val: "current"})


def generate(seeds: int = 5, dims: tuple = DIMENSIONS, seed0: int = 0) -> list[Stream]:
    out = []
    for dim in dims:
        for s in range(seed0, seed0 + seeds):
            out.append(_Builder(dim, s).build())
    return out
