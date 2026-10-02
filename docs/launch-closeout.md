# 第 6 批：启动声明收口

> 状态：已实现·归档 · 第 6 批（启动声明收口）已落地，本文保留为决策记录。

基点是第 5 批。本批不新增运维平台，不改插件对 `ok` 的判断，不写新的必填快照字段，不声称远程模型或 OpenCode L3。

## 决策账本

| 问题 | 选择与理由 | 放弃的方案 | 受影响调用方 | 选错后的失败模式 | 验证 |
|---|---|---|---|---|---|
| 请求何时算被接受 | `/health` 的 `ok` 仍只表示没有 checkpoint fault，进程可以复用。效果是否补齐、快照是否被隔离、有没有远程验证，都是另外的字段 | 把未补齐或未验证写成 `ok: false`。插件只在连接失败时拉起进程；`ok: false` 会让它停在“不可达”，已接受的 outbox 不再重投 | 插件启动探针、`GET /health` | 桥停投，或操作员把“进程在”当成“数据已干净恢复且已远程验证” | 坏快照隔离后 HTTP 仍是 200 且 `ok` 为 true，但 `snapshot` 为 `quarantined`。checkpoint fault 仍是 503 |
| 失败响应能否安全重试 | health 是只读 GET。重复请求不写库 | 让探针顺手触发恢复或保存 | 插件每 250ms 探针 | 探针本身造成写入或重复效果 | 连续两次 GET，回执相同，日志单元数不变 |
| 幂等键 | 本批没有新的写请求，不新增幂等键 | — | — | — | — |
| 空结果与错误 | 没有 `state.pkl` 且没有 `state.corrupt` 是合法空目录，`snapshot=absent`。损坏被隔离是 `snapshot=quarantined`，不是 500，也不是干净的空库 | 损坏时拒绝启动。既有决策是空启动好过桥瘫痪，本批不推翻 | 启动、`/health` | 隔离后的空库看起来像从未有过数据 | 写入坏 `state.pkl`，启动后 `snapshot=quarantined`，记忆为空，服务仍接受只读探针 |
| 队列满和毒任务 | 不改任务队列。`units_pending` 只报告 `unit_work` 里尚未 done 的行，不把它们标成完成 | 启动时把积压显示成 0，以免探针看起来不干净 | `/health` | 效果还没补上，声明却像已经收口 | 只追加 L0、不跑恢复器，`units_pending` 为 1 |
| 谁有提交权 | health 只读，在服务锁内读计数。不领取任务，不提交效果 | 探针里调用恢复器 | 并发 observe | 探针和恢复器抢同一单元 | 本批不在探针路径调用 `process_pending_units` |
| 模型结果迟到 | 不改。本批没有模型调用 | — | — | — | — |
| 提交前后崩溃 | 不新增事务。隔离发生在加载时。本进程隔离过的标记在本次进程内保持，随后的 `save` 不能把它洗成干净加载。进程退出后若只剩下 `state.corrupt`、没有可加载快照，再次启动仍报告 `quarantined` | 标记只放内存，重启后显示 `absent` | 重启 | 重启把数据丢失洗成“本来就是空库” | 隔离后不保存就关闭，再打开，`snapshot` 仍是 `quarantined` |
| 旧库 / 旧快照 | 不增加必填字段。旧 checkpoint 和旧 `state.pkl` 仍按原规则打开。health 多出来的字段只在响应里 | 给两个 SQLite 写配套 generation id。两库无法一次提交，盖章写到一半崩溃会把健康目录判成不配套并拒绝启动 | 启动 | 升级后无法打开，或只回滚一个库仍被说成已检测 | 既有旧快照测试仍过。本批不新增拒绝启动的条件 |
| 备份和回滚 | 不改备份格式，也不假装能检测“只回滚了其中一个库”。文档写明这种回滚仍会丢数据或重复效果，必须整目录成套恢复 | 实现检测但无法证明不会误锁健康目录 | 操作员 | 误锁，或漏检之后仍声称已防护 | `validation` 固定为 `unverified`，测试断言它不是 `remote` / `l3` |
| 新增持久化 | 无。不把隔离标记写入新表或新快照字段 | 新表 | 回滚 | 回滚丢掉标记，或新字段让旧程序拒绝快照 | 状态目录不出现新文件名 |
| 本次进程成功 save 之后怎么说 | 没有隔离标记时，成功 `save` 把 `snapshot` 改为 `loaded`。隔离标记优先，save 不能洗掉它 | 一直保持启动时的 `absent`，直到重启 | `/save`、`/health` | 操作员以为没有写过快照；或坏快照被一次 save 洗白 | 空目录 save 后是 `loaded`；隔离后再 save 仍是 `quarantined` |

## 不变量

1. checkpoint fault 时 `/health` 是 503 且 `ok` 为 false。维护点：`health_view`。故障测试：既有 `test_uncertain_commit_stops_service_until_restart`。
2. 本进程隔离了坏快照，或磁盘上只剩 `state.corrupt` 而没有成功加载的快照，则 `snapshot` 为 `quarantined`，且 `ok` 仍为 true。维护点：`MemoryService` 加载分支与 `health_view`。故障测试：坏 pickle，关闭后再打开，真实 HTTP GET。
3. `validation` 永远是 `unverified`。维护点：`health_view`。故障测试：断言响应不是 `remote` 或 `l3`。
4. 有未完成的 `unit_work` 时，`units_pending` 不为 0。维护点：`health_view` 读取 `work_stats`。故障测试：只追加 L0，不启动恢复器。

## 明确不做

不检测两个 SQLite 是否来自同一次备份。不把 `state.corrupt` 自动删掉。不改插件，因此不能把 `ok` 改成“已验证”。

## 自查（不是独立审查）

反方检查过：重复 GET 不写库；checkpoint fault 仍是 503 且 `validation` 仍是 `unverified`；坏 pickle 隔离后不保存再启动仍是 `quarantined`；成功加载的快照旁边留着旧 `state.corrupt` 时报告 `loaded` 加 `corrupt_file`，不把好快照说成失败；只追加 L0 时 `units_pending` 不为 0。没有新的任务领取路径，也没有新的持久字段。

| 目标 | 实现 | 测试 | 剩余风险 |
|---|---|---|---|
| `ok` 不表示已验证或已干净恢复 | `health_view` 把 `snapshot`、`units_pending`、`validation` 分开；`ok` 仍只看 checkpoint fault | `test_health_does_not_claim_remote_validation_and_retry_is_read_only`、`test_quarantine_survives_restart_and_save_does_not_launder_it` | 插件不读新字段。只看 `ok` 的操作员仍会误判 |
| 隔离后重启不把丢失洗成空库 | 只剩 `state.corrupt` 时 `snapshot=quarantined` | 同上，关闭后再构造服务 | 只回滚一个 SQLite 仍检测不到，也不能靠这份声明找回数据 |
| 未完成的单元效果可见 | `units_pending` 读 `unit_work` | `test_pending_unit_is_visible_and_not_reported_done` | 不自动补齐，也不拒绝新的 observe |
| 公开说明不引用过期通过数，也不把本地测试说成 L3 | README 的验证状态 / 运行 | `test_readme_does_not_advertise_a_stale_pass_count_or_remote_validation` | 本环境没有重跑 TIDE、插件测试、真实 OpenCode 或远程模型 |
