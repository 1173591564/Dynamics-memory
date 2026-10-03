#!/usr/bin/env python3
"""重构验收检查器（H41）：A1–A10 的机械部分 + PENDING 白名单打印。

用法：
  python analysis/acceptance_check.py            # 默认门（约 4 分钟）
  python analysis/acceptance_check.py --full     # + TIDE bench 烟囱（约 +8 分钟）
  python analysis/acceptance_check.py --freeze   # 重冻 A7 契约快照（改契约时，需注明理由）

退出码：0 = 无 FAIL；1 = 有 FAIL。PENDING/SKIP 只打印不判红（H42）。
判定基准：analysis/acceptance-criteria.md；决策依据：analysis/decision-register.md。
本文件只用标准库；被测行为经子进程 pytest / tide 跑。
"""
from __future__ import annotations

import argparse
import ast
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = Path(__file__).resolve().parent / "contract_snapshots"
SNAP_FILES = ("health.json", "signals.json", "status_table.json")

PENDING = [
    ("PENDING-01", "tension_delay=20 致 V 维 judge 迟到", "调优 PR + V 维 NTU 对比"),
    ("PENDING-02", "无依赖失效机制，P 维为负", "依赖失效 ADR 通过"),
    ("PENDING-03", "salience/novelty/confidence 默认 OFF", "每机制 TIDE 证据 + 覆盖率闸门"),
    ("PENDING-04", "verdict 通路合并（走 Selector）", "协议扩展 ADR"),
    ("PENDING-05", "legacy/ 删除", "裸引擎退役删除 ADR"),
    ("PENDING-06", "第二项目端口冲突（固定 17872）", "端口分配方案 ADR"),
    ("PENDING-07", "L0 未脱敏进 LLM", "脱敏层设计 + 能力评测"),
    ("PENDING-08", "L3 真实验证未做", "真实 provider + 人工抽检"),
    ("PENDING-09", "checkpoint 全量 pickle O(N)", "dump_state>2MB 或持续>10效果/s → 分段 pickle（I5 单点接入）"),
    ("PENDING-10", "pin 占用无指标/告警（503 刹车不可预期）", "health/stats 暴露 pin 占用 + 阈值告警"),
]

results: list[tuple[str, str, str]] = []  # (id, VERDICT, detail)


def report(cid: str, verdict: str, detail: str = "") -> None:
    assert verdict in ("PASS", "FAIL", "PENDING", "SKIP")
    results.append((cid, verdict, detail))
    print(f"[{verdict:7s}] {cid} {detail}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None,
        timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), env=env,
                          capture_output=True, text=True, timeout=timeout)


def pytest_run(nodes: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "--tb=short"] + nodes, timeout=timeout)


def detect_phase() -> str:
    # 文件级标记：P1 即创建 service/（context.py）与 transport/（review_cli.py），
    # 目录存在性不可作 P4/P5 判据。
    h = ROOT / "hybrid_memory"
    if (h / "agents" / "opencode.py").is_file():
        return "P6"
    if (h / "transport" / "http.py").is_file():
        return "P5"
    svc = h / "service"
    if svc.is_dir() and any(p.suffix == ".py" and p.name not in
                            ("__init__.py", "context.py")
                            for p in svc.iterdir()):
        return "P4"
    if (ROOT / "tests" / "characterization").is_dir():
        return "P3"
    if (h / "errors.py").is_file():
        return "P2"
    if (h / "legacy").is_dir():
        return "P1"
    return "P0"


# ---------------------------------------------------------------- A1
def check_a1() -> None:
    out = pytest_run(["tests/"], timeout=900)
    tail = (out.stdout + out.stderr).strip().splitlines()
    summary = tail[-1] if tail else "no output"
    if out.returncode == 0:
        report("A1-pytest", "PASS", summary)
    else:
        report("A1-pytest", "FAIL", summary + "\n" + "\n".join(tail[-15:]))
    bun = shutil.which("bun")
    if bun:
        out = run([bun, "test", "tests/"], timeout=300)
        report("A1-bun", "PASS" if out.returncode == 0 else "FAIL",
               (out.stdout + out.stderr).strip().splitlines()[-1:])
    else:
        report("A1-bun", "SKIP", "沙箱无 bun，由 CI 跑；本机只审 TS 源码")


# ---------------------------------------------------------------- A2
A2_ROWS = [
    # (doc, doc_snippet, pytest_node)
    ("README.md", "幂等",
     "tests/integration/test_service_observe.py::test_same_observe_request_id_is_one_unit_and_conflict_does_not_rebind"),
    ("README.md", "unverified",
     "tests/test_launch_closeout.py::test_health_does_not_claim_remote_validation_and_retry_is_read_only"),
    ("README.md", "不能绕过 Selector",
     "tests/test_trio_protocol.py::test_direct_agent_mutations_denied_in_trio_http_mode"),
    ("docs/opencode-trio.md", "CONFLICT",
     "tests/integration/test_service_review.py::test_conflict_quarantined_until_human_review_and_stale_version_stays_hidden"),
    ("docs/opencode-trio.md", "hauler",
     "tests/test_trio_protocol.py::test_hauler_selector_create_exist_and_overlapping_window"),
    ("README.md", "checkpoint",
     "tests/test_durable_tasks.py::test_effect_checkpoint_precedes_ack_and_is_not_lost_to_stale_pickle"),
    ("README.md", "L0",
     "tests/test_logstore.py::test_persists_to_sqlite_file_and_reopens"),
    ("docs/opencode-trio.md", "规则",
     "tests/test_trio_protocol.py::test_scoped_rule_usage_is_audited_and_human_can_disable_it"),
]


def check_a2() -> None:
    ok = True
    for doc, snippet, node in A2_ROWS:
        text = (ROOT / doc).read_text(encoding="utf-8")
        if snippet not in text:
            report("A2", "FAIL", f"{doc} 丢失断言 {snippet!r}（文档漂移）")
            ok = False
            continue
        out = pytest_run([node], timeout=300)
        if out.returncode != 0:
            report("A2", "FAIL", f"证据失效 {node}\n" + out.stdout[-600:])
            ok = False
    if ok:
        report("A2", "PASS", f"{len(A2_ROWS)} 条断言→证据全链通")


# ---------------------------------------------------------------- A3
def check_a3(full: bool) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="accept-tide-"))
    try:
        env = {**os.environ}
        out = run([sys.executable, "-m", "tide", "gen", "--out", str(tmp / "l1"),
                   "--seeds", "2"], cwd=ROOT / "eval", timeout=300)
        if out.returncode != 0:
            report("A3-gen", "FAIL", out.stderr[-500:])
            return
        out = run([sys.executable, "-m", "tide", "meta", "--data", str(tmp / "l1"),
                   "--budget", "64"], cwd=ROOT / "eval", timeout=600)
        if out.returncode == 0 and "PASS" in out.stdout:
            report("A3-meta", "PASS", "tide meta PASS（seeds=2 快检；典式 seeds=5 见手册）")
        else:
            report("A3-meta", "FAIL", (out.stdout + out.stderr)[-800:])
            return
        out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "tests/test_tide.py"], cwd=ROOT / "eval", timeout=300)
        report("A3-tide-unit", "PASS" if out.returncode == 0 else "FAIL",
               out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-300:])
        if not full:
            report("A3-bench-smoke", "SKIP", "默认门跳过；--full 或 make accept 跑")
            return
        # bench 烟囱：mock LLM + 每维度 1 条流的 dynamics-memory
        mock = subprocess.Popen([sys.executable, str(ROOT / "eval" / "mock_llm.py"), "18080"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                try:
                    urllib.request.urlopen("http://127.0.0.1:18080/stats", timeout=2).read()
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                report("A3-bench-smoke", "FAIL", "mock_llm 未在 60s 内就绪")
                return
            benv = {**env, "ZAI_BASE_URL": "http://127.0.0.1:18080",
                    "ZAI_API_KEY": "mock"}
            out = run([sys.executable, "-m", "tide", "bench", "--data", str(tmp / "l1"),
                       "--systems", "recency,bm25,parsed,dynamics-memory",
                       "--dm-repo", str(ROOT), "--max-streams-per-dim", "1",
                       "--out", str(tmp / "runs" / "smoke")],
                      cwd=ROOT / "eval", env=benv, timeout=1500)
            rep = tmp / "runs" / "smoke" / "report.md"
            if out.returncode == 0 and rep.exists():
                dm = [ln for ln in rep.read_text(encoding="utf-8").splitlines()
                      if "dynamics-memory" in ln]
                report("A3-bench-smoke", "PASS",
                       "bench 可跑通；" + (dm[0].strip() if dm else "无 dm 行"))
            else:
                report("A3-bench-smoke", "FAIL", (out.stdout + out.stderr)[-1000:])
        finally:
            mock.terminate()
            mock.wait(timeout=15)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- A4/A5/A6
def check_a4() -> None:
    d = ROOT / "tests" / "characterization"
    if not d.is_dir():
        report("A4", "PENDING", "characterization 套件 P3 冻结")
        return
    out = pytest_run([str(d)], timeout=600)
    report("A4", "PASS" if out.returncode == 0 else "FAIL",
           out.stdout.strip().splitlines()[-1:] if out.returncode == 0 else out.stdout[-600:])


def check_a5() -> None:
    f = ROOT / "tests" / "unit" / "test_import_boundaries.py"
    if not f.is_file():
        report("A5", "PENDING", "导入边界测试 P2 落地")
        return
    out = pytest_run([str(f)], timeout=120)
    report("A5", "PASS" if out.returncode == 0 else "FAIL",
           out.stdout.strip().splitlines()[-1:] if out.returncode == 0 else out.stdout[-600:])


def check_a6() -> None:
    # P2 的 policy.py 是空壳（POLICIES 为空）；A6 以 effects.py 落地（P5）为到期信号。
    pol = ROOT / "hybrid_memory" / "dispatch" / "policy.py"
    eff = ROOT / "hybrid_memory" / "dispatch" / "effects.py"
    if not pol.is_file() or not eff.is_file():
        report("A6", "PENDING", "dispatch.policy/effects P5 落地")
        return
    sys.path.insert(0, str(ROOT))
    try:
        from hybrid_memory.dispatch import policy  # noqa
        from hybrid_memory.dispatch import effects  # noqa
        policy.assert_consumers(effects.EFFECTS)
        report("A6", "PASS", f"{len(effects.EFFECTS)} 种 kind 皆有 applier")
    except Exception as exc:  # noqa: BLE001
        report("A6", "FAIL", f"{type(exc).__name__}: {exc}")
    finally:
        sys.path.remove(str(ROOT))


# ---------------------------------------------------------------- A7/A8 契约快照
def _snapshot_tree(obj, depth: int = 0):
    if isinstance(obj, dict):
        return {k: _snapshot_tree(v, depth + 1) for k, v in sorted(obj.items())} \
            if depth < 2 else sorted(obj)
    if isinstance(obj, (list, tuple)):
        return [_snapshot_tree(x, depth + 1) for x in obj[:3]]
    return type(obj).__name__


def capture_contracts() -> dict:
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT))
    try:
        from test_server import _http, _service  # noqa
        svc = _service()
        health = dict(svc.health_view())
        signals = dict(svc.signals())
        table: dict[str, int] = {}
        with _http(svc) as (post, get, httpd):
            port = httpd.server_address[1]
            table["health_noauth"] = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=10).status
            table["recall_missing_q"] = get("/recall")[0]
            table["search_k0"] = post("/search", {"query": "x", "k": 0})[0]
            table["feedback_badtype"] = post("/feedback", {"retrieval_id": "x"})[0]
            table["feedback_404"] = post(
                "/feedback", {"retrieval_id": 999, "question": "x", "answer": "y"})[0]
            svc.observe("部署在哪", "已改到 B 服务器")
            rid = svc.recall("部署在哪")["retrieval_id"]
            table["feedback_200"] = post(
                "/feedback", {"retrieval_id": rid, "question": "部署在哪",
                              "answer": "B"})[0]
            table["feedback_409"] = post(
                "/feedback", {"retrieval_id": rid, "question": "部署在哪",
                              "answer": "B"})[0]
            table["resolve_badverdict"] = post(
                "/resolve", b'{"left":0,"right":1,"verdict":"updtae"}')[0]
            table["observe_badjson"] = post("/observe", b"{not json")[0]
            table["save_401"] = post("/save", {},
                                     {"Authorization": "Bearer wrong"})[0]
            table["save_405"] = get("/save")[0]
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.putrequest("POST", "/observe")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Authorization", f"Bearer {svc.token}")
            conn.putheader("Content-Length", str(4 * 1024 * 1024 + 1))
            conn.endheaders()
            table["observe_413"] = conn.getresponse().status
            conn.close()
            table["save_415"] = post(
                "/save", {}, {"Content-Type": "application/x-www-form-urlencoded"})[0]
            svc.tasks.capacity = 1
            svc.report_miss("occupy")
            table["miss_503"] = post("/miss", {"query": "another"})[0]
            svc2 = _service()
            svc2.trio_mode = True
            with _http(svc2) as (post2, _, _):
                for name in ("propose", "resolve", "diagnose"):
                    table[f"trio_{name}_403"] = post2(f"/{name}", {})[0]
        return {
            "health": {"fields": _snapshot_tree(health),
                       "literals": {"validation": health.get("validation")}},
            "signals": {"fields": _snapshot_tree(signals)},
            "status_table": table,
        }
    finally:
        sys.path.remove(str(ROOT / "tests"))
        sys.path.remove(str(ROOT))


def check_a7(freeze: bool) -> None:
    live = capture_contracts()
    SNAP_DIR.mkdir(exist_ok=True)
    if freeze:
        for name in SNAP_FILES:
            key = name[:-5]
            (SNAP_DIR / name).write_text(
                json.dumps(live[key], ensure_ascii=False, indent=1, sort_keys=True),
                encoding="utf-8")
        report("A7-freeze", "PASS", f"快照已写 {SNAP_DIR}（改契约需注明理由）")
        return
    ok = True
    for name in SNAP_FILES:
        key = name[:-5]
        p = SNAP_DIR / name
        if not p.is_file():
            report("A7", "FAIL", f"缺快照 {name}，先跑 --freeze")
            ok = False
            continue
        want = json.loads(p.read_text(encoding="utf-8"))
        if want != live[key]:
            report("A7", "FAIL", f"{name} 漂移：want={want} live={live[key]}")
            ok = False
    if ok:
        report("A7", "PASS", "health/signals/状态表与快照一致")


def check_a8() -> None:
    # 状态表比较已在 A7 覆盖；此处先断言"坏输入无 500"，再补 agents 解析 fuzz（P6）与过渡证据。
    p = SNAP_DIR / "status_table.json"
    if p.is_file():
        table = json.loads(p.read_text(encoding="utf-8"))
        bad = {k: v for k, v in table.items() if v == 500}
        if bad:
            report("A8", "FAIL", f"坏输入返回 500：{bad}")
            return
        report("A8", "PASS", f"状态表 {len(table)} 探针无 500（可预见错误皆 4xx/503）")
    ag = ROOT / "hybrid_memory" / "agents" / "opencode.py"
    if not ag.is_file():
        out = pytest_run(["tests/test_trio_protocol.py::"
                          "test_opencode_runner_parses_json_stream_and_rejects_missing_cli"],
                         timeout=120)
        if out.returncode == 0:
            report("A8", "PASS", "过渡证据：trio 解析测试过；fuzz P6 落地")
        else:
            report("A8", "FAIL", "过渡证据失效\n" + out.stdout[-600:])
        return
    sys.path.insert(0, str(ROOT))
    try:
        from hybrid_memory.agents import opencode as oc  # noqa
        bad = ["", "not json", "[1,2]", '{"a":1}\n{"b":', "null"]
        fuzz_ok = True
        for sample in bad:
            try:
                oc.OpenCodeRunner._parse_text(sample)
            except oc.AgentProtocolError:
                continue
            report("A8", "FAIL", f"fuzz 未拒收 {sample!r}")
            fuzz_ok = False
            break
        if fuzz_ok:
            report("A8", "PASS", "agents 解析 fuzz 全拒收")
    except Exception as exc:  # noqa: BLE001
        report("A8", "FAIL", f"{type(exc).__name__}: {exc}")
    finally:
        sys.path.remove(str(ROOT))


# ---------------------------------------------------------------- A9
def _ast_literal_in(path: Path, func: str, value: int) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
            return any(isinstance(n, ast.Constant) and n.value == value
                       for n in ast.walk(node))
    return False


def _find_trio_memories_file() -> tuple[Path | None, str]:
    # P6：agents/payload.memory_snapshot；旧名 _memories 兼容旧树。
    for p in (ROOT / "hybrid_memory" / "agents" / "payload.py",
              ROOT / "hybrid_memory" / "agent" / "trio.py"):
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8")
        if "memory_snapshot" in txt:
            return p, "memory_snapshot"
        if "_memories" in txt:
            return p, "_memories"
    return None, "_memories"


def _find_tasks_file() -> Path:
    p = ROOT / "hybrid_memory" / "store" / "tasks.py"
    return p if p.is_file() else ROOT / "hybrid_memory" / "taskstore.py"


def check_a9(phase: str) -> None:
    import inspect
    sys.path.insert(0, str(ROOT))
    order = ["P0", "P1", "P2", "P3", "P4", "P5", "P6"]
    def due(p: str) -> bool:
        return order.index(phase) >= order.index(p)
    try:
        from hybrid_memory.config import Cfg  # noqa
        from hybrid_memory.taskstore import TaskStore  # noqa
        from hybrid_memory.core.signals import SignalQueue  # noqa
        retained = any(p.suffix == ".py" and "def retention_report" in p.read_text(
            encoding="utf-8", errors="replace")
            for p in (ROOT / "hybrid_memory").rglob("*.py"))
        rows = [
            ("M cap_m", "P0", isinstance(Cfg.cap_m, int) and Cfg.cap_m > 0),
            ("task 4096", "P0",
             inspect.signature(TaskStore.__init__).parameters["capacity"].default == 4096),
            ("signal cap", "P0", "cap" in inspect.signature(SignalQueue.__init__).parameters),
        ]
        mem_file, mem_func = _find_trio_memories_file()
        rows.append(("snapshot 500", "P0",
                     mem_file is not None and _ast_literal_in(mem_file, mem_func, 500)))
        trio_file = (ROOT / "hybrid_memory" / "agents" / "payload.py"
                     if (ROOT / "hybrid_memory" / "agents").is_dir()
                     else ROOT / "hybrid_memory" / "agent" / "trio.py")
        txt = trio_file.read_text(encoding="utf-8") if trio_file.is_file() else ""
        rows.append(("window 12000", "P0", "12000" in txt))
        ttxt = _find_tasks_file().read_text(encoding="utf-8")
        rows.append(("trace 18/24k", "P0", "> 18" in ttxt and "24000" in ttxt))
        rows.append(("cap_c/cap_a", "P2",
                     hasattr(Cfg, "cap_c") and hasattr(Cfg, "cap_a")))
        rows.append(("L0 retention_report", "P4", retained))
        ok = True
        for name, since, passed in rows:
            if not due(since):
                report("A9", "PENDING", f"{name}（{since} 落地）")
            elif passed:
                report("A9", "PASS", name)
            else:
                report("A9", "FAIL", name)
                ok = False
        # propose 批量 50：行为证据（现行测试）
        out = pytest_run(["tests/test_server.py::"
                          "test_proposal_bounds_and_malformed_supersedes_do_not_partially_apply"],
                         timeout=120)
        report("A9", "PASS" if out.returncode == 0 else "FAIL", "propose 批量 50")
        if due("P4"):
            out = pytest_run(["tests/integration/test_service_recall.py::test_contested_bound"],
                             timeout=120)
            report("A9", "PASS" if out.returncode == 0 else "FAIL", "contested 行为")
    finally:
        sys.path.remove(str(ROOT))


# ---------------------------------------------------------------- A10
def check_a10() -> None:
    new = ROOT / "tests" / "integration" / "test_dispatch_recovery.py"
    if new.is_file():
        targets = [str(new)]
    else:
        targets = ["tests/integration/test_service_observe.py", "tests/test_semantic_recovery.py",
                   "tests/test_durable_tasks.py"]
    out = pytest_run(targets, timeout=900)
    if out.returncode == 0:
        report("A10", "PASS", out.stdout.strip().splitlines()[-1])
    else:
        report("A10", "FAIL", out.stdout[-800:])


# ---------------------------------------------------------------- PENDING
def check_pending() -> None:
    text = (ROOT / "analysis" / "acceptance-criteria.md").read_text(encoding="utf-8")
    print("--- PENDING 白名单（可见，不阻塞） ---")
    for pid, what, cond in PENDING:
        mark = "OK " if pid in text else "MISSING"
        print(f"  [{mark}] {pid} {what} → 解冻：{cond}")
        if pid not in text:
            report("PENDING-sync", "FAIL", f"{pid} 未在 acceptance-criteria.md 中")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    phase = detect_phase()
    print(f"repo={ROOT} phase={phase} freeze={args.freeze} full={args.full}", flush=True)
    check_a1()
    check_a2()
    check_a3(full=args.full)
    check_a4()
    check_a5()
    check_a6()
    check_a7(freeze=args.freeze)
    check_a8()
    check_a9(phase)
    check_a10()
    check_pending()
    fails = [r for r in results if r[1] == "FAIL"]
    print(f"=== {len(results)} 项："
          f"{sum(1 for r in results if r[1]=='PASS')} PASS，"
          f"{sum(1 for r in results if r[1]=='PENDING')} PENDING，"
          f"{sum(1 for r in results if r[1]=='SKIP')} SKIP，{len(fails)} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
