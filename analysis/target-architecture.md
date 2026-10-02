# 目标架构（定稿 · 只抽象，不实现）

> 状态：冻结 · 目标架构终稿（2026-10-02）；改动需 ADR。

> 依据：主干全量通读（`hybrid_memory/` + `eval/` + 插件 + 测试 + 文档，除 vendored `agent/`）。
> 决策登记：[`decision-register.md`](decision-register.md)（H1–H42，全部已决）。
> 验收挂钩：[`acceptance-criteria.md`](acceptance-criteria.md)（A1–A10）。
> 本文只回答"应该长成什么样"；迁移动作在第 4 节，实施阶段在第 5 节。
> 取证修正（相对参考草案）：server.py **2091** 行/66 方法；测试 **23** 文件/**333** 函数；
> trio.py **327** 行；`human_review.py` 是 trio CLI（H37），不归 legacy。

---

## 0. 核心思想 → 七条架构公理

项目的一句话：**把连续、嘈杂、前后矛盾的项目交互，蒸馏成有界、可溯源、不会腐烂的 agent 长期记忆。**
从这句话直接推出七条公理，目标结构是它们的必然结果，不是现有目录的重排：

| # | 公理 | 结构后果 |
|---|---|---|
| X1 | **证据 ≠ 记忆** | L0 证据库与记忆状态分离；记忆必须携带 `src`；原文只能经有界窗口回展（`core/` 与 `store/evidence` 的边界） |
| X2 | **记忆是动力系统，不是表** | 动力学（衰减/滞回/淘汰/信用/张力）是纯函数，独立于 I/O 与存储（`core/dynamics.py` 等） |
| X3 | **提取是协议，不是函数调用** | 三类 agent 产物各有"解析→校验→效果"三段，校验在服务端；agent 永不直接改库（`agents/` + `dispatch/effects`） |
| X4 | **效果恰好一次** | 派发层统一持有状态机/租约/幂等键；效果与 checkpoint 同事务（`store/tasks.py` + `dispatch/`） |
| X5 | **一切有界** | 每个池/队列/快照/任务表都有上界 + 淘汰策略 + 可观测计数（`guards/bounds.py` + `core/dynamics.evictable`） |
| X6 | **不静默失败** | 三类错误（Rejected/Degraded/Fatal）；降级必须外显为标志或计数（`errors.py` + `telemetry.py`） |
| X7 | **单进程、单项目、单写者** | 无分布式假设；锁与 checkpoint CAS 足矣（`service/service.py` 持锁，`store/tasks.checkpoint` 定序） |

依赖方向固定为 **transport → service → dispatch/agents → core → store → embed/llm**；
`core/` 不得 import 其它任何层（import 守卫测试强制，A5）。

---

## 1. 目标目录树（精确到文件）

```
Dynamics-memory/
├── README.md                      面向使用者：30 秒上手 + 不变量摘要 + 指向 ARCHITECTURE
├── ARCHITECTURE.md                新增：一页纸架构（= 本文 §0/§2 的压缩版，随代码同 PR 更新）
├── pyproject.toml                 新增：包元数据 / pytest / ruff / 入口点
├── pytest.ini                     保留（testpaths/pythonpath）
├── Makefile                        新增：make test / make accept / make bench
├── .env.example  opencode.json    保留
├── .github/workflows/ci.yml       新增：pytest + 验收检查器 + tide meta
├── analysis/                      新增：本文 + 决策登记 + 验收标准 + acceptance_check.py（设计期产物）
├── .opencode/
│   ├── agent/{hauler,selector,reviewer}.md      协议的一部分，改动需过 protocol 测试
│   └── plugin/memory-bridge.ts                  插件（唯一 TS 交付面；改判 code 不判子串，H24）
├── hybrid_memory/                 包（见 §2 逐文件）
├── eval/
│   ├── tide/                      外部判分器（H39：一行不改）
│   ├── harness/                   新增：mock_llm.py / drive.py / preview_sidecar.py / run_sidecar_offline.py
│   ├── data/l1/  results/  runs/  README.md  BASELINE.md
├── docs/
│   ├── index.md                   新增：文档地图 + 每份文档的状态（现行/历史）
│   ├── architecture.md            新增（= 本设计的落位版）
│   ├── decisions/ADR-*.md         新增：H1–H42 落位（每条一页或分组合并）
│   ├── opencode-trio.md           现行协议文档（加两通路说明，H27）
│   ├── persistence/durable-tasks/… 历史批次记录（加状态抬头，保留溯源）
│   └── opencode-learning/         外部阅读笔记（原样保留）
└── tests/                         见 §2.12
```

选择"保留 `hybrid_memory` 包名"是 H1 的决定：它是插件拉起命令、`opencode.json`、
评测适配器、文档共同引用的部署契约。**内部**目录按公理重排，对外只保留两个兼容入口。

---

## 2. 逐文件接口（类 / 函数 / 职责；只抽象）

### 2.1 顶层

**`hybrid_memory/__init__.py`** — 对外极小面
- `__version__`：包版本（与 `pyproject.toml` 同步）
- `from .service.service import MemoryService`、`from .config import Cfg, Settings`
- 不导出 store/dispatch 细节；`build_default_service` 走 `transport.bootstrap`（延迟导入）

**`hybrid_memory/server.py`** — 兼容入口 shim（3 行）
- `main()`：`from .transport.bootstrap import main`；`python -m hybrid_memory.server` 契约不变（H1/H39）

**`hybrid_memory/config.py`** — 配置唯一真源
- `Cfg`（dataclass）：引擎动力学与机制开关；**新增** `cap_c`（默认 200）、`cap_a`（默认 2000，H11/H12）
- `Settings`（dataclass）：进程级——`project/port/model/task_capacity/pipeline/agent_*/state_dir`
- `resolve_pipeline(env) -> "opencode"|"legacy"`：唯一读 `MEMORY_PIPELINE` 的地方
- `resolve_settings(argv, env) -> Settings`：`CLI > env > 默认`，唯一解析点；import 时不求值
- `load_env_key(project) -> str`：`.env` 读取（现 `server._load_env_key` 迁入）

**`hybrid_memory/errors.py`** — 错误分类（新增，H24）
- `MemoryError` 基类；`Rejected(code, message)`（4xx）；`Degraded(code, detail)`（外显降级）；`Fatal(code, detail)`（拒绝启动）
- `http_status(code) -> int`：错误码 → 状态码唯一映射表

**`hybrid_memory/telemetry.py`** — 观测面（新增）
- `Counters`：`n_missed/n_rejected/n_ungrounded/n_candgen_fail/n_dropped/n_shadow_dropped/n_pool_truncated/n_dead_tasks`
- `health_view(service) -> dict`：现字段集冻结（只许加字段，A7）+ `semantics` 健康段（H27）
- `signals_view(service) -> dict`：现字段集冻结
- `log_event(kind, **fields)`：JSON 一行到 stderr；`warn_once(key, message)`：限频告警

### 2.2 `core/` — 领域层（纯逻辑，无 I/O）

**`core/types.py`** — 数据类型与契约
- `Pool(Enum)`：`CANDIDATE/MEMORY/ARCHIVE`（含定值序列化）；`Memory` 全字段（**新增** `archived_at`，H12）
- `Event`、`Query`、`Tension`、`Retrieval`（字段集冻结，增删需 ADR）
- `is_visible(m)`：唯一"可服务"判定
- `MemorySemantics` / `FeedbackSemantics` / `ConsolidationSemantics`（Protocol）

**`core/interaction.py`** — 抽取输入类型（现文件原样迁入，24 行）
- `InteractionUnit`、`InteractionWindow`

**`core/triggers.py`** — 零 LLM 触发扫描（现文件迁入，82 行）
- `is_correction/is_dissatisfaction/scan_unit` + 正则常量 + `LONG_TURN_CHARS`
- 语义：纯调度提示，永不作为事实证据；改正则需跑安全测试（H18）

**`core/dynamics.py`** — 动力学（新增，从 engine/maintenance 抽出）
- `decay(m, t, cfg)`：`V ← V·e^(−λΔt)` + 保留地板
- `credit(m, weight)`：useful/shadow 命中入账
- `promote/demote/archive(m, cfg)`：滞回与归档判定
- `retention_scale(m, cfg, t)`：salience 保留系数
- `pinned_ids(engine) -> frozenset[int]`：被未决张力/人审引用、禁止淘汰的 id（H14）
- `evictable(pool, mems, cfg, pinned) -> list[int]`：纯函数，给出应淘汰 id，不删
- `overflow_policy(mems, cfg, pinned) -> list[int]`：C 取 V 最低、A 取最旧、M 溢出拒收（H11/H12）

**`core/ingest.py`** — 事件入库：`run_ingest(eng, events, t)`（指纹去重/tau_dup 合并/supersede/张力登记）

**`core/retrieval.py`** — 检索
- `lexical_scores(texts, query)`、`_prior(pool, cfg)`
- `run_retrieve(eng, query, t, budget_tokens, passive)`：质量门 θ → 压制对 → RRF 融合 → π 先验 → 预算截断
- `suppression_pairs(...)`：过相似未入选对 → 张力候选

**`core/tension.py`** — 张力台账（新增，从 maintenance/engine 收拢）
- `TensionBook.register/pending/emit_due/apply_verdict/aggregate/follow_chain`
- 四类裁决后果：synonym→merge、update→新替旧、contradiction→聚合、collision→都留

**`core/maintenance.py`** — 维护回路：`run_maintenance(eng, t)`（老化→滞回→归档→shadow 结算→冲突发射）；`settle_shadow(eng, t)`（H32）

**`core/consolidation.py`** — 巩固回路：`maybe_consolidate(eng, t)`；`admit_reflection(eng, event, chosen, t)`

**`core/confidence.py`** — 置信折损：`discount_to(m, t, cfg)`、`projected(m, cfg)`

**`core/signals.py`** — 有界信号队列：`Signal`、`SignalQueue(cap, on_emit)`；`emit` 语义：`on_emit` 返回非 None = 已持久交接

**`core/engine.py`** — 引擎门面（唯一对外 API）：`observe/retrieve/step/feedback/propose/add_reflection/submit_verdicts/submit_relevance/credit_shown/report_miss/report_unit/miss_key/add_tension/pool_sizes/drain_signals`

### 2.3 `store/` — 持久化层

**`store/schema.py`** — 建表与迁移（新增，H10）
- `SCHEMA_VERSION`、`open_db(path)`（WAL、busy_timeout）、`ensure_schema(conn)`、`migrate(conn)`；高版本 → `Fatal`

**`store/evidence.py`** — L0 证据库（现 `logstore.py`，642 行）
- `append_unit/add_unit`（只追加；同 id 异内容 → `Rejected`）；`get/count/exists/recent_ids/unit_context/next_position`
- `search`（FTS5-trigram + 向量 RRF k=60 + LIKE 兜底）；`timeline/mention_counts/stats`
- `window(unit_ids, max_chars, before)`：**唯一**全文回展通道，返回 `truncated`
- `work/pending_units/work_stats/save_work_result/fail_work/finish_work`：逐单元恢复；`capture_receipt`
- `retention_report()`：体积/最旧单元（H13 只告警）；`close()`

**`store/tasks.py`** — 任务库（现 `taskstore.py`，613 行，H7 合并）
- `transaction()`（`BEGIN IMMEDIATE`）；`enqueue`（`(kind,key)` 去重合并；满 → `Degraded("queue_full")`，H9）
- `checkpoint()/save_checkpoint(state)`：revision CAS，唯一权威状态（H6）
- `claim/store_result/retry/finish`：单状态机 + `KindPolicy` 参数
- `unit_receipt/remember_capture/apply_captured_effect/apply_operation`
- `rule_snapshot/rule_report/disable_rule/rules_for`；`workflow_trace`（18 条/24KB，超限 `Degraded`）
- `pending_reviews/queued_counts/stats/semantic_stats/close`

**`store/state.py`** — 快照（从 server 抽出）
- `STATE_KEYS` / `MEMORY_FIELD_DEFAULTS`；`RestrictedUnpickler`（RCE 防护，保留）
- `dump_state/load_state`；`is_corrupt/quarantine`（坏快照隔离，`snapshot=quarantined`）

### 2.4 `dispatch/` — 派发层（唯一后台循环）

**`dispatch/policy.py`** — 策略表（新增，H7/H8/H25）
- `KindPolicy(kinds, claim_from, daily_cap, max_attempts, on_exhausted, lease_s, backoff)`；`POLICIES`；`policy_for(kind)`；`assert_consumers(appliers)` 启动自检

**`dispatch/worker.py`** — 唯一工作循环：`DispatchWorker(service, runner, policies, idle_s)`；`start/stop/notify/process_once(limit)/stats`
- `process_once`：`recover_expired → list_tasks → claim → run_agent → validate → apply → finish`

**`dispatch/effects.py`** — 效果落地（新增，H21）
- `Applier` 类型；`EFFECTS` 表（9 种 kind 全覆盖）；`effect_transaction(service, mutate)` 唯一入口
- 每个 applier：`validate → mutate → checkpoint`，失败一律 `Degraded` 外显

### 2.5 `agents/` — 抽取协议（现 `agent/trio.py` 327 行拆分，H4）

**`agents/protocol.py`** — 运行器契约：`AgentRunner(Protocol)`（`run/available`）；`AgentTimeout/AgentProtocolError`；`MAX_ATTEMPTS=5`；返回已解析 JSON 对象，否则协议错误（H15）

**`agents/opencode.py`** — 唯一 OpenCode 实现：`OpenCodeRunner(project, executable, timeout)`；`opencode run --pure --agent <name> --format json`；cwd=仓库根；`DYNAMICS_MEMORY_INTERNAL_AGENT=1` 防递归；stdin 关闭；`_event/_parse_text`

**`agents/payload.py`** — 任务 → 载荷：`build_payload(kind, service, row)`（窗口 12k，超限 `Degraded` 不截断，H16）；`memory_snapshot`（500 上限确定性 id 序，H17）；`rules_for`（作用域规则注入）

**`agents/hauler.py`** — 候选校验：`validate(reply, row)`（结构、`source_unit_ids ⊆ 窗口`、长度、去重；空列表合法）

**`agents/selector.py`** — 决定校验（安全核心，H18）：`Decision` 类型；`validate`（每候选恰一 action；`target_id` 存在；UPDATE 门；截断禁猜 H17）

**`agents/reviewer.py`** — 审查校验（H19）：`validate`（diagnosis/rules/repair_candidates/rule_reviews）；`scope_of`（`project|entity:<literal>`）；rule_reviews 引用范围校验

### 2.6 `semantics/` + `llm/` — 判裁与模型客户端

**`semantics/provider.py`** — 判裁契约（新增，H27）：`SemanticsProvider(Protocol)`（`judge/relevant_set/consolidate/health`）；`ProviderHealth(ok/last_error/calls)` 进 `/health`

**`semantics/llm.py`** — 现行实现：`LLMSemantics(client, model)` + 解析容错

**`semantics/prompts.py`** — prompt 模板（从实现抽出）：`JUDGE_SYS/RECOGNIZER_SYS/CONSOLIDATE_SYS + render_*`

**`semantics/stub.py`** — 确定性实现（现 `semantics/real.py`）：`RealChatSemantics`；测试与离线唯一可跑实现

**`llm/client.py`** — 通用 chat 客户端（现 `llm.py`，118 行）：`chat`（磁盘缓存）/`chat_messages`（tools 直连）/`ZhipuChatError`；`BASE_URL` 调用时求值（改掉 import 时求值）

**`llm/cache.py`** — 响应缓存：`cache_lookup/cache_store`（原子写）

### 2.7 `service/` — 编排层（现 server.py 66 方法分家，H2）

**`service/service.py`** — 门面：组装依赖、持有 RLock；对外方法转发，不放业务实现；`lock/current/attach_dispatch/notify`

**`service/lifecycle.py`** — 生命周期：`build_service/recover_or_init/ensure_healthy/save/snapshot_status/corrupt_file_exists/start_unit_recovery/stop_unit_recovery`

**`service/observe.py`** — 观察回路：`observe/process_pending_units/process_unit`（先落 L0 幂等，再扫描，再三 agent 交接；legacy 才走 candgen）

**`service/recall.py`** — 检索回路：`recall/recall_main/recall_result/context_lines`（`[未确认]/[待人审冲突…]/[项目状态汇总]` 前缀 + contested 1+3 上界 H29）；`causal_memory_ids/causal_tensions`

**`service/feedback.py`** — 延迟记账：`feedback`（幂等 + 锁外判裁）

**`service/operate.py`** — agent 操作面：`propose/resolve/diagnose/validate_proposal/durable_propose`；trio 下三入口 `Rejected("direct_write_disabled")`（H35）

**`service/tools.py`** — 只读工具面：`log_search/log_timeline/log_stats/log_window`（`before` 因果上界 + 预算）

**`service/review.py`** — 冲突台账：`human_reviews/decide_human_review`（幂等）；`conflict_ledger` 合并读模型（H14）

**`service/budgets.py`** — 预算：`open_budget/close_budget/admit`；`MAIN_WINDOW_CAP`；预算对象不可变

**`service/context.py`** — 调用上下文（现 `investigation_context.py`，19 行）：`InvestigationContext`；`SignalClosed/CausalViolation`

### 2.8 `guards/` — 横切校验（新增包）

**`guards/provenance.py`**：`validate_sources/sources_known/ensure_within_before`（存在 + 因果上界内）
**`guards/grounding.py`**：`content_grounded`（2 汉字/≥4 标识命中/≥8 标识全出现）；`cited_text`
**`guards/redact.py`**：`redact_secrets` **唯一**实现（legacy 侧 re-export，H5）
**`guards/bounds.py`**：`validate_request_id/require_batch_size/clamp` + `MAX_*` 常量

### 2.9 `transport/` — 传输层

**`transport/http.py`**：`Handler(do_GET/do_POST/reply/body)`；`ROUTES` 声明式表（含 trio 禁用表，H35）；`serve`；统一错误映射（H24）
**`transport/auth.py`**：`load_or_create_token`（0600）；`review_token`；`authorized`（`compare_digest` + 能力位，H36）
**`transport/dto.py`**：`parse_body`（Content-Type/4MiB）；`opt_int/req_str`；`observe_payload/feedback_payload`；`validate_request_id/capture_fingerprint`
**`transport/bootstrap.py`**：`parse_args/resolve_settings/build_default_service/main/install_signal_handlers`
**`transport/review_cli.py`**：human CLI（现 `human_review.py`，H37 纠正归类）

### 2.10 `embed/` — 嵌入（保留）
- `embed/base.py`（`cosine`、`Embedder`）；`embed/cache.py`（`SqliteEmbeddingCache`）；`embed/zhipu.py`（分块/缓存键/离线模式，`ZhipuEmbeddingError`）

### 2.11 `legacy/` — 冻结旧管线（H5/H23）
- `legacy/candgen.py`（候选类型 + ChatGenerator）；`legacy/prompt.py`（redact 改 re-export `guards.redact`）；`legacy/worker.py`（SignalWorker，裸引擎用）；`legacy/investigator.py`；`legacy/inline.py`；`legacy/loop.py`（AgentWorker）；`legacy/__init__.py`（`DEPRECATED=True` + 启动 `warn_once`）
- 兼容 shim（H1）：`hybrid_memory/candgen/`、`hybrid_memory/worker.py`、`hybrid_memory/agent/{inline,loop,investigator}.py`、`hybrid_memory/server.py` 保留为一行 re-export

### 2.12 `tests/` 与 `eval/`
```
tests/
├── conftest.py                    共享夹具（P2 先行抽出）
├── unit/
│   ├── test_core_dynamics.py      衰减/滞回/淘汰/pinned（原 test_smoke 拆分）
│   ├── test_core_retrieval.py     质量门/压制/RRF/先验/预算
│   ├── test_core_tension.py       登记/裁决/聚合/迟到信用链（原 test_follow_chain）
│   ├── test_core_consolidation.py 巩固触发/reflection 入库
│   ├── test_core_triggers.py      原 test_triggers（升级安全测试，H18）
│   ├── test_store_evidence.py     原 test_logstore
│   ├── test_store_tasks.py        原 test_taskstore + durable 机制部分
│   ├── test_store_state.py        原 test_snapshot_format
│   ├── test_semantics.py          判裁解析与容错
│   └── test_import_boundaries.py  新增（A5）
├── integration/
│   ├── test_service_observe.py    原 test_observe_recovery + test_capture_delivery
│   ├── test_service_recall.py     原 test_late_credit + test_source_authenticity
│   ├── test_service_review.py     人审闭环（原 test_server 相关用例）
│   ├── test_http_contract.py      原 test_server（路由/鉴权/状态码/快照，A7/A8）
│   ├── test_dispatch_recovery.py  原 test_semantic_recovery + test_durable_tasks（A10）
│   └── test_legacy_pipeline.py    原 test_ouroboros + legacy 用例
├── protocol/
│   ├── test_agent_protocol.py     原 test_trio_protocol（fake CLI）
│   └── memory_bridge.test.ts      原位（bun）
├── characterization/              P3 冻结套件（P6 末删除，A4）
└── test_acceptance.py             断言 acceptance_check.py 全 PASS（H41）
```
`eval/harness/` 收纳离线脚本（H40）；`eval/tide/` 一行不改（H39）。

---

## 3. 依赖规则与不变式（每条可机械检查）

| # | 不变式 | 检查方式 |
|---|---|---|
| I1 | `core/` 零越层 import；`agents/` 不碰 `store/` | `test_import_boundaries.py`（A5） |
| I2 | `MEMORY_PIPELINE` 只在 `config.resolve_pipeline` 被读 | 已有测试保留 |
| I3 | 每个持久 kind 都有 applier | `assert_consumers` 启动自检（A6） |
| I4 | 每个池都有上界 + 确定超限动作 | `cap_*` 齐全性测试 + `overflow_policy` 单测（A9） |
| I5 | 效果与 checkpoint 同事务 | `effect_transaction` 唯一入口（A10） |
| I6 | `/health`、`/signals` 字段只增 | 契约快照测试（A7） |
| I7 | 文档产品断言有据 | 验收"断言→证据"表（A2） |

---

## 4. 迁移映射（现状 → 目标：改 / 增 / 删 / 移）

| 现状 | 目标 | 动作 |
|---|---|---|
| `server.py`(2091) 66 方法 | `service/*`(10) + `transport/*`(5) + `store/state.py` + `guards/*`(4) + `telemetry.py` + `errors.py` | **拆**（P4/P5 纯搬运） |
| `server.py` 文件本身 | 3 行 shim | **改** |
| `logstore.py`(642) | `store/evidence.py` + `store/schema.py` | **移 + 抽** |
| `taskstore.py`(613) 两套状态机 | `store/tasks.py`(单状态机) + `dispatch/policy.py` | **并**（P3） |
| `agent/trio.py`(327) | `agents/*`(6) + 效果入 `dispatch/effects.py` | **拆**（P6） |
| `worker.py`/`candgen/*`/`agent/{inline,loop,investigator}.py` | `legacy/*` + 一行 shim | **移**（P1） |
| `agent/human_review.py`(50) | `transport/review_cli.py` | **移**（H37） |
| `semantics/{llm,real}.py` | `semantics/{provider,llm,prompts,stub}.py` | **拆 + 增**（P6） |
| `llm.py`(118) | `llm/{client,cache}.py` | **拆**（P6） |
| `interaction.py`(24)/`investigation_context.py`(19)/`triggers.py`(82) | `core/interaction.py`/`service/context.py`/`core/triggers.py` | **移**（P1） |
| `config.py` | +`Settings`/`resolve_settings`/`cap_c/cap_a` | **改**（P2） |
| — | `errors/telemetry/dispatch/*(3)/store/schema/guards/*(5)/ARCHITECTURE/pyproject/Makefile/CI/docs/{index,architecture}/decisions/*` | **增** |
| `eval/*.py` 离线脚本×4 | `eval/harness/` | **移**（P6 低优先） |
| 测试 23 文件/333 函数 | `tests/{unit,integration,protocol,characterization}` | **重组随迁**（H38） |

**包内新增文件**：顶层 2（errors/telemetry）；`core/` +2（dynamics/tension）；
`store/` +2（schema/state）；`dispatch/` +3（全新包）；`agents/` +6；
`semantics/` +2（provider/prompts，llm/stub 为改名）；`llm/` +2；
`service/` +10（占大头，全是 server.py 的分家）；`guards/` +4；`transport/` +5；
`legacy/` +7 —— 共约 45 个文件，其中净新增逻辑不到 10 个，其余全是搬运。

**明令不动**：`core/` 算法语义（H26）、幂等键语义（H22）、因果上界 `before`、RRF 融合、
插件 outbox（H33）、pickle 白名单、`eval/tide/`（H39）、`.opencode/agent/*.md` 语义、
`/health` 字段语义（H34）、UPDATE 门（H18）、直写 403（H35）。

**删除清单**：本次**零删除**（H23）。`tests/characterization/` 在 P6 末删除（临时套件，
唯一的删）。

---

## 5. 实施阶段（P0–P6：每阶段准入/准出/禁止）

> 原则：任何时刻 main 可用（三门全绿）；PR 粒度 = "一模块 + 它的测试"（H38）。

### P0 冻结与基线（0.5–1 天）
- **做**：实现 `analysis/acceptance_check.py`（A2–A10 机械部分）；给历史 docs 加状态抬头；
  写 `docs/index.md`；冻结 `/health`、`/signals`、错误码、trio 禁用表的**现状快照**（A7 基线）。
- **准出**：三门在现状上全绿（基线）；PENDING 表发布。
- **禁止**：改任何产品代码。

### P1 纯搬运（1–2 天）
- **做**：`interaction/triggers/context` 移位；`worker/candgen/agent{inline,loop,investigator}` → `legacy/` + shim；
  `human_review.py` → `transport/review_cli.py`（H37）；`guards/redact` 抽出 + legacy re-export。
- **准出**：`pytest` 全绿；`git diff --stat` 只有改名 + shim（搬运证明）。
- **禁止**：改任何函数体（`redact` re-export 除外）；动测试一字。

### P2 新骨架（1–2 天）
- **做**：`errors/telemetry/guards/{provenance,grounding,bounds}/store/schema/dispatch/policy`
  空壳（函数签名 + `NotImplementedError` 或透传）；`config` +`Settings/cap_c/cap_a`（只加字段，
  不启用新行为）；`conftest.py` 共享夹具抽出；`test_import_boundaries.py`（先对现状标红，
  P4/P5 消红——红是预期的，CI 设为 allow-fail 并显式列出）。
- **准出**：pytest 全绿（新测试 allow-fail 除外）；新模块 import 无环。
- **禁止**：把旧调用切到新壳上（P2 只搭架子不通电）。

### P3 合并状态机（2–3 天，风险最高）
- **做**：`tests/characterization/` 冻结现状（任务状态序列/revision 序列/效果计数）；
  `store/tasks.py` 单状态机 + `dispatch/policy.py` 策略表；调用点逐个切换
  （server → trio → loop），每切一个跑 characterization diff。
- **准出**：characterization 逐字节一致（A4）；旧 `claim_semantic/*` 方法删除；
  测试搬入 `tests/unit/test_store_tasks.py`。
- **禁止**：改耗尽语义（H8 照现状抄：调查类 dead、语义类重排，由策略表表达）；
  动 `core/` 一字。

### P4 拆 server 上半：service 回路（2–3 天）
- **做**：`service/{service,lifecycle,observe,recall,feedback,review,budgets}.py`；
  `store/state.py`（快照搬运）；`telemetry.health_view/signals_view` 接管；
  `overflow_policy` + `cap_c/cap_a` 接线（A9）；contested 上界 H29 修掉。
- **准出**：pytest 全绿；import 边界测试消红一半；`test_service_observe/recall/review` 就位。
- **禁止**：改 HTTP 行为（transport 还没拆，路由原样）；调参（H26）。

### P5 拆 server 下半：transport + operate（2 天）
- **做**：`transport/{http,auth,dto,bootstrap}.py`；`service/{operate,tools}.py`；
  `dispatch/{worker,effects}.py` 接管后台循环；`server.py` 缩为 3 行 shim；
  `test_http_contract.py`（A7/A8 快照）；token 0600 测试（H36）。
- **准出**：`server.py` ≤ 10 行；import 边界全绿；`python -m hybrid_memory.server` 与旧行为一致
  （smoke：起进程 → observe → recall → save → 重启恢复）。
- **禁止**：改任
...[truncated 1030 chars]