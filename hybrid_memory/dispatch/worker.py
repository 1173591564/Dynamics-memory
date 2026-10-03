"""语义后台循环（P5 从 service.py 迁入）：claim→判裁→落库→应用。

run_semantic_tasks 经门面调 svc._semantic_model：测试用实例属性 stub
模型（_semantic_model = lambda），只有经 svc 属性查找 stub 才生效；
应用侧 apply_semantic 无外部 stub，直接调本模块函数。
DispatchWorker（P6 落地，TrioWorker 继任）只驱动工作流 kind；
语义 kind 仍走 run_semantic_tasks（独立驱动，合并不在 P6）。
"""
from __future__ import annotations

import copy
import sys
import threading
from dataclasses import asdict

from ..core import maintenance
from ..core.types import (ConsolidationSemantics, FeedbackSemantics,
                          is_visible)
from ..agents import payload
from ..store.tasks import SEMANTIC_KINDS, WORKFLOW_KINDS, TaskLeaseLost
from . import effects, policy


def semantic_model(svc, row):
    """只读取判定输入；调用外部语义模型时不持服务锁。"""
    kind, payload = row["kind"], row["payload"]
    with svc._lock:
        svc._ensure_healthy()
        if kind == "conflict_pending":
            jobs = []
            for left, right in payload:
                a, b = svc.engine.mems.get(left), svc.engine.mems.get(right)
                if a is not None and b is not None:
                    a, b = maintenance.follow_chain(svc.engine, a), maintenance.follow_chain(svc.engine, b)
                args = ((a.belief_id, a.value, b.belief_id, b.value)
                        if a is not None and b is not None and a.id != b.id else None)
                tension = svc.engine.tensions.get(tuple(sorted((left, right))))
                stamp = [tension.last_seen, tension.observations] if tension else None
                jobs.append((left, right, args, stamp))
        elif kind == "feedback_pending":
            texts = payload.get("texts")
            selected = payload.get("selected")
            if (not isinstance(texts, list) or not isinstance(selected, list)
                    or len(texts) != len(selected)):
                raise ValueError("反馈文本快照与入选记忆不匹配")
        elif kind == "maintenance_due":
            sources = [[i, m.last_seen, m.pool.value, m.superseded_by, m.aggregated_into]
                       for i in payload["ids"] if (m := svc.engine.mems.get(i)) is not None]
            mems = sorted((copy.deepcopy(m) for i in payload["ids"]
                           if (m := svc.engine.mems.get(i)) is not None
                           and is_visible(m) and not m.pending_review and m.kind == "fact"),
                          key=lambda m: (m.birth, m.id))
    # H27/N15：svc.semantics 可能是 SemanticsProvider 包装——能力判定看
    # delegate，调用走 provider（计数与降级可观测）。
    from ..semantics.provider import SemanticsProvider
    sem = svc.semantics
    delegate = sem.delegate if isinstance(sem, SemanticsProvider) else sem
    if kind == "conflict_pending":
        return {"verdicts": [[a, b, sem.judge(*args) if args else "pending", stamp]
                             for a, b, args, stamp in jobs]}
    if kind == "feedback_pending":
        fn = sem.relevant_set if isinstance(delegate, FeedbackSemantics) else None
        used = fn(texts, payload["question"], payload["answer"]) if fn else [True] * len(texts)
        failed = used is None or len(used) != len(texts)
        if failed:
            used = [True] * len(texts)
        return {"used": [bool(u) for u in used], "recog_fail": failed}
    if kind == "maintenance_due":
        if (not isinstance(delegate, ConsolidationSemantics)
                or len(mems) < svc.cfg.consolidation_min_items):
            return {"event": None, "sources": sources}
        event = sem.consolidate(mems, row["t"])
        return {"event": asdict(event) if event is not None else None, "sources": sources}
    raise ValueError(f"未知语义任务 {kind}")


def apply_semantic(svc, row):
    """事务性应用已落库的模型结果；分支走 EFFECTS 表。

    prepare_effect 在锁外预计算向量（N08：模型/向量准备一律锁外），
    计划经 plan 参数穿进 applier。"""
    plan = effects.prepare_effect(svc, row)
    with svc._lock, svc._rollback_effect():
        old_ret = None
        if row["kind"] == "feedback_pending":
            old_ret = svc._retrievals.get(row["payload"]["retrieval_id"])
            ret_fields = dict(old_ret.__dict__) if old_ret is not None else None
        try:
            def mutate(conn, result):
                q = svc.engine.signals
                old_emit = q.on_emit

                def collect(kind, payload, t, key, merge):
                    if kind in SEMANTIC_KINDS | WORKFLOW_KINDS or kind in ("recall_miss", "extract_due"):
                        return svc.tasks._enqueue(
                            conn, kind, effects.signal_payload(svc, kind, payload), t,
                            key=key, merge=merge, memory_next_id=svc.engine._next_id)
                    return old_emit(kind, payload, t, key, merge)

                q.on_emit = collect
                try:
                    applier = effects.EFFECTS[row["kind"]].apply
                    if applier is None:
                        raise ValueError(f"无 dispatch applier: {row['kind']}")
                    return applier(svc, row, result, plan=plan)
                finally:
                    q.on_emit = old_emit

            out, revision = svc.tasks.complete(
                row["id"], row["token"], mutate,
                svc._dump_state, svc._checkpoint_revision)
            svc._checkpoint_revision = revision
            svc._kick()
            return out
        except BaseException:
            if old_ret is not None:
                old_ret.__dict__.clear()
                old_ret.__dict__.update(ret_fields)
            raise


def run_semantic_tasks(svc, limit: int = 8) -> dict:
    """先持久化模型结果，再事务性应用；队列失败可见且独立于调查员。"""
    stats = {"judged": 0, "resolved": 0, "credited": 0,
             "reflected": 0, "thin": 0, "recog_fail": 0, "errors": 0}
    if not svc._semantic_busy.acquire(blocking=False):
        return stats
    try:
        with svc._lock:
            stats["thin"] = len(svc.engine.signals.take(("thin_recall",)))
        svc.tasks.recover_expired(kinds=SEMANTIC_KINDS,
                                  reset_next_run_at=True)
        for item in svc.tasks.list_tasks(states=("pending", "ready"), kinds=SEMANTIC_KINDS,
                                         due_before=svc.tasks.clock(), limit=limit):
            row = None
            try:
                with svc._lock:
                    svc._ensure_healthy()
                    row = svc.tasks.claim(item["id"],
                                          expected_version=item["version"])
                if row is None:
                    continue
                if row["state"] == "running":
                    # N10：语义路径同样封存（payload 已冻结在库，摘要绑定 +
                    # 快照 revision + 协议版本）。
                    with svc._lock:
                        seal_revision = svc._checkpoint_revision
                    svc.tasks.store_call_context(
                        row["id"], row["token"],
                        payload.seal_context(row["kind"], row["payload"],
                                             seal_revision))
                    result = svc._semantic_model(row)
                    if row["kind"] == "conflict_pending":
                        stats["judged"] += len(result["verdicts"])
                    svc.tasks.store_result(row["id"], row["token"], result)
                    with svc._lock:
                        svc._ensure_healthy()
                        row = svc.tasks.claim(row["id"],
                                              expected_version=row["version"])
                    if row is None:
                        continue
                out = apply_semantic(svc, row)
                for key in ("resolved", "credited", "reflected", "recog_fail"):
                    stats[key] += out.get(key, 0)
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                if row is not None:
                    try:
                        svc.tasks.retry(row["id"], row["token"], exc)
                    except TaskLeaseLost:
                        pass  # 产物已落库或其他领取者获权，不覆盖它
                print(f"[memory-sidecar] 语义任务 {item['id']} 待重试: "
                      f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                if svc._checkpoint_fault:
                    break
        return stats
    finally:
        svc._semantic_busy.release()


class DispatchWorker:
    """工作流后台循环（P6：TrioWorker 继任；语义 kind 仍走 run_semantic_tasks）。

    claim→run_agent→store_result→claim→EFFECTS-apply→complete；
    认领状态与重试上限来自 policies（默认值与旧硬编码一致）。
    """

    def __init__(self, service, runner, policies=None, *, idle_s=2, lease_s=600):
        self.svc, self.run_agent = service, runner
        self.policies = policies if policies is not None else policy.POLICIES
        self.idle_s, self.lease_s = idle_s, lease_s
        # 三工作流 kind 同策略，认领状态任取其一（现均为 pending/ready）。
        self._claim_from = self.policies["hauler_due"].claim_from
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._busy = threading.Lock()
        self._processed = 0
        self._errors = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._wake.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="memory-dispatch")
        self._thread.start()

    def stop(self, timeout=5):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def notify(self) -> None:
        self._wake.set()

    def stats(self) -> dict:
        return {"processed": self._processed, "errors": self._errors}

    def _loop(self):
        while True:
            self._wake.wait(self.idle_s)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                self.process_once()
            except Exception as exc:
                print(f"[memory-dispatch] {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)

    def _apply(self, conn, row, output, plan=None):
        applier = effects.EFFECTS[row["kind"]].apply
        if applier is None:
            raise ValueError(f"无 dispatch applier: {row['kind']}")
        return applier(self.svc, row, output, conn, plan=plan)

    def process_once(self, limit=8):
        if not self._busy.acquire(False):
            return 0
        done = 0
        try:
            store = self.svc.tasks
            store.recover_expired(kinds=WORKFLOW_KINDS, reset_next_run_at=True)
            for item in store.list_tasks(states=self._claim_from,
                                         kinds=WORKFLOW_KINDS,
                                         due_before=store.clock(),
                                         limit=limit):
                if self._stop.is_set():
                    break
                row = store.claim(item["id"], expected_version=item["version"],
                                          lease_s=self.lease_s)
                if row is None:
                    continue
                try:
                    if row["state"] == "running":
                        name = row["kind"].removesuffix("_due")
                        task_payload = payload.build_payload(row["kind"], self.svc, row)
                        with self.svc.lock:
                            revision = self.svc._checkpoint_revision
                        # N10：模型调用前封存输入上下文（窗口/规则/移交 ids、
                        # 快照 revision、协议版本、正文摘要）；校验对照封存值。
                        store.store_call_context(
                            row["id"], row["token"],
                            payload.seal_context(row["kind"], task_payload, revision))
                        result = self.run_agent(name, task_payload)
                        store.store_result(row["id"], row["token"], result,
                            rule_ids=[r["id"] for r in task_payload["rules"]])
                        row = store.claim(row["id"], expected_version=row["version"],
                                          lease_s=self.lease_s)
                        if row is None:
                            continue
                    # N08：向量/静态校验在服务锁外完成（prepare_effect），
                    # 计划穿进事务；事务内逐目标复核邮戳漂移。
                    plan = effects.prepare_effect(self.svc, row)
                    with self.svc.lock, self.svc._rollback_effect():
                        _, revision = store.complete(
                            row["id"], row["token"],
                            lambda conn, output: self._apply(conn, row, output, plan),
                            self.svc._dump_state, self.svc._checkpoint_revision)
                        self.svc._checkpoint_revision = revision
                    done += 1
                except Exception as exc:
                    self._errors += 1
                    try:
                        store.retry(row["id"], row["token"], exc,
                            max_attempts=self.policies[row["kind"]].max_attempts,
                            retry_model=isinstance(exc, ValueError))
                    except TaskLeaseLost:
                        pass
                    print(f"[memory-dispatch] task {row['id']}: {type(exc).__name__}: {exc}",
                          file=sys.stderr, flush=True)
            self._processed += done
            return done
        finally:
            self._busy.release()
