"""信号消费者：LLM 语义工作的默认执行体（P2 后引擎不做语义判定）。

引擎 observe/retrieve/step 把语义工作以信号形式排进 SignalQueue；
worker 拉取、调 semantics（judge / relevant_set / consolidate——
只有这些方法允许是 LLM），再经引擎操作面回报：
  conflict_pending  → sem.judge        → submit_verdicts
  feedback_pending  → sem.relevant_set → submit_relevance
  maintenance_due   → sem.consolidate  → add_reflection
  thin_recall       → 仅计数（召回质量遥测，无动作）

只摘自己认识的信号种类（SignalQueue.take），其余原位留给别的消费者
（recall_miss / extract_due 归 agent worker）。

锁纪律：构造时可传入 lock（sidecar 的服务锁）。所有引擎读写都在锁内，
LLM 调用一律在锁外——否则一次几秒的裁判会把 /search 卡死。
不传 lock 时退化为无锁单线程（实验脚本）。

同步实现：process(t) 一次排空自己那部分队列。外部 agent runtime
可不经过本类：直接 drain_signals + 自己的裁判 + submit_*——
memory_conflicts / memory_resolve 工具就是这个模式。
无 worker 时信号有界堆积、n_dropped 计数，引擎照常运转。
"""
from __future__ import annotations

import sys
from contextlib import nullcontext

from .core import maintenance
from .core.types import ConsolidationSemantics, FeedbackSemantics, is_visible

KINDS = frozenset({"conflict_pending", "feedback_pending",
                   "maintenance_due", "thin_recall"})


def _requeue_merge(old, new):
    """回队信号的合并规则：list payload 去重拼接，其余取新。"""
    if isinstance(old, list) and isinstance(new, list):
        return old + [x for x in new if x not in old]
    return new


class SignalWorker:
    def __init__(self, eng, semantics, lock=None):
        self.eng = eng
        self.sem = semantics
        self._lock = lock if lock is not None else nullcontext()
        self.n_calls = 0       # 语义调用计数（judge/relevant_set/consolidate）
        self.n_recog_fail = 0  # 识别器失败计数：失败退化 selected-hit，必须外显

    def process(self, t: int, kinds: set | None = None) -> dict:
        """处理自己那部分信号。kinds 非 None 时只处理指定种类（仍限于本
        worker 认识的种类）。失败的信号回队重试。返回处理统计。"""
        stats = {"judged": 0, "resolved": 0, "credited": 0,
                 "reflected": 0, "thin": 0, "recog_fail": 0, "errors": 0}
        wanted = KINDS if kinds is None else (KINDS & set(kinds))
        with self._lock:
            batch = self.eng.signals.take(wanted)
        requeue = []
        for sig in batch:
            try:
                if sig.kind == "conflict_pending":
                    stats["resolved"] += self._judge(sig.payload, t, stats)
                elif sig.kind == "feedback_pending":
                    stats["credited"] += self._recognize(sig.payload, t, stats)
                elif sig.kind == "maintenance_due":
                    stats["reflected"] += self._consolidate(sig.payload, t)
                elif sig.kind == "thin_recall":
                    stats["thin"] += 1
            except Exception as exc:         # noqa: BLE001
                # 单信号失败不能拖垮整批；已摘出队列，不回队就是丢
                stats["errors"] += 1
                requeue.append(sig)
                print(f"[worker] 信号 {sig.kind} 处理失败（已回队）: "
                      f"{type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)
        if requeue:
            with self._lock:
                for sig in requeue:
                    self.eng.signals.emit(sig.kind, sig.payload, sig.t,
                                          key=sig.key, merge=_requeue_merge)
        return stats

    def _judge(self, pairs, t: int, stats: dict) -> int:
        """对一批 tension 对调 judge 并批量回报。死对/链塌缩对以 pending
        回报——submit_verdicts 的清理路径会摘掉对应 tension。"""
        # 阶段 1（锁内）：把 id 对解析成裁判输入
        jobs = []
        seen = set()
        with self._lock:
            for left, right in pairs:
                key = tuple(sorted((left, right)))
                if key in seen:
                    continue
                seen.add(key)
                a, b = self.eng.mems.get(key[0]), self.eng.mems.get(key[1])
                if a is None or b is None:
                    jobs.append((key, None))
                    continue
                a = maintenance.follow_chain(self.eng, a)
                b = maintenance.follow_chain(self.eng, b)
                if a.id == b.id:
                    jobs.append((key, None))
                    continue
                jobs.append((key, (a.belief_id, a.value, b.belief_id, b.value)))
        # 阶段 2（锁外）：LLM
        verdicts = []
        for key, args in jobs:
            if args is None:
                verdicts.append((key[0], key[1], "pending"))
                continue
            self.n_calls += 1
            stats["judged"] += 1
            verdicts.append((key[0], key[1], self.sem.judge(*args)))
        # 阶段 3（锁内）：回报
        with self._lock:
            return self.eng.submit_verdicts(verdicts, t)

    def _recognize(self, payload, t: int, stats: dict) -> int:
        ret = payload["retrieval"]
        with self._lock:
            if ret.credited:
                return 0
            texts = [m.text for m in ret.selected]
        fn = (self.sem.relevant_set
              if isinstance(self.sem, FeedbackSemantics) else None)
        if fn is None:
            used = [True] * len(texts)   # 无 recognizer → selected-hit
        else:
            self.n_calls += 1
            used = fn(texts, payload["question"], payload["answer"])
        # 识别器失败（None=传输/解析失败；长度不齐=违反协议）：计数外显 +
        # 退化 selected-hit——不抛异常，否则毒信号每次回队重炸整批
        if used is None or len(used) != len(texts):
            self.n_recog_fail += 1
            stats["recog_fail"] += 1
            if self.n_recog_fail == 1:
                print("[worker] recognizer 失败（第 1 次），"
                      "credit 退化 selected-hit", file=sys.stderr, flush=True)
            used = [True] * len(texts)
        with self._lock:
            if ret.credited:      # 锁外期间被别人结清（极少见），不双计
                return 0
            return self.eng.submit_relevance(ret, used, t)

    def _consolidate(self, payload, t: int) -> int:
        if not isinstance(self.sem, ConsolidationSemantics):
            return 0
        with self._lock:
            mems = sorted(
                (m for i in payload["ids"]
                 if (m := self.eng.mems.get(i)) is not None
                 and is_visible(m) and not m.pending_review
                 and m.kind == "fact"),
                key=lambda m: (m.birth, m.id))
            if len(mems) < self.eng.cfg.consolidation_min_items:
                return 0
        self.n_calls += 1
        event = self.sem.consolidate(mems, t)
        if event is None:
            return 0
        with self._lock:
            self.eng.add_reflection(event, payload["ids"], t)
        return 1
