# 决策登记表（Decision Register · H1–H42，全部已决）

> 状态：历史基线 · 保留 P0–P6 的 H1–H42（2026-10-02）。当前唯一目标及本轮修订在 [target-architecture.md](target-architecture.md) 的 N01–N28 / §9.1；冲突条款按该修订执行。本表不构成第二份架构。

> 配套：[`target-architecture.md`](target-architecture.md)（目标结构）、
> [`acceptance-criteria.md`](acceptance-criteria.md)（验收 A1–A10）。
> 取证基线：主干全量通读（除 vendored `agent/`）；行号证据以本轮 `grep` 为准。
> 状态说明：`已决` = 本轮定案；`冻结` = 现状行为上升为架构约束，重构期不得改。

---

## A. 包结构与命名（H1–H5）

### H1 包名 `hybrid_memory` 保留，内部重排 —— 已决：保留
- **背景**：包名同时被插件（`python -m hybrid_memory.server` 拉起命令）、`opencode.json`
  文档、`eval/tide/adapters/dynamics_memory.py`（`python -m hybrid_memory.server --port 0`）、
  全部文档引用。改名是纯装饰性 churn，且会破坏已部署的插件拉起路径。
- **选项**：(a) 保留包名内部重排；(b) 改名（如 `dynmem`）+ 全仓替换。
- **决策**：(a)。**内部**目录按七公理重排，对外只保留两个兼容入口：
  `hybrid_memory.server:main`（3 行 shim）与 `MemoryService` 导入位。
- **后果**：`hybrid_memory/__init__.py` 只导出 `__version__`、`Cfg/Settings`、`MemoryService`；
  兼容 shim 清单见目标文档 §2.11；H23 管 shim 的寿命。

### H2 `server.py`（2091 行 / 66 个方法）必须拆 —— 已决：拆
- **背景**：单文件同时承担 HTTP 解析、鉴权、观察/检索/反馈三回路、agent 操作面、
  快照编解码、预算管理。任何一次需求都迫使整文件回归。
- **选项**：(a) 按层拆（service/* + transport/* + store/state + guards/* + telemetry + errors）；
  (b) 只抽 HTTP 层，保留大 service；(c) 不动。
- **决策**：(a)。拆分线 = 已存在的**调用边界**：凡只读 `self` 若干字段的方法，
  改为 `module.func(service, ...)` 纯搬运；凡跨回路共享的可变状态（`_t/_scene/_retrievals`）
  留在 `MemoryService` 门面内由 RLock 保护。
- **后果**：P4/P5 两阶段执行；每阶段准出 = pytest 全绿 + 行为 characterization 一致（A4）。

### H3 依赖方向固定 + `core/` 零依赖 —— 已决：强制
- **背景**：现状 `core/` 已接近纯净（engine 只依赖 config/types/semantics 协议），
  但没有任何机制阻止未来 import 越层。`server.py` 反向依赖一切。
- **决策**：依赖方向 `transport → service → dispatch/agents → core → store → embed/llm`；
  `core/` 不得 import `store/service/transport/agents/embed/llm`，由
  `tests/unit/test_import_boundaries.py` 静态扫描强制（A5）。
- **后果**：`core/triggers.py`、`core/interaction.py` 是纯类型/纯函数迁移，不带 I/O。

### H4 `agent/trio.py`（327 行）按"解析→校验→效果"拆 —— 已决：拆
- **背景**：单文件混装运行器（subprocess）、载荷构造、三类校验、效果提交。
  其中 Selector 校验是**安全核心**（UPDATE 授权门），必须可独立审计。
- **决策**：拆为 `agents/{protocol,opencode,payload,hauler,selector,reviewer}.py`；
  效果提交移入 `dispatch/effects.py`（H21）。校验函数签名冻结为
  `validate(service, row, reply) -> ...`，只读 service。
- **后果**：P6 执行；`test_agent_protocol.py` 不动（行为契约在 payload/validate 层之下）。

### H5 legacy 代码冻结为 `legacy/` 包 —— 已决：移不删
- **背景**：`worker.py`、`candgen/*`、`agent/{inline,loop,investigator}.py` 在默认管线下
  已不可达（`main()` 二选一），但 `MEMORY_PIPELINE=legacy` 仍是文档化行为，
  且 `eval/BASELINE.md` 的全部证据跑在 legacy 上。
- **决策**：移入 `legacy/` + 原路径留一行 re-export shim + `legacy/__init__.py` 置
  `DEPRECATED = True` 并在 legacy 启动时 `warn_once`。
- **后果**：删除是独立决策（H23），不在本次重构范围。

---

## B. 存储与状态（H6–H14）

### H6 checkpoint 是唯一权威状态，`state.pkl` 降为兼容导出 —— 已决：确立
- **背景**：现状双权威并存：`tasks.sqlite:checkpoint`（revision CAS）与 `state.pkl`
 （pickle 全量）。恢复逻辑（"checkpoint 优先否则 pkl"）已隐含了主次，但 `save()` 语义模糊。
- **决策**：`save()` 必须先推进 checkpoint，`state.pkl` 只是"兼容导出"（给旧版本/调试用）。
  恢复顺序：checkpoint → pkl → 空启动；三者互斥且外显为 `snapshot` 字段。
- **后果**：`store/state.py` 承载全部快照逻辑；`snapshot ∈ {absent,loaded,quarantined}` 语义冻结（A7）。

### H7 合并 taskstore 的两套状态机 —— 已决：单状态机 + 策略表
- **背景**：`claim/store_result/retry/finish`（调查类）与
  `claim_semantic/store_semantic_result/complete_semantic/retry_semantic`（语义+trio 类）
  并存（taskstore.py:256–482），语义 80% 重叠：租约领取、结果暂存、效果提交、重试计数。
- **选项**：(a) 合并为 `claim/store_result/retry/finish` + `KindPolicy` 参数；(b) 保留两套。
- **决策**：(a)。差异收敛为三个策略参数：`claim_from`（可领取的源状态集）、
  `on_exhausted`（耗尽后 dead 还是 requeue，见 H8）、`lease_s/backoff`。
  合并前先写 characterization 套件冻结现状（A4），P3 执行。
- **后果**：`dispatch/policy.py` 是策略唯一存放处；`SEMANTIC_KINDS/WORKFLOW_KINDS` 常量保留。

### H8 耗尽语义：调查类 → dead，语义类 → requeue —— 已决：分开
- **背景**：这是两套状态机**真正**的行为差异，其余都是形状差异。
- **决策依据**：
  - 调查类（recall_miss/extract_due/hauler/selector/reviewer）：失败主因是**证据不存在或输入非法**
    （源单元缺失、窗口超限），重试不改变输入 → `dead` + `last_error` 可见 + 计数。
    例外：`AGENT 进程崩溃`类瞬时失败走 `retry_model` 重试模型调用，不消耗效果次数。
  - 语义类（conflict_pending/feedback_pending/maintenance_due）：失败主因是**模型瞬时错误**
    （超载、解析抖动），输入（张力对/检索登记）依然有效 → `requeue` 回 pending，
    由退避重跑；但 `attempts` 上限仍卡死防无限烧钱（上限见 KindPolicy）。
- **后果**：策略表内逐 kind 注明理由；`dead` 任务永不自动复活，只能人工重发。

### H9 任务表容量 4096 + 满时 503 背压 —— 已决：冻结现状
- **背景**：`TaskStore(capacity=4096)` 满时抛 `TaskQueueFull` → HTTP 503（taskstore.py:179）。
  这是全仓唯一做对了的背压：拒绝新活，不丢旧活。
- **决策**：冻结。`enqueue` 容量检查保留；满时返回 `Degraded("queue_full")`，
  transport 映射为 503 + `accepted` 语义不变（unit 已落 L0，只是效果待定）。
- **后果**：容量值进 `Settings.task_capacity`（可配，默认 4096）；压测由 A10 覆盖。

### H10 schema 版本管理 —— 已决：新增
- **背景**：现状建表全是 `CREATE TABLE IF NOT EXISTS` + 散落的列迁移，
  **旧代码打开新库会静默读错**（缺列 → sqlite 报错算好的；语义漂移则静默）。
- **决策**：`store/schema.py` 持 `SCHEMA_VERSION`；`migrate()` 只做增量迁移；
  `schema_version > 代码版本` → `Fatal` 拒绝启动（H24），日志指明升级方向。
- **后果**：以后每次改表结构必须 bump 版本 + 写迁移 + 补测试；这是新增约束。

### H11 C 池上界：V 最低者淘汰 —— 已决：新增
- **背景**：`Cfg` 只有 `cap_m=40`（生产 8），C/A 无界（"有界长期记忆"的自我矛盾；
  finding #6）。C 是候选池：条目未经确认，低 V = 既无证据支持又无检索命中。
- **选项**：(a) V 最低淘汰；(b) 最旧淘汰；(c) 按置信淘汰。
- **决策**：(a)。C 池条目年龄接近（都是新蒸馏），年龄无信息量；V 是"证据+命中"的唯一综合分。
  但被 `pinned_ids`（未决张力/人审引用）保护的条目跳过（H14 联动）。
- **后果**：新增 `Cfg.cap_c`（默认 200）+ `overflow_policy` 纯函数 + 截断计数
  `n_pool_truncated`（A9）。

### H12 M 溢出拒收、A 最旧删除 —— 已决：新增
- **背景**：M 是"已确认记忆"，晋升是显式事件（滞回越过 θp）；A 是冷归档。
- **决策**：
  - M 满时：**拒绝新晋升**（条目留在 C），不静默挤掉已有 M。理由：挤掉=删除已确认知识，
    必须显式（X6 不静默失败）；晋升失败外显为计数 + `warn_once`。
  - A 满时：删除最旧（按 `archived_at`）。理由：A 已是"被遗忘"层，按时间 FIFO 最可解释；
    且 A 条目可从 L0 证据重建（`src` 仍在），删除是可逆的（代价=重蒸馏）。
- **后果**：新增 `Cfg.cap_a`（默认 2000）+ `archived_at` 字段；M 拒收计数进 telemetry。

### H13 L0 证据零自动删除 —— 已决：只告警
- **背景**：`log.sqlite` 无界增长是 finding #6 的另一半。但 L0 是**审计链**：
  每条记忆的 `src` 指回它；删证据 = 毁溯源。
- **选项**：(a) 按时间/体积自动删；(b) 只告警不删；(c) 压缩归档。
- **决策**：(b)。`retention_report()` 报告体积/最旧单元/`src` 悬空数；
  超阈值 `warn_once` + `/health` 字段。删除是**产品决策**（数据保留政策），
  不是工程默认值——自动删证据的记忆系统不可审计。
- **后果**：运维文档写明"备份整个状态目录"（现状 README 已有，保留）。

### H14 冲突唯一读模型 `conflict_ledger` —— 已决：新增
- **背景**：冲突台账有两处：`engine.tensions`（内存张力）与 `human_reviews` 表（人审队列），
  `/conflicts` 只读前者，人审读后者。同一对冲突在两处状态可能不一致。
- **决策**：`service/review.py:conflict_ledger()` 返回合并视图
  `{tensions: [...], pending_reviews: [...]}`；`/conflicts` 改读它（字段只增，A7）。
  写路径不变（tension 走裁决，CONFLICT 走人审），只统一**读**。
- **后果**：`pinned_ids`（H11）= tensions 两端 ∪ pending_reviews 的 target/candidate，
  淘汰保护有唯一依据。

---

## C. 抽取协议（H15–H20）

### H15 agent 返回契约：已解析 JSON 对象，否则 `AgentProtocolError` —— 已决：严格
- **背景**：`OpenCodeRunner` 解析 `opencode run --format json` 的 JSONL 流
  （trio.py:40–60）。现状对"非 JSON/截断/空输出"的处理散在 try/except 里。
- **决策**：`AgentRunner.run` 契约——成功返回 `dict`，失败抛 `AgentTimeout/AgentProtocolError`。
  **不猜测、不降级**：缺字段不补默认，错类型不强转。截断输出（`["choices"]` 缺 `finish_reason`
  或 JSON 不完整）一律视为协议错误，走 `retry_model` 重跑。
- **后果**：`agents/opencode._parse_text` 是唯一解析点；`fake CLI` 测试覆盖截断/空/乱码。

### H16 Hauler/Reviewer 窗口 12k 上限 + 超限失败 —— 已决：冻结现状
- **背景**：trio.py:109/117 超限抛 `ValueError("...cannot silently omit evidence")`。
  这是全仓最漂亮的一行：**证据窗口不许静默省略**。
- **决策**：冻结。超限 = 该任务失败（`Degraded` + 重试不改变输入 → 最终 dead，H8），
  不截断、不分片。理由：分片会破坏"候选↔源单元"的归因完整性。
- **后果**：`agents/payload.py` 保留 12000 常量；未来若放宽必须走 ADR（这是正确性相关的数）。

### H17 Selector 快照 500 上限 + 截断时禁猜 —— 已决：冻结并收紧
- **背景**：trio.py:134 快照超 500 截断。风险：Selector 因没看到某条记忆而误判 CREATE，
  造成重复入库。
- **决策**：截断时在 payload 置 `snapshot_truncated=true`；`agents/selector.validate`
  规则——若截断且候选与快照无明确对应，**不得 CREATE，必须 CONFLICT**（交人审），
  也不得"猜 EXIST"。确定性 id 序保证重试时看到同一子集（可复现）。
- **后果**：这是 H17 对现状的收紧（现状截断后无特殊处理）；测试覆盖"截断→CONFLICT"。

### H18 UPDATE 需 `verified_correction` + 源单元 `is_correction` —— 已决：冻结（安全核心）
- **背景**：trio.py:200+ 的 proof-gate：Selector 的 UPDATE 必须自带
  `verified_correction=true` 且引用的源单元被 `is_correction` 判定为纠正语句，
  否则降级为 CONFLICT。这是"agent 不能凭空改写记忆"的唯一技术 enforcement。
- **决策**：冻结为安全核心，移入 `agents/selector.py` 时逐行搬运 + 注释注明 H18。
  任何放宽（去 gate、换判定器）必须走 ADR + 安全测试。
- **后果**：`is_correction` 的误报/漏报直接决定 UPDATE 可用性 → 触发器测试（test_triggers）
  升级为安全测试，改正则必须跑全量。

### H19 `rule_reviews` 只能引用 handoffs 中出现过的 rule_id —— 已决：冻结
- **背景**：Reviewer 可以评价规则（`ineffective` → 自动禁用）。若允许引用任意 id，
  被污染/幻觉的 Reviewer 可批量禁用有效规则（权限放大）。
- **决策**：`agents/reviewer.validate` 校验 `rule_id ∈ 本次 handoffs 的 rule_ids`，
  否则整条 `rule_reviews` 拒收（不影响同包的 diagnosis/rules，发 `Degraded`）。
- **后果**：与 H18 同级的安全测试；`test_trio_protocol.py` 已有覆盖，搬运时保留。

### H20 校验在服务端，agent 永不直接改库 —— 已决：架构冻结
- **背景**：现状已是如此（agent 输出经 validate → effect 入库；trio 下直写端点 403）。
- **决策**：上升为架构约束：`agents/*` 只允许返回"待校验结构"，
  唯一写库入口是 `dispatch/effects.py` 的 applier。`agents/` 模块禁止 import `store/`。
- **后果**：import 边界测试覆盖（A5）；未来加新 agent 只需加"载荷+校验器"，效果层复用。

---

## D. 效果与幂等（H21–H25）

### H21 效果与 checkpoint 同事务，`effect_transaction` 唯一入口 —— 已决：确立
- **背景**：`complete_semantic`（taskstore.py:440）已做到"效果/checkpoint/回执/done 同事务"，
  但 `apply_unit`、`apply_operation`、`store_result` 各自为政，调用点散在 server/trio/loop。
- **决策**：`dispatch/effects.effect_transaction(service, mutate)` 是**唯一**效果入口：
  `validate → mutate(内存) → dump → checkpoint CAS → done` 全在一个 `BEGIN IMMEDIATE` 内。
  直接调用 `store.tasks.*` 写方法的代码视为违规（P5 后用扫描测试卡）。
- **后果**：kill -9 恢复语义统一为"效果要么全有要么全无"（A10 现有 subprocess 测试保留）。

### H22 幂等键语义冻结 —— 已决：冻结
- **背景**：三套幂等键并存且都正确：插件 `request_id` 指纹（capture_receipts）、
  操作 `op_key`（operations 表）、任务 `(kind,key)` 去重合并。
- **决策**：语义冻结，搬运时逐字保留：指纹算法（sha256 over sorted JSON）、
  409 冲突语义（同 id 异正文拒绝绑定）、重放返回原回执。
- **后果**：`test_capture_delivery.py` 整体搬入 `tests/integration/test_service_observe.py`，一字不改。

### H23 `legacy/` 与 shim 同生共死 —— 已决：推迟删除
- **背景**：H5 移入 legacy 的代码 + 原路径 shim，何时可删？
- **决策**：删除条件是"**裸引擎不再是交付形态**"——即 `MemoryEngine` 脱离 sidecar
  独立使用的场景（仿真、单测、第三方嵌入）全部迁移完毕或明确放弃。
  在此之前 `legacy/worker.py`（SignalWorker）是裸引擎唯一的语义驱动，
  删了它等于删了裸引擎的可运行性。删就是一次独立决策（另开 ADR），删则连 shim 一起删，
  不留"半截兼容"。
- **后果**：本次重构不删一行 legacy；`DEPRECATED` 标记 + 启动告警是唯一的"推力"。

### H24 三类错误 + 唯一 HTTP 映射 —— 已决：新增
- **背景**：现状错误是字符串 + 散落的状态码（400/401/403/404/409/413/415/429/503），
  调用方（插件）靠 `body.error` 子串判断（如 `"容量" in error`），脆弱。
- **决策**：`errors.py` 定义 `Rejected(code)`（4xx，调用方错）、`Degraded(code, detail)`
  （可继续但外显）、`Fatal(code)`（拒绝启动）；`http_status(code)` 唯一映射；
  插件改判 `code` 不判子串（插件侧小改，向后兼容：保留 `error` 文案字段）。
- **后果**：现有测试里断言状态码的不动；新增 `code` 字段断言；`test_http_contract.py` 冻结映射表。

### H25 每个持久 kind 必须有消费者 —— 已决：启动自检
- **背景**：任务种（kind）是字符串，生产者（observe/report_miss/maintenance）与消费者
  （DispatchWorker/applier）分散两处。加 kind 忘加消费者 = 任务永 pending（静默死信）。
  现状已有 9 种：recall_miss/extract_due/hauler_due/selector_due/reviewer_due/
  conflict_pending/feedback_pending/maintenance_due/feedback（+capture 系）。
- **决策**：`dispatch/policy.assert_consumers(EFFECTS)` 在 service 启动时执行：
  `POLICIES` 的每个 kind 必须在 `EFFECTS` 有 applier，否则 `Fatal` 拒绝启动。
  测试复用同一函数。
- **后果**：加新 kind = 加 policy + 加 applier + 加测试，三件套缺一不可（CI 卡）。

---

## E. 动力学与语义（H26–H32）

### H26 `core/` 算法语义冻结 —— 已决：冻结
- **背景**：衰减公式、滞回阈值、τ_dup/τ_sim、RRF k=60、π 先验、质量门 θ——
  这些是"研究结论"，重构期调任何一个都会污染"行为等价"的验收基线。
- **决策**：P0–P6 全程只搬运不调参；`Cfg` 默认值一个字符不许动。
  调参是独立工作流：改 → 跑 TIDE → 贴 NTU 数字 → 另开 PR。
- **后果**：characterization 套件（A4）是冻结的机械 enforcement。

### H27 双裁判问题：保留 ZAI 直连语义通路，但显式化 —— 已决：保留+显式
- **背景**：finding #1：trio 下 `process_semantic_tasks` 仍在调 `LLMSemantics`
  （judge/recognizer/consolidate），与三 agent 并存。关还是留？
- **选项**：(a) 关掉，trio 下语义任务全部走 agent；(b) 保留但显式化；(c) 合并 verdict 通路。
- **决策**：(b)。理由：`conflict_pending` 裁的是**存量张力**（tension 老化），
  `maintenance_due` 产的是**跨记忆 reflection**——Selector 只处理"候选分流"，
  不管存量；关掉 (a) 会让存量张力永不裁决、巩固回路停摆，是功能倒退。
  (c) 是正确长期方向（verdict 也走 Selector/Reviewer），但需要协议扩展，
  不在重构期做。显式化手段：`SemanticsProvider.health()`（calls/last_error）
  进 `/health` + `/signals`，消灭"隐式第二条 LLM 通路"；文档如实写两条通路的分工。
- **后果**：`semantics/provider.py` 新增；README"架构"节加两通路说明；(c) 记为 ADR 草稿。

### H28 `tension_delay=20` 保留 —— 已决：保留（调优 backlog）
- **背景**：TIDE v0.1 证据：探针在更新后 10 轮发出，`tension_delay=20` 导致 judge 还没轮到，
  V 维 u<0。这是**参数问题**，不是结构问题。
- **决策**：保留 20（H26 冻结）。记入调优 backlog，附 TIDE 复现命令；
  调优 PR 必须贴 V 维 NTU 前后对比。
- **后果**：重构验收（A1–A10）不含此项；防止"重构顺手调参"污染基线。

### H29 contested 行加 `contested_k` 上界 —— 已决：修
- **背景**：BASELINE #3：top-k=5 注入 16 行，11 行是未决冲突，与"有界"承诺矛盾。
  这是**违背已承诺不变量**的 bug，不是调优。
- **决策**：每条入选记忆最多带 1 个对手、总共最多 3 行，超限截断 + `truncated` 标志。
  放在 `service/recall.py:context_lines`，与预算截断同一处。
- **后果**：P4 已修（`service/recall.py:context_lines` + `truncated` 标志；测试 `test_service_recall.py::test_contested_bound` 断言"16 行场景 → ≤8 行 + truncated=true"）。

### H30 TIDE V/P 为负（无依赖失效机制） —— 已决：功能 backlog，不在重构范围
- **背景**：v0.1 报告：V（修订）u<0、P（传播）≈−0.5~−0.9。根因是机制缺失
  （引擎没有"上游变更→派生失效"），不是代码组织问题。
- **决策**：记为功能 backlog（`docs/decisions/ADR-tbd-dependency-invalidation.md` 草稿），
  重构期不动。这是"先把房子结构理顺，再装修"的顺序问题。
- **后果**：验收不含 V/P 转正；但 H29 这类"违背承诺"的必须修（区分标准：文档承诺了没有）。

### H31 salience/novelty/confidence 默认 OFF —— 已决：冻结现状
- **背景**：三套机制 + 开关全在 `Cfg`，生产默认全关。开哪套是**评测问题**（cf. 诊断文档 D2：
  消融测的是空气——机制没触发）。
- **决策**：默认值冻结；每套机制的启用条件写进 ADR 草稿：
  开关打开 ⇔ TIDE 对应维度有显著 NTU 提升 + 覆盖率闸门通过（机制触发次数 > 阈值）。
- **后果**：`Cfg` 注释注明每开关的"启用证据要求"；防止拍脑袋开机制。

### H32 shadow 信用延迟结算 —— 已决：冻结
- **背景**：压制对的 shadow 信用恒延迟到 verdict 到达后结算（`_shadow_pending` + 持久化），
  `test_late_credit.py` 全套覆盖。这是正确但微妙的语义。
- **决策**：冻结，搬运到 `core/maintenance.settle_shadow` 时逐行搬 + 测试一字不改。
- **后果**：`shadow_pending` 的 pickle 字段名冻结（跨版本恢复依赖它）。

---

## F. 传输与插件（H33–H37）

### H33 插件 outbox 语义冻结 —— 已决：冻结
- **背景**：`bridge-outbox.json` + `request_id` 幂等 + 3 次/30s 重试 + 退避，
  是"插件崩溃不丢 turn"的唯一保障，`memory_bridge.test.ts` 全套覆盖。
- **决策**：语义冻结。H24 的 `code` 字段是**加法**（插件改判 code，但保留对旧字段的兼容）。
- **后果**：插件改动必须跑 `bun test`；outbox 文件格式变更需迁移（现在无版本号，加 `v:1`）。

### H34 `/health` 语义冻结 + `validation` 保持 `unverified` —— 已决：冻结
- **背景**：`health_view` 字段集（ok/snapshot/units_pending/validation/corrupt_file/…）
  是插件复用决策 + 运维的唯一依据；`validation=unverified` 是诚实声明（未做 L3）。
- **决策**：字段只增不改语义（A7 契约测试）；`validation` 保持 `unverified` 直到 L3 真实评测完成。
  H27 的 `semantics` 健康段是加法。
- **后果**：`test_launch_closeout.py` 升级为契约测试（改字段即红）。

### H35 trio 下直写端点 403 —— 已决：冻结（安全核心）
- **背景**：`/propose|/resolve|/diagnose` 在 trio 下 403（server.py:1780–1852），
  防止主 agent 绕过 Selector/人审直接改库。与 H18/H20 同属安全核心。
- **决策**：冻结。`transport/http.ROUTES` 用声明式禁用表表达
  `{trio: {"POST /propose": 403, ...}}`，测试枚举全表（防"加了端点忘加禁用"）。
- **后果**：安全测试；禁用表与 H18 同级评审（改动需双人看）。

### H36 双 token（bearer + 人审 capability） —— 已决：保留
- **背景**：`.memory-token`（0600）管读写，`.human-review-token` 管人审决定，
  两权分离。`human_review.py` CLI 已依赖此分离。
- **决策**：保留。`transport/auth.py` 统一 `compare_digest` 校验 + 能力位检查；
  人审端点要求双 header（现状行为，冻结）。
- **后果**：token 文件权限 0600 写进测试（现状只测了 token 内容，未测权限——补）。

### H37 `human_review.py` 是 trio 的 human CLI，不是 legacy —— 已决：纠正归类
- **背景**：该文件用 `/human-reviews` + `.human-review-token` + `rule_report()`，
  全是 trio 设施（50 行已通读）。参考草案误把它归入 `legacy/`。
- **决策**：移入 `transport/review_cli.py`（它是 HTTP 客户端，不是传输服务端，
  但归属 transport 层最贴切：只调 HTTP + 读 token 文件）。
- **后果**：`python -m hybrid_memory.transport.review_cli --project ...` 替代旧调用；
  原路径留 shim（H1 兼容承诺）。

---

## G. 测试与评测（H38–H42）

### H38 测试重组随迁，禁止一次全搬 —— 已决：随迁
- **背景**：23 文件 / 333 个测试函数。测试是行为契约，一次全搬 = 契约真空期。
- **决策**：测试跟着被测代码走：P3 合并状态机时搬 task 相关测试，P4/P5 拆 server 时搬
  http/observe/recall 测试。`tests/characterization/` 是临时冻结套件（P3 用完即删，
  不进长期结构）。`conftest.py` 的共享夹具（service 工厂/fake runner/fake embedder）
  在 P2 先行抽出，避免搬运时复制粘贴。
- **后果**：任何时刻 `pytest` 全绿（A1）；PR 粒度 = "一模块 + 它的测试"。

### H39 `eval/tide/` 一行不改 —— 已决：冻结
- **背景**：TIDE 是外部判分器，"平台与引擎分离"是它的立身之本。重构引擎时顺手改判分器
  = 又当运动员又当裁判。
- **决策**：`eval/tide/` 冻结；重构验收包含"TIDE 元评测 PASS"（A3），用同一基准量前后。
- **后果**：`tide/adapters/dynamics_memory.py` 调用的 `python -m hybrid_memory.server`
  入口必须保持可用（H1 的 shim 承诺在此兑现）。

### H40 `eval/*.py` 离线脚本移入 `eval/harness/` —— 已决：移（低优先）
- **背景**：`mock_llm/drive/preview_sidecar/run_sidecar_offline.py` 是 sidecar 级冒烟工具，
  与 TIDE 判分无关，放 `eval/` 根目录混淆了"判分器 vs 工具"。
- **决策**：P6 收尾时移入 `eval/harness/` + 更新 `eval/README.md` 命令。注意这些脚本
  针对 legacy 行为（candgen/judge），trio 下部分断言会变——移时只改 import，
  行为差异记 backlog 不修。
- **后果**：低优先，可独立 PR。

### H41 验收门槛：pytest + acceptance_check + TIDE meta —— 已决：三门
- **背景**：重构没有"跑起来就行"，必须有机械门槛。
- **决策**：三门缺一不可：(1) `pytest` 全绿（A1）；(2) `analysis/acceptance_check.py`
  全 PASS（A2–A10 的机械部分，PENDING 白名单显式列出）；(3) `python -m tide meta` PASS（A3）。
  三门进 CI（`.github/workflows/ci.yml`），红灯禁合。
- **后果**：`acceptance_check.py` 在 P0 实现（它是验收工具，不是产品代码，放 `analysis/`）。

### H42 PENDING 白名单 —— 已决：显式列出
- **背景**：H28/H30/H31 等"已知未决"若散在口头，会变成"以为修了其实没修"。
- **决策**：`acceptance-criteria.md` 末尾设 PENDING 表：每项写明现状、证据、解冻条件
  （如 H30 的解冻条件是"依赖失效机制设计 ADR 通过"）。白名单项不阻塞合并，
  但 `acceptance_check.py` 必须打印它们（可见，不可 silently pass）。
- **后果**：每季度（或每版本）review 一次白名单，消项走正常 PR。

---

## 决策索引

| ID | 标题 | 结论 |
|---|---|---|
| H1 | 包名 | 保留 `hybrid_memory`，内部重排 |
| H2 | server.py | 按层拆 |
| H3 | 依赖方向 | 固定 + core 零依赖（测试强制） |
| H4 | trio.py | 按三段拆 |
| H5 | legacy 代码 | 移入 `legacy/` + shim |
| H6 | 权威状态 | checkpoint 唯一，pkl 是导出 |
| H7 | 两套状态机 | 合并为单状态机 + 策略表 |
| H8 | 耗尽语义 | 调查类 dead，语义类 requeue |
| H9 | 队列容量 | 4096 + 503 背压冻结 |
| H10 | schema 版本 | 新增版本管理 + 高版本 Fatal |
| H11 | C 池上界 | V 最低淘汰（pinned 豁免） |
| H12 | M/A 上界 | M 拒收新晋升，A 最旧删除 |
| H13 | L0 删除 | 永不自动删，只告警 |
| H14 | 冲突读模型 | `conflict_ledger` 合并视图 |
| H15 | agent 返回契约 | 严格 JSON，否则协议错误 |
| H16 | 证据窗口 12k | 超限失败，不截断 |
| H17 | 快照 500 | 截断时禁猜，CONFLICT |
| H18 | UPDATE 门 | verified_correction + is_correction（安全核心） |
| H19 | rule_reviews 引用 | 仅限 handoffs 内 rule_id |
| H20 | 校验位置 | 服务端，agent 永不直写 |
| H21 | 效果入口 | `effect_transaction` 唯一 |
| H22 | 幂等键 | 三套语义冻结 |
| H23 | legacy 删除 | 推迟，条件是裸引擎退役 |
| H24 | 错误分类 | Rejected/Degraded/Fatal + 映射表 |
| H25 | kind 消费者 | 启动自检，无孤儿 |
| H26 | core 算法 | 全程冻结不调参 |
| H27 | 双裁判 | 保留 ZAI 通路 + 显式化 |
| H28 | tension_delay | 保留 20，调优 backlog |
| H29 | contested 上界 | 修（1+3 行） |
| H30 | V/P 为负 | 功能 backlog，不在重构范围 |
| H31 | 三机制开关 | 默认 OFF 冻结 |
| H32 | shadow 结算 | 语义冻结 |
| H33 | 插件 outbox | 语义冻结 |
| H34 | /health | 字段冻结，validation 保持 unverified |
| H35 | 直写端点 | trio 下 403 冻结（安全核心） |
| H36 | 双 token | 保留 + 0600 测试 |
| H37 | human_review.py | 纠正为 trio CLI → transport |
| H38 | 测试重组 | 随迁，禁一次全搬 |
| H39 | eval/tide | 一行不改 |
| H40 | harness | 移入子目录（低优先） |
| H41 | 验收三门 | pytest + checker + tide meta |
| H42 | PENDING | 白名单显式列出 |

---

## H. 收尾与迁移定案（N29–N33）

### N29 证据与大模型客户端模块迁移（已决：完成）
- `hybrid_memory/logstore.py` 迁移为 `hybrid_memory/store/evidence.py`。
- `hybrid_memory/llm.py` 迁移为 `hybrid_memory/llm/client.py`，保留内部磁盘缓存 `_cache_lookup` / `_cache_store`。
- `hybrid_memory/logstore.py`、`hybrid_memory/llm.py`、`hybrid_memory/llm/__init__.py` 保留为 100% 向后兼容的 re-export shims。

### N30 双语义通路显式提供者（已决：完成）
- `hybrid_memory/semantics/provider.py` 实现 `SemanticsProvider`，统一封装 `judge`、`relevant_set`、`consolidate`，并提供 `health()` 观测字典（calls, failures, last_error）。
- 运行时与配置解除硬耦合，支持 provider 隔离与状态可观测性。

### N31 冲突台账只读视图与统一容量计划（已决：完成）
- `hybrid_memory/service/review.py` 实现 `conflict_ledger(svc, before)`，提供张力、人审、聚合、pin roots 的统一只读聚合模型。
- `hybrid_memory/core/dynamics.py` 实现纯函数 `plan_capacity(mems, cfg, pinned)`，在无 I/O 前提下模拟 C/M/A 容量收口，全 pin 时提供 backpressure (`accepted=False`)。

### N32 任务调用上下文封存与效果准备编排（已决：完成）
- `hybrid_memory/store/tasks.py` 实现 `TaskStore.store_call_context`，在任务执行事务中原子封存调用上下文与快照版本。
- `hybrid_memory/dispatch/effects.py` 实现 `prepare_effect(svc, row)`，在锁外完成静态校验与向量化，保障事务临界区零外部 I/O。

### N33 显式符号契约与清理收敛（已决：完成）
- 清理 N25 指定的废弃符号（`bounds.py::clamp`、`grounding.py::cited_text`、`acceptance_check.py::_has_int_gt`）。
- 架构契约 `analysis/architecture_contract.py` 与符号清单 `docs/architecture-inventory.md` 完整对齐 144 个模块与 1358 个符号。

