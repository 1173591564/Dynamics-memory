"""AgentWorker：从 SQLite 领取调查任务，保存产物，再幂等写回。

pending → running → ready → applying → done；异常有限重试，耗尽保留 dead。
调查信号直接持久化到 SQLite，不再保留内存镜像。
同一个 worker 同时只跑一次；SQLite 租约/token 防同任务重复领取和迟到写入。
模型调用可能重做，但已保存的产物不再问模型；任务效果与回执同事务 checkpoint。
每日调查次数和完成任务 TTL 去重持久化。工具预算仍按每次调查尝试单独开关。
before/origin 在首次领取时冻结，工具与最终 JSON 均沿用；不重建历史引擎。
不领取语义任务；sidecar 的语义任务由独立 SQLite 消费路径负责。
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import asdict
import math
import secrets
import sys
import threading
from typing import Callable

from ..investigation_context import CausalViolation, InvestigationContext
from ..core.signals import Signal
from ..taskstore import TaskLeaseLost
from .investigator import Budget, Investigation, build_payload

ORIGIN_BY_KIND = {"recall_miss": "repair", "extract_due": "extract"}


class AgentWorker:
    def __init__(self, service, investigate: Callable[[dict], Investigation | None],
                 *, budget: Budget | None = None, daily_cap: int = 200,
                 max_attempts: int = 2, dedupe_ttl_s: float = 24 * 3600,
                 idle_s: float = 2.0, before_for: Callable | None = None,
                 max_apply_attempts: int = 3, retry_delay_s: float = 0,
                 lease_s: float | None = None):
        self.svc = service
        self.investigate = investigate
        self.budget = budget or Budget()
        self.daily_cap = int(daily_cap)
        self.max_attempts = int(max_attempts)
        self.dedupe_ttl_s = float(dedupe_ttl_s)
        self.idle_s = float(idle_s)
        self.before_for = before_for or (lambda sig: sig.t + 1)
        self.max_apply_attempts = int(max_apply_attempts)
        self.retry_delay_s = float(retry_delay_s)
        self.lease_s = float(lease_s if lease_s is not None else self.budget.timeout_s + 60)
        if (self.max_attempts < 1 or self.max_apply_attempts < 1
                or not math.isfinite(self.lease_s) or self.lease_s <= 0
                or not math.isfinite(self.retry_delay_s) or self.retry_delay_s < 0
                or not math.isfinite(self.dedupe_ttl_s) or self.dedupe_ttl_s < 0):
            raise ValueError("attempt limits/lease must be positive; delays/TTL finite and non-negative")
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._busy = threading.Lock()
        self.n_runs = 0
        self.n_failed = 0
        self.n_gave_up = 0
        self.n_skipped_recent = 0
        self.n_proposed = 0
        self.n_accepted = 0
        self.n_verdicts = 0
        self.n_diagnosed = 0

    # ---- 生命周期 ----
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="memory-agent",
                                        daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            if not self._thread.is_alive():
                self._thread = None

    def notify(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(self.idle_s)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                self.process_once()
            except Exception as exc:     # noqa: BLE001  后台线程绝不能死
                print(f"[agent] 循环异常: {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)

    # ---- 一轮 ----
    def process_once(self, max_signals: int | None = None) -> dict:
        """以 SQLite 为事实源，逐个领取；绝不先破坏性摘走一整批任务。
        有保存产物的 ready 任务不再调用模型，也不受当天调查次数用尽阻塞。
        """
        stats = {"taken": 0, "run": 0, "failed": 0, "skipped": 0,
                 "accepted": 0, "verdicts": 0, "diagnosed": 0, "deferred": 0}
        if not self._busy.acquire(blocking=False):
            return stats
        try:
            store = self.svc.tasks
            store.recover_expired(self.max_attempts, self.max_apply_attempts)
            batch = store.list_tasks(states=("pending", "ready"), kinds=ORIGIN_BY_KIND)
            stats["taken"] = len(batch)
            processed = 0
            for row in batch:
                if self._stop.is_set() or (max_signals is not None and processed >= max_signals):
                    stats["deferred"] += 1
                    continue
                if store.skip_recent(row["id"], self.dedupe_ttl_s):
                    self.n_skipped_recent += 1
                    stats["skipped"] += 1
                    continue
                if (row["state"] == "pending" and store.runs_today(
                        _dt.date.today().isoformat()) >= self.daily_cap):
                    stats["deferred"] += 1
                    continue
                claimed = None
                try:
                    claimed = self._claim(row)
                    if claimed is None:
                        stats["deferred"] += 1
                        continue
                    processed += 1
                    if claimed["state"] == "running":
                        self.n_runs += 1
                        stats["run"] += 1
                        self._investigate(claimed)
                        # 产物已经持久化；停止时留给下一次启动，而非丢弃。
                        if self._stop.is_set():
                            continue
                        claimed = self._claim(store.get(row["id"]))
                        if claimed is None:
                            continue
                    self._apply(claimed, stats)
                    store.finish(claimed["id"], claimed["token"])
                except Exception as exc:
                    self.n_failed += 1
                    stats["failed"] += 1
                    if claimed is not None:
                        try:
                            state = store.retry(
                                claimed["id"], claimed["token"], f"{type(exc).__name__}: {exc}",
                                max_attempts=self.max_attempts, max_apply_attempts=self.max_apply_attempts,
                                delay=min(300, self.retry_delay_s * 2 ** min(10, max(
                                    claimed["attempts"], claimed["apply_attempts"]) - 1)))
                            if state == "dead":
                                self.n_gave_up += 1
                                print(f"[agent] task {claimed['id']} 重试耗尽，放弃（保留 dead 记录）",
                                      file=sys.stderr, flush=True)
                        except TaskLeaseLost:
                            pass  # 已过期/已保存产物：不能覆盖新领取者的状态
                    print(f"[agent] task {row['id']} 失败，任务/产物保留: "
                          f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return stats
        finally:
            self._busy.release()

    def _claim(self, row):
        with self.svc.lock:
            row = self.svc.tasks.get(row["id"])
            sig = Signal(row["kind"], row["payload"], row["t"], row["task_key"], row["id"])
            before = row["before_t"] if row["before_t"] is not None else int(self.before_for(sig))
            revision = self.svc._checkpoint_revision
            try:
                claimed = self.svc.tasks.claim(
                    row["id"], before=before, origin=ORIGIN_BY_KIND.get(sig.kind, "agent"),
                    day=_dt.date.today().isoformat(), daily_cap=self.daily_cap,
                    lease_s=self.lease_s, checkpoint=self.svc._dump_state(),
                    expected_revision=self.svc._checkpoint_revision, expected_version=row["version"])
            except BaseException:
                self.svc._check_checkpoint_error(revision)
                raise
            if claimed is not None:
                self.svc._checkpoint_revision = claimed["revision"]
            return claimed

    def _investigate(self, row):
        signal_id = f"{row['kind']}-{row['id']}-{secrets.token_hex(12)}"
        sig = Signal(row["kind"], row["payload"], row["t"], row["task_key"], row["id"])
        try:
            with self.svc.lock:
                t_now, scene = self.svc.current()
                ents = list(sig.payload.get("entities", []))[:12] if isinstance(sig.payload, dict) else []
                hints = self.svc.log.mention_counts(ents, before=row["before_t"]) if ents else {}
                payload = build_payload(sig, signal_id=signal_id, t=t_now, scene=scene,
                                        budget=self.budget, entity_hints=hints)
                payload["before"] = row["before_t"]
                self.svc.open_budget(signal_id, tool_calls=self.budget.tool_calls,
                                     window_chars=self.budget.window_chars,
                                     before=row["before_t"], origin=row["origin"],
                                     task_id=row["id"], lease_token=row["token"])
            inv = self.investigate(payload)
            if inv is None:
                raise RuntimeError("调查员没有返回合法产物")
        finally:
            usage = self.svc.close_budget(signal_id)
        # 产物可引用领取后才出现的记忆；与当前引擎 checkpoint 一起提交，
        # 防止重启后有产物却丢掉它所引用的 memory id/版本。
        with self.svc.lock:
            revision = self.svc._checkpoint_revision
            try:
                self.svc._checkpoint_revision = self.svc.tasks.store_result(
                    row["id"], row["token"],
                    {"investigation": asdict(inv), "usage": usage, "signal_id": signal_id},
                    checkpoint=self.svc._dump_state(), expected_revision=revision)
            except BaseException:
                self.svc._check_checkpoint_error(revision)
                raise

    def _apply(self, row, stats):
        result = row["result"]
        inv = Investigation(**result["investigation"])
        context = InvestigationContext(result["signal_id"], row["before_t"], row["origin"],
                                       row["id"], row["token"])
        if inv.proposals:
            self.n_proposed += len(inv.proposals)
            res = self.svc.propose(inv.proposals, _context=context)
            applied = res.get("applied", res["accepted"])
            self.n_accepted += applied
            stats["accepted"] += applied
        for left, right, verdict in inv.verdicts:
            try:
                out = self.svc.resolve(left, right, verdict, ensure_tension=True, _context=context)
            except CausalViolation:
                print(f"[agent] 拒绝越界裁决 {left}/{right}", file=sys.stderr, flush=True)
                continue
            resolved = 0 if out.get("replayed") else out.get("resolved", 0)
            self.n_verdicts += resolved
            stats["verdicts"] += resolved
        if inv.diagnosis is not None:
            out = self.svc.diagnose(inv.diagnosis["miss_type"], inv.diagnosis.get("note", ""),
                                   kind=row["kind"], usage=result["usage"], _context=context)
            if not out.get("replayed"):
                self.n_diagnosed += 1
                stats["diagnosed"] += 1

    def stats(self) -> dict:
        today = _dt.date.today()
        runs_today = self.svc.tasks.runs_today(today.isoformat())
        paused_until = ((today + _dt.timedelta(days=1)).isoformat()
                        if runs_today >= self.daily_cap else "")
        return {"runs": self.n_runs, "failed": self.n_failed,
                "gave_up": self.n_gave_up, "skipped_recent": self.n_skipped_recent,
                "proposed": self.n_proposed, "accepted": self.n_accepted,
                "verdicts": self.n_verdicts, "diagnosed": self.n_diagnosed,
                "runs_today": runs_today, "daily_cap": self.daily_cap,
                "paused_until": paused_until, "tasks": self.svc.tasks.stats(),
                "alive": bool(self._thread and self._thread.is_alive())}
