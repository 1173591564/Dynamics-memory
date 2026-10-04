# 调查任务持久化、重试与幂等写回

> 状态：现行（任务机通用契约）· 第三批调查任务持久化、重试与幂等写回。

第三批覆盖 **AgentWorker 调查任务**（`MEMORY_PIPELINE=legacy`），默认种类为
`recall_miss`、`extract_due`，执行器为 `legacy/inline.py` 的进程内只读工具循环。
**默认管线（opencode）不使用该执行器**：三 Agent 任务（`hauler_due`/`selector_due`/
`reviewer_due`）与语义任务共用同一 `tasks.sqlite` 状态机，本页的状态、租约与幂等
契约对两条管线同样适用。这是本地服务/SQLite 的正确性修复，不是“模型恰好执行一次”，
也不是 L3 真实 agent 验证。

## 状态与落盘时点

状态目录新增 `tasks.sqlite`（WAL、`synchronous=FULL`）：

```text
pending → running → ready → applying → done
             │                  │
             └→ pending         └→ ready       有限次数重试
                  \                /
                   └──── dead ────┘            耗尽，保留产物与错误
pending → skipped                              已完成任务的 TTL 去重
```

- 信号发出时，通过 `SignalQueue.on_emit` **直接提交 SQLite 并返回任务标识，不进入内存队列**。
  没有启动调查员、没有调用 `/save`，也不影响已接受任务的持久性。
- 调查任务只存 SQLite，不再写入有界 SignalQueue。语义信号和 thin_recall 遥测仍走内存队列；健康接口通过 SQL 汇总待处理任务，不维护另一份镜像。
  `GET /signals` 新增 `tasks` 状态计数和 `checkpoint_fault`。
- `pending` 且从未领取的同 `(kind, key)` 任务可以合并；合并提升 payload version 和时间步。
  领取校验版本，防止用旧 payload 算出的因果界领取已更新的任务。
- 首次领取冻结 `before`、`origin`。进入执行/重试后的任务不再接受新事件合并；同 key
  新事件另建任务。在旧任务执行期间到来的新事件，不会因为旧任务刚完成而被 TTL 去重吞掉。
- 同一任务的后续重试沿用原 `before/origin`，不随重启时钟或新的 `before_for` 配置放宽。
- 入队还保留已分配 memory ID 的高水位。即使尚未保存的旧记忆在崩溃后丢失，
  持久任务的旧引用也不能因编号重用指向别的事实；缺失的旧记忆不是自动恢复的。

任务领取、每日调查次数增加及领取时的引擎 checkpoint 同事务。
调查完成后，**产物与当时的引擎 checkpoint 同事务提交**，再进入应用阶段；因此产物
所引用的、领取后新增的记忆不会因为只有旧快照而丢失。产物已保存就不再调用调查模型。

## 领取、租约和重试

- SQLite 写事务串行化领取，同一任务只能有一个有效 token。
- 租约默认 `budget.timeout_s + 60` 秒，可以通过 `AgentWorker(lease_s=...)` 配置。
  没有后台续租；自定义执行器必须有超时，任务超过租约会失去提交权限。
- 进程消失后不会立即抢占尚有效的租约；到期后，下一次 `process_once()` 将其恢复为
  `pending` 或 `ready`，或在次数耗尽时转为 `dead`。
- 每次调查尝试生成新信号号。迟到 HTTP 调用既要过信号准入，也要通过当前 task token
  校验；写回在慢 embedding 后再次校验租约，过期写入回滚。
- 调查失败默认最多 2 次，产物应用默认最多 3 次，两种次数分别持久化。
  `last_error`、下次可执行时间和已保存产物保留在任务记录中。
- CLI 默认从 2 秒起指数退避，上限 300 秒（`--agent-retry-delay`）。Python API 为兼容
  现有同步调用默认 `retry_delay_s=0`；后台轮询间隔仍生效。
- 每日上限按服务器本地日期记录调查**尝试**次数，不是所有 LLM/embedding 请求数。
  重启不重置。`ready` 任务只重试应用，不消耗新的调查次数，也不会被当天调查上限阻塞。
- 完成任务的 TTL 去重记录保存在数据库；它是按 key 的策略，不做新信息的语义判别。
- 单个任务失败被隔离，未领取的其余任务不受影响。`stop()` 超时不再谎报线程已经停止，
  也不会通过 `start()` 另起重复执行线程；已保存产物可留待后续继续应用。

## 效果与回执：同一个事务

`operations` 以 `(task_id, canonical_operation_hash)` 为唯一键。每个操作在服务锁下：

1. 检查租约和 checkpoint revision；命中回执则直接返回原结果，不再做副作用。
2. 运行原有 propose/resolve/diagnose 路径，没有特权记忆池。
3. 把 **引擎 checkpoint 与操作回执放进同一个 SQLite 事务**。
4. 提交后才确认本次操作；所有条目处理完，再把任务标记为 `done`。

所有入口的一次 proposal 批次最多 50 条；超限明确失败，不静默截断后把任务标记完成。
proposal 按实际服务字段规范化文本、来源、salience、entity、supersedes，消除 HTTP
和最终 JSON 的默认值/别名差异；每条 proposal 分别记录回执。诊断按类型与规整后的
note 识别。裁决按 pair、verdict、entity_key、ensure_tension 识别；输入不同不承诺是同一操作。

因此：

- 同一持久任务内，相同的工具提交与最终 JSON 提议/诊断不会重复增加证据或计数。
- 前几个条目已完成、后一个失败时，重试跳过已有回执，只执行未完成的操作。
- 进程在效果提交后、任务完成标记前退出，重启仍靠回执跳过副作用。
- SQLite 回执插入或业务执行失败，会一起回滚数据库与本次内存修改，保留已有 Memory
  对象身份，避免检索登记/在途语义 worker 的引用悬空。
- 如果异常发生在 commit 与返回确认之间，无法继续信任当前内存，服务置
  `checkpoint_fault`，拒绝继续写入/保存，要求重启读取数据库 checkpoint。

这不是整个调查结果的大事务。一个 `dead` 任务可能已经应用了部分条目；回执保留。
模型、embedding 和外部网络请求仍可能执行多次。不同 task ID 之间不做全局内容去重；
未关联持久任务的主 agent 请求、手动 `open_budget()` 调用和 `/observe` 也不自动幂等。

持久任务的诊断以 SQLite 任务产物和操作回执为审计依据，不再要求与 JSONL 双写一致。
非任务 `/diagnose` 仍沿用 `diagnoses.jsonl`。worker 的部分累计统计仍是进程内指标；
恢复状态、尝试次数、每日次数、错误与回执应以 SQLite 为准。

## checkpoint 的迁移与备份规则

1. **尚无 SQLite checkpoint**：继续读取旧 `state.pkl`，兼容旧 Pool 编码；旧快照损坏时
   沿用第一批的隔离/空引擎策略，L0 游标仍安全对齐。
2. **首次领取任务后**：SQLite checkpoint 成为事实源，加载时优先于 `state.pkl`。
   后续 `/save` 同时更新它，并把 `state.pkl` 作为兼容导出保存。
3. SQLite checkpoint 损坏，或任务/回执已存在但 checkpoint 缺失时 **拒绝启动**，不能回退到不含已提交效果的旧快照，否则会出现
   “数据库说应用过、内存却没有”的错误。
4. checkpoint revision 使用比较更新，旧实例不能覆盖别的实例推进的状态。
   这不等于支持多个 sidecar 共享一个内存引擎；生产环境仍应只启动一个实例。

升级前停止服务，备份整个状态目录；升级后备份/恢复也必须配套保留 `log.sqlite`、
`tasks.sqlite`、WAL 文件和快照。不要只复制正在写入的 SQLite 主文件，不要通过删除
任务库或只换回旧 `state.pkl` 来“修复”故障。直接降级到不认识 `tasks.sqlite` 的版本会
忽略任务和更新后的 checkpoint，不能视为安全回滚方案。

本批不自动修复损坏数据库，也不提供人工重新投递 dead 任务或回执清理接口。

## 容量与明确的剩余边界

- 未结束任务默认上限 4096，可用 `--task-queue-cap` 或 `MemoryService(task_capacity=...)`
  调整。满时拒绝新任务（HTTP 503），**不逐出已经接受的任务**；与已有未领取任务合并仍可进行。
- `done/dead/skipped` 记录及操作回执暂不自动清理，磁盘会增长，需要监控和备份。
  不能盲目清理回执，否则会失去重放保护。
- 本批只覆盖调查任务。`feedback_pending`、`conflict_pending`、`maintenance_due` 等
  语义 worker 队列仍未持久化；默认 `thin_recall` 仍是语义遥测，不会自动变调查任务。
- 持久性从**信号成功入队**开始：L0 提交后、candgen/触发器发信号前的崩溃窗口仍未自动补抽。
  容量/磁盘错误时 `/observe` 可能已有 L0，但没有接受调查任务；不能把 503 当成“什么都没发生”。
- 普通主回路在最近一次 checkpoint/save 后尚未保存的状态仍可能丢失；不重放完整 L0。
- 共享 token/可省略信号头、证据是否实际查看/蕴含、HTTP capture request-id 去重等边界不变。
- 本批优先正确性：每个任务操作要序列化引擎 checkpoint，现有同步 ingest/embedding
  仍持服务锁，还没有做性能优化或真实模型费用评测。

## 验证

```bash
python -m pytest -q tests/test_durable_tasks.py tests/test_taskstore.py
python -m pytest tests/ -q
```

第三批时点（历史数字）：Python 3.11.2 下，NumPy 1.26.4 / 2.4.6 两套环境全套各 **302 passed**；当前门禁数字见 README 验证状态与 acceptance 输出。覆盖未保存就重启、调查任务不挤占内存队列、部分应用失败、
每日限额/去重/次数恢复、同任务工具与最终产物去重、租约过期/迟到 token、并发领取、
回执写入失败的内存回滚、checkpoint 冲突/损坏、退避、关闭线程、容量 503 和编号高水位。

另有三个真实子进程 `os._exit` 故障点：保存产物之后、提交效果之后、修改内存但尚未提交
事务时。重启后均验证已保存产物无需重问模型、已提交效果不重复应用。
这验证了本地进程崩溃恢复，不等于断电/磁盘故障认证，更不等于 OpenCode + API 的 L3 闭环。
