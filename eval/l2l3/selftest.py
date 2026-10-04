"""工具链自检（不依赖真实 provider / 真实 opencode CLI）：

mock LLM（eval/mock_llm.py，本地 bge 嵌入）+ 动态 fake opencode CLI
（haul 候选取自窗口原文切片——必然过接地；selector 一律 CREATE）跑通：
语料装配 → sidecar 子进程（真实 bootstrap 接线）→ observe → 探针 → 排空 →
导出 → 盲序工作台 → 填表 → 结算。全链绿 = 工具链就绪，等真实 key 即可跑。
"""
from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

_REPO = Path(__file__).resolve().parents[2]
_EVAL = _REPO / "eval"
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_EVAL))

FAKE_CLI = """#!/usr/bin/env python3
import json, sys
argv = sys.argv[1:]
if argv[:1] == ["serve"]:
    import socket
    port = int(argv[argv.index("--port") + 1])
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port)); s.listen(4)
    while True:
        try:
            c, _ = s.accept(); c.close()
        except OSError:
            break
if argv[:2] == ["run", "--help"]:
    print("Usage: opencode run [options] [message..]")
    print("  --file <path>   attach file")
    print("  --agent <name>")
    sys.exit(0)
role = argv[argv.index("--agent") + 1]
payload = json.loads(open(argv[argv.index("--file") + 1], encoding="utf-8").read())
if role == "hauler":
    win = payload.get("window") or []
    text = ""
    for u in win:
        if u.get("unit_id") != payload["unit_id"]:
            continue
        t = (u.get("user_text") or u.get("assistant_text") or "")
        if t:
            text = t[:80]
            break
    reply = {"candidates": [{"text": text or "项目统一使用 bun 工具",
                             "source_unit_ids": [payload["unit_id"]]}]}
elif role == "selector":
    reply = {"decisions": [{"candidate_index": 0, "action": "CREATE",
                            "reason": "selftest"}]}
else:
    reply = {"diagnosis": "ok", "rules": [], "repair_candidates": [],
             "rule_reviews": []}
print(json.dumps({"type": "text",
                  "part": {"text": json.dumps(reply, ensure_ascii=False)}}))
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_mock(port: int, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(f"http://127.0.0.1:{port}/stats", timeout=2).read()
            return
        except OSError:
            time.sleep(1.0)
    raise RuntimeError("mock_llm 未就绪")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="l2l3-selftest-"))
    cli_dir = tmp / "bin"
    cli_dir.mkdir()
    cli = cli_dir / ("opencode.py" if os.name == "nt" else "opencode")
    cli.write_text(FAKE_CLI, encoding="utf-8")
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    if os.name == "nt":
        (cli_dir / "opencode.cmd").write_text(
            f'@echo off\r\n"{sys.executable}" "{cli}" %*\r\n', encoding="utf-8")

    mock_port = _free_port()
    mock = subprocess.Popen(
        [sys.executable, str(_EVAL / "mock_llm.py"), str(mock_port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_mock(mock_port)
        print(f"[selftest] mock_llm 就绪 :{mock_port}")

        from eval.l2l3.gen_l2 import build as build_l2
        corpus_path = tmp / "l2_corpus.json"
        corpus = build_l2(api_key="mock", seeds=1, out_path=str(corpus_path),
                          mock=True, trim=True)
        corpus["streams"] = corpus["streams"][:2]      # 自检裁剪：只跑 2 条流
        corpus_path.write_text(json.dumps(corpus, ensure_ascii=False),
                               encoding="utf-8")
        n_turns = sum(len(s["turns"]) for s in corpus["streams"])
        print(f"[selftest] 语料装配 {len(corpus['streams'])} 流 / {n_turns} 轮")

        from eval.l2l3.run_audit_chain import run_chain
        env = {"PATH": f"{cli_dir}{os.pathsep}{os.environ.get('PATH', '')}",
               "ZAI_API_KEY": "mock",
               "ZAI_BASE_URL": f"http://127.0.0.1:{mock_port}"}
        run = run_chain(corpus, str(tmp / "proj"), str(tmp / "runs" / "l2"),
                        env_extra=env, drain_timeout=900, with_probes=True)
        print(f"[selftest] 跑链：fed={run['fed_turns']} mems={run['mems']} "
              f"selector_done={run['selector_done']} drain={run['drain']}")
        assert run["fed_turns"] == n_turns
        assert run["mems"] >= 1, "CREATE 未产生任何记忆"
        assert run["selector_done"] >= 1
        assert run["drain"].get("drained") or run["drain"].get("active") == {}

        export = json.loads((tmp / "runs" / "l2" / "export.json")
                            .read_text(encoding="utf-8"))
        unit_ids = {u["unit_id"] for u in export["units"]}
        for m in export["mems"]:
            assert m["src"], f"记忆 {m['id']} 无 L0 引用"
            assert set(m["src"]) <= unit_ids, f"记忆 {m['id']} 引用越界"
        assert run["probe_records"], "探针未产生记录"

        from eval.l2l3.audit import aggregate, build_worksheet
        info = build_worksheet([str(tmp / "runs" / "l2")],
                               str(tmp / "worksheet.jsonl"),
                               str(tmp / "key.json"), n=8)
        print(f"[selftest] 工作台：{info}")
        rows = [json.loads(l) for l in
                (tmp / "worksheet.jsonl").read_text(encoding="utf-8").splitlines()]
        assert rows and len(rows) <= 8
        assert all("corpus_kind" not in r and "chain" not in r for r in rows), \
            "盲序泄漏：worksheet 不得含链路字段"
        filled = tmp / "filled.jsonl"
        with open(filled, "w", encoding="utf-8") as f:
            for r in rows:
                r["verdicts"] = {q: "pass" for q in
                                 ("grounded", "atomic", "faithful",
                                  "disposition", "relevant")}
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        agg = aggregate(str(filled), str(tmp / "key.json"),
                        [str(tmp / "runs" / "l2")], str(tmp / "report.md"))
        print(f"[selftest] 结算：{agg}")
        assert agg["rows"] == len(rows) and agg["defects"] == 0
        print("[selftest] ALL OK")
    finally:
        mock.terminate()
        try:
            mock.wait(10)
        except subprocess.TimeoutExpired:
            mock.kill()
        print(f"[selftest] 工作目录（诊断用）：{tmp}")


if __name__ == "__main__":
    main()
