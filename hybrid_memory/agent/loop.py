"""AgentWorker：衔尾蛇的"手"——后台线程，把引擎信号交给调查员，把产物喂回引擎。

    take(recall_miss / extract_due)（锁内）
      → build_payload（锁内，只读小信息）
      → investigate(payload)（锁外，可能几十秒：opencode 子进程 + 工具调用）
      → service.propose / resolve / diagnose（各自锁内）

纪律（衔尾蛇不能把自己吃死）：
- 同时只跑一个调查员（单线程）；
- 每信号：工具调用上限 + 回展字符上限 + 超时（预算由 service 按 signal_id
  在服务端计量，不靠 LLM 自觉）；
- 每日调用上限：到顶后信号留在有界队列里，次日恢复（不静默丢）；
- 幂等：同 key 的 recall_miss 在 TTL 内只调查一次；extract_due 每 unit 一次；
- 失败重试有限次，超过即放弃并计数外显；
- 因果：before = 信号所在步 + 1（含该步）——日志、记忆工具和写回共用
  此上界；记忆只提供保守筛选后的当前版本，不重建历史状态。
  回放驱动可用 before_for 覆盖。
- 工具结束后关闭预算；正常最终 JSON 使用进程内保留的上下文提交，不把
  已关闭信号重新开放给 HTTP。每轮随机后缀防旧调用在重试/重启后借壳。
"""
from __future__ import annotations

import datetime as _dt
import secrets
import sys
import threading
import time
from typing import Callable

from ..investigation_context import CausalViolation
from .investigator import Budget, Investigation, build_payload

ORIGIN_BY_KIND = {"recall_miss": "repair", "extract_due": "extract",
                  "thin_recall": "repair"}


class AgentWorker:
    def __init__(self, service, investigate: Callable[[dict], Investigation | None],
                 *, kinds=("recall_miss", "extract_due"),
                 budget: Budget | None = None, daily_cap: int = 200,
                 max_attempts: int = 2, dedupe_ttl_s: float = 24 * 3600,
                 idle_s: float = 2.0, before_for: Callable | None = None):
        self.svc = service
        self.investigate = investigate
        self.kinds = tuple(kinds)
        self.budget = budget or Budget()
        self.daily_cap = int(daily_cap)
        self.max_attempts = int(max_attempts)
        self.dedupe_ttl_s = float(dedupe_ttl_s)
        self.idle_s = float(idle_s)
        self.before_for = before_for or (lambda sig: sig.t + 1)
        self._recent: dict[str, float] = {}
        self._attempts: dict[str, int] = {}
        self._day = ""
        self._runs_today = 0
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
        self.paused_until = ""

    # ---- 生命周期 ----
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="memory-agent",
                                        daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
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
    def _cap_ok(self) -> bool:
        today = _dt.date.today().isoformat()
        if today != self._day:
            self._day, self._runs_today = today, 0
            self.paused_until = ""
        if self._runs_today >= self.daily_cap:
            if not self.paused_until:
                self.paused_until = (_dt.date.today()
                                     + _dt.timedelta(days=1)).isoformat()
                print(f"[agent] 今日调查预算 {self.daily_cap} 用尽，信号留队，"
                      f"{self.paused_until} 恢复", file=sys.stderr, flush=True)
            return False
        return True

    def process_once(self, max_signals: int | None = None) -> dict:
        """摘一批自己的信号并逐个调查。可从外部同步调用（测试/回放）。"""
        stats = {"taken": 0, "run": 0, "failed": 0, "skipped": 0,
                 "accepted": 0, "verdicts": 0, "diagnosed": 0, "deferred": 0}
        if not self._busy.acquire(blocking=False):
            return stats                     # 上一轮还在跑
        try:
            with self.svc.lock:
                batch = self.svc.engine.signals.take(self.kinds)
            stats["taken"] = len(batch)
            now = time.monotonic()
            for i, sig in enumerate(batch):
                if max_signals is not None and stats["run"] >= max_signals:
                    self._requeue(batch[i:])
                    stats["deferred"] += len(batch) - i
                    break
                if not self._cap_ok():
                    self._requeue(batch[i:])
                    stats["deferred"] += len(batch) - i
                    break
                key = sig.key or f"{sig.kind}:{sig.id}"
                last = self._recent.get(key)
                if last is not None and now - last < self.dedupe_ttl_s:
                    self.n_skipped_recent += 1
                    stats["skipped"] += 1
                    continue
                ok = self._run_one(sig, stats)
                if ok:
                    self._recent[key] = now
                    self._attempts.pop(key, None)
                else:
                    n = self._attempts.get(key, 0) + 1
                    if n < self.max_attempts:
                        self._attempts[key] = n
                        self._requeue([sig])
                    else:
                        self._attempts.pop(key, None)
                        self.n_gave_up += 1
                        print(f"[agent] 信号 {sig.kind} key={key} 连续失败 "
                              f"{n} 次，放弃", file=sys.stderr, flush=True)
            if len(self._recent) > 4096:     # 有界
                cutoff = now - self.dedupe_ttl_s
                self._recent = {k: v for k, v in self._recent.items() if v >= cutoff}
            return stats
        finally:
            self._busy.release()

    def _requeue(self, sigs) -> None:
        with self.svc.lock:
            for sig in sigs:
                self.svc.engine.signals.emit(sig.kind, sig.payload, sig.t,
                                             key=sig.key,
                                             merge=lambda o, n: o)

    def _run_one(self, sig, stats: dict) -> bool:
        before = int(self.before_for(sig))
        signal_id = f"{sig.kind}-{sig.id}-{sig.t}-{secrets.token_hex(12)}"
        with self.svc.lock:
            t_now, scene = self.svc.current()
            ents = []
            if isinstance(sig.payload, dict):
                ents = list(sig.payload.get("entities", []))[:12]
            hints = self.svc.log.mention_counts(ents, before=before) if ents else {}
            payload = build_payload(sig, signal_id=signal_id, t=t_now,
                                    scene=scene, budget=self.budget,
                                    entity_hints=hints)
            payload["before"] = before
            context = self.svc.open_budget(
                signal_id, tool_calls=self.budget.tool_calls,
                window_chars=self.budget.window_chars, before=before,
                origin=ORIGIN_BY_KIND.get(sig.kind, "agent"))
        self._runs_today += 1
        self.n_runs += 1
        stats["run"] += 1
        try:
            inv = self.investigate(payload)
        except Exception as exc:             # noqa: BLE001
            print(f"[agent] 调查员异常: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
            inv = None
        finally:
            usage = self.svc.close_budget(signal_id)
        if inv is None:
            self.n_failed += 1
            stats["failed"] += 1
            return False
        # 工具已关闭，但正常最终 JSON 仍能提交；仅进程内持有此上下文，
        # 不重新开放 signal_id，也不丢弃原来的因果界/来源标签。
        if inv.proposals:
            self.n_proposed += len(inv.proposals)
            res = self.svc.propose(inv.proposals, _context=context)
            self.n_accepted += res["accepted"]
            stats["accepted"] += res["accepted"]
        for left, right, verdict in inv.verdicts:
            try:
                out = self.svc.resolve(left, right, verdict, ensure_tension=True,
                                       _context=context)
            except CausalViolation:
                # 一条越界裁决不阻断同份 JSON 的合法诊断/提议；也不做任何写入。
                print(f"[agent] 拒绝越界裁决 {left}/{right}", file=sys.stderr, flush=True)
                continue
            self.n_verdicts += out.get("resolved", 0)
            stats["verdicts"] += out.get("resolved", 0)
        if inv.diagnosis is not None:
            self.svc.diagnose(inv.diagnosis["miss_type"],
                              inv.diagnosis.get("note", ""),
                              kind=sig.kind, usage=usage, _context=context)
            self.n_diagnosed += 1
            stats["diagnosed"] += 1
        return True

    def stats(self) -> dict:
        return {"runs": self.n_runs, "failed": self.n_failed,
                "gave_up": self.n_gave_up, "skipped_recent": self.n_skipped_recent,
                "proposed": self.n_proposed, "accepted": self.n_accepted,
                "verdicts": self.n_verdicts, "diagnosed": self.n_diagnosed,
                "runs_today": self._runs_today, "daily_cap": self.daily_cap,
                "paused_until": self.paused_until,
                "alive": bool(self._thread and self._thread.is_alive())}
