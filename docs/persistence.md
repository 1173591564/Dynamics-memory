# L0 持久化与快照恢复

> 状态：现行 · L0 持久化与快照恢复；文中第一批范围与测试数字是历史记录。

本页记录第一批正确性修复。**第三批已新增 [调查任务持久化](durable-tasks.md)**：
有 `tasks.sqlite` checkpoint 时优先从它恢复，`state.pkl` 变为兼容导出；checkpoint
损坏时拒绝启动，不能用旧快照空启动。下述快照隔离/空启动策略只适用于尚无 SQLite
checkpoint 的旧状态。以下第一批范围与测试数字是历史记录，不代表当前功能全貌。

## L0：证据只追加，不覆盖

在线 `MemoryService.observe()` 使用 `LogStore.append_unit()`：

1. 在 SQLite `BEGIN IMMEDIATE` 写事务内读取日志最大 `id` 和最大 `t`。
2. 新编号取 `max(数据库最大 id + 1, 服务编号下界)`；新时间步取
   `max(数据库最大 t + 1, 服务时间下界)`。空数据库从 0 开始。
3. 原文、FTS5 索引和实体 mentions 在同一事务中提交；任一写入失败全部回滚。
4. 可选 embedding 在提交后运行；candgen 在此之后调用。抽取失败不撤销已提交的 L0。

不同 SQLite 连接之间的编号分配由写事务串行化，不只依赖进程内的锁。
取最大值分别使用主键和 `units_t` 索引，不需要每轮全表扫描。
这只保证 L0 追加安全，**不代表多个 sidecar 可以安全共享整套内存状态或同时写同一个快照**。

显式导入 `add_unit(id, t, ...)` 不再执行 `INSERT OR REPLACE`：

- 同 ID、相同 `t/scene/user_text/assistant_text/assistant_turns` 的重放为 no-op。
  不重建索引、重算向量或再次报告 `new_entities`。
- 未传 `ts` 的重放保留首次时间戳；显式传入 `ts` 时也必须与原值相同。
- 同 ID 的任一证据字段不同，抛出 `ValueError`；原记录与索引不变。

这不是 HTTP 请求去重：客户端重复调用 `/observe` 仍会获得新的单元编号。

## 启动：快照与 L0 分别恢复，再对齐

`log.sqlite` 每轮提交，`state.pkl` 则在 `save()` 时更新，两者不是一个事务。
因此快照正常落后于 L0 并不表示日志损坏。

| 快照状态 | 启动行为 |
|---|---|
| 有效、与日志同步 | 恢复记忆、检索登记等已保存状态，继续追加日志 |
| 有效、落后于日志 | 恢复快照中的状态，将编号和时间步提升至 L0 的下一位置 |
| 有效、游标高于日志 | 保留较高下界，不强制填补编号空洞或倒退逻辑时间 |
| 缺失或加载失败 | 使用空记忆引擎，仍从 L0 下一编号/时间步继续；加载失败沿用 `state.corrupt` 隔离流程 |

每次在线追加还会在事务内重新检查日志位置，处理启动后其他连接已追加的情况。
既有 `Memory.src` 指向的 L0 不会因后续追加而被替换。

加载先检查容器/对象类型、游标及计数器，完成旧字段迁移后才更新运行中的状态。
计数器仅允许已知名称，不能借快照中的任意键覆盖服务的锁或其他内部属性。
这避免了加载末尾字段失败却留下部分已恢复状态的问题；它并非对所有嵌套业务字段的完整语义校验。

## Pool 枚举兼容

- 新 `Pool` 序列化固定使用 `Pool(value)`，不依赖宿主 Python 的 Enum reducer。
- 旧 `Pool(value)` 与 `getattr(Pool, member_name)` 两种编码均可读取。
- restricted unpickler 将旧 `getattr` 映射为仅允许 `Pool` 合法成员的适配器，
  **没有放开通用 Python `getattr`**；其他类及 `__class__`、`__members__` 等访问仍拒绝。
- 新服务快照固定使用 pickle protocol 4，避免 Python 默认协议改变带来新的 NumPy 重建入口。

快照仍是本地 pickle 文件；兼容修复不意味着它成为可安全接受任意外部输入的格式。

## 本批明确未解决

- 不恢复已被历史版本覆盖的原始证据，也不自动修复旧数据库里已不一致的索引。
- 不从 L0 自动重建快照之后新增的记忆，不自动补跑未完成的 candgen。
- 不持久化或重放待处理信号、修复任务、反馈任务；也未实现任务的恰好一次处理。
- 不提供 `/observe` 的 request-id 幂等、不修改调查员预算/因果边界或召回策略。
- 不改变现有快照保存频率；本次没有验证断电、磁盘损坏或真实 OpenCode + API 会话。

升级前如需保留可回滚副本，应停止服务后备份整个状态目录，而不是只复制正在写入的
SQLite 主文件（WAL 中可能还有已提交数据）。

## 回归验证

```bash
python -m pytest -q tests/test_logstore.py tests/test_server.py \
  tests/test_snapshot_format.py tests/test_ouroboros.py
python -m pytest tests/ -q
```

覆盖缺失/落后/损坏快照、较高快照游标、并发连接分配、冲突拒写、相同证据重放、
索引失败回滚、抽取前独立连接可见 L0、既有来源引用不变、完整旧枚举快照恢复、
禁止任意 getattr，以及加载失败不发布部分状态。

本批本地全套结果：Python 3.11.2 下，NumPy 1.26.4 / 2.4.6 各 **246 passed**。
这是本地单元/服务集成验证，不是 L3 真实 agent 闭环验证。
