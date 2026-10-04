# 验收标准（Acceptance Criteria · A1–A12）

> 状态：机械验收基线（2026-10-02）。现有 A1–A10 保留；本轮目标的新闸门见唯一 [target-architecture.md](target-architecture.md) §10，尚待接入代码与 CI。旧门通过不等于新目标已经实现；验收变更需同步检查器及对应回归。

> 配套：[`target-architecture.md`](target-architecture.md)（目标结构）、
> [`decision-register.md`](decision-register.md)（H1–H42）。
> 执行：`analysis/acceptance_check.py`（P0 实现）+ `pytest` + `python -m tide meta` 三门（H41）。
> 每条含：断言、检查方式、挂钩决策。PENDING 白名单在末尾（H42）。

---

## A1 pytest 全绿
- **断言**：`python -m pytest tests/ -q` 零失败、零 error；`bun test tests/`（插件契约）零失败。
- **检查**：CI 直接跑；任何时刻（含每个迁移 PR）都必须绿（H38）。
- **基线**：23 文件 / 333 个测试函数（本轮实测）；重组后数量只许增不许减
  （删测试必须说明被哪个新测试替代）。

## A2 文档断言有据
- **断言**：`README.md`、`analysis/target-architecture.md`、`docs/opencode-trio.md` 中的每个产品断言
  （"有界""幂等""恰好一次""X 上限 N"）要么指向一个测试，要么标 `PENDING-xx`。
- **检查**：`acceptance_check.py` 维护"断言→证据"表（手写表 + 链接检查，非 NLP）；
  新增文档断言无证据即红。
- **挂钩**：H29（contested 上界修完才许写"注入块有界"）；H42。

## A3 TIDE 元评测 PASS
- **断言**：同一 L1 数据集上，`python -m tide meta` PASS；`dynamics-memory` 适配器
  可跑通（NTU 数字不要求提升，要求"可比"：同一基准前后差由结构变更解释）。
- **检查**：CI 跑 `tide meta`（纯本地，零 API）；`tide bench --systems dynamics-memory`
  跑 `--max-streams-per-dim 1` 烟囱版（mock LLM）。
- **挂钩**：H39（`eval/tide/` 一行不改）；H26（不调参，所以数字应基本不变——变了就是行为漂移）。

## A4 行为等价（characterization）
- **断言**：P3 合并状态机前后、`tests/characterization/` 套件输出逐字节一致
  （任务状态序列、checkpoint revision 序列、效果计数）。
- **检查**：套件在 P2 末冻结（只许加不许改）；P3–P6 每次跑 diff；P6 末删除套件
  （使命完成，不进长期结构）。
- **挂钩**：H7（合并）、H26（冻结）、H38。

## A5 导入边界
- **断言**：`core/` 不 import `store/service/transport/agents/embed/llm`；
  `agents/` 不 import `store/`；`transport/` 不 import `core/`（只能经 service）。
- **检查**：`tests/unit/test_import_boundaries.py` 用 `ast` 扫描全包；CI 跑。
- **挂钩**：H3、H20。

## A6 无孤儿 kind
- **断言**：`POLICIES` 的每个 kind 在 `EFFECTS` 都有 applier；
  反向：每个 applier 都有 policy（无野 applier）。
- **检查**：`dispatch.policy.assert_consumers()` 启动时执行 + 测试直接调。
- **挂钩**：H25。

## A7 契约冻结（/health、/signals、错误码）
- **断言**：`/health`、`/signals` 响应字段集只增不改语义；`errors.http_status` 映射表
  快照一致；trio 禁用端点表快照一致。
- **检查**：`tests/integration/test_http_contract.py` 快照断言（字段集合 + 示例值类型）；
  改字段/改码即红，需 ADR 才许更新快照。
- **挂钩**：H24、H34、H35。

## A8 无裸错误穿透
- **断言**：HTTP 层不直接抛裸 `RuntimeError/ValueError/KeyError`（500 只能来自 Fatal
  或未预见的 bug，不能是可预见的调用方错误）；`agents/opencode` 的解析失败
  一律转为 `AgentProtocolError`。
- **检查**：`test_http_contract.py` 枚举"坏输入→状态码"表（400/403/404/409/413/415/429/503
  全覆盖）；`agents` 解析 fuzz（截断/空/乱码/缺字段 → 协议错误，不抛裸异常）。
- **挂钩**：H15、H24。

## A9 有界性齐全
- **断言**：每个池/队列/快照/任务表都有 `cap_*`：M（cap_m）、C（cap_c 新增）、A（cap_a 新增）、
  任务表（4096）、信号队列（cap）、快照（500）、窗口（12000）、trace（18/24k）、
  contested（1+3，H29）、propose 批量（50）；超限动作确定（淘汰/拒收/截断/503）且有计数。
- **检查**：`Cfg`/`Settings` 齐全性测试（cap 字段缺一即红）+ `overflow_policy` 单测
  （每池超限动作断言）+ telemetry 计数存在性。
- **挂钩**：H9、H11、H12、H16、H17、H29；例外 H13（L0 只告警，`retention_report` 存在即过）。

## A10 恰好一次（kill -9 恢复）
- **断言**：现有 subprocess 恢复测试（observe/feedback/complete 各阶段 `os._exit`）
  在重组后保留且全过；效果计数 = 1（不多不少），checkpoint revision 单调。
- **检查**：`tests/integration/test_dispatch_recovery.py`（原 test_observe_recovery/
  test_semantic_recovery/test_durable_tasks 重组）；Windows 兼容（subprocess env 修过一次，
  别 regression）。
- **挂钩**：H21、H22。

---

## A11 可观测性与预算闸

- **断言**：pin 水位同容量保护集，0.7 边界告警；预算闸在重启后生效；失败 checkpoint 不污染预算水位；save 不受闸。
- **检查**：`tests/unit/test_observability.py`；`acceptance_check.py::check_a11`。

## A12 L2/L3 审计完整性

- **断言**：裁决不跨 run、不从 dead 归因；结算拒绝漏填/重复/未知 ID，保全各流和 first-pass；撤回改写禁旧值；导出离线只读；启动等待有界。
- **检查**：`tests/unit/test_l2l3_audit.py`；mock 全链自检命令见 `eval/README.md`。本门不代表模型质量或人工验收。

## PENDING 白名单（H42：可见但不阻塞）

| ID | 事项 | 现状证据 | 解冻条件 |
|---|---|---|---|
| PENDING-01 | `tension_delay=20` 致 V 维 judge 迟到 | TIDE v0.1：探针 t+10，delay 20（H28） | 调优 PR + V 维 NTU 对比 |
| PENDING-02 | 无依赖失效机制，P 维为负 | TIDE v0.1：P ≈ −0.5~−0.9（H30） | 依赖失效 ADR 通过 |
| PENDING-03 | salience/novelty/confidence 默认 OFF | `Cfg` 开关全关（H31） | 每机制 TIDE 证据 + 覆盖率闸门 |
| PENDING-04 | verdict 通路合并（verdict 走 Selector） | H27 选 (b)，(c) 为长期方向 | 协议扩展 ADR |
| PENDING-05 | `legacy/` 删除 | H23：条件是裸引擎退役 | 另开删除 ADR |
| PENDING-06 | 第二项目端口冲突（固定 17872） | BASELINE #5 | 端口分配方案 ADR |
| PENDING-07 | L0 未脱敏进 LLM（log_search snippet 含原文） | BASELINE #2 | 脱敏层设计（注意：修了会影响调查员能力，需评测） |
| PENDING-08 | 真实会话 L3 与独立人工复核未闭合 | N48 CLI 首验；N51 inline + 85 条开发日志引述 + Agent 单评；原始 99.8% 不作人工验收 | 真实 provider + 真实会话证据 + 人工抽检 |
| PENDING-09 | checkpoint 全量 pickle O(N)（500 条≈301 KB/次） | design-debts.md §2 实测；2MB 预算闸已接线（N49） | 分段 pickle ADR（I5 单点接入） |
| PENDING-11 | 值链收敛触发盲区：纯观察流量张力不触发，旧代以"当前值"口吻驻留 | N51 实跑：V 链 43/57 过期代入池、21 条当前口吻；端口链 6 条并存；人审 50 条悬置 | 值变更后主动张力检查 或 检索期多代"当前值"消解（设计+回归） |
| PENDING-12 | 值变更判罚口径不统一（同值变更 CREATE/CONFLICT 并存） | N51 实跑 + N52 修正：docs 鉴权链 CONFLICT×3 与 CREATE 并存（人审待决期间同义新记忆可检索） | 口径 ADR（与 PENDING-11 协同） |

> 消项记录：PENDING-10（pin 占用指标+告警）已于 N49 兑现——/health 暴露
> pin_roots/pinned_context/pin_occupancy/alerts，≥0.7 外显告警；回归
> tests/unit/test_observability.py + 验收门 A11。

> `acceptance_check.py` 每次运行必须打印本表（H42）。消项走正常 PR，更新本表。
