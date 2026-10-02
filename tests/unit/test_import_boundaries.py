"""导入边界（A5/I1/I2）：绿护栏 + xfail(strict) 的终态规则。

终态规则现在标红是预期的（P2）；P4/P5/P6 消红时必须摘掉 xfail 标记——
strict=True 让"修好了却忘摘标记"变红（XPASS 即失败），防止标记烂尾。
本文件只扫 `hybrid_memory/`（产品代码），不扫 tests/eval。
"""
from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path

import pytest

PKG = "hybrid_memory"
ALWAYS_OK = {"__future__"}          # 不计入判定
NUMPY_OK_IN = {"core", "embed"}     # 允许用 numpy 的包（数值内核）

NEW_SHELLS = [
    "hybrid_memory.errors",
    "hybrid_memory.telemetry",
    "hybrid_memory.guards.provenance",
    "hybrid_memory.guards.grounding",
    "hybrid_memory.guards.bounds",
    "hybrid_memory.store",
    "hybrid_memory.store.schema",
    "hybrid_memory.dispatch",
    "hybrid_memory.dispatch.policy",
]

# core/ 永不得碰的上层/同级（单向依赖的 eternal guard，P2 即绿）
_CORE_FORBIDDEN = {"service", "transport", "store", "dispatch", "agents",
                   "agent", "guards", "llm", "semantics", "legacy", "server",
                   "taskstore", "logstore", "worker", "candgen", "interaction",
                   "triggers", "investigation_context"}


def _dotted(path: Path, repo_root: Path) -> str:
    rel = path.relative_to(repo_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_from(mod_dotted: str, level: int, name: str | None,
                  alias: str) -> str:
    """ImportFrom 节点 → 绝对虚点名。level=0 是绝对导入，直接记模块名；
    相对导入则 package 上溯 level-1 层再接 name/alias。"""
    if level == 0:
        if name == PKG:  # from hybrid_memory import <sub>：记子模块
            return f"{PKG}.{alias}" if alias != "*" else PKG
        return name or alias
    pkg = mod_dotted.split(".")[:-1] if "." in mod_dotted else []
    up = level - 1
    base = pkg[:len(pkg) - up] if up <= len(pkg) else []
    if name:
        return ".".join(base + name.split("."))
    return ".".join(base + [alias])


def _imports_of(path: Path, repo_root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mod = _dotted(path, repo_root)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    out.add(_resolve_from(mod, node.level, node.module, ""))
                else:
                    out.add(_resolve_from(mod, node.level, node.module, a.name))
    return {i for i in out if i} - ALWAYS_OK


def _is_stdlib(dotted: str) -> bool:
    return dotted.split(".")[0] in sys.stdlib_module_names


def _hm_files(repo_root: Path, *sub: str):
    base = repo_root / PKG
    for part in sub:
        p = base / part
        if p.is_file():
            yield p
        else:
            yield from sorted(p.rglob("*.py"))


# ------------------------------------------------------------- 绿护栏（P2 即绿）


def test_foundation_is_leaf(repo_root):
    """config/errors/telemetry 只用标准库（地基层，不碰任何包）。"""
    bad = {}
    for f in _hm_files(repo_root, "config.py", "errors.py", "telemetry.py"):
        non_std = sorted(i for i in _imports_of(f, repo_root)
                         if not _is_stdlib(i))
        if non_std:
            bad[f.name] = non_std
    assert not bad, f"地基层越界: {bad}"


def test_core_no_upward_imports(repo_root):
    """core/ 永不 import 上层（eternal guard；比终态规则弱，但 P2 即生效）。"""
    bad = {}
    for f in _hm_files(repo_root, "core"):
        hits = sorted(i for i in _imports_of(f, repo_root)
                      if i.startswith(PKG + ".")
                      and i.split(".")[1] in _CORE_FORBIDDEN)
        if hits:
            bad[f.name] = hits
    assert not bad, f"core 上跳: {bad}"


def test_guards_foundation_only(repo_root):
    """guards/* 只用标准库 + errors/config + core（横切层，不碰服务层）。"""
    allowed_prefixes = (PKG + ".errors", PKG + ".config", PKG + ".core.",
                        PKG + ".guards.")
    bad = {}
    for f in _hm_files(repo_root, "guards"):
        hits = sorted(i for i in _imports_of(f, repo_root)
                      if not _is_stdlib(i)
                      and not i.startswith(allowed_prefixes))
        if hits:
            bad[f.name] = hits
    assert not bad, f"guards 越界: {bad}"


def test_new_shells_import_cleanly():
    """P2 准出：新模块 import 无环、无 ImportError。"""
    for dotted in NEW_SHELLS:
        importlib.import_module(dotted)


# --------------------------------------- 终态规则（红是预期的，消红时摘标记）


def test_core_zero_cross_layer(repo_root):
    """终态 core/ 只用标准库 + numpy + core + config/errors（I1 字面）。"""
    allowed_prefixes = (PKG + ".core.", PKG + ".config", PKG + ".errors")
    bad = {}
    for f in _hm_files(repo_root, "core"):
        if f.name == "__init__.py":
            continue
        hits = sorted(i for i in _imports_of(f, repo_root)
                      if not _is_stdlib(i)
                      and not i.split(".")[0] == "numpy"
                      and not i.startswith(allowed_prefixes)
                      and i != PKG + ".core")
        if hits:
            bad[f.name] = hits
    assert not bad, f"core 越层: {bad}"


def test_pipeline_single_reader(repo_root):
    """I2：MEMORY_PIPELINE 只在 config.resolve_pipeline 被读。"""
    pat = re.compile(r"""environ(?:\.get|\[)\s*\(?\s*["']MEMORY_PIPELINE["']|"""
                     r"""getenv\(\s*["']MEMORY_PIPELINE["']""")
    bad = []
    for f in sorted((repo_root / PKG).rglob("*.py")):
        if f.name == "config.py":
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                bad.append(f"{f.relative_to(repo_root)}:{n}")
    assert not bad, f"多处读 MEMORY_PIPELINE: {bad}"


def test_server_is_thin_shim(repo_root):
    """终态 server.py 是薄 shim（≤10 行，只引 service/transport）。"""
    f = repo_root / PKG / "server.py"
    lines = f.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 10, f"server.py 仍是 {len(lines)} 行单体"
    hm = {i for i in _imports_of(f, repo_root) if i.startswith(PKG + ".")}
    bad = sorted(i for i in hm
                 if not i.startswith((PKG + ".service.", PKG + ".transport.")))
    assert not bad, f"server shim 引了旧路径: {bad}"


def test_agents_boundaries(repo_root):
    """终态 agents/ 存在且不碰 store/（I1）。"""
    agents = repo_root / PKG / "agents"
    assert agents.is_dir(), "agents/ 尚未落地"
    bad = {}
    for f in sorted(agents.rglob("*.py")):
        hits = sorted(i for i in _imports_of(f, repo_root)
                      if i.startswith(PKG + ".store"))
        if hits:
            bad[f.name] = hits
    assert not bad, f"agents 碰 store: {bad}"
