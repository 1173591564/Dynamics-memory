"""MemoryEngine 门面：agent runtime 视角是 observe / retrieve / step。

信号化（P2）：引擎不做语义判定——不调用 judge / relevant_set /
consolidate。有活可干时向 SignalQueue 发射信号（conflict_pending /
feedback_pending / maintenance_due / thin_recall），worker 拉取信号、
自主调 LLM、再经操作面（submit_relevance / submit_verdicts /
add_reflection）回报。semantics 只剩本地谓词（relevant / valid / scope /
embedding_key，无网络调用）。无 worker 时引擎照常运转：tension 挂
backlog、检索以 contested 端出、信用停留在 pending——不静默丢活。
内部三回路拆在 ingest / retrieval / maintenance 模块。
"""
from __future__ import annotations

import numpy as np

from ..config import Cfg
from ..core.signals import SignalQueue
from ..core.types import (Event, Memory, MemorySemantics, Pool, Query,
                          Retrieval, Tension)
from .types import Embedder
from . import confidence, consolidation, ingest, maintenance, retrieval


class MemoryEngine:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics: MemorySemantics):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.mems: dict[int, Memory] = {}
        self.tensions: dict[tuple[int, int], Tension] = {}
        self._consolidation_pending: set[int] = set()
        self._consolidation_deferred: dict[str, frozenset[int]] = {}
        self._shadow_pending: list[tuple] = []   # (pair_key, m_id, t_ret, rel)
        self.n_shadow_dropped = 0
        self.signals = SignalQueue(cfg.signal_queue_cap)
        self._next_id = 0
        # 事件计数（遥测：/signals 的 engine_counters）
        self.n_promote = 0
        self.n_demote = 0
        self.n_evict = 0
        self.n_archive = 0
        self.n_revive = 0
        self.n_merge = 0
        self.n_collision = 0
        self.n_tension = 0
        self.n_resolve = 0
        self.n_agg = 0
        self.n_consolidate = 0
        self.n_chain_broken = 0   # supersede/aggregate 链断裂或成环（状态损坏痕迹）
        self.n_pool_truncated = 0   # C 迁 A + A 删除（H11/H12，P4）
        self.n_promote_rejected = 0   # M 满拒收晋升（H12，P4）

    def next_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    def add_tension(self, left: int, right: int, t: int) -> None:
        if not self.cfg.tension_on or left == right:
            return
        key = tuple(sorted((left, right)))
        tension = self.tensions.get(key)
        if tension is None:
            self.tensions[key] = Tension(key[0], key[1], t, t)
            self.n_tension += 1
            # 信号不在此发射：maintenance 对到达 tension_delay 的未决对
            # 统一发 conflict_pending（保持原同步裁决的老化时序语义）
        else:
            tension.last_seen = t
            tension.observations += 1

    def observe(self, events: list[Event], t: int) -> None:
        ingest.run_ingest(self, events, t)

    def retrieve(self, q_emb: np.ndarray, q: Query, t: int) -> Retrieval:
        return retrieval.run_retrieve(self, q_emb, q, t)

    def step(self, t: int) -> None:
        maintenance.run_maintenance(self, t)

    def feedback(self, ret: Retrieval, question: str, answer: str,
                 t: int) -> int:
        """response-level 记账（信号化）：不直接判 recognizer，把
        (retrieval, question, answer) 以 feedback_pending 信号交给
        worker；worker 判完经 submit_relevance 回报才真正入账。
        仅应在 cfg.defer_credit=True 时调用、且每次 retrieve 至多调一次。
        返回 0——入账是异步的，真实入账数由 submit_relevance 返回。"""
        if not ret.selected:
            return 0
        if ret.credited or ret.feedback_sent:
            raise RuntimeError(
                "feedback 重复调用：该 Retrieval 已结清或已在待判队列"
                "（defer_credit=False 时 retrieve 就地结算，不应再调 feedback）")
        ret.feedback_sent = True
        self.signals.emit("feedback_pending",
                          {"retrieval": ret, "question": question,
                           "answer": answer}, t)
        return 0

    def _current_representative(self, m: Memory) -> Memory | None:
        """迟到信用记到当前代表。链断裂时不返回尸体，避免复活已退役条目。"""
        target = maintenance.follow_chain(self, m)
        if target.superseded_by is not None or target.aggregated_into is not None:
            return None
        return target

    def _credit_hit(self, m: Memory, t: int) -> bool:
        target = self._current_representative(m)
        if target is None:
            return False
        target.last_hit = t
        if target.pool is Pool.ARCHIVE:
            target.pool = Pool.CANDIDATE if self.cfg.two_pool else Pool.MEMORY
            self.n_revive += 1
        target.hits += 1
        target.d_hit += 1.0
        return True

    def credit_shown(self, memory_ids: list, used: list, t: int) -> int:
        """注册表里的 Retrieval 已不在时，只按当时展示的 id 记账。"""
        n = 0
        for mid, flag in zip(memory_ids, used):
            m = self.mems.get(mid)
            if flag and m is not None and self._credit_hit(m, t):
                n += 1
        return n

    def submit_relevance(self, ret: Retrieval, used: list, t: int) -> int:
        """操作面：worker 回报 recognizer 结果（哪些入选记忆真被用上），
        发 useful-hit。语义与 feedback 的应用部分完全一致。"""
        if not ret.selected:
            return 0
        if ret.credited:
            raise RuntimeError(
                "relevance 重复记账：该 Retrieval 已结清"
                "（defer_credit=False 时 retrieve 就地结算，不应再回报）")
        n = 0
        for m, u in zip(ret.selected, used):
            if u and self._credit_hit(m, t):
                n += 1
        ret.n_useful = n
        ret.credited = True
        return n

    # ---- shadow 延迟记账（压制路径恒延迟：verdict 到达时结算）----
    def _record_shadow_pending(self, m: Memory, rival: Memory, t: int,
                               rel: bool) -> None:
        key = tuple(sorted((m.id, rival.id)))
        self._shadow_pending.append((key, m.id, t, bool(rel)))
        if len(self._shadow_pending) > self.cfg.shadow_pending_cap:
            self._shadow_pending.pop(0)
            self.n_shadow_dropped += 1

    def _issue_shadow_credit(self, m: Memory, t_ret: int) -> bool:
        target = self._current_representative(m)
        if target is None:
            return False
        target.d_shadow += 1.0
        target.last_hit = t_ret
        if target.pool is Pool.ARCHIVE:
            target.pool = Pool.CANDIDATE if self.cfg.two_pool else Pool.MEMORY
            self.n_revive += 1
        return True

    def _settle_shadow(self, pair_key: tuple, verdict: str) -> int:
        """首个 verdict 到达时结算该对全部待结算 shadow 信用
        （含 verdict=="pending"——与原同步语义一致：只要非 synonym 就发）。
        返回实际结算条数。"""
        n = 0
        keep = []
        for entry in self._shadow_pending:
            key, mid, t_ret, rel = entry
            if key != pair_key:
                keep.append(entry)
                continue
            m = self.mems.get(mid)
            if verdict != "synonym" and rel and m is not None and self._issue_shadow_credit(m, t_ret):
                n += 1
        self._shadow_pending = keep
        return n

    def submit_verdicts(self, verdicts, t: int) -> int:
        """操作面：worker 回报批量 tension 裁决 [(left, right, verdict)]。
        verdict=="pending" 保持 backlog 不消解。返回实际消解条数。"""
        n = 0
        for left, right, verdict in verdicts:
            key = tuple(sorted((left, right)))
            self._settle_shadow(key, verdict)
            if key not in self.tensions:
                continue
            a, b = self.mems.get(key[0]), self.mems.get(key[1])
            if a is None or b is None:
                del self.tensions[key]
                continue
            a = maintenance.follow_chain(self, a)
            b = maintenance.follow_chain(self, b)
            if a.id == b.id:
                del self.tensions[key]
                continue
            if verdict == "pending":
                continue
            del self.tensions[key]
            self.n_resolve += 1
            confidence.discount_to(a, t, self.cfg)   # 消解前折损对齐 V 数学
            confidence.discount_to(b, t, self.cfg)
            maintenance.apply_resolution(self, a, b, verdict, t)
            n += 1
        return n

    def add_reflection(self, event: Event, derived_from, t: int,
                       vector=None) -> Memory:
        """操作面：worker 回报 consolidation 产物（reflection 记忆入库）。
        derived_from 为源记忆 id 列表；vector 为 prepare_effect 预计算值。"""
        chosen = sorted((self.mems[i] for i in derived_from
                         if i in self.mems), key=lambda m: (m.birth, m.id))
        return consolidation.admit_reflection(self, event, chosen, t, vector=vector)

    def drain_signals(self) -> list:
        """worker 拉取待处理信号（清空队列）。"""
        return self.signals.drain()

    # ---- 衔尾蛇：拉式提取的信号面与操作面 ----
    # 引擎仍不调 LLM。这里只把"有活可干"变成小载荷信号（不含日志原文），
    # 由 agent worker 拉证据、经 propose 回报。

    @staticmethod
    def miss_key(q: str) -> str:
        return "miss:" + "".join(q.split()).lower()[:200]

    def report_miss(self, q: str, t: int, *, hint: str = "",
                    source: str = "", retrieval: Retrieval | None = None,
                    entities: tuple = (), retrieved: list[dict] | None = None) -> None:
        """记忆没接住一次需求：发 recall_miss。来源 source ∈
        {recognizer_none, correction, agent_tool, thin, external}。
        同一问题在队列里只留一条，新的 hint/source 合并进去。
        载荷带上当时已召回的记忆 id/文本，供调查员避免重复提议。"""
        if not q or not q.strip():
            return
        if retrieved is None:
            retrieved = [{"id": m.id, "t": m.birth, "text": m.text}
                         for m in (retrieval.selected if retrieval else [])]
        payload = {"q": q, "hints": [hint] if hint else [],
                   "sources": [source] if source else [],
                   "retrieved": retrieved, "entities": list(entities),
                   "first_t": t}

        def merge(old, new):
            for k in ("hints", "sources"):
                old[k] = old[k] + [x for x in new[k] if x not in old[k]]
            if new["retrieved"] and not old["retrieved"]:
                old["retrieved"] = new["retrieved"]
            old["entities"] = list(dict.fromkeys(old["entities"]
                                                 + new["entities"]))
            return old

        self.signals.emit("recall_miss", payload, t,
                          key=self.miss_key(q), merge=merge)

    def report_unit(self, unit_id: int, t: int, *, scene: str = "",
                    reasons: tuple = (), entities: tuple = ()) -> None:
        """触发扫描命中的日志单元：发 extract_due，调查员以该 unit 为锚
        做带上下文（timeline）的定向抽取。按 unit 去重，原因并集。"""
        if not reasons:
            return
        payload = {"unit_id": int(unit_id), "scene": scene,
                   "reasons": list(dict.fromkeys(reasons)),
                   "entities": list(dict.fromkeys(entities))}

        def merge(old, new):
            old["reasons"] = list(dict.fromkeys(old["reasons"] + new["reasons"]))
            old["entities"] = list(dict.fromkeys(old["entities"]
                                                 + new["entities"]))
            return old

        self.signals.emit("extract_due", payload, t,
                          key=f"unit:{int(unit_id)}", merge=merge)

    def propose(self, events: list[Event], t: int, vectors=None) -> list[int]:
        """操作面：agent 提议的记忆入库。与 observe 走同一条 ingest 回路
        （同样 dedup、同样进 C 池、同样动力学）——提议不享有任何捷径。
        vectors 为 prepare_effect 预计算值（§2.5）。返回本次真正新建的
        memory id（verbatim 命中已有条目的不在其中）。"""
        for ev in events:
            if ev.origin == "passive":
                raise ValueError("propose 的 Event 必须标明非 passive 的 origin")
        before = self._next_id
        ingest.run_ingest(self, events, t, vectors=vectors)
        return list(range(before, self._next_id))

    # ---- 遥测 ----
    def pool_sizes(self) -> dict[str, int]:
        out = {p.value: 0 for p in Pool}
        for m in self.mems.values():
            out[m.pool.value] += 1
        return out
