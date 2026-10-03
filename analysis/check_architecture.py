from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

try:  # 脚本方式运行（python analysis/check_architecture.py）
    from architecture_contract import (DELETIONS, MODULE_IO, MODULE_NOTES,
                                       PLANNED_MODULES, PLANNED_SYMBOLS,
                                       SYMBOL_OVERRIDES, TARGET_PATHS)
except ImportError:  # 作为 analysis.check_architecture 导入时
    from analysis.architecture_contract import (DELETIONS, MODULE_IO, MODULE_NOTES,
                                                PLANNED_MODULES, PLANNED_SYMBOLS,
                                                SYMBOL_OVERRIDES, TARGET_PATHS)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "architecture-inventory.md"
DESIGN = ROOT / "analysis" / "target-architecture.md"

MODULES = {
    "hybrid_memory/__init__.py": ("保留", "包的最小导出面及延迟组装", "配置与服务"),
    "hybrid_memory/config.py": ("接线", "引擎参数、进程设置及环境解析", "配置与服务"),
    "hybrid_memory/errors.py": ("接线", "可拒收、可降级、不可启动三类错误", "错误与观测"),
    "hybrid_memory/telemetry.py": ("接线", "健康、队列、模型调用与容量观测", "错误与观测"),
    "hybrid_memory/server.py": ("兼容保留", "python -m hybrid_memory.server 的部署入口", "传输与部署"),
    "hybrid_memory/logstore.py": ("兼容保留", "LogStore 旧导入位；真实实现已迁入 store/evidence.py", "兼容边界"),
    "hybrid_memory/llm.py": ("兼容保留", "智谱 chat 客户端旧导入位；真实实现已迁入 llm/client.py", "兼容边界"),
    "hybrid_memory/llm/": ("保留", "ZAI chat 传输、重试和响应缓存", "模型适配"),
    "hybrid_memory/core/": ("保留收口", "三池、信用、张力、触发及领域协议", "三池与领域"),
    "hybrid_memory/store/evidence.py": ("保留", "不可覆盖的 L0 证据、索引及逐单元恢复", "存储与恢复"),
    "hybrid_memory/store/schema.py": ("实现接线", "各库身份、版本与增量迁移，高版本拒绝启动", "存储与恢复"),
    "hybrid_memory/store/": ("保留收口", "SQLite、租约、回执及 checkpoint 原子性", "存储与恢复"),
    "hybrid_memory/dispatch/": ("统一接线", "业务信号路由、预算调度及效果应用", "信号与派发"),
    "hybrid_memory/agents/": ("保留收口", "三角色载荷、严格校验及 OpenCode 运行器", "三 Agent 协议"),
    "hybrid_memory/service/": ("保留收口", "单项目编排、因果界、读取及人审", "配置与服务"),
    "hybrid_memory/transport/": ("保留收口", "HTTP、鉴权、DTO、组装与人审 CLI", "传输与部署"),
    "hybrid_memory/guards/bounds.py": ("接线", "请求身份与批量上限；clamp 壳明确删除", "边界校验"),
    "hybrid_memory/guards/provenance.py": ("实现接线", "来源存在性与因果上界的纯校验", "边界校验"),
    "hybrid_memory/guards/grounding.py": ("保留收口", "浅层正文一致性；联接 I/O 留在 service", "边界校验"),
    "hybrid_memory/guards/redact.py": ("保留接线", "凭据模式的统一视图脱敏，不修改原始证据", "边界校验"),
    "hybrid_memory/guards/": ("保留", "边界校验包的 import 入口", "边界校验"),
    "hybrid_memory/embed/": ("保留", "向量传输、分块及无原文向量缓存", "模型适配"),
    "hybrid_memory/semantics/provider.py": ("显式化", "SemanticsProvider 双语义通路与健康可观测性", "模型适配"),
    "hybrid_memory/semantics/": ("显式化", "存量 judge、反馈归因及 reflection 语义通路", "模型适配"),
    "hybrid_memory/legacy/": ("兼容保留", "显式 legacy 管线和裸引擎消费者；不在默认管线暗调", "兼容边界"),
    "hybrid_memory/agent/": ("兼容保留", "旧调查员和人审入口的 re-export 垫片", "兼容边界"),
    "hybrid_memory/candgen/": ("兼容保留", "旧候选类型与生成器的 re-export 垫片", "兼容边界"),
    "hybrid_memory/taskstore.py": ("兼容保留", "TaskStore 旧导入位；真实状态机位于 store/tasks.py", "兼容边界"),
    "hybrid_memory/worker.py": ("兼容保留", "裸引擎 SignalWorker 旧导入位", "兼容边界"),
    "hybrid_memory/interaction.py": ("兼容保留", "InteractionUnit/Window 旧导入位", "兼容边界"),
    "hybrid_memory/investigation_context.py": ("兼容保留", "不可变调查上下文旧导入位", "兼容边界"),
    "hybrid_memory/triggers.py": ("兼容保留", "确定性调度提示旧导入位", "兼容边界"),
    "analysis/": ("保留", "设计登记、验收及符号覆盖工具；不参与产品效果", "验收资产"),
    "tests/": ("保留迁移", "行为、恢复、权限及协议回归；不得按产品死代码删除", "验收资产"),
    "eval/tide/": ("冻结保留", "独立账本、生成器、判分、基线及 HTTP 适配", "评测边界"),
    "eval/tests/": ("冻结保留", "TIDE 元评测的测试资产", "评测边界"),
    "eval/checks/": ("历史归档", "依赖已移除仿真模块的历史诊断脚本；不得作为现行入口", "评测边界"),
    "eval/": ("迁移修复", "离线 mock、HTTP 驱动及预览 harness", "评测边界"),
}




def source_paths(root: Path = ROOT) -> list[Path]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
                         check=True, capture_output=True).stdout
    names = {p.decode("utf-8") for p in out.split(b"\0") if p}
    names.add("analysis/check_architecture.py")
    for directory in ("hybrid_memory", "tests", "eval", "analysis"):
        names.update(p.relative_to(root).as_posix() for p in (root / directory).rglob("*.py")
                     if "__pycache__" not in p.parts)
    return [root / n for n in sorted(names)
            if not n.startswith("agent/") and (root / n).is_file()]


def module_policy(path: str) -> tuple[str, str, str]:
    if path in MODULES:
        return MODULES[path]
    prefixes = sorted((k for k in MODULES if k.endswith("/")), key=len, reverse=True)
    for prefix in prefixes:
        if path.startswith(prefix):
            return MODULES[prefix]
    raise ValueError(f"unregistered module: {path}")


def direct_nodes(node: ast.AST):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from direct_nodes(child)


def clean(text: str, limit: int = 300) -> str:
    text = " ".join(text.split()).replace("`", "'")
    return text if len(text) <= limit else text[:limit] + "…"


def function_io(node: ast.FunctionDef | ast.AsyncFunctionDef):
    inputs = ast.unparse(node.args) or "无参数"
    if node.returns is not None:
        annotation = ast.unparse(node.returns)
    else:
        annotation = "未注解"
    returns = sorted({clean(ast.unparse(n.value), 20000) if n.value is not None else "None"
                      for n in direct_nodes(node) if isinstance(n, ast.Return)})
    yields = [n for n in direct_nodes(node) if isinstance(n, (ast.Yield, ast.YieldFrom))]
    abstract = any(isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                   and n.value.value is Ellipsis for n in node.body)
    stub = any(isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
               and isinstance(n.exc.func, ast.Name) and n.exc.func.id == "NotImplementedError"
               for n in direct_nodes(node))
    output = ("协议声明，没有业务实现" if abstract else "未实现；仅抛 NotImplementedError" if stub
              else "生成器/上下文管理器" if yields else "None" if not returns else "；".join(returns))
    output = f"{annotation}；{output}"
    calls = sorted({clean(ast.unparse(n.func), 100) for n in direct_nodes(node)
                    if isinstance(n, ast.Call)})
    raises = sorted({clean(ast.unparse(n.exc), 160) for n in direct_nodes(node)
                     if isinstance(n, ast.Raise) and n.exc is not None})
    effects = "调用 " + (", ".join(calls) or "无外部调用")
    errors = "；异常 " + (", ".join(raises) or "无显式 raise；被调用方错误仍可传播")
    body = [n for n in node.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                    and isinstance(n.value.value, str))]
    delegate = None
    if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Call):
        delegate = clean(ast.unparse(body[0].value.func), 120)
    return clean(inputs, 20000), output, clean(effects, 20000), clean(errors, 20000), delegate


def definitions(tree: ast.AST) -> list[dict]:
    rows = []

    def visit(node: ast.AST, scope: tuple[str, ...]):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = ".".join((*scope, child.name))
                doc = ast.get_docstring(child) or ""
                if isinstance(child, ast.ClassDef):
                    fields = [ast.unparse(n) for n in child.body
                              if isinstance(n, ast.AnnAssign)]
                    bases = [ast.unparse(b) for b in child.bases]
                    rows.append({"name": qualified, "line": child.lineno, "kind": "class",
                                 "doc": clean(doc, 500), "input": clean("；".join(fields), 20000) or "见显式或继承的 __init__；无新增字段",
                                 "output": "类型/实例；基类 " + (", ".join(bases) or "object"),
                                 "effects": "字段与方法契约；dataclass 自动生成的方法不另建手写符号",
                                 "errors": "见构造函数及方法"})
                else:
                    inputs, output, effects, errors, delegate = function_io(child)
                    rows.append({"name": qualified, "line": child.lineno, "kind": "function",
                                 "doc": clean(doc, 500), "input": inputs, "output": output,
                                 "effects": effects, "errors": errors, "delegate": delegate})
                visit(child, (*scope, child.name))
            else:
                visit(child, scope)

    visit(tree, ())
    return rows


def exports(tree: ast.Module) -> list[str]:
    values = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            values.extend(f"{a.asname or a.name} ← {prefix}.{a.name}" for a in node.names)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__"
                                               for t in node.targets):
            values.append("__all__ = " + ast.unparse(node.value))
    return values


def inventory(root: Path = ROOT) -> list[dict]:
    modules = []
    for path in source_paths(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text, filename=relative)
        disposition, purpose, owner = module_policy(relative)
        modules.append({"path": relative, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "disposition": disposition, "purpose": purpose, "owner": owner,
                        "symbols": definitions(tree), "exports": exports(tree)})
    return modules + auxiliary_inventory(root)


def parameter_end(text: str, start: int) -> int | None:
    depth, quote, escaped = 0, "", False
    for pos in range(start, len(text)):
        char = text[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char in "\"'`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return pos
    return None


def ts_definitions(text: str, path: str) -> list[dict]:
    outputs = {
        "log": "void；脱敏 stderr 诊断",
        "auth": "Promise<string>；当前 token，不进入模型载荷",
        "headers": "Promise<Record<string,string>>；bearer 请求头",
        "check": "boolean；401 时关闭后续发送",
        "call": "Promise<Res>；ok/status/data，传输和 JSON 失败外显",
        "errText": "string；失败状态和展示文案",
        "drain": "Promise<void>；消费子进程 pipe",
        "fmtHits": "string；有界命中片段与来源",
        "reportMiss": "void；Legacy 异步缺失上报，Trio 不上报",
        "captureTimeout": "number；有效 timeout 或默认 30000ms",
        "captureAttempts": "number；有限次数或默认 3",
        "captureBackoff": "number；非负毫秒或默认 200",
        "newRequestId": "string；稳定合法 request-id",
        "isTurn": "boolean；outbox turn 形状校验",
        "retain": "boolean；是否保留未确认或终止待查义务",
        "loadOutbox": "CaptureTurn[]；原 id 的持久交付列表",
        "persistOutbox": "void；原子替换 outbox",
        "schedule": "void；串行追加 inflight 工作",
        "observeAck": "acked | retry | stop；observe 接受语义",
        "feedbackAck": "acked | retry | stop；反馈回执语义",
        "attempt": "Promise<{kind,res}>；有限同 id 重试结果",
        "deliver": "Promise<void>；observe 确认后才 feedback，并更新 outbox",
        "flushOutbox": "Promise<void>；顺序交付与重入合并",
        "hooks": "Promise<Plugin>；测试中的 bridge 构造",
    }
    rows = []
    pattern = re.compile(r"(?m)^[ \t]*(?:const|let)[ \t]+(\w+)(?:[ \t]*:[^=\n]*)?"
                         r"[ \t]*=[ \t]*(?:async[ \t]*)?\(")
    for match in pattern.finditer(text):
        start = match.end() - 1
        end = parameter_end(text, start)
        if end is None or re.match(r"\s*(?::[^=]*?)?=>", text[end + 1:end + 1500]) is None:
            continue
        name = match.group(1)
        rows.append({"name": name, "line": text.count("\n", 0, match.start()) + 1,
                     "kind": "function", "doc": outputs.get(name, "具名 TS 内部回调；主文约束其父入口"),
                     "input": clean(text[start + 1:end], 20000) or "无参数",
                     "output": outputs.get(name, "具名回调的实际返回受父入口/测试断言约束"),
                     "effects": "插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界",
                     "errors": "网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显"})
    if path.startswith(".opencode/"):
        rows.append({"name": "default", "line": text.count("\n", 0, text.index("export default")) + 1, "kind": "function",
                     "doc": "主会话 Plugin 组装，不是后台三 Agent runner",
                     "input": "context.directory；process.env；内部会话标记",
                     "output": "Promise<Plugin>；hooks/tool/dispose 或内部会话空对象",
                     "effects": "生命周期、token、本地 outbox、HTTP、会话暂存",
                     "errors": "按主文的 ready/auth/accepted 边界外显"})
        tool_inputs = {
            "memory_search": "query: string",
            "memory_conflicts": "无参数",
            "memory_resolve": "left/right: number；verdict: string；entity_key?: string；服务端要求整数 id",
            "log_search": "query: string；before?: number；scene?: string；k?: number",
            "log_timeline": "entity: string；before?: number；limit?: number",
            "log_stats": "group_by: string；before?: number；limit?: number",
            "log_window": "unit_ids: number[]；max_chars?: number；服务端要求整数 id 与 ≤20 条",
            "memory_propose": "proposals: {text,kind?,salience?,source_unit_ids,entity_key?,supersedes?}[]",
            "memory_diagnose": "miss_type: string；note?: string",
        }
        for match in re.finditer(r"(?m)^\s*(memory_\w+|log_\w+): tool\(\{", text):
            name = "tools." + match.group(1) + ".execute"
            rows.append({"name": name, "line": text.count("\n", 0, match.start()) + 1,
                         "kind": "function", "doc": "注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定",
                         "input": tool_inputs[match.group(1)],
                         "output": "Promise<string>；成功工具视图或可见错误文本",
                         "effects": "调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝",
                         "errors": "Res 错误不得伪装合法空结果"})
        for match in re.finditer(r"(?m)^\s*(?:\"([^\"]+)\"|(event|dispose)):\s*async", text):
            name = match.group(1) or match.group(2)
            rows.append({"name": name, "line": text.count("\n", 0, match.start()) + 1,
                         "kind": "function", "doc": "主会话 hook/关闭入口，功能与参数逐项见主文第 7 节",
                         "input": "sessionID/parts/system output/event；dispose 无参数",
                         "output": "Promise<void>；更新捕获、注入或有界收尾",
                         "effects": "会话状态、检索、outbox、HTTP 与自有进程管理",
                         "errors": "不捕获内部 worker；未确认回合不得静默删除"})
    else:
        for match in re.finditer(r"(?m)^\s*test\((`[^`]*`|\"[^\"]*\"),\s*(?:async\s*)?\(([^)]*)\)\s*=>", text):
            label = clean(match.group(1)[1:-1], 2000)
            rows.append({"name": "test:" + label, "line": text.count("\n", 0, match.start()) + 1,
                         "kind": "function", "doc": "插件行为断言：" + label,
                         "input": match.group(2) or "无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界",
                         "output": "Promise<void> 或 void；成功无值，违约测试失败",
                         "effects": "临时 outbox、mock/spy 与 Plugin hooks，非生产写入",
                         "errors": "expect/assertion/超时失败；不得把过滤用例当完整通过"})
        for name in ("beforeEach", "afterEach"):
            match = re.search(r"(?m)^" + name + r"\(", text)
            if match:
                rows.append({"name": name, "line": text.count("\n", 0, match.start()) + 1,
                             "kind": "function", "doc": "测试隔离设置/恢复，内部匿名 mock 归此回调",
                             "input": "测试运行时，无显式参数", "output": "void",
                             "effects": "建立临时项目、恢复 spy/mock、控制环境",
                             "errors": "初始化/恢复错误导致测试失败"})
    return rows


def auxiliary_inventory(root: Path = ROOT) -> list[dict]:
    paths = [".opencode/plugin/memory-bridge.ts", "tests/memory_bridge.test.ts",
             ".opencode/agent/hauler.md", ".opencode/agent/selector.md", ".opencode/agent/reviewer.md"]
    modules = []
    for path in paths:
        text = (root / path).read_text(encoding="utf-8-sig")
        test = path.startswith("tests/")
        purpose = "真实插件 hooks 的 fake IO 回归" if test else "主会话捕获、检索、工具与可靠交付" if path.endswith(".ts") else "三 Agent 权限与 JSON 输出协议定义"
        modules.append({"path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "disposition": "保留迁移" if test else "保留收口",
                        "purpose": purpose, "owner": "验收资产" if test else "三 Agent 协议与主会话边界",
                        "symbols": ts_definitions(text, path) if path.endswith(".ts") else [],
                        "exports": ["TS 具名 arrow/hook/tool 与参数登记；匿名映射/spy 归其父入口"] if path.endswith(".ts") else
                                   ["输入：封存 role payload；输出：Hauler candidates / Selector decisions / Reviewer bundle；工具权限 '*': deny，mode primary；无源码函数"]})
    return modules


def symbol_purpose(row: dict, module: dict) -> str:
    summaries = {
        "analysis/acceptance_check.py": {
            "report": "追加并打印一条 PASS/FAIL/PENDING/SKIP 验收记录",
            "run": "按受控 cwd/env/timeout 执行验证子进程并捕获结果",
            "pytest_run": "运行指定 pytest 节点，关闭缓存写入并限制执行时间",
            "detect_phase": "按文件存在识别历史迁移阶段，不证明阶段契约都已实现",
            "check_a1": "执行 Python/Bun 测试门并登记结果",
            "check_a2": "验证手工产品断言与对应测试节点的证据链",
            "check_a3": "生成临时 TIDE 数据、元评测和可选 mock bench 烟囱",
            "check_a4": "执行任务状态机 characterization 快照回归",
            "check_a5": "执行静态 import 边界回归",
            "check_a6": "调用当前消费者注册自检并记录结果",
            "_snapshot_tree": "将响应树规范成字段、类型和有限示例结构",
            "capture_contracts": "用 fake 服务和真实本地 HTTP 采集健康、信号和错误契约",
            "check_a7": "比较响应快照；显式 freeze 模式才写新快照",
            "check_a8": "核对错误状态并 fuzz 最终 Agent JSON 对象解析",
            "_ast_literal_in": "查目标函数中是否出现指定常量，只是机械形状检查",
            "_find_trio_memories_file": "定位当前或旧树的记忆快照构造函数",
            "_find_tasks_file": "定位当前 Store 或旧 TaskStore 实现路径",
            "check_a9": "检查当前容量常量、字段与有限行为证据，非完整容量证明",
            "check_a9.due": "判断某容量检查项是否到历史阶段的准出时点",
            "check_a10": "执行逐单元、语义及调查任务恢复测试",
            "check_pending": "逐项打印延期能力并检查基线白名单一致性",
            "main": "组合旧验收门、打印汇总，以 FAIL 数决定退出码",
        },
        "analysis/check_architecture.py": {
            "source_paths": "收集已追踪与新增自有 Python 源路径，排除 vendored agent 和缓存",
            "module_policy": "按已登记文件或责任目录取得处置、功能和归属，未知范围拒绝",
            "direct_nodes": "遍历当前函数节点，排除子函数/类/lambda 的内部行为",
            "clean": "规整登记中的空白与反引号，并按显示字段限制长度",
            "function_io": "提取精确参数、注解、返回/生成器、调用与显式错误；区别协议和空壳",
            "definitions": "枚举全部具名类、方法及 nested 函数并建立作用域全名",
            "definitions.visit": "递归维护类/函数作用域，将每个定义加入源登记",
            "exports": "提取 import/re-export 与 __all__，保留 shim 的对象来源",
            "inventory": "为每个源码模块构造责任、源 hash 和符号输入输出记录",
            "parameter_end": "按引号、转义和括号深度定位 TS 参数边界",
            "ts_definitions": "有限扫描当前 TS 具名 arrow、hook、tool 和测试回调，不假装完整编译器",
            "auxiliary_inventory": "为插件、TS 回归和三份 Agent 定义建立源登记",
            "symbol_purpose": "用明确语义、现状 docstring 或测试场景生成符号说明",
            "render": "生成唯一目标文档的源符号附录，不自动批准新增函数保留",
            "check": "校验模块/符号覆盖、重复、输入输出字段、源漂移和文档链接",
            "main": "显式构建附录或执行只读校验，按问题列表设置退出码",
        },
        "hybrid_memory/core/engine.py": {
            "MemoryEngine": "持有三池、张力、信用待账及信号出口的裸引擎门面",
            "MemoryEngine.next_id": "分配单调记忆 ID 并推进游标",
            "MemoryEngine.add_tension": "登记或刷新未决版本对，不在此执行语义判定",
            "MemoryEngine.observe": "将事件交给领域 ingest",
            "MemoryEngine.retrieve": "将预计算查询向量交给读取算法",
            "MemoryEngine.step": "执行一个逻辑维护步，不用于重复收容量",
            "MemoryEngine._credit_hit": "把 useful 信用记到当前代表，更新命中并按需复活",
            "MemoryEngine._record_shadow_pending": "保存压制对的延迟信用，超限显式计丢弃",
            "MemoryEngine._issue_shadow_credit": "将 shadow 信用结到当前代表并按需复活",
            "MemoryEngine.miss_key": "按问题去空白、小写、长度界生成调查去重 key",
            "MemoryEngine.report_miss.merge": "合并缺失线索、来源和实体，保留已知召回证据",
            "MemoryEngine.report_unit.merge": "并集合并同日志单元的抽取理由和实体",
            "MemoryEngine.pool_sizes": "统计 C/M/A 的物理记忆数，包含退役成员",
        },
        "hybrid_memory/core/confidence.py": {
            "discount_to": "按逻辑时间折损 Beta 证据计数，不修改先验",
            "projected": "计算当前 Beta 置信投影，不修改 Memory",
        },
        "hybrid_memory/core/retrieval.py": {
            "_lex_tokens": "提取 ASCII 标识和 CJK bigram 集合",
            "lexical_scores.idf": "计算当前语料的逆文档频率权重",
            "_prior": "取得 Memory 所属池的检索先验",
            "run_retrieve": "执行排序、质量/置信门、压制、信用和未决冲突读取",
            "run_retrieve._try_select": "尝试选入一条 Memory，必要时记录压制、shadow 和张力",
        },
        "hybrid_memory/core/signals.py": {
            "Signal": "描述业务工作理由的数据载体，不授予操作权限",
            "SignalQueue": "裸引擎有界易失队列与持久交接回调边界",
            "SignalQueue.drain": "取走全部内存信号并清索引；sidecar 不以此可靠交付",
            "SignalQueue.peek_kinds": "只读统计内存信号按 kind 的数量",
            "SignalQueue.__len__": "返回内存队列当前项数",
        },
        "hybrid_memory/agents/opencode.py": {
            "OpenCodeRunner.available": "检测 CLI 是否存在，不证明模型账号可用",
            "OpenCodeRunner.__call__": "兼容 callable 调用并委托唯一 run 实现",
            "OpenCodeRunner.run": "隔离调用真实角色 CLI、采集 JSONL 文本并解析最终对象",
            "OpenCodeRunner._parse_text": "拒绝空输出、非对象、多对象和损坏 JSON",
            "_event": "解析一个 JSONL 事件，非对象或坏行不作为最终角色正文",
        },
        "hybrid_memory/service/observe.py": {
            "_annotate_observe": "将内部单元回执整形成外部接受/重放响应",
            "observe": "先持久绑定交互与请求 ID，再处理有序单元工作",
            "process_unit": "准备封存源结果，原子提交效果与接力后补跨库确认",
            "process_unit.collect": "在当前效果中收集持久信号，不嵌套开启数据库事务",
            "process_unit.mutate": "应用单元游标、场景、信号与一次维护，产生交付回执",
        },
        "hybrid_memory/service/recall.py": {
            "causal_tensions": "筛选双方可访问且观测时刻在因果界内的张力",
            "recall": "准入后选择主动或副本读取，返回统一召回结构",
            "recall_main": "事务性登记真实读取与检索 ID 并保护配置恢复",
            "recall_main.mutate": "修改读取状态及登记，渲染实际展示上下文",
            "recall_result": "按整行 token 预算裁剪并固定真正展示文本",
        },
        "hybrid_memory/service/tools.py": {
            "log_search": "以固定因果上下文查有界日志片段",
            "log_timeline": "以固定因果上下文查实体时间线",
            "log_stats": "在同一因果界取得分组统计和总单元数",
            "log_window": "预留回展预算后读取原文，失败退款、成功按实际字符结算",
            "conflicts": "读取允许范围的未决张力；目标汇入统一冲突台账",
        },
        "hybrid_memory/transport/dto.py": {
            "opt_int": "解析可选严格 64 位整数，排除 bool 和越界数",
            "req_str": "要求非空字符串请求字段",
            "parse_body": "检查媒体、长度与 JSON 对象请求体",
            "capture_request_id": "要求 header/body 身份一致并验证请求 ID 语法",
            "observe_payload": "规范一轮交互 DTO 与幂等身份",
            "feedback_payload": "规范反馈 DTO 的展示 ID、问答和幂等身份",
        },
    }
    if row["name"] in summaries.get(module["path"], {}):
        return summaries[module["path"]][row["name"]]
    if row["doc"]:
        return row["doc"]
    name = row["name"].split(".")[-1]
    if name.startswith("test_"):
        return "行为断言：" + name.removeprefix("test_") + "；成功正常返回，违约抛 AssertionError/pytest 失败"
    if module["path"].startswith(("tests/", "eval/tests/")):
        return "测试场景/夹具/假实现：" + row["name"] + "；输入输出见本项，生产不调用"
    if name == "__init__":
        return "用给定参数与依赖初始化 " + row["name"].removesuffix(".__init__") + "，建立其对象状态；业务归属为" + module["purpose"]
    if module["path"] == "hybrid_memory/service/service.py" and row["kind"] == "function":
        return "服务门面的 " + name + " 入口；转发/状态边界为 " + row["effects"]
    if row["kind"] == "class":
        return "定义 " + row["name"] + " 的数据或接口类型，承载" + module["purpose"] + "；构造字段及继承输出在本项完整登记"
    if row.get("delegate"):
        return "委托 `" + row["delegate"] + "` 执行；边界与失败由被调用方契约承担"
    return module["purpose"] + " 的具名操作；流程见作用行，输入输出见本项签名与返回"


def module_io(path: str):
    if path in MODULE_IO:
        return MODULE_IO[path]
    for prefix in sorted((k for k in MODULE_IO if k.endswith("/")), key=len, reverse=True):
        if path.startswith(prefix):
            return MODULE_IO[prefix]
    return None


def target_path_for(path: str) -> str:
    return TARGET_PATHS.get(path, path)


def symbol_contract(row: dict, module: dict) -> tuple[str, str, str, str, str]:
    key = module["path"] + "::" + row["name"]
    parts = SYMBOL_OVERRIDES.get(key)
    if parts is None:
        return (symbol_purpose(row, module), row["input"], row["output"],
                row["effects"], row["errors"].lstrip("；"))
    pick = lambda idx, fallback: parts[idx] if len(parts) > idx and parts[idx] else fallback  # noqa: E731
    return (parts[0], pick(1, row["input"]), pick(2, row["output"]),
            pick(3, row["effects"]), pick(4, row["errors"].lstrip("；")))


def render(modules: list[dict]) -> str:
    count = sum(len(m["symbols"]) for m in modules)
    lines = ["# 架构源符号登记与逐符号目标契约（唯一目标架构附录）", "",
             "> 基线：db26787；唯一目标设计见 [target-architecture](../analysis/target-architecture.md)。",
             "> 本页是设计文档的组成部分，不是自动批准保留：源码里出现但未在本页登记的符号=覆盖检查失败；",
             "> 未在本页出现的函数/模块在下一轮统一删除前，必须先在此登记或列入删除项。",
             "> 生成命令：`python analysis/check_architecture.py --build-inventory`；核对：同命令不带参数。",
             "> 固定契约数据（目标路径、显式契约、计划新增、删除条件、模块备注）在 `analysis/architecture_contract.py`。",
             f"> 当前登记 {sum(m['path'].endswith('.py') for m in modules)} 个 Python 模块、"
             f"{sum(not m['path'].endswith('.py') for m in modules)} 个 TS/角色定义模块、"
             f"{count} 个显式类/函数/具名回调（含私有、嵌套、测试、评测），"
             f"{len(PLANNED_MODULES)} 个计划新增模块、{len(PLANNED_SYMBOLS)} 个计划新增符号、{len(DELETIONS)} 个删除项。",
             "",
             "每符号给出：功能、输入、输出、作用、错误、目标（目标路径/处置/变更）。",
             "公开产品符号在固定契约里逐条定义目标；私有 helper 与测试符号由模块契约+语法签名合成，仍必须完整给出上述字段。",
             "匿名 lambda/回调属于其具名父函数；dataclass/Enum/TypedDict 隐式方法由类型契约覆盖，不单独删除。",
             "TS 的具名 arrow、hook、tool 与测试回调及三份角色定义也登记；TS 识别是当前语法的有限静态扫描，不冒充完整 TypeScript 解析器。",
             "vendored `mvp/agent/` 完全排除。", ""]
    for module in modules:
        io = module_io(module["path"])
        tpath = target_path_for(module["path"])
        lines += [f"## `{module['path']}`", "",
                  f"- 模块功能：{module['purpose']}。",
                  f"- 设计归属：{module['owner']}；处置：{module['disposition']}。",
                  f"- 目标路径：`{tpath}`" + ("（当前路径）" if tpath == module["path"] else "（模块迁移）") + "。",
                  f"- 模块输入：{io[0]}。" if io else "- 模块输入：缺失契约（检查失败）。",
                  f"- 模块输出：{io[1]}。" if io else "- 模块输出：缺失契约（检查失败）。",
                  f"- 源校验：`{module['sha256']}`。"]
        if module["path"] in MODULE_NOTES:
            lines.append("- 模块备注：" + MODULE_NOTES[module["path"]])
        if not module["symbols"] and not module["path"].endswith(".py"):
            lines.append("- 输入/输出：角色模块接收封存 JSON 并规定 role 输出；无源码函数。")
        elif not module["symbols"]:
            lines.append("- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。")
        if module["path"].startswith(("hybrid_memory/agent/", "hybrid_memory/candgen/")) or not module["symbols"] or not module["path"].endswith(".py"):
            lines.append("- 导出/输入依赖：" + clean("；".join(module["exports"]), 5000))
        for row in module["symbols"]:
            key = module["path"] + "::" + row["name"]
            func, ins, outs, fx, err = symbol_contract(row, module)
            if key in DELETIONS:
                disp, reason = DELETIONS[key]
                change = "删除条件：" + reason
            else:
                disp = module["disposition"]
                change = "按本项目标契约实施" if key in SYMBOL_OVERRIDES else "保留当前签名与 IO"
            lines += ["", f"### `{key}`", "",
                      f"- 功能：{func}", f"- 输入：`{ins}`。",
                      f"- 输出：`{outs}`。", f"- 作用：{fx}。",
                      f"- 错误：{err}。",
                      f"- 目标：`{tpath}`；处置：{disp}；变更：{change}；"
                      f"[源码](../{module['path']}#L{row['line']})。"]
        lines.append("")
    lines += ["## 计划新增模块（当前源码不存在；实施后并入上方模块章节）", ""]
    for path, note in PLANNED_MODULES:
        lines += [f"**`{path}`**", "", f"- 功能：{note}",
                  f"- 目标：`{path}`；处置：计划新增；变更：实施后迁入模块章节。", ""]
    lines += ["## 计划新增符号（当前源码不存在；实施后并入对应模块章节）", ""]
    for mod, name, func, ins, outs, fx, err in PLANNED_SYMBOLS:
        lines += ["", f"### `{mod}::{name}`", "",
                  f"- 功能：{func}", f"- 输入：`{ins}`。",
                  f"- 输出：`{outs}`。", f"- 作用：{fx}。", f"- 错误：{err}。",
                  f"- 目标：`{mod}`；处置：计划新增；变更：实施后移入模块章节。", ""]
    return "\n".join(lines)


def check(modules: list[dict], root: Path = ROOT) -> list[str]:
    problems = []
    if not INDEX.is_file() or not DESIGN.is_file():
        return ["analysis/target-architecture.md 或 docs/architecture-inventory.md 缺失"]
    text = INDEX.read_text(encoding="utf-8")
    listed_modules = re.findall(r"^## `([^`]+)`$", text, re.M)
    listed_modules += re.findall(r"^\*\*`([^`]+)`\*\*$", text, re.M)
    listed_symbols = re.findall(r"^### `([^`]+::[^`]+)`$", text, re.M)
    wanted_modules = {m["path"] for m in modules}
    source_symbols = {m["path"] + "::" + s["name"] for m in modules for s in m["symbols"]}
    planned_symbols = {mod + "::" + name for mod, name, *_ in PLANNED_SYMBOLS}
    planned_modules = {path for path, _ in PLANNED_MODULES}
    if len(listed_modules) != len(set(listed_modules)) or len(listed_symbols) != len(set(listed_symbols)):
        problems.append("登记存在重复模块或符号")
    for label, want, have in (("模块", wanted_modules | planned_modules, set(listed_modules)),
                              ("符号", source_symbols | planned_symbols, set(listed_symbols))):
        problems += [f"漏登{label}: {n}" for n in sorted(want - have)]
        problems += [f"失效{label}: {n}" for n in sorted(have - want)]
    for module in modules:
        if module_io(module["path"]) is None:
            problems.append("模块缺少输入/输出契约: " + module["path"])
        if f"`{module['sha256']}`" not in text:
            problems.append(f"源已变化须复核登记: {module['path']}")
    for block in re.split(r"(?=^### `)", text, flags=re.M)[1:]:
        if "::" not in block.splitlines()[0]:
            continue
        if not all(f"- {field}：" in block for field in ("功能", "输入", "输出", "作用", "错误", "目标")):
            problems.append("符号契约字段不齐: " + block.splitlines()[0])
    for module in modules:
        if not module["path"].startswith("hybrid_memory/"):
            continue
        for row in module["symbols"]:
            name = row["name"].split(".")[-1]
            key = module["path"] + "::" + row["name"]
            if name.startswith("_") or name.startswith("test_") or name == "__init__":
                continue
            if key in SYMBOL_OVERRIDES or row.get("doc") or row.get("delegate"):
                continue
            problems.append("公开符号缺少显式契约（override/docstring/delegate）: " + key)
    for key, (_disp, reason) in DELETIONS.items():
        if key not in source_symbols:
            problems.append("删除项在源码中不存在（失效）: " + key)
        if not reason:
            problems.append("删除项缺少条件说明: " + key)
    for key in SYMBOL_OVERRIDES:
        if key not in source_symbols:
            problems.append("显式契约指向不存在符号: " + key)
    for src, dst in TARGET_PATHS.items():
        if src not in wanted_modules:
            problems.append("迁移源模块不存在: " + src)
        if dst in wanted_modules:
            problems.append("迁移目标已是现存模块，需合并契约: " + dst)
    for key in MODULE_NOTES:
        if key not in wanted_modules:
            problems.append("模块备注指向不存在模块: " + key)
    design_text = DESIGN.read_text(encoding="utf-8")
    for path, _note in PLANNED_MODULES:
        if path in wanted_modules:
            problems.append("计划新增模块已存在: " + path)
        if Path(path).name not in design_text:
            problems.append("计划新增模块未在主文出现: " + path)
    for mod, name, *_rest in PLANNED_SYMBOLS:
        if mod + "::" + name in source_symbols:
            problems.append("计划新增符号已存在于源码: " + mod + "::" + name)
        ascii_name = re.search(r"[A-Za-z_][A-Za-z0-9_.]*", name)
        if ascii_name and ascii_name.group(0).split(".")[-1] not in design_text:
            problems.append("计划新增符号未在主文出现: " + name)
    for bad in ("目标约束见主文对应责任家", "具体职责和权限见唯一目标 §5.1", "见主文对应责任家"):
        if bad in text:
            problems.append("附录仍含占位说明: " + bad)
    for file in (DESIGN, INDEX):
        body = file.read_text(encoding="utf-8")
        for link in re.findall(r"\]\(([^)]+)\)", body):
            if re.match(r"[a-zA-Z]+://", link) or link.startswith("#"):
                continue
            target = link.split("#", 1)[0]
            if target and not (file.parent / target).exists():
                try:
                    shown = file.relative_to(root)
                except ValueError:
                    shown = file
                problems.append(f"链接失效: {shown} -> {link}")
    for section in ("信号与派发", "三 Agent 协议", "三池与领域", "迁移与删除决策", "验收"):
        if section not in design_text:
            problems.append(f"主设计缺主题: {section}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-inventory", action="store_true")
    ap.add_argument("--inventory-json", action="store_true")
    args = ap.parse_args()
    modules = inventory()
    if args.inventory_json:
        print(json.dumps(modules, ensure_ascii=False, indent=1))
        return 0
    if args.build_inventory:
        INDEX.write_text(render(modules), encoding="utf-8")
    problems = check(modules)
    for problem in problems:
        print("FAIL " + problem)
    print(f"architecture coverage: modules={len(modules)} "
          f"symbols={sum(len(m['symbols']) for m in modules)} failures={len(problems)}")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
