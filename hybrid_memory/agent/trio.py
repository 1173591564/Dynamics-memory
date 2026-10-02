"""OpenCode-backed Hauler → Selector → Reviewer task protocol.

Only the named OpenCode agents make semantic decisions. The sidecar owns durable
message delivery, evidence validation and memory effects; it never trusts an
agent to mutate SQLite or to declare its own decision committed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from ..core.types import Pool
from ..store.tasks import TaskLeaseLost, WORKFLOW_KINDS
from ..core import triggers


class OpenCodeRunner:
    """Run real OpenCode agents, not a local imitation of their reasoning loop."""

    def __init__(self, project: Path, executable: str | None = None, timeout: int = 300):
        self.project = Path(project)
        self.executable = executable or os.environ.get("MEMORY_OPENCODE_BIN", "opencode")
        self.timeout = timeout
        self.agent_root = Path(__file__).resolve().parents[2]

    def __call__(self, name: str, payload: dict) -> dict:
        if name not in {"hauler", "selector", "reviewer"}:
            raise ValueError("unknown agent")
        if not shutil.which(self.executable):
            raise RuntimeError(f"OpenCode CLI not installed: {self.executable}")
        prompt = ("Process this protocol message. Return exactly one JSON object. "
                  "Never claim to have read a source absent from the payload.\n"
                  + json.dumps(payload, ensure_ascii=False, sort_keys=True))
        env = dict(os.environ, DYNAMICS_MEMORY_INTERNAL_AGENT="1")
        # --pure loads local agent definitions but skips external plugins;
        # internal env guard is defence in depth against capturing worker text.
        done = subprocess.run(
            [self.executable, "run", "--pure", "--agent", name,
             "--format", "json", prompt],
            cwd=self.agent_root, env=env, capture_output=True, text=True,
            timeout=self.timeout, check=False)
        if done.returncode:
            raise RuntimeError(f"OpenCode {name} exited {done.returncode}: {done.stderr[-500:]}")
        if f'agent "{name}" not found' in done.stdout + done.stderr:
            raise RuntimeError(f"OpenCode did not load the {name} agent")
        text = "\n".join(
            str(row.get("part", {}).get("text", ""))
            for line in done.stdout.splitlines()
            for row in _event(line) if row.get("type") == "text")
        if not text.strip():
            raise ValueError(f"OpenCode {name} returned no final text")
        obj = json.loads(text.strip())
        if not isinstance(obj, dict):
            raise ValueError("agent result must be a JSON object")
        return obj


def _event(line):
    try:
        obj = json.loads(line)
    except ValueError:
        return ()
    return (obj,) if isinstance(obj, dict) else ()


class TrioWorker:
    def __init__(self, service, run_agent, *, idle_s=2, lease_s=600):
        self.svc, self.run_agent, self.idle_s, self.lease_s = service, run_agent, idle_s, lease_s
        self._stop = threading.Event()
        self._thread = None
        self._busy = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="memory-trio")
        self._thread.start()

    def stop(self, timeout=5):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _loop(self):
        while not self._stop.wait(self.idle_s):
            try:
                self.process_once()
            except Exception as exc:
                print(f"[memory-trio] {type(exc).__name__}: {exc}", file=__import__("sys").stderr)

    def _payload(self, row):
        kind = row["kind"]
        with self.svc.lock:
            uid = row["payload"]["unit_id"]
            unit = self.svc.log.get(uid)
            if unit is None:
                raise ValueError(f"unit {uid} missing from L0")
            if kind == "hauler_due":
                # Window closes at this unit, never includes future interactions.
                ids = self.svc.log.recent_ids(uid, limit=6)
                win = self.svc.log.window(ids, max_chars=12000, before=unit["t"] + 1)
                if win["truncated"]:
                    raise ValueError("Hauler window exceeded 12000 characters; cannot silently omit evidence")
                return {"kind": kind, "task_id": row["id"], "unit_id": uid,
                        "window": win["units"], "rules": self.svc.tasks.rule_snapshot(
                            "hauler", unit["user_text"] + "\n" + unit["assistant_text"])}
            if kind == "reviewer_due":
                ids = self.svc.log.recent_ids(uid, limit=6)
                win = self.svc.log.window(ids, max_chars=12000, before=unit["t"] + 1)
                if win["truncated"]:
                    raise ValueError("Reviewer window exceeded 12000 characters; cannot silently omit evidence")
                work = self.svc.log.work(uid)
                trace = self.svc.tasks.workflow_trace(ids, before_task_id=row["id"])
                return {"kind": kind, "task_id": row["id"], "complaint": unit,
                        "window": win["units"], "handoffs": trace,
                        "previous_retrieval": (work or {}).get("context", {}),
                        "rules": self.svc.tasks.rule_snapshot("reviewer", unit["user_text"]),
                        "memories": self._memories()}
            return {"kind": kind, "task_id": row["id"], "unit_id": uid,
                    "candidates": row["payload"]["candidates"],
                    "memories": self._memories(), "rules": self.svc.tasks.rule_snapshot(
                        "selector", "\n".join(c["text"] for c in row["payload"]["candidates"]))}

    def _memories(self):
        memories = [m for m in self.svc.engine.mems.values()
                    if m.superseded_by is None and m.aggregated_into is None]
        # Never let a truncated pool be mistaken for the whole store.
        if len(memories) > 500:
            raise RuntimeError("selector memory context exceeds limit; needs indexed paging")
        return [{"id": m.id, "text": m.text, "src": sorted(m.src),
                 "entity": m.entity, "birth": m.birth, "pool": m.pool.value}
                for m in sorted(memories, key=lambda m: m.id)]

    def process_once(self, limit=8):
        if not self._busy.acquire(False):
            return 0
        done = 0
        try:
            store = self.svc.tasks
            store.recover_expired(kinds=WORKFLOW_KINDS, reset_next_run_at=True)
            for item in store.list_tasks(states=("pending", "ready"), kinds=WORKFLOW_KINDS)[:limit]:
                if self._stop.is_set():
                    break
                row = store.claim(item["id"], expected_version=item["version"],
                                          lease_s=self.lease_s)
                if row is None:
                    continue
                try:
                    if row["state"] == "running":
                        name = row["kind"].removesuffix("_due")
                        payload = self._payload(row)
                        result = self.run_agent(name, payload)
                        store.store_result(row["id"], row["token"], result,
                            rule_ids=[r["id"] for r in payload["rules"]])
                        row = store.claim(row["id"], expected_version=row["version"],
                                          lease_s=self.lease_s)
                        if row is None:
                            continue
                    with self.svc.lock, self.svc._rollback_effect():
                        _, revision = store.complete(
                            row["id"], row["token"],
                            lambda conn, output: self._apply(conn, row, output),
                            self.svc._dump_state, self.svc._checkpoint_revision)
                        self.svc._checkpoint_revision = revision
                    done += 1
                except Exception as exc:
                    try:
                        store.retry(row["id"], row["token"], exc,
                            retry_model=isinstance(exc, ValueError))
                    except TaskLeaseLost:
                        pass
                    print(f"[memory-trio] task {row['id']}: {type(exc).__name__}: {exc}",
                          file=__import__("sys").stderr)
            return done
        finally:
            self._busy.release()

    def _send(self, conn, kind, uid, candidates, parent):
        if not candidates:
            return
        self.svc.tasks._enqueue(conn, kind,
            {"unit_id": uid, "candidates": candidates, "parent_task": parent},
            self.svc._t, key=f"{kind}:{parent}", memory_next_id=self.svc.engine._next_id)

    def _validate_sources(self, candidates, uid):
        allowed = set(self.svc.log.recent_ids(uid, limit=6))
        for c in candidates:
            if (not isinstance(c, dict) or not isinstance(c.get("text"), str)
                or not c["text"].strip() or not isinstance(c.get("source_unit_ids"), list)
                or not c["source_unit_ids"] or any(type(i) is not int or i not in allowed
                                                     for i in c["source_unit_ids"])):
                raise ValueError("candidate must cite only units in the supplied window")

    def _apply(self, conn, row, output):
        kind, uid = row["kind"], row["payload"]["unit_id"]
        if kind == "hauler_due":
            candidates = output.get("candidates")
            if not isinstance(candidates, list) or len(candidates) > 50:
                raise ValueError("Hauler candidates must be a list of at most 50")
            self._validate_sources(candidates, uid)
            self._send(conn, "selector_due", uid, candidates, row["id"])
            return {"candidates": len(candidates)}
        if kind == "reviewer_due":
            if not isinstance(output.get("diagnosis"), str) or not output["diagnosis"].strip():
                raise ValueError("Reviewer must supply a diagnosis")
            rule_reviews = output.get("rule_reviews", [])
            if not isinstance(rule_reviews, list) or len(rule_reviews) > 10:
                raise ValueError("Reviewer rule reviews must be a list of at most 10")
            review_context = self._payload(row)
            used = {rid for task in review_context["handoffs"]
                    for rid in task.get("rule_ids", [])}
            seen = set()
            for rr in rule_reviews:
                if (not isinstance(rr, dict) or type(rr.get("rule_id")) is not int
                    or rr["rule_id"] in seen or rr["rule_id"] not in used
                    or rr.get("assessment") not in ("helpful", "ineffective", "uncertain")
                    or not isinstance(rr.get("reason"), str)
                    or not 0 < len(rr["reason"].strip()) <= 500):
                    raise ValueError("rule assessment requires observed prior use and a reason")
                seen.add(rr["rule_id"])
                conn.execute("INSERT INTO agent_rule_feedback"
                    "(reviewer_task,rule_id,assessment,reason,at) VALUES(?,?,?,?,?)",
                    (row["id"], rr["rule_id"], rr["assessment"],
                     rr["reason"].strip(), time.time()))
                if rr["assessment"] == "ineffective":
                    updated = conn.execute("UPDATE agent_rules SET enabled=0 "
                        "WHERE id=? AND enabled=1", (rr["rule_id"],))
                    if updated.rowcount:
                        conn.execute("INSERT INTO agent_rule_audit(rule_id,action,actor,at) "
                            "VALUES(?,'disable','reviewer',?)",
                            (rr["rule_id"], time.time()))
            rules = output.get("rules", [])
            if not isinstance(rules, list) or len(rules) > 10:
                raise ValueError("Reviewer rules must be a list of at most 10")
            for r in rules:
                if (not isinstance(r, dict) or r.get("target") not in ("hauler", "selector")
                    or not isinstance(r.get("instruction"), str)
                    or not 0 < len(r["instruction"].strip()) <= 500):
                    raise ValueError("invalid Reviewer rule")
                scope = r.get("scope", "project")
                if (scope != "project" and (not isinstance(scope, str) or
                        not scope.startswith("entity:") or
                        not 0 < len(scope[7:].strip()) <= 120)):
                    raise ValueError("rule scope must be project or entity:<literal>")
                cur = conn.execute("INSERT OR IGNORE INTO agent_rules"
                             "(source_task,target,instruction,scope,created_at) "
                             "VALUES(?,?,?,?,?)", (row["id"], r["target"],
                                 r["instruction"].strip(), scope, time.time()))
                if cur.rowcount:
                    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute("INSERT INTO agent_rule_audit(rule_id,action,actor,at) "
                                 "VALUES(?,'create','reviewer',?)", (rid, time.time()))
            candidates = output.get("repair_candidates", [])
            if not isinstance(candidates, list) or len(candidates) > 20:
                raise ValueError("Reviewer repairs must be a list of at most 20")
            self._validate_sources(candidates, uid)
            self._send(conn, "selector_due", uid, candidates, row["id"])
            return {"rules": len(rules), "repair_candidates": len(candidates)}
        decisions = output.get("decisions")
        candidates = row["payload"]["candidates"]
        if (not isinstance(decisions, list) or len(decisions) != len(candidates)
                or sorted(d.get("candidate_index") for d in decisions if isinstance(d, dict))
                != list(range(len(candidates)))):
            raise ValueError("Selector must return exactly one decision per candidate")
        outcomes = []
        for d in decisions:
            idx, action = d["candidate_index"], d.get("action")
            c = candidates[idx]
            if action not in {"CREATE", "EXIST", "UPDATE", "CONFLICT", "REJECT"}:
                raise ValueError("invalid Selector action")
            if action == "REJECT":
                outcomes.append({"index": idx, "action": action})
                continue
            # The selector cannot widen a source boundary established by its parent.
            self._validate_sources([c], uid)
            # Treat even model-produced recommendations as untrusted input.
            ev, _ = self.svc._validate_proposal(c, None)
            ev.origin = "agent"
            target = d.get("target_id")
            old = self.svc.engine.mems.get(target) if type(target) is int else None
            # Exact re-extraction from overlapping windows cannot yield a second
            # identical memory even when the model misclassifies it as CREATE.
            if action == "CREATE":
                same = next((m for m in self.svc.engine.mems.values()
                             if m.superseded_by is None and m.aggregated_into is None
                             and m.text == ev.text), None)
                if same is not None:
                    action, old = "EXIST", same
            if action != "CREATE" and (old is None or old.superseded_by is not None
                                       or old.aggregated_into is not None):
                raise ValueError("Selector target is retired or unknown")
            if action == "EXIST":
                new_sources = set(ev.src) - set(old.src)
                old.src = old.src | frozenset(ev.src)
                old.evid += len(new_sources)
                if old.pool is Pool.ARCHIVE:
                    old.pool = Pool.CANDIDATE if self.svc.cfg.two_pool else Pool.MEMORY
                old.last_seen = max(old.last_seen, self.svc._t)
                outcomes.append({"index": idx, "action": action, "target_id": old.id,
                                 "new_evidence": len(new_sources)})
                continue
            if action == "UPDATE":
                # Recent != correct. Without an explicit user correction, refer
                # incompatible statements to a human rather than choosing newest.
                confirmed = bool(d.get("verified_correction")) and any(
                    triggers.is_correction(self.svc.log.get(i)["user_text"])
                    for i in ev.src if self.svc.log.get(i))
                if not confirmed:
                    action = "CONFLICT"
            if action == "CONFLICT":
                conn.execute("INSERT OR IGNORE INTO human_reviews"
                             "(source_task,target_id,candidate,reason,created_at) VALUES(?,?,?,?,?)",
                             (row["id"], old.id, json.dumps(c, ensure_ascii=False, sort_keys=True),
                              str(d.get("reason", "conflicting evidence"))[:500], time.time()))
                old.pending_review = True
                outcomes.append({"index": idx, "action": action, "target_id": old.id})
                continue
            ids = self.svc.engine.propose([ev], self.svc._t)
            if action == "UPDATE" and ids:
                self.svc.engine.add_tension(ids[0], old.id, self.svc._t)
                self.svc.engine.submit_verdicts([(ids[0], old.id, "update")], self.svc._t)
            outcomes.append({"index": idx, "action": action if ids else "EXIST", "new_ids": ids})
        return {"outcomes": outcomes}
