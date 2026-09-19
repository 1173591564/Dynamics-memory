"""信号消费者：LLM 语义工作的默认执行体（P2 后引擎不做语义判定）。

引擎 observe/retrieve/step 把语义工作以信号形式排进 SignalQueue；
worker 拉取、调 semantics（judge / relevant_set / consolidate——
只有这些方法允许是 LLM），再经引擎操作面回报：
  conflict_pending  → sem.judge        → submit_verdicts
  feedback_pending  → sem.relevant_set → submit_relevance
  maintenance_due   → sem.consolidate  → add_reflection
  thin_recall       → 仅计数（召回质量遥测，无动作）

同步实现：process(t) 一次排空队列，与原同步语义等价但走信号通路。
agent runtime（opencode 等）可不经过本类：直接 drain_signals + 自己的
裁判 + submit_*——memory_conflicts / memory_resolve 工具就是这个模式。
无 worker 时信号有界堆积、n_dropped 计数，引擎照常运转。
"""
from __future__ import annotations

from .core import maintenance
from .core.types import ConsolidationSemantics, FeedbackSemantics, is_visible


def _requeue_merge(old, new):
    """回队信号的合并规则：list payload 去重拼接，其余取新。"""
    if isinstance(old, list) and isinstance(new, list):
        return old + [x for x in new if x not in old]
    return new


class SignalWorker:
    def __init__(self, eng, semantics):
        self.eng = eng
        self.sem = semantics
        self.n_calls = 0       # 语义调用计数（judge/relevant_set/consolidate）

    def process(self, t: int, kinds: set | None = None) -> dict:
        """排空信号队列。kinds 非 None 时只处理指定种类，未匹配的信号
        重新入队（按引擎合并规则归位）。返回处理统计。"""
        stats = {"judged": 0, "resolved": 0, "credited": 0,
                 "reflected": 0, "thin": 0}
        requeue = []
        for sig in self.eng.drain_signals():
            if kinds is not None and sig.kind not in kinds:
                requeue.append(sig)
            elif sig.kind == "conflict_pending":
                stats["resolved"] += self._judge(sig.payload, t, stats)
            elif sig.kind == "feedback_pending":
                stats["credited"] += self._recognize(sig.payload, t)
            elif sig.kind == "maintenance_due":
                stats["reflected"] += self._consolidate(sig.payload, t)
            elif sig.kind == "thin_recall":
                stats["thin"] += 1
            else:
                requeue.append(sig)          # 未知信号不吞，回队
        for sig in requeue:
            self.eng.signals.emit(sig.kind, sig.payload, sig.t,
                                  key=sig.key, merge=_requeue_merge)
        return stats

    def _judge(self, pairs, t: int, stats: dict) -> int:
        """对一批 tension 对调 judge 并批量回报。死对/链塌缩对以 pending
        回报——submit_verdicts 的清理路径会摘掉对应 tension。"""
        verdicts = []
        seen = set()
        for left, right in pairs:
            key = tuple(sorted((left, right)))
            if key in seen:
                continue
            seen.add(key)
            a, b = self.eng.mems.get(key[0]), self.eng.mems.get(key[1])
            if a is None or b is None:
                verdicts.append((key[0], key[1], "pending"))
                continue
            a = maintenance.follow_chain(self.eng, a)
            b = maintenance.follow_chain(self.eng, b)
            if a.id == b.id:
                verdicts.append((key[0], key[1], "pending"))
                continue
            self.n_calls += 1
            stats["judged"] += 1
            verdicts.append((key[0], key[1],
                             self.sem.judge(a.belief_id, a.value,
                                            b.belief_id, b.value)))
        return self.eng.submit_verdicts(verdicts, t)

    def _recognize(self, payload, t: int) -> int:
        ret = payload["retrieval"]
        if ret.credited:
            return 0
        fn = (self.sem.relevant_set
              if isinstance(self.sem, FeedbackSemantics) else None)
        if fn is None:
            used = [True] * len(ret.selected)   # 无 recognizer → selected-hit
        else:
            self.n_calls += 1
            used = fn([m.text for m in ret.selected],
                      payload["question"], payload["answer"])
        if len(used) != len(ret.selected):
            raise RuntimeError(
                f"relevant_set 返回长度 {len(used)} != selected "
                f"{len(ret.selected)}")
        return self.eng.submit_relevance(ret, used, t)

    def _consolidate(self, payload, t: int) -> int:
        if not isinstance(self.sem, ConsolidationSemantics):
            return 0
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
        self.eng.add_reflection(event, payload["ids"], t)
        return 1
