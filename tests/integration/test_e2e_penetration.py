"""端到端穿透回归（P1 验收面）：真组件全链，不走内部 stub。

- 链 1：observe → hauler_due → OpenCodeRunner 文件通道（fake CLI 脚本，
  真 exec、真 --file payload）→ selector_due → 效果落库 → recall →
  feedback → feedback_pending → 信用结清；
- 链 2：selector 裁 CONFLICT → human_reviews 待审 → accept_new（新版本
  入库、旧版退役、待审关闭）与 keep_old（候选被拒、旧版保留）两分支；
- 链 3：kill -9 崩溃恢复（真子进程 SIGKILL）：两库崩溃点——log 库已提交
  单元未进 checkpoint、tasks 库 running 任务租约未过期——重启后经
  start_unit_recovery 恢复，已提交数据不丢。
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from hybrid_memory.agents.opencode import OpenCodeRunner
from hybrid_memory.dispatch.worker import DispatchWorker

from test_ouroboros import _svc

REPO_ROOT = Path(__file__).resolve().parents[2]

# fake opencode CLI：真 exec 的 python 脚本。读 --file payload，按 --agent
# 角色回 opencode 风格 JSONL；把观测写入 $FAKE_OC_OBS 供断言。
FAKE_CLI = """#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
if argv[:2] == ["run", "--help"]:
    print("Usage: opencode run [options] [message..]")
    print("  --file <path>   attach file")
    print("  --agent <name>")
    sys.exit(0)
role = argv[argv.index("--agent") + 1]
payload = json.loads(open(argv[argv.index("--file") + 1], encoding="utf-8").read())
obs_path = os.environ.get("FAKE_OC_OBS")
if obs_path:
    with open(obs_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"role": role, "payload": payload}) + "\\n")
if role == "hauler":
    reply = {"candidates": [{"text": "项目统一使用 bun 工具",
                             "source_unit_ids": [payload["unit_id"]]}]}
elif role == "selector":
    reply = {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
else:
    reply = {"diagnosis": "ok", "rules": [], "repair_candidates": [],
             "rule_reviews": []}
print(json.dumps({"type": "text", "part": {"text": json.dumps(reply)}}))
sys.exit(0)
"""


def _make_fake_cli(tmp_path):
    """真 exec 的假 CLI：POSIX 用 shebang 脚本；Windows 不能 exec .py，
    写 .cmd 启动器转发到 sys.executable（等价真实 CLI 可执行文件）。"""
    script = tmp_path / "fake-opencode.py"
    script.write_text(FAKE_CLI, encoding="utf-8")
    if os.name == "nt":
        launcher = tmp_path / "fake-opencode.cmd"
        launcher.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "{script}" %*\r\n',
            encoding="utf-8")
        return launcher
    script.chmod(0o755)
    return script


def _drain(worker, rounds=8):
    for _ in range(rounds):
        if not worker.process_once():
            break


def test_chain1_full_pipeline_via_real_file_channel(tmp_path, monkeypatch):
    """链 1：真 OpenCodeRunner（fake CLI）全工作流到信用结清。"""
    cli = _make_fake_cli(tmp_path)
    obs = tmp_path / "obs.jsonl"
    monkeypatch.setenv("FAKE_OC_OBS", str(obs))
    svc = _svc(tmp_path / "state")
    svc.trio_mode = True
    runner = OpenCodeRunner(tmp_path, executable=str(cli))
    worker = DispatchWorker(svc, runner)
    try:
        assert runner.verify_channel() is True, "前置：通道探测通过"
        svc.observe("以后统一用 bun", "好的")
        _drain(worker)
        mems = list(svc.engine.mems.values())
        assert len(mems) == 1 and mems[0].text == "项目统一使用 bun 工具", \
            "效果落库：hauler→selector→CREATE 全链"
        # 封存上下文真的记录了模型输入（N10）
        calls = [json.loads(line) for line in
                 obs.read_text(encoding="utf-8").splitlines()]
        roles = [c["role"] for c in calls]
        assert roles[:2] == ["hauler", "selector"], "两角色都经真 CLI 跑过"
        # recall 命中
        rec = svc.recall("项目用什么构建")
        assert rec["retrieval_id"] >= 0
        # feedback → 语义任务 → 信用结清
        svc.feedback(rec["retrieval_id"], "项目用什么构建", "bun")
        svc.process_semantic_tasks()
        ret = svc._retrievals[rec["retrieval_id"]]
        assert ret.credited is True, "信用必须结清（feedback_pending→apply_feedback）"
        done = {t["kind"] for t in svc.tasks.list_tasks(states=("done",))}
        assert {"hauler_due", "selector_due"} <= done
        assert ret.feedback_sent and ret.n_useful >= 0
    finally:
        svc.tasks.close()
        svc.log.close()


def _seed_conflict_target(svc, text="部署在 A 服务器"):
    """第一轮 CREATE 落一条记忆作为后续 CONFLICT 的 target。"""
    from hybrid_memory.core.types import Event
    eng = svc.engine
    ids = eng.propose([Event(svc.semantics.fingerprint(text), text, text,
                             (0,), origin="agent")], 0)
    assert ids, "前置：target 记忆已入库"
    return ids[0]


def _apply_selector_conflict(svc, target_id, uid=0):
    """经 apply_semantic 走真实 selector_due 应用路径产 CONFLICT 人审。"""
    from hybrid_memory.dispatch import effects
    cand = {"text": "部署改到 B 服务器", "source_unit_ids": [uid]}
    result = {"decisions": [{"candidate_index": 0, "action": "CONFLICT",
                             "target_id": target_id}]}
    with svc.tasks.transaction() as conn:
        conn.execute(
            "INSERT INTO tasks(kind,task_key,payload,t,state,result,"
            "created_at,updated_at) VALUES('selector_due',?,?,0,'ready',?,0,0)",
            (f"conf-{target_id}",
             json.dumps({"unit_id": uid, "candidates": [cand],
                         "parent_task": 1}),
             json.dumps(result)))
    row = svc.tasks.list_tasks(kinds=("selector_due",))[-1]
    row = dict(row)
    with svc._lock, svc._rollback_effect():
        with svc.tasks.transaction() as conn:
            effects.EFFECTS["selector_due"].apply(svc, row, row["result"], conn)
    return row["id"]


def test_chain2_conflict_to_human_review_both_branches(tmp_path):
    """链 2：CONFLICT → 人审 accept_new 与 keep_old 闭环。"""
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.observe("部署在 A 服务器", "说明")   # L0 unit 0：候选引用窗口
        target = _seed_conflict_target(svc)
        _apply_selector_conflict(svc, target)
        reviews = svc.tasks.pending_reviews()
        assert len(reviews) == 1, "CONFLICT 必须落人审队列"
        assert reviews[0]["target_id"] == target
        assert svc.engine.mems[target].pending_review is True

        # 分支 A：keep_old —— 候选被拒，旧版保留、解除保护
        out = svc.decide_human_review(reviews[0]["id"], "keep_old",
                                      svc.human_review_token)
        assert out["decision"] == "keep_old"
        assert svc.engine.mems[target].pending_review is False
        assert len(svc.engine.mems) == 1, "keep_old 不得新增记忆"
        assert svc.tasks.pending_reviews() == []

        # 分支 B：accept_new —— 新版本入库、旧版退役、张力消解
        _apply_selector_conflict(svc, target)
        reviews = svc.tasks.pending_reviews()
        assert len(reviews) == 1
        out = svc.decide_human_review(reviews[0]["id"], "accept_new",
                                      svc.human_review_token)
        assert out["decision"] == "accept_new"
        eng = svc.engine
        new_ids = [i for i, m in eng.mems.items()
                   if m.text == "部署改到 B 服务器"]
        assert new_ids, "accept_new 必须入库新版本"
        new_id = new_ids[0]
        assert eng.mems[target].superseded_by == new_id, "旧版退役指向新版本"
        assert eng.mems[new_id].origin == "user_confirmed"
        assert not eng.tensions, "人审裁决后张力必须消解"
        assert svc.tasks.pending_reviews() == []
        # 幂等重放
        out2 = svc.decide_human_review(reviews[0]["id"], "accept_new",
                                       svc.human_review_token)
        assert out2.get("replayed") is True
    finally:
        svc.tasks.close()
        svc.log.close()


# 子进程：起真 sidecar（文件库），observe 提交 L0 后发信号并挂住等死。
_CHILD = """
import sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from hybrid_memory.config import Cfg
from hybrid_memory.core.types import Memory
from hybrid_memory.embed.base import Embedder
from hybrid_memory.semantics.real import RealChatSemantics
from hybrid_memory.service.service import MemoryService
from hybrid_memory.legacy.candgen import ChatGenerator


class _Emb(Embedder):
    def embed(self, texts, keys=None):
        import numpy as np
        return np.zeros((len(texts), 64), dtype=float)


state = Path({state!r})
svc = MemoryService(Cfg(theta=0.2, suppression_on=False, defer_credit=True),
                    _Emb(), RealChatSemantics(None),
                    ChatGenerator(lambda system, user: ""),
                    state_dir=state)
svc.observe("崩溃前已提交的证据", "好的")
# 再留一个 running 任务（租约未过期）：第二个崩溃点
tid = svc.tasks.enqueue("maintenance_due", {{"scene": "s", "ids": [0]}}, 0)
svc.tasks.claim(tid, expected_version=0)
print("READY", flush=True)
time.sleep(600)
"""


def test_chain3_kill9_recovery_across_both_dbs(tmp_path):
    """链 3：SIGKILL 真崩溃 → 重启恢复两库（L0 单元 + 过期租约任务）。"""
    state = tmp_path / "state"
    state.mkdir(parents=True)
    code = _CHILD.format(repo=str(REPO_ROOT), state=str(state))
    proc = subprocess.Popen(
        [sys.executable, "-c", code], cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        line = proc.stdout.readline()
        assert line.strip() == "READY", f"子进程未就绪: {line!r} {proc.stderr.read()}"
        # 子进程已提交 L0 单元 + 领取任务（租约 360s）——此刻强杀：
        # POSIX SIGKILL / Windows TerminateProcess，均为无清理的崩溃语义
        if os.name == "nt":
            proc.kill()
            proc.wait(timeout=30)
            assert proc.returncode != 0, "必须是强杀死亡"
        else:
            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=30)
            assert proc.returncode == -signal.SIGKILL, "必须是 SIGKILL 死亡"
    finally:
        if proc.poll() is None:
            proc.kill()

    # 重启：同一 state_dir 构建新服务并恢复
    from hybrid_memory.config import Cfg
    from tests.test_ouroboros import _HashEmbedder, _NoCandGen
    svc = _svc(state)
    svc.trio_mode = True
    try:
        # log 库崩溃点：已提交单元必须存活（不丢已提交证据）
        assert svc.log.count() >= 1, "L0 已提交单元必须存活"
        unit = svc.log.get(0)
        assert unit is not None and unit["user_text"] == "崩溃前已提交的证据"
        # 单元恢复回路可推进（崩溃前已被处理的单元幂等跳过）
        assert isinstance(svc.process_pending_units(), dict)
        # tasks 库崩溃点：running 任务租约到期后恢复可跑
        now = time.time()
        svc.tasks.clock = lambda: now + 400.0   # 越过 360s 租约
        svc.tasks.recover_expired(kinds=("maintenance_due",),
                                  reset_next_run_at=True)
        row = svc.tasks.get(1)
        assert row is not None and row["state"] in ("pending", "ready"), \
            f"崩溃任务必须可恢复重跑，实际 {row and row['state']}"
    finally:
        svc.tasks.close()
        svc.log.close()
