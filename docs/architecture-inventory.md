# 架构源符号登记与逐符号目标契约（唯一目标架构附录）

> 基线：db26787；唯一目标设计见 [target-architecture](../analysis/target-architecture.md)。
> 本页是设计文档的组成部分，不是自动批准保留：源码里出现但未在本页登记的符号=覆盖检查失败；
> 未在本页出现的函数/模块在下一轮统一删除前，必须先在此登记或列入删除项。
> 生成命令：`python analysis/check_architecture.py --build-inventory`；核对：同命令不带参数。
> 固定契约数据（目标路径、显式契约、计划新增、删除条件、模块备注）在 `analysis/architecture_contract.py`。
> 当前登记 140 个 Python 模块、5 个 TS/角色定义模块、1359 个显式类/函数/具名回调（含私有、嵌套、测试、评测），0 个计划新增模块、0 个计划新增符号、3 个删除项。

每符号给出：功能、输入、输出、作用、错误、目标（目标路径/处置/变更）。
公开产品符号在固定契约里逐条定义目标；私有 helper 与测试符号由模块契约+语法签名合成，仍必须完整给出上述字段。
匿名 lambda/回调属于其具名父函数；dataclass/Enum/TypedDict 隐式方法由类型契约覆盖，不单独删除。
TS 的具名 arrow、hook、tool 与测试回调及三份角色定义也登记；TS 识别是当前语法的有限静态扫描，不冒充完整 TypeScript 解析器。
vendored `mvp/agent/` 完全排除。

## `analysis/acceptance_check.py`

- 模块功能：设计登记、验收及符号覆盖工具；不参与产品效果。
- 设计归属：验收资产；处置：保留。
- 目标路径：`analysis/acceptance_check.py`（当前路径）。
- 模块输入：源文件与设计契约数据。
- 模块输出：符号覆盖、验收与目标契约结论。
- 源校验：`15b32935e9c01d584d30a5a0549b2b53c1e805cc1ca2865a736425b7bb69bce7`。

### `analysis/acceptance_check.py::report`

- 功能：追加并打印一条 PASS/FAIL/PENDING/SKIP 验收记录
- 输入：`cid: str, verdict: str, detail: str=''`。
- 输出：`None；None`。
- 作用：调用 print, results.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L47)。

### `analysis/acceptance_check.py::run`

- 功能：按受控 cwd/env/timeout 执行验证子进程并捕获结果
- 输入：`cmd: list[str], cwd: Path | None=None, env: dict | None=None, timeout: int=600`。
- 输出：`subprocess.CompletedProcess；subprocess.run(cmd, cwd=str(cwd or ROOT), env=env, capture_output=True, text=True, timeout=timeout)`。
- 作用：调用 str, subprocess.run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L53)。

### `analysis/acceptance_check.py::pytest_run`

- 功能：运行指定 pytest 节点，关闭缓存写入并限制执行时间
- 输入：`nodes: list[str], timeout: int=300`。
- 输出：`subprocess.CompletedProcess；run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--tb=short'] + nodes, timeout=timeout)`。
- 作用：调用 run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L59)。

### `analysis/acceptance_check.py::detect_phase`

- 功能：按文件存在识别历史迁移阶段，不证明阶段契约都已实现
- 输入：`无参数`。
- 输出：`str；'P0'；'P1'；'P2'；'P3'；'P4'；'P5'；'P6'`。
- 作用：调用 (ROOT / 'tests' / 'characterization').is_dir, (h / 'agents' / 'opencode.py').is_file, (h / 'errors.py').is_file, (h / 'legacy').is_dir, (h / 'transport' / 'http.py').is_file, any, svc.is_dir, svc.iterdir。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L64)。

### `analysis/acceptance_check.py::check_a1`

- 功能：执行 Python/Bun 测试门并登记结果
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 '\n'.join, (out.stdout + out.stderr).strip, (out.stdout + out.stderr).strip().splitlines, pytest_run, report, run, shutil.which。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L87)。

### `analysis/acceptance_check.py::check_a2`

- 功能：验证手工产品断言与对应测试节点的证据链
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 (ROOT / doc).read_text, len, pytest_run, report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L126)。

### `analysis/acceptance_check.py::check_a3`

- 功能：生成临时 TIDE 数据、元评测和可选 mock bench 烟囱
- 输入：`full: bool`。
- 输出：`None；None`。
- 作用：调用 Path, dm[0].strip, mock.terminate, mock.wait, out.stdout.strip, out.stdout.strip().splitlines, rep.exists, rep.read_text, rep.read_text(encoding='utf-8').splitlines, report, run, shutil.rmtree, str, subprocess.Popen, tempfile.mkdtemp, time.sleep, time.time, urllib.request.urlopen, urllib.request.urlopen('http://127.0.0.1:18080/stats', timeout=2).read。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L143)。

### `analysis/acceptance_check.py::check_a4`

- 功能：执行任务状态机 characterization 快照回归
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 d.is_dir, out.stdout.strip, out.stdout.strip().splitlines, pytest_run, report, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L203)。

### `analysis/acceptance_check.py::check_a5`

- 功能：执行静态 import 边界回归
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 f.is_file, out.stdout.strip, out.stdout.strip().splitlines, pytest_run, report, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L213)。

### `analysis/acceptance_check.py::check_a6`

- 功能：调用当前消费者注册自检并记录结果
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 eff.is_file, len, pol.is_file, policy.assert_consumers, report, str, sys.path.insert, sys.path.remove, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L223)。

### `analysis/acceptance_check.py::_snapshot_tree`

- 功能：将响应树规范成字段、类型和有限示例结构
- 输入：`obj, depth: int=0`。
- 输出：`未注解；[_snapshot_tree(x, depth + 1) for x in obj[:3]]；type(obj).__name__；{k: _snapshot_tree(v, depth + 1) for k, v in sorted(obj.items())} if depth < 2 else sorted(obj)`。
- 作用：调用 _snapshot_tree, isinstance, obj.items, sorted, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L243)。

### `analysis/acceptance_check.py::capture_contracts`

- 功能：用 fake 服务和真实本地 HTTP 采集健康、信号和错误契约
- 输入：`无参数`。
- 输出：`dict；{'health': {'fields': _snapshot_tree(health), 'literals': {'validation': health.get('validation')}}, 'signals': {'fields': _snapshot_tree(signals)}, 'status_table': table}`。
- 作用：调用 _http, _service, _snapshot_tree, conn.close, conn.endheaders, conn.getresponse, conn.putheader, conn.putrequest, dict, get, health.get, http.client.HTTPConnection, post, post2, str, svc.health_view, svc.observe, svc.recall, svc.report_miss, svc.signals, sys.path.insert, sys.path.remove, urllib.request.urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L252)。

### `analysis/acceptance_check.py::check_a7`

- 功能：比较响应快照；显式 freeze 模式才写新快照
- 输入：`freeze: bool`。
- 输出：`None；None`。
- 作用：调用 (SNAP_DIR / name).write_text, SNAP_DIR.mkdir, capture_contracts, json.dumps, json.loads, p.is_file, p.read_text, report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L313)。

### `analysis/acceptance_check.py::check_a8`

- 功能：核对错误状态并 fuzz 最终 Agent JSON 对象解析
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 ag.is_file, json.loads, len, oc.OpenCodeRunner._parse_text, p.is_file, p.read_text, pytest_run, report, str, sys.path.insert, sys.path.remove, table.items, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L340)。

### `analysis/acceptance_check.py::_ast_literal_in`

- 功能：查目标函数中是否出现指定常量，只是机械形状检查
- 输入：`path: Path, func: str, value: int`。
- 输出：`bool；False；any((isinstance(n, ast.Constant) and n.value == value for n in ast.walk(node)))`。
- 作用：调用 any, ast.parse, ast.walk, isinstance, path.read_text。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L382)。

### `analysis/acceptance_check.py::_find_trio_memories_file`

- 功能：定位当前或旧树的记忆快照构造函数
- 输入：`无参数`。
- 输出：`tuple[Path | None, str]；(None, '_memories')；(p, '_memories')；(p, 'memory_snapshot')`。
- 作用：调用 p.is_file, p.read_text。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L391)。

### `analysis/acceptance_check.py::_find_tasks_file`

- 功能：定位当前 Store 或旧 TaskStore 实现路径
- 输入：`无参数`。
- 输出：`Path；p if p.is_file() else ROOT / 'hybrid_memory' / 'taskstore.py'`。
- 作用：调用 p.is_file。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L405)。

### `analysis/acceptance_check.py::check_a9`

- 功能：检查当前容量常量、字段与有限行为证据，非完整容量证明
- 输入：`phase: str`。
- 输出：`None；None`。
- 作用：调用 (ROOT / 'hybrid_memory' / 'agents').is_dir, (ROOT / 'hybrid_memory').rglob, _ast_literal_in, _find_tasks_file, _find_tasks_file().read_text, _find_trio_memories_file, any, due, hasattr, inspect.signature, isinstance, p.read_text, pytest_run, report, rows.append, str, sys.path.insert, sys.path.remove, trio_file.is_file, trio_file.read_text。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L410)。

### `analysis/acceptance_check.py::check_a9.due`

- 功能：判断某容量检查项是否到历史阶段的准出时点
- 输入：`p: str`。
- 输出：`bool；order.index(phase) >= order.index(p)`。
- 作用：调用 order.index。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L414)。

### `analysis/acceptance_check.py::check_a10`

- 功能：执行逐单元、语义及调查任务恢复测试
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 new.is_file, out.stdout.strip, out.stdout.strip().splitlines, pytest_run, report, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L465)。

### `analysis/acceptance_check.py::check_pending`

- 功能：逐项打印延期能力并检查基线白名单一致性
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 (ROOT / 'analysis' / 'acceptance-criteria.md').read_text, print, report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L480)。

### `analysis/acceptance_check.py::main`

- 功能：组合旧验收门、打印汇总，以 FAIL 数决定退出码
- 输入：`无参数`。
- 输出：`int；1 if fails else 0`。
- 作用：调用 ap.add_argument, ap.parse_args, argparse.ArgumentParser, check_a1, check_a10, check_a2, check_a3, check_a4, check_a5, check_a6, check_a7, check_a8, check_a9, check_pending, detect_phase, len, print, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/acceptance_check.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/acceptance_check.py#L490)。

## `analysis/architecture_contract.py`

- 模块功能：设计登记、验收及符号覆盖工具；不参与产品效果。
- 设计归属：验收资产；处置：保留。
- 目标路径：`analysis/architecture_contract.py`（当前路径）。
- 模块输入：源码语法树与人工冻结的契约数据。
- 模块输出：无运行逻辑；供检查器渲染逐符号目标与执行覆盖校验。
- 源校验：`7640fcf4bf450995971f463d9f999446ba994a54909b17e2e967eef85dce7e11`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：annotations ← __future__.annotations

## `analysis/check_architecture.py`

- 模块功能：设计登记、验收及符号覆盖工具；不参与产品效果。
- 设计归属：验收资产；处置：保留。
- 目标路径：`analysis/check_architecture.py`（当前路径）。
- 模块输入：源文件与设计契约数据。
- 模块输出：符号覆盖、验收与目标契约结论。
- 源校验：`1ae6fb6ea0d16fb041c0012501406bfc36685ebdba203a942e8b0abde5efb633`。

### `analysis/check_architecture.py::source_paths`

- 功能：收集已追踪与新增自有 Python 源路径，排除 vendored agent 和缓存
- 输入：`root: Path=ROOT`。
- 输出：`list[Path]；[root / n for n in sorted(names) if not n.startswith('agent/') and (root / n).is_file()]`。
- 作用：调用 (root / directory).rglob, (root / n).is_file, n.startswith, names.add, names.update, out.split, p.decode, p.relative_to, p.relative_to(root).as_posix, sorted, str, subprocess.run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L68)。

### `analysis/check_architecture.py::module_policy`

- 功能：按已登记文件或责任目录取得处置、功能和归属，未知范围拒绝
- 输入：`path: str`。
- 输出：`tuple[str, str, str]；MODULES[path]；MODULES[prefix]`。
- 作用：调用 ValueError, k.endswith, path.startswith, sorted。
- 错误：异常 ValueError(f'unregistered module: {path}')。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L80)。

### `analysis/check_architecture.py::direct_nodes`

- 功能：遍历当前函数节点，排除子函数/类/lambda 的内部行为
- 输入：`node: ast.AST`。
- 输出：`未注解；生成器/上下文管理器`。
- 作用：调用 ast.iter_child_nodes, direct_nodes, isinstance。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L90)。

### `analysis/check_architecture.py::clean`

- 功能：规整登记中的空白与反引号，并按显示字段限制长度
- 输入：`text: str, limit: int=300`。
- 输出：`str；text if len(text) <= limit else text[:limit] + '…'`。
- 作用：调用 ' '.join, ' '.join(text.split()).replace, len, text.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L98)。

### `analysis/check_architecture.py::function_io`

- 功能：提取精确参数、注解、返回/生成器、调用与显式错误；区别协议和空壳
- 输入：`node: ast.FunctionDef | ast.AsyncFunctionDef`。
- 输出：`未注解；(clean(inputs, 20000), output, clean(effects, 20000), clean(errors, 20000), delegate)`。
- 作用：调用 ', '.join, '；'.join, any, ast.unparse, clean, direct_nodes, isinstance, len, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L103)。

### `analysis/check_architecture.py::definitions`

- 功能：枚举全部具名类、方法及 nested 函数并建立作用域全名
- 输入：`tree: ast.AST`。
- 输出：`list[dict]；rows`。
- 作用：调用 visit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L135)。

### `analysis/check_architecture.py::definitions.visit`

- 功能：递归维护类/函数作用域，将每个定义加入源登记
- 输入：`node: ast.AST, scope: tuple[str, ...]`。
- 输出：`未注解；None`。
- 作用：调用 ', '.join, '.'.join, '；'.join, ast.get_docstring, ast.iter_child_nodes, ast.unparse, clean, function_io, isinstance, rows.append, visit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L138)。

### `analysis/check_architecture.py::exports`

- 功能：提取 import/re-export 与 __all__，保留 shim 的对象来源
- 输入：`tree: ast.Module`。
- 输出：`list[str]；values`。
- 作用：调用 any, ast.unparse, isinstance, values.append, values.extend。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L165)。

### `analysis/check_architecture.py::inventory`

- 功能：为每个源码模块构造责任、源 hash 和符号输入输出记录
- 输入：`root: Path=ROOT`。
- 输出：`list[dict]；modules + auxiliary_inventory(root)`。
- 作用：调用 ast.parse, auxiliary_inventory, definitions, exports, hashlib.sha256, hashlib.sha256(text.encode('utf-8')).hexdigest, module_policy, modules.append, path.read_text, path.relative_to, path.relative_to(root).as_posix, source_paths, text.encode。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L177)。

### `analysis/check_architecture.py::parameter_end`

- 功能：按引号、转义和括号深度定位 TS 参数边界
- 输入：`text: str, start: int`。
- 输出：`int | None；None；pos`。
- 作用：调用 len, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L190)。

### `analysis/check_architecture.py::ts_definitions`

- 功能：有限扫描当前 TS 具名 arrow、hook、tool 和测试回调，不假装完整编译器
- 输入：`text: str, path: str`。
- 输出：`list[dict]；rows`。
- 作用：调用 clean, match.end, match.group, match.start, outputs.get, parameter_end, path.startswith, pattern.finditer, re.compile, re.finditer, re.match, re.search, rows.append, text.count, text.index。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L212)。

### `analysis/check_architecture.py::auxiliary_inventory`

- 功能：为插件、TS 回归和三份 Agent 定义建立源登记
- 输入：`root: Path=ROOT`。
- 输出：`list[dict]；modules`。
- 作用：调用 (root / path).read_text, hashlib.sha256, hashlib.sha256(text.encode('utf-8')).hexdigest, modules.append, path.endswith, path.startswith, text.encode, ts_definitions。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L308)。

### `analysis/check_architecture.py::symbol_purpose`

- 功能：用明确语义、现状 docstring 或测试场景生成符号说明
- 输入：`row: dict, module: dict`。
- 输出：`str；'委托 '' + row['delegate'] + '' 执行；边界与失败由被调用方契约承担'；'定义 ' + row['name'] + ' 的数据或接口类型，承载' + module['purpose'] + '；构造字段及继承输出在本项完整登记'；'服务门面的 ' + name + ' 入口；转发/状态边界为 ' + row['effects']；'测试场景/夹具/假实现：' + row['name'] + '；输入输出见本项，生产不调用'；'用给定参数与依赖初始化 ' + row['name'].removesuffix('.__init__') + '，建立其对象状态；业务归属为' + module['purpose']；'行为断言：' + name.removeprefix('test_') + '；成功正常返回，违约抛 AssertionError/pytest 失败'；module['purpose'] + ' 的具名操作；流程见作用行，输入输出见本项签名与返回'；row['doc']；summaries[module['path']][row['name']]`。
- 作用：调用 module['path'].startswith, name.removeprefix, name.startswith, row.get, row['name'].removesuffix, row['name'].split, summaries.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L325)。

### `analysis/check_architecture.py::module_io`

- 功能：设计登记、验收及符号覆盖工具；不参与产品效果 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`path: str`。
- 输出：`未注解；MODULE_IO[path]；MODULE_IO[prefix]；None`。
- 作用：调用 k.endswith, path.startswith, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L459)。

### `analysis/check_architecture.py::target_path_for`

- 功能：委托 `TARGET_PATHS.get` 执行；边界与失败由被调用方契约承担
- 输入：`path: str`。
- 输出：`str；TARGET_PATHS.get(path, path)`。
- 作用：调用 TARGET_PATHS.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L468)。

### `analysis/check_architecture.py::symbol_contract`

- 功能：设计登记、验收及符号覆盖工具；不参与产品效果 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`row: dict, module: dict`。
- 输出：`tuple[str, str, str, str, str]；(parts[0], pick(1, row['input']), pick(2, row['output']), pick(3, row['effects']), pick(4, row['errors'].lstrip('；')))；(symbol_purpose(row, module), row['input'], row['output'], row['effects'], row['errors'].lstrip('；'))`。
- 作用：调用 SYMBOL_OVERRIDES.get, pick, row['errors'].lstrip, symbol_purpose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L472)。

### `analysis/check_architecture.py::render`

- 功能：生成唯一目标文档的源符号附录，不自动批准新增函数保留
- 输入：`modules: list[dict]`。
- 输出：`str；'\n'.join(lines)`。
- 作用：调用 '\n'.join, '；'.join, clean, len, lines.append, m['path'].endswith, module['path'].endswith, module['path'].startswith, module_io, sum, symbol_contract, target_path_for。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L483)。

### `analysis/check_architecture.py::check`

- 功能：校验模块/符号覆盖、重复、输入输出字段、源漂移和文档链接
- 输入：`modules: list[dict], root: Path=ROOT`。
- 输出：`list[str]；['analysis/target-architecture.md 或 docs/architecture-inventory.md 缺失']；problems`。
- 作用：调用 (file.parent / target).exists, DELETIONS.items, DESIGN.is_file, DESIGN.read_text, INDEX.is_file, INDEX.read_text, Path, TARGET_PATHS.items, all, ascii_name.group, ascii_name.group(0).split, block.splitlines, file.read_text, file.relative_to, len, link.split, link.startswith, module['path'].startswith, module_io, name.startswith, problems.append, re.findall, re.match, re.search, re.split, row.get, row['name'].split, set, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L548)。

### `analysis/check_architecture.py::main`

- 功能：显式构建附录或执行只读校验，按问题列表设置退出码
- 输入：`无参数`。
- 输出：`int；0；int(bool(problems))`。
- 作用：调用 INDEX.write_text, ap.add_argument, ap.parse_args, argparse.ArgumentParser, bool, check, int, inventory, json.dumps, len, print, render, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`analysis/check_architecture.py`；处置：保留；变更：保留当前签名与 IO；[源码](../analysis/check_architecture.py#L636)。

## `eval/checks/aggcheck_conflict.py`

- 模块功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口。
- 设计归属：评测边界；处置：历史归档。
- 目标路径：`eval/checks/aggcheck_conflict.py`（当前路径）。
- 模块输入：历史输入。
- 模块输出：只作归档证据；不得作为现行入口。
- 源校验：`0f874e62c081bfc24ba1def4e13bfe61e82817c6fa0449a98e422edd6dfa7665`。
- 模块备注：历史归档：依赖已删除的 experiments/synthetic/sim；不得作为现行入口。

### `eval/checks/aggcheck_conflict.py::run`

- 功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name, seed`。
- 输出：`未注解；(n, hit_orig, hit_agg, agg_seen)`。
- 作用：调用 MemoryEngine, SignalWorker, StreamGen, SyntheticEmbedder, any, emb.embed, eng.observe, eng.retrieve, eng.step, ok, range, worker.process, world.embedding_key, world.phase, world.step。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/checks/aggcheck_conflict.py`；处置：历史归档；变更：保留当前签名与 IO；[源码](../eval/checks/aggcheck_conflict.py#L9)。

### `eval/checks/aggcheck_conflict.py::run.ok`

- 功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`m`。
- 输出：`未注解；False；True；any((world.relevant(eng.mems[i].belief_id, eng.mems[i].value, q, t) for i in m.agg_members if i in eng.mems))`。
- 作用：调用 any, world.relevant。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/checks/aggcheck_conflict.py`；处置：历史归档；变更：保留当前签名与 IO；[源码](../eval/checks/aggcheck_conflict.py#L21)。

## `eval/checks/rescore_aggregate.py`

- 模块功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口。
- 设计归属：评测边界；处置：历史归档。
- 目标路径：`eval/checks/rescore_aggregate.py`（当前路径）。
- 模块输入：历史输入。
- 模块输出：只作归档证据；不得作为现行入口。
- 源校验：`7e72dd070ada347f3579f1286515683ed179a5f4d82a959908551ce011fc0ab2`。
- 模块备注：历史归档：同上，删除前先迁引用。

### `eval/checks/rescore_aggregate.py::run`

- 功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name, seed, acc`。
- 输出：`未注解；None`。
- 作用：调用 MemoryEngine, SignalWorker, StreamGen, SyntheticEmbedder, any, emb.embed, eng.observe, eng.retrieve, eng.step, ok, range, worker.process, world.embedding_key, world.phase, world.step。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/checks/rescore_aggregate.py`；处置：历史归档；变更：保留当前签名与 IO；[源码](../eval/checks/rescore_aggregate.py#L8)。

### `eval/checks/rescore_aggregate.py::run.ok`

- 功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`m`。
- 输出：`未注解；True；bool(m.agg_members) and any((world.relevant(eng.mems[i].belief_id, eng.mems[i].value, q, t) for i in m.agg_members if i in eng.mems))`。
- 作用：调用 any, bool, world.relevant。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/checks/rescore_aggregate.py`；处置：历史归档；变更：保留当前签名与 IO；[源码](../eval/checks/rescore_aggregate.py#L16)。

## `eval/checks/stale_in_context.py`

- 模块功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口。
- 设计归属：评测边界；处置：历史归档。
- 目标路径：`eval/checks/stale_in_context.py`（当前路径）。
- 模块输入：历史输入。
- 模块输出：只作归档证据；不得作为现行入口。
- 源校验：`a75dd08c24316ad9a117ee1512c5e25578980ccb848fa06f43831e623ebe9e87`。
- 模块备注：历史归档：同上。

### `eval/checks/stale_in_context.py::run`

- 功能：依赖已移除仿真模块的历史诊断脚本；不得作为现行入口 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name, seed, acc`。
- 输出：`未注解；None`。
- 作用：调用 MemoryEngine, SignalWorker, StreamGen, SyntheticEmbedder, any, b.value.endswith, emb.embed, eng.observe, eng.retrieve, eng.step, len, range, set, worker.process, world.beliefs.values, world.embedding_key, world.step。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/checks/stale_in_context.py`；处置：历史归档；变更：保留当前签名与 IO；[源码](../eval/checks/stale_in_context.py#L8)。

## `eval/drive.py`

- 模块功能：离线 mock、HTTP 驱动及预览 harness。
- 设计归属：评测边界；处置：迁移修复。
- 目标路径：`eval/drive.py`（当前路径）。
- 模块输入：端口、项目目录、mock 端点与模式参数。
- 模块输出：离线驱动/预览/harness 诊断输出；不修改判分真值。
- 源校验：`a620c9e92461205b508ee172691bfc6967c32ee9ef5ffea476b8fccfd10f897c`。

### `eval/drive.py::call`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`method, path, body=None, headers=None`。
- 输出：`未注解；(e.code, json.loads(e.read() or b'{}'))；(r.status, json.loads(r.read()))`。
- 作用：调用 e.read, json.dumps, json.dumps(body).encode, json.loads, r.read, urllib.request.Request, urllib.request.urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/drive.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/drive.py#L19)。

### `eval/drive.py::turn`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`i, user, asst`。
- 输出：`未注解；None`。
- 作用：调用 call, ctx.replace, obs.get, print, rec.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/drive.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/drive.py#L55)。

### `eval/drive.py::main`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 call, enumerate, json.dumps, print, turn, urllib_noauth。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/drive.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/drive.py#L69)。

### `eval/drive.py::urllib_noauth`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`无参数`。
- 输出：`未注解；e.code`。
- 作用：调用 urllib.request.Request, urllib.request.urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/drive.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/drive.py#L102)。

### `eval/drive.py::more`

- 功能：再跑 n 轮，让 tension 老化超过 tension_delay=20 → conflict_pending → judge。
- 输入：`n=12`。
- 输出：`未注解；None`。
- 作用：调用 call, json.dumps, print, range, turn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/drive.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/drive.py#L111)。

## `eval/mock_llm.py`

- 模块功能：离线 mock、HTTP 驱动及预览 harness。
- 设计归属：评测边界；处置：迁移修复。
- 目标路径：`eval/mock_llm.py`（当前路径）。
- 模块输入：端口、项目目录、mock 端点与模式参数。
- 模块输出：离线驱动/预览/harness 诊断输出；不修改判分真值。
- 源校验：`7acaeec67a90053a51a961e9dc34a62132370dfd043ffdd51d563b752df4ba12`。

### `eval/mock_llm.py::_toks`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`text: str`。
- 输出：`list[str]；out`。
- 作用：调用 len, range, re.findall, text.lower。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L32)。

### `eval/mock_llm.py::embed_batch`

- 功能：真实本地中文向量模型 bge-small-zh-v1.5（512 维，补零到 2048，余弦不变）。 装不上 fastembed 时退化为哈希词袋。
- 输入：`texts`。
- 输出：`未注解；[embed(t) for t in texts]；out`。
- 作用：调用 TextEmbedding, _BGE.embed, embed, len, list, np.zeros, out.append, pad.tolist。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L43)。

### `eval/mock_llm.py::embed`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`text: str`。
- 输出：`list[float]；(v / n).tolist()`。
- 作用：调用 (v / n).tolist, _toks, hashlib.md5, hashlib.md5(tok.encode()).hexdigest, int, np.linalg.norm, np.zeros, tok.encode。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L61)。

### `eval/mock_llm.py::candgen`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`user: str`。
- 输出：`str；json.dumps({'scene_name': scene, 'memories': mems[:4]}, ensure_ascii=False)`。
- 作用：调用 _KEY.search, int, json.dumps, len, m.group, mems.append, prev.group, prev.group(1).strip, range, re.search, re.split, s.strip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L78)。

### `eval/mock_llm.py::judge`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`user: str`。
- 输出：`str；'collision'；'synonym'；'update'`。
- 作用：调用 _toks, len, m.group, max, re.findall, re.match, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L99)。

### `eval/mock_llm.py::recognizer`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`user: str`。
- 输出：`str；','.join(hits) or 'NONE'`。
- 作用：调用 ','.join, _toks, ans.group, hits.append, len, re.findall, re.search, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L114)。

### `eval/mock_llm.py::route_chat`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`system: str, user: str`。
- 输出：`tuple[str, str]；('candgen', candgen(user))；('consolidate', 'NONE')；('judge', judge(user))；('other', '（mock 回复）好的，我已了解当前项目状态。')；('recognizer', recognizer(user))`。
- 作用：调用 candgen, judge, recognizer。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L125)。

### `eval/mock_llm.py::investigator_step`

- 功能：脚本化的调查员：真的发 tool_calls，走插件 worker 角色的工具面。 返回 ("tool", name, args) 或 ("text", str)。
- 输入：`body: dict`。
- 输出：`未注解；('text', json.dumps({'proposals': [], 'diagnosis': {'miss_type': 'never_logged', 'note': 'mock: 无命中'}}, ensure_ascii=False))；('text', json.dumps({'proposals': [{'text': f'（调查员核实）{snippet}', 'kind': 'work_fact', 'salience': 0.7, 'source_unit_ids': units[:1]}], 'diagnosis': {'miss_type': 'dropped_by_candgen', 'note': 'mock investigator'}}, ensure_ascii=False))；('tool', 'log_search', {'query': q.group(1) if q else 'cap_m'})；('tool', 'log_window', {'unit_ids': [int(uid.group(1))], 'max_chars': 800})`。
- 作用：调用 _c, body.get, int, json.dumps, last.splitlines, len, m.get, q.group, re.findall, re.search, re.sub, uid.group。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L137)。

### `eval/mock_llm.py::investigator_step._c`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`m`。
- 输出：`未注解；c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)`。
- 作用：调用 isinstance, json.dumps, m.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L143)。

### `eval/mock_llm.py::H`

- 功能：定义 H 的数据或接口类型，承载离线 mock、HTTP 驱动及预览 harness；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 BaseHTTPRequestHandler`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L166)。

### `eval/mock_llm.py::H.log_message`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, *a`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L167)。

### `eval/mock_llm.py::H._json`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, code, obj`。
- 输出：`未注解；None`。
- 作用：调用 json.dumps, json.dumps(obj, ensure_ascii=False).encode, len, self.end_headers, self.send_header, self.send_response, self.wfile.write, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L170)。

### `eval/mock_llm.py::H.do_GET`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；self._json(200, STATS)；self._json(200, {'object': 'list', 'data': [{'id': 'glm-5.3-flash', 'object': 'model'}]})`。
- 作用：调用 self._json, self.path.rstrip, self.path.rstrip('/').endswith, self.path.startswith。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L178)。

### `eval/mock_llm.py::H.do_POST`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None；self._json(200, {'data': [{'index': i, 'embedding': e} for i, e in enumerate(embed_batch(inp))], 'usage': {'prompt_tokens': sum((len(t) for t in inp))}})；self._json(200, {'id': 'x', 'object': 'chat.completion', 'model': body.get('model'), 'choices': [{'index': 0, 'finish_reason': finish, 'message': message}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}})；self._json(401, {'error': 'no auth'})`。
- 作用：调用 '\n'.join, STATS['chat'].get, _txt, body.get, embed_batch, enumerate, ev, f.write, int, investigator_step, isinstance, json.dump, json.dumps, json.loads, len, m.get, open, route_chat, self._json, self.end_headers, self.headers.get, self.headers.get('Authorization', '').startswith, self.path.endswith, self.rfile.read, self.send_header, self.send_response, self.wfile.flush, self.wfile.write, sum, t.get, t.get('function', {}).get, time.time。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L187)。

### `eval/mock_llm.py::H.do_POST._txt`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`c`。
- 输出：`未注解；''.join((p.get('text', '') for p in c if isinstance(p, dict)))；c or ''`。
- 作用：调用 ''.join, isinstance, p.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L204)。

### `eval/mock_llm.py::H.do_POST.ev`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`d`。
- 输出：`未注解；None`。
- 作用：调用 f'data: {json.dumps(d, ensure_ascii=False)}\n\n'.encode, json.dumps, self.wfile.flush, self.wfile.write。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/mock_llm.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/mock_llm.py#L232)。

## `eval/preview_sidecar.py`

- 模块功能：离线 mock、HTTP 驱动及预览 harness。
- 设计归属：评测边界；处置：迁移修复。
- 目标路径：`eval/preview_sidecar.py`（当前路径）。
- 模块输入：端口、项目目录、mock 端点与模式参数。
- 模块输出：离线驱动/预览/harness 诊断输出；不修改判分真值。
- 源校验：`8b941d1a98241a900c1711d9a001bf26c0718ca0a89151fb50ff3ff31368d935`。

### `eval/preview_sidecar.py::_mem_rows`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`service`。
- 输出：`list[dict]；rows`。
- 作用：调用 float, getattr, round, rows.append, service.engine.mems.values, sorted, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L68)。

### `eval/preview_sidecar.py::PreviewHandler`

- 功能：定义 PreviewHandler 的数据或接口类型，承载离线 mock、HTTP 驱动及预览 harness；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 H.Handler`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L79)。

### `eval/preview_sidecar.py::PreviewHandler._send`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, code: int, body: bytes, ctype: str`。
- 输出：`None；None`。
- 作用：调用 len, self.end_headers, self.send_header, self.send_response, self.wfile.write, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L80)。

### `eval/preview_sidecar.py::PreviewHandler._json`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, obj, code: int=200`。
- 输出：`None；None`。
- 作用：调用 json.dumps, json.dumps(obj, ensure_ascii=False, default=str).encode, self._send。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L87)。

### `eval/preview_sidecar.py::PreviewHandler.do_GET`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；self._json(svc.recall(q, None))；self._json({'error': 'q required'}, 400)；self._json({'health': health, 'memories': _mem_rows(svc)})；self._send(200, PAGE.encode(), 'text/html; charset=utf-8')；super().do_GET()`。
- 作用：调用 PAGE.encode, _mem_rows, len, parse_qs, parse_qs(u.query).get, self._json, self._send, super, super().do_GET, svc.engine.pool_sizes, svc.log.count, svc.recall, urlparse。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L91)。

### `eval/preview_sidecar.py::PreviewHandler.do_POST`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；self._json(self.service.observe(user, asst))；self._json({'error': 'empty turn'}, 400)；super().do_POST()`。
- 作用：调用 asst.strip, body.get, int, json.loads, self._json, self.headers.get, self.rfile.read, self.service.observe, super, super().do_POST, urlparse, user.strip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L110)。

### `eval/preview_sidecar.py::main`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 Path, Path(args.project).mkdir, S.ThreadingHTTPServer, S.build_default_service, ap.add_argument, ap.parse_args, argparse.ArgumentParser, httpd.serve_forever, httpd.server_close, len, print, service.log.count, service.save, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/preview_sidecar.py`；处置：迁移修复；变更：保留当前签名与 IO；[源码](../eval/preview_sidecar.py#L122)。

## `eval/run_sidecar_offline.py`

- 模块功能：离线 mock、HTTP 驱动及预览 harness。
- 设计归属：评测边界；处置：迁移修复。
- 目标路径：`eval/run_sidecar_offline.py`（当前路径）。
- 模块输入：端口、项目目录、mock 端点与模式参数。
- 模块输出：离线驱动/预览/harness 诊断输出；不修改判分真值。
- 源校验：`73cb005c0b062f5e955d308b65c428222c9a7f7ae54fecda0138cc74c1a84793`。

### `eval/run_sidecar_offline.py::_Request`

- 功能：离线 mock、HTTP 驱动及预览 harness 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`url, *a, **kw`。
- 输出：`未注解；_OrigRequest(url, *a, **kw)`。
- 作用：调用 _OrigRequest, isinstance, len, url.startswith。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/run_sidecar_offline.py`；处置：迁移后删除；变更：删除条件：旧请求劫持；Settings endpoint 注入接管后移除；[源码](../eval/run_sidecar_offline.py#L24)。

## `eval/tests/test_tide.py`

- 模块功能：TIDE 元评测的测试资产。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tests/test_tide.py`（当前路径）。
- 模块输入：TIDE 资产。
- 模块输出：元评测通过/失败断言；冻结保留。
- 源校验：`d1a14482ef3741c23e6b93f013e38feb38c2a567b5a3836150e2f95c754515c2`。

### `eval/tests/test_tide.py::streams`

- 功能：测试场景/夹具/假实现：streams；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`未注解；generate(seeds=2)`。
- 作用：调用 generate, pytest.fixture。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L15)。

### `eval/tests/test_tide.py::test_deterministic`

- 功能：行为断言：deterministic；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 generate, json.dumps, s.to_json。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L19)。

### `eval/tests/test_tide.py::test_roundtrip`

- 功能：行为断言：roundtrip；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, streams`。
- 输出：`未注解；None`。
- 作用：调用 load_streams, s.to_json, save_streams, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L25)。

### `eval/tests/test_tide.py::test_tokens_unique_and_isolated`

- 功能：行为断言：tokens_unique_and_isolated；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`streams`。
- 输出：`未注解；None`。
- 作用：调用 any, has_token, len, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L31)。

### `eval/tests/test_tide.py::test_text_utils`

- 功能：行为断言：text_utils；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 approx_tokens, has_token, truncate_lines。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L49)。

### `eval/tests/test_tide.py::test_score_and_classify`

- 功能：行为断言：score_and_classify；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`streams`。
- 输出：`未注解；None`。
- 作用：调用 classify_answer, next, score_context。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L57)。

### `eval/tests/test_tide.py::test_anchors`

- 功能：行为断言：anchors；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`streams`。
- 输出：`未注解；None`。
- 作用：调用 BM25, NoMemory, Oracle, Parsed, Recency, aggregate, all, run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L66)。

### `eval/tests/test_tide.py::test_non_passive_replay_equivalent`

- 功能：行为断言：non_passive_replay_equivalent；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`streams`。
- 输出：`未注解；None`。
- 作用：调用 NP, Parsed, run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L78)。

### `eval/tests/test_tide.py::test_non_passive_replay_equivalent.NP`

- 功能：测试场景/夹具/假实现：test_non_passive_replay_equivalent.NP；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Parsed`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L79)。

### `eval/tests/test_tide.py::test_meta_passes`

- 功能：行为断言：meta_passes；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`streams`。
- 输出：`未注解；None`。
- 作用：调用 run_meta。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tests/test_tide.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tests/test_tide.py#L88)。

## `eval/tide/__main__.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/__main__.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`54d3c20d4d5b01d9388e5bcdcd8e5a44be553563e2fb7d5612241716db0529b8`。

### `eval/tide/__main__.py::_streams`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`args`。
- 输出：`未注解；ss`。
- 作用：调用 Path, Path(args.data).exists, args.dims.split, cnt.get, generate, getattr, load_streams, out.append, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L25)。

### `eval/tide/__main__.py::_system`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name, args`。
- 输出：`未注解；DynamicsMemory(args.dm_repo)；Parsed(name[7:])；table[name]()`。
- 作用：调用 DynamicsMemory, Parsed, SystemExit, name.startswith, table[name]。
- 错误：异常 SystemExit('--dm-repo required for dynamics-memory'), SystemExit(f'unknown system {name}')。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L44)。

### `eval/tide/__main__.py::_fmt`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`x, ci=None`。
- 输出：`未注解；'—'；s`。
- 作用：调用 any, isinstance, math.isnan。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L59)。

### `eval/tide/__main__.py::render_report`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`summary: dict`。
- 输出：`str；'\n'.join(out)`。
- 作用：调用 ' | '.join, '\n'.join, _fmt, any, len, max, out.append, sorted, str, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L68)。

### `eval/tide/__main__.py::cmd_gen`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`args`。
- 输出：`未注解；None`。
- 作用：调用 generate, len, print, save_streams, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L104)。

### `eval/tide/__main__.py::cmd_meta`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`args`。
- 输出：`未注解；None`。
- 作用：调用 (Path(args.out) / 'meta.json').write_text, (Path(args.out) / 'meta.md').write_text, Path, Path(args.out).mkdir, SystemExit, _streams, format_meta, json.dumps, print, run_meta。
- 错误：异常 SystemExit(0 if res['pass'] else 1)。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L110)。

### `eval/tide/__main__.py::cmd_bench`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`args`。
- 输出：`未注解；None`。
- 作用：调用 (out / 'report.md').write_text, (out / 'summary.json').write_text, Path, _streams, _system, aggregate, args.budgets.split, args.systems.split, f.write, int, json.dumps, len, names.insert, open, out.mkdir, print, render_report, run, sum, sysm.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L121)。

### `eval/tide/__main__.py::cmd_report`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`args`。
- 输出：`未注解；None`。
- 作用：调用 (Path(args.run) / 'summary.json').read_text, Path, json.loads, print, render_report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L148)。

### `eval/tide/__main__.py::main`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ap.add_subparsers, ap.parse_args, argparse.ArgumentParser, args.fn, b.add_argument, g.add_argument, g.set_defaults, hasattr, p.add_argument, p.set_defaults, r.add_argument, r.set_defaults, sub.add_parser, sub.choices['meta'].add_argument, sys.stdout.reconfigure。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/__main__.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/__main__.py#L153)。

## `eval/tide/adapters/__init__.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/adapters/__init__.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `eval/tide/adapters/dynamics_memory.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/adapters/dynamics_memory.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`8bc36360b4e798bd1d47ac4e83e4b929fe4ef6022307d4f1d95318bff8302e77`。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory`

- 功能：定义 DynamicsMemory 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemorySystem`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L24)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory.__init__`

- 功能：用给定参数与依赖初始化 DynamicsMemory，建立其对象状态；业务归属为独立账本、生成器、判分、基线及 HTTP 适配
- 输入：`self, repo: str, python: str='python', name: str='dynamics-memory', env: dict | None=None, extra_args: list[str] | None=None, timeout: float=120.0`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(repo).resolve, self.env.get, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L27)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory._start`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 Path, RuntimeError, int, m.group, re.search, self._get, self.proc.poll, self.proc.stdout.readline, subprocess.Popen, tempfile.mkdtemp, time.time, tok.read_text, tok.read_text(encoding='utf-8').strip。
- 错误：异常 RuntimeError('sidecar did not announce a port'), RuntimeError(f'sidecar exited rc={self.proc.returncode}')。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L40)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory.close`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 self.proc.kill, self.proc.terminate, self.proc.wait, shutil.rmtree。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L65)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory._get`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, path`。
- 输出：`未注解；json.loads(r.read())`。
- 作用：调用 json.loads, r.read, urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L78)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory._post`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, path, body`。
- 输出：`未注解；json.loads(r.read())`。
- 作用：调用 Request, json.dumps, json.dumps(body).encode, json.loads, r.read, urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L82)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id`。
- 输出：`未注解；None`。
- 作用：调用 self._start, self.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L90)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user, assistant, t`。
- 输出：`未注解；None`。
- 作用：调用 self._post。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L94)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory.serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query, t, budget_tokens, passive=True, probe=None`。
- 输出：`未注解；out.get('context', '')`。
- 作用：调用 bool, out.get, self._post。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L98)。

### `eval/tide/adapters/dynamics_memory.py::DynamicsMemory.cost`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；{'observe_calls': self._calls}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/adapters/dynamics_memory.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/adapters/dynamics_memory.py#L103)。

## `eval/tide/gen_l1.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/gen_l1.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`6da2b3d12d1c4c6effba7fafaa8ae21ec3a77fb5978cb9907ec92046a0545993`。

### `eval/tide/gen_l1.py::_Builder`

- 功能：定义 _Builder 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L32)。

### `eval/tide/gen_l1.py::_Builder.__init__`

- 功能：用给定参数与依赖初始化 _Builder，建立其对象状态；业务归属为独立账本、生成器、判分、基线及 HTTP 适配
- 输入：`self, dim: str, seed: int`。
- 输出：`未注解；None`。
- 作用：调用 DIMENSIONS.index, np.random.default_rng, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L33)。

### `eval/tide/gen_l1.py::_Builder.token`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`str；tok`。
- 作用：调用 ''.join, int, list, range, self._tokens.add, self.rng.choice, self.rng.integers。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L46)。

### `eval/tide/gen_l1.py::_Builder.subject`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, head: str | None=None`。
- 输出：`str；s`。
- 作用：调用 RuntimeError, range, self._subjects.add, self.rng.choice, str。
- 错误：异常 RuntimeError('主体用尽')。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L56)。

### `eval/tide/gen_l1.py::_Builder.fresh_head`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`str；h`。
- 作用：调用 self._heads_used.add, self.rng.choice, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L65)。

### `eval/tide/gen_l1.py::_Builder.fact`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, subj: str, scope: str, val: str, t: int, **kw`。
- 输出：`Fact；f`。
- 作用：调用 Fact, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L71)。

### `eval/tide/gen_l1.py::_Builder.place`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, t_pref: int, utter: tuple[str, str], op: str, facts: list[str]`。
- 输出：`int；t`。
- 作用：调用 RuntimeError, Turn, int, max。
- 错误：异常 RuntimeError(f'{self.id}: 排程溢出（t={t_pref}）')。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L78)。

### `eval/tide/gen_l1.py::_Builder.probe`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, t: int, knob: int, query: str, gold: list, harmful: list, oracle: str, candidates: dict`。
- 输出：`None；None`。
- 作用：调用 Probe, RuntimeError, len, self.probes.append。
- 错误：异常 RuntimeError(f'{self.id}: 探针越界 t={t}')。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L88)。

### `eval/tide/gen_l1.py::_Builder.place_in`

- 功能：在 [lo, hi) 的空位里随机放一轮（干扰项必须落在提问之前）。
- 输入：`self, lo: int, hi: int, utter: tuple[str, str], op: str, facts: list[str]`。
- 输出：`int；t`。
- 作用：调用 RuntimeError, Turn, int, max, min, range, self.rng.choice。
- 错误：异常 RuntimeError(f'{self.id}: [{lo},{hi}) 没有空位')。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L97)。

### `eval/tide/gen_l1.py::_Builder.free_t`

- 功能：[lo, hi) 里随机一个起点（place 会顺延到空位）。
- 输入：`self, lo: int, hi: int`。
- 输出：`int；int(self.rng.integers(lo, max(lo + 1, hi)))`。
- 作用：调用 int, max, self.rng.integers。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L107)。

### `eval/tide/gen_l1.py::_Builder.build`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`Stream；Stream(id=self.id, dimension=self.dim, seed=self.seed, turns=turns, probes=self.probes, facts=list(self.facts.values()))`。
- 作用：调用 Stream, Turn, getattr, getattr(self, f'_build_{self.dim}'), int, len, list, range, self.facts.values, self.probes.sort, self.rng.integers, turns.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L111)。

### `eval/tide/gen_l1.py::_Builder._build_R`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 ask, range, say_set, self.fact, self.free_t, self.place, self.probe, self.subject, self.token。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L125)。

### `eval/tide/gen_l1.py::_Builder._build_V`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 ask, range, say_set, say_update, self.fact, self.free_t, self.place, self.probe, self.subject, self.token。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L137)。

### `eval/tide/gen_l1.py::_Builder._build_P`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 ask, chain.append, range, say_derive, say_set, say_update, self.fact, self.free_t, self.place, self.probe, self.subject, self.token。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L158)。

### `eval/tide/gen_l1.py::_Builder._build_C`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 ask, int, list, range, say_set, self.fact, self.free_t, self.place, self.probe, self.rng.choice, self.rng.integers, self.subject, self.token, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L187)。

### `eval/tide/gen_l1.py::_Builder._build_F`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 ask, range, say_retract, say_set, self.fact, self.free_t, self.place, self.probe, self.subject, self.token。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L206)。

### `eval/tide/gen_l1.py::_Builder._build_I`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 ask, range, say_set, self.fact, self.free_t, self.fresh_head, self.place, self.place_in, self.probe, self.rng.shuffle, self.subject, self.token。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L220)。

### `eval/tide/gen_l1.py::generate`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`seeds: int=5, dims: tuple=DIMENSIONS, seed0: int=0`。
- 输出：`list[Stream]；out`。
- 作用：调用 _Builder, _Builder(dim, s).build, out.append, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/gen_l1.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/gen_l1.py#L245)。

## `eval/tide/ledger.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/ledger.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`af8853630b9be8827633c1980ae99ca54576dd3cbfdd6e1fc0dca3e4233b9dd0`。

### `eval/tide/ledger.py::Fact`

- 功能：定义 Fact 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`id: str；subject: str；scope: str；value: str；t_valid: list；kind: str = 'fact'；supersedes: str | None = None；depends_on: str | None = None；status: str = 'valid'`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L26)。

### `eval/tide/ledger.py::Turn`

- 功能：定义 Turn 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`t: int；user: str；assistant: str；op: str = 'filler'；facts: list = field(default_factory=list)`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L39)。

### `eval/tide/ledger.py::Probe`

- 功能：定义 Probe 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`id: str；t: int；dimension: str；knob: int；query: str；gold: list；harmful: list；oracle_context: str；candidates: dict = field(default_factory=dict)；weight: float = 1.0`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L48)。

### `eval/tide/ledger.py::Stream`

- 功能：定义 Stream 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`id: str；dimension: str；seed: int；turns: list；probes: list；facts: list`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L62)。

### `eval/tide/ledger.py::Stream.to_json`

- 功能：委托 `asdict` 执行；边界与失败由被调用方契约承担
- 输入：`self`。
- 输出：`dict；asdict(self)`。
- 作用：调用 asdict。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L70)。

### `eval/tide/ledger.py::Stream.from_json`

- 功能：委托 `Stream` 执行；边界与失败由被调用方契约承担
- 输入：`d: dict`。
- 输出：`'Stream'；Stream(id=d['id'], dimension=d['dimension'], seed=d['seed'], turns=[Turn(**x) for x in d['turns']], probes=[Probe(**x) for x in d['probes']], facts=[Fact(**x) for x in d['facts']])`。
- 作用：调用 Fact, Probe, Stream, Turn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L74)。

### `eval/tide/ledger.py::save_streams`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`streams: list[Stream], out_dir: str | Path`。
- 输出：`None；None`。
- 作用：调用 (out / f'{s.id}.json').write_text, Path, json.dumps, out.mkdir, s.to_json。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L81)。

### `eval/tide/ledger.py::load_streams`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`data_dir: str | Path`。
- 输出：`list[Stream]；[Stream.from_json(json.loads(f.read_text(encoding='utf-8'))) for f in files]`。
- 作用：调用 FileNotFoundError, Path, Path(data_dir).glob, Stream.from_json, f.read_text, json.loads, sorted。
- 错误：异常 FileNotFoundError(f'{data_dir} 下没有流文件（先跑 python -m tide gen）')。
- 目标：`eval/tide/ledger.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/ledger.py#L89)。

## `eval/tide/meta.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/meta.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`506af778e2c363c93e5d21069a3ee9270ea9bebe7c2fa36f70fc5a712ab6adb3`。

### `eval/tide/meta.py::run_meta`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`streams, budget: int=64`。
- 输出：`dict；{'budget': budget, 'checks': checks, 'matrix': matrix, 'ntu': {k: v['ntu'] for k, v in agg.items()}, 'pass': all((c['pass'] for c in checks))}`。
- 作用：调用 ' → '.join, DOSE.items, NoMemory, Oracle, Parsed, abs, agg.items, aggregate, all, check, round, run, sorted, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/meta.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/meta.py#L35)。

### `eval/tide/meta.py::run_meta.check`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name, ok, detail`。
- 输出：`未注解；None`。
- 作用：调用 bool, checks.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/meta.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/meta.py#L44)。

### `eval/tide/meta.py::format_meta`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`res: dict`。
- 输出：`str；'\n'.join(out) + '\n'`。
- 作用：调用 ' | '.join, '\n'.join, any, cells.append, len, out.append, res['matrix'].items, res['matrix'].values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/meta.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/meta.py#L80)。

## `eval/tide/protocol.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/protocol.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`7f0e570a4d403be41a3f36aedda8e4501090666f91cf24992836dfa10ec54271`。

### `eval/tide/protocol.py::Capabilities`

- 功能：定义 Capabilities 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`passive: bool = True；privileged: bool = False`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L18)。

### `eval/tide/protocol.py::MemorySystem`

- 功能：定义 MemorySystem 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`name: str = 'system'；caps: Capabilities = Capabilities()`。
- 输出：`类型/实例；基类 ABC`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L23)。

### `eval/tide/protocol.py::MemorySystem.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id: str`。
- 输出：`None；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L28)。

### `eval/tide/protocol.py::MemorySystem.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user: str, assistant: str, t: int`。
- 输出：`None；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L31)。

### `eval/tide/protocol.py::MemorySystem.serve`

- 功能：probe 仅在 caps.privileged 时由平台传入。
- 输入：`self, query: str, t: int, budget_tokens: int, passive: bool=True, probe=None`。
- 输出：`str；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L34)。

### `eval/tide/protocol.py::MemorySystem.cost`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`dict；{'llm_calls': 0, 'tokens': 0}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L38)。

### `eval/tide/protocol.py::MemorySystem.close`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/protocol.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/protocol.py#L41)。

## `eval/tide/runner.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/runner.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`cdc1f48972d94be82c0cb6eefdf1661ab5d4b82d10d2ab44a4704b43d619065a`。

### `eval/tide/runner.py::_record`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`system: MemorySystem, stream: Stream, probe, budget: int, raw: str, dt: float`。
- 输出：`dict；rec`。
- 作用：调用 rec.update, round, score_context, truncate_lines。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/runner.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/runner.py#L17)。

### `eval/tide/runner.py::_serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`system, stream, probe, budget`。
- 输出：`未注解；_record(system, stream, probe, budget, raw, time.perf_counter() - t0)`。
- 作用：调用 _record, system.serve, time.perf_counter。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/runner.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/runner.py#L28)。

### `eval/tide/runner.py::run_stream`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`system: MemorySystem, stream: Stream, budgets: list[int]`。
- 输出：`list[dict]；out`。
- 作用：调用 _serve, enumerate, len, sorted, system.ingest, system.reset。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/runner.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/runner.py#L35)。

### `eval/tide/runner.py::run`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`system: MemorySystem, streams: list[Stream], budgets: list[int], progress: bool=False`。
- 输出：`list[dict]；out`。
- 作用：调用 enumerate, len, print, run_stream, time.perf_counter。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/runner.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/runner.py#L56)。

## `eval/tide/score.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/score.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`a1b0b23a35bf528209fca5ef15a9932dbbae5567194b35571865e4ea8165edac`。

### `eval/tide/score.py::score_context`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`context: str, gold: list, harmful: list`。
- 输出：`dict；{'S': s, 'H': h, 'u': s - LAMBDA_H * h}`。
- 作用：调用 any, has_token, len, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/score.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/score.py#L22)。

### `eval/tide/score.py::classify_answer`

- 功能：回答层第 1 级：字符串映射到账本候选。命中多个类别时取最差（有害优先）； 都没命中：金值为空 → abstain-ok 候选由调用方二次判定，否则 OTHER（交 LLM/人工）。
- 输入：`answer: str, probe`。
- 输出：`str；'OTHER'；cls`。
- 作用：调用 has_token, len, probe.candidates.items。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/score.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/score.py#L28)。

### `eval/tide/score.py::_ntu`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`us, un, uo`。
- 输出：`未注解；(us - un) / den if abs(den) > 1e-09 else float('nan')`。
- 作用：调用 abs, float。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/score.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/score.py#L42)。

### `eval/tide/score.py::aggregate`

- 功能：records：同一数据集、同一预算下 system / none / oracle 三者的探针记录。
- 输入：`records: list[dict], system: str, budget: int, n_boot: int=1000, seed: int=0`。
- 输出：`dict；out；{}`。
- 作用：调用 boot, by.values, defaultdict, enumerate, float, int, knobs.items, knobs[v[system]['knob']].append, len, np.mean, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/score.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/score.py#L47)。

### `eval/tide/score.py::aggregate.arrays`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`sel`。
- 输出：`未注解；(us, un, uo, st)`。
- 作用：调用 np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/score.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/score.py#L61)。

### `eval/tide/score.py::aggregate.boot`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`sel`。
- 输出：`未注解；(float(point), (float(lo), float(hi)))；(point, (float('nan'), float('nan')))`。
- 作用：调用 (st == k).sum, _ntu, arrays, float, len, np.array, np.isnan, np.percentile, np.random.default_rng, np.unique, pick[:, 0].sum, pick[:, 1].sum, pick[:, 2].sum, pick[:, 3].sum, range, rng.integers, un.mean, un[st == k].sum, uo.mean, uo[st == k].sum, us.mean, us[st == k].sum, vals.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/score.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/score.py#L68)。

## `eval/tide/systems/__init__.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/systems/__init__.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `eval/tide/systems/reference.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/systems/reference.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`350aab7bcc8eacb0784ce6f24f5883627d538712a61a8615d20df64a40db2a81`。

### `eval/tide/systems/reference.py::_line`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`t: int, user: str, assistant: str`。
- 输出：`str；f'[t={t}] 用户：{user} 助手：{assistant}'`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L19)。

### `eval/tide/systems/reference.py::_pack`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`lines: list[str], budget: int`。
- 输出：`list[str]；kept`。
- 作用：调用 approx_tokens, kept.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L23)。

### `eval/tide/systems/reference.py::NoMemory`

- 功能：定义 NoMemory 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemorySystem`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L34)。

### `eval/tide/systems/reference.py::NoMemory.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L37)。

### `eval/tide/systems/reference.py::NoMemory.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user, assistant, t`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L38)。

### `eval/tide/systems/reference.py::NoMemory.serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query, t, budget_tokens, passive=True, probe=None`。
- 输出：`未注解；''`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L39)。

### `eval/tide/systems/reference.py::Oracle`

- 功能：定义 Oracle 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemorySystem`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L42)。

### `eval/tide/systems/reference.py::Oracle.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L46)。

### `eval/tide/systems/reference.py::Oracle.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user, assistant, t`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L47)。

### `eval/tide/systems/reference.py::Oracle.serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query, t, budget_tokens, passive=True, probe=None`。
- 输出：`未注解；probe.oracle_context if probe is not None else ''`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L49)。

### `eval/tide/systems/reference.py::Recency`

- 功能：定义 Recency 的数据或接口类型，承载独立账本、生成器、判分、基线及 HTTP 适配；构造字段及继承输出在本项完整登记
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemorySystem`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L53)。

### `eval/tide/systems/reference.py::Recency.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L56)。

### `eval/tide/systems/reference.py::Recency.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user, assistant, t`。
- 输出：`未注解；None`。
- 作用：调用 _line, self.turns.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L59)。

### `eval/tide/systems/reference.py::Recency.serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query, t, budget_tokens, passive=True, probe=None`。
- 输出：`未注解；'\n'.join(reversed(kept))`。
- 作用：调用 '\n'.join, _pack, list, reversed。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L62)。

### `eval/tide/systems/reference.py::_terms`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`text: str`。
- 输出：`list[str]；out`。
- 作用：调用 len, range, re.findall, w.lower。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L67)。

### `eval/tide/systems/reference.py::BM25`

- 功能：原始日志逐轮建索引，按 BM25 取最相关的轮塞满预算，输出按时间排序。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemorySystem`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L75)。

### `eval/tide/systems/reference.py::BM25.__init__`

- 功能：用给定参数与依赖初始化 BM25，建立其对象状态；业务归属为独立账本、生成器、判分、基线及 HTTP 适配
- 输入：`self, k1: float=1.2, b: float=0.75`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L79)。

### `eval/tide/systems/reference.py::BM25.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id`。
- 输出：`未注解；None`。
- 作用：调用 Counter。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L82)。

### `eval/tide/systems/reference.py::BM25.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user, assistant, t`。
- 输出：`未注解；None`。
- 作用：调用 Counter, _line, _terms, self.df.update, self.docs.append, self.tf.append, tf.keys。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L85)。

### `eval/tide/systems/reference.py::BM25.serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query, t, budget_tokens, passive=True, probe=None`。
- 输出：`未注解；''；'\n'.join(sorted(kept, key=order.get))`。
- 作用：调用 '\n'.join, _pack, _terms, enumerate, len, math.log, scored.append, scored.sort, set, sorted, sum, tf.get, tf.values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L92)。

### `eval/tide/systems/reference.py::Parsed`

- 功能：理想抽取（解析 L1 模板）+ 当前状态表。defect 注入一种已知缺陷： stale 忽略更新，永远保留首个值 → 预期伤 V、P noscope 作用域被丢弃，同主体后写覆盖前写 → 预期伤 C nocascade 上游变更不让派生值失效 → 预期伤 P noretract 撤回被忽略 → 预期伤 F hoard 服务该主体的全部历史陈述 → 预期伤 V、P、F（有害注入） amnesic 只记最近 k 轮 → 预期伤 R（大 Δ） fuzzy 按头词模糊匹配，端出所有同族主体 → 预期伤 I
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemorySystem`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L118)。

### `eval/tide/systems/reference.py::Parsed.__init__`

- 功能：用给定参数与依赖初始化 Parsed，建立其对象状态；业务归属为独立账本、生成器、判分、基线及 HTTP 适配
- 输入：`self, defect: str | None=None, amnesic_k: int=48`。
- 输出：`未注解；None`。
- 作用：调用 ValueError。
- 错误：异常 ValueError(f'unknown defect {defect}')。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L130)。

### `eval/tide/systems/reference.py::Parsed.reset`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, stream_id`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L137)。

### `eval/tide/systems/reference.py::Parsed._key`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, scope, subj`。
- 输出：`未注解；subj if self.defect == 'noscope' else (scope or '', subj)`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L142)。

### `eval/tide/systems/reference.py::Parsed.ingest`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, user, assistant, t`。
- 输出：`未注解；None`。
- 作用：调用 RE_DERIVE.match, RE_RETRACT.match, RE_SET.match, RE_UPDATE.match, m.groups, self._key, self.history.setdefault, self.history.setdefault(key, []).append, self.state.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L145)。

### `eval/tide/systems/reference.py::Parsed._visible`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, rec, now`。
- 输出：`未注解；self.defect != 'amnesic' or now - rec['t'] <= self.k`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L173)。

### `eval/tide/systems/reference.py::Parsed._stale_root`

- 功能：沿依赖链上溯：任何一环的上游值与派生时记下的不一致 → 返回失效的根。
- 输入：`self, key, seen=()`。
- 输出：`未注解；None；dep；self._stale_root(dep, seen + (key,))`。
- 作用：调用 rec.get, self._stale_root, self.state.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L176)。

### `eval/tide/systems/reference.py::Parsed._lines_for`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, key, now`。
- 输出：`未注解；[]；[rec['text']]；[self.retract_text[key]]；[txt for _, txt in reversed(self.history.get(key, []))]；self._lines_for(root, now) if root in self.state else []`。
- 作用：调用 reversed, self._lines_for, self._stale_root, self._visible, self.history.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L187)。

### `eval/tide/systems/reference.py::Parsed.serve`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query, t, budget_tokens, passive=True, probe=None`。
- 输出：`未注解；''；'\n'.join(_pack(lines, budget_tokens))`。
- 作用：调用 '\n'.join, (k if isinstance(k, str) else k[1]).startswith, RE_ASK.match, _pack, isinstance, m.groups, self._key, self._lines_for, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L206)。

### `eval/tide/systems/reference.py::reference_systems`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`无参数`。
- 输出：`dict；{'none': NoMemory, 'oracle': Oracle, 'recency': Recency, 'bm25': BM25, 'parsed': Parsed}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/systems/reference.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/systems/reference.py#L222)。

## `eval/tide/text.py`

- 模块功能：独立账本、生成器、判分、基线及 HTTP 适配。
- 设计归属：评测边界；处置：冻结保留。
- 目标路径：`eval/tide/text.py`（当前路径）。
- 模块输入：账本、流与系统接口。
- 模块输出：判分、元评测与可比报告；算法冻结，不为引擎放水。
- 源校验：`911031c42b5fd6a6b04f766bb41fceafe049f0bab072796b239424fbd75f33e9`。

### `eval/tide/text.py::approx_tokens`

- 功能：CJK 单字 = 1，ASCII 词 = 1，其余非空白符号 = 1。
- 输入：`text: str`。
- 输出：`int；len(_TOKEN_RE.findall(text))`。
- 作用：调用 _TOKEN_RE.findall, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L13)。

### `eval/tide/text.py::truncate_lines`

- 功能：按整行截断到预算内。返回 (文本, 实际 token 数, 是否发生截断)。
- 输入：`text: str, budget: int`。
- 输出：`tuple[str, int, bool]；('\n'.join(kept), used, False)；('\n'.join(kept), used, True)`。
- 作用：调用 '\n'.join, approx_tokens, kept.append, ln.strip, text.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L18)。

### `eval/tide/text.py::has_token`

- 功能：值 token 形如 zorvex-4821：前后不能紧贴字母数字或连字符。
- 输入：`text: str, tok: str`。
- 输出：`bool；re.search(f'(?<![A-Za-z0-9\\-]){re.escape(tok)}(?![A-Za-z0-9\\-])', text) is not None`。
- 作用：调用 re.escape, re.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L31)。

### `eval/tide/text.py::scope_prefix`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`scope: str`。
- 输出：`str；f'{scope} 模块的' if scope else ''`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L38)。

### `eval/tide/text.py::say_set`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`subj: str, scope: str, val: str`。
- 输出：`tuple[str, str]；(f'{p}{subj}定为 {val}。', f'好的，已记录：{p}{subj}是 {val}。')`。
- 作用：调用 scope_prefix。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L42)。

### `eval/tide/text.py::say_update`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`subj: str, scope: str, val: str`。
- 输出：`tuple[str, str]；(f'{p}{subj}改成 {val} 了。', f'明白，{p}{subj}已改为 {val}。')`。
- 作用：调用 scope_prefix。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L47)。

### `eval/tide/text.py::say_retract`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`subj: str, scope: str`。
- 输出：`tuple[str, str]；(f'{p}{subj}那个设定作废了，先别用。', f'好的，{p}{subj}的设定已作废。')`。
- 作用：调用 scope_prefix。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L52)。

### `eval/tide/text.py::say_derive`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`up_subj: str, up_val: str, subj: str, val: str`。
- 输出：`tuple[str, str]；(f'因为{up_subj}是 {up_val}，所以{subj}用 {val}。', f'收到，{subj}是 {val}（依赖{up_subj}）。')`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L57)。

### `eval/tide/text.py::ask`

- 功能：独立账本、生成器、判分、基线及 HTTP 适配 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`subj: str, scope: str=''`。
- 输出：`str；f'{scope_prefix(scope)}{subj}现在是什么？'`。
- 作用：调用 scope_prefix。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`eval/tide/text.py`；处置：冻结保留；变更：保留当前签名与 IO；[源码](../eval/tide/text.py#L62)。

## `hybrid_memory/__init__.py`

- 模块功能：包的最小导出面及延迟组装。
- 设计归属：配置与服务；处置：保留。
- 目标路径：`hybrid_memory/__init__.py`（当前路径）。
- 模块输入：进程 import 与部署方 import；不接收业务请求。
- 模块输出：Cfg/Settings/MemoryService 与延迟 build_default_service；未知属性 AttributeError。
- 源校验：`d5509c950113d6a8615c85984897cd2c14a1f981d86402141d838b9bea15f8a3`。

### `hybrid_memory/__init__.py::__getattr__`

- 功能：包的最小导出面及延迟组装 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name: str`。
- 输出：`未注解；build_default_service`。
- 作用：调用 AttributeError。
- 错误：异常 AttributeError(f'module {__name__!r} has no attribute {name!r}')。
- 目标：`hybrid_memory/__init__.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/__init__.py#L12)。

## `hybrid_memory/agent/__init__.py`

- 模块功能：旧调查员和人审入口的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/agent/__init__.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy/transport 的同一对象 re-export；无独立逻辑。
- 源校验：`02d5f8d8d79d334413c055901a6781710a63f2ac2ba150772e6602fee1b398f7`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/agent/human_review.py`

- 模块功能：旧调查员和人审入口的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/agent/human_review.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy/transport 的同一对象 re-export；无独立逻辑。
- 源校验：`79b70b3b7bb22b2ecc084e1934b84180c9912a28de2a505431ba7f217af5779c`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：main ← hybrid_memory.transport.review_cli.main；__all__ = ['main']

## `hybrid_memory/agent/inline.py`

- 模块功能：旧调查员和人审入口的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/agent/inline.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy/transport 的同一对象 re-export；无独立逻辑。
- 源校验：`c1e912f7bb4e2eef2551c063cfc8c1edb27851222281dcd2a26e4a803bfa39cc`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：TOOLS ← hybrid_memory.legacy.inline.TOOLS；InlineInvestigator ← hybrid_memory.legacy.inline.InlineInvestigator；__all__ = ['TOOLS', 'InlineInvestigator']

## `hybrid_memory/agent/investigator.py`

- 模块功能：旧调查员和人审入口的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/agent/investigator.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy/transport 的同一对象 re-export；无独立逻辑。
- 源校验：`54cfa39a510f65a36fc38976309ed2772350e096938768b33bc7daa522230e01`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：INVESTIGATOR_SYS ← hybrid_memory.legacy.investigator.INVESTIGATOR_SYS；KINDS ← hybrid_memory.legacy.investigator.KINDS；MISS_TYPES ← hybrid_memory.legacy.investigator.MISS_TYPES；VERDICTS ← hybrid_memory.legacy.investigator.VERDICTS；Budget ← hybrid_memory.legacy.investigator.Budget；Investigation ← hybrid_memory.legacy.investigator.Investigation；build_payload ← hybrid_memory.legacy.investigator.build_payload；parse_investigation ← hybrid_memory.legacy.investigator.parse_investigation；__all__ = ['INVESTIGATOR_SYS', 'KINDS', 'MISS_TYPES', 'VERDICTS', 'Budget', 'Investigation', 'build_payload', 'parse_investigation']

## `hybrid_memory/agent/loop.py`

- 模块功能：旧调查员和人审入口的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/agent/loop.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy/transport 的同一对象 re-export；无独立逻辑。
- 源校验：`7291cd05b52b17cfb743930bdafee1cbfaebd055045a2d2efe7156e6236ed9b7`。
- 模块备注：_dt 兼容别名随调用迁移后删除；不得先删后改调用方。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：ORIGIN_BY_KIND ← hybrid_memory.legacy.loop.ORIGIN_BY_KIND；AgentWorker ← hybrid_memory.legacy.loop.AgentWorker；_dt ← hybrid_memory.legacy.loop._dt；__all__ = ['ORIGIN_BY_KIND', 'AgentWorker']

## `hybrid_memory/agents/__init__.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`3b83b78ad1088462a9fb78f552edd5839eafdee458363af79b8415b83a0f9e72`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/agents/hauler.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/hauler.py`（当前路径）。
- 模块输入：Hauler 回复、任务行与封存窗口。
- 模块输出：规范化候选列表或整批拒绝；来源必须属于实际供给。
- 源校验：`697386754fbcbb5e79e09d1edaa634f220164b9844e5fbfe600eed6ce361d5bb`。

### `hybrid_memory/agents/hauler.py::validate_sources`

- 功能：每条候选必须是非空文本，且只引用所给窗口内的 unit。
- 输入：`svc, candidates, uid`。
- 输出：`未注解；None`。
- 作用：调用 ValueError, any, c.get, c['text'].strip, isinstance, set, svc.log.recent_ids, type。
- 错误：异常 ValueError('candidate must cite only units in the supplied window')。
- 目标：`hybrid_memory/agents/hauler.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/hauler.py#L8)。

### `hybrid_memory/agents/hauler.py::validate`

- 功能：Hauler 输出校验
- 输入：`reply、row、封存窗口`。
- 输出：`规范候选列表`。
- 作用：类型/来源/因果/长度/去重。
- 错误：整批 ValueError；空批合法。
- 目标：`hybrid_memory/agents/hauler.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/hauler.py#L19)。

## `hybrid_memory/agents/opencode.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/opencode.py`（当前路径）。
- 模块输入：角色名、封存 JSON、CLI 路径与超时。
- 模块输出：严格 JSON 对象；CLI 缺失/超时/坏输出显式失败，不回退假模型。
- 源校验：`c5e4d46d442c797163b21e3d97f8a2a822d35552e7fc0a6f35ce921dfc8067c1`。
- 模块备注：目标：payload 经私有 UTF-8 临时文件以 --file 附件传递；不支持该通道的 CLI 拒绝启动，不回退超长 argv；用后清理。

### `hybrid_memory/agents/opencode.py::OpenCodeRunner`

- 功能：Run real OpenCode agents, not a local imitation of their reasoning loop.
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/opencode.py#L17)。

### `hybrid_memory/agents/opencode.py::OpenCodeRunner.__init__`

- 功能：用给定参数与依赖初始化 OpenCodeRunner，建立其对象状态；业务归属为三角色载荷、严格校验及 OpenCode 运行器
- 输入：`self, project: Path, executable: str | None=None, timeout: int=300`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(__file__).resolve, os.environ.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/opencode.py#L20)。

### `hybrid_memory/agents/opencode.py::OpenCodeRunner.available`

- 功能：CLI 存在性探活；不证明 provider 账号可用
- 输入：`self`。
- 输出：`bool；shutil.which(self.executable) is not None`。
- 作用：调用 shutil.which。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/opencode.py#L26)。

### `hybrid_memory/agents/opencode.py::OpenCodeRunner.__call__`

- 功能：兼容 callable 调用并委托唯一 run 实现
- 输入：`self, name: str, payload: dict`。
- 输出：`dict；self.run(name, payload)`。
- 作用：调用 self.run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/opencode.py#L29)。

### `hybrid_memory/agents/opencode.py::OpenCodeRunner.run`

- 功能：真实角色调用
- 输入：`name、封存 payload`。
- 输出：`已解析 JSON 对象`。
- 作用：隔离 CLI、UTF-8、超时、JSONL 文本提取。
- 错误：CLI/超时/协议错误显式；不得 log 原文与凭据。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/opencode.py#L32)。

### `hybrid_memory/agents/opencode.py::OpenCodeRunner._parse_text`

- 功能：拒绝空输出、非对象、多对象和损坏 JSON
- 输入：`text: str, name: str='agent'`。
- 输出：`dict；obj`。
- 作用：调用 AgentProtocolError, isinstance, json.loads, str, text.strip。
- 错误：异常 AgentProtocolError('agent result must be a JSON object'), AgentProtocolError(f'OpenCode {name} returned no final text'), AgentProtocolError(str(exc))。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/opencode.py#L75)。

### `hybrid_memory/agents/opencode.py::_event`

- 功能：解析一个 JSONL 事件，非对象或坏行不作为最终角色正文
- 输入：`line`。
- 输出：`未注解；()；(obj,) if isinstance(obj, dict) else ()`。
- 作用：调用 isinstance, json.loads。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/opencode.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/opencode.py#L87)。

## `hybrid_memory/agents/payload.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/payload.py`（当前路径）。
- 模块输入：任务行、封存上下文、规则与记忆快照。
- 模块输出：角色 payload；窗≤12k、快照≤500 且≤1MiB，超限失败不截断。
- 源校验：`233a7fdcd3d323aaf7db592421895cbd4664258d719e88df7a66f98b572febad`。

### `hybrid_memory/agents/payload.py::rules_for`

- 功能：作用域规则注入：三角色各取自己的规则快照（文本不同）。
- 输入：`svc, kind, row, unit`。
- 输出：`未注解；svc.tasks.rule_snapshot('hauler', unit['user_text'] + '\n' + unit['assistant_text'])；svc.tasks.rule_snapshot('reviewer', unit['user_text'])；svc.tasks.rule_snapshot('selector', '\n'.join((c['text'] for c in row['payload']['candidates'])))`。
- 作用：调用 '\n'.join, svc.tasks.rule_snapshot。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/payload.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/payload.py#L8)。

### `hybrid_memory/agents/payload.py::memory_snapshot`

- 功能：完整记忆快照
- 输入：`svc`。
- 输出：`list[{id,text,src,entity,birth,pool}] 按 id 序`。
- 作用：未退役含 A；目标附邮戳。
- 错误：>500 或 >1MiB 直接失败，禁截断猜测。
- 目标：`hybrid_memory/agents/payload.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/payload.py#L17)。

### `hybrid_memory/agents/payload.py::build_payload`

- 功能：角色输入组装
- 输入：`kind、svc、row（目标：封存上下文）`。
- 输出：`kind/task_id/unit_id/window|complaint/handoffs/previous_retrieval/rules/memories|candidates`。
- 作用：只读；窗≤12k；Reviewer 含真实规则使用。
- 错误：超限/缺 unit 失败不截断。
- 目标：`hybrid_memory/agents/payload.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/payload.py#L29)。

## `hybrid_memory/agents/protocol.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/protocol.py`（当前路径）。
- 模块输入：角色名、封存 payload 与运行器能力。
- 模块输出：已解析 dict 或 AgentProtocolError/AgentTimeout；不得猜测修复。
- 源校验：`b3e392e6c743065650c8467d848dc6eee85ecaa383c29b410bcea251ac31c57b`。
- 模块备注：MAX_ATTEMPTS 常量迁移后删除：唯一上限真源在 dispatch.policy（WF/SEM=5、INV=2/3）。

### `hybrid_memory/agents/protocol.py::AgentProtocolError`

- 功能：Agent 返回不可解析/非对象：协议错（可重试整轮）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 ValueError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/agents/protocol.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/protocol.py#L14)。

### `hybrid_memory/agents/protocol.py::AgentTimeout`

- 功能：Agent CLI 超时（非输入错，不重开整轮）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Exception`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/agents/protocol.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/protocol.py#L18)。

### `hybrid_memory/agents/protocol.py::AgentRunner`

- 功能：OpenCode 运行器形状：run 主调，available 探活。fake runner 只需可调用。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Protocol`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/agents/protocol.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/protocol.py#L22)。

### `hybrid_memory/agents/protocol.py::AgentRunner.run`

- 功能：运行器协议：角色名+封存 payload → 已解析 dict
- 输入：`self, name: str, payload: dict`。
- 输出：`dict；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/protocol.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/protocol.py#L25)。

### `hybrid_memory/agents/protocol.py::AgentRunner.available`

- 功能：运行器协议：探活 bool
- 输入：`self`。
- 输出：`bool；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/agents/protocol.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/protocol.py#L28)。

## `hybrid_memory/agents/reviewer.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/reviewer.py`（当前路径）。
- 模块输入：Reviewer 回复、任务行与封存 handoffs。
- 模块输出：归一化 bundle 或整包拒绝；规则引用必须来自实际使用记录。
- 源校验：`16c52f7c40556ad86d45f7d80817ffc2e93aa7d8c5bfe1893d0f288f749da68f`。

### `hybrid_memory/agents/reviewer.py::scope_of`

- 功能：规则作用域：project 或 entity:<字面>；非法抛错。
- 输入：`scope`。
- 输出：`str；scope`。
- 作用：调用 ValueError, isinstance, len, scope.startswith, scope[7:].strip。
- 错误：异常 ValueError('rule scope must be project or entity:<literal>')。
- 目标：`hybrid_memory/agents/reviewer.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/agents/reviewer.py#L7)。

### `hybrid_memory/agents/reviewer.py::validate`

- 功能：Reviewer 输出校验
- 输入：`reply、row、封存 handoffs`。
- 输出：`归一化 bundle`。
- 作用：限额、scope、规则引用来自实际使用。
- 错误：整包拒绝，不部分安装。
- 目标：`hybrid_memory/agents/reviewer.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/reviewer.py#L16)。

## `hybrid_memory/agents/selector.py`

- 模块功能：三角色载荷、严格校验及 OpenCode 运行器。
- 设计归属：三 Agent 协议；处置：保留收口。
- 目标路径：`hybrid_memory/agents/selector.py`（当前路径）。
- 模块输入：Selector 回复、任务行与已给快照。
- 模块输出：规范 Decision 计划；严格类型、每候选恰一、目标在快照。
- 源校验：`a45a5df0358dab039861b36fd416ab150aa384fa5378a7554a71e34821efa4d5`。

### `hybrid_memory/agents/selector.py::Decision`

- 功能：Selector 决定结构：candidate_index/action/target_id/verified_correction/reason
- 输入：`candidate_index: int；action: str；target_id: int；verified_correction: bool；reason: str`。
- 输出：`类型/实例；基类 TypedDict`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/agents/selector.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/selector.py#L14)。

### `hybrid_memory/agents/selector.py::validate`

- 功能：Selector 输出预检
- 输入：`reply、row、已给快照`。
- 输出：`规范 Decision 计划`。
- 作用：严格 index 类型/覆盖、目标在快照、UPDATE proof。
- 错误：整批拒绝；不写库。
- 目标：`hybrid_memory/agents/selector.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/agents/selector.py#L22)。

## `hybrid_memory/candgen/__init__.py`

- 模块功能：旧候选类型与生成器的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/candgen/__init__.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy 候选类型与生成器同一对象 re-export。
- 源校验：`9f93a91f5cc5345a11963d98d37625344c1e284e4efdfbb46c9388b813e9920c`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：CandidateGeneration ← hybrid_memory.legacy.candgen.CandidateGeneration；CandidateGenerator ← hybrid_memory.legacy.candgen.CandidateGenerator；MemoryCandidate ← hybrid_memory.legacy.candgen.MemoryCandidate；parse_generation ← hybrid_memory.legacy.prompt.parse_generation；priority_to_salience ← hybrid_memory.legacy.prompt.priority_to_salience；redact_secrets ← hybrid_memory.legacy.prompt.redact_secrets；serialize_window ← hybrid_memory.legacy.prompt.serialize_window；__all__ = ['CandidateGeneration', 'CandidateGenerator', 'MemoryCandidate', 'parse_generation', 'priority_to_salience', 'redact_secrets', 'serialize_window']

## `hybrid_memory/candgen/base.py`

- 模块功能：旧候选类型与生成器的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/candgen/base.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy 候选类型与生成器同一对象 re-export。
- 源校验：`266b9e9c121baba95a135553524b7a31008efc7772567b510da747020ea61d61`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：CandidateGeneration ← hybrid_memory.legacy.candgen.CandidateGeneration；CandidateGenerator ← hybrid_memory.legacy.candgen.CandidateGenerator；MemoryCandidate ← hybrid_memory.legacy.candgen.MemoryCandidate；__all__ = ['CandidateGeneration', 'CandidateGenerator', 'MemoryCandidate']

## `hybrid_memory/candgen/chat.py`

- 模块功能：旧候选类型与生成器的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/candgen/chat.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy 候选类型与生成器同一对象 re-export。
- 源校验：`eb37a79147f94cda7c48046f24243259b979f1dfe7dead9c2630b053a59b773a`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：ChatGenerator ← hybrid_memory.legacy.candgen.ChatGenerator；__all__ = ['ChatGenerator']

## `hybrid_memory/candgen/prompt.py`

- 模块功能：旧候选类型与生成器的 re-export 垫片。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/candgen/prompt.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy 候选类型与生成器同一对象 re-export。
- 源校验：`7b4799657d79e57f637b93b4be0084da9656f6a93d480d700892858e9e40b979`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：INSTRUCTION ← hybrid_memory.legacy.prompt.INSTRUCTION；parse_candidate ← hybrid_memory.legacy.prompt.parse_candidate；parse_generation ← hybrid_memory.legacy.prompt.parse_generation；parse_ids ← hybrid_memory.legacy.prompt.parse_ids；parse_salience ← hybrid_memory.legacy.prompt.parse_salience；priority_to_salience ← hybrid_memory.legacy.prompt.priority_to_salience；redact_secrets ← hybrid_memory.legacy.prompt.redact_secrets；serialize_window ← hybrid_memory.legacy.prompt.serialize_window；__all__ = ['INSTRUCTION', 'parse_candidate', 'parse_generation', 'parse_ids', 'parse_salience', 'priority_to_salience', 'redact_secrets', 'serialize_window']

## `hybrid_memory/config.py`

- 模块功能：引擎参数、进程设置及环境解析。
- 设计归属：配置与服务；处置：接线。
- 目标路径：`hybrid_memory/config.py`（当前路径）。
- 模块输入：argv、环境变量、项目与包根 .env、默认值。
- 模块输出：不可变 Settings 与 Cfg 字段表、凭据字符串或 None；非法值拒绝且不静默回退。
- 源校验：`2596b9d3db263012f9880aec1f6495aa11ff3d45ee32816e06942c0cc407c030`。

### `hybrid_memory/config.py::Cfg`

- 功能：引擎动力学与机制开关字段表；默认值冻结，目标增 cap_context
- 输入：`k: int = 5；theta: float = 0.35；tau_dup: float = 0.9；tau_sim: float = 0.8；pi_m: float = 0.05；pi_a: float = -0.3；fresh_alpha: float = 0.1；shortlist_n: int = 30；lex_weight: float = 0.0；lam: float = 0.02；eta: float = 0.3；eta_shadow: float = 0.1；v_init: float = 0.5；theta_p: float = 1.5；theta_d: float = 0.8；idle_p: int = 50；cap_m: int = 40；cap_c: int = 200；cap_a: int = 2000；eta_c: float = 0.6；tension_delay: int = 20；two_pool: bool = True；shadow_credit: bool = True；ingest_dedup: bool = True；useful_hit: bool = True；defer_credit: bool = False；confidence_on: bool = False；conf_prior_alpha: float = 1.0；conf_prior_beta: float = 1.0；conf_write_evidence: float = 1.0；conf_confirm_evidence: float = 1.0；conf_negative_evidence: float = 1.0；conf_half_life: float = 50.0；theta_conf: float = 0.62；provisional_margin: float = 0.08；provisional_k: int = 1；salience_on: bool = False；salience_default: float = 0.5；salience_retention_floor: float = 0.5；salience_retention_weight: float = 3.0；novelty_on: bool = False；novelty_bonus: float = 0.25；consolidation_on: bool = False；consolidation_salience_budget: float = 6.0；consolidation_min_items: int = 5；consolidation_max_items: int = 12；signal_queue_cap: int = 256；shadow_pending_cap: int = 256；capacity_on: bool = True；suppression_on: bool = True；tension_on: bool = True；archive_retrieval: bool = True；miss_on_recognizer_none: bool = False`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/config.py#L18)。

### `hybrid_memory/config.py::Settings`

- 功能：进程级配置（§2 config）。经 'resolve_settings' 构造；不可变。
- 输入：`project: str = '.'；port: int = 17872；model: str = 'glm-5.3-flash'；pipeline: str = 'opencode'；task_capacity: int = 4096；no_agent: bool = False；agent_model: str = 'glm-5.3-flash'；agent_daily_cap: int = 200；agent_tool_calls: int = 8；agent_window_chars: int = 4000；agent_retry_delay: float = 2.0`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/config.py#L86)。

### `hybrid_memory/config.py::Settings.state_dir`

- 功能：派生：<project>/.opencode/memory（与 server.build 默认一致）。
- 输入：`self`。
- 输出：`Path；Path(self.project) / '.opencode' / 'memory'`。
- 作用：调用 Path。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/config.py#L102)。

### `hybrid_memory/config.py::resolve_pipeline`

- 功能：唯一读取 MEMORY_PIPELINE 的解析点
- 输入：`可选 env 映射（None 读进程环境）`。
- 输出：`'opencode' 或 'legacy'`。
- 作用：无副作用；不连接网络。
- 错误：目标：未知值 Fatal 拒绝启动；当前非 legacy 默认 opencode 是待修差异。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/config.py#L107)。

### `hybrid_memory/config.py::resolve_settings`

- 功能：CLI > env > 默认 的唯一进程配置解析
- 输入：`argv 列表与 env 映射；None 时读进程状态，import 时不求值`。
- 输出：`不可变 Settings；数值含正负/有限/上下界校验`。
- 作用：无 I/O；不写全局状态。
- 错误：非法值拒绝；目标与 bootstrap argparse 合并为同一解析。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/config.py#L116)。

### `hybrid_memory/config.py::resolve_settings.pick`

- 功能：CLI>env>默认的单值选择 helper
- 输入：`cli, env_key: str | None, cast, default`。
- 输出：`未注解；cast(source[env_key])；cli；default`。
- 作用：调用 cast, source.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/config.py#L138)。

### `hybrid_memory/config.py::load_env_key`

- 功能：凭据读取：env → 项目 .env → 包根 .env
- 输入：`项目目录路径`。
- 输出：`ZAI_API_KEY 字符串或 None`。
- 作用：读文件；不打印值。
- 错误：文件不可读不抛业务错误；测试必须隔离两级 .env。
- 目标：`hybrid_memory/config.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/config.py#L173)。

## `hybrid_memory/core/__init__.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/core/confidence.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/confidence.py`（当前路径）。
- 模块输入：Memory 的 Beta 证据计数、逻辑时间与 Cfg。
- 模块输出：就地折损或投影值；confidence_on=False 时 no-op。
- 源校验：`080d72c5f395d651e7a7ca020ce6b2db9fa8765a02a516b2c6812ebf6b8fdc1d`。

### `hybrid_memory/core/confidence.py::discount_to`

- 功能：按逻辑时间折损 Beta 证据计数；confidence_on=False 时 no-op
- 输入：`m, t: int, cfg`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/confidence.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/confidence.py#L9)。

### `hybrid_memory/core/confidence.py::projected`

- 功能：当前 Beta 置信投影值，不修改 Memory
- 输入：`m, cfg`。
- 输出：`float；(cfg.conf_prior_alpha + m.conf_pos) / (cfg.conf_prior_alpha + cfg.conf_prior_beta + m.conf_pos + m.conf_neg)`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/confidence.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/confidence.py#L20)。

## `hybrid_memory/core/consolidation.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/consolidation.py`（当前路径）。
- 模块输入：pending fact 集合、scene 与逻辑时间。
- 模块输出：maintenance_due 发射或 reflection Memory；不退役来源。
- 源校验：`40aaf730fbb815b01afe5a0ff5326b8b6b9a23c3618ff93884541d7143e5d254`。

### `hybrid_memory/core/consolidation.py::maybe_consolidate`

- 功能：按 scene 预算触发 maintenance_due；同签名不重复发射
- 输入：`eng, t: int`。
- 输出：`None；None`。
- 作用：调用 _budget, deferred.get, eng.mems.get, eng.signals.emit, frozenset, groups.items, groups.setdefault, groups.setdefault(m.scene, []).append, len, list, max, pending.discard, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/consolidation.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/consolidation.py#L15)。

### `hybrid_memory/core/consolidation.py::maybe_consolidate._budget`

- 功能：委托 `sum` 执行；边界与失败由被调用方契约承担
- 输入：`items`。
- 输出：`float；sum((max(0.0, min(1.0, m.salience)) for m in items))`。
- 作用：调用 max, min, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/consolidation.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/consolidation.py#L34)。

### `hybrid_memory/core/consolidation.py::admit_reflection`

- 功能：add_reflection 入库：嵌入、novelty 计算、建档、清理 pending/deferred。
- 输入：`eng, event, chosen, t: int`。
- 输出：`Memory；m`。
- 作用：调用 Memory, cosine, eng._consolidation_deferred.pop, eng._consolidation_pending.discard, eng.emb.embed, eng.mems.values, eng.next_id, eng.semantics.embedding_key, frozenset, frozenset().union, is_visible, max, min, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/consolidation.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/consolidation.py#L67)。

## `hybrid_memory/core/dynamics.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/dynamics.py`（当前路径）。
- 模块输入：Memory 映射、Cfg 容量与保护根集合。
- 模块输出：应迁出/删除 id 计划与容量收口结论；纯函数，无 I/O、不衰减。
- 源校验：`5ad7f2b190d20c85ab8daa3b7cea2a5fb465af18681b3f9818a7edf60b6583c2`。
- 模块备注：decay/credit/promote/demote/archive/retention_scale 的独立包装取消，逻辑保留在 maintenance/engine。

### `hybrid_memory/core/dynamics.py::pinned_ids`

- 功能：淘汰保护集合
- 输入：`engine 与目标外部 roots`。
- 输出：`frozenset id`。
- 作用：求张力/人审/聚合/信用/任务引用闭包。
- 错误：当前仅内存态；外部 roots 待接线。
- 目标：`hybrid_memory/core/dynamics.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/dynamics.py#L15)。

### `hybrid_memory/core/dynamics.py::evictable`

- 功能：单池应迁出/删除计划
- 输入：`pool、mems、cfg、pinned`。
- 输出：`有序 id 列表`。
- 作用：C 按 V 最低、A 按 archived_at 最旧、M 恒空。
- 错误：A 也必须滤 pinned；当前缺失是待修。
- 目标：`hybrid_memory/core/dynamics.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/dynamics.py#L33)。

### `hybrid_memory/core/dynamics.py::overflow_policy`

- 功能：C/A 溢出计划
- 输入：`mems、cfg、pinned`。
- 输出：`{'archive':[...], 'delete':[...]}`。
- 作用：纯函数不删。
- 错误：目标并入 plan_capacity。
- 目标：`hybrid_memory/core/dynamics.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/dynamics.py#L56)。

### `hybrid_memory/core/dynamics.py::plan_capacity`

- 功能：提交前容量收口模拟
- 输入：`mems、cfg、pinned`。
- 输出：`{archive,delete,remaining,accepted,reason}`。
- 作用：模拟 C→A 后重算 A 与 cap_context；无 I/O、不衰减 V。
- 错误：全 pin 时 accepted=false 背压，禁止破上限或解除保护。
- 目标：`hybrid_memory/core/dynamics.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/dynamics.py#L63)。

## `hybrid_memory/core/engine.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/engine.py`（当前路径）。
- 模块输入：Event/向量/Retrieval/verdict/信用回报与逻辑时间。
- 模块输出：裸引擎内存状态与操作面回执；不直接 SQLite/HTTP/subprocess。
- 源校验：`8e6c0a216903baaf9692731263111f98d13a3d7c2eefaaba3b721e67dfac49d0`。

### `hybrid_memory/core/engine.py::MemoryEngine`

- 功能：裸引擎门面：三池/张力/信用待账/信号出口，不直接 I/O
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L24)。

### `hybrid_memory/core/engine.py::MemoryEngine.__init__`

- 功能：用给定参数与依赖初始化 MemoryEngine，建立其对象状态；业务归属为三池、信用、张力、触发及领域协议
- 输入：`self, cfg: Cfg, emb: Embedder, semantics: MemorySemantics`。
- 输出：`未注解；None`。
- 作用：调用 SignalQueue, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L25)。

### `hybrid_memory/core/engine.py::MemoryEngine.next_id`

- 功能：单调分配 Memory id 并推进游标
- 输入：`self`。
- 输出：`int；i`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L53)。

### `hybrid_memory/core/engine.py::MemoryEngine.add_tension`

- 功能：登记或刷新未决版本对；不在此执行语义判定
- 输入：`self, left: int, right: int, t: int`。
- 输出：`None；None`。
- 作用：调用 Tension, self.tensions.get, sorted, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L58)。

### `hybrid_memory/core/engine.py::MemoryEngine.observe`

- 功能：事件入库门面
- 输入：`Event 列表、逻辑时间 t 与可选预计算向量`。
- 输出：`None`。
- 作用：委托 ingest；同源不增证据。
- 错误：由 ingest 校验。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L72)。

### `hybrid_memory/core/engine.py::MemoryEngine.retrieve`

- 功能：读取门面
- 输入：`预计算查询向量、Query 与逻辑时间`。
- 输出：`Retrieval`。
- 作用：委托 retrieval；不在 core 渲染 token。
- 错误：由 retrieval 承担。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L75)。

### `hybrid_memory/core/engine.py::MemoryEngine.step`

- 功能：一次逻辑维护
- 输入：`逻辑时间 t`。
- 输出：`None`。
- 作用：委托 maintenance；不得用于额外收容量。
- 错误：由 maintenance 承担。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L78)。

### `hybrid_memory/core/engine.py::MemoryEngine.feedback`

- 功能：回答后延迟记账入口
- 输入：`Retrieval、question、answer、t`。
- 输出：`0（入账异步）`。
- 作用：置 feedback_sent 并发 feedback_pending。
- 错误：空 selected 无活；重复 credited/sent 抛 RuntimeError。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L81)。

### `hybrid_memory/core/engine.py::MemoryEngine._current_representative`

- 功能：迟到信用记到当前代表。链断裂时不返回尸体，避免复活已退役条目。
- 输入：`self, m: Memory`。
- 输出：`Memory | None；None；target`。
- 作用：调用 maintenance.follow_chain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L100)。

### `hybrid_memory/core/engine.py::MemoryEngine._credit_hit`

- 功能：把 useful 信用记到当前代表，更新命中并按需复活
- 输入：`self, m: Memory, t: int`。
- 输出：`bool；False；True`。
- 作用：调用 self._current_representative。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L107)。

### `hybrid_memory/core/engine.py::MemoryEngine.credit_shown`

- 功能：注册表里的 Retrieval 已不在时，只按当时展示的 id 记账。
- 输入：`self, memory_ids: list, used: list, t: int`。
- 输出：`int；n`。
- 作用：调用 self._credit_hit, self.mems.get, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L119)。

### `hybrid_memory/core/engine.py::MemoryEngine.submit_relevance`

- 功能：recognizer 结果入账
- 输入：`Retrieval、used bool 列表与 t`。
- 输出：`n_useful 并置 credited`。
- 作用：代表命中/复活。
- 错误：长度必须一致；重复结清 RuntimeError。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L128)。

### `hybrid_memory/core/engine.py::MemoryEngine._record_shadow_pending`

- 功能：保存压制对的延迟信用，超限显式计丢弃
- 输入：`self, m: Memory, rival: Memory, t: int, rel: bool`。
- 输出：`None；None`。
- 作用：调用 bool, len, self._shadow_pending.append, self._shadow_pending.pop, sorted, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L146)。

### `hybrid_memory/core/engine.py::MemoryEngine._issue_shadow_credit`

- 功能：将 shadow 信用结到当前代表并按需复活
- 输入：`self, m: Memory, t_ret: int`。
- 输出：`bool；False；True`。
- 作用：调用 self._current_representative。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L154)。

### `hybrid_memory/core/engine.py::MemoryEngine._settle_shadow`

- 功能：首个 verdict 到达时结算该对全部待结算 shadow 信用 （含 verdict=="pending"——与原同步语义一致：只要非 synonym 就发）。 返回实际结算条数。
- 输入：`self, pair_key: tuple, verdict: str`。
- 输出：`int；n`。
- 作用：调用 keep.append, self._issue_shadow_credit, self.mems.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L165)。

### `hybrid_memory/core/engine.py::MemoryEngine.submit_verdicts`

- 功能：批量张力裁决回报
- 输入：`[(left,right,verdict)] 与 t`。
- 输出：`实际消解条数`。
- 作用：pending 留 backlog；死对/塌缩对清理；先折损再 apply_resolution。
- 错误：目标：调用方须先过版本/人审冻结门。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L182)。

### `hybrid_memory/core/engine.py::MemoryEngine.add_reflection`

- 功能：reflection 入库门面
- 输入：`Event、derived_from 与 t`。
- 输出：`新 Memory`。
- 作用：委托 consolidation；不退役来源。
- 错误：由 consolidation 承担。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L210)。

### `hybrid_memory/core/engine.py::MemoryEngine.drain_signals`

- 功能：worker 拉取待处理信号（清空队列）。
- 输入：`self`。
- 输出：`list；self.signals.drain()`。
- 作用：调用 self.signals.drain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/engine.py#L217)。

### `hybrid_memory/core/engine.py::MemoryEngine.miss_key`

- 功能：规范化问题去重 key（去空白/小写/长度界）
- 输入：`q: str`。
- 输出：`str；'miss:' + ''.join(q.split()).lower()[:200]`。
- 作用：调用 ''.join, ''.join(q.split()).lower, q.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L226)。

### `hybrid_memory/core/engine.py::MemoryEngine.report_miss`

- 功能：缺失信号发射
- 输入：`q、t、hint/source/retrieval/entities`。
- 输出：`None`。
- 作用：规范问题 key 去重合并；携带已召回证据。
- 错误：空 q 无动作。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L229)。

### `hybrid_memory/core/engine.py::MemoryEngine.report_miss.merge`

- 功能：合并缺失线索/来源/实体，保留已知召回证据
- 输入：`old, new`。
- 输出：`未注解；old`。
- 作用：调用 dict.fromkeys, list。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L246)。

### `hybrid_memory/core/engine.py::MemoryEngine.report_unit`

- 功能：定向抽取信号发射
- 输入：`uid、t、scene、reasons、entities`。
- 输出：`None`。
- 作用：按 unit 去重、原因并集。
- 错误：无 reasons 不发。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L258)。

### `hybrid_memory/core/engine.py::MemoryEngine.report_unit.merge`

- 功能：并集合并同单元的抽取理由与实体
- 输入：`old, new`。
- 输出：`未注解；old`。
- 作用：调用 dict.fromkeys, list。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L268)。

### `hybrid_memory/core/engine.py::MemoryEngine.propose`

- 功能：agent 提议入库
- 输入：`Event 列表、t 与可选 vectors`。
- 输出：`实际新建 id 列表`。
- 作用：与 observe 同一 ingest；不直进 M。
- 错误：origin=passive 拒绝；重复不返回 id。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L277)。

### `hybrid_memory/core/engine.py::MemoryEngine.pool_sizes`

- 功能：C/M/A 物理数量（含退役成员）
- 输入：`self`。
- 输出：`dict[str, int]；out`。
- 作用：调用 self.mems.values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/engine.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/engine.py#L289)。

## `hybrid_memory/core/ingest.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/ingest.py`（当前路径）。
- 模块输入：事件列表、逻辑时间与可选预计算向量。
- 模块输出：去重/合并/新建候选与张力登记；同源不增证据、不直进 M。
- 源校验：`1d82b2d16e31dd06e40e58152a56600294b198b623d6d9061e4bd4f9b2185ad0`。

### `hybrid_memory/core/ingest.py::run_ingest`

- 功能：事件写入主体
- 输入：`engine、events、t、可选 vectors`。
- 输出：`None`。
- 作用：指纹+值去重、新 C、高相似张力。
- 错误：同源不增 evid；向量预计算优先。
- 目标：`hybrid_memory/core/ingest.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/ingest.py#L15)。

## `hybrid_memory/core/interaction.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/interaction.py`（当前路径）。
- 模块输入：一轮交互与窗口边界。
- 模块输出：InteractionUnit/InteractionWindow 数据载体；不是池项。
- 源校验：`dbd5d821d287d8eafeef7edb8f862d463463a9ed084dbd5cc4a8fa81e8ce235f`。

### `hybrid_memory/core/interaction.py::InteractionUnit`

- 功能：一轮交互载体：id/时界/user_text/assistant_text/turns
- 输入：`id: int；start_time: int；end_time: int；user_text: str；assistant_text: str；assistant_turns: int`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/interaction.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/interaction.py#L8)。

### `hybrid_memory/core/interaction.py::InteractionWindow`

- 功能：抽取窗口载体：编号/时界/units
- 输入：`id: int；start_unit_id: int；end_unit_id: int；start_time: int；end_time: int；units: tuple[InteractionUnit, ...]`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/interaction.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/interaction.py#L18)。

## `hybrid_memory/core/maintenance.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/maintenance.py`（当前路径）。
- 模块输入：引擎状态与逻辑时间。
- 模块输出：一次维护的效果：衰减/滞回/容量/归档/张力发射/巩固；不额外重放。
- 源校验：`452fed7cf593b6044301de03316bb97fb35c3539500dcc801da63352cc2c20de`。

### `hybrid_memory/core/maintenance.py::_retention_scale`

- 功能：三池、信用、张力、触发及领域协议 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`m, cfg`。
- 输出：`float；1.0；1.0 + cfg.salience_retention_weight * excess`。
- 作用：调用 max, min。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/maintenance.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/maintenance.py#L21)。

### `hybrid_memory/core/maintenance.py::_warn_promote_reject_once`

- 功能：M 拒收只告警一次（core 内镜像 telemetry.warn_once 语义：core 不得 import telemetry，I1；计数 n_promote_rejected 另行累积在引擎上）。
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 print。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/maintenance.py`；处置：迁移后删除；变更：删除条件：core 内打印违背纯状态层；telemetry 限频告警接管后移除；[源码](../hybrid_memory/core/maintenance.py#L33)。

### `hybrid_memory/core/maintenance.py::run_maintenance`

- 功能：一次维护：衰减/滞回/容量/归档/信号
- 输入：`engine 与 t`。
- 输出：`None`。
- 作用：每新逻辑 unit 一次；消费 d_hit/d_shadow。
- 错误：容量不足以收口时按目标背压，不额外 step。
- 目标：`hybrid_memory/core/maintenance.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/maintenance.py#L44)。

### `hybrid_memory/core/maintenance.py::_emit_pending_conflicts`

- 功能：tension 维护：剪掉死对/链塌缩对，把到达 tension_delay 的未决对 以 conflict_pending 信号交给 worker 裁决（引擎不做语义判定）。 verdict 经 submit_verdicts 回报后由 apply_resolution 消解。
- 输入：`eng, t: int`。
- 输出：`None；None`。
- 作用：调用 aged.append, eng.signals.emit, eng.tensions.items, follow_chain, list。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/maintenance.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/maintenance.py#L109)。

### `hybrid_memory/core/maintenance.py::follow_chain`

- 功能：代表链跟随
- 输入：`engine 与 Memory`。
- 输出：`当前代表 Memory`。
- 作用：断裂/成环计数后停止；id=0 有效。
- 错误：不得复活尸体。
- 目标：`hybrid_memory/core/maintenance.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/maintenance.py#L131)。

### `hybrid_memory/core/maintenance.py::apply_resolution`

- 功能：四类裁决后果
- 输入：`a、b、verdict、t`。
- 输出：`None`。
- 作用：synonym/update/contradiction/collision；旧版 A 且打 archived_at。
- 错误：人审冻结目标不得自动退役。
- 目标：`hybrid_memory/core/maintenance.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/maintenance.py#L152)。

### `hybrid_memory/core/maintenance.py::_make_aggregate`

- 功能：同实体矛盾收编为聚合 memory：成员退居幕后（aggregated_into）， 聚合体带全部版本+时间戳出场。pending=True 表示冲突未裁决。
- 输入：`eng, a, b, t: int, text: str, pending: bool`。
- 输出：`None；None`。
- 作用：调用 Memory, eng.next_id, float, max, min, np.linalg.norm。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/maintenance.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/maintenance.py#L207)。

## `hybrid_memory/core/retrieval.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/retrieval.py`（当前路径）。
- 模块输入：查询向量、Query、逻辑时间与引擎状态。
- 模块输出：Retrieval：入选、压制、shadow、provisional、contested 与 thin 遥测。
- 源校验：`7208aa48c7db9ce576e9bab184ac62c8b9b227aca9533d4c220bd5730d23299f`。

### `hybrid_memory/core/retrieval.py::_lex_tokens`

- 功能：提取 ASCII 标识和 CJK bigram 集合
- 输入：`text: str`。
- 输出：`set[str]；toks`。
- 作用：调用 _ASCII_TOK.findall, _CJK_RUN.findall, len, range, set, text.lower, toks.update。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/retrieval.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/retrieval.py#L23)。

### `hybrid_memory/core/retrieval.py::lexical_scores`

- 功能：IDF 加权的 query 项覆盖率：记忆包含的稀有 query 词越多分越高。 ASCII 标识符（PR号/hash/文件名）与中文 bigram 各占一路； 权重 = log((N+1)/(df+0.5))，分母为 query 全部 token 的权重和。
- 输入：`query: str, texts: dict[int, str]`。
- 输出：`dict[int, float]；{mid: sum((idf(t) for t in qtok & mt)) / denom for mid, mt in toks_by_id.items() if qtok & mt}；{}`。
- 作用：调用 _lex_tokens, any, df.get, idf, int, len, max, sum, texts.items, toks_by_id.items。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/retrieval.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/retrieval.py#L31)。

### `hybrid_memory/core/retrieval.py::lexical_scores.idf`

- 功能：计算当前语料的逆文档频率权重
- 输入：`tok: str`。
- 输出：`float；math.log((n + 1) / (df.get(tok, 0) + 0.5))`。
- 作用：调用 df.get, math.log。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/retrieval.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/retrieval.py#L53)。

### `hybrid_memory/core/retrieval.py::_prior`

- 功能：取得 Memory 所属池的检索先验
- 输入：`m: Memory, cfg`。
- 输出：`float；0.0；cfg.pi_a；cfg.pi_m if cfg.two_pool else 0.0`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/retrieval.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/retrieval.py#L61)。

### `hybrid_memory/core/retrieval.py::run_retrieve`

- 功能：读取算法主体
- 输入：`engine、查询向量、Query、t`。
- 输出：`Retrieval（selected/suppressed/contested/provisional/thin）`。
- 作用：质量门、置信、压制、信用、张力。
- 错误：passive/调查副本由 service 调用，不在此分叉。
- 目标：`hybrid_memory/core/retrieval.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/retrieval.py#L69)。

### `hybrid_memory/core/retrieval.py::run_retrieve._try_select`

- 功能：尝试选入一条 Memory，必要时记录压制、shadow 和张力
- 输入：`m: Memory`。
- 输出：`bool；False；True`。
- 作用：调用 cosine, eng._record_shadow_pending, eng.add_tension, eng.semantics.relevant, eng.signals.emit, max, ret.suppressed.append, sorted, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/retrieval.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/retrieval.py#L95)。

## `hybrid_memory/core/signals.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/signals.py`（当前路径）。
- 模块输入：kind/payload/t/key/merge 与容量。
- 模块输出：Signal 或持久交接回调结果；易失队列允许丢弃但必须计数。
- 源校验：`4936c77d96891c1d5447ed8a34caf22bc53c792bdfe8de02034475a9b4416abc`。

### `hybrid_memory/core/signals.py::Signal`

- 功能：业务工作理由载体：kind/payload/t/key/id；不授予权限
- 输入：`kind: str；payload: object；t: int；key: str = ''；id: int = 0`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/signals.py#L14)。

### `hybrid_memory/core/signals.py::SignalQueue`

- 功能：有界易失队列与持久交接回调边界
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/signals.py#L22)。

### `hybrid_memory/core/signals.py::SignalQueue.__init__`

- 功能：用给定参数与依赖初始化 SignalQueue，建立其对象状态；业务归属为三池、信用、张力、触发及领域协议
- 输入：`self, cap: int=256, on_emit=None`。
- 输出：`未注解；None`。
- 作用：调用 deque, int, max。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/signals.py#L23)。

### `hybrid_memory/core/signals.py::SignalQueue.emit`

- 功能：信号发射与持久交接边界
- 输入：`kind/payload/t/key/merge`。
- 输出：`Signal（或已交接的占位）`。
- 作用：on_emit 非 None 即接管；否则有界入队/去重/丢最旧计数。
- 错误：不得把已接受 Task 放回会丢队列。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/signals.py#L32)。

### `hybrid_memory/core/signals.py::SignalQueue.drain`

- 功能：取空内存队列；sidecar 不用于可靠交付
- 输入：`self`。
- 输出：`list[Signal]；out`。
- 作用：调用 list, self._by_key.clear, self._items.clear。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/signals.py#L62)。

### `hybrid_memory/core/signals.py::SignalQueue.take`

- 功能：按 kind 摘取
- 输入：`kinds 集合`。
- 输出：`选中 Signal 列表，其余保序`。
- 作用：移除内存镜像；不触碰 DB。
- 错误：调用方负责锁。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/signals.py#L68)。

### `hybrid_memory/core/signals.py::SignalQueue.peek_kinds`

- 功能：内存队列 kind 计数（只读）
- 输入：`self`。
- 输出：`dict[str, int]；counts`。
- 作用：调用 counts.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/signals.py#L83)。

### `hybrid_memory/core/signals.py::SignalQueue.__len__`

- 功能：返回内存队列当前项数
- 输入：`self`。
- 输出：`int；len(self._items)`。
- 作用：调用 len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/signals.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/signals.py#L89)。

## `hybrid_memory/core/triggers.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/triggers.py`（当前路径）。
- 模块输入：用户文本、助手文本与首次实体列表。
- 模块输出：correction/decision/quant/new_entity/long_turn 调度理由；永不作为事实证据。
- 源校验：`5648482a7e6ad8846722c126268caf3b8e9191aa06f93ee814feae6104772e7e`。

### `hybrid_memory/core/triggers.py::is_dissatisfaction`

- 功能：A scheduling hint, never evidence that the old memory is incorrect.
- 输入：`user_text: str`。
- 输出：`bool；bool(user_text) and (is_correction(user_text) or DISSATISFACTION_RE.search(user_text[:500]) is not None)`。
- 作用：调用 DISSATISFACTION_RE.search, bool, is_correction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/triggers.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/triggers.py#L57)。

### `hybrid_memory/core/triggers.py::is_correction`

- 功能：首 80 字符严格纠正提示；UPDATE proof 辅助，不授权事实
- 输入：`user_text: str`。
- 输出：`bool；bool(user_text) and CORRECTION_RE.search(user_text[:80]) is not None`。
- 作用：调用 CORRECTION_RE.search, bool。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/triggers.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/triggers.py#L63)。

### `hybrid_memory/core/triggers.py::scan_unit`

- 功能：→ 命中的原因列表（可能为空 = 不抽取）。
- 输入：`user_text: str, assistant_text: str, new_entities: list[str] | tuple=()`。
- 输出：`list[str]；reasons`。
- 作用：调用 DECISION_RE.search, QUANT_RE.search, is_correction, len, reasons.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/triggers.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/triggers.py#L67)。

## `hybrid_memory/core/types.py`

- 模块功能：三池、信用、张力、触发及领域协议。
- 设计归属：三池与领域；处置：保留收口。
- 目标路径：`hybrid_memory/core/types.py`（当前路径）。
- 模块输入：领域字段、池值、检索与协议形状。
- 模块输出：Memory/Event/Query/Tension/Retrieval 数据结构、Pool、is_visible、cosine 与协议声明；不含 I/O。
- 源校验：`56ef6deb43ecda1f410882fb99f377e63a83d1ebdee9c6cc814bacc907a7d5a9`。

### `hybrid_memory/core/types.py::Pool`

- 功能：C/M/A 池枚举（按值序列化）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Enum`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L11)。

### `hybrid_memory/core/types.py::Pool.__reduce_ex__`

- 功能：三池、信用、张力、触发及领域协议 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, protocol`。
- 输出：`未注解；(Pool, (self.value,))`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/types.py#L16)。

### `hybrid_memory/core/types.py::is_visible`

- 功能：可出场判定
- 输入：`Memory`。
- 输出：`bool`。
- 作用：未归档/未退役/未聚合。
- 错误：不代表 A 禁止读取。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L21)。

### `hybrid_memory/core/types.py::Memory`

- 功能：记忆全字段：池/V/证据/信用/归档/退役/来源/置信/场景/origin/entity
- 输入：`id: int；belief_id: int；value: str；text: str；emb: np.ndarray；pool: Pool = Pool.CANDIDATE；v: float = 0.5；hits: int = 0；shadow_hits: int = 0；evid: int = 1；birth: int = 0；last_hit: int | None = None；last_seen: int = 0；archived_at: int | None = None；suppressed_by: int | None = None；superseded_by: int | None = None；aggregated_into: int | None = None；agg_members: tuple = ()；pending_review: bool = False；src: frozenset = frozenset()；d_hit: float = 0.0；d_shadow: float = 0.0；conf_pos: float = 0.0；conf_neg: float = 0.0；conf_updated_at: int = 0；salience: float = 0.5；novelty: float = 1.0；kind: str = 'fact'；derived_from: tuple[int, ...] = ()；scene: str = ''；origin: str = 'passive'；entity: str = ''`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L33)。

### `hybrid_memory/core/types.py::Event`

- 功能：准入事件：指纹/规范值/正文/来源与显式元数据
- 输入：`belief_id: int；value: str；text: str；src: tuple = ()；salience: float = 0.5；kind: str = 'fact'；derived_from: tuple[int, ...] = ()；conf_pos: float | None = None；conf_neg: float | None = None；scene: str = ''；origin: str = 'passive'；entity: str = ''`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L76)。

### `hybrid_memory/core/types.py::Query`

- 功能：读取上下文：target 与文本；真实查询 target=-1
- 输入：`target: int；text: str`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L92)。

### `hybrid_memory/core/types.py::MemorySemantics`

- 功能：本地语义谓词与 embedding key 协议（无网络调用）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Protocol`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L97)。

### `hybrid_memory/core/types.py::MemorySemantics.judge`

- 功能：worker 外部关系协议声明；core 不直接调用
- 输入：`self, a_bid: int, a_val: str, b_bid: int, b_val: str`。
- 输出：`str；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L98)。

### `hybrid_memory/core/types.py::MemorySemantics.relevant`

- 功能：本地相关性谓词声明
- 输入：`self, belief_id: int, value: str, query: Query, t: int`。
- 输出：`bool；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L99)。

### `hybrid_memory/core/types.py::MemorySemantics.valid`

- 功能：本地有效性谓词声明（裸兼容，非真实真值）
- 输入：`self, belief_id: int, value: str, t: int`。
- 输出：`bool；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L100)。

### `hybrid_memory/core/types.py::MemorySemantics.embedding_key`

- 功能：向量缓存键协议声明
- 输入：`self, belief_id: int, value: str`。
- 输出：`tuple；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L101)。

### `hybrid_memory/core/types.py::MemorySemantics.scope`

- 功能：作用域谓词声明（当前常空）
- 输入：`self, belief_id: int`。
- 输出：`str；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L102)。

### `hybrid_memory/core/types.py::FeedbackSemantics`

- 功能：可选能力：response-level recognizer。 实现了它，engine.feedback 才会只给真被答案用上的记忆发 useful-hit； 缺失时退化为 selected-hit 全记。返回 None 表示识别失败——worker 计数告警后同样退化全记，失败不静默。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Protocol`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/types.py#L106)。

### `hybrid_memory/core/types.py::FeedbackSemantics.relevant_set`

- 功能：可选归因协议：bool 列表或失败 None
- 输入：`self, texts: list, question: str, answer: str`。
- 输出：`list | None；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L111)。

### `hybrid_memory/core/types.py::ConsolidationSemantics`

- 功能：可选能力：scene 级巩固回调。 实现了它，consolidation 回路才能把 pending 组蒸馏成 kind="reflection" 记忆；缺失时该回路不产 reflection（pending 照常修剪，不堆积）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Protocol`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/types.py#L116)。

### `hybrid_memory/core/types.py::ConsolidationSemantics.consolidate`

- 功能：可选巩固协议：Event 或 None
- 输入：`self, memories: list, t: int`。
- 输出：`未注解；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L121)。

### `hybrid_memory/core/types.py::Tension`

- 功能：版本对账本项：左右/首末见/观测数
- 输入：`left: int；right: int；first_seen: int；last_seen: int；observations: int = 1`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L125)。

### `hybrid_memory/core/types.py::Retrieval`

- 功能：读取结果：入选/展示快照/压制/未决/置信/信用标志
- 输入：`selected: list[Memory] = field(default_factory=list)；presented_texts: tuple[str, ...] = ()；suppressed: list[tuple[int, int]] = field(default_factory=list)；contested: list[tuple[Memory, Memory]] = field(default_factory=list)；provisional: list[Memory] = field(default_factory=list)；n_shortlisted: int = 0；n_useful: int = 0；credited: bool = False；feedback_sent: bool = False`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L134)。

### `hybrid_memory/core/types.py::cosine`

- 功能：余弦相似（P4 从 embed.base 原样迁入：core 零越层 I1，算法一字不动）。
- 输入：`a: np.ndarray, b: np.ndarray`。
- 输出：`float；0.0；float(a @ b / (na * nb))`。
- 作用：调用 float, np.linalg.norm。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/types.py#L150)。

### `hybrid_memory/core/types.py::Embedder`

- 功能：向量生产者契约（P4 从 embed.base 原样迁入；产出的向量由 cosine 消费）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Protocol`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/core/types.py#L158)。

### `hybrid_memory/core/types.py::Embedder.embed`

- 功能：向量生产协议声明（允许外部 I/O）
- 输入：`self, texts: list[str], keys: list | None=None`。
- 输出：`np.ndarray；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/core/types.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/core/types.py#L161)。

## `hybrid_memory/dispatch/__init__.py`

- 模块功能：业务信号路由、预算调度及效果应用。
- 设计归属：信号与派发；处置：统一接线。
- 目标路径：`hybrid_memory/dispatch/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`5c5e4ed7992b64e405b21515e5a98b786fc7726dbd2a0dc56df71a02e6cbf94c`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/dispatch/effects.py`

- 模块功能：业务信号路由、预算调度及效果应用。
- 设计归属：信号与派发；处置：统一接线。
- 目标路径：`hybrid_memory/dispatch/effects.py`（当前路径）。
- 模块输入：任务行、模型产物、连接与回执上下文。
- 模块输出：唯一效果编排与九类 applier 的结构化结果；整批原子、容量复核。
- 源校验：`ab8a6aeb166e61f937f439daf6d6b58dd2a0220d391b0c373693a612ad133b0a`。

### `hybrid_memory/dispatch/effects.py::Applier`

- 功能：一种 kind 的消费者登记：dispatch 自持 applier 函数， 外部循环（legacy-agent/service）只登记归属；工作流类 P6 起归 dispatch。
- 输入：`kind: str；owner: str；apply: Callable | None = None`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/effects.py#L24)。

### `hybrid_memory/dispatch/effects.py::Applier.runner`

- 功能：运行器标识，对齐 owner。
- 输入：`self`。
- 输出：`str；self.owner`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/effects.py#L32)。

### `hybrid_memory/dispatch/effects.py::journal_signal`

- 功能：引擎信号出口：调查类进任务表，其余走易失队列（原 _journal_signal）。
- 输入：`svc, kind, payload, t, key, merge`。
- 输出：`未注解；None；svc.tasks.enqueue(kind, payload, t, key=key, merge=merge, memory_next_id=svc.engine._next_id)`。
- 作用：调用 svc._ensure_healthy, svc.tasks.enqueue。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/effects.py#L37)。

### `hybrid_memory/dispatch/effects.py::signal_payload`

- 功能：仅存稳定 id/JSON；绝不把 Retrieval/Memory 实例放进任务表。
- 输入：`svc, kind, payload`。
- 输出：`未注解；[list(pair) for pair in payload]；payload；{'retrieval_id': rid, 'selected': [m.id for m in ret.selected], 'texts': list(texts), 'question': payload['question'], 'answer': payload['answer']}`。
- 作用：调用 ValueError, getattr, len, list, next, svc._retrievals.items, tuple。
- 错误：异常 ValueError('feedback retrieval 不在服务注册表')。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/effects.py#L46)。

### `hybrid_memory/dispatch/effects.py::effect_transaction`

- 功能：唯一效果编排
- 输入：`svc、mutate、capture/task/unit 上下文`。
- 输出：`回执 dict`。
- 作用：内存备份、信号收集、CAS、回执、done 与回滚。
- 错误：上下文互斥；提交后确认丢失设 fault。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L65)。

### `hybrid_memory/dispatch/effects.py::effect_transaction.run`

- 功能：事务内闭包：安装信号收集并执行 mutate
- 输入：`conn`。
- 输出：`未注解；mutate()`。
- 作用：调用 mutate。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L76)。

### `hybrid_memory/dispatch/effects.py::effect_transaction.run.collect`

- 功能：同事务收集持久信号；不嵌套 BEGIN
- 输入：`kind, payload, t, key, merge`。
- 输出：`未注解；old_emit(kind, payload, t, key, merge)；svc.tasks._enqueue(conn, kind, signal_payload(svc, kind, payload), t, key=key, merge=merge, memory_next_id=svc.engine._next_id)`。
- 作用：调用 old_emit, signal_payload, svc.tasks._enqueue。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L80)。

### `hybrid_memory/dispatch/effects.py::apply_conflict`

- 功能：存量裁决落地
- 输入：`svc、row、result`。
- 输出：`{'resolved':n}`。
- 作用：邮戳一致才裁决；过期重排；人审冻结优先。
- 错误：pending 保持 backlog。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L114)。

### `hybrid_memory/dispatch/effects.py::apply_feedback`

- 功能：归因信用结算
- 输入：`svc、row、result`。
- 输出：`{'credited':n,'recog_fail':bool,'retired_source'?}`。
- 作用：按展示集合或持久快照结算；不改正文。
- 错误：长度不符拒绝。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L133)。

### `hybrid_memory/dispatch/effects.py::apply_maintenance`

- 功能：reflection 落地
- 输入：`svc、row、result`。
- 输出：`{'reflected':0|1}`。
- 作用：来源版本一致才入库；漂移重派。
- 错误：合法 NONE 计 0 并保留原因。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L162)。

### `hybrid_memory/dispatch/effects.py::send_workflow`

- 功能：工作流交接：下发下一角色任务；空候选不建任务（原 TrioWorker._send）。
- 输入：`conn, svc, kind, uid, candidates, parent`。
- 输出：`未注解；None`。
- 作用：调用 svc.tasks._enqueue。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/effects.py#L182)。

### `hybrid_memory/dispatch/effects.py::apply_hauler`

- 功能：候选校验与接力
- 输入：`svc、row、output、conn`。
- 输出：`{'candidates':n}`。
- 作用：去重后建 selector_due；空批不建任务。
- 错误：非法候选整批拒绝。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L191)。

### `hybrid_memory/dispatch/effects.py::apply_selector`

- 功能：五路分流执行
- 输入：`svc、row、output、conn`。
- 输出：`{'outcomes':[{index,action,target_id?,new_ids?,new_evidence?}]}`。
- 作用：规范计划+动态复核+容量准入；全批原子。
- 错误：非法/漂移整批回滚；容量不足背压。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L199)。

### `hybrid_memory/dispatch/effects.py::prepare_effect`

- 功能：事务前效果计划
- 输入：`svc 与任务行`。
- 输出：`{events,vectors,targets,expected_revision,actions} 计划`。
- 作用：embedding 与静态校验在锁外完成；失败无内存效果。
- 错误：来源/因果/窗口非法即失败，不部分构建。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L281)。

### `hybrid_memory/dispatch/effects.py::apply_reviewer`

- 功能：规则与修复落地
- 输入：`svc、row、output、conn`。
- 输出：`{'rules':n,'repair_candidates':n}`。
- 作用：规则/停用/审计与接力同事务。
- 错误：非法 bundle 整拒；上限满背压。
- 目标：`hybrid_memory/dispatch/effects.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/effects.py#L306)。

## `hybrid_memory/dispatch/policy.py`

- 模块功能：业务信号路由、预算调度及效果应用。
- 设计归属：信号与派发；处置：统一接线。
- 目标路径：`hybrid_memory/dispatch/policy.py`（当前路径）。
- 模块输入：kind 与限额/租约/退避数据。
- 模块输出：不可变 KindPolicy、唯一 policy_for 与启动消费者自检；未知 kind Fatal。
- 源校验：`f465922bb4af5766c66510edbb240dd12699800ae69480e65f13a0fc5695eeac`。
- 模块备注：目标：KindPolicy 增 max_apply_attempts（WF/SEM=5、INV=3）；与模型上限分别计入。

### `hybrid_memory/dispatch/policy.py::KindPolicy`

- 功能：一类任务的认领与重试策略（静态配置，不可变）。
- 输入：`kinds: tuple[str, ...] = ()；claim_from: tuple[str, ...] = ('pending', 'ready')；daily_cap: int | None = None；max_attempts: int | None = None；max_apply_attempts: int | None = None；on_exhausted: str = 'dead'；lease_s: float | None = None；backoff: float = 0.0`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/dispatch/policy.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/policy.py#L24)。

### `hybrid_memory/dispatch/policy.py::policy_for`

- 功能：取某 kind 的策略；未知 kind 抛 Fatal（配置错必须 loud）。
- 输入：`kind: str`。
- 输出：`KindPolicy；POLICIES[kind]`。
- 作用：调用 Fatal。
- 错误：异常 Fatal(f'unknown task kind: {kind}')。
- 目标：`hybrid_memory/dispatch/policy.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/policy.py#L77)。

### `hybrid_memory/dispatch/policy.py::assert_consumers`

- 功能：kind 消费者自检
- 输入：`appliers/active kinds/policies/runners`。
- 输出：`None`。
- 作用：正反一致、callable、pipeline gate、回执豁免。
- 错误：缺失/野项 Fatal；当前仅查键待升级。
- 目标：`hybrid_memory/dispatch/policy.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/policy.py#L85)。

## `hybrid_memory/dispatch/worker.py`

- 模块功能：业务信号路由、预算调度及效果应用。
- 设计归属：信号与派发；处置：统一接线。
- 目标路径：`hybrid_memory/dispatch/worker.py`（当前路径）。
- 模块输入：service、runner、settings/policy 与轮次上限。
- 模块输出：本轮完成的 Task 数与阶段统计；模型锁外、产物可复用、停止有界。
- 源校验：`0e0a83a6d5ce3fc2d44f377c5814e2eb4fbc4d1547d3a6d0c9b718014365bc3f`。
- 模块备注：目标：run_semantic_tasks 与 Legacy.process_once 降为无独立线程 adapter，统一 due 筛选/额度/策略；unit_work 仍按 uid 顺序。

### `hybrid_memory/dispatch/worker.py::semantic_model`

- 功能：只读取判定输入；调用外部语义模型时不持服务锁。
- 输入：`svc, row`。
- 输出：`未注解；{'event': None, 'sources': sources}；{'event': asdict(event) if event is not None else None, 'sources': sources}；{'used': [bool(u) for u in used], 'recog_fail': failed}；{'verdicts': [[a, b, svc.semantics.judge(*args) if args else 'pending', stamp] for a, b, args, stamp in jobs]}`。
- 作用：调用 ValueError, asdict, bool, copy.deepcopy, fn, is_visible, isinstance, jobs.append, len, maintenance.follow_chain, payload.get, sorted, svc._ensure_healthy, svc.engine.mems.get, svc.engine.tensions.get, svc.semantics.consolidate, svc.semantics.judge, tuple。
- 错误：异常 ValueError('反馈文本快照与入选记忆不匹配'), ValueError(f'未知语义任务 {kind}')。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/worker.py#L24)。

### `hybrid_memory/dispatch/worker.py::apply_semantic`

- 功能：事务性应用已落库的模型结果；分支走 EFFECTS 表。
- 输入：`svc, row`。
- 输出：`未注解；out`。
- 作用：调用 dict, old_ret.__dict__.clear, old_ret.__dict__.update, svc._kick, svc._retrievals.get, svc._rollback_effect, svc.tasks.complete。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/worker.py#L72)。

### `hybrid_memory/dispatch/worker.py::apply_semantic.mutate`

- 功能：complete 事务内的应用闭包
- 输入：`conn, result`。
- 输出：`未注解；applier(svc, row, result)`。
- 作用：调用 ValueError, applier。
- 错误：异常 ValueError(f"无 dispatch applier: {row['kind']}")。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L80)。

### `hybrid_memory/dispatch/worker.py::apply_semantic.mutate.collect`

- 功能：应用期信号收集闭包
- 输入：`kind, payload, t, key, merge`。
- 输出：`未注解；old_emit(kind, payload, t, key, merge)；svc.tasks._enqueue(conn, kind, effects.signal_payload(svc, kind, payload), t, key=key, merge=merge, memory_next_id=svc.engine._next_id)`。
- 作用：调用 effects.signal_payload, old_emit, svc.tasks._enqueue。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L84)。

### `hybrid_memory/dispatch/worker.py::run_semantic_tasks`

- 功能：语义任务阶段适配
- 输入：`svc 与 limit`。
- 输出：`judged/resolved/credited/reflected/thin/recog_fail/errors`。
- 作用：目标无独立线程，统一 due/quota/policy。
- 错误：单任务失败不影响整批；fault 即停。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L113)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker`

- 功能：工作流后台循环（P6：TrioWorker 继任；语义 kind 仍走 run_semantic_tasks）。 claim→run_agent→store_result→claim→EFFECTS-apply→complete； 认领状态与重试上限来自 policies（默认值与旧硬编码一致）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/worker.py#L164)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker.__init__`

- 功能：用给定参数与依赖初始化 DispatchWorker，建立其对象状态；业务归属为业务信号路由、预算调度及效果应用
- 输入：`self, service, runner, policies=None, *, idle_s=2, lease_s=600`。
- 输出：`未注解；None`。
- 作用：调用 threading.Event, threading.Lock。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/worker.py#L171)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker.start`

- 功能：幂等启动后台调度线程
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 self._stop.clear, self._thread.is_alive, self._thread.start, self._wake.clear, threading.Thread。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L184)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker.stop`

- 功能：有界停止
- 输入：`timeout`。
- 输出：`None`。
- 作用：停领取、唤醒、等在途、产物可存则 ready。
- 错误：未停成功必须报告，不假装安全保存。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L193)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker.notify`

- 功能：set 唤醒事件（允许合并）
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 self._wake.set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L199)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker.stats`

- 功能：processed/errors 计数；目标扩展 inflight/paused/dead
- 输入：`self`。
- 输出：`dict；{'processed': self._processed, 'errors': self._errors}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L202)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker._loop`

- 功能：业务信号路由、预算调度及效果应用 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 print, self._stop.is_set, self._wake.clear, self._wake.wait, self.process_once, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/worker.py#L205)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker._apply`

- 功能：业务信号路由、预算调度及效果应用 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, conn, row, output`。
- 输出：`未注解；applier(self.svc, row, output, conn)`。
- 作用：调用 ValueError, applier。
- 错误：异常 ValueError(f"无 dispatch applier: {row['kind']}")。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/dispatch/worker.py#L217)。

### `hybrid_memory/dispatch/worker.py::DispatchWorker.process_once`

- 功能：统一调度一轮
- 输入：`limit`。
- 输出：`int 完成数`。
- 作用：recover→due→claim→模型或复用→效果；类别公平。
- 错误：异常不杀循环；dead 留人工。
- 目标：`hybrid_memory/dispatch/worker.py`；处置：统一接线；变更：按本项目标契约实施；[源码](../hybrid_memory/dispatch/worker.py#L223)。

## `hybrid_memory/embed/__init__.py`

- 模块功能：向量传输、分块及无原文向量缓存。
- 设计归属：模型适配；处置：保留。
- 目标路径：`hybrid_memory/embed/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/embed/base.py`

- 模块功能：向量传输、分块及无原文向量缓存。
- 设计归属：模型适配；处置：保留。
- 目标路径：`hybrid_memory/embed/base.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：core.types 的 Embedder/cosine 同一对象。
- 源校验：`68fe43b2542166a6fcc51a88a9e3a36cf830e5ceebf8fcaa59921f0a99f5aa91`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：Embedder ← ..core.types.Embedder；cosine ← ..core.types.cosine；__all__ = ['Embedder', 'cosine']

## `hybrid_memory/embed/cache.py`

- 模块功能：向量传输、分块及无原文向量缓存。
- 设计归属：模型适配；处置：保留。
- 目标路径：`hybrid_memory/embed/cache.py`（当前路径）。
- 模块输入：cache_key 与 float32 向量。
- 模块输出：维度校验后的向量副本或 None；不存正文/密钥。
- 源校验：`cb33a6b0d1528cc114a14595ac410696b71ce22a8787022191df916f0da64677`。

### `hybrid_memory/embed/cache.py::SqliteEmbeddingCache`

- 功能：SQLite 向量缓存（不存正文/密钥）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/embed/cache.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/embed/cache.py#L16)。

### `hybrid_memory/embed/cache.py::SqliteEmbeddingCache.__init__`

- 功能：用给定参数与依赖初始化 SqliteEmbeddingCache，建立其对象状态；业务归属为向量传输、分块及无原文向量缓存
- 输入：`self, path: str | Path`。
- 输出：`未注解；None`。
- 作用：调用 Path, closing, conn.execute, self.path.parent.mkdir, sqlite3.connect, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/embed/cache.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/cache.py#L17)。

### `hybrid_memory/embed/cache.py::SqliteEmbeddingCache.get`

- 功能：读缓存并校验维度，返回副本或 None
- 输入：`self, cache_key: str`。
- 输出：`np.ndarray | None；None；np.frombuffer(blob, dtype='<f4').copy()`。
- 作用：调用 closing, conn.execute, conn.execute('SELECT dimensions, vector FROM embeddings WHERE cache_key = ?', (cache_key,)).fetchone, len, np.dtype, np.frombuffer, np.frombuffer(blob, dtype='<f4').copy, sqlite3.connect, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/embed/cache.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/embed/cache.py#L24)。

### `hybrid_memory/embed/cache.py::SqliteEmbeddingCache.put`

- 功能：写 float32 向量
- 输入：`self, cache_key: str, vector: np.ndarray`。
- 输出：`None；None`。
- 作用：调用 closing, conn.execute, int, np.ascontiguousarray, np.ascontiguousarray(vector, dtype='<f4').reshape, sqlite3.connect, str, vec.tobytes。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/embed/cache.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/embed/cache.py#L36)。

## `hybrid_memory/embed/zhipu.py`

- 模块功能：向量传输、分块及无原文向量缓存。
- 设计归属：模型适配；处置：保留。
- 目标路径：`hybrid_memory/embed/zhipu.py`（当前路径）。
- 模块输入：文本批次、模型/维度/缓存/端点与可选注入 HTTP。
- 模块输出：归一化向量或 ZhipuEmbeddingError；分块与重试有界。
- 源校验：`bff7e78079f3e268ebf1ccc89530b6588099f426f062564cb38745d7b0bbefa2`。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbeddingError`

- 功能：向量边界/传输错误
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 RuntimeError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/embed/zhipu.py#L18)。

### `hybrid_memory/embed/zhipu.py::_unit_vectors`

- 功能：先缩放再求范数，避免有限值溢出/下溢；禁止零向量流入引擎。
- 输入：`vectors`。
- 输出：`未注解；(vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)).astype(np.float32)`。
- 作用：调用 (vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)).astype, ZhipuEmbeddingError, np.abs, np.any, np.asarray, np.isfinite, np.isfinite(vectors).all, np.linalg.norm, np.max。
- 错误：异常 ZhipuEmbeddingError('non-finite embedding'), ZhipuEmbeddingError('zero embedding (possibly cancelled chunks)')。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/zhipu.py#L22)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder`

- 功能：智谱 embedding 适配器：分块/缓存/重试/离线模式
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Embedder`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/embed/zhipu.py#L34)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder.__init__`

- 功能：用给定参数与依赖初始化 ZhipuEmbedder，建立其对象状态；业务归属为向量传输、分块及无原文向量缓存
- 输入：`self, api_key: str | None=None, model: str='embedding-3', dimensions: int=2048, batch_size: int=64, max_chars: int=2000, timeout: float=60.0, max_retries: int=2, cache: SqliteEmbeddingCache | None=None, offline: bool=False, http_post: Callable[[Request, float], bytes] | None=None`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, ValueError, os.environ.get。
- 错误：异常 RuntimeError('ZAI_API_KEY is not set'), ValueError('batch_size must be in 1..64'), ValueError('max_chars must be >= 1'), ValueError('max_retries must be >= 0'), ValueError('timeout must be > 0'), ValueError(f'dimensions must be one of {self._DIMENSIONS}')。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/zhipu.py#L39)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder.embed`

- 功能：批量文本 → 归一化向量（分块+缓存+按长度加权）
- 输入：`self, texts: list[str], keys: list | None=None`。
- 输出：`np.ndarray；_unit_vectors(out)；np.zeros((0, dim), dtype=np.float32)`。
- 作用：调用 ValueError, ZhipuEmbeddingError, _unit_vectors, chunks.append, enumerate, isinstance, json.dumps, json.dumps({'model': self.model, 'input': [chunk for _, chunk in batch], 'dimensions': dim}).encode, key_to_indices.items, key_to_indices.setdefault, key_to_indices.setdefault(key, []).append, len, np.zeros, range, self._cache_key, self._request, self.cache.get, self.cache.put, spans.append, zip。
- 错误：异常 ValueError('each text must be a non-empty string'), ZhipuEmbeddingError('embedding cache miss in offline mode'), ZhipuEmbeddingError('invalid cached dimensions')。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/embed/zhipu.py#L78)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder._cache_key`

- 功能：向量传输、分块及无原文向量缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, text: str`。
- 输出：`str；hashlib.sha256(raw).hexdigest()`。
- 作用：调用 f'{self.model}\x00{self.dimensions}\x00{text}'.encode, hashlib.sha256, hashlib.sha256(raw).hexdigest。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/zhipu.py#L131)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder._default_post`

- 功能：向量传输、分块及无原文向量缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, request: Request, timeout: float`。
- 输出：`bytes；response.read()`。
- 作用：调用 response.read, urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/zhipu.py#L135)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder._request`

- 功能：向量传输、分块及无原文向量缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, body: bytes, n: int`。
- 输出：`list[np.ndarray]；self._parse(raw, n)`。
- 作用：调用 Request, ZhipuEmbeddingError, range, self._http_post, self._parse, time.sleep, type。
- 错误：异常 ZhipuEmbeddingError(f'HTTP {status}'), ZhipuEmbeddingError(f'transport error: {type(exc).__name__}')。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/zhipu.py#L139)。

### `hybrid_memory/embed/zhipu.py::ZhipuEmbedder._parse`

- 功能：向量传输、分块及无原文向量缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, raw: bytes, n: int`。
- 输出：`list[np.ndarray]；[vec for _, vec in items]`。
- 作用：调用 ZhipuEmbeddingError, _unit_vectors, entry.get, int, isinstance, items.append, items.sort, json.loads, len, np.asarray, payload.get, range, seen.add, set, type, usage.get。
- 错误：异常 ZhipuEmbeddingError('invalid JSON response'), ZhipuEmbeddingError('invalid data index'), ZhipuEmbeddingError('invalid data item'), ZhipuEmbeddingError('invalid embedding dimensions'), ZhipuEmbeddingError('invalid embedding'), ZhipuEmbeddingError('invalid response data'), ZhipuEmbeddingError('invalid response payload'), ZhipuEmbeddingError('non-contiguous data index')。
- 目标：`hybrid_memory/embed/zhipu.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/embed/zhipu.py#L164)。

## `hybrid_memory/errors.py`

- 模块功能：可拒收、可降级、不可启动三类错误。
- 设计归属：错误与观测；处置：接线。
- 目标路径：`hybrid_memory/errors.py`（当前路径）。
- 模块输入：错误码、文案与 detail；不含业务数据。
- 模块输出：Rejected/Degraded/Fatal/ProposalRejected 异常与唯一状态码映射；未知码 KeyError。
- 源校验：`1da1312841f10fe0fec87d0c82204d020908690aebbf07bd823f7e04656a958a`。

### `hybrid_memory/errors.py::MemoryError`

- 功能：基类：code 稳定（给插件判），message 给人读，detail 给运维查。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Exception`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/errors.py#L10)。

### `hybrid_memory/errors.py::MemoryError.__init__`

- 功能：用给定参数与依赖初始化 MemoryError，建立其对象状态；业务归属为可拒收、可降级、不可启动三类错误
- 输入：`self, code: str, message: str='', detail: str=''`。
- 输出：`None；None`。
- 作用：调用 super, super().__init__。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/errors.py#L13)。

### `hybrid_memory/errors.py::Rejected`

- 功能：调用方错：4xx，不重试（幂等键冲突靠重放，不靠重试语义）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemoryError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/errors.py#L20)。

### `hybrid_memory/errors.py::Degraded`

- 功能：可继续但必须外显：调用方收到 200/503 + 降级标志或计数。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemoryError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/errors.py#L24)。

### `hybrid_memory/errors.py::Fatal`

- 功能：拒绝启动：配置错/版本错/自检不过，不进 HTTP。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 MemoryError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/errors.py#L28)。

### `hybrid_memory/errors.py::ProposalRejected`

- 功能：写入校验失败（P6 自 service/operate.py 归位至此）。 保持 ValueError 基类：trio 重试的 retry_model 整轮重开、HTTP 400 映射 都认 ValueError；operate/service/server 逐层 re-export 兼容旧引用。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 ValueError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/errors.py#L32)。

### `hybrid_memory/errors.py::http_status`

- 功能：错误码 → HTTP 状态唯一映射
- 输入：`稳定字符串 code`。
- 输出：`int 状态码`。
- 作用：无副作用。
- 错误：未知码 KeyError（调用方 bug 必须响亮）。
- 目标：`hybrid_memory/errors.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/errors.py#L55)。

## `hybrid_memory/guards/__init__.py`

- 模块功能：边界校验包的 import 入口。
- 设计归属：边界校验；处置：保留。
- 目标路径：`hybrid_memory/guards/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`04b7063f8ba8d7ff051460b47b3bff28d3719e84df43e027f680327c38bbf72d`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/guards/bounds.py`

- 模块功能：请求身份与批量上限；clamp 壳明确删除。
- 设计归属：边界校验；处置：接线。
- 目标路径：`hybrid_memory/guards/bounds.py`（当前路径）。
- 模块输入：request_id、指纹字段、批量与数值。
- 模块输出：规范 id/指纹或拒绝；批量上限整批无效果。
- 源校验：`380ee7156eaf8620b3017db2fdbada9eda209514de483442b1bbdb60d70772de`。
- 模块备注：MAX_PROPOSE_BATCH/MAX_BODY_BYTES 目标接唯一真源；与 dto.MAX_BODY 不得两份并存。

### `hybrid_memory/guards/bounds.py::validate_request_id`

- 功能：请求 id 语法校验（P4 从 server 原样迁入）。
- 输入：`value`。
- 输出：`未注解；None；value`。
- 作用：调用 ValueError, _REQUEST_ID_RE.fullmatch, isinstance。
- 错误：异常 ValueError('request_id must be 8–80 characters of [A-Za-z0-9._:-]')。
- 目标：`hybrid_memory/guards/bounds.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/guards/bounds.py#L17)。

### `hybrid_memory/guards/bounds.py::capture_fingerprint`

- 功能：请求体规范指纹（幂等绑定用；P4 从 server 迁入）。
- 输入：`fields: dict`。
- 输出：`str；hashlib.sha256(raw.encode('utf-8')).hexdigest()`。
- 作用：调用 hashlib.sha256, hashlib.sha256(raw.encode('utf-8')).hexdigest, json.dumps, raw.encode。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/guards/bounds.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/guards/bounds.py#L26)。

### `hybrid_memory/guards/bounds.py::require_batch_size`

- 功能：批量上限校验
- 输入：`items 与 limit`。
- 输出：`None 或 Rejected`。
- 作用：调用方保证整批无部分效果。
- 错误：超限拒绝；目标实现接线，当前为 stub。
- 目标：`hybrid_memory/guards/bounds.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/guards/bounds.py#L33)。

## `hybrid_memory/guards/grounding.py`

- 模块功能：浅层正文一致性；联接 I/O 留在 service。
- 设计归属：边界校验；处置：保留收口。
- 目标路径：`hybrid_memory/guards/grounding.py`（当前路径）。
- 模块输入：候选正文与所引原文。
- 模块输出：浅层一致性 bool；不证明语义蕴含。
- 源校验：`02b50b1e13036981fc6384b00ed159ce947ca173f6a4a7d1a5ce9fca83a1e33a`。

### `hybrid_memory/guards/grounding.py::content_grounded`

- 功能：正文至少有一个可核对片段出现在所引原文中。 可核对片段是连续两个汉字，或长度 ≥ 4 的 ASCII/数字串。长度 ≥ 8 的标识 （脱敏占位 REDACTED 除外）必须全部出现，不能靠一个真片段夹带假标识。 没有任何可核对片段时拒绝：无法区分空话和编造。
- 输入：`candidate_text, window_text: str`。
- 输出：`bool；False；matched`。
- 作用：调用 ''.join, any, candidate_text.split, isinstance, len, range, re.findall, src.lower, tok.lower, window_text.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/guards/grounding.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/guards/grounding.py#L7)。

## `hybrid_memory/guards/provenance.py`

- 模块功能：来源存在性与因果上界的纯校验。
- 设计归属：边界校验；处置：实现接线。
- 目标路径：`hybrid_memory/guards/provenance.py`（当前路径）。
- 模块输入：来源 id 集合与注入的本地存在/时间查询。
- 模块输出：存在性与因果界判定；未知/越界拒绝，不做 I/O。
- 源校验：`f4fe721dba2aceca39dda7b5fc10fa893b94220b4d03eab3951fa4741eeecdba`。
- 模块备注：目标：三函数由 stub 实现接线，注入本地 lookup，I/O 留在 service。

### `hybrid_memory/guards/provenance.py::sources_known`

- 功能：来源集合纯判定
- 输入：`ids 与已知集合`。
- 输出：`bool`。
- 作用：无 I/O。
- 错误：未知只是 False；目标实现接线，当前为 stub。
- 目标：`hybrid_memory/guards/provenance.py`；处置：实现接线；变更：按本项目标契约实施；[源码](../hybrid_memory/guards/provenance.py#L9)。

### `hybrid_memory/guards/provenance.py::validate_sources`

- 功能：来源存在性校验
- 输入：`ids 与注入的 exists 查询`。
- 输出：`None 或 Rejected`。
- 作用：无 I/O；I/O 由 service 预取。
- 错误：未知 id 拒绝；目标实现接线，当前为 stub。
- 目标：`hybrid_memory/guards/provenance.py`；处置：实现接线；变更：按本项目标契约实施；[源码](../hybrid_memory/guards/provenance.py#L15)。

### `hybrid_memory/guards/provenance.py::ensure_within_before`

- 功能：因果上界校验
- 输入：`ids、before 与注入的 birth 查询`。
- 输出：`None 或 Rejected`。
- 作用：无 I/O。
- 错误：越界 id 拒绝；目标实现接线，当前为 stub。
- 目标：`hybrid_memory/guards/provenance.py`；处置：实现接线；变更：按本项目标契约实施；[源码](../hybrid_memory/guards/provenance.py#L26)。

## `hybrid_memory/guards/redact.py`

- 模块功能：凭据模式的统一视图脱敏，不修改原始证据。
- 设计归属：边界校验；处置：保留接线。
- 目标路径：`hybrid_memory/guards/redact.py`（当前路径）。
- 模块输入：待展示/入库的文本视图。
- 模块输出：凭据模式替换后的文本；原始 L0 证据不改。
- 源校验：`cf868411917a77243b8501ef4c4984a43c3d063b977d67c9b0f755445e2bb8d1`。

### `hybrid_memory/guards/redact.py::redact_secrets`

- 功能：输出层兜底：凭据模式替换为 [REDACTED]，事实陈述保留。
- 输入：`text: str`。
- 输出：`str；_SECRET_RE.sub('[REDACTED]', text)`。
- 作用：调用 _SECRET_RE.sub。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/guards/redact.py`；处置：保留接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/guards/redact.py#L19)。

## `hybrid_memory/interaction.py`

- 模块功能：InteractionUnit/Window 旧导入位。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/interaction.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：core.interaction 的 InteractionUnit/InteractionWindow 同一对象。
- 源校验：`c039b2042c3f79d3cdcb9a644ffedc3481d5d39f8517caaed7611c81aade118a`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：InteractionUnit ← hybrid_memory.core.interaction.InteractionUnit；InteractionWindow ← hybrid_memory.core.interaction.InteractionWindow；__all__ = ['InteractionUnit', 'InteractionWindow']

## `hybrid_memory/investigation_context.py`

- 模块功能：不可变调查上下文旧导入位。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/investigation_context.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：service.context 的调查上下文与异常同一对象。
- 源校验：`24ce981a3bf449726ff758ac2ee21d8deba1d46502e9bee9a2d25ba058362f38`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：CausalViolation ← hybrid_memory.service.context.CausalViolation；InvestigationContext ← hybrid_memory.service.context.InvestigationContext；SignalClosed ← hybrid_memory.service.context.SignalClosed；__all__ = ['CausalViolation', 'InvestigationContext', 'SignalClosed']

## `hybrid_memory/legacy/__init__.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/__init__.py`（当前路径）。
- 模块输入：兼容启动。
- 模块输出：DEPRECATED 标记与一次启动告警。
- 源校验：`f0721c68fb78a35eac4998a06d920bbb5fdf38a5ae716ffc80919708189942e5`。

### `hybrid_memory/legacy/__init__.py::warn_once`

- 功能：sidecar 以 legacy 管线启动时调一次（stderr 提示，不改行为）。
- 输入：`无参数`。
- 输出：`None；None`。
- 作用：调用 _warnings.warn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/__init__.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/__init__.py#L8)。

## `hybrid_memory/legacy/candgen.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/candgen.py`（当前路径）。
- 模块输入：窗口与 chat_fn。
- 模块输出：候选生成结构；无写权。
- 源校验：`09d2cbec65ebc61c07688442103ee11745465d09b5e20272a39db8b8599e8f99`。

### `hybrid_memory/legacy/candgen.py::ChatGenerator`

- 功能：Legacy 单轮候选生成器（无写权）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/candgen.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/candgen.py#L17)。

### `hybrid_memory/legacy/candgen.py::ChatGenerator.__init__`

- 功能：用给定参数与依赖初始化 ChatGenerator，建立其对象状态；业务归属为显式 legacy 管线和裸引擎消费者；不在默认管线暗调
- 输入：`self, chat_fn`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/candgen.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/candgen.py#L18)。

### `hybrid_memory/legacy/candgen.py::ChatGenerator.generate`

- 功能：窗口+情境 → 候选结构
- 输入：`self, window: InteractionWindow, prev_scene: str=''`。
- 输出：`CandidateGeneration；parse_generation(out)`。
- 作用：调用 parse_generation, self._chat, serialize_window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/candgen.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/candgen.py#L21)。

## `hybrid_memory/legacy/inline.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/inline.py`（当前路径）。
- 模块输入：信号 payload 与注入 chat。
- 模块输出：Investigation 或 None；只读工具、预算与因果由服务端闸。
- 源校验：`1ba3858411c6828915404b021adc1eeb34ef75bddefefee79580eb3358f8aba9`。

### `hybrid_memory/legacy/inline.py::_fn`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`name: str, desc: str, props: dict, required: list[str]`。
- 输出：`dict；{'type': 'function', 'function': {'name': name, 'description': desc, 'parameters': {'type': 'object', 'properties': props, 'required': required}}}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L24)。

### `hybrid_memory/legacy/inline.py::_hits`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`hits: list`。
- 输出：`str；'\n'.join((f"[unit {h['unit_id']} | t={h['t']}{(' | ' + h['scene'] if h.get('scene') else '')}] {h['snippet']}" for h in hits))；'（无命中）'`。
- 作用：调用 '\n'.join, h.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L60)。

### `hybrid_memory/legacy/inline.py::_positive_int`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`args, name, default`。
- 输出：`未注解；default；value`。
- 作用：调用 ValueError, args.get, type。
- 错误：异常 ValueError(f'{name} must be a positive integer')。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L68)。

### `hybrid_memory/legacy/inline.py::InlineInvestigator`

- 功能：可调用对象：payload dict → Investigation | None（失败），供 AgentWorker 调用。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L77)。

### `hybrid_memory/legacy/inline.py::InlineInvestigator.__init__`

- 功能：用给定参数与依赖初始化 InlineInvestigator，建立其对象状态；业务归属为显式 legacy 管线和裸引擎消费者；不在默认管线暗调
- 输入：`self, service, *, model: str='glm-5.3-flash', api_key: str | None=None, chat_fn: Callable[..., dict] | None=None, max_turns: int | None=None`。
- 输出：`未注解；None`。
- 作用：调用 model.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L80)。

### `hybrid_memory/legacy/inline.py::InlineInvestigator._default_chat`

- 功能：委托 `chat_messages` 执行；边界与失败由被调用方契约承担
- 输入：`self, messages: list, tools: list`。
- 输出：`dict；chat_messages(messages, tools=tools, api_key=self.api_key, model=self.model)`。
- 作用：调用 chat_messages。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L92)。

### `hybrid_memory/legacy/inline.py::InlineInvestigator._tool`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, name: str, args: dict, sid: str`。
- 输出：`str；'\n'.join((f"[id={m['id']} | t={m['birth']}] {m['text']}" for m in rec['selected'])) or '（无相关记忆）'；'\n'.join((f"[{c['left']} vs {c['right']}] {c['left_text']} ⚔ {c['right_text']}" for c in cs)) or '（无未决冲突）'；'\n\n'.join(parts) + (f"\n\n（{'；'.join(tail)}）" if tail else '')；'group_by 必须是 scene | entity | week'；_hits(svc.log_search(str(args.get('query', '')), scene=args.get('scene') or None, k=_positive_int(args, 'k', 8), signal_id=sid)['hits'])；f"{r['entity']} 时间线（{r['n']} 处）：\n{_hits(r['timeline'])}"；f"共 {r['units_total']} 个单元\n" + '\n'.join((json.dumps(x, ensure_ascii=False) for x in r['rows']))；f'未知工具 {name}'`。
- 作用：调用 '\n'.join, '\n\n'.join, '；'.join, ValueError, _hits, _positive_int, all, args.get, isinstance, json.dumps, len, r.get, str, svc.conflicts, svc.log_search, svc.log_stats, svc.log_timeline, svc.log_window, svc.recall, tail.append, type, u.get。
- 错误：异常 ValueError('unit_ids must be a non-empty integer list (≤20)')。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L97)。

### `hybrid_memory/legacy/inline.py::InlineInvestigator.__call__`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, payload: dict`。
- 输出：`Investigation | None；None；inv`。
- 作用：调用 (payload.get('budget') or {}).get, c.get, fn.get, int, isinstance, json.dumps, json.loads, messages.append, msg.get, parse_investigation, payload.get, print, range, self._chat, self._tool, str, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/inline.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/inline.py#L143)。

## `hybrid_memory/legacy/investigator.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/investigator.py`（当前路径）。
- 模块输入：信号与预算。
- 模块输出：调查附件与 Investigation 或 None；旧宽容解析。
- 源校验：`086d3d84f7d5f73505713de023be8f74a1b31c445b163a539fc1c3c222fb5495`。

### `hybrid_memory/legacy/investigator.py::Budget`

- 功能：调查预算：tool_calls/window_chars/timeout_s
- 输入：`tool_calls: int = 8；window_chars: int = 4000；timeout_s: int = 300`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/investigator.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/investigator.py#L64)。

### `hybrid_memory/legacy/investigator.py::Investigation`

- 功能：调查产物：proposals/verdicts/diagnosis/raw
- 输入：`proposals: list[dict] = field(default_factory=list)；verdicts: list[tuple[int, int, str]] = field(default_factory=list)；diagnosis: dict | None = None；raw: str = ''`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/investigator.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/investigator.py#L71)。

### `hybrid_memory/legacy/investigator.py::build_payload`

- 功能：信号 → 调查员附件。只放引擎已经知道的小信息 + 确定性线索。
- 输入：`signal, *, signal_id: str, t: int, scene: str, budget: Budget, entity_hints: dict | None=None`。
- 输出：`dict；base`。
- 作用：调用 base.update, isinstance, p.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/investigator.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/investigator.py#L79)。

### `hybrid_memory/legacy/investigator.py::_first_json_object`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`text: str`。
- 输出：`dict | None；None；obj`。
- 作用：调用 any, dec.raw_decode, isinstance, json.JSONDecoder, text.find。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/investigator.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/investigator.py#L108)。

### `hybrid_memory/legacy/investigator.py::parse_investigation`

- 功能：→ Investigation；找不到合法对象返回 None（调用方计失败）。 单条形状不对只丢那一条。
- 输入：`text: str`。
- 输出：`Investigation | None；None；inv`。
- 作用：调用 Investigation, _first_json_object, diag.get, ek.strip, inv.proposals.append, inv.verdicts.append, isinstance, item.get, len, note.strip, obj.get, parse_ids, parse_salience, str, str(diag.get('miss_type', '')).strip, str(item.get('verdict', '')).strip, str(item.get('verdict', '')).strip().lower, txt.strip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/investigator.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/investigator.py#L124)。

## `hybrid_memory/legacy/loop.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/loop.py`（当前路径）。
- 模块输入：调查任务、预算与限额。
- 模块输出：阶段统计与任务状态；目标委托统一 dispatch，不再独立线程。
- 源校验：`fd29452755be144af8652c3e7cced5e5bd87b16f4993c4869b42e627dfab13bf`。

### `hybrid_memory/legacy/loop.py::AgentWorker`

- 功能：Legacy 调查任务适配器；目标委托统一调度，不再独立线程
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/loop.py#L29)。

### `hybrid_memory/legacy/loop.py::AgentWorker.__init__`

- 功能：用给定参数与依赖初始化 AgentWorker，建立其对象状态；业务归属为显式 legacy 管线和裸引擎消费者；不在默认管线暗调
- 输入：`self, service, investigate: Callable[[dict], Investigation | None], *, budget: Budget | None=None, daily_cap: int=200, max_attempts: int=2, dedupe_ttl_s: float=24 * 3600, idle_s: float=2.0, before_for: Callable | None=None, max_apply_attempts: int=3, retry_delay_s: float=0, lease_s: float | None=None`。
- 输出：`未注解；None`。
- 作用：调用 Budget, ValueError, float, int, math.isfinite, threading.Event, threading.Lock。
- 错误：异常 ValueError('attempt limits/lease must be positive; delays/TTL finite and non-negative')。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/loop.py#L30)。

### `hybrid_memory/legacy/loop.py::AgentWorker.start`

- 功能：启动 Legacy 调查线程（兼容）
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 self._stop.clear, self._thread.is_alive, self._thread.start, threading.Thread。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/loop.py#L66)。

### `hybrid_memory/legacy/loop.py::AgentWorker.stop`

- 功能：有界停止调查线程
- 输入：`self, timeout: float=5.0`。
- 输出：`None；None`。
- 作用：调用 self._stop.set, self._thread.is_alive, self._thread.join, self._wake.set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/loop.py#L74)。

### `hybrid_memory/legacy/loop.py::AgentWorker.notify`

- 功能：唤醒调查线程
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 self._wake.set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/loop.py#L82)。

### `hybrid_memory/legacy/loop.py::AgentWorker._loop`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 print, self._stop.is_set, self._wake.clear, self._wake.wait, self.process_once, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/loop.py#L85)。

### `hybrid_memory/legacy/loop.py::AgentWorker.process_once`

- 功能：以 SQLite 为事实源，逐个领取；绝不先破坏性摘走一整批任务。 有保存产物的 ready 任务不再调用模型，也不受当天调查次数用尽阻塞。
- 输入：`self, max_signals: int | None=None`。
- 输出：`dict；stats`。
- 作用：调用 _dt.date.today, _dt.date.today().isoformat, len, max, min, print, self._apply, self._busy.acquire, self._busy.release, self._claim, self._investigate, self._stop.is_set, store.finish, store.get, store.list_tasks, store.recover_expired, store.retry, store.runs_today, store.skip_recent, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/loop.py#L98)。

### `hybrid_memory/legacy/loop.py::AgentWorker._claim`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, row`。
- 输出：`未注解；claimed`。
- 作用：调用 ORIGIN_BY_KIND.get, Signal, _dt.date.today, _dt.date.today().isoformat, int, self.before_for, self.svc._check_checkpoint_error, self.svc._dump_state, self.svc.tasks.claim, self.svc.tasks.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/loop.py#L167)。

### `hybrid_memory/legacy/loop.py::AgentWorker._investigate`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, row`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, Signal, asdict, build_payload, isinstance, list, secrets.token_hex, self.investigate, self.svc._check_checkpoint_error, self.svc._dump_state, self.svc.close_budget, self.svc.current, self.svc.log.mention_counts, self.svc.open_budget, self.svc.tasks.store_result, sig.payload.get。
- 错误：异常 RuntimeError('调查员没有返回合法产物')。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/loop.py#L186)。

### `hybrid_memory/legacy/loop.py::AgentWorker._apply`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, row, stats`。
- 输出：`未注解；None`。
- 作用：调用 Investigation, InvestigationContext, inv.diagnosis.get, len, out.get, print, res.get, self.svc.diagnose, self.svc.propose, self.svc.resolve。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/loop.py#L219)。

### `hybrid_memory/legacy/loop.py::AgentWorker.stats`

- 功能：调查计数/日额度/任务状态
- 输入：`self`。
- 输出：`dict；{'runs': self.n_runs, 'failed': self.n_failed, 'gave_up': self.n_gave_up, 'skipped_recent': self.n_skipped_recent, 'proposed': self.n_proposed, 'accepted': self.n_accepted, 'verdicts': self.n_verdicts, 'diagnosed': self.n_diagnosed, 'runs_today': runs_today, 'daily_cap': self.daily_cap, 'paused_until': paused_until, 'tasks': self.svc.tasks.stats(), 'alive': bool(self._thread and self._thread.is_alive())}`。
- 作用：调用 (today + _dt.timedelta(days=1)).isoformat, _dt.date.today, _dt.timedelta, bool, self._thread.is_alive, self.svc.tasks.runs_today, self.svc.tasks.stats, today.isoformat。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/loop.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/loop.py#L246)。

## `hybrid_memory/legacy/prompt.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/prompt.py`（当前路径）。
- 模块输入：窗口、模型 JSON 文本与旧缓存字段。
- 模块输出：候选/情境结构或宽容解析结果；公共 parse 目标迁 guards。
- 源校验：`d547519c1f797820f5eb85707046295a3b01419d6b0bb349ed3c818820193bf7`。
- 模块备注：parse_ids/parse_salience 目标迁 guards 供新协议严格校验；Legacy 宽容解析保留兼容。

### `hybrid_memory/legacy/prompt.py::MemoryCandidate`

- 功能：Legacy 候选字段：text/type/priority/source_unit_ids/salience
- 输入：`text: str；type: str = ''；priority: int | None = None；source_unit_ids: tuple[int, ...] = ()；salience: float = 0.5`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L58)。

### `hybrid_memory/legacy/prompt.py::CandidateGeneration`

- 功能：一次窗口抽取的完整产物：候选 + 供下一窗携带的情境名。
- 输入：`candidates: tuple[MemoryCandidate, ...]；scene_name: str = ''`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/prompt.py#L67)。

### `hybrid_memory/legacy/prompt.py::CandidateGenerator`

- 功能：Legacy 生成器协议
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Protocol`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L73)。

### `hybrid_memory/legacy/prompt.py::CandidateGenerator.generate`

- 功能：窗口+prev_scene → CandidateGeneration
- 输入：`self, window: InteractionWindow, prev_scene: str=''`。
- 输出：`CandidateGeneration；协议声明，没有业务实现`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L74)。

### `hybrid_memory/legacy/prompt.py::serialize_window`

- 功能：窗口 → 带 unit id 的提示文本
- 输入：`window: InteractionWindow, prev_scene: str=''`。
- 输出：`str；head + '\n\n'.join(parts)`。
- 作用：调用 '\n\n'.join, parts.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L78)。

### `hybrid_memory/legacy/prompt.py::parse_salience`

- 功能：0–1 有限值解析（非法回默认）
- 输入：`value, default: float=0.5`。
- 输出：`float；default；float(max(0, min(1, value)))`。
- 作用：调用 float, isinstance, math.isfinite, max, min。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L89)。

### `hybrid_memory/legacy/prompt.py::priority_to_salience`

- 功能：priority → salience 兼容映射
- 输入：`priority, default: float=0.5`。
- 输出：`float；(max(60, min(100, priority)) - 60) / 40；default`。
- 作用：调用 isinstance, math.isfinite, max, min。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L96)。

### `hybrid_memory/legacy/prompt.py::parse_ids`

- 功能：模型/旧缓存的 ID 列表：兼容十进制字符串和整值浮点，不截断小数。 只保留非负 SQLite INTEGER 范围，避免 bool、NaN 和超大整数污染溯源。
- 输入：`values`。
- 输出：`list[int]；[]；out`。
- 作用：调用 int, isinstance, out.append, value.is_integer, value.strip, value.strip().isdecimal。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/prompt.py#L103)。

### `hybrid_memory/legacy/prompt.py::parse_candidate`

- 功能：宽松候选解析；公共 parse 目标迁 guards
- 输入：`item: dict | str`。
- 输出：`MemoryCandidate | None；MemoryCandidate(text=redact_secrets(text.strip()), type=str(item.get('type', '')), priority=item.get('priority') if type(item.get('priority')) is int else None, source_unit_ids=tuple(parse_ids(src)), salience=salience)；None`。
- 作用：调用 MemoryCandidate, isinstance, item.get, parse_ids, parse_salience, priority_to_salience, redact_secrets, str, text.strip, tuple, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/prompt.py#L127)。

### `hybrid_memory/legacy/prompt.py::parse_generation`

- 功能：解析 v2/v1，容忍围栏/前言；无合法载荷抛 ValueError，不伪装成空结果。
- 输入：`text: str`。
- 输出：`CandidateGeneration；CandidateGeneration(tuple((c for item in items if isinstance(item, dict) and (c := parse_candidate(item)) is not None)), scene)`。
- 作用：调用 CandidateGeneration, ValueError, decoder.raw_decode, isinstance, json.JSONDecoder, match.start, obj.get, parse_candidate, re.search, str, tuple。
- 错误：异常 ValueError('no valid candidate generation JSON')。
- 目标：`hybrid_memory/legacy/prompt.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/prompt.py#L147)。

## `hybrid_memory/legacy/worker.py`

- 模块功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/legacy/worker.py`（当前路径）。
- 模块输入：裸引擎信号与语义实现。
- 模块输出：阶段统计；锁外模型、锁内提交，易失队列语义保留。
- 源校验：`48f6e00de316d67cfbcdeee5af5fd484edfbc1a1a0fdf0e04b18edcc03a116c2`。

### `hybrid_memory/legacy/worker.py::_requeue_merge`

- 功能：回队信号的合并规则：list payload 去重拼接，其余取新。
- 输入：`old, new`。
- 输出：`未注解；new；old + [x for x in new if x not in old]`。
- 作用：调用 isinstance。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/worker.py#L34)。

### `hybrid_memory/legacy/worker.py::SignalWorker`

- 功能：裸引擎内存信号消费者（易失队列语义）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：按本项目标契约实施；[源码](../hybrid_memory/legacy/worker.py#L41)。

### `hybrid_memory/legacy/worker.py::SignalWorker.__init__`

- 功能：用给定参数与依赖初始化 SignalWorker，建立其对象状态；业务归属为显式 legacy 管线和裸引擎消费者；不在默认管线暗调
- 输入：`self, eng, semantics, lock=None`。
- 输出：`未注解；None`。
- 作用：调用 nullcontext。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/worker.py#L42)。

### `hybrid_memory/legacy/worker.py::SignalWorker.process`

- 功能：处理自己那部分信号。kinds 非 None 时只处理指定种类（仍限于本 worker 认识的种类）。失败的信号回队重试。返回处理统计。
- 输入：`self, t: int, kinds: set | None=None`。
- 输出：`dict；stats`。
- 作用：调用 print, requeue.append, self._consolidate, self._judge, self._recognize, self.eng.signals.emit, self.eng.signals.take, set, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/worker.py#L49)。

### `hybrid_memory/legacy/worker.py::SignalWorker._judge`

- 功能：对一批 tension 对调 judge 并批量回报。死对/链塌缩对以 pending 回报——submit_verdicts 的清理路径会摘掉对应 tension。
- 输入：`self, pairs, t: int, stats: dict`。
- 输出：`int；self.eng.submit_verdicts(verdicts, t)`。
- 作用：调用 jobs.append, maintenance.follow_chain, seen.add, self.eng.mems.get, self.eng.submit_verdicts, self.sem.judge, set, sorted, tuple, verdicts.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/worker.py#L82)。

### `hybrid_memory/legacy/worker.py::SignalWorker._recognize`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, payload, t: int, stats: dict`。
- 输出：`int；0；self.eng.submit_relevance(ret, used, t)`。
- 作用：调用 fn, isinstance, len, print, self.eng.submit_relevance。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/worker.py#L117)。

### `hybrid_memory/legacy/worker.py::SignalWorker._consolidate`

- 功能：显式 legacy 管线和裸引擎消费者；不在默认管线暗调 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, payload, t: int`。
- 输出：`int；0；1`。
- 作用：调用 is_visible, isinstance, len, self.eng.add_reflection, self.eng.mems.get, self.sem.consolidate, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/legacy/worker.py`；处置：兼容保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/legacy/worker.py#L144)。

## `hybrid_memory/llm.py`

- 模块功能：智谱 chat 客户端旧导入位；真实实现已迁入 llm/client.py。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/llm.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：llm.client 对应符号 re-export。
- 源校验：`14f47ae676dc0036c34b1e910a085d01d65889253d5d417efd331c979d22e173`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：annotations ← __future__.annotations；Request ← urllib.request.Request；urlopen ← urllib.request.urlopen；BASE_URL ← .llm.client.BASE_URL；ZhipuChatError ← .llm.client.ZhipuChatError；_cache_lookup ← .llm.client._cache_lookup；_cache_store ← .llm.client._cache_store；_post_chat ← .llm.client._post_chat；chat ← .llm.client.chat；chat_messages ← .llm.client.chat_messages；__all__ = ['BASE_URL', 'Request', 'ZhipuChatError', '_cache_lookup', '_cache_store', '_post_chat', 'chat', 'chat_messages', 'os', 'time', 'urlopen']

## `hybrid_memory/llm/__init__.py`

- 模块功能：ZAI chat 传输、重试和响应缓存。
- 设计归属：模型适配；处置：保留。
- 目标路径：`hybrid_memory/llm/__init__.py`（当前路径）。
- 模块输入：llm 包导入。
- 模块输出：客户端函数与异常 re-export。
- 源校验：`4c1b87234e6c6fa79c48ee85d9a031fd065fa7e5606d33dad7bfab893514d676`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：annotations ← __future__.annotations；Request ← urllib.request.Request；urlopen ← urllib.request.urlopen；BASE_URL ← .client.BASE_URL；ZhipuChatError ← .client.ZhipuChatError；_cache_lookup ← .client._cache_lookup；_cache_store ← .client._cache_store；_post_chat ← .client._post_chat；chat ← .client.chat；chat_messages ← .client.chat_messages；__all__ = ['BASE_URL', 'Request', 'ZhipuChatError', '_cache_lookup', '_cache_store', '_post_chat', 'chat', 'chat_messages', 'os', 'time', 'urlopen']

## `hybrid_memory/llm/client.py`

- 模块功能：ZAI chat 传输、重试和响应缓存。
- 设计归属：模型适配；处置：保留。
- 目标路径：`hybrid_memory/llm/client.py`（当前路径）。
- 模块输入：OpenAI 兼容 chat 请求、凭据、模型与磁盘缓存目录。
- 模块输出：message/文本结果或 ZhipuChatError；缓存命中不证明新推理。
- 源校验：`f0082d60beb44df85d4e9287db833cd8ca88861a4deb8effc19b320fe9bdc3a1`。

### `hybrid_memory/llm/client.py::ZhipuChatError`

- 功能：chat 传输/结构错误
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 RuntimeError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/llm/client.py#L24)。

### `hybrid_memory/llm/client.py::_urlopen_compat`

- 功能：ZAI chat 传输、重试和响应缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`req, timeout=60.0`。
- 输出：`未注解；fn(req, timeout=timeout)`。
- 作用：调用 fn, getattr, sys.modules.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L28)。

### `hybrid_memory/llm/client.py::_sleep_compat`

- 功能：ZAI chat 传输、重试和响应缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`dur`。
- 输出：`未注解；m_time.sleep(dur)`。
- 作用：调用 getattr, m_time.sleep, sys.modules.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L34)。

### `hybrid_memory/llm/client.py::_os_replace_compat`

- 功能：ZAI chat 传输、重试和响应缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`src, dst`。
- 输出：`未注解；m_os.replace(src, dst)`。
- 作用：调用 getattr, m_os.replace, sys.modules.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L40)。

### `hybrid_memory/llm/client.py::_post_chat`

- 功能：POST /chat/completions → choices[0].message（dict）。失败抛 ZhipuChatError。
- 输入：`key: str, body: dict, timeout: float, max_retries: int`。
- 输出：`dict；msg`。
- 作用：调用 Request, ZhipuChatError, _sleep_compat, _urlopen_compat, isinstance, json.dumps, json.dumps(body).encode, json.loads, range, resp.read, type。
- 错误：异常 ZhipuChatError('invalid chat response'), ZhipuChatError(f'HTTP {exc.code}'), ZhipuChatError(f'transport: {type(exc).__name__}')。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L46)。

### `hybrid_memory/llm/client.py::chat_messages`

- 功能：多轮 + function calling：返回 assistant message（可能带 tool_calls）。 调查员回路用；不缓存（载荷含唯一 signal_id，缓存永不命中）。
- 输入：`messages: list, *, tools: list | None=None, api_key: str | None=None, model: str='glm-5.3-flash', timeout: float=120.0, max_retries: int=2, temperature: float=0.0`。
- 输出：`dict；_post_chat(key, body, timeout, max_retries)`。
- 作用：调用 ZhipuChatError, _post_chat, os.environ.get。
- 错误：异常 ZhipuChatError('ZAI_API_KEY is not set')。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L77)。

### `hybrid_memory/llm/client.py::_cache_lookup`

- 功能：ZAI chat 传输、重试和响应缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`cache_dir: Path, ck: str`。
- 输出：`str | None；None；out if isinstance(out, str) else None`。
- 作用：调用 (cache_dir / f'{ck}.json').read_text, isinstance, json.loads。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L92)。

### `hybrid_memory/llm/client.py::_cache_store`

- 功能：ZAI chat 传输、重试和响应缓存 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`cache_dir: Path, ck: str, out: str`。
- 输出：`None；None`。
- 作用：调用 Path, Path(name).unlink, _os_replace_compat, cache_dir.mkdir, json.dump, os.fdopen, tempfile.mkstemp。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/llm/client.py#L101)。

### `hybrid_memory/llm/client.py::chat`

- 功能：单轮 chat
- 输入：`凭据/模型/system/user/超时/重试/缓存目录`。
- 输出：`content 文本`。
- 作用：磁盘缓存命中可复用；无则请求。
- 错误：缺凭据/传输/结构错误 ZhipuChatError。
- 目标：`hybrid_memory/llm/client.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/llm/client.py#L112)。

## `hybrid_memory/logstore.py`

- 模块功能：LogStore 旧导入位；真实实现已迁入 store/evidence.py。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/logstore.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：store.evidence 对应符号 re-export。
- 源校验：`0fa7a1eec1e359495432b246408048a45b60585a2a5715d6044203fa9cec5637`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：annotations ← __future__.annotations；LogStore ← .store.evidence.LogStore；_fts_expr ← .store.evidence._fts_expr；_snippet ← .store.evidence._snippet；_tokens ← .store.evidence._tokens；entities_in ← .store.evidence.entities_in；__all__ = ['LogStore', 'entities_in', '_tokens', '_fts_expr', '_snippet']

## `hybrid_memory/semantics/__init__.py`

- 模块功能：存量 judge、反馈归因及 reflection 语义通路。
- 设计归属：模型适配；处置：显式化。
- 目标路径：`hybrid_memory/semantics/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：RealChatSemantics/normalize 同一对象。
- 源校验：`fc7d05697ca76b40e13c66341965ed070f04239c9ee5de4026629526d2c4da05`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：RealChatSemantics ← .real.RealChatSemantics；normalize ← .real.normalize；__all__ = ['RealChatSemantics', 'normalize']

## `hybrid_memory/semantics/llm.py`

- 模块功能：存量 judge、反馈归因及 reflection 语义通路。
- 设计归属：模型适配；处置：显式化。
- 目标路径：`hybrid_memory/semantics/llm.py`（当前路径）。
- 模块输入：判定输入、注入 chat 或客户端与缓存。
- 模块输出：verdict、used 列表或 None、reflection Event 或 None；失败必须外显。
- 源校验：`8f0f29b7358bf35c3eb981b1a44fc93ffddabc6e7728d65441cd6bea55b846a7`。

### `hybrid_memory/semantics/llm.py::_one_word`

- 功能：存量 judge、反馈归因及 reflection 语义通路 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`out: str`。
- 输出：`str；'pending'；x`。
- 作用：调用 out.lower, re.findall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/llm.py#L46)。

### `hybrid_memory/semantics/llm.py::_index_set`

- 功能：解析 "1,3" / "NONE" → bool 列表；解析失败返回 None。 NONE 容忍尾部标点（"NONE."）：否则被判成识别失败 → worker 退化 全记——本意是"一条都没用上"反而变成全记，指标直接反过来。
- 输入：`out: str, n: int`。
- 输出：`list[bool] | None；[False] * n if s == 'none' else None；[i in idx for i in range(n)] if idx else None`。
- 作用：调用 idx.add, int, out.strip, out.strip().lower, out.strip().lower().rstrip, range, re.findall, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/llm.py#L54)。

### `hybrid_memory/semantics/llm.py::LLMSemantics`

- 功能：在线裁判实现：judge/归因/巩固
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 RealChatSemantics`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/llm.py#L69)。

### `hybrid_memory/semantics/llm.py::LLMSemantics.__init__`

- 功能：用给定参数与依赖初始化 LLMSemantics，建立其对象状态；业务归属为存量 judge、反馈归因及 reflection 语义通路
- 输入：`self, labels_path: str | Path | None=None, chat_fn=None, model: str='glm-5.3-flash', cache_dir: Path | None=None, api_key: str | None=None`。
- 输出：`未注解；None`。
- 作用：调用 super, super().__init__。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/llm.py#L70)。

### `hybrid_memory/semantics/llm.py::LLMSemantics._chat`

- 功能：存量 judge、反馈归因及 reflection 语义通路 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, system: str, user: str`。
- 输出：`str；chat(api_key=self._api_key, model=self._model, system=system, user=user, cache_dir=self._cache)；self._fn(system, user)`。
- 作用：调用 chat, self._fn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/llm.py#L80)。

### `hybrid_memory/semantics/llm.py::LLMSemantics.judge`

- 功能：本地→LLM→失败 pending
- 输入：`self, a_bid: int, a_val: str, b_bid: int, b_val: str`。
- 输出：`str；'pending'；_one_word(self._chat(_JUDGE_SYS, f'A: {a_val}\nB: {b_val}'))；v`。
- 作用：调用 _one_word, self._chat, super, super().judge。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/llm.py#L86)。

### `hybrid_memory/semantics/llm.py::LLMSemantics.relevant_set`

- 功能：回答归因
- 输入：`texts、question、answer`。
- 输出：`bool 列表或 None`。
- 作用：失败 None 由调用方计数退化。
- 错误：None 不是 NONE（NONE 是合法没用）。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/llm.py#L95)。

### `hybrid_memory/semantics/llm.py::LLMSemantics.consolidate`

- 功能：巩固回调：按时间标注的记忆 → 一条高层状态 Event；失败/NONE → None。
- 输入：`self, memories, t: int`。
- 输出：`Event | None；Event(belief_id=self.fingerprint(text), value=normalize(text), text=text, src=tuple(sorted(frozenset().union(*(m.src for m in memories)))), salience=max((m.salience for m in memories)), kind='reflection', derived_from=tuple((m.id for m in memories)), conf_pos=min((m.conf_pos for m in memories)), conf_neg=max((m.conf_neg for m in memories)), scene=memories[0].scene)；None`。
- 作用：调用 '\n'.join, Event, frozenset, frozenset().union, max, min, normalize, out.lower, redact_secrets, self._chat, self._chat(_CONSOLIDATE_SYS, user).strip, self.fingerprint, sorted, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/llm.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/llm.py#L108)。

## `hybrid_memory/semantics/provider.py`

- 模块功能：SemanticsProvider 双语义通路与健康可观测性。
- 设计归属：模型适配；处置：显式化。
- 目标路径：`hybrid_memory/semantics/provider.py`（当前路径）。
- 模块输入：两段值/指纹、实际展示记忆、reflection 记忆列表与时间步。
- 模块输出：verdict 判定、used bool 列表、reflection Event 与 health 观测。
- 源校验：`dcf11fb936189e0ffdfc49897f4c995dc1e3efe74fd9e038d88204f1b2f9beda`。

### `hybrid_memory/semantics/provider.py::SemanticsProvider`

- 功能：双语义通路提供者：封装 judge、relevant_set、consolidate 并提供 health()。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/provider.py#L11)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.__init__`

- 功能：用给定参数与依赖初始化 SemanticsProvider，建立其对象状态；业务归属为SemanticsProvider 双语义通路与健康可观测性
- 输入：`self, delegate: RealChatSemantics | None=None, *, provider: str='zhipu', model: str='glm-5.3-flash'`。
- 输出：`未注解；None`。
- 作用：调用 LLMSemantics。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/provider.py#L14)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.health`

- 功能：双语义通路的可观测健康段
- 输入：`无参数；provider/model 与内部计数`。
- 输出：`{provider,model,calls,failures,last_error}`。
- 作用：只读；合法 NONE 与 transport/parse 失败分开计数。
- 错误：读取失败返回 last_error，不外抛掩盖真实任务错误。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/provider.py#L23)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.judge`

- 功能：存量张力关系判定包装
- 输入：`两段值/指纹与当前计数`。
- 输出：`verdict 字符串（含 pending）`。
- 作用：调用配置的 chat；锁外执行。
- 错误：传输失败返回 pending 并计入 failures，不冒充关系。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/provider.py#L33)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.relevant_set`

- 功能：实际展示记忆归因包装
- 输入：`texts、question、answer`。
- 输出：`bool 列表或 None`。
- 作用：失败计数外显；退化 selected-hit 由调用方负责。
- 错误：None=失败，NONE=合法没用，两者不得混同。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/provider.py#L43)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.consolidate`

- 功能：reflection 语义包装
- 输入：`Memory 列表与 t`。
- 输出：`Event 或 None`。
- 作用：返回前脱敏；来源并集。
- 错误：失败与合法 NONE 分开记录。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/provider.py#L54)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.fingerprint`

- 功能：委托 `self.delegate.fingerprint` 执行；边界与失败由被调用方契约承担
- 输入：`self, text: str`。
- 输出：`int；self.delegate.fingerprint(text)`。
- 作用：调用 self.delegate.fingerprint。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/provider.py#L64)。

### `hybrid_memory/semantics/provider.py::SemanticsProvider.scope`

- 功能：委托 `self.delegate.scope` 执行；边界与失败由被调用方契约承担
- 输入：`self, belief_id: int`。
- 输出：`未注解；self.delegate.scope(belief_id)`。
- 作用：调用 self.delegate.scope。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/provider.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/provider.py#L67)。

## `hybrid_memory/semantics/real.py`

- 模块功能：存量 judge、反馈归因及 reflection 语义通路。
- 设计归属：模型适配；处置：显式化。
- 目标路径：`hybrid_memory/semantics/real.py`（当前路径）。
- 模块输入：文本或标注文件。
- 模块输出：规范文本、指纹与本地判定；relevant/valid 恒真仅为无真值兼容。
- 源校验：`e7d0b09dae520663425b52057a869afd9dd223b88110c3328f51df4161141ccf`。

### `hybrid_memory/semantics/real.py::normalize`

- 功能：委托 `_PUNCT.sub('', _WS.sub('', text)).lower` 执行；边界与失败由被调用方契约承担
- 输入：`text: str`。
- 输出：`str；_PUNCT.sub('', _WS.sub('', text)).lower()`。
- 作用：调用 _PUNCT.sub, _PUNCT.sub('', _WS.sub('', text)).lower, _WS.sub。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/real.py#L27)。

### `hybrid_memory/semantics/real.py::RealChatSemantics`

- 功能：labels_path 指向 JSONL：{"a": textA, "b": textB, "verdict": ...}。 无文件/未命中 → pending。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/real.py#L31)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.__init__`

- 功能：用给定参数与依赖初始化 RealChatSemantics，建立其对象状态；业务归属为存量 judge、反馈归因及 reflection 语义通路
- 输入：`self, labels_path: str | Path | None=None`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(labels_path).exists, Path(labels_path).read_text, Path(labels_path).read_text(encoding='utf-8').splitlines, json.loads, line.strip, normalize, row.get, sorted, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/real.py#L35)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.fingerprint`

- 功能：委托 `zlib.crc32` 执行；边界与失败由被调用方契约承担
- 输入：`text: str`。
- 输出：`int；zlib.crc32(normalize(text).encode('utf-8'))`。
- 作用：调用 normalize, normalize(text).encode, zlib.crc32。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：保留当前签名与 IO；[源码](../hybrid_memory/semantics/real.py#L49)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.judge`

- 功能：精确同值/标注/pending
- 输入：`self, a_bid: int, a_val: str, b_bid: int, b_val: str`。
- 输出：`str；'synonym'；self.labels.get(tuple(sorted((a_val, b_val))), 'pending')`。
- 作用：调用 self.labels.get, sorted, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/real.py#L53)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.relevant`

- 功能：恒真（无真值兼容）
- 输入：`self, belief_id: int, value: str, query, t: int`。
- 输出：`bool；True`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/real.py#L58)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.valid`

- 功能：恒真（无真值兼容）
- 输入：`self, belief_id: int, value: str, t: int`。
- 输出：`bool；True`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/real.py#L61)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.embedding_key`

- 功能：(value,) 缓存键
- 输入：`self, belief_id: int, value: str`。
- 输出：`tuple；(value,)`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/real.py#L64)。

### `hybrid_memory/semantics/real.py::RealChatSemantics.scope`

- 功能：未知 scope 返回空串
- 输入：`self, belief_id: int`。
- 输出：`str；''`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/semantics/real.py`；处置：显式化；变更：按本项目标契约实施；[源码](../hybrid_memory/semantics/real.py#L67)。

## `hybrid_memory/server.py`

- 模块功能：python -m hybrid_memory.server 的部署入口。
- 设计归属：传输与部署；处置：兼容保留。
- 目标路径：`hybrid_memory/server.py`（当前路径）。
- 模块输入：`python -m hybrid_memory.server` 的进程参数。
- 模块输出：兼容导出 MemoryService/serve/build_default_service/main；无独立业务逻辑。
- 源校验：`0641017036494638f920a50d1ea662aa6544a50706b995f6c8201c2f344ae8c0`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：MemoryService ← .service.service.MemoryService；ProposalRejected ← .service.service.ProposalRejected；build_default_service ← .transport.bootstrap.build_default_service；main ← .transport.bootstrap.main；serve ← .transport.http.serve

## `hybrid_memory/service/__init__.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`b19f3055bea28c7c05d5a327261567f67e1b2d4b2577a85f56cb21e69c287b0d`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/service/budgets.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/budgets.py`（当前路径）。
- 模块输入：signal 与 tool/window/before 限额。
- 模块输出：调查上下文、预算使用与回展预留；超限区分 403/429。
- 源校验：`0b58df211abfe1befa52885d2dd697f935da4247317d53e9e7a4213f1e2dd90c`。

### `hybrid_memory/service/budgets.py::open_budget`

- 功能：打开一次调查并返回仅供进程内最终 JSON 使用的不可变上下文。 HTTP 工具必须使用活跃 signal_id；不能提供此对象跳过计量。
- 输入：`svc, signal_id: str, *, tool_calls: int, window_chars: int, before: int, origin: str | None=None, task_id: int | None=None, lease_token: str | None=None`。
- 输出：`InvestigationContext；ctx`。
- 作用：调用 InvestigationContext, ValueError, isinstance, signal_id.strip, time.time, type。
- 错误：异常 ValueError('signal_id required'), ValueError(f'signal {signal_id} already open'), ValueError(f'{name} must be a non-negative int')。
- 目标：`hybrid_memory/service/budgets.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/budgets.py#L17)。

### `hybrid_memory/service/budgets.py::close_budget`

- 功能：关闭预算并返回 calls/window_used/reserved/elapsed
- 输入：`svc, signal_id: str`。
- 输出：`dict；{'calls': bud['calls'], 'window_used': bud['window_used'], 'window_reserved': bud['window_reserved'], 'elapsed_s': round(time.time() - bud['opened'], 1)}；{}`。
- 作用：调用 round, svc._budgets.pop, time.time。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/budgets.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/budgets.py#L43)。

### `hybrid_memory/service/budgets.py::admit`

- 功能：同一临界区内校验存活、计调用、固定因果界，并预留回展额度。 返回不可变上下文、该次预算对象和预留量。I/O 后只用这些对象， 不再按 signal_id 二次查找，避免 close/reopen 丢失边界或串账。 calls 统计尝试次数（含 429），window_used 只统计成功返回的原文字数。
- 输入：`svc, signal_id: str | None, before: int | None=None, *, window: bool=False, max_chars: int | None=None`。
- 输出：`tuple[InvestigationContext, dict | None, int]；(ctx, bud, cap)`。
- 作用：调用 InvestigationContext, PermissionError, SignalClosed, ValueError, min, replace, svc._budgets.get, svc._ensure_healthy, svc.tasks.check_owned, type。
- 错误：异常 PermissionError('该信号回展预算已用尽（含在途预留）'), PermissionError(f"该信号工具调用预算 {bud['tool_calls']} 已用尽，请立即汇总输出"), SignalClosed(f'signal {signal_id} 已关闭或不存在'), ValueError('before must be a non-negative int'), ValueError('max_chars must be a positive int')。
- 目标：`hybrid_memory/service/budgets.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/budgets.py#L53)。

## `hybrid_memory/service/context.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/context.py`（当前路径）。
- 模块输入：signal_id/before/origin/task/lease 与错误原因。
- 模块输出：不可变调查上下文与权限/因果异常；HTTP 不能伪造。
- 源校验：`8a0774448cbe8c81bf03d22043c510910f7dc6ff933724e12ece0548f0d6f1a7`。

### `hybrid_memory/service/context.py::InvestigationContext`

- 功能：不可变调查上下文：signal/before/origin/task/lease
- 输入：`signal_id: str | None；before: int | None；origin: str = 'agent'；task_id: int | None = None；lease_token: str | None = None`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/service/context.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/context.py#L9)。

### `hybrid_memory/service/context.py::SignalClosed`

- 功能：调查已关闭、不存在，或该端点不允许调查调用（HTTP 403）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Exception`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/service/context.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/context.py#L17)。

### `hybrid_memory/service/context.py::CausalViolation`

- 功能：操作指向未知或因果上界外的记忆（HTTP 403）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Exception`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/service/context.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/context.py#L21)。

## `hybrid_memory/service/feedback.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/feedback.py`（当前路径）。
- 模块输入：retrieval_id、问答与 request_id。
- 模块输出：归因接受回执或稳定 unknown/duplicate；效果已提交不因模型失败翻转。
- 源校验：`7ea592442a3169f778bb40380d4be2aba769e811a16184c0755c1632c67ab51a`。

### `hybrid_memory/service/feedback.py::feedback`

- 功能：回答后归因
- 输入：`retrieval_id、q、a、request_id`。
- 输出：`n_useful/pending/accepted/worker/retrieval_id/request_id/replayed 或 error`。
- 作用：capture 重放优先；封展示快照。
- 错误：重复已结清返回稳定错误；效果已提交不翻转。
- 目标：`hybrid_memory/service/feedback.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/feedback.py#L13)。

### `hybrid_memory/service/feedback.py::feedback.mutate`

- 功能：登记 feedback_sent 并发持久归因任务
- 输入：`无参数`。
- 输出：`未注解；{'n_useful': 0, 'pending': True, 'accepted': True, 'retrieval_id': retrieval_id, **({'request_id': request_id} if request_id else {})}`。
- 作用：调用 svc.engine.feedback。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/feedback.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/feedback.py#L50)。

## `hybrid_memory/service/lifecycle.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/lifecycle.py`（当前路径）。
- 模块输入：state_dir、stores 与线程生命周期。
- 模块输出：恢复/健康/保存/单元补确认；坏 checkpoint 拒绝、坏 pkl 隔离。
- 源校验：`320a8158466c51f14208550c8c63072468f02851132af87fb3a9fd44bf5456b4`。

### `hybrid_memory/service/lifecycle.py::recover_or_init`

- 功能：启动恢复
- 输入：`svc`。
- 输出：`None`。
- 作用：checkpoint→pkl→空；对齐游标；挂信号出口。
- 错误：坏 checkpoint 拒绝启动；坏 pkl 隔离空启。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/lifecycle.py#L15)。

### `hybrid_memory/service/lifecycle.py::ensure_healthy`

- 功能：checkpoint fault 时拒绝写入
- 输入：`svc`。
- 输出：`None；None`。
- 作用：调用 CheckpointConflict。
- 错误：异常 CheckpointConflict('checkpoint 状态不确定或已被其他实例推进；请重启服务')。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/lifecycle.py#L64)。

### `hybrid_memory/service/lifecycle.py::corrupt_file_exists`

- 功能：委托 `bool` 执行；边界与失败由被调用方契约承担
- 输入：`svc`。
- 输出：`bool；bool(svc.state_path and svc.state_path.with_suffix('.corrupt').exists())`。
- 作用：调用 bool, svc.state_path.with_suffix, svc.state_path.with_suffix('.corrupt').exists。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/lifecycle.py#L69)。

### `hybrid_memory/service/lifecycle.py::save`

- 功能：权威保存
- 输入：`svc`。
- 输出：`{'saved':bool,'mems'|'reason'}`。
- 作用：先 checkpoint 再原子导出 pkl。
- 错误：不得洗掉 quarantined。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/lifecycle.py#L73)。

### `hybrid_memory/service/lifecycle.py::start_unit_recovery`

- 功能：启动单元补确认线程
- 输入：`svc`。
- 输出：`None；None`。
- 作用：调用 svc._unit_stop.clear, svc._unit_thread.is_alive, svc._unit_thread.start, threading.Thread。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/lifecycle.py#L96)。

### `hybrid_memory/service/lifecycle.py::start_unit_recovery.loop`

- 功能：循环补 L0 交接与确认
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 print, process, svc._unit_stop.is_set, svc._unit_wake.clear, svc._unit_wake.wait, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/lifecycle.py#L101)。

### `hybrid_memory/service/lifecycle.py::stop_unit_recovery`

- 功能：有界停止并报告未停超时
- 输入：`svc, timeout: float=5.0`。
- 输出：`None；None`。
- 作用：调用 svc._unit_stop.set, svc._unit_thread.join, svc._unit_wake.set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/lifecycle.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/lifecycle.py#L120)。

## `hybrid_memory/service/observe.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/observe.py`（当前路径）。
- 模块输入：一轮 user/assistant、request_id 与有序单元工作。
- 模块输出：接受回执与逐单元交付回执；先持久证据再效果，重放不推进时钟。
- 源校验：`f38062997515e809764b0bb99de41fa63e1cd051819305a600c4d6c29e4d23e8`。

### `hybrid_memory/service/observe.py::_annotate_observe`

- 功能：将内部单元回执整形成外部接受/重放响应
- 输入：`body: dict, unit_id: int, *, replayed: bool, request_id: str | None`。
- 输出：`dict；out`。
- 作用：调用 body.items。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/observe.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/observe.py#L25)。

### `hybrid_memory/service/observe.py::observe`

- 功能：交互接受与单元处理
- 输入：`user/assistant/request_id`。
- 输出：`accepted/unit_id/pending/pool/t/replayed/request_id/worker`。
- 作用：先 L0+work 再效果；队满说明证据已接受。
- 错误：重放不推进时钟；不丢已接受证据。
- 目标：`hybrid_memory/service/observe.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/observe.py#L37)。

### `hybrid_memory/service/observe.py::process_pending_units`

- 功能：按原 L0 顺序处理；同服务仅一个处理器。不得越过退避中的旧单元。
- 输入：`svc, limit: int=8`。
- 输出：`dict[int, dict]；completed；{}`。
- 作用：调用 process_unit, svc._ensure_healthy, svc._unit_busy.acquire, svc._unit_busy.release, svc.log.fail_work, svc.log.pending_units, svc.log.work, svc.tasks.unit_receipt, time.time。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/observe.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/observe.py#L85)。

### `hybrid_memory/service/observe.py::process_unit`

- 功能：单单元交付
- 输入：`uid、work`。
- 输出：`交付回执+worker 统计`。
- 作用：准备→原子效果/接力/回执→finish_work。
- 错误：失败留 pending 与退避；重复只读回执。
- 目标：`hybrid_memory/service/observe.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/observe.py#L107)。

### `hybrid_memory/service/observe.py::process_unit.collect`

- 功能：单元事务内收集 handoffs
- 输入：`kind, payload, at, key, merge`。
- 输出：`未注解；-1；old_emit(kind, payload, at, key, merge)`。
- 作用：调用 handoffs.append, old_emit, svc._signal_payload。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/observe.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/observe.py#L139)。

### `hybrid_memory/service/observe.py::process_unit.mutate`

- 功能：推进游标/场景/信号并产生单元回执
- 输入：`无参数`。
- 输出：`未注解；{'unit_id': uid, 'candidates': len(evs), 'scene': svc._scene, 'reasons': list(reasons), 'pool': svc.engine.pool_sizes(), 't': svc._t, 'next_memory_id': svc.engine._next_id}`。
- 作用：调用 Event, _content_grounded, cand.get, entities_in, grounded.append, len, list, max, normalize, svc.engine.observe, svc.engine.pool_sizes, svc.engine.report_miss, svc.engine.report_unit, svc.engine.signals.emit, svc.engine.step, svc.semantics.fingerprint, triggers.is_correction, triggers.is_dissatisfaction, tuple, work['context'].get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/observe.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/observe.py#L145)。

## `hybrid_memory/service/operate.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/operate.py`（当前路径）。
- 模块输入：Legacy 提议/裁决/诊断/缺失与可信 context。
- 模块输出：逐条回执、裁决计数与诊断统计；公开直写 Trio 拒绝、Legacy 立即 checkpoint。
- 源校验：`09122eb0c9b69cbb71f9e06f4210b1d534e376dc67bc291e9ce1400c902b674a`。

### `hybrid_memory/service/operate.py::_cited_text`

- 功能：单项目编排、因果界、读取及人审 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`svc, unit_ids`。
- 输出：`str；'\n'.join(parts)`。
- 作用：调用 '\n'.join, parts.append, svc.log.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/operate.py#L39)。

### `hybrid_memory/service/operate.py::validate_proposal`

- 功能：提议校验：来源/因果/脱敏/自指/浅接地
- 输入：`svc, p: dict, before: int | None`。
- 输出：`tuple[Event, list[int]]；(ev, sup)`。
- 作用：调用 Event, ProposalRejected, _SELF_REF_RE.search, _cited_text, _content_grounded, ek.strip, isinstance, len, normalize, p.get, parse_ids, parse_salience, redact_secrets, set, sorted, svc.log.exists, svc.semantics.fingerprint, text.strip, tuple。
- 错误：异常 ProposalRejected('empty_text'), ProposalRejected('no_source'), ProposalRejected('self_reference'), ProposalRejected('supersedes_must_be_list'), ProposalRejected('ungrounded_content'), ProposalRejected(f'too_long>{_MAX_PROPOSAL_CHARS}'), ProposalRejected(f'unknown_or_future_source:{bad}')。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L50)。

### `hybrid_memory/service/operate.py::_task_once`

- 功能：调用方持服务锁；操作、checkpoint、回执同事务。
- 输入：`svc, ctx, request, mutate`。
- 输出：`未注解；dict(out, replayed=replayed)`。
- 作用：调用 dict, svc._rollback_effect, svc.tasks.apply_operation。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/operate.py#L84)。

### `hybrid_memory/service/operate.py::durable_propose`

- 功能：任务上下文内的幂等提议与回执
- 输入：`svc, proposals, ctx`。
- 输出：`未注解；{'accepted': accepted, 'new_ids': ids, 'merged': accepted - len(ids), 'rejected': rejected, 'replayed': replayed, 'applied': applied, 'origin': ctx.origin, 'pool': svc.engine.pool_sizes(), 't': svc._t}`。
- 作用：调用 _task_once, dict, enumerate, ids.extend, int, len, list, rejected.extend, replace, set, sorted, svc.engine.pool_sizes, validate_proposal。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L94)。

### `hybrid_memory/service/operate.py::report_miss`

- 功能：缺失上报
- 输入：`query/hint/source`。
- 输出：`{'queued':n,'t':t}`。
- 作用：Legacy 持久调查；Trio 必须拒绝。
- 错误：Trio 拒绝而非制造孤儿任务。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L119)。

### `hybrid_memory/service/operate.py::resolve`

- 功能：裁决回报
- 输入：`left/right/verdict/entity/ensure/context`。
- 输出：`{'resolved':n,'t':t}`。
- 作用：因果与版本复核、登记张力、幂等操作。
- 错误：人审冻结/越界拒绝；重复返回 replayed。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L134)。

### `hybrid_memory/service/operate.py::resolve.mutate`

- 功能：裁决与实体回填的实际效果
- 输入：`无参数`。
- 输出：`未注解；{'resolved': n, 't': svc._t}`。
- 作用：调用 svc.engine.add_tension, svc.engine.submit_verdicts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L159)。

### `hybrid_memory/service/operate.py::propose`

- 功能：Legacy 提议入库
- 输入：`proposals、origin、signal/context`。
- 输出：`accepted/new_ids/merged/rejected[...]/origin/pool/t`。
- 作用：逐条校验；Legacy 立即 checkpoint；Trio 走 Selector。
- 错误：逐条拒绝保留原因；不可部分伪成功。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L174)。

### `hybrid_memory/service/operate.py::diagnose`

- 功能：记录 miss_type、计数与审计
- 输入：`svc, miss_type: str, note: str='', *, signal_id: str | None=None, kind: str='', usage: dict | None=None, _context: InvestigationContext | None=None, _audit=True`。
- 输出：`dict；_task_once(svc, ctx, {'action': 'diagnose', 'miss_type': miss_type, 'note': (note or '').strip()[:500]}, lambda: diagnose(svc, miss_type, note, kind=kind, usage=usage, _context=replace(ctx, task_id=None, lease_token=None), _audit=False))；{'miss_counts': counts}`。
- 作用：调用 (note or '').strip, ValueError, _task_once, dict, f.write, json.dumps, open, round, svc._admit, svc.miss_counts.get, time.time。
- 错误：异常 ValueError(f'miss_type must be one of {MISS_TYPES}')。
- 目标：`hybrid_memory/service/operate.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/operate.py#L228)。

## `hybrid_memory/service/recall.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/recall.py`（当前路径）。
- 模块输入：query/k/signal/budget/passive 与引擎状态。
- 模块输出：RecallResult、因果集与统一冲突视图；副本读取无副作用。
- 源校验：`3db5decaeb0f311f5366fa3c08668a1ce7de1d0cdbc4ecd08f2023e240aa5cb5`。

### `hybrid_memory/service/recall.py::_safe_mem_text`

- 功能：记忆文本进 <relevant-memories> 包裹块前的消毒：中和同名分隔符 （含嵌套/带属性/自闭合变体），防存储型注入破 tag 逃逸污染 system prompt。
- 输入：`text: str`。
- 输出：`str；_MEM_TAG_RE.sub(' ', text)`。
- 作用：调用 _MEM_TAG_RE.sub。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/recall.py#L29)。

### `hybrid_memory/service/recall.py::approx_tokens`

- 功能：与 TIDE 平台一致的近似 token 计数：CJK 单字 = 1，ASCII 词 = 1， 其余非空白符号 = 1。只用于预算截断，不追求与具体 tokenizer 对齐。
- 输入：`text: str`。
- 输出：`int；len(_TOKEN_RE.findall(text))`。
- 作用：调用 _TOKEN_RE.findall, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/recall.py#L36)。

### `hybrid_memory/service/recall.py::context_lines`

- 功能：渲染注入行；返回 (lines, truncated)。 H29/N20：contested 按入选记忆去重（首个对手胜出），总行数不超过 CONTESTED_K；有任何 contested 对被丢弃即 truncated=True。 对手被省略的入选条目，在主条目显式标注“[有未决冲突，不可断言为当前事实]”。
- 输入：`ret: Retrieval`。
- 输出：`tuple[list[tuple[str, object]], bool]；(lines, emitted != len(ret.contested))`。
- 作用：调用 _safe_mem_text, emitted_m_ids.add, emitted_set.remove, len, lines.append, set, shown.add。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/recall.py#L42)。

### `hybrid_memory/service/recall.py::causal_memory_ids`

- 功能：保守的当前版本过滤，不冒充历史版本重建；调用方持 service lock。 birth 不够：旧记忆也可能在未来被确认/合并，或携带未来来源。
- 输入：`svc, before: int | None`。
- 输出：`set[int]；eligible；set(svc.engine.mems)`。
- 作用：调用 any, set, svc.engine.mems.values, svc.log.exists。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/recall.py#L84)。

### `hybrid_memory/service/recall.py::causal_tensions`

- 功能：因果界内张力子集
- 输入：`svc, ids: set[int], before: int | None`。
- 输出：`dict；{pair: tension for pair, tension in svc.engine.tensions.items() if all((mid in ids for mid in pair)) and (before is None or tension.last_seen < before)}`。
- 作用：调用 all, svc.engine.tensions.items。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/recall.py#L106)。

### `hybrid_memory/service/recall.py::recall`

- 功能：统一召回入口
- 输入：`q/k/signal_id/budget_tokens/passive`。
- 输出：`RecallResult`。
- 作用：准入后 embed；主读取或因果副本。
- 错误：未准入不调 embedding。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/recall.py#L112)。

### `hybrid_memory/service/recall.py::recall_main`

- 功能：主动读取、rid 登记与统计
- 输入：`svc, q: str, k: int | None=None, budget_tokens: int | None=None`。
- 输出：`dict；out`。
- 作用：调用 svc._commit_sidecar_effect, svc._ensure_healthy, svc._unit_wake.set, svc.emb.embed。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/recall.py#L139)。

### `hybrid_memory/service/recall.py::recall_main.mutate`

- 功能：读取/登记/渲染的事务内实现
- 输入：`无参数`。
- 输出：`未注解；recall_result(ret, rid, budget_tokens)`。
- 作用：调用 Query, len, min, recall_result, svc._retrievals.items, svc._retrievals.pop, svc.engine.retrieve。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/recall.py#L145)。

### `hybrid_memory/service/recall.py::recall_result`

- 功能：上下文渲染与预算
- 输入：`Retrieval、rid、budget_tokens`。
- 输出：`retrieval_id/context/n/tokens/truncated/selected[...]`。
- 作用：整行裁剪；固定真实 presented_texts；省略对手必须标主条目。
- 错误：超预算整行丢弃并置 truncated。
- 目标：`hybrid_memory/service/recall.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/recall.py#L172)。

## `hybrid_memory/service/review.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/review.py`（当前路径）。
- 模块输入：人审台账、capability 与决策。
- 模块输出：待审列表、幂等决定与统一冲突台账；退役/变化即 stale。
- 源校验：`7e4a26e75d0dd8563f853cbcbc2ffa16583a605348b4cc8ef36328959abeea6a`。

### `hybrid_memory/service/review.py::review_token`

- 功能：Separate capability: ordinary plugin and agent bearer cannot approve conflicts.
- 输入：`svc`。
- 输出：`str；secrets.token_hex(24)；token`。
- 作用：调用 RuntimeError, os.chmod, p.exists, p.read_text, p.read_text(encoding='utf-8').strip, p.write_text, secrets.token_hex。
- 错误：异常 RuntimeError('human-review-token is empty')。
- 目标：`hybrid_memory/service/review.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/review.py#L9)。

### `hybrid_memory/service/review.py::human_reviews`

- 功能：待审列表+现有正文/来源/pool
- 输入：`svc`。
- 输出：`list[dict]；reviews`。
- 作用：调用 sorted, svc.engine.mems.get, svc.tasks.pending_reviews。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/review.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/review.py#L23)。

### `hybrid_memory/service/review.py::decide_human_review`

- 功能：人审决定
- 输入：`review_id、decision、capability`。
- 输出：`{'review_id','decision','new_ids','replayed'}`。
- 作用：双权校验、版本复核、原子 checkpoint、其他审批 stale。
- 错误：capability 错 403；目标变化 stale。
- 目标：`hybrid_memory/service/review.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/review.py#L34)。

### `hybrid_memory/service/review.py::conflict_ledger`

- 功能：冲突统一读模型
- 输入：`svc 与可选 before`。
- 输出：`{conflicts,tensions,pending_reviews,aggregates,pin_roots,truncated}`。
- 作用：只读汇总；不触发裁决或人审。
- 错误：越界正文不返回；缺失对象标 stale 而非隐藏。
- 目标：`hybrid_memory/service/review.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/review.py#L76)。

## `hybrid_memory/service/service.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/service.py`（当前路径）。
- 模块输入：cfg/embed/semantics/generator/stores 与业务请求。
- 模块输出：单项目门面回执与锁内状态；不放业务算法、不 import transport。
- 源校验：`efee662782bc359bfd13320b2aa7b3c25a5b950ff844fdf39f78a219eb6cb0ff`。

### `hybrid_memory/service/service.py::MemoryService`

- 功能：单项目服务门面：组装/锁/回路转发
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/service.py#L31)。

### `hybrid_memory/service/service.py::MemoryService.__init__`

- 功能：用给定参数与依赖初始化 MemoryService，建立其对象状态；业务归属为单项目编排、因果界、读取及人审
- 输入：`self, cfg: Cfg, emb: Embedder, semantics, generator: CandidateGenerator, state_dir: Path | None=None, logstore: LogStore | None=None, task_capacity: int=4096`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, MemoryEngine, Path, TaskStore, lifecycle.recover_or_init, policy.assert_consumers, self._load_or_create_token, self._review_token, threading.Event, threading.Lock, threading.RLock。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L32)。

### `hybrid_memory/service/service.py::MemoryService._review_token`

- 功能：服务门面的 _review_token 入口；转发/状态边界为 调用 review.review_token
- 输入：`self`。
- 输出：`str；review.review_token(self)`。
- 作用：调用 review.review_token。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L79)。

### `hybrid_memory/service/service.py::MemoryService.human_reviews`

- 功能：服务门面的 human_reviews 入口；转发/状态边界为 调用 review.human_reviews
- 输入：`self`。
- 输出：`list[dict]；review.human_reviews(self)`。
- 作用：调用 review.human_reviews。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L82)。

### `hybrid_memory/service/service.py::MemoryService.decide_human_review`

- 功能：服务门面的 decide_human_review 入口；转发/状态边界为 调用 review.decide_human_review
- 输入：`self, review_id: int, decision: str, capability: str`。
- 输出：`dict；review.decide_human_review(self, review_id, decision, capability)`。
- 作用：调用 review.decide_human_review。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L85)。

### `hybrid_memory/service/service.py::MemoryService._corrupt_file_exists`

- 功能：服务门面的 _corrupt_file_exists 入口；转发/状态边界为 调用 lifecycle.corrupt_file_exists
- 输入：`self`。
- 输出：`bool；lifecycle.corrupt_file_exists(self)`。
- 作用：调用 lifecycle.corrupt_file_exists。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L88)。

### `hybrid_memory/service/service.py::MemoryService.health_view`

- 功能：进程在不在，和数据有没有干净恢复，是两件事。 'ok' 只表示没有 checkpoint fault，插件据此复用进程。 'validation' 固定为 unverified：本进程不能自称远程或 L3 已验证。
- 输入：`self`。
- 输出：`dict；telemetry.health_view(self)`。
- 作用：调用 telemetry.health_view。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L91)。

### `hybrid_memory/service/service.py::MemoryService._ensure_healthy`

- 功能：服务门面的 _ensure_healthy 入口；转发/状态边界为 调用 lifecycle.ensure_healthy
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 lifecycle.ensure_healthy。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L99)。

### `hybrid_memory/service/service.py::MemoryService._check_checkpoint_error`

- 功能：服务门面的 _check_checkpoint_error 入口；转发/状态边界为 调用 self.tasks.checkpoint
- 输入：`self, revision`。
- 输出：`未注解；None`。
- 作用：调用 self.tasks.checkpoint。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L102)。

### `hybrid_memory/service/service.py::MemoryService._journal_signal`

- 功能：服务门面的 _journal_signal 入口；转发/状态边界为 调用 effects.journal_signal
- 输入：`self, kind, payload, t, key, merge`。
- 输出：`未注解；effects.journal_signal(self, kind, payload, t, key, merge)`。
- 作用：调用 effects.journal_signal。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L108)。

### `hybrid_memory/service/service.py::MemoryService._signal_payload`

- 功能：服务门面的 _signal_payload 入口；转发/状态边界为 调用 effects.signal_payload
- 输入：`self, kind, payload`。
- 输出：`未注解；effects.signal_payload(self, kind, payload)`。
- 作用：调用 effects.signal_payload。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L111)。

### `hybrid_memory/service/service.py::MemoryService._commit_sidecar_effect`

- 功能：服务门面的 _commit_sidecar_effect 入口；转发/状态边界为 调用 effects.effect_transaction
- 输入：`self, mutate, *, capture=None`。
- 输出：`未注解；effects.effect_transaction(self, mutate, capture=capture)`。
- 作用：调用 effects.effect_transaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L114)。

### `hybrid_memory/service/service.py::MemoryService._rollback_effect`

- 功能：任务操作与单元效果共用的内存回滚；原 Memory/队列对象身份不变。
- 输入：`self`。
- 输出：`未注解；生成器/上下文管理器`。
- 作用：调用 backup.items, copy.deepcopy, counters.items, dict, getattr, original.__dict__.clear, original.__dict__.update, original_mems.items, self._check_checkpoint_error, self._ensure_healthy, setattr, type, type(q._items)。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L119)。

### `hybrid_memory/service/service.py::MemoryService.lock`

- 功能：服务 RLock
- 输入：`self`。
- 输出：`未注解；self._lock`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/service.py#L156)。

### `hybrid_memory/service/service.py::MemoryService.current`

- 功能：当前 (t, scene)
- 输入：`self`。
- 输出：`tuple[int, str]；(self._t, self._scene)`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/service.py#L159)。

### `hybrid_memory/service/service.py::MemoryService.attach_agent`

- 功能：挂 Legacy 调查器（兼容 seam）
- 输入：`self, agent`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/service.py#L162)。

### `hybrid_memory/service/service.py::MemoryService.attach_dispatch`

- 功能：挂后台循环（P6 最终形态；worker 只需有 notify()）。
- 输入：`self, worker`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L165)。

### `hybrid_memory/service/service.py::MemoryService.notify`

- 功能：唤醒后台循环早跑一轮（legacy agent 与 dispatch 二选一常设）。
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 self.agent.notify, self.dispatch_worker.notify。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L169)。

### `hybrid_memory/service/service.py::MemoryService._kick`

- 功能：服务门面的 _kick 入口；转发/状态边界为 调用 self.notify
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 self.notify。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L176)。

### `hybrid_memory/service/service.py::MemoryService._load_or_create_token`

- 功能：HTTP 鉴权令牌：持久化在 state_dir/.memory-token（插件侧同路径 读取），无 state_dir 时临时生成。防浏览器 CSRF 写与端口占位复用。
- 输入：`self`。
- 输出：`str；tok`。
- 作用：调用 os.chmod, p.exists, p.parent.mkdir, p.read_text, p.read_text(encoding='utf-8').strip, p.write_text, secrets.token_hex。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L179)。

### `hybrid_memory/service/service.py::MemoryService.observe`

- 功能：服务门面的 observe 入口；转发/状态边界为 调用 observe.observe
- 输入：`self, user_text: str, assistant_text: str, request_id: str | None=None`。
- 输出：`dict；observe.observe(self, user_text, assistant_text, request_id)`。
- 作用：调用 observe.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L200)。

### `hybrid_memory/service/service.py::MemoryService.process_pending_units`

- 功能：服务门面的 process_pending_units 入口；转发/状态边界为 调用 observe.process_pending_units
- 输入：`self, limit: int=8`。
- 输出：`dict[int, dict]；observe.process_pending_units(self, limit)`。
- 作用：调用 observe.process_pending_units。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L204)。

### `hybrid_memory/service/service.py::MemoryService._semantic_model`

- 功能：服务门面的 _semantic_model 入口；转发/状态边界为 调用 worker.semantic_model
- 输入：`self, row`。
- 输出：`未注解；worker.semantic_model(self, row)`。
- 作用：调用 worker.semantic_model。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L208)。

### `hybrid_memory/service/service.py::MemoryService.process_semantic_tasks`

- 功能：服务门面的 process_semantic_tasks 入口；转发/状态边界为 调用 worker.run_semantic_tasks
- 输入：`self, limit: int=8`。
- 输出：`dict；worker.run_semantic_tasks(self, limit)`。
- 作用：调用 worker.run_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L212)。

### `hybrid_memory/service/service.py::MemoryService.start_unit_recovery`

- 功能：委托 lifecycle 启动补确认
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 lifecycle.start_unit_recovery。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/service.py#L215)。

### `hybrid_memory/service/service.py::MemoryService.stop_unit_recovery`

- 功能：委托 lifecycle 有界停止
- 输入：`self, timeout: float=5.0`。
- 输出：`None；None`。
- 作用：调用 lifecycle.stop_unit_recovery。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/service.py#L218)。

### `hybrid_memory/service/service.py::MemoryService._causal_memory_ids`

- 功能：服务门面的 _causal_memory_ids 入口；转发/状态边界为 调用 recall.causal_memory_ids
- 输入：`self, before: int | None`。
- 输出：`set[int]；recall.causal_memory_ids(self, before)`。
- 作用：调用 recall.causal_memory_ids。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L221)。

### `hybrid_memory/service/service.py::MemoryService._causal_tensions`

- 功能：服务门面的 _causal_tensions 入口；转发/状态边界为 调用 recall.causal_tensions
- 输入：`self, ids: set[int], before: int | None`。
- 输出：`dict；recall.causal_tensions(self, ids, before)`。
- 作用：调用 recall.causal_tensions。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L224)。

### `hybrid_memory/service/service.py::MemoryService.recall`

- 功能：服务门面的 recall 入口；转发/状态边界为 调用 recall.recall
- 输入：`self, q: str, k: int | None=None, *, signal_id: str | None=None, budget_tokens: int | None=None, passive: bool=False`。
- 输出：`dict；recall.recall(self, q, k, signal_id=signal_id, budget_tokens=budget_tokens, passive=passive)`。
- 作用：调用 recall.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L227)。

### `hybrid_memory/service/service.py::MemoryService.feedback`

- 功能：服务门面的 feedback 入口；转发/状态边界为 调用 feedback.feedback
- 输入：`self, retrieval_id: int, question: str, answer: str, request_id: str | None=None`。
- 输出：`dict；feedback.feedback(self, retrieval_id, question, answer, request_id)`。
- 作用：调用 feedback.feedback。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L233)。

### `hybrid_memory/service/service.py::MemoryService.report_miss`

- 功能：服务门面的 report_miss 入口；转发/状态边界为 调用 operate.report_miss
- 输入：`self, query: str, hint: str='', source: str='agent_tool'`。
- 输出：`dict；operate.report_miss(self, query, hint, source)`。
- 作用：调用 operate.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L237)。

### `hybrid_memory/service/service.py::MemoryService.conflicts`

- 功能：服务门面的 conflicts 入口；转发/状态边界为 调用 tools.conflicts
- 输入：`self, *, signal_id: str | None=None`。
- 输出：`dict；tools.conflicts(self, signal_id=signal_id)`。
- 作用：调用 tools.conflicts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L241)。

### `hybrid_memory/service/service.py::MemoryService.resolve`

- 功能：裁决回报。ensure_tension=True（调查员/主 agent 主动裁决两条此前 没被判为张力的记忆）时先登记 tension 再消解；entity_key 回填到双方。
- 输入：`self, left: int, right: int, verdict: str, entity_key: str='', ensure_tension: bool=False, *, signal_id: str | None=None, _context: InvestigationContext | None=None, _checkpoint: bool=True`。
- 输出：`dict；operate.resolve(self, left, right, verdict, entity_key, ensure_tension, signal_id=signal_id, _context=_context, _checkpoint=_checkpoint)`。
- 作用：调用 operate.resolve。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L244)。

### `hybrid_memory/service/service.py::MemoryService._admit`

- 功能：服务门面的 _admit 入口；转发/状态边界为 调用 budgets.admit
- 输入：`self, signal_id: str | None, before: int | None=None, *, window: bool=False, max_chars: int | None=None`。
- 输出：`tuple[InvestigationContext, dict | None, int]；budgets.admit(self, signal_id, before, window=window, max_chars=max_chars)`。
- 作用：调用 budgets.admit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L256)。

### `hybrid_memory/service/service.py::MemoryService.log_search`

- 功能：服务门面的 log_search 入口；转发/状态边界为 调用 tools.log_search
- 输入：`self, query: str, *, before=None, scene=None, k=8, signal_id: str | None=None`。
- 输出：`dict；tools.log_search(self, query, before=before, scene=scene, k=k, signal_id=signal_id)`。
- 作用：调用 tools.log_search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L262)。

### `hybrid_memory/service/service.py::MemoryService.log_timeline`

- 功能：服务门面的 log_timeline 入口；转发/状态边界为 调用 tools.log_timeline
- 输入：`self, entity: str, *, before=None, limit=30, signal_id: str | None=None`。
- 输出：`dict；tools.log_timeline(self, entity, before=before, limit=limit, signal_id=signal_id)`。
- 作用：调用 tools.log_timeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L267)。

### `hybrid_memory/service/service.py::MemoryService.log_stats`

- 功能：服务门面的 log_stats 入口；转发/状态边界为 调用 tools.log_stats
- 输入：`self, group_by: str='scene', *, before=None, limit=30, signal_id: str | None=None`。
- 输出：`dict；tools.log_stats(self, group_by, before=before, limit=limit, signal_id=signal_id)`。
- 作用：调用 tools.log_stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L272)。

### `hybrid_memory/service/service.py::MemoryService.log_window`

- 功能：服务门面的 log_window 入口；转发/状态边界为 调用 tools.log_window
- 输入：`self, unit_ids, *, max_chars=None, signal_id: str | None=None`。
- 输出：`dict；tools.log_window(self, unit_ids, max_chars=max_chars, signal_id=signal_id)`。
- 作用：调用 tools.log_window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L277)。

### `hybrid_memory/service/service.py::MemoryService.open_budget`

- 功能：服务门面的 open_budget 入口；转发/状态边界为 调用 budgets.open_budget
- 输入：`self, signal_id: str, *, tool_calls: int, window_chars: int, before: int, origin: str | None=None, task_id: int | None=None, lease_token: str | None=None`。
- 输出：`InvestigationContext；budgets.open_budget(self, signal_id, tool_calls=tool_calls, window_chars=window_chars, before=before, origin=origin, task_id=task_id, lease_token=lease_token)`。
- 作用：调用 budgets.open_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L282)。

### `hybrid_memory/service/service.py::MemoryService.close_budget`

- 功能：服务门面的 close_budget 入口；转发/状态边界为 调用 budgets.close_budget
- 输入：`self, signal_id: str`。
- 输出：`dict；budgets.close_budget(self, signal_id)`。
- 作用：调用 budgets.close_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L291)。

### `hybrid_memory/service/service.py::MemoryService._validate_proposal`

- 功能：服务门面的 _validate_proposal 入口；转发/状态边界为 调用 operate.validate_proposal
- 输入：`self, p: dict, before: int | None`。
- 输出：`tuple[Event, list[int]]；operate.validate_proposal(self, p, before)`。
- 作用：调用 operate.validate_proposal。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L295)。

### `hybrid_memory/service/service.py::MemoryService.propose`

- 功能：agent 提议入库。逐条校验（溯源非空且存在、因果、脱敏、自指、长度）， 通过的走引擎同一条 ingest 回路；supersedes 经 update 裁决把旧条目 取代。返回逐条结果。
- 输入：`self, proposals: list, *, origin: str='agent', signal_id: str | None=None, before: int | None=None, _context: InvestigationContext | None=None`。
- 输出：`dict；operate.propose(self, proposals, origin=origin, signal_id=signal_id, before=before, _context=_context)`。
- 作用：调用 operate.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L298)。

### `hybrid_memory/service/service.py::MemoryService.diagnose`

- 功能：服务门面的 diagnose 入口；转发/状态边界为 调用 operate.diagnose
- 输入：`self, miss_type: str, note: str='', *, signal_id: str | None=None, kind: str='', usage: dict | None=None, _context: InvestigationContext | None=None, _audit=True`。
- 输出：`dict；operate.diagnose(self, miss_type, note, signal_id=signal_id, kind=kind, usage=usage, _context=_context, _audit=_audit)`。
- 作用：调用 operate.diagnose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L308)。

### `hybrid_memory/service/service.py::MemoryService.signals`

- 功能：服务门面的 signals 入口；转发/状态边界为 调用 telemetry.signals_view
- 输入：`self`。
- 输出：`dict；telemetry.signals_view(self)`。
- 作用：调用 telemetry.signals_view。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L316)。

### `hybrid_memory/service/service.py::MemoryService._state`

- 功能：服务门面的 _state 入口；转发/状态边界为 调用 state._state
- 输入：`self`。
- 输出：`未注解；state._state(self)`。
- 作用：调用 state._state。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L320)。

### `hybrid_memory/service/service.py::MemoryService._dump_state`

- 功能：服务门面的 _dump_state 入口；转发/状态边界为 调用 state.dump_state
- 输入：`self`。
- 输出：`未注解；state.dump_state(self)`。
- 作用：调用 state.dump_state。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L323)。

### `hybrid_memory/service/service.py::MemoryService.save`

- 功能：服务门面的 save 入口；转发/状态边界为 调用 lifecycle.save
- 输入：`self`。
- 输出：`dict；lifecycle.save(self)`。
- 作用：调用 lifecycle.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L326)。

### `hybrid_memory/service/service.py::MemoryService._load`

- 功能：服务门面的 _load 入口；转发/状态边界为 调用 state.load_state
- 输入：`self, checkpoint: bytes | None=None`。
- 输出：`None；None`。
- 作用：调用 state.load_state。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/service.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/service/service.py#L329)。

## `hybrid_memory/service/tools.py`

- 模块功能：单项目编排、因果界、读取及人审。
- 设计归属：配置与服务；处置：保留收口。
- 目标路径：`hybrid_memory/service/tools.py`（当前路径）。
- 模块输入：查询/实体/分组/IDs、before 与预算。
- 模块输出：有界片段/时间线/统计/受限原文；不返回超因果界正文。
- 源校验：`284e5fd793c57f41295fac3a19ce160e3bac8b29fe705de2a72b2386cf091fd8`。

### `hybrid_memory/service/tools.py::log_search`

- 功能：有界日志片段检索（k≤20）
- 输入：`svc, query: str, *, before=None, scene=None, k=8, signal_id: str | None=None`。
- 输出：`dict；{'hits': hits, 'n': len(hits)}`。
- 作用：调用 int, len, min, svc._admit, svc.log.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/tools.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/tools.py#L8)。

### `hybrid_memory/service/tools.py::log_timeline`

- 功能：实体时间线（limit≤100）
- 输入：`svc, entity: str, *, before=None, limit=30, signal_id: str | None=None`。
- 输出：`dict；{'entity': entity, 'timeline': rows, 'n': len(rows)}`。
- 作用：调用 int, len, min, svc._admit, svc.log.timeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/tools.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/tools.py#L16)。

### `hybrid_memory/service/tools.py::log_stats`

- 功能：分组统计（limit≤200，同因果界）
- 输入：`svc, group_by: str='scene', *, before=None, limit=30, signal_id: str | None=None`。
- 输出：`dict；{'group_by': group_by, 'rows': rows, 'n': len(rows), 'units_total': svc.log.count(ctx.before)}`。
- 作用：调用 int, len, min, svc._admit, svc.log.count, svc.log.stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/tools.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/tools.py#L24)。

### `hybrid_memory/service/tools.py::log_window`

- 功能：唯一受限原文回展（预留+按实际结算）
- 输入：`svc, unit_ids, *, max_chars=None, signal_id: str | None=None`。
- 输出：`dict；out`。
- 作用：调用 svc._admit, svc.log.window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/tools.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/tools.py#L32)。

### `hybrid_memory/service/tools.py::conflicts`

- 功能：未决张力读取；目标并入统一 ledger
- 输入：`svc, *, signal_id: str | None=None`。
- 输出：`dict；{'conflicts': out, 't': svc._t}`。
- 作用：调用 out.append, svc._admit, svc._causal_memory_ids, svc._causal_tensions, svc.engine.mems.get, tensions.items。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/service/tools.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/service/tools.py#L50)。

## `hybrid_memory/store/__init__.py`

- 模块功能：SQLite、租约、回执及 checkpoint 原子性。
- 设计归属：存储与恢复；处置：保留收口。
- 目标路径：`hybrid_memory/store/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`174118104ac07f458462801f88a39668e3248a57c62fcc66884e3f929b3e4abb`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/store/evidence.py`

- 模块功能：不可覆盖的 L0 证据、索引及逐单元恢复。
- 设计归属：存储与恢复；处置：保留。
- 目标路径：`hybrid_memory/store/evidence.py`（当前路径）。
- 模块输入：L0 单元原文、请求绑定、逐单元工作与查询。
- 模块输出：不可覆盖证据、FTS/mentions/向量索引、片段/统计/受限窗口与恢复回执。
- 源校验：`3f5321dd964d5f0fb6476ca571589ed0b1de4ece42c5014290f2193325f598e6`。

### `hybrid_memory/store/evidence.py::entities_in`

- 功能：→ [(entity, kind)]，去重、保序、小写化（URL 保留原样去尾标点）。
- 输入：`text: str, limit: int=64`。
- 输出：`list[tuple[str, str]]；[]；out`。
- 作用：调用 any, c.isalpha, c.isdigit, ent.lower, ent.rstrip, len, m.group, out.append, pat.finditer, seen.add, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L58)。

### `hybrid_memory/store/evidence.py::_tokens`

- 功能：查询切词：ASCII 串按空白/标点，CJK 连续串整段（trigram 需 ≥3 字符， 短于 3 的丢弃——否则 FTS 返回空集）。
- 输入：`query: str`。
- 输出：`list[str]；toks`。
- 作用：调用 _TOKEN_RE.findall, len, tok.strip, toks.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L141)。

### `hybrid_memory/store/evidence.py::_fts_expr`

- 功能：委托 `' OR '.join` 执行；边界与失败由被调用方契约承担
- 输入：`tokens: list[str]`。
- 输出：`str；' OR '.join(('"' + t.replace('"', '""') + '"' for t in tokens))`。
- 作用：调用 ' OR '.join, t.replace。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L152)。

### `hybrid_memory/store/evidence.py::_snippet`

- 功能：不可覆盖的 L0 证据、索引及逐单元恢复 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`text: str, tokens: list[str], width: int`。
- 输出：`str；('…' if start > 0 else '') + piece + ('…' if end < len(text) else '')`。
- 作用：调用 len, low.find, max, min, text.lower, text[start:end].replace, tok.lower。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L156)。

### `hybrid_memory/store/evidence.py::LogStore`

- 功能：L0 证据库：不可覆盖原文+索引+逐单元恢复
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L171)。

### `hybrid_memory/store/evidence.py::LogStore.__init__`

- 功能：用给定参数与依赖初始化 LogStore，建立其对象状态；业务归属为不可覆盖的 L0 证据、索引及逐单元恢复
- 输入：`self, path: str | Path | None=None, embedder=None`。
- 输出：`未注解；None`。
- 作用：调用 Path, self._conn.execute, self._conn.executescript, self.path.parent.mkdir, sqlite3.connect, str, threading.RLock。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L172)。

### `hybrid_memory/store/evidence.py::LogStore.next_position`

- 功能：L0 的下一编号/逻辑时间；启动对齐用，写入时仍需在事务内重新读取。
- 输入：`self`。
- 输出：`tuple[int, int]；(max(0, uid), max(0, t))`。
- 作用：调用 max, self._conn.execute, self._conn.execute('SELECT COALESCE((SELECT MAX(id) FROM units), -1) + 1, COALESCE((SELECT MAX(t) FR…。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L190)。

### `hybrid_memory/store/evidence.py::LogStore.append_unit`

- 功能：在线追加 L0
- 输入：`t、文本、scene、请求绑定与游标下界`。
- 输出：`unit_id/t/entities/new_entities/replayed`。
- 作用：L0+work+request 同事务；向量提交后补。
- 错误：请求冲突/证据不可覆盖显式。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L199)。

### `hybrid_memory/store/evidence.py::LogStore.add_unit`

- 功能：导入或重放单元
- 输入：`id、t、文本与绑定`。
- 输出：`unit_id/t/entities/new_entities`。
- 作用：同内容 no-op；异内容拒绝。
- 错误：CaptureConflict/ValueError。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L217)。

### `hybrid_memory/store/evidence.py::LogStore._embed`

- 功能：不可覆盖的 L0 证据、索引及逐单元恢复 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, unit_id: int, user_text: str, assistant_text: str`。
- 输出：`None；None`。
- 作用：调用 int, np.asarray, self._conn.execute, self._embedder.embed, vec.tobytes。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L291)。

### `hybrid_memory/store/evidence.py::LogStore.capture_receipt`

- 功能：查请求绑定回执
- 输入：`self, request_id: str`。
- 输出：`dict | None；None；{'request_id': row[0], 'unit_id': row[1], 'fingerprint': row[2], 'created_at': row[3]}`。
- 作用：调用 self._conn.execute, self._conn.execute('SELECT request_id, unit_id, fingerprint, created_at FROM capture_receipts WHERE …。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L306)。

### `hybrid_memory/store/evidence.py::LogStore.recent_ids`

- 功能：Contiguous preceding units, bounded at the triggering unit's logical time.
- 输入：`self, unit_id: int, *, limit: int=6`。
- 输出：`list[int]；[]；list(reversed(ids))`。
- 作用：调用 list, reversed, self._conn.execute, self._conn.execute('SELECT t FROM units WHERE id=?', (unit_id,)).fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L316)。

### `hybrid_memory/store/evidence.py::LogStore.work`

- 功能：单元工作行：状态/结果/上下文/退避
- 输入：`self, unit_id: int`。
- 输出：`dict | None；None；{'unit_id': row[0], 'state': row[1], 'result': row[2], 'context': json.loads(row[3]), 'attempts': row[4], 'last_error': row[5], 'next_run_at': row[6]}`。
- 作用：调用 json.loads, self._conn.execute, self._conn.execute('SELECT unit_id,state,result,context,attempts,last_error,next_run_at FROM unit_wo…。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L327)。

### `hybrid_memory/store/evidence.py::LogStore.pending_units`

- 功能：严格 uid 顺序的待处理单元
- 输入：`self, limit: int=8`。
- 输出：`list[int]；[r[0] for r in self._conn.execute("SELECT unit_id FROM unit_work WHERE state='pending' ORDER BY unit_id LIMIT ?", (limit,))]`。
- 作用：调用 self._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L338)。

### `hybrid_memory/store/evidence.py::LogStore.work_stats`

- 功能：pending/result_saved/failed/done 计数
- 输入：`self`。
- 输出：`dict；{'pending': pending, 'result_saved': ready, 'failed': failed, 'done': done}`。
- 作用：调用 self._conn.execute, self._conn.execute("SELECT COUNT(*) FILTER (WHERE state='pending'), COUNT(*) FILTER (WHERE state='pe…。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L345)。

### `hybrid_memory/store/evidence.py::LogStore.unit_context`

- 功能：按原单元时间恢复首次出现的实体及上一轮原文，不使用当前时钟。
- 输入：`self, unit_id: int`。
- 输出：`dict；{'unit': unit, 'entities': [e for e, _ in ents], 'new_entities': first, 'previous_user': previous[0] if previous else ''}`。
- 作用：调用 ValueError, entities_in, self._conn.execute, self._conn.execute('SELECT 1 FROM mentions m JOIN units u ON u.id=m.unit_id WHERE m.entity=? AND u.t…, self._conn.execute('SELECT user_text FROM units WHERE t<? ORDER BY t DESC LIMIT 1', (unit['t'],)).fe…, self.get。
- 错误：异常 ValueError(f'pending unit {unit_id} 缺失 L0 原文')。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L354)。

### `hybrid_memory/store/evidence.py::LogStore.save_work_result`

- 功能：首次合法抽取结果落库；重复拒绝
- 输入：`self, unit_id: int, result: str`。
- 输出：`None；None`。
- 作用：调用 RuntimeError, self._conn.execute。
- 错误：异常 RuntimeError(f'unit {unit_id} 结果不可写（已完成或重复）')。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L370)。

### `hybrid_memory/store/evidence.py::LogStore.fail_work`

- 功能：记录错误与退避，不删单元
- 输入：`self, unit_id: int, error: Exception`。
- 输出：`None；None`。
- 作用：调用 min, self._conn.execute, self._conn.execute("SELECT attempts FROM unit_work WHERE unit_id=? AND state='pending'", (unit_id,))…, time.time, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L378)。

### `hybrid_memory/store/evidence.py::LogStore.finish_work`

- 功能：跨库回执确认；重复 done 可接受
- 输入：`self, unit_id: int`。
- 输出：`None；None`。
- 作用：调用 RuntimeError, self._conn.execute, self.work。
- 错误：异常 RuntimeError(f'unit {unit_id} 无待确认工作')。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L390)。

### `hybrid_memory/store/evidence.py::LogStore.get`

- 功能：按 id 取单元
- 输入：`self, unit_id: int`。
- 输出：`dict | None；self._row(row) if row else None`。
- 作用：调用 int, self._conn.execute, self._conn.execute('SELECT id, t, ts, scene, user_text, assistant_text, assistant_turns FROM units W…, self._row。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L401)。

### `hybrid_memory/store/evidence.py::LogStore.count`

- 功能：单元数（可限因果界）
- 输入：`self, before: int | None=None`。
- 输出：`int；self._conn.execute('SELECT count(*) FROM units WHERE t<?', (int(before),)).fetchone()[0]；self._conn.execute('SELECT count(*) FROM units').fetchone()[0]`。
- 作用：调用 int, self._conn.execute, self._conn.execute('SELECT count(*) FROM units WHERE t<?', (int(before),)).fetchone, self._conn.execute('SELECT count(*) FROM units').fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L409)。

### `hybrid_memory/store/evidence.py::LogStore.exists`

- 功能：→ {unit_id: t}，只含存在（且满足 before）的。
- 输入：`self, unit_ids: Iterable[int], before: int | None=None`。
- 输出：`dict；{r[0]: r[1] for r in self._conn.execute(q, args).fetchall()}；{}`。
- 作用：调用 ','.join, int, len, self._conn.execute, self._conn.execute(q, args).fetchall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L416)。

### `hybrid_memory/store/evidence.py::LogStore.retention_report`

- 功能：L0 保留报告
- 输入：`可选 src_ids`。
- 输出：`units/bytes/oldest_unit_id/oldest_t/dangling_src`。
- 作用：只告警不删。
- 错误：不宣称含全部 WAL/缓存磁盘。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L429)。

### `hybrid_memory/store/evidence.py::LogStore.search`

- 功能：混合检索 → [{unit_id, t, scene, snippet, score}]。 词法路：FTS5 trigram，bm25 排序；向量路：有 embedder 且有缓存向量时； 两路 RRF 融合。永远不返回全文。
- 输入：`self, query: str, *, before: int | None=None, scene: str | None=None, k: int=8, snippet: int=160`。
- 输出：`list[dict]；out`。
- 作用：调用 _fts_expr, _snippet, _tokens, args.append, enumerate, fused.get, fused.items, int, max, out.append, query.strip, round, self._conn.execute, self._conn.execute(sql, args).fetchall, self._vector_rank, self.get, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L453)。

### `hybrid_memory/store/evidence.py::LogStore._vector_rank`

- 功能：不可覆盖的 L0 证据、索引及逐单元恢复 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, query: str, *, before, scene, k: int`。
- 输出：`list[int]；[]；[uid for _, uid in scored[:k]]`。
- 作用：调用 ' AND '.join, args.append, conds.append, cosine, int, np.asarray, np.frombuffer, scored.append, scored.sort, self._conn.execute, self._conn.execute(sql, args).fetchall, self._embedder.embed。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L512)。

### `hybrid_memory/store/evidence.py::LogStore.timeline`

- 功能：实体时间线 → [{unit_id, t, scene, snippet}]（按 t 升序）。 mentions 精确命中优先；没有（如 CJK 概念）则回退 FTS/LIKE。
- 输入：`self, entity: str, *, before: int | None=None, limit: int=50, snippet: int=160`。
- 输出：`list[dict]；[]；[{k2: h[k2] for k2 in ('unit_id', 't', 'scene', 'snippet')} for h in hits]；out`。
- 作用：调用 _snippet, args.append, ent.lower, ent.startswith, entity.strip, hits.sort, int, out.append, self._conn.execute, self._conn.execute(sql, args).fetchall, self.get, self.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L543)。

### `hybrid_memory/store/evidence.py::LogStore.mention_counts`

- 功能：实体提及计数
- 输入：`self, entities: Iterable[str], before: int | None=None`。
- 输出：`dict[str, int]；out`。
- 作用：调用 args.append, ent.lower, ent.startswith, int, self._conn.execute, self._conn.execute(sql, args).fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L576)。

### `hybrid_memory/store/evidence.py::LogStore.stats`

- 功能：聚合视图（不含原文）。group_by ∈ scene | entity | week。
- 输入：`self, group_by: str='scene', *, before: int | None=None, limit: int=50`。
- 输出：`list[dict]；[{'entity': r[0], 'kind': r[1], 'mentions': r[2], 'first_t': r[3], 'last_t': r[4]} for r in rows]；[{'scene': r[0], 'units': r[1], 'first_t': r[2], 'last_t': r[3]} for r in rows]；sorted(buckets.values(), key=lambda b: b['week'])[:limit]`。
- 作用：调用 ValueError, _dt.datetime.fromtimestamp, _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isocalendar, buckets.setdefault, buckets.values, int, max, min, self._conn.execute, self._conn.execute(f'SELECT m.entity, m.kind, count(*), min(u.t), max(u.t) FROM mentions m JOIN unit…, self._conn.execute(f'SELECT u.scene, count(*), min(u.t), max(u.t) FROM units u{cond} GROUP BY u.scen…, self._conn.execute(f'SELECT u.ts, u.t FROM units u{cond}', args).fetchall, sorted。
- 错误：异常 ValueError('group_by must be scene | entity | week')。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L590)。

### `hybrid_memory/store/evidence.py::LogStore.window`

- 功能：唯一原文回展
- 输入：`unit_ids、max_chars、before`。
- 输出：`units/chars/truncated/missing/omitted`。
- 作用：按序字符预算；missing 与 omitted 分开。
- 错误：越界/缺失不静默补。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L626)。

### `hybrid_memory/store/evidence.py::LogStore.close`

- 功能：关闭连接
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 self._conn.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：按本项目标契约实施；[源码](../hybrid_memory/store/evidence.py#L658)。

### `hybrid_memory/store/evidence.py::LogStore._row`

- 功能：不可覆盖的 L0 证据、索引及逐单元恢复 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`row`。
- 输出：`dict；{'id': row[0], 't': row[1], 'ts': row[2], 'scene': row[3], 'user_text': row[4], 'assistant_text': row[5], 'assistant_turns': row[6]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/evidence.py`；处置：保留；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/evidence.py#L663)。

## `hybrid_memory/store/schema.py`

- 模块功能：各库身份、版本与增量迁移，高版本拒绝启动。
- 设计归属：存储与恢复；处置：实现接线。
- 目标路径：`hybrid_memory/store/schema.py`（当前路径）。
- 模块输入：库路径与库身份 log/tasks/cache。
- 模块输出：经 WAL/FULL/FK/busy_timeout 配置的连接、幂等建表与版本迁移；高版本 Fatal 且先于 DDL。
- 源校验：`89a52a7e25bbf643529ca0f8bb457582cb7df24fbee917f51c417c0e4b771e13`。

### `hybrid_memory/store/schema.py::open_db`

- 功能：按库身份打开连接
- 输入：`路径与 kind=log/tasks/cache`。
- 输出：`配置完成的 Connection`。
- 作用：WAL/FULL/FK/busy_timeout。
- 错误：路径/权限错误直接抛出。
- 目标：`hybrid_memory/store/schema.py`；处置：实现接线；变更：按本项目标契约实施；[源码](../hybrid_memory/store/schema.py#L12)。

### `hybrid_memory/store/schema.py::ensure_schema`

- 功能：幂等建表与索引
- 输入：`Connection 与 kind`。
- 输出：`None`。
- 作用：只建该库对象；无版本按 legacy_v0 迁入。
- 错误：已有数据不被清空。
- 目标：`hybrid_memory/store/schema.py`；处置：实现接线；变更：按本项目标契约实施；[源码](../hybrid_memory/store/schema.py#L29)。

### `hybrid_memory/store/schema.py::migrate`

- 功能：增量版本迁移
- 输入：`Connection 与 kind`。
- 输出：`None`。
- 作用：版本事务；高版本先 Fatal。
- 错误：禁止先 DDL 后检查；禁止自动降级。
- 目标：`hybrid_memory/store/schema.py`；处置：实现接线；变更：按本项目标契约实施；[源码](../hybrid_memory/store/schema.py#L39)。

## `hybrid_memory/store/state.py`

- 模块功能：SQLite、租约、回执及 checkpoint 原子性。
- 设计归属：存储与恢复；处置：保留收口。
- 目标路径：`hybrid_memory/store/state.py`（当前路径）。
- 模块输入：引擎/服务快照与 checkpoint bytes。
- 模块输出：受限反序列化、校验后一次发布的状态或明确损坏错误；不半恢复。
- 源校验：`e864c3049b8106a1e44cfa5149889507596689eb6c1070b38caa33178b580119`。

### `hybrid_memory/store/state.py::_legacy_pool_member`

- 功能：只兼容旧 Enum 的 getattr(Pool, 成员名)，绝不开放通用 getattr。
- 输入：`cls, name`。
- 输出：`未注解；Pool.__members__[name]`。
- 作用：调用 pickle.UnpicklingError, type。
- 错误：异常 pickle.UnpicklingError('state.pkl 含非法的 Pool 成员访问')。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/state.py#L51)。

### `hybrid_memory/store/state.py::RestrictedUnpickler`

- 功能：白名单反序列化（RCE 防线）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 pickle.Unpickler`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/state.py#L58)。

### `hybrid_memory/store/state.py::RestrictedUnpickler.find_class`

- 功能：只允许白名单 global
- 输入：`self, module: str, name: str`。
- 输出：`未注解；_legacy_pool_member；super().find_class(module, name)`。
- 作用：调用 pickle.UnpicklingError, super, super().find_class。
- 错误：异常 pickle.UnpicklingError(f'state.pkl 含未授权 global: {module}.{name}')。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/state.py#L59)。

### `hybrid_memory/store/state.py::_valid_shadow_pending`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`pending`。
- 输出：`bool；False；True`。
- 作用：调用 any, isinstance, len, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/state.py#L68)。

### `hybrid_memory/store/state.py::_shadow_entry`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`item`。
- 输出：`tuple；(tuple(key), mid, t_ret, rel)`。
- 作用：调用 tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/state.py#L84)。

### `hybrid_memory/store/state.py::_state`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`svc`。
- 输出：`未注解；{'mems': svc.engine.mems, 'tensions': svc.engine.tensions, 'next_id': svc.engine._next_id, 'consolidation_pending': svc.engine._consolidation_pending, 'consolidation_deferred': svc.engine._consolidation_deferred, 'counters': {k: getattr(svc.engine, k) for k in _COUNTERS}, 'shadow_pending': list(svc.engine._shadow_pending), 'retrievals': svc._retrievals, 'next_retrieval': svc._next_retrieval, 'miss_counts': dict(svc.miss_counts), 'service_counters': {k: getattr(svc, k) for k in _SERVICE_COUNTERS}, 't': svc._t, 'unit_id': svc._unit_id, 'scene': svc._scene, 'scene_t': svc._scene_t}`。
- 作用：调用 dict, getattr, list。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/state.py#L89)。

### `hybrid_memory/store/state.py::dump_state`

- 功能：健康门+pickle4 快照
- 输入：`svc`。
- 输出：`未注解；pickle.dumps(_state(svc), protocol=4)`。
- 作用：调用 _state, pickle.dumps, svc._ensure_healthy。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/state.py#L105)。

### `hybrid_memory/store/state.py::load_state`

- 功能：校验后一次发布；不半恢复
- 输入：`svc, checkpoint: bytes | None=None`。
- 输出：`None；None`。
- 作用：调用 MEMORY_FIELD_DEFAULTS.items, RestrictedUnpickler, RestrictedUnpickler(f).load, RestrictedUnpickler(io.BytesIO(checkpoint)).load, ValueError, _shadow_entry, _valid_shadow_pending, all, any, io.BytesIO, isinstance, len, max, nonnegative_int, open, setattr, sorted, state.get, state.keys, state.setdefault, state['consolidation_deferred'].items, state['counters'].items, state['mems'].items, state['mems'].values, state['miss_counts'].items, state['retrievals'].items, state['service_counters'].items, state['tensions'].items, state[key].items, type。
- 错误：异常 ValueError('state.pkl 的 consolidation_deferred 格式异常'), ValueError('state.pkl 的 consolidation_pending 必须是 id 集合'), ValueError('state.pkl 的 mems 格式异常'), ValueError('state.pkl 的 miss_counts 格式异常'), ValueError('state.pkl 的 retrievals 格式异常'), ValueError('state.pkl 的 scene 必须是字符串'), ValueError('state.pkl 的 scene_t 必须是整数'), ValueError('state.pkl 的 shadow_pending 格式异常'), ValueError('state.pkl 的 tensions 格式异常'), ValueError(f'state.pkl 的 {key} 含未知或非法计数器'), ValueError(f'state.pkl 的 {key} 必须是 dict'), ValueError(f'state.pkl 的 {key} 必须是非负整数'), ValueError(f'state.pkl 缺字段: {sorted(missing)}'), ValueError(f'state.pkl 顶层类型异常: {type(state).__name__}')。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/state.py#L110)。

### `hybrid_memory/store/state.py::load_state.nonnegative_int`

- 功能：严格非负 int 判定（排 bool）
- 输入：`value`。
- 输出：`未注解；type(value) is int and value >= 0`。
- 作用：调用 type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/state.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/state.py#L128)。

## `hybrid_memory/store/tasks.py`

- 模块功能：SQLite、租约、回执及 checkpoint 原子性。
- 设计归属：存储与恢复；处置：保留收口。
- 目标路径：`hybrid_memory/store/tasks.py`（当前路径）。
- 模块输入：kind/payload/版本/租约/回执/checkpoint 与效果回调。
- 模块输出：任务行、状态迁移、原子效果回执与查询统计；不承诺模型只执行一次。
- 源校验：`b5586ab3f28600e3c859087496f83c9c3b4a5a18387dcaa5a5d151d2ceff2eef`。
- 模块备注：旧 claim_semantic/complete_semantic 等 API 已删除，不得复活；目标新增 store_call_context。

### `hybrid_memory/store/tasks.py::TaskLeaseLost`

- 功能：租约失效异常
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 SignalClosed`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L31)。

### `hybrid_memory/store/tasks.py::CheckpointConflict`

- 功能：checkpoint CAS 冲突
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 RuntimeError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L35)。

### `hybrid_memory/store/tasks.py::TaskQueueFull`

- 功能：任务队列满（背压）
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 RuntimeError`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L39)。

### `hybrid_memory/store/tasks.py::CaptureConflict`

- 功能：同一 request-id 已绑定不同正文。不得改绑，也不得当成新请求执行。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Exception`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L43)。

### `hybrid_memory/store/tasks.py::encode`

- 功能：委托 `json.dumps` 执行；边界与失败由被调用方契约承担
- 输入：`value`。
- 输出：`str；json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)`。
- 作用：调用 json.dumps。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L47)。

### `hybrid_memory/store/tasks.py::TaskStore`

- 功能：任务库：状态机/租约/回执/checkpoint
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L114)。

### `hybrid_memory/store/tasks.py::TaskStore.__init__`

- 功能：用给定参数与依赖初始化 TaskStore，建立其对象状态；业务归属为SQLite、租约、回执及 checkpoint 原子性
- 输入：`self, path: str | Path | None=None, *, clock=None, capacity=4096`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(path).parent.mkdir, int, max, self._conn.execute, self._conn.executescript, sqlite3.connect, str, threading.RLock。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L115)。

### `hybrid_memory/store/tasks.py::TaskStore.transaction`

- 功能：BEGIN IMMEDIATE 上下文
- 输入：`self`。
- 输出：`未注解；生成器/上下文管理器`。
- 作用：调用 self._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L138)。

### `hybrid_memory/store/tasks.py::TaskStore._decode`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`row`。
- 输出：`未注解；None；out`。
- 作用：调用 dict, json.loads。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L144)。

### `hybrid_memory/store/tasks.py::TaskStore.get`

- 功能：按 id 取任务行
- 输入：`self, task_id`。
- 输出：`未注解；self._decode(self._conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())`。
- 作用：调用 self._conn.execute, self._conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone, self._decode。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L153)。

### `hybrid_memory/store/tasks.py::TaskStore.list_tasks`

- 功能：按状态/kind 查询；目标加 due/limit
- 输入：`self, *, states=None, kinds=None, due_before: float | None=None, limit: int | None=None`。
- 输出：`未注解；[]；[self._decode(r) for r in self._conn.execute(query, params)]`。
- 作用：调用 ','.join, params.append, params.extend, self._conn.execute, self._decode, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L158)。

### `hybrid_memory/store/tasks.py::TaskStore.enqueue`

- 功能：持久接受任务
- 输入：`kind/payload/t/key/merge/游标`。
- 输出：`任务 id`。
- 作用：(kind,key) 仅合未领任务；容量 4096 背压。
- 错误：满 TaskQueueFull；不得逐出已接受。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L177)。

### `hybrid_memory/store/tasks.py::TaskStore._enqueue`

- 功能：与 unit checkpoint 共用事务；不得在此方法内部再次 BEGIN。
- 输入：`self, conn, kind, payload, t, *, key='', merge=None, memory_next_id=0`。
- 输出：`未注解；cur.lastrowid；row['id']`。
- 作用：调用 TaskQueueFull, conn.execute, conn.execute("SELECT * FROM tasks WHERE kind=? AND task_key=? AND state='pending' AND attempts=0", (…, conn.execute("SELECT COUNT(*) FROM tasks WHERE state IN ('pending','running','ready','applying')").f…, conn.execute("SELECT id FROM tasks WHERE kind=? AND task_key=? AND state='done' ORDER BY updated_at …, encode, json.loads, max, merge, self.clock。
- 错误：异常 TaskQueueFull(f'任务队列容量 {self.capacity} 已满；未接受新任务')。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L182)。

### `hybrid_memory/store/tasks.py::TaskStore.memory_next_id`

- 功能：持久记忆游标
- 输入：`self`。
- 输出：`未注解；row[0] if row else 0`。
- 作用：调用 self._conn.execute, self._conn.execute("SELECT value FROM metadata WHERE key='memory_next_id'").fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L208)。

### `hybrid_memory/store/tasks.py::TaskStore.checkpoint`

- 功能：权威状态读取
- 输入：`无参数`。
- 输出：`(revision, bytes|None)`。
- 作用：存在操作但无 checkpoint 时拒绝。
- 错误：CheckpointConflict 拒绝旧实例。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L213)。

### `hybrid_memory/store/tasks.py::TaskStore._write_checkpoint`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`conn, state: bytes, expected_revision: int`。
- 输出：`未注解；revision`。
- 作用：调用 CheckpointConflict, conn.execute, conn.execute('SELECT revision FROM checkpoint WHERE id=1').fetchone。
- 错误：异常 CheckpointConflict('checkpoint 已由其他服务实例推进；请重启加载最新状态')。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L228)。

### `hybrid_memory/store/tasks.py::TaskStore.save_checkpoint`

- 功能：显式保存 checkpoint（CAS）
- 输入：`self, state, expected_revision`。
- 输出：`未注解；revision`。
- 作用：调用 self._write_checkpoint, self.transaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L239)。

### `hybrid_memory/store/tasks.py::TaskStore.runs_today`

- 功能：当日逻辑调用数
- 输入：`self, day`。
- 输出：`未注解；row[0] if row else 0`。
- 作用：调用 self._conn.execute, self._conn.execute('SELECT runs FROM daily_runs WHERE day=?', (day,)).fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L244)。

### `hybrid_memory/store/tasks.py::TaskStore.recover_expired`

- 功能：过期回收
- 输入：`阶段上限、kinds、reset_next_run_at`。
- 输出：`None`。
- 作用：过期也计尝试；不复活 dead。
- 错误：达到上限且 policy=dead 才 dead。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L249)。

### `hybrid_memory/store/tasks.py::TaskStore.skip_recent`

- 功能：Legacy 同 key TTL 去重
- 输入：`self, task_id, ttl`。
- 输出：`未注解；False；True`。
- 作用：调用 conn.execute, conn.execute("SELECT 1 FROM tasks WHERE id=? AND state='done' AND updated_at>? LIMIT 1", (row['dedup…, conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone, self.clock, self.transaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L304)。

### `hybrid_memory/store/tasks.py::TaskStore.claim`

- 功能：领取任务
- 输入：`id、version、可选 before/origin/day/cap/lease/checkpoint`。
- 输出：`任务行或 None`。
- 作用：token+lease+尝试计数同事务；ready 不扣模型额度。
- 错误：version/退避/上限不符返回 None，不抛用户错误。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L317)。

### `hybrid_memory/store/tasks.py::TaskStore._owned`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, conn, task_id, token, states=('running', 'applying')`。
- 输出：`未注解；row`。
- 作用：调用 TaskLeaseLost, conn.execute, conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone, self.clock。
- 错误：异常 TaskLeaseLost(f'task {task_id} 租约已失效')。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L358)。

### `hybrid_memory/store/tasks.py::TaskStore.check_owned`

- 功能：租约/token 复核
- 输入：`self, task_id, token`。
- 输出：`未注解；None`。
- 作用：调用 self._owned。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L365)。

### `hybrid_memory/store/tasks.py::TaskStore.store_call_context`

- 功能：封存一次模型调用的原始输入上下文
- 输入：`task_id、token、context（窗口 ids、规则 id、快照 revision、协议版本、正文摘要）`。
- 输出：`None（写入）或明确冲突`。
- 作用：running 且 owned 时同事务写入；同 attempt 不可改绑。
- 错误：租约/版本不符 TaskLeaseLost；重复封存不同内容拒绝。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L369)。

### `hybrid_memory/store/tasks.py::TaskStore.store_result`

- 功能：持久化模型产物
- 输入：`id、token、result、可选 checkpoint/rule_ids`。
- 输出：`新 revision 或 None`。
- 作用：产物转 ready 并冻结规则引用。
- 错误：租约失效 TaskLeaseLost。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L388)。

### `hybrid_memory/store/tasks.py::TaskStore.retry`

- 功能：两阶段重试
- 输入：`id、token、error 与阶段上限/退避`。
- 输出：`新 state`。
- 作用：区分模型与应用尝试；合法产物保留。
- 错误：耗尽按 policy 转 dead/requeue。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L405)。

### `hybrid_memory/store/tasks.py::TaskStore.finish`

- 功能：Legacy 操作完成；default 用 complete
- 输入：`self, task_id, token`。
- 输出：`未注解；None`。
- 作用：调用 conn.execute, self._owned, self.clock, self.transaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L431)。

### `hybrid_memory/store/tasks.py::TaskStore.unit_receipt`

- 功能：查单元回执
- 输入：`self, unit_id`。
- 输出：`未注解；json.loads(row[0]) if row else None`。
- 作用：调用 json.loads, self._conn.execute, self._conn.execute('SELECT response FROM unit_receipts WHERE unit_id=?', (unit_id,)).fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L437)。

### `hybrid_memory/store/tasks.py::TaskStore.apply_unit`

- 功能：单元效果原子提交
- 输入：`uid、mutate、dump、handoffs、expected_revision`。
- 输出：`(response, revision, replayed)`。
- 作用：L0 回执与效果同事务；跨库确认另行。
- 错误：重复单元返回原回执。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L443)。

### `hybrid_memory/store/tasks.py::TaskStore.read_capture`

- 功能：查请求回执绑定
- 输入：`self, request_id`。
- 输出：`未注解；None；{'kind': row[0], 'fingerprint': row[1], 'response': json.loads(row[2])}`。
- 作用：调用 json.loads, self._conn.execute, self._conn.execute('SELECT kind, fingerprint, response FROM capture_receipts WHERE request_id=?', (r…。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L462)。

### `hybrid_memory/store/tasks.py::TaskStore._capture_hit`

- 功能：SQLite、租约、回执及 checkpoint 原子性 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, conn, capture`。
- 输出：`未注解；None；json.loads(old[1])`。
- 作用：调用 CaptureConflict, conn.execute, conn.execute('SELECT fingerprint, response FROM capture_receipts WHERE request_id=?', (capture['requ…, json.loads。
- 错误：异常 CaptureConflict(f"request_id {capture['request_id']} 已绑定不同请求")。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L471)。

### `hybrid_memory/store/tasks.py::TaskStore.remember_capture`

- 功能：无引擎效果的接受回执。与查找同事务，避免空反馈在挤出检索后无法回放。
- 输入：`self, request_id, kind, fingerprint, response`。
- 输出：`未注解；(old, True)；(response, False)`。
- 作用：调用 conn.execute, encode, self._capture_hit, self.clock, self.transaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L481)。

### `hybrid_memory/store/tasks.py::TaskStore.apply_effect`

- 功能：非单元 sidecar 改动、发射的任务和 checkpoint 共用一笔事务。
- 输入：`self, mutate, dump_state, expected_revision`。
- 输出：`未注解；(out, revision)`。
- 作用：调用 CheckpointConflict, conn.execute, conn.execute('SELECT revision FROM checkpoint WHERE id=1').fetchone, dump_state, mutate, self._write_checkpoint, self.transaction。
- 错误：异常 CheckpointConflict('checkpoint 已推进；拒绝旧内存实例')。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L494)。

### `hybrid_memory/store/tasks.py::TaskStore.apply_captured_effect`

- 功能：效果、checkpoint 与 request-id 回执同事务。已有回执只返回，不执行 mutate。
- 输入：`self, mutate, dump_state, expected_revision, capture`。
- 输出：`未注解；(old, expected_revision, True)；(out, revision, False)`。
- 作用：调用 CheckpointConflict, conn.execute, conn.execute('SELECT revision FROM checkpoint WHERE id=1').fetchone, dump_state, encode, mutate, self._capture_hit, self._write_checkpoint, self.clock, self.transaction。
- 错误：异常 CheckpointConflict('checkpoint 已推进；拒绝旧内存实例')。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L504)。

### `hybrid_memory/store/tasks.py::TaskStore.complete`

- 功能：效果原子提交
- 输入：`id、token、mutate、dump、expected_revision`。
- 输出：`(out, revision)`。
- 作用：效果+新 Task+checkpoint+回执+done 同事务。
- 错误：CAS 冲突/租约失效显式。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L522)。

### `hybrid_memory/store/tasks.py::TaskStore.apply_operation`

- 功能：Legacy 操作幂等提交
- 输入：`id、token、request、mutate、dump、revision`。
- 输出：`(response, revision, replayed)`。
- 作用：同 task 操作签名去重；慢 I/O 后复核租约。
- 错误：过期 token 不得写入。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L551)。

### `hybrid_memory/store/tasks.py::TaskStore.rule_snapshot`

- 功能：作用域规则注入
- 输入：`target 与字面上下文`。
- 输出：`有效规则行列表`。
- 作用：project 或 entity 字面匹配。
- 错误：不执行规则文本。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L570)。

### `hybrid_memory/store/tasks.py::TaskStore.rule_report`

- 功能：规则版本/启用/uses 列表
- 输入：`self`。
- 输出：`未注解；[dict(r) for r in self._conn.execute('SELECT r.id,r.target,r.scope,r.instruction,r.enabled,r.source_task,COUNT(u.task_id) AS uses FROM agent_rules r LEFT JOIN agent_rule_uses u ON u.rule_id=r.id GROUP BY r.id ORDER BY r.id')]`。
- 作用：调用 dict, self._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L581)。

### `hybrid_memory/store/tasks.py::TaskStore.disable_rule`

- 功能：Human/offline rollback; history and usage remain inspectable.
- 输入：`self, rule_id`。
- 输出：`未注解；bool(cur.rowcount)`。
- 作用：调用 bool, conn.execute, self.clock, self.transaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/store/tasks.py#L588)。

### `hybrid_memory/store/tasks.py::TaskStore.rules_for`

- 功能：旧无 scope 读法（迁移后删除）
- 输入：`self, target`。
- 输出：`未注解；[r[0] for r in self._conn.execute('SELECT instruction FROM agent_rules WHERE target=? AND enabled=1 ORDER BY id', (target,)).fetchall()]`。
- 作用：调用 self._conn.execute, self._conn.execute('SELECT instruction FROM agent_rules WHERE target=? AND enabled=1 ORDER BY id', (…。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：迁移后删除；变更：删除条件：无作用域旧读法仅测试使用；rule_snapshot/rule_report 接管后移除；[源码](../hybrid_memory/store/tasks.py#L598)。

### `hybrid_memory/store/tasks.py::TaskStore.workflow_trace`

- 功能：投诉前交接证据
- 输入：`unit_ids 与 before_task_id`。
- 输出：`有界 trace 列表`。
- 作用：只承认派发前完成；≤18 项/24000 字符。
- 错误：超限 ValueError 需人工调查。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L604)。

### `hybrid_memory/store/tasks.py::TaskStore.pending_reviews`

- 功能：待审人审行
- 输入：`self`。
- 输出：`未注解；[dict(r) for r in self._conn.execute("SELECT * FROM human_reviews WHERE status='pending' ORDER BY id")]`。
- 作用：调用 dict, self._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L646)。

### `hybrid_memory/store/tasks.py::TaskStore.queued_counts`

- 功能：active kind 计数
- 输入：`self`。
- 输出：`未注解；dict(self._conn.execute("SELECT kind,COUNT(*) FROM tasks WHERE state IN ('pending','ready') GROUP BY kind"))`。
- 作用：调用 dict, self._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L651)。

### `hybrid_memory/store/tasks.py::TaskStore.semantic_stats`

- 功能：语义任务状态/退避/错误
- 输入：`self`。
- 输出：`未注解；{'states': dict(rows), 'retrying': retrying, 'errors': errors, 'recog_fail': failure[0] if failure else 0}`。
- 作用：调用 dict, list, self._conn.execute, self._conn.execute("SELECT COUNT(*) FROM tasks WHERE kind IN ('conflict_pending','feedback_pending',…, self._conn.execute("SELECT value FROM metadata WHERE key='semantic_recog_fail'").fetchone, self.clock。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L656)。

### `hybrid_memory/store/tasks.py::TaskStore.stats`

- 功能：任务状态与操作数
- 输入：`self`。
- 输出：`未注解；counts`。
- 作用：调用 self._conn.execute, self._conn.execute('SELECT COUNT(*) FROM operations').fetchone。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L674)。

### `hybrid_memory/store/tasks.py::TaskStore.close`

- 功能：关闭连接
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 self._conn.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/store/tasks.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/store/tasks.py#L680)。

## `hybrid_memory/taskstore.py`

- 模块功能：TaskStore 旧导入位；真实状态机位于 store/tasks.py。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/taskstore.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：store.tasks 的状态机、异常与常量同一对象。
- 源校验：`44d45b2640eab34996fc7633f5d0b7cd6f4564b703f469a14434a608dfa7c8d2`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：SEMANTIC_KINDS ← hybrid_memory.store.tasks.SEMANTIC_KINDS；WORKFLOW_KINDS ← hybrid_memory.store.tasks.WORKFLOW_KINDS；CaptureConflict ← hybrid_memory.store.tasks.CaptureConflict；CheckpointConflict ← hybrid_memory.store.tasks.CheckpointConflict；TaskLeaseLost ← hybrid_memory.store.tasks.TaskLeaseLost；TaskQueueFull ← hybrid_memory.store.tasks.TaskQueueFull；TaskStore ← hybrid_memory.store.tasks.TaskStore；encode ← hybrid_memory.store.tasks.encode；__all__ = ['SEMANTIC_KINDS', 'WORKFLOW_KINDS', 'CaptureConflict', 'CheckpointConflict', 'TaskLeaseLost', 'TaskQueueFull', 'TaskStore', 'encode']

## `hybrid_memory/telemetry.py`

- 模块功能：健康、队列、模型调用与容量观测。
- 设计归属：错误与观测；处置：接线。
- 目标路径：`hybrid_memory/telemetry.py`（当前路径）。
- 模块输入：service 的锁内状态与计数。
- 模块输出：health/signals 只增字段视图、脱敏结构日志与限频告警。
- 源校验：`3614dcaa46e1a0a4b0887bb15a6bd9850d2ae57364fd734182d2c32ea96a067c`。

### `hybrid_memory/telemetry.py::Counters`

- 功能：降级/丢弃计数的唯一口径（§2 telemetry）。
- 输入：`n_missed: int = 0；n_rejected: int = 0；n_ungrounded: int = 0；n_candgen_fail: int = 0；n_dropped: int = 0；n_shadow_dropped: int = 0；n_pool_truncated: int = 0；n_dead_tasks: int = 0`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/telemetry.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/telemetry.py#L16)。

### `hybrid_memory/telemetry.py::health_view`

- 功能：恢复/调度/容量/语义健康视图
- 输入：`service（持锁读取）`。
- 输出：`ok/checkpoint_fault/snapshot/corrupt_file/units_pending/validation/t/mems/tensions/signals/log_units/agent 及目标新增 paused/degraded/provider/retention/capacity`。
- 作用：只读；字段只增不改语义。
- 错误：读取失败不得吞掉；validation 保持 unverified。
- 目标：`hybrid_memory/telemetry.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/telemetry.py#L29)。

### `hybrid_memory/telemetry.py::signals_view`

- 功能：队列、任务、重试、信用与容量遥测
- 输入：`service（持锁读取）`。
- 输出：`queued/n_emitted/n_dropped/open_budgets/tasks/semantic/checkpoint_fault/missed/proposals/rejected/candgen_fail/miss_counts/log_units/units/agent/t 及目标新增 dispatch/dead/limit 计数`。
- 作用：只读；不触发裁决。
- 错误：不得把历史 done 行当 active 容量。
- 目标：`hybrid_memory/telemetry.py`；处置：接线；变更：按本项目标契约实施；[源码](../hybrid_memory/telemetry.py#L50)。

### `hybrid_memory/telemetry.py::log_event`

- 功能：JSON 一行到 stderr（{"t", "kind", **fields}）。
- 输入：`kind: str, **fields`。
- 输出：`None；None`。
- 作用：调用 json.dumps, print, time.time。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/telemetry.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/telemetry.py#L68)。

### `hybrid_memory/telemetry.py::warn_once`

- 功能：限频告警（同 key 进程内只报一次）。
- 输入：`key: str, message: str`。
- 输出：`None；None`。
- 作用：调用 _warned.add, print。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/telemetry.py`；处置：接线；变更：保留当前签名与 IO；[源码](../hybrid_memory/telemetry.py#L78)。

## `hybrid_memory/transport/__init__.py`

- 模块功能：HTTP、鉴权、DTO、组装与人审 CLI。
- 设计归属：传输与部署；处置：保留收口。
- 目标路径：`hybrid_memory/transport/__init__.py`（当前路径）。
- 模块输入：包 import。
- 模块输出：无业务符号；子模块由各自契约承担。
- 源校验：`576a2303a129c4aea439d1e5cbd75553d6867259e50e84ce65b6b853cf8a3638`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：

## `hybrid_memory/transport/auth.py`

- 模块功能：HTTP、鉴权、DTO、组装与人审 CLI。
- 设计归属：传输与部署；处置：保留收口。
- 目标路径：`hybrid_memory/transport/auth.py`（当前路径）。
- 模块输入：Authorization 头与期望 token。
- 模块输出：常量时间 bool；bearer 不代表人审 capability。
- 源校验：`539e93c4afe9e34a9c8334bf2c6309112fb078469f4606c92fac657e24823ecc`。

### `hybrid_memory/transport/auth.py::authorized`

- 功能：委托 `secrets.compare_digest` 执行；边界与失败由被调用方契约承担
- 输入：`headers, token: str`。
- 输出：`bool；secrets.compare_digest((headers.get('Authorization') or '').encode('utf-8'), f'Bearer {token}'.encode('utf-8'))`。
- 作用：调用 (headers.get('Authorization') or '').encode, f'Bearer {token}'.encode, headers.get, secrets.compare_digest。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/auth.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/transport/auth.py#L13)。

## `hybrid_memory/transport/bootstrap.py`

- 模块功能：HTTP、鉴权、DTO、组装与人审 CLI。
- 设计归属：传输与部署；处置：保留收口。
- 目标路径：`hybrid_memory/transport/bootstrap.py`（当前路径）。
- 模块输入：argv/env、项目目录与状态目录。
- 模块输出：组装好的 MemoryService、HTTP 进程与真停机收尾；唯一组合根。
- 源校验：`75ebbff198580f52be216b0d370d6e7dbac1eae9eb78c4ce826a5591181de67b`。

### `hybrid_memory/transport/bootstrap.py::build_default_service`

- 功能：默认依赖组装；目标以 Settings 唯一解析
- 输入：`project_dir: str | Path, model: str='glm-5.3-flash', embed_log: bool=True, task_capacity: int=4096`。
- 输出：`MemoryService；MemoryService(cfg, emb, semantics, ChatGenerator(chat_fn), state_dir=mem_dir, logstore=log, task_capacity=task_capacity)`。
- 作用：调用 Cfg, ChatGenerator, LLMSemantics, LogStore, MemoryService, Path, SqliteEmbeddingCache, ZhipuEmbedder, gi.exists, gi.write_text, load_env_key, mem_dir.mkdir。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/bootstrap.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/bootstrap.py#L24)。

### `hybrid_memory/transport/bootstrap.py::build_default_service.chat_fn`

- 功能：委托 `chat` 执行；边界与失败由被调用方契约承担
- 输入：`system: str, user: str`。
- 输出：`str；chat(api_key=key, model=model, system=system, user=user, cache_dir=mem_dir / 'chat-cache')`。
- 作用：调用 chat。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/bootstrap.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/transport/bootstrap.py#L39)。

### `hybrid_memory/transport/bootstrap.py::main`

- 功能：进程入口
- 输入：`argv/env`。
- 输出：`None`。
- 作用：解析→组装→恢复→HTTP/worker→信号→serve→真停机。
- 错误：非法参数拒绝；stop 未收束不得静默退出。
- 目标：`hybrid_memory/transport/bootstrap.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/bootstrap.py#L53)。

### `hybrid_memory/transport/bootstrap.py::main._term`

- 功能：HTTP、鉴权、DTO、组装与人审 CLI 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`*_`。
- 输出：`未注解；None`。
- 作用：调用 SystemExit。
- 错误：异常 SystemExit(0)。
- 目标：`hybrid_memory/transport/bootstrap.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/transport/bootstrap.py#L124)。

## `hybrid_memory/transport/dto.py`

- 模块功能：HTTP、鉴权、DTO、组装与人审 CLI。
- 设计归属：传输与部署；处置：保留收口。
- 目标路径：`hybrid_memory/transport/dto.py`（当前路径）。
- 模块输入：HTTP headers 与 JSON body。
- 模块输出：规范 DTO 或 HttpError；严格 64 位 int、媒体与 4MiB 限制。
- 源校验：`0e05a2957654ab29032b893e21623b2127e86c5e4b3e06de83ab99661ee1e6e4`。
- 模块备注：目标：observe/feedback DTO 增可选 session_id/turn_id 并纳入指纹；缺失标 unknown，不得跨会话归因。

### `hybrid_memory/transport/dto.py::HttpError`

- 功能：HTTP 状态+文案异常
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Exception`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L12)。

### `hybrid_memory/transport/dto.py::HttpError.__init__`

- 功能：用给定参数与依赖初始化 HttpError，建立其对象状态；业务归属为HTTP、鉴权、DTO、组装与人审 CLI
- 输入：`self, code: int, msg: str`。
- 输出：`未注解；None`。
- 作用：调用 super, super().__init__。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/transport/dto.py#L13)。

### `hybrid_memory/transport/dto.py::opt_int`

- 功能：严格 64 位可选 int（排 bool/越界）
- 输入：`body: dict, key: str, *, positive: bool=False`。
- 输出：`未注解；None；v`。
- 作用：调用 HttpError, body.get, type。
- 错误：异常 HttpError(400, f'{key} must be a 64-bit int'), HttpError(400, f'{key} must be positive')。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L28)。

### `hybrid_memory/transport/dto.py::req_str`

- 功能：要求非空字符串字段
- 输入：`body: dict, key: str`。
- 输出：`str；v`。
- 作用：调用 HttpError, body.get, isinstance, v.strip。
- 错误：异常 HttpError(400, f'{key} required')。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L39)。

### `hybrid_memory/transport/dto.py::parse_body`

- 功能：请求体解析
- 输入：`headers 与 rfile`。
- 输出：`JSON 对象 dict`。
- 作用：媒体/长度 4MiB/对象校验。
- 错误：HttpError 400/413/415。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L46)。

### `hybrid_memory/transport/dto.py::capture_request_id`

- 功能：header/body 一致的请求身份
- 输入：`headers, body: dict`。
- 输出：`str | None；None；_validate_request_id(chosen)`。
- 作用：调用 HttpError, _validate_request_id, body.get, header.strip, headers.get, isinstance, str。
- 错误：异常 HttpError(400, 'X-Request-Id and request_id disagree'), HttpError(400, 'X-Request-Id must not be empty'), HttpError(400, 'request_id must be a string'), HttpError(400, 'request_id must not be empty'), HttpError(400, str(exc))。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L69)。

### `hybrid_memory/transport/dto.py::observe_payload`

- 功能：一轮交互 DTO 与幂等身份
- 输入：`headers 与 JSON body`。
- 输出：`user_text/assistant_text/request_id（目标含 session_id/turn_id）`。
- 作用：纳入幂等指纹；缺省不推断。
- 错误：空轮/类型非法 400；会话身份缺失标 unknown。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L91)。

### `hybrid_memory/transport/dto.py::feedback_payload`

- 功能：反馈 DTO 与幂等身份
- 输入：`headers 与 JSON body`。
- 输出：`retrieval_id/question/answer/request_id（目标含 session_id/turn_id）`。
- 作用：纳入幂等指纹。
- 错误：rid/类型非法 400。
- 目标：`hybrid_memory/transport/dto.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/dto.py#L102)。

## `hybrid_memory/transport/http.py`

- 模块功能：HTTP、鉴权、DTO、组装与人审 CLI。
- 设计归属：传输与部署；处置：保留收口。
- 目标路径：`hybrid_memory/transport/http.py`（当前路径）。
- 模块输入：HTTP 请求与 service。
- 模块输出：JSON 响应与统一错误码；trio 禁直写、方法白名单、loopback 绑定。
- 源校验：`3993b81d10af583a681fc02dfbda7ce75bbb16452c4523c08bb2e0c7d741d4f2`。

### `hybrid_memory/transport/http.py::Handler`

- 功能：HTTP 请求处理器（ROUTES 驱动）
- 输入：`service: MemoryService`。
- 输出：`类型/实例；基类 BaseHTTPRequestHandler`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L50)。

### `hybrid_memory/transport/http.py::Handler.log_message`

- 功能：故意静默访问日志
- 输入：`self, *args`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L53)。

### `hybrid_memory/transport/http.py::Handler._reply`

- 功能：HTTP、鉴权、DTO、组装与人审 CLI 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, code: int, obj`。
- 输出：`None；None`。
- 作用：调用 json.dumps, json.dumps(obj, ensure_ascii=False).encode, len, self.end_headers, self.send_header, self.send_response, self.wfile.write, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/transport/http.py#L56)。

### `hybrid_memory/transport/http.py::Handler.handle_health`

- 功能：公开恢复健康视图
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 self._reply, svc.health_view。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L64)。

### `hybrid_memory/transport/http.py::Handler.handle_recall`

- 功能：GET 召回与预算参数校验
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, int, q.get, self._reply, svc.recall。
- 错误：异常 HttpError(400, 'budget_tokens must be int'), HttpError(400, 'k must be int'), HttpError(400, 'k must be positive'), HttpError(400, 'q required')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L69)。

### `hybrid_memory/transport/http.py::Handler.handle_conflicts`

- 功能：冲突读取（目标统一 ledger）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 self._reply, self.service.conflicts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L90)。

### `hybrid_memory/transport/http.py::Handler.handle_signals`

- 功能：遥测读取
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 self._reply, self.service.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L93)。

### `hybrid_memory/transport/http.py::Handler.handle_observe`

- 功能：交互接受（DTO→observe）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 dto.observe_payload, self._reply, self.service.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L96)。

### `hybrid_memory/transport/http.py::Handler.handle_feedback`

- 功能：回答归因回执与稳定重复码
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, dto.feedback_payload, self._reply, self.service.feedback。
- 错误：异常 HttpError(404, out['error'])。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L101)。

### `hybrid_memory/transport/http.py::Handler.handle_human_reviews`

- 功能：人审列表
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 self._reply, self.service.human_reviews。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L112)。

### `hybrid_memory/transport/http.py::Handler.handle_human_review`

- 功能：双 token 人审决定
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, body.get, dto.opt_int, secrets.compare_digest, self._reply, self.headers.get, self.service.decide_human_review, str。
- 错误：异常 HttpError(400, 'review_id required'), HttpError(400, str(exc)), HttpError(403, 'human review capability required'), HttpError(404, str(exc)), HttpError(409, str(exc))。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L115)。

### `hybrid_memory/transport/http.py::Handler.handle_resolve`

- 功能：Legacy 裁决（Trio 拒绝）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, body.get, dto.opt_int, isinstance, self._reply, sorted, str, svc.resolve。
- 错误：异常 HttpError(400, 'ensure_tension must be bool'), HttpError(400, 'left/right required'), HttpError(400, f'verdict must be one of {sorted(VERDICTS)}')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L132)。

### `hybrid_memory/transport/http.py::Handler.handle_search`

- 功能：POST 召回（CJK 长查询）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, body.get, dto.opt_int, isinstance, self._reply, self.service.recall。
- 错误：异常 HttpError(400, 'query required')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L150)。

### `hybrid_memory/transport/http.py::Handler.handle_miss`

- 功能：Legacy 缺失上报（Trio 拒绝）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 body.get, dto.req_str, isinstance, self._reply, self.service.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L159)。

### `hybrid_memory/transport/http.py::Handler.handle_log_search`

- 功能：有界日志检索
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 body.get, dto.opt_int, dto.req_str, isinstance, self._reply, self.service.log_search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L167)。

### `hybrid_memory/transport/http.py::Handler.handle_log_timeline`

- 功能：实体时间线
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 dto.opt_int, dto.req_str, self._reply, self.service.log_timeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L175)。

### `hybrid_memory/transport/http.py::Handler.handle_log_stats`

- 功能：分组统计
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, body.get, dto.opt_int, self._reply, self.service.log_stats。
- 错误：异常 HttpError(400, 'group_by must be scene | entity | week')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L182)。

### `hybrid_memory/transport/http.py::Handler.handle_log_window`

- 功能：受限原文回展（≤20 ids）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, all, body.get, dto.opt_int, isinstance, len, self._reply, self.service.log_window, type。
- 错误：异常 HttpError(400, 'unit_ids must be a non-empty int list (≤20)')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L191)。

### `hybrid_memory/transport/http.py::Handler.handle_propose`

- 功能：Legacy 提议（Trio 拒绝）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, body.get, dto.opt_int, isinstance, self._reply, self.service.propose。
- 错误：异常 HttpError(400, 'proposals must be a list')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L200)。

### `hybrid_memory/transport/http.py::Handler.handle_diagnose`

- 功能：Legacy 诊断（Trio 拒绝）
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 HttpError, body.get, dto.req_str, isinstance, self._reply, str, svc.diagnose。
- 错误：异常 HttpError(400, str(exc))。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L209)。

### `hybrid_memory/transport/http.py::Handler.handle_save`

- 功能：保存回执
- 输入：`self, q, body, sid`。
- 输出：`None；None`。
- 作用：调用 self._reply, self.service.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L220)。

### `hybrid_memory/transport/http.py::Handler._dispatch`

- 功能：HTTP、鉴权、DTO、组装与人审 CLI 的具名操作；流程见作用行，输入输出见本项签名与返回
- 输入：`self, path: str, q: dict, body: dict`。
- 输出：`None；None`。
- 作用：调用 HttpError, ROUTES.get, SignalClosed, getattr, getattr(self, handler), raw_sid.strip, self._reply, self.headers.get。
- 错误：异常 HttpError(403, TRIO_DISABLED[path]), SignalClosed(f'调查员不允许访问 {path}')。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：保留当前签名与 IO；[源码](../hybrid_memory/transport/http.py#L223)。

### `hybrid_memory/transport/http.py::Handler._run`

- 功能：统一错误映射
- 输入：`path/q/body`。
- 输出：`HTTP JSON 响应`。
- 作用：错误码→状态；未知故障 500 但可预见错误必须 4xx/5xx 明确。
- 错误：目标响应含稳定 code；能力 403 与预算 429 分开。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L238)。

### `hybrid_memory/transport/http.py::Handler.do_GET`

- 功能：鉴权→GET 白名单→dispatch
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 auth.authorized, parse_qs, parse_qs(u.query).items, self._reply, self._run, urlparse。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L263)。

### `hybrid_memory/transport/http.py::Handler.do_POST`

- 功能：鉴权→POST 白名单→body→dispatch
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 auth.authorized, dto.parse_body, self._reply, self._run, str, urlparse。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L277)。

### `hybrid_memory/transport/http.py::serve`

- 功能：HTTP 启动
- 输入：`service、port、host`。
- 输出：`ThreadingHTTPServer`。
- 作用：绑定 loopback；支持 port 0。
- 错误：端口占用显式失败。
- 目标：`hybrid_memory/transport/http.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/http.py#L293)。

## `hybrid_memory/transport/review_cli.py`

- 模块功能：HTTP、鉴权、DTO、组装与人审 CLI。
- 设计归属：传输与部署；处置：保留收口。
- 目标路径：`hybrid_memory/transport/review_cli.py`（当前路径）。
- 模块输入：argv 项目/端口与本地 token。
- 模块输出：规则审计输出或人审决定；skip 不写库。
- 源校验：`fb4b335937afa7c55ecb8fe2d33804a788ff82177e8552e163ddb29fa5ed70ea`。

### `hybrid_memory/transport/review_cli.py::main`

- 功能：人审/规则审计 CLI
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 (root / '.human-review-token').read_text, (root / '.human-review-token').read_text().strip, (root / '.memory-token').read_text, (root / '.memory-token').read_text().strip, Path, TaskStore, ap.add_argument, ap.parse_args, argparse.ArgumentParser, input, input('Choose accept_new / keep_old / skip: ').strip, json.dumps, post, print, store.close, store.disable_rule, store.rule_report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/review_cli.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/review_cli.py#L8)。

### `hybrid_memory/transport/review_cli.py::main.post`

- 功能：带 capability 的 HTTP 调用
- 输入：`path, payload, *, privileged=False`。
- 输出：`未注解；json.load(response)`。
- 作用：调用 Request, json.dumps, json.dumps(payload).encode, json.load, urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`hybrid_memory/transport/review_cli.py`；处置：保留收口；变更：按本项目标契约实施；[源码](../hybrid_memory/transport/review_cli.py#L30)。

## `hybrid_memory/triggers.py`

- 模块功能：确定性调度提示旧导入位。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/triggers.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：core.triggers 的确定性提示同一对象。
- 源校验：`9414efed81461b818818d808012f1f4cc51eb870474ceea4e15f79a15dbffcca`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：CORRECTION_RE ← hybrid_memory.core.triggers.CORRECTION_RE；DECISION_RE ← hybrid_memory.core.triggers.DECISION_RE；DISSATISFACTION_RE ← hybrid_memory.core.triggers.DISSATISFACTION_RE；LONG_TURN_CHARS ← hybrid_memory.core.triggers.LONG_TURN_CHARS；QUANT_RE ← hybrid_memory.core.triggers.QUANT_RE；is_correction ← hybrid_memory.core.triggers.is_correction；is_dissatisfaction ← hybrid_memory.core.triggers.is_dissatisfaction；scan_unit ← hybrid_memory.core.triggers.scan_unit；__all__ = ['CORRECTION_RE', 'DECISION_RE', 'DISSATISFACTION_RE', 'LONG_TURN_CHARS', 'QUANT_RE', 'is_correction', 'is_dissatisfaction', 'scan_unit']

## `hybrid_memory/worker.py`

- 模块功能：裸引擎 SignalWorker 旧导入位。
- 设计归属：兼容边界；处置：兼容保留。
- 目标路径：`hybrid_memory/worker.py`（当前路径）。
- 模块输入：旧导入位。
- 模块输出：legacy.worker 的 SignalWorker/KINDS 同一对象。
- 源校验：`3d09bcf3bd32092aa9734cd61b6fb3dfce4999a9e22d1e4e5aacc523f9a0f2ef`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：KINDS ← hybrid_memory.legacy.worker.KINDS；SignalWorker ← hybrid_memory.legacy.worker.SignalWorker；__all__ = ['KINDS', 'SignalWorker']

## `tests/characterization/test_task_machines.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/characterization/test_task_machines.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`e1fe9bc700f8db39b77f8e01d20a5f2ecd8c4d8f88c6f452363671ee35e6fcaf`。

### `tests/characterization/test_task_machines.py::Clock`

- 功能：测试场景/夹具/假实现：Clock；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L28)。

### `tests/characterization/test_task_machines.py::Clock.__init__`

- 功能：测试场景/夹具/假实现：Clock.__init__；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L29)。

### `tests/characterization/test_task_machines.py::Clock.__call__`

- 功能：测试场景/夹具/假实现：Clock.__call__；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`float；self.t`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L32)。

### `tests/characterization/test_task_machines.py::Clock.advance`

- 功能：测试场景/夹具/假实现：Clock.advance；输入输出见本项，生产不调用
- 输入：`self, dt: float`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L35)。

### `tests/characterization/test_task_machines.py::_norm_row`

- 功能：测试场景/夹具/假实现：_norm_row；输入输出见本项，生产不调用
- 输入：`store: TaskStore, tid: int`。
- 输出：`dict；row`。
- 作用：调用 store.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L39)。

### `tests/characterization/test_task_machines.py::_snap_state`

- 功能：测试场景/夹具/假实现：_snap_state；输入输出见本项，生产不调用
- 输入：`store: TaskStore`。
- 输出：`dict；{'tasks': [_norm_row(store, r['id']) for r in store.list_tasks()], 'revision': rev, 'checkpoint': blob.decode() if blob else None, 'checkpoint_error': ckpt_err, 'counts': store.stats(), 'queued': store.queued_counts()}`。
- 作用：调用 _norm_row, blob.decode, store.checkpoint, store.list_tasks, store.queued_counts, store.stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L45)。

### `tests/characterization/test_task_machines.py::Rec`

- 功能：场景记录器：每步记 {op, out, state}，out 中 token/异常归一化。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L63)。

### `tests/characterization/test_task_machines.py::Rec.__init__`

- 功能：测试场景/夹具/假实现：Rec.__init__；输入输出见本项，生产不调用
- 输入：`self, store: TaskStore`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L66)。

### `tests/characterization/test_task_machines.py::Rec.op`

- 功能：测试场景/夹具/假实现：Rec.op；输入输出见本项，生产不调用
- 输入：`self, name: str, out=None`。
- 输出：`None；None`。
- 作用：调用 _norm_out, _snap_state, self.steps.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L70)。

### `tests/characterization/test_task_machines.py::_norm_out`

- 功能：测试场景/夹具/假实现：_norm_out；输入输出见本项，生产不调用
- 输入：`out`。
- 输出：`未注解；[out[0], out[1]]；f'{type(out).__name__}: {out}'；out`。
- 作用：调用 dict, isinstance, len, out.get, type。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L75)。

### `tests/characterization/test_task_machines.py::_check`

- 功能：测试场景/夹具/假实现：_check；输入输出见本项，生产不调用
- 输入：`name: str, rec: Rec`。
- 输出：`None；None`。
- 作用：调用 '\n'.join, SNAP_DIR.mkdir, diff.append, enumerate, json.dumps, len, path.is_file, path.read_text, path.write_text, print, pytest.fail, text.splitlines, want.splitlines, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L88)。

### `tests/characterization/test_task_machines.py::_store`

- 功能：测试场景/夹具/假实现：_store；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`tuple[TaskStore, Clock]；(TaskStore(clock=clock), clock)`。
- 作用：调用 Clock, TaskStore。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L108)。

### `tests/characterization/test_task_machines.py::test_char_a_lifecycle`

- 功能：行为断言：char_a_lifecycle；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_a, _store, rec.op, store.close, store.enqueue, store.finish, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L116)。

### `tests/characterization/test_task_machines.py::test_char_a_retry_dead`

- 功能：行为断言：char_a_retry_dead；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_a, _store, clock.advance, range, rec.op, store.checkpoint, store.close, store.enqueue, store.get, store.retry。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L137)。

### `tests/characterization/test_task_machines.py::test_char_a_recover_and_gates`

- 功能：行为断言：char_a_recover_and_gates；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_a, _recover_a, _store, clock.advance, rec.op, store.close, store.enqueue, store.get, store.retry, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L159)。

### `tests/characterization/test_task_machines.py::test_char_a_pending_at_limit_dead_and_skip`

- 功能：行为断言：char_a_pending_at_limit_dead_and_skip；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_a, _recover_a, _store, clock.advance, range, rec.op, store.checkpoint, store.close, store.enqueue, store.finish, store.get, store.retry, store.skip_recent, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L191)。

### `tests/characterization/test_task_machines.py::test_char_a_checkpoint_conflict_no_daily_charge`

- 功能：行为断言：char_a_checkpoint_conflict_no_daily_charge；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_a, _store, rec.op, store.checkpoint, store.close, store.enqueue, store.get, store.runs_today, store.save_checkpoint。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L225)。

### `tests/characterization/test_task_machines.py::test_char_b_lifecycle_with_mutate_enqueue`

- 功能：行为断言：char_b_lifecycle_with_mutate_enqueue；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_b, _store, dict, rec.op, store._conn.execute, store._conn.execute('SELECT op_key,response FROM operations').fetchall, store._conn.execute('SELECT task_id,rule_id FROM agent_rule_uses').fetchall, store.close, store.complete, store.enqueue, store.get, store.semantic_stats, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L247)。

### `tests/characterization/test_task_machines.py::test_char_b_lifecycle_with_mutate_enqueue.mutate`

- 功能：测试场景/夹具/假实现：test_char_b_lifecycle_with_mutate_enqueue.mutate；输入输出见本项，生产不调用
- 输入：`conn, result`。
- 输出：`未注解；{'resolved': 1, 'recog_fail': True}`。
- 作用：调用 store._enqueue。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L261)。

### `tests/characterization/test_task_machines.py::test_char_b_retry_model_and_backoff`

- 功能：行为断言：char_b_retry_model_and_backoff；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, RuntimeError, ValueError, _check, _claim_b, _store, clock, clock.advance, delays.append, range, rec.op, store.close, store.enqueue, store.get, store.retry, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L280)。

### `tests/characterization/test_task_machines.py::test_char_b_trio_dead_at_five`

- 功能：行为断言：char_b_trio_dead_at_five；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, ValueError, _check, _claim_b, _store, clock.advance, range, rec.op, store.close, store.enqueue, store.get, store.retry。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L308)。

### `tests/characterization/test_task_machines.py::test_char_b_recover_and_gates`

- 功能：行为断言：char_b_recover_and_gates；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_b, _recover_b, _store, clock, clock.advance, rec.op, store.close, store.enqueue, store.get, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L330)。

### `tests/characterization/test_task_machines.py::test_char_enqueue_merge_dedupe_capacity`

- 功能：行为断言：char_enqueue_merge_dedupe_capacity；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _store, rec.op, store.close, store.enqueue, store.get, store.memory_next_id。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L358)。

### `tests/characterization/test_task_machines.py::test_char_receipts_and_captured_effects`

- 功能：行为断言：char_receipts_and_captured_effects；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _store, rec.op, store.apply_captured_effect, store.apply_unit, store.close, store.read_capture, store.remember_capture。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L385)。

### `tests/characterization/test_task_machines.py::test_char_apply_operation_replay_and_lease`

- 功能：行为断言：char_apply_operation_replay_and_lease；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_a, _store, rec.op, store.apply_operation, store.close, store.enqueue。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L417)。

### `tests/characterization/test_task_machines.py::test_char_rules_trace_reviews_stats`

- 功能：行为断言：char_rules_trace_reviews_stats；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Rec, _check, _claim_b, _store, clock, clock.advance, rec.op, store._conn.execute, store.close, store.complete, store.disable_rule, store.enqueue, store.pending_reviews, store.queued_counts, store.rule_report, store.rule_snapshot, store.rules_for, store.semantic_stats, store.store_result, store.workflow_trace。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L440)。

### `tests/characterization/test_task_machines.py::_claim_a`

- 功能：测试场景/夹具/假实现：_claim_a；输入输出见本项，生产不调用
- 输入：`store, tid, *, before=1, rev=0, lease_s=10, daily_cap=10, expected_version=None`。
- 输出：`未注解；store.claim(tid, before=before, origin='repair', day='2026-10-01', daily_cap=daily_cap, lease_s=lease_s, checkpoint=f'state-{rev}'.encode(), expected_revision=rev, expected_version=store.get(tid)['version'] if expected_version is None else expected_version)`。
- 作用：调用 f'state-{rev}'.encode, store.claim, store.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L492)。

### `tests/characterization/test_task_machines.py::_claim_b`

- 功能：测试场景/夹具/假实现：_claim_b；输入输出见本项，生产不调用
- 输入：`store, tid, *, lease_s=None, version=None`。
- 输出：`未注解；store.claim(tid, lease_s=lease_s, expected_version=store.get(tid)['version'] if version is None else version)`。
- 作用：调用 store.claim, store.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L502)。

### `tests/characterization/test_task_machines.py::_recover_a`

- 功能：测试场景/夹具/假实现：_recover_a；输入输出见本项，生产不调用
- 输入：`store, max_attempts, max_apply_attempts`。
- 输出：`未注解；None`。
- 作用：调用 store.recover_expired。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L509)。

### `tests/characterization/test_task_machines.py::_recover_b`

- 功能：测试场景/夹具/假实现：_recover_b；输入输出见本项，生产不调用
- 输入：`store`。
- 输出：`未注解；None`。
- 作用：调用 store.recover_expired。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/characterization/test_task_machines.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/characterization/test_task_machines.py#L515)。

## `tests/conftest.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/conftest.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`cfbcc1d7143d76e9a050c42e6ca829d206efd99dc56052b663b814b59c59c4ad`。

### `tests/conftest.py::repo_root`

- 功能：测试场景/夹具/假实现：repo_root；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`Path；Path(__file__).resolve().parents[1]`。
- 作用：调用 Path, Path(__file__).resolve, pytest.fixture。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/conftest.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/conftest.py#L14)。

## `tests/fakes.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/fakes.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`0c5c7d08a8e2a6c0a236710bfc4b8e6dbad1e40791350c4c578321350985e064`。

### `tests/fakes.py::Belief`

- 功能：测试场景/夹具/假实现：Belief；输入输出见本项，生产不调用
- 输入：`id: int；entity: int；scope: str；birth: int；value: str；death: int | None = None；noise: bool = False；phrasings: dict = field(default_factory=dict)`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L17)。

### `tests/fakes.py::Belief.alive`

- 功能：测试场景/夹具/假实现：Belief.alive；输入输出见本项，生产不调用
- 输入：`self, t: int`。
- 输出：`bool；self.birth <= t and (self.death is None or t < self.death)`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L27)。

### `tests/fakes.py::FakeWorld`

- 功能：预置 n 个互不相关的 belief（v0..v{n-1}）；其余按用例 spawn。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L31)。

### `tests/fakes.py::FakeWorld.__init__`

- 功能：测试场景/夹具/假实现：FakeWorld.__init__；输入输出见本项，生产不调用
- 输入：`self, n: int=20`。
- 输出：`未注解；None`。
- 作用：调用 range, self.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L34)。

### `tests/fakes.py::FakeWorld.spawn`

- 功能：测试场景/夹具/假实现：FakeWorld.spawn；输入输出见本项，生产不调用
- 输入：`self, value: str, *, entity: int | None=None, scope: str='', birth: int=0, death: int | None=None, noise: bool=False`。
- 输出：`Belief；b`。
- 作用：调用 Belief, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L41)。

### `tests/fakes.py::FakeWorld.set_value`

- 功能：belief 换值（旧措辞加撇号派生新措辞）。
- 输入：`self, belief_id: int, value: str`。
- 输出：`None；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L54)。

### `tests/fakes.py::FakeWorld.event`

- 功能：测试场景/夹具/假实现：FakeWorld.event；输入输出见本项，生产不调用
- 输入：`self, belief_id: int, j: int=0`。
- 输出：`Event；Event(b.id, b.value, b.phrasings[b.value][j])`。
- 作用：调用 Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L60)。

### `tests/fakes.py::FakeWorld.query`

- 功能：测试场景/夹具/假实现：FakeWorld.query；输入输出见本项，生产不调用
- 输入：`self, belief_id: int`。
- 输出：`Query；Query(b.id, f'what is b{b.id}:{b.scope} now?')`。
- 作用：调用 Query。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L64)。

### `tests/fakes.py::FakeWorld.judge`

- 功能：测试场景/夹具/假实现：FakeWorld.judge；输入输出见本项，生产不调用
- 输入：`self, a_bid: int, a_val: str, b_bid: int, b_val: str`。
- 输出：`str；'collision'；'contradiction'；'synonym' if a_val == b_val else 'update'`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L69)。

### `tests/fakes.py::FakeWorld.embedding_key`

- 功能：测试场景/夹具/假实现：FakeWorld.embedding_key；输入输出见本项，生产不调用
- 输入：`self, belief_id: int, value: str`。
- 输出：`tuple；(b.entity, b.id, value)`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L76)。

### `tests/fakes.py::FakeWorld.scope`

- 功能：测试场景/夹具/假实现：FakeWorld.scope；输入输出见本项，生产不调用
- 输入：`self, belief_id: int`。
- 输出：`str；self.beliefs[belief_id].scope`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L80)。

### `tests/fakes.py::FakeWorld.valid`

- 功能：测试场景/夹具/假实现：FakeWorld.valid；输入输出见本项，生产不调用
- 输入：`self, belief_id: int, value: str, t: int`。
- 输出：`bool；b.alive(t) and (not b.noise) and (b.value == value)`。
- 作用：调用 b.alive。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L83)。

### `tests/fakes.py::FakeWorld.relevant`

- 功能：测试场景/夹具/假实现：FakeWorld.relevant；输入输出见本项，生产不调用
- 输入：`self, belief_id: int, value: str, query: Query, t: int`。
- 输出：`bool；belief_id == query.target and self.valid(belief_id, value, t)`。
- 作用：调用 self.valid。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L87)。

### `tests/fakes.py::SyntheticEmbedder`

- 功能：把相似度结构捏在手里：entity 中心 → belief 偏移（同实体异 scope 的高相似对） → value 偏移 → 观测加噪。同 (belief, value) 高余弦（dedup 区）；同 entity 异 belief 在 τ_dup 带附近（压制区）；异 entity 低相似。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 Embedder`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L91)。

### `tests/fakes.py::SyntheticEmbedder.__init__`

- 功能：测试场景/夹具/假实现：SyntheticEmbedder.__init__；输入输出见本项，生产不调用
- 输入：`self, dim: int=64, scope_off: float=0.12, value_off: float=0.06, noise: float=0.15, seed: int=0`。
- 输出：`未注解；None`。
- 作用：调用 np.random.default_rng。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L96)。

### `tests/fakes.py::SyntheticEmbedder._unit`

- 功能：测试场景/夹具/假实现：SyntheticEmbedder._unit；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`np.ndarray；g / np.linalg.norm(g)`。
- 作用：调用 np.linalg.norm, self._rng.standard_normal。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L107)。

### `tests/fakes.py::SyntheticEmbedder._center`

- 功能：测试场景/夹具/假实现：SyntheticEmbedder._center；输入输出见本项，生产不调用
- 输入：`self, cache: dict, key, scale: float, base=None`。
- 输出：`np.ndarray；cache[key]`。
- 作用：调用 np.linalg.norm, self._unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L111)。

### `tests/fakes.py::SyntheticEmbedder.vec_for`

- 功能：测试场景/夹具/假实现：SyntheticEmbedder.vec_for；输入输出见本项，生产不调用
- 输入：`self, entity_id: int, belief_id: int, value: str`。
- 输出：`np.ndarray；obs / np.linalg.norm(obs)`。
- 作用：调用 np.linalg.norm, self._center, self._unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L117)。

### `tests/fakes.py::SyntheticEmbedder.embed`

- 功能：测试场景/夹具/假实现：SyntheticEmbedder.embed；输入输出见本项，生产不调用
- 输入：`self, texts: list[str], keys: list | None=None`。
- 输出：`np.ndarray；np.stack([self._center({}, ('t', t), 0) for t in texts])；np.stack([self.vec_for(*k) for k in keys])`。
- 作用：调用 np.stack, self._center, self.vec_for。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/fakes.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/fakes.py#L124)。

## `tests/integration/conftest.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/integration/conftest.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`4d40d6790e0366da2ad866344f9dbe14fe290ea013b8c04981ec23d10edf7493`。
- 输入/输出：本模块只有常量/数据契约，无独立函数；语义见模块输入/输出与备注。
- 导出/输入依赖：annotations ← __future__.annotations；Path ← pathlib.Path

## `tests/integration/test_http_contract.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/integration/test_http_contract.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`418de3009d6a17bd305bcb4d36fa383703417adf15bdbd564574eb6b04e967c3`。

### `tests/integration/test_http_contract.py::test_routes_cover_method_tables`

- 功能：行为断言：routes_cover_method_tables；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ROUTES.items, callable, getattr, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L16)。

### `tests/integration/test_http_contract.py::test_shim_reexports_canonical`

- 功能：行为断言：shim_reexports_canonical；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L23)。

### `tests/integration/test_http_contract.py::test_package_surface_is_minimal`

- 功能：行为断言：package_surface_is_minimal；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 hasattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L29)。

### `tests/integration/test_http_contract.py::test_auth_bearer`

- 功能：行为断言：auth_bearer；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 auth.authorized。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L38)。

### `tests/integration/test_http_contract.py::test_dto_observe_rejects_empty_turn`

- 功能：行为断言：dto_observe_rejects_empty_turn；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 dto.observe_payload, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L44)。

### `tests/integration/test_http_contract.py::test_token_files_are_0600`

- 功能：行为断言：token_files_are_0600；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _service, oct, os.stat, pytest.skip, stat.S_IMODE。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L50)。

### `tests/integration/test_http_contract.py::test_live_health_open_and_recall_guarded`

- 功能：行为断言：live_health_open_and_recall_guarded；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, err.value.close, post, pytest.raises, urllib.request.urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_http_contract.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_http_contract.py#L60)。

## `tests/integration/test_service_observe.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/integration/test_service_observe.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`72b0dc45a57da6da7a1982580e3a2d61c3711af8fe3c28f6429864addf553672`。

### `tests/integration/test_service_observe.py::Generator`

- 功能：测试场景/夹具/假实现：Generator；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L19)。

### `tests/integration/test_service_observe.py::Generator.__init__`

- 功能：测试场景/夹具/假实现：Generator.__init__；输入输出见本项，生产不调用
- 输入：`self, candidates=('unit fact',), scene='新场景'`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L20)。

### `tests/integration/test_service_observe.py::Generator.generate`

- 功能：测试场景/夹具/假实现：Generator.generate；输入输出见本项，生产不调用
- 输入：`self, window, prev_scene=''`。
- 输出：`未注解；CandidateGeneration(tuple((MemoryCandidate(x) for x in self.candidates)), self.scene)`。
- 作用：调用 CandidateGeneration, MemoryCandidate, self.calls.append, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L25)。

### `tests/integration/test_service_observe.py::_close`

- 功能：测试场景/夹具/假实现：_close；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；None`。
- 作用：调用 svc.log.close, svc.stop_unit_recovery, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L31)。

### `tests/integration/test_service_observe.py::test_online_registration_is_atomic_and_legacy_units_are_not_replayed`

- 功能：行为断言：online_registration_is_atomic_and_legacy_units_are_not_replayed；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, LogStore, _close, _svc, log._conn.execute, log.add_unit, log.append_unit, log.close, log.count, log.work, log.work_stats, pytest.raises, svc.log.get, svc.log.pending_units, svc.log.work, svc.process_pending_units。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L37)。

### `tests/integration/test_service_observe.py::test_valid_empty_generation_finishes_without_repeated_model_call`

- 功能：行为断言：valid_empty_generation_finishes_without_repeated_model_call；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, len, svc.log.work, svc.observe, svc.process_pending_units, svc.signals, svc.tasks.unit_receipt。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L58)。

### `tests/integration/test_service_observe.py::test_real_process_exit_recovers_each_cross_db_boundary`

- 功能：行为断言：real_process_exit_recovers_each_cross_db_boundary；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, stage`。
- 输出：`未注解；None`。
- 作用：调用 Generator, Path, Path(__file__).resolve, _close, _svc, len, out.stderr.decode, pytest.mark.parametrize, str, subprocess.run, svc.log.count, svc.log.get, svc.log.work, svc.process_pending_units, svc.start_unit_recovery, svc.tasks.queued_counts, svc.tasks.unit_receipt, time.monotonic, time.sleep。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L74)。

### `tests/integration/test_service_observe.py::test_saved_result_survives_full_queue_and_retries_without_new_model_call`

- 功能：行为断言：saved_result_survives_full_queue_and_retries_without_new_model_call；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _http, _svc, get, len, post, svc.log._conn.execute, svc.log.count, svc.log.work, svc.process_pending_units, svc.report_miss, svc.tasks._conn.execute, svc.tasks.queued_counts, svc.tasks.unit_receipt。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L119)。

### `tests/integration/test_service_observe.py::test_sql_failure_rolls_back_effect_and_volatile_signal_in_place`

- 功能：行为断言：sql_failure_rolls_back_effect_and_volatile_signal_in_place；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, len, monkeypatch.setattr, pytest.raises, q.peek_kinds, svc.log._conn.execute, svc.log.work, svc.observe, svc.process_pending_units, svc.tasks._conn.execute, svc.tasks.checkpoint, svc.tasks.queued_counts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L143)。

### `tests/integration/test_service_observe.py::test_sql_failure_rolls_back_effect_and_volatile_signal_in_place.extra_signal`

- 功能：测试场景/夹具/假实现：test_sql_failure_rolls_back_effect_and_volatile_signal_in_place.extra_signal；输入输出见本项，生产不调用
- 输入：`t`。
- 输出：`未注解；None`。
- 作用：调用 old, q.emit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L149)。

### `tests/integration/test_service_observe.py::test_duplicate_processing_and_concurrent_observe_do_not_reapply`

- 功能：行为断言：duplicate_processing_and_concurrent_observe_do_not_reapply；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, ThreadPoolExecutor, _close, _svc, entered.wait, first.result, len, pool.submit, release.set, second.result, svc.log.pending_units, svc.log.work_stats, svc.process_pending_units, svc.tasks.list_tasks, svc.tasks.unit_receipt, threading.Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L173)。

### `tests/integration/test_service_observe.py::test_duplicate_processing_and_concurrent_observe_do_not_reapply.blocked`

- 功能：测试场景/夹具/假实现：test_duplicate_processing_and_concurrent_observe_do_not_reapply.blocked；输入输出见本项，生产不调用
- 输入：`*args`。
- 输出：`未注解；original(*args)`。
- 作用：调用 entered.set, original, release.wait。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L178)。

### `tests/integration/test_service_observe.py::test_correction_keeps_prior_retrieval_even_across_restart`

- 功能：行为断言：correction_keeps_prior_retrieval_even_across_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _service, _svc, pytest.raises, restored.log.get, restored.process_pending_units, restored.tasks.list_tasks, svc.feedback, svc.log.get, svc.log.work, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L209)。

### `tests/integration/test_service_observe.py::test_correction_keeps_prior_retrieval_even_across_restart.stop`

- 功能：测试场景/夹具/假实现：test_correction_keeps_prior_retrieval_even_across_restart.stop；输入输出见本项，生产不调用
- 输入：`*args`。
- 输出：`未注解；None`。
- 作用：调用 SystemExit。
- 错误：异常 SystemExit('simulated interruption after append')。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L219)。

### `tests/integration/test_service_observe.py::test_uncertain_effect_commit_requires_restart`

- 功能：行为断言：uncertain_effect_commit_requires_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, len, monkeypatch.setattr, pytest.raises, restored.process_pending_units, svc.log.work, svc.observe, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L246)。

### `tests/integration/test_service_observe.py::test_uncertain_effect_commit_requires_restart.commit_then_lie`

- 功能：测试场景/夹具/假实现：test_uncertain_effect_commit_requires_restart.commit_then_lie；输入输出见本项，生产不调用
- 输入：`*args`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, original。
- 错误：异常 RuntimeError('commit acknowledgement lost')。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L250)。

### `tests/integration/test_service_observe.py::test_handoff_sql_failure_keeps_entire_unit_retriable`

- 功能：行为断言：handoff_sql_failure_keeps_entire_unit_retriable；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, len, pytest.raises, svc.log._conn.execute, svc.log.work, svc.observe, svc.process_pending_units, svc.tasks._conn.execute, svc.tasks.checkpoint, svc.tasks.queued_counts, svc.tasks.unit_receipt。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L271)。

### `tests/integration/test_service_observe.py::test_ack_retry_after_later_checkpoint_does_not_repeat_effect`

- 功能：行为断言：ack_retry_after_later_checkpoint_does_not_repeat_effect；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, len, monkeypatch.setattr, pytest.raises, svc.log.work, svc.observe, svc.process_pending_units, svc.save, svc.tasks.list_tasks, svc.tasks.unit_receipt。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L292)。

### `tests/integration/test_service_observe.py::test_ack_retry_after_later_checkpoint_does_not_repeat_effect.unavailable`

- 功能：测试场景/夹具/假实现：test_ack_retry_after_later_checkpoint_does_not_repeat_effect.unavailable；输入输出见本项，生产不调用
- 输入：`*_`。
- 输出：`未注解；None`。
- 作用：调用 OSError。
- 错误：异常 OSError('log ack unavailable')。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L297)。

### `tests/integration/test_service_observe.py::test_upgrade_creates_work_table_without_replaying_old_rows`

- 功能：行为断言：upgrade_creates_work_table_without_replaying_old_rows；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, conn.execute, sqlite3.connect, store.append_unit, store.close, store.get, store.pending_units, store.work。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L317)。

### `tests/integration/test_service_observe.py::test_unit_failure_preserves_existing_memory_and_retrieval_identity`

- 功能：行为断言：unit_failure_preserves_existing_memory_and_retrieval_identity；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, pytest.raises, svc.log._conn.execute, svc.observe, svc.process_pending_units, svc.recall, svc.tasks._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L334)。

### `tests/integration/test_service_observe.py::test_retrying_older_unit_blocks_newer_unit_without_losing_either`

- 功能：行为断言：retrying_older_unit_blocks_newer_unit_without_losing_either；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, len, list, pytest.raises, svc.log._conn.execute, svc.log.get, svc.log.pending_units, svc.log.work, svc.observe, svc.process_pending_units, svc.report_miss, svc.tasks._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L356)。

### `tests/integration/test_service_observe.py::test_same_observe_request_id_is_one_unit_and_conflict_does_not_rebind`

- 功能：行为断言：same_observe_request_id_is_one_unit_and_conflict_does_not_rebind；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, pytest.raises, svc.log.capture_receipt, svc.log.count, svc.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L400)。

### `tests/integration/test_service_observe.py::test_capture_receipt_rolls_back_with_the_unit`

- 功能：行为断言：capture_receipt_rolls_back_with_the_unit；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _svc, pytest.raises, svc.log._conn.execute, svc.log.capture_receipt, svc.log.count, svc.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L419)。

### `tests/integration/test_service_observe.py::test_http_capacity_503_is_accepted_and_retry_does_not_append`

- 功能：行为断言：http_capacity_503_is_accepted_and_retry_does_not_append；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, _close, _http, _svc, len, post, svc.log._conn.execute, svc.log.count, svc.process_pending_units, svc.report_miss, svc.tasks._conn.execute, svc.tasks.unit_receipt。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L432)。

### `tests/integration/test_service_observe.py::test_concurrent_same_request_id_appends_once`

- 功能：行为断言：concurrent_same_request_id_appends_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, ThreadPoolExecutor, _close, _http, _svc, all, body.get, list, pool.map, range, svc.log.count。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L466)。

### `tests/integration/test_service_observe.py::test_concurrent_same_request_id_appends_once.once`

- 功能：测试场景/夹具/假实现：test_concurrent_same_request_id_appends_once.once；输入输出见本项，生产不调用
- 输入：`_`。
- 输出：`未注解；post('/observe', {'user_text': '并发', 'assistant_text': '一次', 'request_id': 'concurrent-id-01'})`。
- 作用：调用 post。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L470)。

### `tests/integration/test_service_observe.py::test_process_exit_after_observe_receipt_replays_same_unit`

- 功能：行为断言：process_exit_after_observe_receipt_replays_same_unit；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Generator, Path, Path(__file__).resolve, _close, _svc, len, out.stderr.decode, str, subprocess.run, svc.log.count, svc.observe, svc.tasks.queued_counts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L483)。

### `tests/integration/test_service_observe.py::test_feedback_receipt_survives_response_loss_and_eviction`

- 功能：行为断言：feedback_receipt_survives_response_loss_and_eviction；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, first.get, len, pytest.raises, svc._retrievals.pop, svc.feedback, svc.tasks.list_tasks, svc.tasks.list_tasks(kinds=('feedback_pending',)).__len__。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L511)。

### `tests/integration/test_service_observe.py::test_feedback_receipt_survives_response_loss_and_eviction.no_worker`

- 功能：测试场景/夹具/假实现：test_feedback_receipt_survives_response_loss_and_eviction.no_worker；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`未注解；{}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L514)。

### `tests/integration/test_service_observe.py::test_process_exit_after_feedback_commit_replays_without_second_task`

- 功能：行为断言：process_exit_after_feedback_commit_replays_without_second_task；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(__file__).resolve, _close, _service, iter, len, next, out.stderr.decode, str, subprocess.run, svc._retrievals.clear, svc.feedback, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L531)。

### `tests/integration/test_service_observe.py::test_old_log_database_gains_capture_table_without_replaying_units`

- 功能：行为断言：old_log_database_gains_capture_table_without_replaying_units；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, conn.execute, sqlite3.connect, store.append_unit, store.capture_receipt, store.close, store.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L560)。

### `tests/integration/test_service_observe.py::test_feedback_capacity_failure_keeps_no_receipt`

- 功能：行为断言：feedback_capacity_failure_keeps_no_receipt；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, pytest.raises, svc.feedback, svc.report_miss, svc.tasks.list_tasks, svc.tasks.read_capture。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L579)。

### `tests/integration/test_service_observe.py::test_http_feedback_retry_and_already_credited_are_distinct`

- 功能：行为断言：http_feedback_retry_and_already_credited_are_distinct；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _http, _prepared, len, post, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L593)。

### `tests/integration/test_service_observe.py::_prepared`

- 功能：测试场景/夹具/假实现：_prepared；输入输出见本项，生产不调用
- 输入：`tmp_path`。
- 输出：`未注解；(svc, svc.recall('部署在哪')['retrieval_id'])`。
- 作用：调用 _service, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_observe.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_observe.py#L613)。

## `tests/integration/test_service_recall.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/integration/test_service_recall.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`8fc63b62bf9ee1982c0ebd49249aa01a8c28e8771c27f47e98d7a24e81022c3f`。

### `tests/integration/test_service_recall.py::_close`

- 功能：测试场景/夹具/假实现：_close；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；None`。
- 作用：调用 svc.log.close, svc.stop_unit_recovery, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L17)。

### `tests/integration/test_service_recall.py::_suppressed`

- 功能：测试场景/夹具/假实现：_suppressed；输入输出见本项，生产不调用
- 输入：`tmp_path`。
- 输出：`未注解；svc`。
- 作用：调用 Cfg, MemoryService, RealChatSemantics, _FixedGenerator, _TableEmbedder, len, np.array, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L23)。

### `tests/integration/test_service_recall.py::test_shadow_pending_survives_restart_and_settles_once`

- 功能：行为断言：shadow_pending_survives_restart_and_settles_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, MemoryService, Path, Path(__file__).resolve, RealChatSemantics, _FixedGenerator, _TableEmbedder, _close, again.engine.mems.values, again.engine.submit_verdicts, len, next, out.stderr.decode, str, subprocess.run, svc.resolve。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L42)。

### `tests/integration/test_service_recall.py::test_late_shadow_credits_successor_not_retired_member`

- 功能：行为断言：late_shadow_credits_successor_not_retired_member；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _suppressed, next, svc.engine.mems.values, svc.observe, svc.resolve。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L78)。

### `tests/integration/test_service_recall.py::test_feedback_after_registry_retirement_credits_once`

- 功能：行为断言：feedback_after_registry_retirement_credits_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, svc._retrievals.pop, svc.feedback, svc.observe, svc.recall, type, type(svc).process_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L98)。

### `tests/integration/test_service_recall.py::test_late_feedback_does_not_revive_superseded_memory`

- 功能：行为断言：late_feedback_does_not_revive_superseded_memory；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, old.emb.copy, svc.feedback, svc.observe, svc.recall, type, type(old), type(svc).process_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L116)。

### `tests/integration/test_service_recall.py::test_old_checkpoint_without_shadow_pending_loads_empty`

- 功能：行为断言：old_checkpoint_without_shadow_pending_loads_empty；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, pickle.dumps, pytest.raises, svc._load, svc._state。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L137)。

### `tests/integration/test_service_recall.py::test_existing_source_id_does_not_authenticate_unrelated_text`

- 功能：行为断言：existing_source_id_does_not_authenticate_unrelated_text；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, list, svc.engine.mems.values, svc.observe, svc.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L160)。

### `tests/integration/test_service_recall.py::test_long_identifier_cannot_ride_on_a_real_span`

- 功能：行为断言：long_identifier_cannot_ride_on_a_real_span；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, svc.observe, svc.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L176)。

### `tests/integration/test_service_recall.py::test_ungrounded_candgen_is_not_stored_as_window_memory`

- 功能：行为断言：ungrounded_candgen_is_not_stored_as_window_memory；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ChatGenerator, _close, _service, svc.observe, svc.tasks.queued_counts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L188)。

### `tests/integration/test_service_recall.py::test_grounding_rule_rejects_unverifiable_short_text`

- 功能：行为断言：grounding_rule_rejects_unverifiable_short_text；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _content_grounded。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L200)。

### `tests/integration/test_service_recall.py::test_contested_bound`

- 功能：H29:BASELINE #3 的 16 行场景(5 入选 + 11 未决冲突)→ 8 行 + truncated=true。 每条入选记忆至多带 1 个对手、总 contested 行不超过 CONTESTED_K(3)。
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Retrieval, len, list, mem, range, recall_svc.context_lines, recall_svc.recall_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L205)。

### `tests/integration/test_service_recall.py::test_contested_bound.mem`

- 功能：测试场景/夹具/假实现：test_contested_bound.mem；输入输出见本项，生产不调用
- 输入：`i, text`。
- 输出：`未注解；Memory(id=i, belief_id=i, value=text, text=text, emb=np.zeros(4), birth=i, src={i}, pool=Pool.CANDIDATE)`。
- 作用：调用 Memory, np.zeros。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_recall.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_recall.py#L213)。

## `tests/integration/test_service_review.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/integration/test_service_review.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`3550a37862556e122032e08550f4d7d0efad3e98a84f9065d049c172069da221`。

### `tests/integration/test_service_review.py::drain`

- 功能：测试场景/夹具/假实现：drain；输入输出见本项，生产不调用
- 输入：`worker, n=6`。
- 输出：`未注解；None`。
- 作用：调用 range, worker.process_once。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_review.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_review.py#L14)。

### `tests/integration/test_service_review.py::test_conflict_quarantined_until_human_review_and_stale_version_stays_hidden`

- 功能：行为断言：conflict_quarantined_until_human_review_and_stale_version_stays_hidden；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, Query, _svc, drain, len, pytest.raises, svc.decide_human_review, svc.emb.embed, svc.engine.retrieve, svc.human_reviews, svc.log.close, svc.observe, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_review.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_review.py#L20)。

### `tests/integration/test_service_review.py::test_conflict_quarantined_until_human_review_and_stale_version_stays_hidden.fake`

- 功能：测试场景/夹具/假实现：test_conflict_quarantined_until_human_review_and_stale_version_stays_hidden.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': [{'text': text, 'source_unit_ids': [p['unit_id']]}]}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE' if p['unit_id'] == 0 else 'CONFLICT', **({'target_id': 0} if p['unit_id'] else {})}]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_review.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_review.py#L24)。

### `tests/integration/test_service_review.py::test_review_http_requires_independent_human_capability`

- 功能：行为断言：review_http_requires_independent_human_capability；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, call, drain, httpd.server_close, httpd.shutdown, len, serve, svc.log.close, svc.observe, svc.tasks.close, thread.join, thread.start, threading.Thread。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_review.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_review.py#L60)。

### `tests/integration/test_service_review.py::test_review_http_requires_independent_human_capability.fake`

- 功能：测试场景/夹具/假实现：test_review_http_requires_independent_human_capability.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': [{'text': f"端口现在是 {(8080 if p['unit_id'] == 0 else 9090)}", 'source_unit_ids': [p['unit_id']]}]}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE' if p['unit_id'] == 0 else 'CONFLICT', **({'target_id': 0} if p['unit_id'] else {})}]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_review.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_review.py#L67)。

### `tests/integration/test_service_review.py::test_review_http_requires_independent_human_capability.call`

- 功能：测试场景/夹具/假实现：test_review_http_requires_independent_human_capability.call；输入输出见本项，生产不调用
- 输入：`path, data, token=''`。
- 输出：`未注解；(exc.code, json.load(exc))；(r.status, json.load(r))`。
- 作用：调用 Request, json.dumps, json.dumps(data).encode, json.load, urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/integration/test_service_review.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/integration/test_service_review.py#L80)。

## `tests/manual_opencode_smoke.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/manual_opencode_smoke.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`b9d606cf64697c26dd2b26b58eb060c53086efbeed57a1b61f8c5b6b05b9bbe5`。

### `tests/manual_opencode_smoke.py::MockModel`

- 功能：测试场景/夹具/假实现：MockModel；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 BaseHTTPRequestHandler`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/manual_opencode_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/manual_opencode_smoke.py#L21)。

### `tests/manual_opencode_smoke.py::MockModel.log_message`

- 功能：测试场景/夹具/假实现：MockModel.log_message；输入输出见本项，生产不调用
- 输入：`self, *_`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/manual_opencode_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/manual_opencode_smoke.py#L22)。

### `tests/manual_opencode_smoke.py::MockModel.do_POST`

- 功能：测试场景/夹具/假实现：MockModel.do_POST；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`未注解；None`。
- 作用：调用 '\n'.join, ('data: ' + json.dumps(event) + '\n\n').encode, chunk, int, json.dumps, json.loads, prompt.replace, request.get, self.end_headers, self.rfile.read, self.rfile.read(int(self.headers['Content-Length'])).decode, self.send_header, self.send_response, self.wfile.flush, self.wfile.write, texts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/manual_opencode_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/manual_opencode_smoke.py#L25)。

### `tests/manual_opencode_smoke.py::MockModel.do_POST.texts`

- 功能：测试场景/夹具/假实现：MockModel.do_POST.texts；输入输出见本项，生产不调用
- 输入：`obj`。
- 输出：`未注解；[]；[item for x in obj for item in texts(x)]；[item for x in obj.values() for item in texts(x)]；[obj]`。
- 作用：调用 isinstance, obj.values, texts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/manual_opencode_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/manual_opencode_smoke.py#L28)。

### `tests/manual_opencode_smoke.py::MockModel.do_POST.chunk`

- 功能：测试场景/夹具/假实现：MockModel.do_POST.chunk；输入输出见本项，生产不调用
- 输入：`delta, reason`。
- 输出：`未注解；{'id': 'local-mock', 'object': 'chat.completion.chunk', 'created': 1, 'model': request.get('model', 'echo'), 'choices': [{'index': 0, 'delta': delta, 'finish_reason': reason}]}`。
- 作用：调用 request.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/manual_opencode_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/manual_opencode_smoke.py#L51)。

### `tests/manual_opencode_smoke.py::main`

- 功能：测试场景/夹具/假实现：main；输入输出见本项，生产不调用
- 输入：`executable`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, OpenCodeRunner, Path, Thread, ThreadingHTTPServer, _svc, httpd.server_close, httpd.shutdown, json.dumps, len, os.environ.get, os.environ.pop, print, range, svc.log.close, svc.observe, svc.tasks.close, svc.tasks.list_tasks, svc.tasks.rule_report, tempfile.TemporaryDirectory, thread.join, thread.start, worker.process_once。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/manual_opencode_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/manual_opencode_smoke.py#L62)。

## `tests/test_candgen_real.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_candgen_real.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`eeaeb34cb0aadb772b80f168c77957346871e16ceafaec7b05e4117229a4784e`。

### `tests/test_candgen_real.py::_StubEmbedder`

- 功能：测试场景/夹具/假实现：_StubEmbedder；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L22)。

### `tests/test_candgen_real.py::_StubEmbedder.__init__`

- 功能：测试场景/夹具/假实现：_StubEmbedder.__init__；输入输出见本项，生产不调用
- 输入：`self, table`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L23)。

### `tests/test_candgen_real.py::_StubEmbedder.embed`

- 功能：测试场景/夹具/假实现：_StubEmbedder.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array([self.table[t] for t in texts], dtype=np.float32)`。
- 作用：调用 np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L26)。

### `tests/test_candgen_real.py::_unit`

- 功能：测试场景/夹具/假实现：_unit；输入输出见本项，生产不调用
- 输入：`i`。
- 输出：`未注解；InteractionUnit(id=i, start_time=i, end_time=i, user_text=f'q{i}', assistant_text=f'a{i}', assistant_turns=1)`。
- 作用：调用 InteractionUnit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L30)。

### `tests/test_candgen_real.py::test_normalize_strips_case_ws_punct`

- 功能：行为断言：normalize_strips_case_ws_punct；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 normalize。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L36)。

### `tests/test_candgen_real.py::test_redact_secrets`

- 功能：行为断言：redact_secrets；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 redact_secrets。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L41)。

### `tests/test_candgen_real.py::test_parse_candidates_json_array_and_redact`

- 功能：行为断言：parse_candidates_json_array_and_redact；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 parse_generation, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L60)。

### `tests/test_candgen_real.py::test_parse_generation_v2_envelope_and_v1_fallback`

- 功能：行为断言：parse_generation_v2_envelope_and_v1_fallback；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 parse_generation。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L70)。

### `tests/test_candgen_real.py::test_priority_to_salience_mapping`

- 功能：行为断言：priority_to_salience_mapping；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 priority_to_salience。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L82)。

### `tests/test_candgen_real.py::test_parse_generation_salience_clamp_and_fallback`

- 功能：行为断言：parse_generation_salience_clamp_and_fallback；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 parse_generation。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L92)。

### `tests/test_candgen_real.py::test_serialize_window_carries_prev_scene`

- 功能：行为断言：serialize_window_carries_prev_scene；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 InteractionWindow, _unit, serialize_window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L104)。

### `tests/test_candgen_real.py::test_serialize_window_role_structure`

- 功能：行为断言：serialize_window_role_structure；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 InteractionWindow, _unit, serialize_window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L112)。

### `tests/test_candgen_real.py::test_real_semantics_judge_levels`

- 功能：行为断言：real_semantics_judge_levels；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Path, RealChatSemantics, json.dumps, normalize, p.write_text, sem.judge, sem2.judge, tempfile.TemporaryDirectory。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L120)。

### `tests/test_candgen_real.py::test_pending_tension_stays_in_backlog`

- 功能：真实 judge 未标注时，worker 回报 pending，tension 不消解。
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, MemoryEngine, RealChatSemantics, SignalWorker, _StubEmbedder, eng.observe, eng.step, iter, len, next, normalize, np.array, range, sem.fingerprint, sorted, tuple, worker.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L135)。

### `tests/test_candgen_real.py::test_chat_generator_uses_injected_transport_and_shared_prompt`

- 功能：行为断言：chat_generator_uses_injected_transport_and_shared_prompt；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ChatGenerator, ChatGenerator(chat_fn).generate, InteractionWindow, _unit, serialize_window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L163)。

### `tests/test_candgen_real.py::test_chat_generator_uses_injected_transport_and_shared_prompt.chat_fn`

- 功能：测试场景/夹具/假实现：test_chat_generator_uses_injected_transport_and_shared_prompt.chat_fn；输入输出见本项，生产不调用
- 输入：`system, user`。
- 输出：`未注解；'{"scene_name":"new scene","memories":[{"text":"fact"}]}'`。
- 作用：调用 calls.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L169)。

### `tests/test_candgen_real.py::test_candidate_malformed_metadata_is_bounded`

- 功能：行为断言：candidate_malformed_metadata_is_bounded；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`src`。
- 输出：`未注解；None`。
- 作用：调用 float, isinstance, parse_candidate, pytest.mark.parametrize。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L182)。

### `tests/test_candgen_real.py::test_invalid_generation_is_not_successful_empty_or_nested_metadata`

- 功能：行为断言：invalid_generation_is_not_successful_empty_or_nested_metadata；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 parse_generation, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_candgen_real.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_candgen_real.py#L191)。

## `tests/test_durable_tasks.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_durable_tasks.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`f0c773dcdb14498d997ced807aa2390f3b95711d799c9fa45548e40e8467364b`。

### `tests/test_durable_tasks.py::_queued`

- 功能：测试场景/夹具/假实现：_queued；输入输出见本项，生产不调用
- 输入：`path=None`。
- 输出：`未注解；svc`。
- 作用：调用 _svc, svc.log.add_unit, svc.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L14)。

### `tests/test_durable_tasks.py::_close`

- 功能：测试场景/夹具/假实现：_close；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；None`。
- 作用：调用 svc.log.close, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L21)。

### `tests/test_durable_tasks.py::test_emitted_task_survives_restart_without_save_or_worker`

- 功能：行为断言：emitted_task_survives_restart_without_save_or_worker；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _close, _fake, _queued, _svc, agent.process_once, restored.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L26)。

### `tests/test_durable_tasks.py::test_durable_jobs_do_not_compete_with_volatile_queue_capacity`

- 功能：行为断言：durable_jobs_do_not_compete_with_volatile_queue_capacity；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.process_once, len, range, svc.engine.drain_signals, svc.engine.signals.emit, svc.engine.signals.peek_kinds, svc.report_miss, svc.tasks.list_tasks, svc.tasks.queued_counts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L38)。

### `tests/test_durable_tasks.py::test_apply_failure_keeps_result_and_rest_of_batch`

- 功能：行为断言：apply_failure_keeps_result_and_rest_of_batch；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _queued, agent.process_once, all, iter, len, monkeypatch.setattr, next, svc.engine.mems.values, svc.report_miss, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L52)。

### `tests/test_durable_tasks.py::test_apply_failure_keeps_result_and_rest_of_batch.fail_once`

- 功能：测试场景/夹具/假实现：test_apply_failure_keeps_result_and_rest_of_batch.fail_once；输入输出见本项，生产不调用
- 输入：`events, t`。
- 输出：`未注解；original(events, t)`。
- 作用：调用 RuntimeError, failures.pop, original。
- 错误：异常 RuntimeError('apply failed after mutation')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L60)。

### `tests/test_durable_tasks.py::test_partial_result_retry_does_not_repeat_first_effect_or_diagnosis`

- 功能：行为断言：partial_result_retry_does_not_repeat_first_effect_or_diagnosis；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _close, _fake, _queued, _svc, agent.process_once, all, monkeypatch.setattr, restored.engine.mems.values, resumed.process_once。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L80)。

### `tests/test_durable_tasks.py::test_partial_result_retry_does_not_repeat_first_effect_or_diagnosis.fail_second`

- 功能：测试场景/夹具/假实现：test_partial_result_retry_does_not_repeat_first_effect_or_diagnosis.fail_second；输入输出见本项，生产不调用
- 输入：`events, t`。
- 输出：`未注解；original(events, t)`。
- 作用：调用 RuntimeError, original。
- 错误：异常 RuntimeError('second proposal failed')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L87)。

### `tests/test_durable_tasks.py::test_effect_checkpoint_precedes_ack_and_is_not_lost_to_stale_pickle`

- 功能：行为断言：effect_checkpoint_precedes_ack_and_is_not_lost_to_stale_pickle；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, fake).process_once, _close, _fake, _queued, _svc, agent.process_once, iter, monkeypatch.setattr, next, restored.engine.mems.values, restored.tasks.list_tasks, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L110)。

### `tests/test_durable_tasks.py::test_effect_checkpoint_precedes_ack_and_is_not_lost_to_stale_pickle.fail_ack`

- 功能：测试场景/夹具/假实现：test_effect_checkpoint_precedes_ack_and_is_not_lost_to_stale_pickle.fail_ack；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('ack unavailable')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L113)。

### `tests/test_durable_tasks.py::test_daily_cap_and_dedupe_survive_restart`

- 功能：行为断言：daily_cap_and_dedupe_survive_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, fake, daily_cap=1).process_once, AgentWorker(svc, _fake(diagnosis={'miss_type': 'no_miss'}), daily_cap=1).process_once, _close, _fake, _queued, _svc, restored.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L133)。

### `tests/test_durable_tasks.py::test_investigation_attempts_are_durable_and_exhaustion_is_visible`

- 功能：行为断言：investigation_attempts_are_durable_and_exhaustion_is_visible；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _close, _queued, _svc, agent.process_once, restored.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L149)。

### `tests/test_durable_tasks.py::test_tool_and_final_proposal_and_diagnosis_are_idempotent_within_task`

- 功能：行为断言：tool_and_final_proposal_and_diagnosis_are_idempotent_within_task；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(svc, investigate).process_once, _queued, iter, next, svc.engine.mems.values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L166)。

### `tests/test_durable_tasks.py::test_tool_and_final_proposal_and_diagnosis_are_idempotent_within_task.investigate`

- 功能：测试场景/夹具/假实现：test_tool_and_final_proposal_and_diagnosis_are_idempotent_within_task.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；Investigation(proposals=[dict(PROPOSAL, kind='work_fact', salience=0.5, entity_key='', supersedes=[])], diagnosis={'miss_type': 'no_miss', 'note': 'same'})`。
- 作用：调用 Investigation, dict, svc.diagnose, svc.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L169)。

### `tests/test_durable_tasks.py::test_durable_checkpoint_corruption_fails_closed`

- 功能：行为断言：durable_checkpoint_corruption_fails_closed；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, corruption`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once, _close, _fake, _queued, _svc, pytest.mark.parametrize, pytest.raises, svc.tasks._conn.execute。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L183)。

### `tests/test_durable_tasks.py::test_expired_running_lease_recovers_and_rejects_old_token`

- 功能：行为断言：expired_running_lease_recovers_and_rejects_old_token；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, fake).process_once, InvestigationContext, _close, _fake, _queued, _svc, agent._claim, pytest.raises, restored.propose, restored.tasks.list_tasks, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L196)。

### `tests/test_durable_tasks.py::test_expired_applying_lease_replays_receipt_not_effect`

- 功能：行为断言：expired_applying_lease_replays_receipt_not_effect；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, fake, daily_cap=0).process_once, Investigation, InvestigationContext, _close, _fake, _queued, _svc, agent._claim, asdict, iter, next, restored.engine.mems.values, restored.tasks.get, svc._dump_state, svc.propose, svc.tasks.get, svc.tasks.list_tasks, svc.tasks.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L220)。

### `tests/test_durable_tasks.py::test_sqlite_receipt_failure_rolls_back_checkpoint_and_preserves_memory_identity`

- 功能：行为断言：sqlite_receipt_failure_rolls_back_checkpoint_and_preserves_memory_identity；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _queued, agent.process_once, len, svc.propose, svc.recall, svc.tasks._conn.execute, svc.tasks.stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L248)。

### `tests/test_durable_tasks.py::test_uncertain_commit_stops_service_until_restart`

- 功能：行为断言：uncertain_commit_stops_service_until_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, _fake()).process_once, AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once, _close, _fake, _http, _queued, _svc, get, monkeypatch.setattr, pytest.raises, restored.tasks.list_tasks, svc.observe, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L269)。

### `tests/test_durable_tasks.py::test_uncertain_commit_stops_service_until_restart.commit_then_raise`

- 功能：测试场景/夹具/假实现：test_uncertain_commit_stops_service_until_restart.commit_then_raise；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, original。
- 错误：异常 RuntimeError('lost commit acknowledgement')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L275)。

### `tests/test_durable_tasks.py::test_retry_backoff_and_application_exhaustion_are_durable`

- 功能：行为断言：retry_backoff_and_application_exhaustion_are_durable；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, _fake()).process_once, _close, _fake, _queued, _svc, agent.process_once, len, monkeypatch.setattr, restored.signals, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L301)。

### `tests/test_durable_tasks.py::test_retry_backoff_and_application_exhaustion_are_durable.boom`

- 功能：测试场景/夹具/假实现：test_retry_backoff_and_application_exhaustion_are_durable.boom；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('permanent embedding outage')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L307)。

### `tests/test_durable_tasks.py::test_signal_merge_is_durable_but_running_task_payload_is_frozen`

- 功能：行为断言：signal_merge_is_durable_but_running_task_payload_is_frozen；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _queued, agent.process_once, len, svc.report_miss, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L329)。

### `tests/test_durable_tasks.py::test_signal_merge_is_durable_but_running_task_payload_is_frozen.investigate`

- 功能：测试场景/夹具/假实现：test_signal_merge_is_durable_but_running_task_payload_is_frozen.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；Investigation(diagnosis={'miss_type': 'no_miss'})`。
- 作用：调用 Investigation, len, seen.append, svc.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L335)。

### `tests/test_durable_tasks.py::test_enqueue_failure_does_not_mutate_volatile_signal_or_claim_success`

- 功能：行为断言：enqueue_failure_does_not_mutate_volatile_signal_or_claim_success；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _queued, pickle.dumps, pytest.raises, svc.report_miss, svc.tasks._conn.execute, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L350)。

### `tests/test_durable_tasks.py::test_normal_save_after_task_updates_authoritative_checkpoint`

- 功能：行为断言：normal_save_after_task_updates_authoritative_checkpoint；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.pkl').unlink, AgentWorker, AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once, _close, _fake, _queued, _svc, len, restored.tasks.list_tasks, svc.propose, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L366)。

### `tests/test_durable_tasks.py::test_result_retry_keeps_original_bound_even_if_worker_configuration_changes`

- 功能：行为断言：result_retry_keeps_original_bound_even_if_worker_configuration_changes；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, _fake(), before_for=lambda sig: 999).process_once, AgentWorker(svc, fake).process_once, _close, _fake, _queued, _svc, iter, monkeypatch.setattr, next, restored.engine.mems.values, restored.tasks.list_tasks, svc.log.add_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L382)。

### `tests/test_durable_tasks.py::test_verdict_receipt_prevents_repeated_aggregation_on_ack_retry`

- 功能：行为断言：verdict_receipt_prevents_repeated_aggregation_on_ack_retry；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _ev, _fake, _queued, agent.process_once, len, monkeypatch.setattr, svc.engine.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L400)。

### `tests/test_durable_tasks.py::test_actual_process_exit_recovers_without_duplicate_effect`

- 功能：行为断言：actual_process_exit_recovers_without_duplicate_effect；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, point`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, fake).process_once, Path, Path(__file__).resolve, _close, _fake, _svc, len, out.stderr.decode, pytest.mark.parametrize, restored.tasks.list_tasks, restored.tasks.stats, str, subprocess.run。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L417)。

### `tests/test_durable_tasks.py::test_stop_timeout_does_not_hide_live_thread_or_start_duplicate`

- 功能：行为断言：stop_timeout_does_not_hide_live_thread_or_start_duplicate；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _queued, agent.start, agent.stats, agent.stop, entered.wait, finished.wait, len, release.set, svc.tasks.list_tasks, threading.Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L465)。

### `tests/test_durable_tasks.py::test_stop_timeout_does_not_hide_live_thread_or_start_duplicate.investigate`

- 功能：测试场景/夹具/假实现：test_stop_timeout_does_not_hide_live_thread_or_start_duplicate.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；Investigation(diagnosis={'miss_type': 'no_miss'})`。
- 作用：调用 Investigation, calls.append, entered.set, release.wait。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L472)。

### `tests/test_durable_tasks.py::test_stop_timeout_does_not_hide_live_thread_or_start_duplicate.finish`

- 功能：测试场景/夹具/假实现：test_stop_timeout_does_not_hide_live_thread_or_start_duplicate.finish；输入输出见本项，生产不调用
- 输入：`*args`。
- 输出：`未注解；None`。
- 作用：调用 finished.set, original。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L480)。

### `tests/test_durable_tasks.py::test_task_queue_full_is_explicit_http_backpressure`

- 功能：行为断言：task_queue_full_is_explicit_http_backpressure；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _queued, len, post, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L506)。

### `tests/test_durable_tasks.py::test_pending_task_reserves_referenced_memory_ids_before_any_checkpoint`

- 功能：行为断言：pending_task_reserves_referenced_memory_ids_before_any_checkpoint；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _svc, restored.propose, svc.log.add_unit, svc.propose, svc.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L517)。

### `tests/test_durable_tasks.py::test_result_and_current_memory_checkpoint_are_saved_together`

- 功能：行为断言：result_and_current_memory_checkpoint_are_saved_together；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(restored, _fake()).process_once, AgentWorker(svc, investigate).process_once, _close, _fake, _queued, _svc, len, monkeypatch.setattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L532)。

### `tests/test_durable_tasks.py::test_result_and_current_memory_checkpoint_are_saved_together.store_then_interrupt`

- 功能：测试场景/夹具/假实现：test_result_and_current_memory_checkpoint_are_saved_together.store_then_interrupt；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, original。
- 错误：异常 RuntimeError('stopped after result commit')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L536)。

### `tests/test_durable_tasks.py::test_result_and_current_memory_checkpoint_are_saved_together.investigate`

- 功能：测试场景/夹具/假实现：test_result_and_current_memory_checkpoint_are_saved_together.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；Investigation(diagnosis={'miss_type': 'no_miss'})`。
- 作用：调用 Investigation, svc.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L542)。

### `tests/test_durable_tasks.py::test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain`

- 功能：行为断言：inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(svc, _fake(proposals=[PROPOSAL])).process_once, BlockedGenerator, ThreadPoolExecutor, _fake, _queued, entered.wait, monkeypatch.setattr, observe.result, pool.submit, pytest.raises, release.set, svc.log.count, threading.Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L558)。

### `tests/test_durable_tasks.py::test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain.BlockedGenerator`

- 功能：测试场景/夹具/假实现：test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain.BlockedGenerator；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L568)。

### `tests/test_durable_tasks.py::test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain.BlockedGenerator.generate`

- 功能：测试场景/夹具/假实现：test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain.BlockedGenerator.generate；输入输出见本项，生产不调用
- 输入：`self, *args`。
- 输出：`未注解；CandidateGeneration(candidates=(), scene_name='must not publish')`。
- 作用：调用 CandidateGeneration, entered.set, release.wait。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L569)。

### `tests/test_durable_tasks.py::test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain.commit_then_raise`

- 功能：测试场景/夹具/假实现：test_inflight_observe_cannot_publish_after_checkpoint_becomes_uncertain.commit_then_raise；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, original。
- 错误：异常 RuntimeError('uncertain commit')。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L578)。

### `tests/test_durable_tasks.py::test_oversized_saved_result_is_visible_failure_not_silently_truncated`

- 功能：行为断言：oversized_saved_result_is_visible_failure_not_silently_truncated；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, AgentWorker(svc, fake, max_apply_attempts=1).process_once, _fake, _queued, dict, len, range, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_durable_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_durable_tasks.py#L596)。

## `tests/test_follow_chain.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_follow_chain.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`5c76233d91eca009bd76195dd12d63407285b312debc5d5c4247b6b04368edea`。

### `tests/test_follow_chain.py::_engine`

- 功能：测试场景/夹具/假实现：_engine；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`未注解；MemoryEngine(Cfg(), emb, world)`。
- 作用：调用 Cfg, FakeWorld, MemoryEngine, SyntheticEmbedder。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L15)。

### `tests/test_follow_chain.py::_mem`

- 功能：测试场景/夹具/假实现：_mem；输入输出见本项，生产不调用
- 输入：`i, **kw`。
- 输出：`未注解；Memory(id=i, belief_id=0, value='v', text=f'm{i}', emb=np.array([1.0, 0.0]), **kw)`。
- 作用：调用 Memory, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L21)。

### `tests/test_follow_chain.py::test_chain_to_memory_id_zero_is_followed`

- 功能：行为断言：chain_to_memory_id_zero_is_followed；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine, _mem, maintenance.follow_chain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L26)。

### `tests/test_follow_chain.py::test_aggregated_into_zero_is_followed`

- 功能：行为断言：aggregated_into_zero_is_followed；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine, _mem, maintenance.follow_chain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L35)。

### `tests/test_follow_chain.py::test_multi_hop_chain_mixed_pointers`

- 功能：行为断言：multi_hop_chain_mixed_pointers；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine, _mem, maintenance.follow_chain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L42)。

### `tests/test_follow_chain.py::test_cycle_is_broken_not_infinite`

- 功能：行为断言：cycle_is_broken_not_infinite；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine, _mem, maintenance.follow_chain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L49)。

### `tests/test_follow_chain.py::test_dangling_pointer_is_broken_not_keyerror`

- 功能：行为断言：dangling_pointer_is_broken_not_keyerror；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine, _mem, maintenance.follow_chain。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L57)。

### `tests/test_follow_chain.py::test_step_with_tension_on_zero_chain_does_not_crash`

- 功能：行为断言：step_with_tension_on_zero_chain_does_not_crash；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine, _mem, eng.add_tension, eng.drain_signals, eng.step。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L64)。

### `tests/test_follow_chain.py::test_update_and_conflict_chains_survive_long_run`

- 功能：行为断言：update_and_conflict_chains_survive_long_run；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`seed`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, FakeWorld, MemoryEngine, SignalWorker, SyntheticEmbedder, any, b.alive, emb.embed, eng.mems.values, eng.observe, eng.retrieve, eng.step, len, pytest.mark.parametrize, range, worker.process, world.beliefs.values, world.embedding_key, world.event, world.query, world.set_value, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_follow_chain.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_follow_chain.py#L77)。

## `tests/test_investigation_scope.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_investigation_scope.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`344069d1f8e123637cd326d2651c16a7db998fa1a1e43a6805ea2717f56dddc5`。

### `tests/test_investigation_scope.py::_seed`

- 功能：测试场景/夹具/假实现：_seed；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；None`。
- 作用：调用 Memory, Tension, frozenset, np.array, svc.log.add_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L17)。

### `tests/test_investigation_scope.py::_open`

- 功能：测试场景/夹具/假实现：_open；输入输出见本项，生产不调用
- 输入：`svc, calls=20, chars=10`。
- 输出：`未注解；svc.open_budget('s', tool_calls=calls, window_chars=chars, before=1, origin='repair')`。
- 作用：调用 svc.open_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L36)。

### `tests/test_investigation_scope.py::test_all_investigation_http_tools_share_admission`

- 功能：行为断言：all_investigation_http_tools_share_admission；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`state, expected`。
- 输出：`未注解；None`。
- 作用：调用 _http, _open, _seed, _service, get, pickle.dumps, post, pytest.mark.parametrize, svc.close_budget, svc.log.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L43)。

### `tests/test_investigation_scope.py::test_search_filters_before_top_k_and_never_leaks_contested_future`

- 功能：行为断言：search_filters_before_top_k_and_never_leaks_contested_future；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _open, _seed, _service, len, np.array, pickle.dumps, svc.close_budget, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L74)。

### `tests/test_investigation_scope.py::test_conflicts_resolve_and_supersedes_obey_same_bound`

- 功能：行为断言：conflicts_resolve_and_supersedes_obey_same_bound；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`target`。
- 输出：`未注解；None`。
- 作用：调用 _http, _open, _seed, _service, get, len, pickle.dumps, post, pytest.mark.parametrize, svc.close_budget, svc.log.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L94)。

### `tests/test_investigation_scope.py::test_stats_keeps_one_bound_even_if_closed_mid_read`

- 功能：行为断言：stats_keeps_one_bound_even_if_closed_mid_read；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 _open, _seed, _service, monkeypatch.setattr, pytest.raises, sum, svc.log_search, svc.log_stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L120)。

### `tests/test_investigation_scope.py::test_stats_keeps_one_bound_even_if_closed_mid_read.close_then_read`

- 功能：测试场景/夹具/假实现：test_stats_keeps_one_bound_even_if_closed_mid_read.close_then_read；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；original(*args, **kwargs)`。
- 作用：调用 original, svc.close_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L126)。

### `tests/test_investigation_scope.py::test_window_reserves_before_unlocked_io`

- 功能：行为断言：window_reserves_before_unlocked_io；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 ThreadPoolExecutor, _open, _seed, _service, entered.wait, first.result, monkeypatch.setattr, pool.submit, pytest.raises, release.set, second.result, svc.close_budget, threading.Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L138)。

### `tests/test_investigation_scope.py::test_window_reserves_before_unlocked_io.blocked`

- 功能：测试场景/夹具/假实现：test_window_reserves_before_unlocked_io.blocked；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；original(*args, **kwargs)`。
- 作用：调用 entered.set, original, release.wait。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L145)。

### `tests/test_investigation_scope.py::test_window_refunds_unused_reservation_and_failure`

- 功能：行为断言：window_refunds_unused_reservation_and_failure；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 _open, _seed, _service, monkeypatch.setattr, pytest.raises, svc.log_window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L164)。

### `tests/test_investigation_scope.py::test_window_refunds_unused_reservation_and_failure.boom`

- 功能：测试场景/夹具/假实现：test_window_refunds_unused_reservation_and_failure.boom；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('read failed')。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L171)。

### `tests/test_investigation_scope.py::test_worker_final_json_after_budget_exhaustion_keeps_causality_and_origin`

- 功能：行为断言：worker_final_json_after_budget_exhaustion_keeps_causality_and_origin；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, Budget, _seed, _service, agent.process_once, svc.report_miss, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L182)。

### `tests/test_investigation_scope.py::test_worker_final_json_after_budget_exhaustion_keeps_causality_and_origin.investigate`

- 功能：测试场景/夹具/假实现：test_worker_final_json_after_budget_exhaustion_keeps_causality_and_origin.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；Investigation(proposals=[{'text': '从历史证据修复 handler.ts', 'source_unit_ids': [0]}, {'text': '不该接受的 future 证据', 'source_unit_ids': [1]}], verdicts=[(0, 1, 'update')], diagnosis={'miss_type': 'too_coarse'})`。
- 作用：调用 Investigation, pytest.raises, svc.log_search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L188)。

### `tests/test_investigation_scope.py::test_worker_retry_uses_fresh_signal_handle`

- 功能：行为断言：worker_retry_uses_fresh_signal_handle；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _service, agent.process_once, len, svc.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L206)。

### `tests/test_investigation_scope.py::test_worker_retry_uses_fresh_signal_handle.investigate`

- 功能：测试场景/夹具/假实现：test_worker_retry_uses_fresh_signal_handle.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；None`。
- 作用：调用 checked.append, handles.append, len, pytest.raises, svc.log_stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L211)。

### `tests/test_investigation_scope.py::test_resolve_cannot_follow_an_old_id_to_future_representative`

- 功能：行为断言：resolve_cannot_follow_an_old_id_to_future_representative；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`pointer`。
- 输出：`未注解；None`。
- 作用：调用 _http, _open, _seed, _service, pickle.dumps, post, pytest.mark.parametrize, setattr, svc.log.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L230)。

### `tests/test_investigation_scope.py::test_blank_signal_header_is_not_a_main_agent_request`

- 功能：行为断言：blank_signal_header_is_not_a_main_agent_request；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, post, svc.log.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L246)。

### `tests/test_investigation_scope.py::test_inflight_window_retains_bound_and_never_charges_reopened_budget`

- 功能：行为断言：inflight_window_retains_bound_and_never_charges_reopened_budget；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 ThreadPoolExecutor, _open, _seed, _service, entered.wait, monkeypatch.setattr, pending.result, pool.submit, release.set, svc.close_budget, svc.open_budget, threading.Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L255)。

### `tests/test_investigation_scope.py::test_inflight_window_retains_bound_and_never_charges_reopened_budget.blocked`

- 功能：测试场景/夹具/假实现：test_inflight_window_retains_bound_and_never_charges_reopened_budget.blocked；输入输出见本项，生产不调用
- 输入：`*args, **kwargs`。
- 输出：`未注解；original(*args, **kwargs)`。
- 作用：调用 entered.set, original, release.wait。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L262)。

### `tests/test_investigation_scope.py::test_concurrent_calls_share_one_call_allowance`

- 功能：行为断言：concurrent_calls_share_one_call_allowance；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ThreadPoolExecutor, _open, _seed, _service, pool.map, range, sum, svc.close_budget, threading.Barrier。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L285)。

### `tests/test_investigation_scope.py::test_concurrent_calls_share_one_call_allowance.request`

- 功能：测试场景/夹具/假实现：test_concurrent_calls_share_one_call_allowance.request；输入输出见本项，生产不调用
- 输入：`_`。
- 输出：`未注解；False；True`。
- 作用：调用 barrier.wait, svc.log_search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L291)。

### `tests/test_investigation_scope.py::test_signal_requests_cannot_use_main_only_endpoints_or_forge_context`

- 功能：行为断言：signal_requests_cannot_use_main_only_endpoints_or_forge_context；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _open, _service, get, post, svc.close_budget, svc.log.close, svc.log.count。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L304)。

### `tests/test_investigation_scope.py::test_all_tools_draw_from_the_same_call_budget`

- 功能：行为断言：all_tools_draw_from_the_same_call_budget；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _open, _seed, _service, get, post, svc.close_budget, svc.log.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L324)。

### `tests/test_investigation_scope.py::test_request_bound_can_only_tighten_context`

- 功能：行为断言：request_bound_can_only_tighten_context；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`before, expected`。
- 输出：`未注解；None`。
- 作用：调用 _open, _seed, _service, pytest.mark.parametrize, svc.log_search, svc.log_stats, svc.log_timeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L344)。

### `tests/test_investigation_scope.py::test_denied_search_never_calls_embedding`

- 功能：行为断言：denied_search_never_calls_embedding；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 _open, _service, monkeypatch.setattr, pytest.raises, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L353)。

### `tests/test_investigation_scope.py::test_context_is_immutable_and_active_budget_cannot_be_reset`

- 功能：行为断言：context_is_immutable_and_active_budget_cannot_be_reset；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _open, _service, pytest.raises, svc.close_budget, svc.log_stats。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L365)。

### `tests/test_investigation_scope.py::test_investigator_search_does_not_revive_or_credit_even_with_eager_config`

- 功能：行为断言：investigator_search_does_not_revive_or_credit_even_with_eager_config；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _open, _seed, _service, len, pickle.dumps, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L378)。

### `tests/test_investigation_scope.py::test_active_http_search_and_recall_are_bounded_but_main_search_is_unchanged`

- 功能：行为断言：active_http_search_and_recall_are_bounded_but_main_search_is_unchanged；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _open, _seed, _service, get, isinstance, post, quote, svc.close_budget, svc.log.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L401)。

### `tests/test_investigation_scope.py::test_invalid_budget_or_window_size_cannot_manufacture_allowance`

- 功能：行为断言：invalid_budget_or_window_size_cannot_manufacture_allowance；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _open, _service, args.update, dict, pytest.raises, svc.close_budget, svc.log_window, svc.open_budget, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L422)。

### `tests/test_investigation_scope.py::test_inline_memory_tools_use_causal_readonly_admission`

- 功能：行为断言：inline_memory_tools_use_causal_readonly_admission；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`name, args`。
- 输出：`未注解；None`。
- 作用：调用 InlineInvestigator, _open, _seed, _service, inv._tool, pickle.dumps, pytest.mark.parametrize, pytest.raises, svc._state, svc.close_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_investigation_scope.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_investigation_scope.py#L441)。

## `tests/test_launch_closeout.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_launch_closeout.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`35a004c3ddbd827c7c4ea22abc8906c526335bba4ff1761e60739670b9eb837f`。

### `tests/test_launch_closeout.py::_close`

- 功能：测试场景/夹具/假实现：_close；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；None`。
- 作用：调用 svc.log.close, svc.stop_unit_recovery, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L7)。

### `tests/test_launch_closeout.py::test_health_does_not_claim_remote_validation_and_retry_is_read_only`

- 功能：行为断言：health_does_not_claim_remote_validation_and_retry_is_read_only；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _http, _service, get, svc.health_view, svc.log.count, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L13)。

### `tests/test_launch_closeout.py::test_pending_unit_is_visible_and_not_reported_done`

- 功能：行为断言：pending_unit_is_visible_and_not_reported_done；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _http, _service, get, svc.log.append_unit, svc.log.work。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L33)。

### `tests/test_launch_closeout.py::test_quarantine_survives_restart_and_save_does_not_launder_it`

- 功能：行为断言：quarantine_survives_restart_and_save_does_not_launder_it；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.corrupt').exists, (tmp_path / 'state.pkl').unlink, (tmp_path / 'state.pkl').write_bytes, _close, _http, _service, again.health_view, get, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L47)。

### `tests/test_launch_closeout.py::test_checkpoint_fault_does_not_become_a_validation_claim`

- 功能：行为断言：checkpoint_fault_does_not_become_a_validation_claim；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, svc.health_view。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L78)。

### `tests/test_launch_closeout.py::test_leftover_corrupt_file_does_not_override_a_successful_load`

- 功能：行为断言：leftover_corrupt_file_does_not_override_a_successful_load；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.corrupt').write_bytes, _close, _service, again.health_view, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L90)。

### `tests/test_launch_closeout.py::test_readme_does_not_advertise_a_stale_pass_count_or_remote_validation`

- 功能：行为断言：readme_does_not_advertise_a_stale_pass_count_or_remote_validation；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path('README.md').read_text。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_launch_closeout.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_launch_closeout.py#L106)。

## `tests/test_logstore.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_logstore.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`9543b72fd4bfcbaf4b6e19d488da99132e331aa0d59c8e46a86c5165f6a4f424`。

### `tests/test_logstore.py::_fill`

- 功能：测试场景/夹具/假实现：_fill；输入输出见本项，生产不调用
- 输入：`store, scene='接入'`。
- 输出：`未注解；None`。
- 作用：调用 store.add_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L10)。

### `tests/test_logstore.py::test_entities_in_picks_hard_identifiers_only`

- 功能：行为断言：entities_in_picks_hard_identifiers_only；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 dict, entities_in, ents.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L23)。

### `tests/test_logstore.py::test_add_unit_reports_new_entities_once`

- 功能：行为断言：add_unit_reports_new_entities_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, s.add_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L34)。

### `tests/test_logstore.py::test_search_lexical_returns_snippets_not_full_text`

- 功能：行为断言：search_lexical_returns_snippets_not_full_text；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.search, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L44)。

### `tests/test_logstore.py::test_search_cjk_query_works_with_trigram`

- 功能：行为断言：search_cjk_query_works_with_trigram；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L54)。

### `tests/test_logstore.py::test_search_before_is_strict_and_scene_filters`

- 功能：行为断言：search_before_is_strict_and_scene_filters；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L60)。

### `tests/test_logstore.py::test_search_vector_path_fuses_with_lexical`

- 功能：行为断言：search_vector_path_fuses_with_lexical；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Emb, LogStore, _fill, s.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L69)。

### `tests/test_logstore.py::test_search_vector_path_fuses_with_lexical.Emb`

- 功能：测试场景/夹具/假实现：test_search_vector_path_fuses_with_lexical.Emb；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L70)。

### `tests/test_logstore.py::test_search_vector_path_fuses_with_lexical.Emb.embed`

- 功能：测试场景/夹具/假实现：test_search_vector_path_fuses_with_lexical.Emb.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array([[1.0, 0.0] if 'form agent' in t else [0.0, 1.0] for t in texts], dtype=np.float32)`。
- 作用：调用 np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L71)。

### `tests/test_logstore.py::test_embedder_failure_does_not_block_write`

- 功能：行为断言：embedder_failure_does_not_block_write；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Boom, LogStore, s.add_unit, s.count, s.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L81)。

### `tests/test_logstore.py::test_embedder_failure_does_not_block_write.Boom`

- 功能：测试场景/夹具/假实现：test_embedder_failure_does_not_block_write.Boom；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L82)。

### `tests/test_logstore.py::test_embedder_failure_does_not_block_write.Boom.embed`

- 功能：测试场景/夹具/假实现：test_embedder_failure_does_not_block_write.Boom.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('no network')。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L83)。

### `tests/test_logstore.py::test_timeline_and_mention_counts_respect_before`

- 功能：行为断言：timeline_and_mention_counts_respect_before；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.mention_counts, s.timeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L92)。

### `tests/test_logstore.py::test_stats_group_by_scene_entity_week`

- 功能：行为断言：stats_group_by_scene_entity_week；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, all, len, pytest.raises, s.stats, sum。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L104)。

### `tests/test_logstore.py::test_window_truncates_by_budget_and_reports_missing_omitted`

- 功能：行为断言：window_truncates_by_budget_and_reports_missing_omitted；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, len, s.add_unit, s.window。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L122)。

### `tests/test_logstore.py::test_exists_and_count_with_before`

- 功能：行为断言：exists_and_count_with_before；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.count, s.exists。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L137)。

### `tests/test_logstore.py::test_persists_to_sqlite_file_and_reopens`

- 功能：行为断言：persists_to_sqlite_file_and_reopens；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.close, s2.count, s2.get, s2.get(1)['assistant_text'].startswith, s2.timeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L146)。

### `tests/test_logstore.py::test_duplicate_id_with_different_evidence_is_rejected`

- 功能：行为断言：duplicate_id_with_different_evidence_is_rejected；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`change`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, dict, pytest.mark.parametrize, pytest.raises, s._conn.execute, s.add_unit, s.close, s.count, s.get, s.search, s.timeline, s.timeline('old_module.py')[0]['snippet'].startswith。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L162)。

### `tests/test_logstore.py::test_exact_reimport_preserves_timestamp_indexes_and_embedding`

- 功能：行为断言：exact_reimport_preserves_timestamp_indexes_and_embedding；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Emb, LogStore, dict, s._conn.execute, s.add_unit, s.close, s.get, s.mention_counts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L179)。

### `tests/test_logstore.py::test_exact_reimport_preserves_timestamp_indexes_and_embedding.Emb`

- 功能：测试场景/夹具/假实现：test_exact_reimport_preserves_timestamp_indexes_and_embedding.Emb；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L180)。

### `tests/test_logstore.py::test_exact_reimport_preserves_timestamp_indexes_and_embedding.Emb.embed`

- 功能：测试场景/夹具/假实现：test_exact_reimport_preserves_timestamp_indexes_and_embedding.Emb.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array([[1.0, 0.0]], dtype=np.float32)`。
- 作用：调用 np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L183)。

### `tests/test_logstore.py::test_append_allocates_above_database_and_snapshot_floors`

- 功能：行为断言：append_allocates_above_database_and_snapshot_floors；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, s.add_unit, s.append_unit, s.close, s.get, s.next_position。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L203)。

### `tests/test_logstore.py::test_parallel_connections_allocate_distinct_ids_and_times`

- 功能：行为断言：parallel_connections_allocate_distinct_ids_and_times；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, ThreadPoolExecutor, len, list, pool.map, range, s.close, sorted, stores[0].count, stores[0].get, threading.Barrier。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L219)。

### `tests/test_logstore.py::test_parallel_connections_allocate_distinct_ids_and_times.write`

- 功能：测试场景/夹具/假实现：test_parallel_connections_allocate_distinct_ids_and_times.write；输入输出见本项，生产不调用
- 输入：`i`。
- 输出：`未注解；[stores[i].append_unit(0, user_text=f'writer-{i}-{j}', assistant_text='answer') for j in range(5)]`。
- 作用：调用 barrier.wait, range, stores[i].append_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L226)。

### `tests/test_logstore.py::test_failed_index_write_rolls_back_unit_and_allocation`

- 功能：行为断言：failed_index_write_rolls_back_unit_and_allocation；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, pytest.raises, s._conn.execute, s.append_unit, s.close, s.count, s.search。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L243)。

### `tests/test_logstore.py::test_retention_report_units_bytes_oldest_and_dangling`

- 功能：行为断言：retention_report_units_bytes_oldest_and_dangling；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _fill, s.close, s.retention_report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_logstore.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_logstore.py#L261)。

## `tests/test_ouroboros.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_ouroboros.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`f08c11c95b3458b8e532d9d3273136b31c772678ac3bdc28a294ee5d6f7db752`。

### `tests/test_ouroboros.py::_HashEmbedder`

- 功能：字符哈希词袋：确定、无网络，相近文本余弦相近。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L25)。

### `tests/test_ouroboros.py::_HashEmbedder.embed`

- 功能：测试场景/夹具/假实现：_HashEmbedder.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array(out, dtype=np.float32)`。
- 作用：调用 hash, np.array, np.linalg.norm, np.zeros, out.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L27)。

### `tests/test_ouroboros.py::_NoCandGen`

- 功能：被动抽取什么都不抽——模拟漏记，让修复回路有事可做。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L37)。

### `tests/test_ouroboros.py::_NoCandGen.generate`

- 功能：测试场景/夹具/假实现：_NoCandGen.generate；输入输出见本项，生产不调用
- 输入：`self, window, prev_scene=''`。
- 输出：`未注解；CandidateGeneration(candidates=(), scene_name='接入')`。
- 作用：调用 CandidateGeneration。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L39)。

### `tests/test_ouroboros.py::_BoomCandGen`

- 功能：测试场景/夹具/假实现：_BoomCandGen；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L43)。

### `tests/test_ouroboros.py::_BoomCandGen.generate`

- 功能：测试场景/夹具/假实现：_BoomCandGen.generate；输入输出见本项，生产不调用
- 输入：`self, window, prev_scene=''`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('LLM down')。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L44)。

### `tests/test_ouroboros.py::_svc`

- 功能：测试场景/夹具/假实现：_svc；输入输出见本项，生产不调用
- 输入：`tmp_path=None, generator=None, **cfg`。
- 输出：`未注解；MemoryService(Cfg(**base), _HashEmbedder(), RealChatSemantics(None), generator or _NoCandGen(), state_dir=tmp_path)`。
- 作用：调用 Cfg, MemoryService, RealChatSemantics, _HashEmbedder, _NoCandGen, base.update, dict。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L48)。

### `tests/test_ouroboros.py::_ev`

- 功能：测试场景/夹具/假实现：_ev；输入输出见本项，生产不调用
- 输入：`text, t=0, origin='repair', src=(0,)`。
- 输出：`未注解；Event(text, text, text, tuple(src), origin=origin)`。
- 作用：调用 Event, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L56)。

### `tests/test_ouroboros.py::test_build_payload_shapes`

- 功能：行为断言：build_payload_shapes；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Budget, SignalQueue, build_payload, len, q.emit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L61)。

### `tests/test_ouroboros.py::test_parse_investigation_tolerates_noise_and_validates_items`

- 功能：行为断言：parse_investigation_tolerates_noise_and_validates_items；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 len, parse_investigation。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L77)。

### `tests/test_ouroboros.py::test_parse_investigation_rejects_garbage`

- 功能：行为断言：parse_investigation_rejects_garbage；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 parse_investigation。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L93)。

### `tests/test_ouroboros.py::_fake`

- 功能：测试场景/夹具/假实现：_fake；输入输出见本项，生产不调用
- 输入：`proposals=(), diagnosis=None, verdicts=()`。
- 输出：`未注解；investigate`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L102)。

### `tests/test_ouroboros.py::_fake.investigate`

- 功能：测试场景/夹具/假实现：_fake.investigate；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；Investigation(proposals=list(proposals), verdicts=list(verdicts), diagnosis=diagnosis)`。
- 作用：调用 Investigation, calls.append, list。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L105)。

### `tests/test_ouroboros.py::test_correction_triggers_repair_and_recall_improves`

- 功能：行为断言：correction_triggers_repair_and_recall_improves；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.process_once, len, list, miss_payload['q'].startswith, svc.attach_agent, svc.engine.mems.values, svc.observe, svc.recall, svc.signals, svc.signals()['queued'].get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L113)。

### `tests/test_ouroboros.py::test_extract_due_uses_extract_origin_and_causal_bound`

- 功能：行为断言：extract_due_uses_extract_origin_and_causal_bound；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.process_once, iter, next, svc.engine.mems.values, svc.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L143)。

### `tests/test_ouroboros.py::test_investigator_failure_requeues_then_gives_up`

- 功能：行为断言：investigator_failure_requeues_then_gives_up；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`capsys`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _svc, agent.process_once, capsys.readouterr, len, svc.report_miss, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L161)。

### `tests/test_ouroboros.py::test_investigator_failure_requeues_then_gives_up.flaky`

- 功能：测试场景/夹具/假实现：test_investigator_failure_requeues_then_gives_up.flaky；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；None`。
- 作用：调用 calls.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L166)。

### `tests/test_ouroboros.py::test_investigator_exception_is_contained`

- 功能：行为断言：investigator_exception_is_contained；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _svc, agent.process_once, svc.report_miss, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L179)。

### `tests/test_ouroboros.py::test_investigator_exception_is_contained.boom`

- 功能：测试场景/夹具/假实现：test_investigator_exception_is_contained.boom；输入输出见本项，生产不调用
- 输入：`payload`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('opencode exploded')。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L183)。

### `tests/test_ouroboros.py::test_daily_cap_pauses_and_keeps_signals`

- 功能：行为断言：daily_cap_pauses_and_keeps_signals；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.process_once, agent.stats, datetime.date.today, datetime.timedelta, monkeypatch.setattr, svc.report_miss, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L191)。

### `tests/test_ouroboros.py::test_daily_cap_pauses_and_keeps_signals.NextDay`

- 功能：测试场景/夹具/假实现：test_daily_cap_pauses_and_keeps_signals.NextDay；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 datetime.date`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L206)。

### `tests/test_ouroboros.py::test_daily_cap_pauses_and_keeps_signals.NextDay.today`

- 功能：测试场景/夹具/假实现：test_daily_cap_pauses_and_keeps_signals.NextDay.today；输入输出见本项，生产不调用
- 输入：`cls`。
- 输出：`未注解；tomorrow`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L208)。

### `tests/test_ouroboros.py::test_recent_dedupe_skips_same_question`

- 功能：行为断言：recent_dedupe_skips_same_question；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.process_once, len, svc.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L218)。

### `tests/test_ouroboros.py::test_max_signals_defers_rest`

- 功能：行为断言：max_signals_defers_rest；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.process_once, svc.report_miss, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L229)。

### `tests/test_ouroboros.py::test_verdicts_from_investigator_are_applied`

- 功能：行为断言：verdicts_from_investigator_are_applied；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _ev, _fake, _svc, agent.process_once, svc.engine.propose, svc.log.add_unit, svc.report_miss。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L239)。

### `tests/test_ouroboros.py::test_candgen_failure_keeps_unit_and_flags_extract_due`

- 功能：行为断言：candgen_failure_keeps_unit_and_flags_extract_due；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _BoomCandGen, _svc, svc.log.count, svc.observe, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L253)。

### `tests/test_ouroboros.py::test_agent_worker_thread_start_stop`

- 功能：行为断言：agent_worker_thread_start_stop；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, _fake, _svc, agent.start, agent.stats, agent.stop, range, svc.attach_agent, svc.report_miss, time.sleep。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L261)。

### `tests/test_ouroboros.py::test_repair_memories_survive_restart`

- 功能：行为断言：repair_memories_survive_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'diagnoses.jsonl').read_text, (tmp_path / 'diagnoses.jsonl').read_text(encoding='utf-8').splitlines, _svc, iter, json.loads, next, svc.diagnose, svc.observe, svc.propose, svc.save, svc2.engine.mems.values, svc2.log.count。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L281)。

### `tests/test_ouroboros.py::test_investigation_malformed_collections_and_ids_do_not_crash_or_retarget`

- 功能：行为断言：investigation_malformed_collections_and_ids_do_not_crash_or_retarget；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 float, json.dumps, parse_investigation。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L302)。

### `tests/test_ouroboros.py::test_inline_investigator_tool_loop_end_to_end`

- 功能：recall_miss → AgentWorker → 进程内 function-calling 循环： log_search 真的打到服务层（按 signal_id 记账）→ 最终 JSON → propose 入库。 调查过程不产生任何 observe（火墙天然成立）。
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 AgentWorker, Budget, InlineInvestigator, _svc, len, svc.engine.mems.values, svc.log.add_unit, svc.log.count, svc.report_miss, svc.tasks.list_tasks, w.process_once。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L314)。

### `tests/test_ouroboros.py::test_inline_investigator_tool_loop_end_to_end.fake_chat`

- 功能：测试场景/夹具/假实现：test_inline_investigator_tool_loop_end_to_end.fake_chat；输入输出见本项，生产不调用
- 输入：`messages, tools`。
- 输出：`未注解；_tool_msg('log_search', {'query': '端口'})；{'role': 'assistant', 'content': json.dumps({'proposals': [{'text': '服务端口已从 8080 改为 9090。', 'source_unit_ids': [0], 'entity_key': 'port'}], 'diagnosis': {'miss_type': 'dropped_by_candgen', 'note': '漏抽'}}, ensure_ascii=False)}`。
- 作用：调用 _tool_msg, json.dumps, len, seen.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L324)。

### `tests/test_ouroboros.py::test_inline_investigator_budget_and_turn_cap`

- 功能：工具预算用尽 → PermissionError 作为工具结果回给模型； 模型一直要工具 → 轮数上限后最后一轮不给工具、再不收尾就判失败。
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 InlineInvestigator, _svc, inv, inv2, len, svc.close_budget, svc.observe, svc.open_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L354)。

### `tests/test_ouroboros.py::test_inline_investigator_budget_and_turn_cap.greedy`

- 功能：测试场景/夹具/假实现：test_inline_investigator_budget_and_turn_cap.greedy；输入输出见本项，生产不调用
- 输入：`messages, tools`。
- 输出：`未注解；_tool_msg('log_search', {'query': 'a'}, cid=str(len(calls)))`。
- 作用：调用 _tool_msg, calls.append, len, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L364)。

### `tests/test_ouroboros.py::test_inline_investigator_budget_and_turn_cap.bad_json`

- 功能：测试场景/夹具/假实现：test_inline_investigator_budget_and_turn_cap.bad_json；输入输出见本项，生产不调用
- 输入：`messages, tools`。
- 输出：`未注解；{'role': 'assistant', 'content': '不是 JSON'}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L374)。

### `tests/test_ouroboros.py::test_inline_investigator_llm_error_and_model_compat`

- 功能：行为断言：inline_investigator_llm_error_and_model_compat；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 InlineInvestigator, _svc, inv。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L381)。

### `tests/test_ouroboros.py::test_inline_investigator_llm_error_and_model_compat.down`

- 功能：测试场景/夹具/假实现：test_inline_investigator_llm_error_and_model_compat.down；输入输出见本项，生产不调用
- 输入：`messages, tools`。
- 输出：`未注解；None`。
- 作用：调用 ZhipuChatError。
- 错误：异常 ZhipuChatError('HTTP 401')。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L385)。

### `tests/test_ouroboros.py::_tool_msg`

- 功能：测试场景/夹具/假实现：_tool_msg；输入输出见本项，生产不调用
- 输入：`name, args, cid='c1'`。
- 输出：`未注解；{'role': 'assistant', 'content': '', 'tool_calls': [{'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}]}`。
- 作用：调用 json.dumps。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_ouroboros.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_ouroboros.py#L393)。

## `tests/test_semantic_recovery.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_semantic_recovery.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`4068e453db6cb41f834d0ba63fee562e2029218be5d2db00b965c82d81b8104c`。

### `tests/test_semantic_recovery.py::_close`

- 功能：测试场景/夹具/假实现：_close；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；None`。
- 作用：调用 svc.log.close, svc.stop_unit_recovery, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L15)。

### `tests/test_semantic_recovery.py::_prepared`

- 功能：测试场景/夹具/假实现：_prepared；输入输出见本项，生产不调用
- 输入：`tmp_path`。
- 输出：`未注解；(svc, rid)`。
- 作用：调用 _service, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L21)。

### `tests/test_semantic_recovery.py::test_feedback_is_durable_before_worker_and_recovers_once`

- 功能：行为断言：feedback_is_durable_before_worker_and_recovers_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _http, _prepared, _service, get, get('/signals')[1]['queued'].get, post, restored.process_semantic_tasks, restored.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L28)。

### `tests/test_semantic_recovery.py::test_feedback_capacity_failure_restores_sent_flag`

- 功能：行为断言：feedback_capacity_failure_restores_sent_flag；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, pytest.raises, svc.feedback, svc.report_miss, svc.tasks._conn.execute, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L55)。

### `tests/test_semantic_recovery.py::test_semantic_receipt_sql_failure_rolls_back_in_place_then_retries`

- 功能：行为断言：semantic_receipt_sql_failure_rolls_back_in_place_then_retries；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, svc.feedback, svc.tasks._conn.execute, svc.tasks.list_tasks, type, type(svc).process_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L71)。

### `tests/test_semantic_recovery.py::test_expired_semantic_lease_fences_old_token`

- 功能：行为断言：expired_semantic_lease_fences_old_token；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, pytest.raises, svc.feedback, svc.tasks._conn.execute, svc.tasks.claim, svc.tasks.list_tasks, svc.tasks.recover_expired, svc.tasks.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L93)。

### `tests/test_semantic_recovery.py::test_saved_model_result_is_not_invoked_again_after_restart`

- 功能：行为断言：saved_model_result_is_not_invoked_again_after_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, _service, restored.process_semantic_tasks, svc.feedback, svc.tasks.claim, svc.tasks.list_tasks, svc.tasks.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L114)。

### `tests/test_semantic_recovery.py::test_crashes_before_effect_and_after_atomic_commit`

- 功能：行为断言：crashes_before_effect_and_after_atomic_commit；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(__file__).resolve, _close, _prepared, _service, restored.process_semantic_tasks, restored.tasks._conn.execute, restored.tasks.list_tasks, str, subprocess.run, svc.feedback。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L134)。

### `tests/test_semantic_recovery.py::_Judge`

- 功能：测试场景/夹具/假实现：_Judge；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L176)。

### `tests/test_semantic_recovery.py::_Judge.__init__`

- 功能：测试场景/夹具/假实现：_Judge.__init__；输入输出见本项，生产不调用
- 输入：`self, inner`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L177)。

### `tests/test_semantic_recovery.py::_Judge.__getattr__`

- 功能：测试场景/夹具/假实现：_Judge.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self.inner, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L181)。

### `tests/test_semantic_recovery.py::_Judge.judge`

- 功能：测试场景/夹具/假实现：_Judge.judge；输入输出见本项，生产不调用
- 输入：`self, *args`。
- 输出：`未注解；'update'`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L184)。

### `tests/test_semantic_recovery.py::_Judge.consolidate`

- 功能：测试场景/夹具/假实现：_Judge.consolidate；输入输出见本项，生产不调用
- 输入：`self, mems, t`。
- 输出：`未注解；Event(123, 'reflection', '新反思', src=(0,), scene='测试场景')`。
- 作用：调用 Event。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L188)。

### `tests/test_semantic_recovery.py::test_conflict_and_consolidation_durable_across_restart`

- 功能：行为断言：conflict_and_consolidation_durable_across_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Memory, _Judge, _close, _service, old.emb.copy, restored.process_semantic_tasks, svc._commit_sidecar_effect, svc.engine._consolidation_pending.add, svc.engine.add_tension, svc.observe, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L193)。

### `tests/test_semantic_recovery.py::test_process_crash_after_claim_before_model_recovers_without_losing_job`

- 功能：行为断言：process_crash_after_claim_before_model_recovers_without_losing_job；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(__file__).resolve, _close, _prepared, _service, restored.process_semantic_tasks, restored.tasks._conn.execute, restored.tasks.list_tasks, str, subprocess.run, svc.feedback。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L226)。

### `tests/test_semantic_recovery.py::test_consolidation_none_is_valid_completion`

- 功能：行为断言：consolidation_none_is_valid_completion；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 NoReflection, _close, _service, svc._commit_sidecar_effect, svc.engine._consolidation_pending.add, svc.observe, svc.process_semantic_tasks, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L257)。

### `tests/test_semantic_recovery.py::test_consolidation_none_is_valid_completion.NoReflection`

- 功能：测试场景/夹具/假实现：test_consolidation_none_is_valid_completion.NoReflection；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 _Judge`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L266)。

### `tests/test_semantic_recovery.py::test_consolidation_none_is_valid_completion.NoReflection.consolidate`

- 功能：测试场景/夹具/假实现：test_consolidation_none_is_valid_completion.NoReflection.consolidate；输入输出见本项，生产不调用
- 输入：`self, mems, t`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L267)。

### `tests/test_semantic_recovery.py::test_concurrent_feedback_accepts_one_durable_job`

- 功能：行为断言：concurrent_feedback_accepts_one_durable_job；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 ThreadPoolExecutor, _close, _prepared, len, list, pool.map, range, sum, svc.tasks.list_tasks, type, type(svc).process_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L280)。

### `tests/test_semantic_recovery.py::test_l0_effect_hands_off_semantic_work_in_same_task_transaction`

- 功能：行为断言：l0_effect_hands_off_semantic_work_in_same_task_transaction；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _Judge, _close, _service, len, restored.engine.mems.values, restored.process_semantic_tasks, svc.engine.signals.peek_kinds, svc.engine.signals.peek_kinds().get, svc.log.get, svc.log.work, svc.observe, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L295)。

### `tests/test_semantic_recovery.py::test_semantic_status_shows_retry_and_recent_error`

- 功能：行为断言：semantic_status_shows_retry_and_recent_error；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _http, _prepared, get, svc.feedback, type, type(svc).process_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L321)。

### `tests/test_semantic_recovery.py::test_semantic_status_shows_retry_and_recent_error.unavailable`

- 功能：测试场景/夹具/假实现：test_semantic_status_shows_retry_and_recent_error.unavailable；输入输出见本项，生产不调用
- 输入：`row`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError。
- 错误：异常 RuntimeError('model unavailable')。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L326)。

### `tests/test_semantic_recovery.py::test_stale_verdict_requeues_current_tension_with_capacity_one`

- 功能：行为断言：stale_verdict_requeues_current_tension_with_capacity_one；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Memory, _Judge, _close, _service, old.emb.copy, svc._commit_sidecar_effect, svc._semantic_model, svc.engine.add_tension, svc.observe, svc.process_semantic_tasks, svc.tasks.claim, svc.tasks.list_tasks, svc.tasks.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L341)。

### `tests/test_semantic_recovery.py::test_background_recovers_semantic_when_older_unit_is_backed_off`

- 功能：行为断言：background_recovers_semantic_when_older_unit_is_backed_off；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, pytest.raises, svc.feedback, svc.log.work, svc.observe, svc.start_unit_recovery, svc.tasks.list_tasks, time.monotonic, time.sleep。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L372)。

### `tests/test_semantic_recovery.py::test_unit_semantic_handoff_failure_rolls_back_effect_and_recovers`

- 功能：行为断言：unit_semantic_handoff_failure_rolls_back_effect_and_recovers；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, pytest.raises, svc.log._conn.execute, svc.log.work, svc.observe, svc.process_pending_units, svc.tasks._conn.execute, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L394)。

### `tests/test_semantic_recovery.py::test_recognizer_none_handoff_is_atomic_with_credit`

- 功能：行为断言：recognizer_none_handoff_is_atomic_with_credit；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _prepared, len, svc.feedback, svc.tasks._conn.execute, svc.tasks.claim, svc.tasks.list_tasks, svc.tasks.store_result, type, type(svc).process_semantic_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L417)。

### `tests/test_semantic_recovery.py::test_crash_after_unit_semantic_emission_before_worker`

- 功能：行为断言：crash_after_unit_semantic_emission_before_worker；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Path, Path(__file__).resolve, _Judge, _close, _service, str, subprocess.run, svc.log.work, svc.process_semantic_tasks, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L443)。

### `tests/test_semantic_recovery.py::test_feedback_for_empty_presented_context_has_no_pending_task`

- 功能：行为断言：feedback_for_empty_presented_context_has_no_pending_task；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _close, _service, svc.feedback, svc.observe, svc.recall, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L471)。

### `tests/test_semantic_recovery.py::test_recognizer_protocol_failure_falls_back_and_is_counted_durably`

- 功能：行为断言：recognizer_protocol_failure_falls_back_and_is_counted_durably；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 BadRecognizer, _close, _prepared, _service, restored.process_semantic_tasks, restored.signals, svc.feedback, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L483)。

### `tests/test_semantic_recovery.py::test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer`

- 功能：测试场景/夹具/假实现：test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L486)。

### `tests/test_semantic_recovery.py::test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer.__init__`

- 功能：测试场景/夹具/假实现：test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer.__init__；输入输出见本项，生产不调用
- 输入：`self, inner`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L487)。

### `tests/test_semantic_recovery.py::test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer.__getattr__`

- 功能：测试场景/夹具/假实现：test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self.inner, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L490)。

### `tests/test_semantic_recovery.py::test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer.relevant_set`

- 功能：测试场景/夹具/假实现：test_recognizer_protocol_failure_falls_back_and_is_counted_durably.BadRecognizer.relevant_set；输入输出见本项，生产不调用
- 输入：`self, texts, question, answer`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L493)。

### `tests/test_semantic_recovery.py::test_stale_reflection_requeues_changed_sources_once`

- 功能：行为断言：stale_reflection_requeues_changed_sources_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _Judge, _close, _service, len, svc._commit_sidecar_effect, svc._semantic_model, svc.engine._consolidation_pending.add, svc.engine.mems.values, svc.observe, svc.process_semantic_tasks, svc.tasks.claim, svc.tasks.list_tasks, svc.tasks.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L512)。

### `tests/test_semantic_recovery.py::test_conflict_model_result_survives_process_crash_before_effect`

- 功能：行为断言：conflict_model_result_survives_process_crash_before_effect；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Memory, Path, Path(__file__).resolve, _close, _service, old.emb.copy, restored.process_semantic_tasks, restored.tasks._conn.execute, restored.tasks.list_tasks, str, subprocess.run, svc._commit_sidecar_effect, svc.engine.add_tension, svc.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L539)。

### `tests/test_semantic_recovery.py::test_feedback_model_uses_text_actually_presented_before_memory_changes`

- 功能：行为断言：feedback_model_uses_text_actually_presented_before_memory_changes；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Probe, _close, _prepared, svc._commit_sidecar_effect, svc.feedback。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L580)。

### `tests/test_semantic_recovery.py::test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe`

- 功能：测试场景/夹具/假实现：test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L586)。

### `tests/test_semantic_recovery.py::test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe.__init__`

- 功能：测试场景/夹具/假实现：test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe.__init__；输入输出见本项，生产不调用
- 输入：`self, inner`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L587)。

### `tests/test_semantic_recovery.py::test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe.__getattr__`

- 功能：测试场景/夹具/假实现：test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self.inner, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L591)。

### `tests/test_semantic_recovery.py::test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe.relevant_set`

- 功能：测试场景/夹具/假实现：test_feedback_model_uses_text_actually_presented_before_memory_changes.Probe.relevant_set；输入输出见本项，生产不调用
- 输入：`self, texts, question, answer`。
- 输出：`未注解；[True] * len(texts)`。
- 作用：调用 len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_semantic_recovery.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_semantic_recovery.py#L594)。

## `tests/test_server.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_server.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`9e646a38e3a53601c54f41acd0ddc5b00fb5cb2fdf6bf1403820cd874261963a`。

### `tests/test_server.py::_TableEmbedder`

- 功能：测试场景/夹具/假实现：_TableEmbedder；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L18)。

### `tests/test_server.py::_TableEmbedder.__init__`

- 功能：测试场景/夹具/假实现：_TableEmbedder.__init__；输入输出见本项，生产不调用
- 输入：`self, table, default=None`。
- 输出：`未注解；None`。
- 作用：调用 np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L19)。

### `tests/test_server.py::_TableEmbedder.embed`

- 功能：测试场景/夹具/假实现：_TableEmbedder.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array([self.table.get(t, self.default) for t in texts], dtype=np.float32)`。
- 作用：调用 np.array, self.table.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L23)。

### `tests/test_server.py::_FixedGenerator`

- 功能：测试场景/夹具/假实现：_FixedGenerator；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L28)。

### `tests/test_server.py::_FixedGenerator.__init__`

- 功能：测试场景/夹具/假实现：_FixedGenerator.__init__；输入输出见本项，生产不调用
- 输入：`self, texts`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L29)。

### `tests/test_server.py::_FixedGenerator.generate`

- 功能：测试场景/夹具/假实现：_FixedGenerator.generate；输入输出见本项，生产不调用
- 输入：`self, window, prev_scene=''`。
- 输出：`未注解；CandidateGeneration(candidates=tuple((MemoryCandidate(text=t) for t in self.texts)), scene_name='测试场景')`。
- 作用：调用 CandidateGeneration, MemoryCandidate, tuple。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L33)。

### `tests/test_server.py::_service`

- 功能：测试场景/夹具/假实现：_service；输入输出见本项，生产不调用
- 输入：`tmp_path=None, texts=('部署在 B 服务器',)`。
- 输出：`未注解；svc`。
- 作用：调用 Cfg, MemoryService, RealChatSemantics, _FixedGenerator, _TableEmbedder, list, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L40)。

### `tests/test_server.py::test_observe_ingests_candidates`

- 功能：行为断言：observe_ingests_candidates；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, svc.engine.pool_sizes, svc.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L50)。

### `tests/test_server.py::test_recall_returns_context_and_registry`

- 功能：行为断言：recall_returns_context_and_registry；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, isinstance, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L58)。

### `tests/test_server.py::_engine_fingerprint`

- 功能：测试场景/夹具/假实现：_engine_fingerprint；输入输出见本项，生产不调用
- 输入：`svc`。
- 输出：`未注解；(mems, sorted(eng.tensions), len(eng.signals), len(eng._shadow_pending), svc._next_retrieval, svc._t)`。
- 作用：调用 eng.mems.values, len, round, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L67)。

### `tests/test_server.py::test_passive_recall_leaves_no_trace`

- 功能：行为断言：passive_recall_leaves_no_trace；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _engine_fingerprint, _service, isinstance, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L75)。

### `tests/test_server.py::test_recall_budget_truncates_whole_lines`

- 功能：行为断言：recall_budget_truncates_whole_lines；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, approx_tokens, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L89)。

### `tests/test_server.py::test_approx_tokens_rule`

- 功能：行为断言：approx_tokens_rule；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 approx_tokens。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L101)。

### `tests/test_server.py::test_feedback_credits_and_guards_double_call`

- 功能：行为断言：feedback_credits_and_guards_double_call；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, svc.feedback, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L107)。

### `tests/test_server.py::test_conflicts_and_resolve`

- 功能：行为断言：conflicts_and_resolve；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, np.array, svc.conflicts, svc.engine.add_tension, svc.observe, svc.resolve, type, type(svc.engine.mems[0])。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L118)。

### `tests/test_server.py::test_state_persists_across_restart`

- 功能：行为断言：state_persists_across_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.pkl').exists, Cfg, MemoryService, RealChatSemantics, _FixedGenerator, _TableEmbedder, _service, len, svc.observe, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L132)。

### `tests/test_server.py::test_http_roundtrip`

- 功能：行为断言：http_roundtrip；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, get, post。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L148)。

### `tests/test_server.py::test_http_auth_and_method_guards`

- 功能：行为断言：http_auth_and_method_guards；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / '.memory-token').read_text, (tmp_path / '.memory-token').read_text().strip, _http, _service, err.value.close, get, post, pytest.raises, urllib.request.urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L162)。

### `tests/test_server.py::test_http_body_and_k_guards`

- 功能：行为断言：http_body_and_k_guards；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, conn.close, conn.endheaders, conn.getresponse, conn.putheader, conn.putrequest, get, http.client.HTTPConnection, post, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L183)。

### `tests/test_server.py::test_http_field_and_body_validation`

- 功能：行为断言：http_field_and_body_validation；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, conn.close, conn.endheaders, conn.getresponse, conn.putheader, conn.putrequest, get, http.client.HTTPConnection, post。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L203)。

### `tests/test_server.py::test_empty_token_file_regenerates`

- 功能：行为断言：empty_token_file_regenerates；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / '.memory-token').read_text, (tmp_path / '.memory-token').read_text().strip, (tmp_path / '.memory-token').write_text, _service。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L229)。

### `tests/test_server.py::test_retrieval_registry_survives_restart`

- 功能：行为断言：retrieval_registry_survives_restart；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, MemoryService, RealChatSemantics, _FixedGenerator, _TableEmbedder, _service, np.array, svc.observe, svc.recall, svc.save, svc2.feedback, svc2.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L237)。

### `tests/test_server.py::test_state_load_rejects_evil_and_broken_pickle`

- 功能：行为断言：state_load_rejects_evil_and_broken_pickle；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.corrupt').exists, _service, evil.exists, evil.write_bytes, len, pickle.dumps。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L259)。

### `tests/test_server.py::test_memory_text_cannot_break_context_tag`

- 功能：行为断言：memory_text_cannot_break_context_tag；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, ctx.lower, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L273)。

### `tests/test_server.py::_http`

- 功能：共用 HTTP 往返/错误解码；退出时关闭服务。post/get 返回 (status, json)。
- 输入：`svc`。
- 输出：`未注解；生成器/上下文管理器`。
- 作用：调用 httpd.server_close, httpd.shutdown, serve, threading.Thread, threading.Thread(target=httpd.serve_forever, daemon=True).start。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L288)。

### `tests/test_server.py::_http.call`

- 功能：测试场景/夹具/假实现：_http.call；输入输出见本项，生产不调用
- 输入：`req`。
- 输出：`未注解；(e.code, json.loads(body))；(e.code, {'error': body})；(r.status, json.loads(r.read().decode('utf-8') or 'null'))`。
- 作用：调用 e.read, e.read().decode, json.loads, r.read, r.read().decode, urllib.request.urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L295)。

### `tests/test_server.py::_http.post`

- 功能：测试场景/夹具/假实现：_http.post；输入输出见本项，生产不调用
- 输入：`path, body, extra=None`。
- 输出：`未注解；call(urllib.request.Request(base + path, data=body if isinstance(body, bytes) else json.dumps(body).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {svc.token}', **(extra or {})}, method='POST'))`。
- 作用：调用 call, isinstance, json.dumps, json.dumps(body).encode, urllib.request.Request。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L306)。

### `tests/test_server.py::_http.get`

- 功能：测试场景/夹具/假实现：_http.get；输入输出见本项，生产不调用
- 输入：`path, extra=None`。
- 输出：`未注解；call(urllib.request.Request(base + path, headers={'Authorization': f'Bearer {svc.token}', **(extra or {})}))`。
- 作用：调用 call, urllib.request.Request。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L313)。

### `tests/test_server.py::test_observe_writes_l0_and_emits_extract_due`

- 功能：行为断言：observe_writes_l0_and_emits_extract_due；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, set, svc.log.count, svc.log.get, svc.log.get(0)['user_text'].startswith, svc.observe, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L325)。

### `tests/test_server.py::test_correction_reports_miss_with_the_retrieval_used`

- 功能：行为断言：correction_reports_miss_with_the_retrieval_used；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _service, sig['payload']['hints'][0].startswith, svc.feedback, svc.observe, svc.recall, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L334)。

### `tests/test_server.py::test_recognizer_none_miss_is_opt_in`

- 功能：行为断言：recognizer_none_miss_is_opt_in；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, MemoryService, _FixedGenerator, _NoneRecognizer, _TableEmbedder, np.array, svc.feedback, svc.observe, svc.recall, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L349)。

### `tests/test_server.py::test_recognizer_none_miss_is_opt_in._NoneRecognizer`

- 功能：测试场景/夹具/假实现：test_recognizer_none_miss_is_opt_in._NoneRecognizer；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 RealChatSemantics`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L350)。

### `tests/test_server.py::test_recognizer_none_miss_is_opt_in._NoneRecognizer.relevant_set`

- 功能：测试场景/夹具/假实现：test_recognizer_none_miss_is_opt_in._NoneRecognizer.relevant_set；输入输出见本项，生产不调用
- 输入：`self, texts, question, answer`。
- 输出：`未注解；[False] * len(texts)`。
- 作用：调用 len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L351)。

### `tests/test_server.py::test_log_tools_over_http`

- 功能：HTTP 只服务主 agent：不带信号、不计量、看得到全部。
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, get, list, post, range, svc.close_budget, svc.observe, svc.open_budget。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L368)。

### `tests/test_server.py::test_log_tools_signal_budget_and_causal_bound`

- 功能：进程内调查员带 signal_id：因果上界 + 调用次数/回展字符预算。
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _service, pytest.raises, svc.close_budget, svc.log_search, svc.log_stats, svc.log_window, svc.observe, svc.open_budget, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L393)。

### `tests/test_server.py::test_propose_validates_and_stamps_origin`

- 功能：行为断言：propose_validates_and_stamps_origin；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, get, post, reasons[5].startswith, svc.close_budget, svc.observe, svc.open_budget, svc.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L416)。

### `tests/test_server.py::test_miss_and_diagnose_endpoints`

- 功能：行为断言：miss_and_diagnose_endpoints；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'diagnoses.jsonl').read_text, (tmp_path / 'diagnoses.jsonl').read_text(encoding='utf-8').splitlines, _http, _service, get, json.loads, post, svc.tasks.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L457)。

### `tests/test_server.py::test_feedback_double_call_is_409_over_http`

- 功能：行为断言：feedback_double_call_is_409_over_http；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, post, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L479)。

### `tests/test_server.py::test_old_state_without_origin_and_entity_migrates`

- 功能：行为断言：old_state_without_origin_and_entity_migrates；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _service, iter, m.__dict__.pop, next, open, pickle.dump, pickle.load, state.pop, state['mems'].values, svc.observe, svc.save, svc2.engine.mems.values, svc2.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L489)。

### `tests/test_server.py::test_restart_with_missing_stale_or_corrupt_snapshot_preserves_l0`

- 功能：行为断言：restart_with_missing_stale_or_corrupt_snapshot_preserves_l0；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (directory / 'state.pkl').write_bytes, _service, restored.log.close, restored.log.count, restored.log.get, restored.log.search, restored.log.timeline, restored.observe, svc.log.close, svc.log.get, svc.observe, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L513)。

### `tests/test_server.py::test_stale_snapshot_keeps_memory_sources_and_advances_from_log`

- 功能：行为断言：stale_snapshot_keeps_memory_sources_and_advances_from_log；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _service, iter, next, restored.engine.mems.values, restored.log.close, restored.log.count, restored.log.get, restored.observe, svc.log.close, svc.log.get, svc.observe, svc.recall, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L538)。

### `tests/test_server.py::test_snapshot_cursors_ahead_of_log_are_not_rewound`

- 功能：行为断言：snapshot_cursors_ahead_of_log_are_not_rewound；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _service, restored.log.close, restored.log.get, restored.observe, svc.log.close, svc.observe, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L561)。

### `tests/test_server.py::test_observe_refreshes_cursors_even_when_log_advances_after_startup`

- 功能：行为断言：observe_refreshes_cursors_even_when_log_advances_after_startup；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 LogStore, _service, other.add_unit, other.close, svc.log.close, svc.log.get, svc.observe。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L576)。

### `tests/test_server.py::test_l0_is_committed_before_candgen_even_with_allocated_ids`

- 功能：行为断言：l0_is_committed_before_candgen_even_with_allocated_ids；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 CheckGenerator, _service, svc.log.close, svc.log.count, svc.observe, svc.signals。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L592)。

### `tests/test_server.py::test_l0_is_committed_before_candgen_even_with_allocated_ids.CheckGenerator`

- 功能：测试场景/夹具/假实现：test_l0_is_committed_before_candgen_even_with_allocated_ids.CheckGenerator；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L599)。

### `tests/test_server.py::test_l0_is_committed_before_candgen_even_with_allocated_ids.CheckGenerator.generate`

- 功能：测试场景/夹具/假实现：test_l0_is_committed_before_candgen_even_with_allocated_ids.CheckGenerator.generate；输入输出见本项，生产不调用
- 输入：`self, window, prev_scene=''`。
- 输出：`未注解；None`。
- 作用：调用 RuntimeError, committed.append, conn.execute, conn.execute('SELECT id, t, user_text FROM units').fetchone, sqlite3.connect。
- 错误：异常 RuntimeError('expected candgen outage')。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L600)。

### `tests/test_server.py::test_invalid_snapshot_does_not_publish_partially_loaded_memory`

- 功能：行为断言：invalid_snapshot_does_not_publish_partially_loaded_memory；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _service, path.open, pickle.dump, pickle.load, restored.log.close, restored.log.get, restored.observe, svc.log.add_unit, svc.log.close, svc.propose, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L618)。

### `tests/test_server.py::test_snapshot_counters_cannot_replace_service_internals`

- 功能：行为断言：snapshot_counters_cannot_replace_service_internals；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.corrupt').exists, _service, path.open, pickle.dump, pickle.load, restored.log.close, restored.observe, svc.log.close, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L646)。

### `tests/test_server.py::test_complete_legacy_name_encoded_snapshot_restores`

- 功能：行为断言：complete_legacy_name_encoded_snapshot_restores；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'state.corrupt').exists, (tmp_path / 'state.pkl').read_bytes, _service, iter, monkeypatch.context, next, patch.setattr, restored.engine.mems.values, restored.log.close, restored.observe, restored.save, svc.log.close, svc.observe, svc.recall, svc.save。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L666)。

### `tests/test_server.py::test_bad_http_ids_and_feedback_types_do_not_mutate_state`

- 功能：行为断言：bad_http_ids_and_feedback_types_do_not_mutate_state；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, float, pickle.dumps, post, svc._state, svc.observe, svc.recall。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L691)。

### `tests/test_server.py::test_proposal_bounds_and_malformed_supersedes_do_not_partially_apply`

- 功能：行为断言：proposal_bounds_and_malformed_supersedes_do_not_partially_apply；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, dict, float, post, svc.observe, svc.propose。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L710)。

### `tests/test_server.py::test_passive_sources_belong_to_actual_window_and_bad_json_schedules_repair`

- 功能：行为断言：passive_sources_belong_to_actual_window_and_bad_json_schedules_repair；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ChatGenerator, _service, frozenset, svc.observe, svc.tasks.queued_counts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L724)。

### `tests/test_server.py::test_http_passive_budget_keeps_checkpoint_unchanged`

- 功能：行为断言：http_passive_budget_keeps_checkpoint_unchanged；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 _http, _service, get, post, svc._dump_state, svc.observe, svc.save, svc.tasks.checkpoint。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_server.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_server.py#L736)。

## `tests/test_signals.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_signals.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`ad2e5dbf841b9aaa2ec1942db641451dbfc5fdc93b873da115636747e7d7cd82`。

### `tests/test_signals.py::make`

- 功能：测试场景/夹具/假实现：make；输入输出见本项，生产不调用
- 输入：`seed=0, cfg=None`。
- 输出：`未注解；(emb, world, MemoryEngine(cfg or Cfg(), emb, world))`。
- 作用：调用 Cfg, FakeWorld, MemoryEngine, SyntheticEmbedder。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L21)。

### `tests/test_signals.py::_Judge`

- 功能：judge 固定 verdict（或 fail=True 被调即炸），其余委托 FakeWorld。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L27)。

### `tests/test_signals.py::_Judge.__init__`

- 功能：测试场景/夹具/假实现：_Judge.__init__；输入输出见本项，生产不调用
- 输入：`self, inner, verdict='synonym', fail=False`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L30)。

### `tests/test_signals.py::_Judge.__getattr__`

- 功能：测试场景/夹具/假实现：_Judge.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self._inner, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L35)。

### `tests/test_signals.py::_Judge.judge`

- 功能：测试场景/夹具/假实现：_Judge.judge；输入输出见本项，生产不调用
- 输入：`self, *args`。
- 输出：`未注解；self._verdict`。
- 作用：调用 AssertionError。
- 错误：异常 AssertionError('defer 模式下不应调用 judge')。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L38)。

### `tests/test_signals.py::_suppression_setup`

- 功能：构造压制场景：rival 先入选，m 与 rival 相似度 0.99 > tau_sim。 verdict/fail 在检索前注入 judge stub。
- 输入：`cfg, verdict=None, fail=False`。
- 输出：`未注解；(eng, ret, rival, m)`。
- 作用：调用 Memory, Query, _Judge, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L44)。

### `tests/test_signals.py::test_queue_bound_and_drop_counter`

- 功能：行为断言：queue_bound_and_drop_counter；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 SignalQueue, len, q.drain, q.emit, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L61)。

### `tests/test_signals.py::test_conflict_signal_emits_aged_pairs_at_step`

- 功能：行为断言：conflict_signal_emits_aged_pairs_at_step；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, eng.add_tension, eng.drain_signals, eng.step, len, make, np.array, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L72)。

### `tests/test_signals.py::test_conflict_signal_respects_tension_delay`

- 功能：行为断言：conflict_signal_respects_tension_delay；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, eng.add_tension, eng.drain_signals, eng.step, make, np.array, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L94)。

### `tests/test_signals.py::test_thin_recall_deduped_per_step`

- 功能：行为断言：thin_recall_deduped_per_step；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Query, emb.embed, eng.drain_signals, eng.retrieve, kinds.count, make。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L110)。

### `tests/test_signals.py::test_feedback_pending_emitted_by_feedback_call`

- 功能：行为断言：feedback_pending_emitted_by_feedback_call；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.vec_for, emb2.vec_for, eng.drain_signals, eng.feedback, eng.observe, eng.retrieve, eng2.feedback, eng2.observe, eng2.retrieve, len, make, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L121)。

### `tests/test_signals.py::test_submit_relevance_matches_feedback_effects`

- 功能：行为断言：submit_relevance_matches_feedback_effects；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.vec_for, eng.observe, eng.retrieve, eng.submit_relevance, len, make, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L145)。

### `tests/test_signals.py::test_submit_verdicts_synonym_matches_worker_path`

- 功能：行为断言：submit_verdicts_synonym_matches_worker_path；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 SignalWorker, SignalWorker(eng_w, _Judge(world_w, verdict='synonym')).process, _Judge, _setup, eng_op.submit_verdicts, eng_w.step。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L159)。

### `tests/test_signals.py::test_submit_verdicts_synonym_matches_worker_path._setup`

- 功能：测试场景/夹具/假实现：test_submit_verdicts_synonym_matches_worker_path._setup；输入输出见本项，生产不调用
- 输入：`seed`。
- 输出：`未注解；(world, eng, a, bb)`。
- 作用：调用 Cfg, Memory, eng.add_tension, make, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L160)。

### `tests/test_signals.py::test_submit_verdicts_pending_keeps_backlog`

- 功能：行为断言：submit_verdicts_pending_keeps_backlog；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, eng.add_tension, eng.submit_verdicts, make, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L185)。

### `tests/test_signals.py::test_submit_verdicts_stale_pair_dropped`

- 功能：行为断言：submit_verdicts_stale_pair_dropped；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Memory, eng.add_tension, eng.submit_verdicts, make, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L197)。

### `tests/test_signals.py::test_maintenance_due_emitted_without_callback`

- 功能：行为断言：maintenance_due_emitted_without_callback；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, eng.drain_signals, eng.step, make, np.array, range, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L206)。

### `tests/test_signals.py::test_add_reflection_admits_memory`

- 功能：行为断言：add_reflection_admits_memory；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.add_reflection, make。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L223)。

### `tests/test_signals.py::test_shadow_records_pending_without_judge`

- 功能：行为断言：shadow_records_pending_without_judge；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, _suppression_setup, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L233)。

### `tests/test_signals.py::test_shadow_settles_on_update_verdict`

- 功能：行为断言：shadow_settles_on_update_verdict；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, _suppression_setup, eng.submit_verdicts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L243)。

### `tests/test_signals.py::test_shadow_synonym_no_credit`

- 功能：行为断言：shadow_synonym_no_credit；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, _suppression_setup, eng.submit_verdicts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L253)。

### `tests/test_signals.py::test_shadow_pending_verdict_credits_keeps_backlog`

- 功能：行为断言：shadow_pending_verdict_credits_keeps_backlog；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, _suppression_setup, eng.submit_verdicts。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L259)。

### `tests/test_signals.py::test_shadow_settles_via_worker`

- 功能：行为断言：shadow_settles_via_worker；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, SignalWorker, SignalWorker(eng, _Judge(eng.semantics, verdict='update')).process, _Judge, _suppression_setup, eng.step。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L268)。

### `tests/test_signals.py::test_shadow_pending_bounded`

- 功能：行为断言：shadow_pending_bounded；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, _suppression_setup, eng._record_shadow_pending, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L276)。

### `tests/test_signals.py::test_worker_absent_system_operates_and_queue_bounded`

- 功能：行为断言：worker_absent_system_operates_and_queue_bounded；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.vec_for, eng.observe, eng.pool_sizes, eng.retrieve, eng.step, len, make, range。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L283)。

### `tests/test_signals.py::_RecogStub`

- 功能：relevant_set 返回指定值（None=失败 / 长度不齐=违约），其余委托。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L297)。

### `tests/test_signals.py::_RecogStub.__init__`

- 功能：测试场景/夹具/假实现：_RecogStub.__init__；输入输出见本项，生产不调用
- 输入：`self, inner, ret`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L300)。

### `tests/test_signals.py::_RecogStub.__getattr__`

- 功能：测试场景/夹具/假实现：_RecogStub.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self._inner, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L304)。

### `tests/test_signals.py::_RecogStub.relevant_set`

- 功能：测试场景/夹具/假实现：_RecogStub.relevant_set；输入输出见本项，生产不调用
- 输入：`self, texts, question, answer`。
- 输出：`未注解；self._ret`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L307)。

### `tests/test_signals.py::_feedback_setup`

- 功能：一次 defer 检索 + feedback 信号已入队的场景。
- 输入：`sem_wrap=None`。
- 输出：`未注解；(eng, ret, w)`。
- 作用：调用 Cfg, Event, Query, SignalWorker, emb.vec_for, eng.feedback, eng.observe, eng.retrieve, make, sem_wrap。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L311)。

### `tests/test_signals.py::test_worker_recog_fail_counts_and_degrades`

- 功能：行为断言：worker_recog_fail_counts_and_degrades；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _feedback_setup, len, w.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L323)。

### `tests/test_signals.py::test_worker_recog_bad_length_is_failure_not_crash`

- 功能：行为断言：worker_recog_bad_length_is_failure_not_crash；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _feedback_setup, len, w.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L332)。

### `tests/test_signals.py::test_worker_error_containment_requeues_failed_signal`

- 功能：行为断言：worker_error_containment_requeues_failed_signal；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Memory, Query, SignalWorker, _Judge, emb.embed, emb.vec_for, eng.add_tension, eng.drain_signals, eng.feedback, eng.observe, eng.retrieve, eng.step, make, w.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L341)。

### `tests/test_signals.py::_HashEmbedder`

- 功能：字符哈希词袋：真实文本可嵌入、确定、无网络。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L363)。

### `tests/test_signals.py::_HashEmbedder.embed`

- 功能：测试场景/夹具/假实现：_HashEmbedder.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array(out, dtype=np.float32)`。
- 作用：调用 hash, np.array, np.linalg.norm, np.zeros, out.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L365)。

### `tests/test_signals.py::_plain_engine`

- 功能：测试场景/夹具/假实现：_plain_engine；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`未注解；MemoryEngine(Cfg(), _HashEmbedder(), RealChatSemantics(None))`。
- 作用：调用 Cfg, MemoryEngine, RealChatSemantics, _HashEmbedder。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L375)。

### `tests/test_signals.py::test_take_only_removes_requested_kinds_in_order`

- 功能：行为断言：take_only_removes_requested_kinds_in_order；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 SignalQueue, q.drain, q.emit, q.peek_kinds, q.take。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L380)。

### `tests/test_signals.py::test_take_releases_keys_so_signal_can_be_re_emitted`

- 功能：行为断言：take_releases_keys_so_signal_can_be_re_emitted；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 SignalQueue, q.emit, q.peek_kinds, q.take。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L392)。

### `tests/test_signals.py::test_report_miss_dedupes_by_question_and_merges_payload`

- 功能：行为断言：report_miss_dedupes_by_question_and_merges_payload；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _plain_engine, eng.report_miss, eng.signals.take, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L400)。

### `tests/test_signals.py::test_report_unit_dedupes_by_unit_and_unions_reasons`

- 功能：行为断言：report_unit_dedupes_by_unit_and_unions_reasons；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 _plain_engine, eng.report_unit, eng.signals.take, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L415)。

### `tests/test_signals.py::test_engine_propose_requires_non_passive_origin_and_keeps_it`

- 功能：行为断言：engine_propose_requires_non_passive_origin_and_keeps_it；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, _plain_engine, eng.propose, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L426)。

### `tests/test_signals.py::test_semantic_worker_leaves_agent_signals_in_queue`

- 功能：行为断言：semantic_worker_leaves_agent_signals_in_queue；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 RealChatSemantics, SignalWorker, SignalWorker(eng, RealChatSemantics(None)).process, _plain_engine, eng.report_miss, eng.report_unit, eng.signals.peek_kinds。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L438)。

### `tests/test_signals.py::test_worker_two_phase_lock_does_not_hold_lock_during_semantics`

- 功能：worker 持服务锁时只做引擎读写；调 semantics 时锁必须是放开的。
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Memory, SignalWorker, _Probe, all, eng.add_tension, eng.signals.emit, make, np.array, threading.RLock, worker.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L447)。

### `tests/test_signals.py::test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe`

- 功能：测试场景/夹具/假实现：test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L454)。

### `tests/test_signals.py::test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe.__getattr__`

- 功能：测试场景/夹具/假实现：test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(world, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L455)。

### `tests/test_signals.py::test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe.judge`

- 功能：测试场景/夹具/假实现：test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe.judge；输入输出见本项，生产不调用
- 输入：`self, *args`。
- 输出：`未注解；world.judge(*args)`。
- 作用：调用 bool, seen.append, th.join, th.start, threading.Thread, world.judge。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L458)。

### `tests/test_signals.py::test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe.judge.probe`

- 功能：测试场景/夹具/假实现：test_worker_two_phase_lock_does_not_hold_lock_during_semantics._Probe.judge.probe；输入输出见本项，生产不调用
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 got.append, lock.acquire, lock.release。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_signals.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_signals.py#L463)。

## `tests/test_smoke.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_smoke.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`6cd33e28922db966e658943c3a79c64f86fb8efc51ab5d942e8065dcad3083c0`。

### `tests/test_smoke.py::make`

- 功能：测试场景/夹具/假实现：make；输入输出见本项，生产不调用
- 输入：`seed=0, cfg=None`。
- 输出：`未注解；(emb, world, MemoryEngine(cfg or Cfg(), emb, world))`。
- 作用：调用 Cfg, FakeWorld, MemoryEngine, SyntheticEmbedder。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L18)。

### `tests/test_smoke.py::_TableEmbedder`

- 功能：按 text 查表给向量，用于精确控制 ingest 余弦。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L24)。

### `tests/test_smoke.py::_TableEmbedder.__init__`

- 功能：测试场景/夹具/假实现：_TableEmbedder.__init__；输入输出见本项，生产不调用
- 输入：`self, table`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L27)。

### `tests/test_smoke.py::_TableEmbedder.embed`

- 功能：测试场景/夹具/假实现：_TableEmbedder.embed；输入输出见本项，生产不调用
- 输入：`self, texts, keys=None`。
- 输出：`未注解；np.array([self.table[t] for t in texts], dtype=np.float32)`。
- 作用：调用 np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L30)。

### `tests/test_smoke.py::_stub_engine`

- 功能：测试场景/夹具/假实现：_stub_engine；输入输出见本项，生产不调用
- 输入：`cfg, table`。
- 输出：`未注解；(world, MemoryEngine(cfg, _TableEmbedder(table), world))`。
- 作用：调用 FakeWorld, MemoryEngine, _TableEmbedder。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L34)。

### `tests/test_smoke.py::_Consolidatable`

- 功能：FakeWorld 委托 + 可注入 consolidate 回调（out 原样返回）。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L39)。

### `tests/test_smoke.py::_Consolidatable.__init__`

- 功能：测试场景/夹具/假实现：_Consolidatable.__init__；输入输出见本项，生产不调用
- 输入：`self, world, out`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L42)。

### `tests/test_smoke.py::_Consolidatable.__getattr__`

- 功能：测试场景/夹具/假实现：_Consolidatable.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self._world, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L47)。

### `tests/test_smoke.py::_Consolidatable.consolidate`

- 功能：测试场景/夹具/假实现：_Consolidatable.consolidate；输入输出见本项，生产不调用
- 输入：`self, memories, t`。
- 输出：`未注解；out`。
- 作用：调用 callable, isinstance, self._out, self.calls.append。
- 错误：异常 out。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L50)。

### `tests/test_smoke.py::_JudgeSpy`

- 功能：包装 semantics：judge 计数/注入 verdict；fail=True 时被调即炸。
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L58)。

### `tests/test_smoke.py::_JudgeSpy.__init__`

- 功能：测试场景/夹具/假实现：_JudgeSpy.__init__；输入输出见本项，生产不调用
- 输入：`self, inner, verdict='synonym', fail=False`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L61)。

### `tests/test_smoke.py::_JudgeSpy.__getattr__`

- 功能：测试场景/夹具/假实现：_JudgeSpy.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(self._inner, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L67)。

### `tests/test_smoke.py::_JudgeSpy.judge`

- 功能：测试场景/夹具/假实现：_JudgeSpy.judge；输入输出见本项，生产不调用
- 输入：`self, *args`。
- 输出：`未注解；self._verdict`。
- 作用：调用 AssertionError, self.calls.append。
- 错误：异常 AssertionError('不该调用 judge')。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L70)。

### `tests/test_smoke.py::test_ingest_dedup_pools_evidence`

- 功能：行为断言：ingest_dedup_pools_evidence；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.observe, iter, len, make, next, range, world.beliefs.values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L77)。

### `tests/test_smoke.py::test_ingest_low_sim_never_calls_judge`

- 功能：行为断言：ingest_low_sim_never_calls_judge；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _JudgeSpy, _stub_engine, eng.observe, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L87)。

### `tests/test_smoke.py::test_ingest_high_sim_verbatim_dedup_needs_no_judge`

- 功能：行为断言：ingest_high_sim_verbatim_dedup_needs_no_judge；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _JudgeSpy, _stub_engine, eng.observe, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L97)。

### `tests/test_smoke.py::test_ingest_near_dup_resolves_via_worker`

- 功能：行为断言：ingest_near_dup_resolves_via_worker；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, SignalWorker(eng, spy).process, _JudgeSpy, _stub_engine, eng.observe, eng.step, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L108)。

### `tests/test_smoke.py::test_ingest_dedup_off_high_sim_no_judge_still_tension`

- 功能：行为断言：ingest_dedup_off_high_sim_no_judge_still_tension；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _JudgeSpy, _stub_engine, eng.observe, len。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L124)。

### `tests/test_smoke.py::test_promotion_and_demotion`

- 功能：行为断言：promotion_and_demotion；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.observe, eng.step, iter, make, next, world.beliefs.values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L134)。

### `tests/test_smoke.py::test_archive_on_idle`

- 功能：行为断言：archive_on_idle；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.observe, eng.step, iter, make, next, world.beliefs.values。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L147)。

### `tests/test_smoke.py::test_capacity_eviction`

- 功能：行为断言：capacity_eviction；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.mems.values, eng.observe, eng.step, make, range, sum, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L155)。

### `tests/test_smoke.py::test_c_overflow_archives_lowest_v_first`

- 功能：行为断言：c_overflow_archives_lowest_v_first；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, all, eng.mems.values, eng.observe, eng.step, make, math.exp, range, sorted, sum, world.spawn, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L170)。

### `tests/test_smoke.py::test_a_overflow_deletes_oldest_first`

- 功能：行为断言：a_overflow_deletes_oldest_first；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.mems.values, eng.observe, eng.step, make, range, sorted, world.spawn, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L188)。

### `tests/test_smoke.py::test_m_full_rejects_promotion`

- 功能：行为断言：m_full_rejects_promotion；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.mems.values, eng.observe, eng.step, list, make, range, sum, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L202)。

### `tests/test_smoke.py::test_pinned_memories_skip_c_eviction`

- 功能：行为断言：pinned_memories_skip_c_eviction；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.add_tension, eng.mems.values, eng.observe, eng.step, list, make, range, sorted, world.spawn, zip。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L223)。

### `tests/test_smoke.py::test_overflow_policy_pure_shape`

- 功能：行为断言：overflow_policy_pure_shape；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.mems.values, eng.observe, evictable, frozenset, list, make, overflow_policy, range, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L242)。

### `tests/test_smoke.py::test_retrieve_returns_topk`

- 功能：行为断言：retrieve_returns_topk；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 emb.vec_for, eng.observe, eng.retrieve, len, make, world.event, world.query。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L260)。

### `tests/test_smoke.py::test_relevance_is_query_specific`

- 功能：行为断言：relevance_is_query_specific；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.embed, eng.observe, eng.retrieve, len, make, world.embedding_key, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L268)。

### `tests/test_smoke.py::test_irrelevant_selection_does_not_extend_idle_life`

- 功能：行为断言：irrelevant_selection_does_not_extend_idle_life；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, eng.mems[0].emb.copy, eng.observe, eng.retrieve, eng.step, make, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L284)。

### `tests/test_smoke.py::test_late_candidate_gets_full_idle_window`

- 功能：行为断言：late_candidate_gets_full_idle_window；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.observe, eng.step, make, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L301)。

### `tests/test_smoke.py::test_archive_revival`

- 功能：行为断言：archive_revival；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, Query, emb.embed, eng.observe, eng.retrieve, eng.step, make, world.embedding_key。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L313)。

### `tests/test_smoke.py::test_archive_retrieval_can_be_disabled`

- 功能：行为断言：archive_retrieval_can_be_disabled；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.embed, eng.observe, eng.retrieve, make, world.embedding_key。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L326)。

### `tests/test_smoke.py::test_archive_prior_affects_quality_gate`

- 功能：行为断言：archive_prior_affects_quality_gate；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L337)。

### `tests/test_smoke.py::test_freshness_does_not_bypass_quality_gate`

- 功能：行为断言：freshness_does_not_bypass_quality_gate；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L351)。

### `tests/test_smoke.py::test_delayed_tension_scope_resolution`

- 功能：行为断言：delayed_tension_scope_resolution；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, SignalWorker(eng, world).process, eng.mems.values, eng.observe, eng.step, len, make, next, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L365)。

### `tests/test_smoke.py::test_shadow_credit_reaches_relevant_challenger`

- 功能：行为断言：shadow_credit_reaches_relevant_challenger；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, SignalWorker, SignalWorker(eng, world).process, challenger_memory.emb.copy, eng.observe, eng.retrieve, eng.step, incumbent_memory.emb.copy, make, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L389)。

### `tests/test_smoke.py::test_drift_supersedes_old_value_after_delay`

- 功能：行为断言：drift_supersedes_old_value_after_delay；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, SignalWorker(eng, world).process, eng.mems.values, eng.observe, eng.step, make, next, world.valid。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L417)。

### `tests/test_smoke.py::test_noise_burst_never_promotes_and_expires`

- 功能：行为断言：noise_burst_never_promotes_and_expires；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 all, eng.mems.values, eng.observe, eng.step, make, range, world.event, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L437)。

### `tests/test_smoke.py::test_deferred_credit_only_rewards_recognized`

- 功能：行为断言：deferred_credit_only_rewards_recognized；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, MemoryEngine, Query, Recog, SignalWorker, SignalWorker(eng2, Recog()).process, all, emb.embed, eng.observe, eng.retrieve, eng2.feedback, eng2.observe, eng2.retrieve, len, make, world.embedding_key, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L449)。

### `tests/test_smoke.py::test_deferred_credit_only_rewards_recognized.Recog`

- 功能：测试场景/夹具/假实现：test_deferred_credit_only_rewards_recognized.Recog；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L465)。

### `tests/test_smoke.py::test_deferred_credit_only_rewards_recognized.Recog.__getattr__`

- 功能：测试场景/夹具/假实现：test_deferred_credit_only_rewards_recognized.Recog.__getattr__；输入输出见本项，生产不调用
- 输入：`self, k`。
- 输出：`未注解；getattr(world, k)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L466)。

### `tests/test_smoke.py::test_deferred_credit_only_rewards_recognized.Recog.relevant_set`

- 功能：测试场景/夹具/假实现：test_deferred_credit_only_rewards_recognized.Recog.relevant_set；输入输出见本项，生产不调用
- 输入：`self, texts, q, a`。
- 输出：`未注解；[True, False]`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L469)。

### `tests/test_smoke.py::test_llm_semantics_parse_with_fake_chat`

- 功能：行为断言：llm_semantics_parse_with_fake_chat；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LLMSemantics, iter, sem.judge, sem2.relevant_set, sem3.relevant_set, sem3b.relevant_set, sem4.relevant_set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L485)。

### `tests/test_smoke.py::test_confidence_write_and_confirm_evidence`

- 功能：行为断言：confidence_write_and_confirm_evidence；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, abs, eng.observe, make, projected。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L507)。

### `tests/test_smoke.py::test_confidence_discount_half_life_idempotent`

- 功能：行为断言：confidence_discount_half_life_idempotent；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, abs, discount_to, eng.observe, eng.step, make, projected。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L519)。

### `tests/test_smoke.py::test_low_confidence_excluded_without_margin`

- 功能：行为断言：low_confidence_excluded_without_margin；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L533)。

### `tests/test_smoke.py::test_lone_low_confidence_served_as_provisional`

- 功能：行为断言：lone_low_confidence_served_as_provisional；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L548)。

### `tests/test_smoke.py::test_low_confidence_co_served_when_margin_exceeded`

- 功能：行为断言：low_confidence_co_served_when_margin_exceeded；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L560)。

### `tests/test_smoke.py::test_provisional_k_counts_admitted_not_attempted`

- 功能：行为断言：provisional_k_counts_admitted_not_attempted；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L575)。

### `tests/test_smoke.py::test_feedback_on_provisional_does_not_change_confidence`

- 功能：行为断言：feedback_on_provisional_does_not_change_confidence；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, SignalWorker, SignalWorker(eng, world).process, eng.feedback, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L598)。

### `tests/test_smoke.py::test_contradiction_scoped_no_negative_evidence`

- 功能：行为断言：contradiction_scoped_no_negative_evidence；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, SignalWorker(eng, world).process, abs, eng.mems.values, eng.observe, eng.step, make, next, projected, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L614)。

### `tests/test_smoke.py::test_contradiction_unscoped_adds_negative_evidence`

- 功能：行为断言：contradiction_unscoped_adds_negative_evidence；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, FakeWorld, MemoryEngine, SignalWorker, SignalWorker(eng, Unscoped()).process, SyntheticEmbedder, Unscoped, eng.mems.values, eng.observe, eng.step, max, min, next, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L634)。

### `tests/test_smoke.py::test_contradiction_unscoped_adds_negative_evidence.Unscoped`

- 功能：测试场景/夹具/假实现：test_contradiction_unscoped_adds_negative_evidence.Unscoped；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L639)。

### `tests/test_smoke.py::test_contradiction_unscoped_adds_negative_evidence.Unscoped.__getattr__`

- 功能：测试场景/夹具/假实现：test_contradiction_unscoped_adds_negative_evidence.Unscoped.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(world, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L640)。

### `tests/test_smoke.py::test_contradiction_unscoped_adds_negative_evidence.Unscoped.judge`

- 功能：测试场景/夹具/假实现：test_contradiction_unscoped_adds_negative_evidence.Unscoped.judge；输入输出见本项，生产不调用
- 输入：`self, a_bid, a_val, b_bid, b_val`。
- 输出：`未注解；'contradiction'`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L643)。

### `tests/test_smoke.py::test_contradiction_unscoped_adds_negative_evidence.Unscoped.scope`

- 功能：测试场景/夹具/假实现：test_contradiction_unscoped_adds_negative_evidence.Unscoped.scope；输入输出见本项，生产不调用
- 输入：`self, belief_id`。
- 输出：`未注解；''`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L646)。

### `tests/test_smoke.py::test_salience_off_ignores_event_and_decays_identically`

- 功能：行为断言：salience_off_ignores_event_and_decays_identically；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Memory, eng.observe, eng.step, make, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L667)。

### `tests/test_smoke.py::test_salience_on_exponential_decay`

- 功能：行为断言：salience_on_exponential_decay；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, abs, eng.step, make, math.exp, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L684)。

### `tests/test_smoke.py::test_retention_scale_floor`

- 功能：行为断言：retention_scale_floor；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, _retention_scale, abs, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L697)。

### `tests/test_smoke.py::test_salience_extends_idle_horizon_not_immortal`

- 功能：行为断言：salience_extends_idle_horizon_not_immortal；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, eng.step, make, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L709)。

### `tests/test_smoke.py::test_salience_does_not_couple_confidence_discount`

- 功能：行为断言：salience_does_not_couple_confidence_discount；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, abs, eng.step, make, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L726)。

### `tests/test_smoke.py::test_salience_on_ingest_clamps_and_dedup_takes_max`

- 功能：行为断言：salience_on_ingest_clamps_and_dedup_takes_max；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.observe, make。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L740)。

### `tests/test_smoke.py::test_salience_propagates_on_merge_update_aggregate`

- 功能：行为断言：salience_propagates_on_merge_update_aggregate；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, SignalWorker, SignalWorker(eng, world).process, eng.add_tension, eng.mems.values, eng.step, make, next, np.array, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L757)。

### `tests/test_smoke.py::test_novelty_off_records_metadata_without_v_change`

- 功能：行为断言：novelty_off_records_metadata_without_v_change；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _stub_engine, eng.observe, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L806)。

### `tests/test_smoke.py::test_novelty_on_bonus_scales_initial_v`

- 功能：行为断言：novelty_on_bonus_scales_initial_v；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _stub_engine, eng.observe, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L818)。

### `tests/test_smoke.py::test_novelty_clamps_negative_and_identical_cosine`

- 功能：行为断言：novelty_clamps_negative_and_identical_cosine；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _stub_engine, eng.observe, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L830)。

### `tests/test_smoke.py::test_low_novelty_update_still_admitted_with_tension`

- 功能：行为断言：low_novelty_update_still_admitted_with_tension；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, _stub_engine, eng.observe, len, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L843)。

### `tests/test_smoke.py::test_novelty_leaves_confidence_and_salience_unchanged`

- 功能：行为断言：novelty_leaves_confidence_and_salience_unchanged；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.observe, make。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L855)。

### `tests/test_smoke.py::test_novelty_bonus_alone_never_promotes_and_decays`

- 功能：行为断言：novelty_bonus_alone_never_promotes_and_decays；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, eng.observe, eng.step, make。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L867)。

### `tests/test_smoke.py::test_aggregate_novelty_max_without_extra_v_bonus`

- 功能：行为断言：aggregate_novelty_max_without_extra_v_bonus；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, SignalWorker, SignalWorker(eng, world).process, eng.add_tension, eng.mems.values, eng.step, make, max, next, np.array, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L880)。

### `tests/test_smoke.py::test_consolidation_below_budget_not_called`

- 功能：行为断言：consolidation_below_budget_not_called；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, all, eng.mems.values, eng.observe, eng.step, make, worker.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L899)。

### `tests/test_smoke.py::test_consolidation_threshold_creates_reflection_once`

- 功能：行为断言：consolidation_threshold_creates_reflection_once；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, abs, eng.mems.values, eng.observe, eng.step, float, frozenset, make, max, min, next, np.dot, np.linalg.norm, range, worker.process, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L915)。

### `tests/test_smoke.py::test_consolidation_none_callback_leaves_pending`

- 功能：行为断言：consolidation_none_callback_leaves_pending；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, eng.observe, eng.step, make, range, worker.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L961)。

### `tests/test_smoke.py::test_consolidation_prunes_ineligible_pending`

- 功能：行为断言：consolidation_prunes_ineligible_pending；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Memory, SignalWorker, SignalWorker(eng, sem).process, _Consolidatable, eng._consolidation_pending.update, eng.observe, eng.step, make, np.array, range, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L979)。

### `tests/test_smoke.py::test_lineage_suppression_creates_no_tension`

- 功能：行为断言：lineage_suppression_creates_no_tension；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, NoJudge, Query, eng.retrieve, make, math.sqrt, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1004)。

### `tests/test_smoke.py::test_lineage_suppression_creates_no_tension.NoJudge`

- 功能：测试场景/夹具/假实现：test_lineage_suppression_creates_no_tension.NoJudge；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1009)。

### `tests/test_smoke.py::test_lineage_suppression_creates_no_tension.NoJudge.__getattr__`

- 功能：测试场景/夹具/假实现：test_lineage_suppression_creates_no_tension.NoJudge.__getattr__；输入输出见本项，生产不调用
- 输入：`self, name`。
- 输出：`未注解；getattr(world, name)`。
- 作用：调用 getattr。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1010)。

### `tests/test_smoke.py::test_lineage_suppression_creates_no_tension.NoJudge.judge`

- 功能：测试场景/夹具/假实现：test_lineage_suppression_creates_no_tension.NoJudge.judge；输入输出见本项，生产不调用
- 输入：`self, *a`。
- 输出：`未注解；None`。
- 作用：调用 AssertionError。
- 错误：异常 AssertionError('judge must not be called')。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1013)。

### `tests/test_smoke.py::test_consolidation_reflection_gets_no_write_evidence`

- 功能：行为断言：consolidation_reflection_gets_no_write_evidence；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, eng.mems.values, eng.observe, eng.step, make, next, worker.process, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1033)。

### `tests/test_smoke.py::test_llm_consolidate_payload_event_and_fallbacks`

- 功能：行为断言：llm_consolidate_payload_event_and_fallbacks；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 LLMSemantics, LLMSemantics(None, chat_fn=boom).consolidate, LLMSemantics(None, chat_fn=lambda s, u: ' ').consolidate, LLMSemantics(None, chat_fn=lambda s, u: ' none ').consolidate, LLMSemantics(None, chat_fn=lambda s, u: 'NONE').consolidate, LLMSemantics(None, chat_fn=lambda s, u: 'key 是 sk-abc123def456ghi789').consolidate, Memory, normalize, np.array, seen[0].splitlines, sem.consolidate, sem.fingerprint。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1052)。

### `tests/test_smoke.py::test_llm_consolidate_payload_event_and_fallbacks.fake`

- 功能：测试场景/夹具/假实现：test_llm_consolidate_payload_event_and_fallbacks.fake；输入输出见本项，生产不调用
- 输入：`sys_prompt, user`。
- 输出：`未注解；' 当前状态：A 已完成，B 进行中 '`。
- 作用：调用 seen.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1058)。

### `tests/test_smoke.py::test_llm_consolidate_payload_event_and_fallbacks.boom`

- 功能：测试场景/夹具/假实现：test_llm_consolidate_payload_event_and_fallbacks.boom；输入输出见本项，生产不调用
- 输入：`s, u`。
- 输出：`未注解；None`。
- 作用：调用 ZhipuChatError。
- 错误：异常 ZhipuChatError('HTTP 500')。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1090)。

### `tests/test_smoke.py::test_llm_semantics_passes_api_key_to_chat`

- 功能：行为断言：llm_semantics_passes_api_key_to_chat；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 calls.clear, len, llm_sem.LLMSemantics, monkeypatch.setattr, sem.relevant_set, sem2.relevant_set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1100)。

### `tests/test_smoke.py::test_llm_semantics_passes_api_key_to_chat.fake_chat`

- 功能：测试场景/夹具/假实现：test_llm_semantics_passes_api_key_to_chat.fake_chat；输入输出见本项，生产不调用
- 输入：`**kwargs`。
- 输出：`未注解；'1'`。
- 作用：调用 calls.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1104)。

### `tests/test_smoke.py::test_event_scene_threads_to_memory`

- 功能：行为断言：event_scene_threads_to_memory；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Event, eng.observe, make。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1128)。

### `tests/test_smoke.py::test_consolidation_scene_groups_no_cross_budget`

- 功能：行为断言：consolidation_scene_groups_no_cross_budget；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, eng.observe, eng.step, make, worker.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1136)。

### `tests/test_smoke.py::test_consolidation_ready_scene_only`

- 功能：行为断言：consolidation_ready_scene_only；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, eng.mems.values, eng.observe, eng.step, make, next, worker.process, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1154)。

### `tests/test_smoke.py::test_consolidation_picks_most_recent_scene_first`

- 功能：行为断言：consolidation_picks_most_recent_scene_first；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, eng.observe, eng.step, make, worker.process, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1176)。

### `tests/test_smoke.py::test_consolidation_none_defers_signature_no_starvation`

- 功能：行为断言：consolidation_none_defers_signature_no_starvation；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, SignalWorker, _Consolidatable, eng.observe, eng.step, frozenset, len, make, sorted, worker.process, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1201)。

### `tests/test_smoke.py::test_consolidation_callback_error_contained`

- 功能：行为断言：consolidation_callback_error_contained；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, RuntimeError, SignalWorker, _Consolidatable, eng.drain_signals, eng.observe, eng.step, frozenset, make, worker.process。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1241)。

### `tests/test_smoke.py::test_consolidation_novelty_ignores_hidden_members`

- 功能：行为断言：consolidation_novelty_ignores_hidden_members；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Memory, SignalWorker, SignalWorker(eng, sem).process, _Consolidatable, _stub_engine, eng.mems.values, eng.observe, eng.step, next, np.array, world.spawn。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1259)。

### `tests/test_smoke.py::test_lexical_channel_surfaces_token_match`

- 功能：行为断言：lexical_channel_surfaces_token_match；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, _stub_engine, eng.mems[0].emb.copy, eng.observe, eng.retrieve, eng2.observe, eng2.retrieve, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1281)。

### `tests/test_smoke.py::test_feedback_double_credit_raises`

- 功能：行为断言：feedback_double_credit_raises；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.vec_for, eng.feedback, eng.observe, eng.retrieve, make, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1307)。

### `tests/test_smoke.py::test_feedback_without_defer_credit_raises`

- 功能：行为断言：feedback_without_defer_credit_raises；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Query, emb.vec_for, eng.feedback, eng.observe, eng.retrieve, make, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1320)。

### `tests/test_smoke.py::test_ingest_dedup_ignores_hidden_members`

- 功能：行为断言：ingest_dedup_ignores_hidden_members；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Event, Memory, _stub_engine, eng.observe, len, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1333)。

### `tests/test_smoke.py::test_lex_scores_skip_hidden_members`

- 功能：行为断言：lex_scores_skip_hidden_members；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, Query, _stub_engine, eng.retrieve, monkeypatch.setattr, np.array。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1348)。

### `tests/test_smoke.py::test_lex_scores_skip_hidden_members.spy`

- 功能：测试场景/夹具/假实现：test_lex_scores_skip_hidden_members.spy；输入输出见本项，生产不调用
- 输入：`query, texts`。
- 输出：`未注解；score(query, texts)`。
- 作用：调用 captured.append, score。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1361)。

### `tests/test_smoke.py::test_consolidation_pending_pruned_without_callback`

- 功能：行为断言：consolidation_pending_pruned_without_callback；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, _stub_engine, eng._consolidation_pending.update, maybe_consolidate, np.array, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_smoke.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_smoke.py#L1371)。

## `tests/test_snapshot_format.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_snapshot_format.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`b3eda0e115d0f84f7cb70a4621de7559f35b4e7c064e9d3189f2ce2a13a01eae`。

### `tests/test_snapshot_format.py::_ByName`

- 功能：测试场景/夹具/假实现：_ByName；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L11)。

### `tests/test_snapshot_format.py::_ByName.__init__`

- 功能：测试场景/夹具/假实现：_ByName.__init__；输入输出见本项，生产不调用
- 输入：`self, cls, name`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L12)。

### `tests/test_snapshot_format.py::_ByName.__reduce__`

- 功能：测试场景/夹具/假实现：_ByName.__reduce__；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`未注解；(getattr, (self.cls, self.name))`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L15)。

### `tests/test_snapshot_format.py::_ByValue`

- 功能：测试场景/夹具/假实现：_ByValue；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L19)。

### `tests/test_snapshot_format.py::_ByValue.__init__`

- 功能：测试场景/夹具/假实现：_ByValue.__init__；输入输出见本项，生产不调用
- 输入：`self, value`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L20)。

### `tests/test_snapshot_format.py::_ByValue.__reduce__`

- 功能：测试场景/夹具/假实现：_ByValue.__reduce__；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`未注解；(Pool, (self.value,))`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L23)。

### `tests/test_snapshot_format.py::test_pool_writes_stable_value_encoding`

- 功能：行为断言：pool_writes_stable_value_encoding；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`protocol, member`。
- 输出：`未注解；None`。
- 作用：调用 _RestrictedUnpickler, _RestrictedUnpickler(io.BytesIO(data)).load, io.BytesIO, list, pickle.dumps, pytest.mark.parametrize。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L29)。

### `tests/test_snapshot_format.py::test_legacy_pool_name_and_value_encodings_are_readable`

- 功能：行为断言：legacy_pool_name_and_value_encodings_are_readable；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`member`。
- 输出：`未注解；None`。
- 作用：调用 _ByName, _ByValue, _RestrictedUnpickler, _RestrictedUnpickler(io.BytesIO(data)).load, io.BytesIO, list, pickle.dumps, pytest.mark.parametrize。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L36)。

### `tests/test_snapshot_format.py::test_legacy_getattr_adapter_rejects_non_pool_member_access`

- 功能：行为断言：legacy_getattr_adapter_rejects_non_pool_member_access；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`cls, name`。
- 输出：`未注解；None`。
- 作用：调用 _ByName, _RestrictedUnpickler, _RestrictedUnpickler(io.BytesIO(data)).load, io.BytesIO, pickle.dumps, pytest.mark.parametrize, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L46)。

### `tests/test_snapshot_format.py::test_legacy_niche_field_loads_but_does_not_bypass_suppression`

- 功能：行为断言：legacy_niche_field_loads_but_does_not_bypass_suppression；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, MemoryEngine, Query, RealChatSemantics, _RestrictedUnpickler, _RestrictedUnpickler(io.BytesIO(pickle.dumps(mems, protocol=4))).load, engine.retrieve, io.BytesIO, np.array, pickle.dumps, range, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_snapshot_format.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_snapshot_format.py#L52)。

## `tests/test_triggers.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_triggers.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`86118d6896fb436ed2b900d4863b6334d4a6d7a4c76105547f552695581d4eb3`。

### `tests/test_triggers.py::test_correction_positive`

- 功能：行为断言：correction_positive；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`text`。
- 输出：`未注解；None`。
- 作用：调用 is_correction, pytest.mark.parametrize。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_triggers.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_triggers.py#L18)。

### `tests/test_triggers.py::test_correction_negative`

- 功能：行为断言：correction_negative；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`text`。
- 输出：`未注解；None`。
- 作用：调用 is_correction, pytest.mark.parametrize。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_triggers.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_triggers.py#L28)。

### `tests/test_triggers.py::test_scan_unit_reasons`

- 功能：行为断言：scan_unit_reasons；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 scan_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_triggers.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_triggers.py#L32)。

### `tests/test_triggers.py::test_scan_unit_chitchat_is_empty`

- 功能：行为断言：scan_unit_chitchat_is_empty；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 scan_unit。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_triggers.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_triggers.py#L40)。

## `tests/test_trio_protocol.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_trio_protocol.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`f7aa8e211f69d595d281e2df558954997ddf9d93666b51931966fece704a94d7`。

### `tests/test_trio_protocol.py::drain`

- 功能：测试场景/夹具/假实现：drain；输入输出见本项，生产不调用
- 输入：`worker, n=6`。
- 输出：`未注解；None`。
- 作用：调用 range, worker.process_once。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L11)。

### `tests/test_trio_protocol.py::test_hauler_selector_create_exist_and_overlapping_window`

- 功能：行为断言：hauler_selector_create_exist_and_overlapping_window；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, len, svc.log.close, svc.observe, svc.tasks.close, svc.tasks.list_tasks, worker.process_once。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L17)。

### `tests/test_trio_protocol.py::test_hauler_selector_create_exist_and_overlapping_window.fake`

- 功能：测试场景/夹具/假实现：test_hauler_selector_create_exist_and_overlapping_window.fake；输入输出见本项，生产不调用
- 输入：`name, payload`。
- 输出：`未注解；{'candidates': [{'text': '项目统一使用 bun 工具', 'source_unit_ids': [payload['unit_id']]}]}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE'}]}；{'decisions': [{'candidate_index': 0, 'action': 'EXIST', 'target_id': 0}]}`。
- 作用：调用 calls.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L22)。

### `tests/test_trio_protocol.py::test_reviewer_writes_rules_for_later_agent_inputs`

- 功能：行为断言：reviewer_writes_rules_for_later_agent_inputs；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, any, drain, svc.log.close, svc.observe, svc.tasks.close, svc.tasks.rules_for。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L58)。

### `tests/test_trio_protocol.py::test_reviewer_writes_rules_for_later_agent_inputs.fake`

- 功能：测试场景/夹具/假实现：test_reviewer_writes_rules_for_later_agent_inputs.fake；输入输出见本项，生产不调用
- 输入：`name, payload`。
- 输出：`未注解；{'candidates': []}；{'diagnosis': 'hauler overlooked an explicit decision', 'rules': [{'target': 'hauler', 'instruction': 'Pay attention to explicit user decisions.'}], 'repair_candidates': []}`。
- 作用：调用 AssertionError, seen.append。
- 错误：异常 AssertionError(name)。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L63)。

### `tests/test_trio_protocol.py::test_opencode_runner_parses_json_stream_and_rejects_missing_cli`

- 功能：行为断言：opencode_runner_parses_json_stream_and_rejects_missing_cli；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 OpenCodeRunner, monkeypatch.setattr, pytest.raises, runner。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L87)。

### `tests/test_trio_protocol.py::test_opencode_runner_parses_json_stream_and_rejects_missing_cli.Result`

- 功能：测试场景/夹具/假实现：test_opencode_runner_parses_json_stream_and_rejects_missing_cli.Result；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L91)。

### `tests/test_trio_protocol.py::test_opencode_runner_parses_json_stream_and_rejects_missing_cli.run`

- 功能：测试场景/夹具/假实现：test_opencode_runner_parses_json_stream_and_rejects_missing_cli.run；输入输出见本项，生产不调用
- 输入：`cmd, **kwargs`。
- 输出：`未注解；Result()`。
- 作用：调用 Result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L96)。

### `tests/test_trio_protocol.py::test_stored_agent_result_survives_restart_without_rerunning_model`

- 功能：行为断言：stored_agent_result_survives_restart_without_rerunning_model；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, fake, fresh.log.close, fresh.tasks.close, fresh.tasks.list_tasks, len, svc.log.close, svc.observe, svc.tasks.claim, svc.tasks.close, svc.tasks.list_tasks, svc.tasks.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L104)。

### `tests/test_trio_protocol.py::test_stored_agent_result_survives_restart_without_rerunning_model.fake`

- 功能：测试场景/夹具/假实现：test_stored_agent_result_survives_restart_without_rerunning_model.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': [{'text': '项目统一使用 bun 工具', 'source_unit_ids': [p['unit_id']]}]}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE'}]}`。
- 作用：调用 calls.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L109)。

### `tests/test_trio_protocol.py::test_bad_reviewer_source_does_not_install_rule_or_handoff`

- 功能：行为断言：bad_reviewer_source_does_not_install_rule_or_handoff；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, DispatchWorker(svc, fake).process_once, _svc, any, svc.log.close, svc.observe, svc.tasks.close, svc.tasks.list_tasks, svc.tasks.rules_for。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L136)。

### `tests/test_trio_protocol.py::test_bad_reviewer_source_does_not_install_rule_or_handoff.fake`

- 功能：测试场景/夹具/假实现：test_bad_reviewer_source_does_not_install_rule_or_handoff.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': []}；{'rules': [{'target': 'selector', 'instruction': 'unsafe instruction'}], 'repair_candidates': [{'text': 'fake', 'source_unit_ids': [999]}]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L140)。

### `tests/test_trio_protocol.py::test_exact_duplicate_create_cannot_inflate_overlapping_source`

- 功能：行为断言：exact_duplicate_create_cannot_inflate_overlapping_source；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, len, svc.log.close, svc.observe, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L156)。

### `tests/test_trio_protocol.py::test_exact_duplicate_create_cannot_inflate_overlapping_source.fake`

- 功能：测试场景/夹具/假实现：test_exact_duplicate_create_cannot_inflate_overlapping_source.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': [{'text': '项目统一使用 bun 工具', 'source_unit_ids': [0]}]}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE'}]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L159)。

### `tests/test_trio_protocol.py::test_reviewer_sees_committed_handoffs_and_captured_prior_retrieval`

- 功能：行为断言：reviewer_sees_committed_handoffs_and_captured_prior_retrieval；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, len, next, svc.feedback, svc.log.close, svc.observe, svc.recall, svc.tasks.close, triggers.is_correction, triggers.is_dissatisfaction。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L176)。

### `tests/test_trio_protocol.py::test_reviewer_sees_committed_handoffs_and_captured_prior_retrieval.fake`

- 功能：测试场景/夹具/假实现：test_reviewer_sees_committed_handoffs_and_captured_prior_retrieval.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': [{'text': '端口现在是 8080', 'source_unit_ids': [0]}] if p['unit_id'] == 0 else []}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE'}]}；{'diagnosis': 'not enough evidence to blame extraction', 'rules': [], 'repair_candidates': []}`。
- 作用：调用 seen.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L185)。

### `tests/test_trio_protocol.py::test_scoped_rule_usage_is_audited_and_human_can_disable_it`

- 功能：行为断言：scoped_rule_usage_is_audited_and_human_can_disable_it；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, svc.log.close, svc.observe, svc.tasks.close, svc.tasks.disable_rule, svc.tasks.rule_report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L215)。

### `tests/test_trio_protocol.py::test_scoped_rule_usage_is_audited_and_human_can_disable_it.fake`

- 功能：测试场景/夹具/假实现：test_scoped_rule_usage_is_audited_and_human_can_disable_it.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': []}；{'diagnosis': 'a missed port rule', 'rules': [{'target': 'hauler', 'scope': 'entity:8080', 'instruction': 'Check explicit port decisions.'}], 'repair_candidates': []}`。
- 作用：调用 seen.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L220)。

### `tests/test_trio_protocol.py::test_reviewer_does_not_confuse_late_hauler_completion_with_prior_decision`

- 功能：行为断言：reviewer_does_not_confuse_late_hauler_completion_with_prior_decision；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, next, svc.log.close, svc.observe, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L251)。

### `tests/test_trio_protocol.py::test_reviewer_does_not_confuse_late_hauler_completion_with_prior_decision.fake`

- 功能：测试场景/夹具/假实现：test_reviewer_does_not_confuse_late_hauler_completion_with_prior_decision.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': []}；{'diagnosis': 'pending extraction at complaint', 'rules': [], 'repair_candidates': []}`。
- 作用：调用 seen.append。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L256)。

### `tests/test_trio_protocol.py::test_direct_agent_mutations_denied_in_trio_http_mode`

- 功能：行为断言：direct_agent_mutations_denied_in_trio_http_mode；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 Request, _svc, httpd.server_close, httpd.shutdown, pytest.raises, serve, svc.log.close, svc.tasks.close, thread.join, thread.start, threading.Thread, urlopen。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L275)。

### `tests/test_trio_protocol.py::test_existing_agent_rules_table_is_migrated_without_disabling_rules`

- 功能：行为断言：existing_agent_rules_table_is_migrated_without_disabling_rules；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, conn.close, conn.commit, conn.execute, sqlite3.connect, store.close, store.disable_rule, store.rule_snapshot。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L302)。

### `tests/test_trio_protocol.py::test_reviewer_can_assess_used_rule_and_atomically_roll_it_back`

- 功能：行为断言：reviewer_can_assess_used_rule_and_atomically_roll_it_back；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, svc.log.close, svc.observe, svc.tasks._conn.execute, svc.tasks._conn.execute('SELECT assessment FROM agent_rule_feedback WHERE rule_id=?', (rule['id'],))…, svc.tasks.close, svc.tasks.rule_report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L324)。

### `tests/test_trio_protocol.py::test_reviewer_can_assess_used_rule_and_atomically_roll_it_back.fake`

- 功能：测试场景/夹具/假实现：test_reviewer_can_assess_used_rule_and_atomically_roll_it_back.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': []}；{'diagnosis': 'missed a port decision', 'rules': [{'target': 'hauler', 'scope': 'entity:8080', 'instruction': 'Check port.'}], 'repair_candidates': []}；{'diagnosis': 'rule did not fix the observed complaint', 'rules': [], 'repair_candidates': [], 'rule_reviews': [{'rule_id': used[0], 'assessment': 'ineffective', 'reason': 'same omission after applying this rule'}]}`。
- 作用：调用 task.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L327)。

### `tests/test_trio_protocol.py::test_reviewer_cannot_disable_rule_not_observed_in_handoff`

- 功能：行为断言：reviewer_cannot_disable_rule_not_observed_in_handoff；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, DispatchWorker(svc, fake).process_once, _svc, svc.log.close, svc.observe, svc.tasks.close, svc.tasks.list_tasks, svc.tasks.rule_report。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L360)。

### `tests/test_trio_protocol.py::test_reviewer_cannot_disable_rule_not_observed_in_handoff.fake`

- 功能：测试场景/夹具/假实现：test_reviewer_cannot_disable_rule_not_observed_in_handoff.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': []}；{'diagnosis': 'guess', 'rules': [], 'repair_candidates': [], 'rule_reviews': [{'rule_id': 123, 'assessment': 'ineffective', 'reason': 'not observed'}]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L364)。

### `tests/test_trio_protocol.py::test_archived_equivalent_is_reactivated_not_duplicated`

- 功能：行为断言：archived_equivalent_is_reactivated_not_duplicated；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 DispatchWorker, _svc, drain, len, svc.log.close, svc.observe, svc.tasks.close。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L379)。

### `tests/test_trio_protocol.py::test_archived_equivalent_is_reactivated_not_duplicated.fake`

- 功能：测试场景/夹具/假实现：test_archived_equivalent_is_reactivated_not_duplicated.fake；输入输出见本项，生产不调用
- 输入：`name, p`。
- 输出：`未注解；{'candidates': [{'text': '项目统一使用 bun 工具', 'source_unit_ids': [p['unit_id']]}]}；{'decisions': [{'candidate_index': 0, 'action': 'CREATE'}]}`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L383)。

### `tests/test_trio_protocol.py::test_workflow_attempt_bound_matches_policy`

- 功能：H8 锁死：agents 侧 MAX_ATTEMPTS 与 KindPolicy 同值。
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_trio_protocol.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_trio_protocol.py#L404)。

## `tests/test_zhipu_embedder.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/test_zhipu_embedder.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`0034aa0a3774c432e7fe04ec553c4094533dfe2c656b1f7bd4d0947fac01de53`。

### `tests/test_zhipu_embedder.py::one_hot`

- 功能：测试场景/夹具/假实现：one_hot；输入输出见本项，生产不调用
- 输入：`pos: int, dims: int, scale: float=1.0`。
- 输出：`list[float]；vec`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L19)。

### `tests/test_zhipu_embedder.py::respond`

- 功能：测试场景/夹具/假实现：respond；输入输出见本项，生产不调用
- 输入：`request, vectors`。
- 输出：`bytes；json.dumps({'data': data, 'usage': {'prompt_tokens': len(payload['input'])}}).encode('utf-8')`。
- 作用：调用 enumerate, json.dumps, json.dumps({'data': data, 'usage': {'prompt_tokens': len(payload['input'])}}).encode, json.loads, len, request.data.decode, vectors。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L25)。

### `tests/test_zhipu_embedder.py::expect`

- 功能：测试场景/夹具/假实现：expect；输入输出见本项，生产不调用
- 输入：`exc_type, fn, contains: str=''`。
- 输出：`None；None`。
- 作用：调用 AssertionError, fn, str。
- 错误：异常 AssertionError(f'expected {exc_type.__name__}')。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L35)。

### `tests/test_zhipu_embedder.py::test_missing_key_fails_without_transport`

- 功能：行为断言：missing_key_fails_without_transport；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 expect, patch.dict。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L44)。

### `tests/test_zhipu_embedder.py::test_response_order_normalization_and_batching`

- 功能：行为断言：response_order_normalization_and_batching；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ZhipuEmbedder, emb.embed, enumerate, np.allclose, np.count_nonzero, np.linalg.norm。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L49)。

### `tests/test_zhipu_embedder.py::test_response_order_normalization_and_batching.post`

- 功能：测试场景/夹具/假实现：test_response_order_normalization_and_batching.post；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；json.dumps({'data': data, 'usage': {'prompt_tokens': 7}}).encode('utf-8')`。
- 作用：调用 calls.append, data.reverse, enumerate, json.dumps, json.dumps({'data': data, 'usage': {'prompt_tokens': 7}}).encode, json.loads, len, one_hot, request.data.decode, texts.index。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L53)。

### `tests/test_zhipu_embedder.py::test_chunk_weighted_merge`

- 功能：行为断言：chunk_weighted_merge；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ZhipuEmbedder, abs, emb.embed, math.sqrt。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L74)。

### `tests/test_zhipu_embedder.py::test_chunk_weighted_merge.post`

- 功能：测试场景/夹具/假实现：test_chunk_weighted_merge.post；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；respond(request, lambda text, dims: one_hot(0 if text == 'abc' else 1, dims))`。
- 作用：调用 respond。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L75)。

### `tests/test_zhipu_embedder.py::test_sqlite_cache_avoids_second_request`

- 功能：行为断言：sqlite_cache_avoids_second_request；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Path, SqliteEmbeddingCache, ZhipuEmbedder, conn.close, conn.execute, conn.execute('SELECT COUNT(*) FROM embeddings').fetchone, expect, first.embed, np.array_equal, second.embed, sqlite3.connect, str, tempfile.TemporaryDirectory。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L87)。

### `tests/test_zhipu_embedder.py::test_sqlite_cache_avoids_second_request.post`

- 功能：测试场景/夹具/假实现：test_sqlite_cache_avoids_second_request.post；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；respond(request, lambda text, dims: one_hot(0, dims))`。
- 作用：调用 calls.append, respond。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L92)。

### `tests/test_zhipu_embedder.py::test_invalid_response_rejected`

- 功能：行为断言：invalid_response_rejected；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ZhipuEmbedder, expect。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L120)。

### `tests/test_zhipu_embedder.py::test_invalid_response_rejected.post`

- 功能：测试场景/夹具/假实现：test_invalid_response_rejected.post；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；json.dumps({'data': data}).encode('utf-8')`。
- 作用：调用 json.dumps, json.dumps({'data': data}).encode, json.loads, one_hot, request.data.decode。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L121)。

### `tests/test_zhipu_embedder.py::test_retry_only_retryable_http_statuses`

- 功能：行为断言：retry_only_retryable_http_statuses；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 ZhipuEmbedder, ZhipuEmbedder(dimensions=256, max_retries=1, http_post=retry_post).embed, expect, patch。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L132)。

### `tests/test_zhipu_embedder.py::test_retry_only_retryable_http_statuses.retry_post`

- 功能：测试场景/夹具/假实现：test_retry_only_retryable_http_statuses.retry_post；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；respond(request, lambda text, dims: one_hot(0, dims))`。
- 作用：调用 HTTPError, len, respond, retry_calls.append。
- 错误：异常 HTTPError(request.full_url, 429, 'rate limit', None, None)。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L135)。

### `tests/test_zhipu_embedder.py::test_retry_only_retryable_http_statuses.bad_post`

- 功能：测试场景/夹具/假实现：test_retry_only_retryable_http_statuses.bad_post；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；None`。
- 作用：调用 HTTPError, bad_calls.append。
- 错误：异常 HTTPError(request.full_url, 400, 'bad request', None, None)。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L149)。

### `tests/test_zhipu_embedder.py::test_chat_retries_remote_disconnected`

- 功能：行为断言：chat_retries_remote_disconnected；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 calls.clear, chat, expect, patch。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L158)。

### `tests/test_zhipu_embedder.py::test_chat_retries_remote_disconnected.Resp`

- 功能：测试场景/夹具/假实现：test_chat_retries_remote_disconnected.Resp；输入输出见本项，生产不调用
- 输入：`见显式或继承的 __init__；无新增字段`。
- 输出：`类型/实例；基类 object`。
- 作用：字段与方法契约；dataclass 自动生成的方法不另建手写符号。
- 错误：见构造函数及方法。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L161)。

### `tests/test_zhipu_embedder.py::test_chat_retries_remote_disconnected.Resp.__enter__`

- 功能：测试场景/夹具/假实现：test_chat_retries_remote_disconnected.Resp.__enter__；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`未注解；self`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L162)。

### `tests/test_zhipu_embedder.py::test_chat_retries_remote_disconnected.Resp.__exit__`

- 功能：测试场景/夹具/假实现：test_chat_retries_remote_disconnected.Resp.__exit__；输入输出见本项，生产不调用
- 输入：`self, *a`。
- 输出：`未注解；False`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L165)。

### `tests/test_zhipu_embedder.py::test_chat_retries_remote_disconnected.Resp.read`

- 功能：测试场景/夹具/假实现：test_chat_retries_remote_disconnected.Resp.read；输入输出见本项，生产不调用
- 输入：`self`。
- 输出：`未注解；json.dumps({'choices': [{'message': {'content': 'ok'}}]}).encode()`。
- 作用：调用 json.dumps, json.dumps({'choices': [{'message': {'content': 'ok'}}]}).encode。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L168)。

### `tests/test_zhipu_embedder.py::test_chat_retries_remote_disconnected.flaky`

- 功能：测试场景/夹具/假实现：test_chat_retries_remote_disconnected.flaky；输入输出见本项，生产不调用
- 输入：`request, timeout`。
- 输出：`未注解；Resp()`。
- 作用：调用 RemoteDisconnected, Resp, calls.append, len。
- 错误：异常 RemoteDisconnected('dropped')。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L174)。

### `tests/test_zhipu_embedder.py::test_extreme_embeddings_are_finite_unit_vectors_and_cancelled_chunks_fail`

- 功能：行为断言：extreme_embeddings_are_finite_unit_vectors_and_cancelled_chunks_fail；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 SqliteEmbeddingCache, ZhipuEmbedder, cache.put, emb.embed, expect, np.array, offline._cache_key, offline.embed, one_hot。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L196)。

### `tests/test_zhipu_embedder.py::test_malformed_chat_response_uses_transport_error_contract`

- 功能：行为断言：malformed_chat_response_uses_transport_error_contract；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 BytesIO, expect, json.dumps, json.dumps({'choices': [{'message': {'content': content}}]}).encode, patch。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L210)。

### `tests/test_zhipu_embedder.py::test_invalid_chat_cache_is_miss_and_failed_replace_keeps_previous`

- 功能：行为断言：invalid_chat_cache_is_miss_and_failed_replace_keeps_previous；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / 'key.json').write_text, list, llm._cache_lookup, llm._cache_store, monkeypatch.setattr, pytest.raises, tmp_path.glob。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L219)。

### `tests/test_zhipu_embedder.py::test_invalid_chat_cache_is_miss_and_failed_replace_keeps_previous.fail`

- 功能：测试场景/夹具/假实现：test_invalid_chat_cache_is_miss_and_failed_replace_keeps_previous.fail；输入输出见本项，生产不调用
- 输入：`*_`。
- 输出：`未注解；None`。
- 作用：调用 OSError。
- 错误：异常 OSError('replace failed')。
- 目标：`tests/test_zhipu_embedder.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/test_zhipu_embedder.py#L226)。

## `tests/unit/test_config.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/unit/test_config.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`279c8ebcb3842f9a3a71f59f683ace517797153c1e27bd4ba86738f5716fc2c2`。

### `tests/unit/test_config.py::test_pool_caps_default`

- 功能：行为断言：pool_caps_default；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L10)。

### `tests/unit/test_config.py::test_settings_defaults_and_state_dir`

- 功能：行为断言：settings_defaults_and_state_dir；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Settings, resolve_settings。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L14)。

### `tests/unit/test_config.py::test_resolve_pipeline_matrix`

- 功能：行为断言：resolve_pipeline_matrix；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 resolve_pipeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L21)。

### `tests/unit/test_config.py::test_cli_beats_env_beats_default`

- 功能：行为断言：cli_beats_env_beats_default；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 resolve_settings。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L29)。

### `tests/unit/test_config.py::test_no_agent_flag_and_env`

- 功能：行为断言：no_agent_flag_and_env；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 resolve_settings。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L41)。

### `tests/unit/test_config.py::test_invalid_values_raise`

- 功能：行为断言：invalid_values_raise；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 pytest.raises, resolve_settings。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L47)。

### `tests/unit/test_config.py::test_load_env_key_prefers_process_env`

- 功能：行为断言：load_env_key_prefers_process_env；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 load_env_key, monkeypatch.setenv。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L56)。

### `tests/unit/test_config.py::test_load_env_key_reads_project_dotenv`

- 功能：行为断言：load_env_key_reads_project_dotenv；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 (tmp_path / '.env').write_text, load_env_key, monkeypatch.delenv。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L61)。

### `tests/unit/test_config.py::test_load_env_key_missing_is_none`

- 功能：行为断言：load_env_key_missing_is_none；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path, monkeypatch`。
- 输出：`未注解；None`。
- 作用：调用 load_env_key, monkeypatch.delenv, monkeypatch.setattr, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_config.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_config.py#L67)。

## `tests/unit/test_defects_regression.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/unit/test_defects_regression.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`42707db14d73a5eccdcebe8c99379b5d712d999a72de5a804c9ed496d1479292`。

### `tests/unit/test_defects_regression.py::test_plan_capacity_under_limit`

- 功能：行为断言：plan_capacity_under_limit；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, dynamics.plan_capacity, np.zeros, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L36)。

### `tests/unit/test_defects_regression.py::test_plan_capacity_eviction_and_pin_protection`

- 功能：行为断言：plan_capacity_eviction_and_pin_protection；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, dynamics.plan_capacity, np.zeros, set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L49)。

### `tests/unit/test_defects_regression.py::test_plan_capacity_all_pinned_backpressure`

- 功能：行为断言：plan_capacity_all_pinned_backpressure；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Cfg, Memory, dynamics.plan_capacity, np.zeros。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L67)。

### `tests/unit/test_defects_regression.py::test_require_batch_size_guard`

- 功能：行为断言：require_batch_size_guard；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 pytest.raises, require_batch_size。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L79)。

### `tests/unit/test_defects_regression.py::test_semantics_provider_health_and_calls`

- 功能：行为断言：semantics_provider_health_and_calls；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 SemanticsProvider, provider.health, provider.relevant_set。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L86)。

### `tests/unit/test_defects_regression.py::test_task_store_call_context_and_fencing`

- 功能：行为断言：task_store_call_context_and_fencing；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, pytest.raises, store.claim, store.close, store.enqueue, store.store_call_context。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L98)。

### `tests/unit/test_defects_regression.py::test_evidence_and_llm_shims`

- 功能：行为断言：evidence_and_llm_shims；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 无外部调用。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L120)。

### `tests/unit/test_defects_regression.py::test_policy_consumers_registration`

- 功能：行为断言：policy_consumers_registration；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 effects.EFFECTS.items, policy.assert_consumers。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L132)。

### `tests/unit/test_defects_regression.py::test_resolve_pipeline_matrix_behavior`

- 功能：行为断言：resolve_pipeline_matrix_behavior；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 resolve_pipeline。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_defects_regression.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_defects_regression.py#L138)。

## `tests/unit/test_errors.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/unit/test_errors.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`57461237341488bd857a51c37ee95dd1eaae25e198cb9d59be00636334c54735`。

### `tests/unit/test_errors.py::test_hierarchy_and_attrs`

- 功能：行为断言：hierarchy_and_attrs；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 Degraded, Rejected, issubclass, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_errors.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_errors.py#L10)。

### `tests/unit/test_errors.py::test_http_status_table_covers_current_behavior`

- 功能：行为断言：http_status_table_covers_current_behavior；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 http_status。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_errors.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_errors.py#L20)。

### `tests/unit/test_errors.py::test_unknown_code_is_loud`

- 功能：行为断言：unknown_code_is_loud；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 http_status, pytest.raises。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_errors.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_errors.py#L34)。

## `tests/unit/test_import_boundaries.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/unit/test_import_boundaries.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`31fed82e0c93fc32098866a03b3b84fbbc84b43fe4be7a10b103f36898caabdf`。
- 模块备注：NUMPY_OK_IN 死常量删除；保留 import 边界断言。

### `tests/unit/test_import_boundaries.py::_dotted`

- 功能：测试场景/夹具/假实现：_dotted；输入输出见本项，生产不调用
- 输入：`path: Path, repo_root: Path`。
- 输出：`str；'.'.join(parts)`。
- 作用：调用 '.'.join, list, parts.pop, path.relative_to, path.relative_to(repo_root).with_suffix。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L39)。

### `tests/unit/test_import_boundaries.py::_resolve_from`

- 功能：ImportFrom 节点 → 绝对虚点名。level=0 是绝对导入，直接记模块名； 相对导入则 package 上溯 level-1 层再接 name/alias。
- 输入：`mod_dotted: str, level: int, name: str | None, alias: str`。
- 输出：`str；'.'.join(base + [alias])；'.'.join(base + name.split('.'))；f'{PKG}.{alias}' if alias != '*' else PKG；name or alias`。
- 作用：调用 '.'.join, len, mod_dotted.split, name.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L47)。

### `tests/unit/test_import_boundaries.py::_imports_of`

- 功能：测试场景/夹具/假实现：_imports_of；输入输出见本项，生产不调用
- 输入：`path: Path, repo_root: Path`。
- 输出：`set[str]；{i for i in out if i} - ALWAYS_OK`。
- 作用：调用 _dotted, _resolve_from, ast.parse, ast.walk, isinstance, out.add, out.update, path.read_text, set, str。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L63)。

### `tests/unit/test_import_boundaries.py::_is_stdlib`

- 功能：测试场景/夹具/假实现：_is_stdlib；输入输出见本项，生产不调用
- 输入：`dotted: str`。
- 输出：`bool；dotted.split('.')[0] in sys.stdlib_module_names`。
- 作用：调用 dotted.split。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L79)。

### `tests/unit/test_import_boundaries.py::_hm_files`

- 功能：测试场景/夹具/假实现：_hm_files；输入输出见本项，生产不调用
- 输入：`repo_root: Path, *sub: str`。
- 输出：`未注解；生成器/上下文管理器`。
- 作用：调用 p.is_file, p.rglob, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L83)。

### `tests/unit/test_import_boundaries.py::test_foundation_is_leaf`

- 功能：config/errors/telemetry 只用标准库（地基层，不碰任何包）。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 _hm_files, _imports_of, _is_stdlib, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L96)。

### `tests/unit/test_import_boundaries.py::test_core_no_upward_imports`

- 功能：core/ 永不 import 上层（eternal guard；比终态规则弱，但 P2 即生效）。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 _hm_files, _imports_of, i.split, i.startswith, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L107)。

### `tests/unit/test_import_boundaries.py::test_guards_foundation_only`

- 功能：guards/* 只用标准库 + errors/config + core（横切层，不碰服务层）。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 _hm_files, _imports_of, _is_stdlib, i.startswith, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L119)。

### `tests/unit/test_import_boundaries.py::test_new_shells_import_cleanly`

- 功能：P2 准出：新模块 import 无环、无 ImportError。
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 importlib.import_module。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L133)。

### `tests/unit/test_import_boundaries.py::test_core_zero_cross_layer`

- 功能：终态 core/ 只用标准库 + numpy + core + config/errors（I1 字面）。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 _hm_files, _imports_of, _is_stdlib, i.split, i.startswith, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L142)。

### `tests/unit/test_import_boundaries.py::test_pipeline_single_reader`

- 功能：I2：MEMORY_PIPELINE 只在 config.resolve_pipeline 被读。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 (repo_root / PKG).rglob, bad.append, enumerate, f.read_text, f.read_text(encoding='utf-8').splitlines, f.relative_to, pat.search, re.compile, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L159)。

### `tests/unit/test_import_boundaries.py::test_server_is_thin_shim`

- 功能：终态 server.py 是薄 shim（≤10 行，只引 service/transport）。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 _imports_of, f.read_text, f.read_text(encoding='utf-8').splitlines, i.startswith, len, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L173)。

### `tests/unit/test_import_boundaries.py::test_agents_boundaries`

- 功能：终态 agents/ 存在且不碰 store/（I1）。
- 输入：`repo_root`。
- 输出：`未注解；None`。
- 作用：调用 _imports_of, agents.is_dir, agents.rglob, i.startswith, sorted。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_import_boundaries.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_import_boundaries.py#L184)。

## `tests/unit/test_store_tasks.py`

- 模块功能：行为、恢复、权限及协议回归；不得按产品死代码删除。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/unit/test_store_tasks.py`（当前路径）。
- 模块输入：被测对象与 pytest 夹具。
- 模块输出：通过/失败断言与恢复、权限、协议证据；验收资产，删除须有替代断言。
- 源校验：`310ae7043cf846b44114f1f069c3157582be605d77c416ca4d6739ca2d3012f0`。

### `tests/unit/test_store_tasks.py::_claim`

- 功能：测试场景/夹具/假实现：_claim；输入输出见本项，生产不调用
- 输入：`store, task_id, **overrides`。
- 输出：`未注解；store.claim(task_id, **args)`。
- 作用：调用 args.update, dict, store.claim, store.get。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L10)。

### `tests/unit/test_store_tasks.py::test_parallel_connections_only_one_claim_and_one_daily_charge`

- 功能：行为断言：parallel_connections_only_one_claim_and_one_daily_charge；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`tmp_path`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, ThreadPoolExecutor, list, pool.map, range, store.close, stores[0].enqueue, stores[0].runs_today, sum, threading.Barrier。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L18)。

### `tests/unit/test_store_tasks.py::test_parallel_connections_only_one_claim_and_one_daily_charge.claim`

- 功能：测试场景/夹具/假实现：test_parallel_connections_only_one_claim_and_one_daily_charge.claim；输入输出见本项，生产不调用
- 输入：`i`。
- 输出：`未注解；_claim(stores[i], tid)`。
- 作用：调用 _claim, barrier.wait。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L23)。

### `tests/unit/test_store_tasks.py::test_stale_claim_token_cannot_store_result_or_finish`

- 功能：行为断言：stale_claim_token_cannot_store_result_or_finish；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, _claim, pytest.raises, store.enqueue, store.finish, store.get, store.recover_expired, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L37)。

### `tests/unit/test_store_tasks.py::test_stale_checkpoint_cannot_overwrite_or_consume_daily_allowance`

- 功能：行为断言：stale_checkpoint_cannot_overwrite_or_consume_daily_allowance；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, _claim, pytest.raises, store.checkpoint, store.enqueue, store.get, store.runs_today, store.save_checkpoint。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L54)。

### `tests/unit/test_store_tasks.py::test_merged_payload_version_must_match_claim_bound`

- 功能：行为断言：merged_payload_version_must_match_claim_bound；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, _claim, store.enqueue, store.get, store.runs_today。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L65)。

### `tests/unit/test_store_tasks.py::test_capacity_rejects_instead_of_evicting_accepted_task`

- 功能：行为断言：capacity_rejects_instead_of_evicting_accepted_task；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, len, pytest.raises, store.enqueue, store.get, store.list_tasks。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L75)。

### `tests/unit/test_store_tasks.py::test_result_and_checkpoint_commit_together_with_revision_guard`

- 功能：行为断言：result_and_checkpoint_commit_together_with_revision_guard；成功正常返回，违约抛 AssertionError/pytest 失败
- 输入：`无参数`。
- 输出：`未注解；None`。
- 作用：调用 TaskStore, _claim, pytest.raises, store.checkpoint, store.close, store.enqueue, store.get, store.save_checkpoint, store.store_result。
- 错误：异常 无显式 raise；被调用方错误仍可传播。
- 目标：`tests/unit/test_store_tasks.py`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/unit/test_store_tasks.py#L84)。

## `.opencode/plugin/memory-bridge.ts`

- 模块功能：主会话捕获、检索、工具与可靠交付。
- 设计归属：三 Agent 协议与主会话边界；处置：保留收口。
- 目标路径：`.opencode/plugin/memory-bridge.ts`（当前路径）。
- 模块输入：OpenCode plugin context、env、会话事件与本地 token。
- 模块输出：hooks/tools/dispose、outbox 与 sidecar 生命周期；正文只经有界交付。
- 源校验：`99e8b1678e14ea940df58c1b84a6ba88ca97723de0c5884d671debf56646504a`。
- 导出/输入依赖：TS 具名 arrow/hook/tool 与参数登记；匿名映射/spy 归其父入口

### `.opencode/plugin/memory-bridge.ts::log`

- 功能：void；脱敏 stderr 诊断
- 输入：`msg: string`。
- 输出：`void；脱敏 stderr 诊断`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L41)。

### `.opencode/plugin/memory-bridge.ts::auth`

- 功能：Promise<string>；当前 token，不进入模型载荷
- 输入：`无参数`。
- 输出：`Promise<string>；当前 token，不进入模型载荷`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L49)。

### `.opencode/plugin/memory-bridge.ts::headers`

- 功能：Promise<Record<string,string>>；bearer 请求头
- 输入：`无参数`。
- 输出：`Promise<Record<string,string>>；bearer 请求头`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L53)。

### `.opencode/plugin/memory-bridge.ts::check`

- 功能：boolean；401 时关闭后续发送
- 输入：`r: Response`。
- 输出：`boolean；401 时关闭后续发送`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L57)。

### `.opencode/plugin/memory-bridge.ts::call`

- 功能：Promise<Res>；ok/status/data，传输和 JSON 失败外显
- 输入：`method: "GET" | "POST", path: string, body?: unknown, opts?: { timeoutMs?: number; requestId?: string },`。
- 输出：`Promise<Res>；ok/status/data，传输和 JSON 失败外显`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L69)。

### `.opencode/plugin/memory-bridge.ts::errText`

- 功能：string；失败状态和展示文案
- 输入：`r: Res`。
- 输出：`string；失败状态和展示文案`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L96)。

### `.opencode/plugin/memory-bridge.ts::drain`

- 功能：Promise<void>；消费子进程 pipe
- 输入：`stream: ReadableStream<Uint8Array> | undefined, tag: string`。
- 输出：`Promise<void>；消费子进程 pipe`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L111)。

### `.opencode/plugin/memory-bridge.ts::fmtHits`

- 功能：string；有界命中片段与来源
- 输入：`hits: Hit[]`。
- 输出：`string；有界命中片段与来源`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L130)。

### `.opencode/plugin/memory-bridge.ts::reportMiss`

- 功能：void；Legacy 异步缺失上报，Trio 不上报
- 输入：`query: string, hint: string`。
- 输出：`void；Legacy 异步缺失上报，Trio 不上报`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L137)。

### `.opencode/plugin/memory-bridge.ts::captureTimeout`

- 功能：number；有效 timeout 或默认 30000ms
- 输入：`无参数`。
- 输出：`number；有效 timeout 或默认 30000ms`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L324)。

### `.opencode/plugin/memory-bridge.ts::captureAttempts`

- 功能：number；有限次数或默认 3
- 输入：`无参数`。
- 输出：`number；有限次数或默认 3`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L328)。

### `.opencode/plugin/memory-bridge.ts::captureBackoff`

- 功能：number；非负毫秒或默认 200
- 输入：`无参数`。
- 输出：`number；非负毫秒或默认 200`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L332)。

### `.opencode/plugin/memory-bridge.ts::newRequestId`

- 功能：string；稳定合法 request-id
- 输入：`prefix: string`。
- 输出：`string；稳定合法 request-id`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L336)。

### `.opencode/plugin/memory-bridge.ts::isTurn`

- 功能：boolean；outbox turn 形状校验
- 输入：`value: unknown`。
- 输出：`boolean；outbox turn 形状校验`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L341)。

### `.opencode/plugin/memory-bridge.ts::retain`

- 功能：boolean；是否保留未确认或终止待查义务
- 输入：`t: CaptureTurn`。
- 输出：`boolean；是否保留未确认或终止待查义务`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L350)。

### `.opencode/plugin/memory-bridge.ts::loadOutbox`

- 功能：CaptureTurn[]；原 id 的持久交付列表
- 输入：`无参数`。
- 输出：`CaptureTurn[]；原 id 的持久交付列表`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L353)。

### `.opencode/plugin/memory-bridge.ts::persistOutbox`

- 功能：void；原子替换 outbox
- 输入：`无参数`。
- 输出：`void；原子替换 outbox`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L369)。

### `.opencode/plugin/memory-bridge.ts::schedule`

- 功能：void；串行追加 inflight 工作
- 输入：`job: () => Promise<void>`。
- 输出：`void；串行追加 inflight 工作`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L379)。

### `.opencode/plugin/memory-bridge.ts::observeAck`

- 功能：acked | retry | stop；observe 接受语义
- 输入：`r: Res`。
- 输出：`acked | retry | stop；observe 接受语义`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L382)。

### `.opencode/plugin/memory-bridge.ts::feedbackAck`

- 功能：acked | retry | stop；反馈回执语义
- 输入：`r: Res`。
- 输出：`acked | retry | stop；反馈回执语义`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L389)。

### `.opencode/plugin/memory-bridge.ts::attempt`

- 功能：Promise<{kind,res}>；有限同 id 重试结果
- 输入：`path: "/observe" | "/feedback", body: Record<string, unknown>, requestId: string, judge: (r: Res) => "acked" | "retry" | "stop"`。
- 输出：`Promise<{kind,res}>；有限同 id 重试结果`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L397)。

### `.opencode/plugin/memory-bridge.ts::deliver`

- 功能：Promise<void>；observe 确认后才 feedback，并更新 outbox
- 输入：`turn: CaptureTurn`。
- 输出：`Promise<void>；observe 确认后才 feedback，并更新 outbox`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L412)。

### `.opencode/plugin/memory-bridge.ts::flushOutbox`

- 功能：Promise<void>；顺序交付与重入合并
- 输入：`无参数`。
- 输出：`Promise<void>；顺序交付与重入合并`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L444)。

### `.opencode/plugin/memory-bridge.ts::default`

- 功能：主会话 Plugin 组装，不是后台三 Agent runner
- 输入：`context.directory；process.env；内部会话标记`。
- 输出：`Promise<Plugin>；hooks/tool/dispose 或内部会话空对象`。
- 作用：生命周期、token、本地 outbox、HTTP、会话暂存。
- 错误：按主文的 ready/auth/accepted 边界外显。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L37)。

### `.opencode/plugin/memory-bridge.ts::tools.memory_search.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`query: string`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L146)。

### `.opencode/plugin/memory-bridge.ts::tools.memory_conflicts.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`无参数`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L154)。

### `.opencode/plugin/memory-bridge.ts::tools.memory_resolve.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`left/right: number；verdict: string；entity_key?: string；服务端要求整数 id`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L166)。

### `.opencode/plugin/memory-bridge.ts::tools.log_search.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`query: string；before?: number；scene?: string；k?: number`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L186)。

### `.opencode/plugin/memory-bridge.ts::tools.log_timeline.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`entity: string；before?: number；limit?: number`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L206)。

### `.opencode/plugin/memory-bridge.ts::tools.log_stats.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`group_by: string；before?: number；limit?: number`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L223)。

### `.opencode/plugin/memory-bridge.ts::tools.log_window.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`unit_ids: number[]；max_chars?: number；服务端要求整数 id 与 ≤20 条`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L241)。

### `.opencode/plugin/memory-bridge.ts::tools.memory_propose.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`proposals: {text,kind?,salience?,source_unit_ids,entity_key?,supersedes?}[]`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L262)。

### `.opencode/plugin/memory-bridge.ts::tools.memory_diagnose.execute`

- 功能：注册工具操作；事实只读或 Legacy-only 写入，主文第 7 节逐项规定
- 输入：`miss_type: string；note?: string`。
- 输出：`Promise<string>；成功工具视图或可见错误文本`。
- 作用：调用对应 HTTP；Legacy 写工具在 Trio 隐藏且服务端再拒绝。
- 错误：Res 错误不得伪装合法空结果。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L289)。

### `.opencode/plugin/memory-bridge.ts::chat.message`

- 功能：主会话 hook/关闭入口，功能与参数逐项见主文第 7 节
- 输入：`sessionID/parts/system output/event；dispose 无参数`。
- 输出：`Promise<void>；更新捕获、注入或有界收尾`。
- 作用：会话状态、检索、outbox、HTTP 与自有进程管理。
- 错误：不捕获内部 worker；未确认回合不得静默删除。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L473)。

### `.opencode/plugin/memory-bridge.ts::experimental.chat.system.transform`

- 功能：主会话 hook/关闭入口，功能与参数逐项见主文第 7 节
- 输入：`sessionID/parts/system output/event；dispose 无参数`。
- 输出：`Promise<void>；更新捕获、注入或有界收尾`。
- 作用：会话状态、检索、outbox、HTTP 与自有进程管理。
- 错误：不捕获内部 worker；未确认回合不得静默删除。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L480)。

### `.opencode/plugin/memory-bridge.ts::event`

- 功能：主会话 hook/关闭入口，功能与参数逐项见主文第 7 节
- 输入：`sessionID/parts/system output/event；dispose 无参数`。
- 输出：`Promise<void>；更新捕获、注入或有界收尾`。
- 作用：会话状态、检索、outbox、HTTP 与自有进程管理。
- 错误：不捕获内部 worker；未确认回合不得静默删除。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L504)。

### `.opencode/plugin/memory-bridge.ts::dispose`

- 功能：主会话 hook/关闭入口，功能与参数逐项见主文第 7 节
- 输入：`sessionID/parts/system output/event；dispose 无参数`。
- 输出：`Promise<void>；更新捕获、注入或有界收尾`。
- 作用：会话状态、检索、outbox、HTTP 与自有进程管理。
- 错误：不捕获内部 worker；未确认回合不得静默删除。
- 目标：`.opencode/plugin/memory-bridge.ts`；处置：保留收口；变更：保留当前签名与 IO；[源码](../.opencode/plugin/memory-bridge.ts#L565)。

## `tests/memory_bridge.test.ts`

- 模块功能：真实插件 hooks 的 fake IO 回归。
- 设计归属：验收资产；处置：保留迁移。
- 目标路径：`tests/memory_bridge.test.ts`（当前路径）。
- 模块输入：fake HTTP/Bun/spy 与临时项目。
- 模块输出：插件行为断言；过滤用例不得冒充完整通过。
- 源校验：`63b67dd551e3ce4ab4639a944d2305bd58f1aa07614f4e0536ee5df0f77486a0`。
- 导出/输入依赖：TS 具名 arrow/hook/tool 与参数登记；匿名映射/spy 归其父入口

### `tests/memory_bridge.test.ts::hooks`

- 功能：Promise<Plugin>；测试中的 bridge 构造
- 输入：`无参数`。
- 输出：`Promise<Plugin>；测试中的 bridge 构造`。
- 作用：插件 IO/会话/交付权限见主文第 7 节；测试回调只操作 fake 边界。
- 错误：网络/JSON 错误返回 Res；文件/协议/断言错误按入口外显。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L20)。

### `tests/memory_bridge.test.ts::test:memory tools surface HTTP ${status}, not an empty result`

- 功能：插件行为断言：memory tools surface HTTP ${status}, not an empty result
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L63)。

### `tests/memory_bridge.test.ts::test:successful empty responses remain empty, not failures`

- 功能：插件行为断言：successful empty responses remain empty, not failures
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L76)。

### `tests/memory_bridge.test.ts::test:unhealthy probe ${JSON.stringify(reply)} is not readiness`

- 功能：插件行为断言：unhealthy probe ${JSON.stringify(reply)} is not readiness
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L90)。

### `tests/memory_bridge.test.ts::test:malformed successful response ${raw} is a visible failure`

- 功能：插件行为断言：malformed successful response ${raw} is a visible failure
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L103)。

### `tests/memory_bridge.test.ts::test:connection failure spawns once and waits for a healthy probe`

- 功能：插件行为断言：connection failure spawns once and waits for a healthy probe
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L109)。

### `tests/memory_bridge.test.ts::test:401 stops subsequent data transmission`

- 功能：插件行为断言：401 stops subsequent data transmission
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L123)。

### `tests/memory_bridge.test.ts::test:failed miss reports do not mark the query as successfully reported`

- 功能：插件行为断言：failed miss reports do not mark the query as successfully reported
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L131)。

### `tests/memory_bridge.test.ts::test:capture feedback requires an acknowledged observe (${status})`

- 功能：插件行为断言：capture feedback requires an acknowledged observe (${status})
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L146)。

### `tests/memory_bridge.test.ts::test:accepted 503 is delivery, not a second observe, and still sends feedback`

- 功能：插件行为断言：accepted 503 is delivery, not a second observe, and still sends feedback
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L180)。

### `tests/memory_bridge.test.ts::test:timeout retries the same observe id and does not mint another`

- 功能：插件行为断言：timeout retries the same observe id and does not mint another
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L204)。

### `tests/memory_bridge.test.ts::test:fingerprint 409 does not mint another observe id or send feedback`

- 功能：插件行为断言：fingerprint 409 does not mint another observe id or send feedback
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L240)。

### `tests/memory_bridge.test.ts::test:a new plugin instance replays an unacked outbox id instead of creating another`

- 功能：插件行为断言：a new plugin instance replays an unacked outbox id instead of creating another
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L262)。

### `tests/memory_bridge.test.ts::test:capture keeps latest parts but only confirmed assistant text (${role})`

- 功能：插件行为断言：capture keeps latest parts but only confirmed assistant text (${role})
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L290)。

### `tests/memory_bridge.test.ts::test:internal OpenCode agent sessions do not initialize the memory bridge`

- 功能：插件行为断言：internal OpenCode agent sessions do not initialize the memory bridge
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L323)。

### `tests/memory_bridge.test.ts::test:trio main-session tools cannot bypass Selector or human review`

- 功能：插件行为断言：trio main-session tools cannot bypass Selector or human review
- 输入：`无显式参数；beforeEach 的临时项目、fake HTTP/Bun/tool 边界`。
- 输出：`Promise<void> 或 void；成功无值，违约测试失败`。
- 作用：临时 outbox、mock/spy 与 Plugin hooks，非生产写入。
- 错误：expect/assertion/超时失败；不得把过滤用例当完整通过。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L335)。

### `tests/memory_bridge.test.ts::beforeEach`

- 功能：测试隔离设置/恢复，内部匿名 mock 归此回调
- 输入：`测试运行时，无显式参数`。
- 输出：`void`。
- 作用：建立临时项目、恢复 spy/mock、控制环境。
- 错误：初始化/恢复错误导致测试失败。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L23)。

### `tests/memory_bridge.test.ts::afterEach`

- 功能：测试隔离设置/恢复，内部匿名 mock 归此回调
- 输入：`测试运行时，无显式参数`。
- 输出：`void`。
- 作用：建立临时项目、恢复 spy/mock、控制环境。
- 错误：初始化/恢复错误导致测试失败。
- 目标：`tests/memory_bridge.test.ts`；处置：保留迁移；变更：保留当前签名与 IO；[源码](../tests/memory_bridge.test.ts#L60)。

## `.opencode/agent/hauler.md`

- 模块功能：三 Agent 权限与 JSON 输出协议定义。
- 设计归属：三 Agent 协议与主会话边界；处置：保留收口。
- 目标路径：`.opencode/agent/hauler.md`（当前路径）。
- 模块输入：封存 JSON payload。
- 模块输出：candidates JSON；permission 全 deny，不判分类。
- 源校验：`a5da787c96dee1098edaab4b873240dbb6b6a611f3479ecfcd7b6197283926ea`。
- 输入/输出：角色模块接收封存 JSON 并规定 role 输出；无源码函数。
- 导出/输入依赖：输入：封存 role payload；输出：Hauler candidates / Selector decisions / Reviewer bundle；工具权限 '*': deny，mode primary；无源码函数

## `.opencode/agent/selector.md`

- 模块功能：三 Agent 权限与 JSON 输出协议定义。
- 设计归属：三 Agent 协议与主会话边界；处置：保留收口。
- 目标路径：`.opencode/agent/selector.md`（当前路径）。
- 模块输入：候选批与记忆快照。
- 模块输出：decisions JSON；每候选恰一，不自行批准冲突。
- 源校验：`2afbf9fe5db996efb74a8c6956d0cfacd22593962c289ab21ec52ffe1c9bcde7`。
- 输入/输出：角色模块接收封存 JSON 并规定 role 输出；无源码函数。
- 导出/输入依赖：输入：封存 role payload；输出：Hauler candidates / Selector decisions / Reviewer bundle；工具权限 '*': deny，mode primary；无源码函数

## `.opencode/agent/reviewer.md`

- 模块功能：三 Agent 权限与 JSON 输出协议定义。
- 设计归属：三 Agent 协议与主会话边界；处置：保留收口。
- 目标路径：`.opencode/agent/reviewer.md`（当前路径）。
- 模块输入：投诉、窗口、handoffs 与规则。
- 模块输出：diagnosis/rules/repairs/rule_reviews JSON；不改库、不改权限。
- 源校验：`87b783d55758eef109cfb321fd8795b8e4ffd81c7eb469908cf0d35cbf79e26a`。
- 输入/输出：角色模块接收封存 JSON 并规定 role 输出；无源码函数。
- 导出/输入依赖：输入：封存 role payload；输出：Hauler candidates / Selector decisions / Reviewer bundle；工具权限 '*': deny，mode primary；无源码函数

## 计划新增模块（当前源码不存在；实施后并入上方模块章节）

## 计划新增符号（当前源码不存在；实施后并入对应模块章节）
