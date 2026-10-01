# 第 2 批计划与验收：sidecar 语义任务的持久交接与效果回执

> **基点**：第 1 批 PR #2 已由仓库方合并，当前 main 为 `696f3a745686bc105c0ba84c891ccfef16f675c4`。已核对合并树与 PR #2 工作树一致；本批在固定会话分支上以此为基点，另行提交 PR。

## 已核对的现状与调用方（基于 main 696f3a7，PR #2 的合并树）

- 裸 `MemoryEngine` 的 `SignalQueue` 是有界内存队列；sidecar 仅通过 `on_emit` 将 `recall_miss`、`extract_due` 同步写到 `TaskStore`。这些调查任务属于既有独立持久通道，不应换新协议。
- 语义信号来源：`conflict_pending` 在 maintenance 与检索压制路径发出；`maintenance_due` 在 consolidation 发出；`feedback_pending` 由 `engine.feedback` 发出，载荷中是带 Memory 对象引用的 `Retrieval`，不能直接 JSON 化；`thin_recall` 只是计数遥测。`SignalWorker.process()` 用 `take()` 从内存队列摘取前三类，LLM 判定在服务锁外，效果在锁内；失败回到同一内存队列。裸引擎/仿真与 tests 依赖该接口，应保留内存语义。
- sidecar 在单元效果确认后立即调用 `worker.process(t)`，并在 `/feedback` 内同步调用它；进程终止或两次调用之间的信号会丢。`/feedback` 会把 Retrieval 标记 `feedback_sent`，却不原子存入持久待办。`_retrievals` 仅在 checkpoint/`state.pkl` 中保留；后续 `report_miss(recognizer_none)` 依赖 recognizer 的最终结果。`/recall`、`/resolve`、独立任务操作也可能产生或改变语义信号。CLI `--no-agent` 仍应恢复语义任务。
- `tasks.sqlite` 已有 revision CAS、事务内 checkpoint 与操作回执，但现有调查任务的领取器/容量/去重规则不可不经筛选直接用于语义任务。`log.sqlite` 的 L0 工作项属于第 1 批跨库协议。

## 本批目标与非目标

目标：sidecar 中的 `conflict_pending`、`feedback_pending`、`maintenance_due` 在产生时有持久责任；重启后重试可观察；语义判定允许重复执行，但同一工作项的**引擎效果至多一次**且 checkpoint/回执/确认有可恢复中断点。保持模型调用在服务锁外；继续提供裸引擎的原有内存 `SignalQueue` 行为。

不顺带实现：插件可靠重传、所有 HTTP 请求的 request-id 去重、调查任务重写、真实模型 exactly-once、多 sidecar 并发多主或原始旧易失信号的历史补发。`thin_recall` 无引擎效果，保持计数遥测并明确无持久保证；如复核发现它参与决策，必须调整范围再实施。

## 拟定设计，实施前核定

1. 列出全部 sidecar 发射与消费调用点、反馈对象/检索 ID 的持久边界，明确旧 checkpoint 与新 SQLite 状态的升级路径。不反序列化任意未经校验的 JSON/对象，不把 Retrieval/Memory 实例直接存 JSON。只存稳定的 retrieval ID、入选 memory ID、问题/答案和必要的反馈快照，在加载的权威 checkpoint 上重新绑定，并防止与旧对象重复记账。
2. 将 sidecar 的语义发射接入 `tasks.sqlite` 的 durable 工作存储；发射和对应的引擎改动/`feedback_sent`/checkpoint 必须一起提交。特别是第 1 批 `apply_unit()` 的效果、语义待办和回执要同事务；非单元路径也逐一补齐事务责任，不能只在 `on_emit` 单独 enqueue 后才保存修改过的池。
3. 语义任务读取/领取/模型输出缓存/效果确认采用持久状态及有期限的租约；不同消费者只能处理自己的 kind，保留原调查队列的容量/预算/去重语义。回报时用 CAS 与幂等回执，将效果、checkpoint、回执和 done 同事务更新；提交失败则重试，提交成功而调用方失联时重启只看到 done，不重放效果。失效租约或较旧模型结果不得写入较新 checkpoint。
4. 去除 sidecar 中被新通路取代的易失摘队与失败回队路径；裸引擎继续使用现有 `SignalWorker`/`SignalQueue`。后台扫描独立于调查员是否开启，失败有退避且不静默丢弃，`/signals` 展示 pending/running/ready/applying/done、退避计数与最近错误；不自动丢弃语义任务。
5. 检查 feedback 幂等返回和 recognizer_none 衍生的调查任务交接：回报 0 个有用结果、调查任务入队、n_missed 计数要与语义效果遵守一致的失败/恢复协议，不能恢复时反复生成遗漏信号。

## 可执行验收（真实 SQLite / HTTP / 进程重启）

- 对反馈任务在发射事务提交后、模型领取后、模型结果存盘后以及效果与 checkpoint/done 同事务提交后注入 `os._exit` 并重启；对冲突结果保存后与巩固信号交接后亦注入进程退出；三类任务均单独验证数据库重启；已提交效果不重复，未提交任务可恢复，持久化模型结果不必再调用模型。
- 容量满、数据库插入/更新/回执失败、处理超时与重复领取、提交确认不明、并发 `/feedback`、反馈中 Retrieval 身份与来源关系、LLM 错误与合法空结果；各场景不丢待办、不双计命中/裁决/反思，失败可见。
- 旧 `tasks.sqlite`/`log.sqlite` 和 `state.pkl` 安全升级，无旧日志批量重放；`--no-agent` 的 sidecar HTTP 重启烟测使用本地假模型。完整 Python/TIDE/静态检查与 PR 差异审阅；注明未经真实 OpenCode/远程模型及断电验证。
- 发布前配套备份整个状态目录（SQLite 与 WAL、快照）；不得只回滚一库。记录旧程序不理解新语义工作项时的降级风险、回滚丢失备份后数据的问题及前向修复策略。

实施时若发现上述设计要求在本批内无法闭环，先缩小并重新确认范围，不能用只持久化排队、仍易失地应用效果来宣称语义任务可靠。

## 实施核对、实际契约与限制

- 未另造任务状态机：继续使用既有 `tasks` 的 pending → running → ready → applying → done、lease/token、checkpoint CAS 与 `operations` 回执；`AgentWorker` 的扫描/过期处理仅面向调查 kind，语义任务使用相同表中自己的 kind，互不误领。语义任务不适用调查员每日配额，不设置自动丢弃上限；持续模型故障在有退避的 pending/ready 中保留，容量可能耗尽。`TaskStore` 增加非单元服务效果、语义任务领取/保存结果/原子完成的方法。
- 第 1 批 L0 效果事务把三种语义信号和调查任务一并交接；主 `/recall` 与 `/feedback` 的引擎修改、检索 registry/feedback_sent、语义任务与 checkpoint 在任务库同事务落地，失败时恢复原对象/计数。已保存的模型判定在 ready 状态复用；语义效果、checkpoint、回执、done 在**同一个任务库事务**中提交，不存在任务库内部「效果已提交、done 未提交」窗口。信号含稳定的入选 memory id 和 `/recall` 实际送给下游的文本快照，不把 Memory/Retrieval 对象 JSON 化；checkpoint 保留原始对象关系，未完成的反馈检索不会被普通 registry 轮换挤掉。
- 原 sidecar `SignalWorker.process()` 易失语义消费被 SQLite 消费替换；裸引擎/仿真继续使用它。`thin_recall` 仍是易失遥测，由扫描器消费，不计入可靠任务。后台恢复器在 L0 因容量/DB 错误退避时仍扫描语义任务，免得两类任务互相卡死；模型调用在服务锁外。`/signals.semantic` 展示状态计数、退避数与最近五个错误，`/feedback` 在工作仍未完成时返回 `pending:true`。
- 已检查因模型执行期间发生的后续变更：冲突产物记录 tension 的观察版本、巩固产物记录源记忆版本；可检测的过期产物不直接写旧效果，而是对仍有效的来源另交接新待办（同事务）。令牌过期也拒绝迟到提交。这个检查并非多主一致性机制，不保证在未版本化的任意外部对象修改下捕获所有语义变化。
- 对旧库仅使用 `tasks` 已有 schema 与旧 checkpoint 结构；新增方法不批量重放既有易失队列，也不要求更新历史快照格式。升级前停机并备份同一目录的 `log.sqlite`、`tasks.sqlite` 与 WAL、`state.pkl`；回滚只能成套恢复升级前副本，备份之后接受的任务/单元会丢失，应优先前向修复。旧程序不认识新语义任务 kind，不能直接降级后继续写同一组数据库。语义任务在 `tasks.sqlite` 中保存用户问题/答案与入选记忆文本快照（已完成任务也保留），应按原始 L0 的敏感数据保护标准备份与控制访问；本批未加入保留期/清理策略。真实远程模型/OpenCode L3、插件请求可靠重传、异常断电/磁盘损坏与多 sidecar 多主仍未验证。

## 差异审阅记录

- 移除 sidecar 对内存 `SignalWorker.process()` 的效果提交调用；裸引擎 worker 不改算法。未引入新语义表或并行任务状态机，调查 worker 只增加 kind 隔离；已核对 `/observe`、`/recall`、`/feedback`、`/signals`、`--no-agent` 与旧任务消费者。历史架构说明文档记录的是当时状态，不篡改旧批次验收记录；更正现行模块注释。
- 自审发现并修正：较早 L0 因容量失败会挡住语义扫描；旧判定遇后续 tension/source 更新可能误应用；结果陈旧重新排队在满容量下会自锁；反馈 registry 轮换可能挤掉已接受的任务来源；后续池更新会改变已展示的反馈文本（现以 `/recall` 时原文快照判定，旧快照无字段时退化为当前文本）；空检索误报 pending；跨 SQLite JSON 的 tuple/list 差异使冲突对去重失效。分别以故障/回归测试锁定。

## 本地回归记录

- `tests/test_semantic_recovery.py`：真实 SQLite/HTTP；子进程 `os._exit` 于 L0 语义信号发出后、任务领取后模型前、结果保存后效果前、效果/checkpoint/done 提交后；重启核对单次信用、反思、已保存结果复用；注入 SQL 回执/调查交接/单元交接失败、队列容量满、过期租约、并发反馈、过期 verdict、新结果回队、合法空反思与后台队列互锁解除。外部语义模型/嵌入均为测试替身。
- Python 3.11.2 / NumPy 1.26.4 与 2.4.6 下各完成全套 `339 passed`，独立 TIDE `8 passed`；22 项新增语义恢复故障测试通过，阶段性恢复测试组合额外重复三轮，每轮 `33 passed`，Ruff F/E9、`compileall`、`git diff --check` 通过。无 Bun，插件 TS 测试未运行且本批未改插件。不能以测试通过宣称生产零缺陷。
- 另使用真实 sidecar CLI `--no-agent` 接本地 mock LLM/embedding HTTP（非远程真实模型）：`/observe` 得到候选、`/recall` 返回记忆、`/feedback` 完成一次语义归因且持久任务 done；正常停止并重启，`/signals` 仍显示原 L0 done、语义 done 且无 pending。子进程 `os._exit` 验证的是进程中断，不是异常断电/磁盘损坏认证。
