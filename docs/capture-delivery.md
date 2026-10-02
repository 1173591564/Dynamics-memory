# 第 3 批计划：插件到 sidecar 的可靠交付与请求幂等

> 状态：已实现·归档 · 第 3 批（可靠交付与幂等）已落地，本文保留为决策记录；行为以 tests/test_capture_delivery.py 为准。

基点是已合并 PR #3 的 `origin/main` `a8471be`（head `36397ed`）。本批只做主 agent 捕获回路的 `/observe` 与 `/feedback`。不改 `agent/` 第三方 runtime，不改 eval 评分，不实现第 4–6 批。

## 已核实的现状

插件 `.opencode/plugin/memory-bridge.ts` 在 `session.idle` 时把用户/助手文本放进内存 `inflight` 链，POST `/observe`，仅当响应 `ok` 才 POST `/feedback`。`dispose` await 这条链后再 `/save` + kill。没有请求超时、没有请求 ID、没有跨进程 outbox。连接失败或超时会丢掉这一轮；若盲目重投，会再写一条 L0。

服务端 `MemoryService.observe` 在 `log.sqlite` 事务里 `append_unit` 之后才跑候选和应用。队列满时 `process_pending_units` 抛 `TaskQueueFull`，HTTP 变成 503，但 L0 与 `unit_work` 已经提交（`tests/test_observe_recovery.py` 已覆盖）。响应体原先只有 `error`，没有“已接受”标记。`/feedback` 用检索对象上的 `feedback_sent` 防重复，效果与 checkpoint 同事务；响应丢失后，检索对象被挤出或进程重启时，客户端无法用请求身份取回那次回执。没有 request-id 表。

`memory_propose` 仍引用未定义的 `ROLE`（`memory-bridge.ts` 工具执行体）。这是主 agent 主动工具，不在 idle 捕获的 observe/feedback 链上。本批核实后不修，避免把工具写入协议混进交付幂等。

## 目标

1. 插件在发送前把回合持久化到项目记忆目录的 outbox，进程退出、超时、连接失败后用**同一个** request-id 重投。
2. 服务端把 observe 的 request-id 与 L0 单元在 `log.sqlite` 同一事务绑定；把 feedback 的 request-id 与效果/checkpoint 在 `tasks.sqlite` 同一事务绑定。响应丢失后再投，返回原回执，不产生第二条 L0、不第二次发射 `feedback_pending`。
3. `/observe` 在 L0 已接受但效果尚未完成（含容量 503）时，响应带 `accepted: true` 与 `unit_id`。插件把这视为交付完成，不换新 id，也不因此跳过已绑定的 feedback。效果仍由既有单元恢复器继续。
4. 无 request-id 的旧客户端行为不变：每次调用仍追加。这不是去重承诺。

## 非目标

- 不给 `/miss`、`/propose`、`/search`、`/resolve` 做 request-id 去重。
- 不保证模型只调用一次；单元恢复与语义 worker 的既有“效果至多一次”不变。
- 不支持多个 sidecar 共享一个内存引擎，也不做多主。
- 不回放升级前没有 request-id 的历史 HTTP。
- 不修改 `ROLE` 未定义问题。
- 反馈若在第一次提交前检索对象已被挤出（`_RETRIEVAL_KEEP`），且没有回执，则无法补记账。插件在检索后立即入队，缩小这个窗口；这不是“检索永不过期”。

## 协议

- `request_id`：可选字符串，8–80 字符，字符集 `[A-Za-z0-9._:-]`。body 字段与 `X-Request-Id` 同时出现时必须一致，否则 400。空字符串 400。
- 指纹：规范化 JSON（`user_text`/`assistant_text`，或 `retrieval_id`/`question`/`answer`）的 SHA-256。同一 id 不同指纹返回 409，不写入。
- observe 回执表 `log.sqlite.capture_receipts(request_id PRIMARY KEY, unit_id, fingerprint, created_at)`，与 units/unit_work 同事务。重放不分配新 id、不推进服务时钟、不重复 embedding。
- feedback 回执表 `tasks.sqlite.capture_receipts(request_id PRIMARY KEY, kind, fingerprint, response, created_at)`，与效果、语义入队、checkpoint 同事务。重放不跑模型。
- 交付成功：响应含 `accepted: true` 且 observe 含 `unit_id`；或 feedback 为 200/`replayed`，或 409 且 error 含 `already`（同一 retrieval 已记账）。
- 可重试且必须沿用原 id：超时、连接失败、408/429/500/502/503/504，以及没有 `accepted` 的 503。401 停止本进程发送，outbox 留给下次启动。400 与指纹 409 标记终止，不换 id。
- 插件 outbox：`<project>/.opencode/memory/bridge-outbox.json`，0600，原子替换。成功后删除该回合。未接受的终止回合留在文件里，避免热循环，也避免丢掉尚未入库的原文。目录 `.gitignore` 缺失时写 `*`。

## 中断点

| 点 | 持久状态 | 重投结果 |
|---|---|---|
| outbox 写完、请求未发出 | 仅 outbox | 原 id 首次接受 |
| observe 事务提交后、响应前（含 candgen 中 `os._exit`、容量 503） | L0 + capture 回执，效果可能未提交 | 原 unit_id，不第二 append |
| observe 效果/回执提交后、日志 done 前 | 既有 unit_receipt | 既有恢复只确认，不重复效果 |
| feedback 事务提交后、响应前 | capture 回执 + 一条 feedback_pending | 回放回执，不第二发射 |
| feedback 未提交（容量/冲突） | 无回执，`feedback_sent` 回滚 | 原 id 再投一次效果 |
| 插件 dispose 超时或进程被杀 | outbox 仍在 | 下次加载同一 id 再投 |
| 指纹冲突 | 原绑定不变 | 409，不换 id |

跨库仍不是一个分布式事务。observe 的“已接受”以 log 回执为准；效果以 tasks 的 unit_receipt 为准。二者配套备份，不能只回滚一个库。

## 迁移、备份、回滚

旧库在打开时 `CREATE TABLE IF NOT EXISTS`，不回填历史请求。无 request-id 的在途请求无法事后去重。

上线前停机、确认无其他写入者，备份整个状态目录（`log.sqlite`、`tasks.sqlite`、WAL、`state.pkl`）以及同目录的 `bridge-outbox.json`。先在副本上演练。回滚必须插件与 sidecar 一起回到旧版本：新插件对着旧 sidecar 重投会被当成新 L0。回滚后 outbox 里未确认回合不会被旧插件自动重放，文件仍在，可人工查看；不要删除它来“清空错误”。备份之后的新数据不能靠旧副本无损找回。

## 敏感数据与性能

outbox 在确认前保存用户/助手原文，敏感级别与 L0 相同，必须留在已 gitignore 的记忆目录，权限 0600。日志只打 id 和长度。回执只存哈希和状态 JSON，不复制第二份原文。每次捕获多一次主键读写和一次小文件替换，面向交互回合，不是高 QPS 队列。超时默认 30 秒，不取消服务端已开始的工作。

## 验收

1. 同一 observe request-id 两次（含并发）只产生一个 L0；不同正文 409。
2. 无 id 的两次 observe 仍是两个单元。
3. 容量 503 含 `accepted` 与 `unit_id`；同 id 再投不增加单元；容量恢复后效果只应用一次。
4. `os._exit` 于 observe 已落 L0/回执、响应前：重启后同 id 复用单元，效果一次。
5. `os._exit` 于 feedback 已提交、响应前：重启后同 id 回放，只有一条 `feedback_pending`。
6. 检索对象被移出注册表后，已有 feedback 回执仍可回放。
7. 插件：503 无 accepted 时重试同一 id 且不发 feedback；503 有 accepted 时不重投 observe 并发 feedback；超时重试用同一 id；新插件实例从 outbox 继续，不铸造第二个 id；dispose 等到在途请求结束后再 `/save`。
8. 旧库打开后能写入新回执表。非法 id、header/body 不一致为 400 且不写单元。
9. 完整 Python 测试、独立 TIDE、插件测试（环境可用时）、Ruff/编译、`git diff --check`。假模型与真远程模型分开记录。

## 实现核对

- `log.sqlite.capture_receipts` 在 `BEGIN IMMEDIATE` 内、分配 id 之前查找。命中且指纹相同则返回原 `unit_id`，不 `_embed`、不推进 `_t`/`_unit_id`。插入与 units/unit_work 同一事务；插入失败整笔回滚。
- `tasks.sqlite.capture_receipts` 与效果、checkpoint 同一事务。`apply_effect` / `_commit_sidecar_effect` 的返回值个数不变。无效果的空反馈走 `remember_capture`。重放不调用 `mutate`，因此不跑模型。
- L0 已提交后的 `TaskQueueFull` / `CheckpointConflict` 仍是原异常，HTTP 附加 `accepted`/`unit_id`。接受前的 `_ensure_healthy` 失败仍只有 `error`。`IntegrityError` 不吞掉。反馈容量失败回滚且无回执。
- 插件 outbox 在 handler 返回前用 `writeFileSync` + `renameSync` 落盘，不依赖测试里的 `Bun.file` mock。`accepted` 且有 `unit_id`（含 503）视为 observe 已交付，然后发同一回合的 feedback。无 `accepted` 的超时/连接失败/5xx 沿用原 id。401 停止本进程。400 与指纹 409 终止且不换 id。dispose 先停收新请求，等在途链和已落盘回合，再 `/save`，再 kill。

## 已跑

- `/tmp/venv`（numpy 2.4.6）`pytest tests`：349 passed。`tests/test_capture_delivery.py`：10 passed。
- `/tmp/venv126`（numpy 1.26.4）observe/semantic/server/capture：83 passed。
- `PYTHONPATH=eval pytest eval/tests/test_tide.py`：8 passed。评分未改。
- `bun test tests/memory_bridge.test.ts`：24 passed。
- 新测试文件 Ruff 通过；`compileall` 通过；`git diff --check` 通过。仓库其余文件原有 Ruff 告警未顺手改。
- 假模型与本地 HTTP。没有真实远程模型，也没有在 OpenCode 里跑过插件。不能把这说成 L3 或线上验证。

## 未覆盖的风险

| 风险 | 为什么留下 | 失败时会怎样 |
|---|---|---|
| log.sqlite 与 tasks.sqlite 不是一笔事务 | 现有双库设计；本批不引入分布式事务 | 只备份其中一个库时，回执和效果可能不配套。必须按计划整目录备份 |
| 无 request-id 的旧客户端 | 协议明确不给旧请求事后去重 | 重投仍会再写一条 L0 |
| 反馈重放返回的是提交时的占位回执，不是 worker 跑完后的 `n_useful` | 交付承诺是“效果已接受”，worker 由 sidecar 自己重试 | 客户端可能看到 `pending: true`，但不会因此再记一次 |
| 检索被挤出且当时没有回执 | `_RETRIEVAL_KEEP` 仍在；404 终止是为了不热循环 | 该次 feedback 不再补记。L0 还在 |
| 终止的 observe（400/指纹 409）留在 outbox | 原文可能尚未入库，不能删了假装已处理 | 文件会留下这轮原文，直到人工处理。不会换 id 重投 |
| outbox 损坏 | 无法判断哪些 id 已用过 | 整文件改名为 `.bad-*`，不自动重放，也不删除 |
| outbox 写入失败（磁盘满） | 不能无中生有地保证落盘 | 本进程仍用已铸造的 id 发送；若在发送前崩溃，这轮丢失 |
| 两个插件进程写同一个 outbox | 不是多主设计 | 后写覆盖先写，可能丢掉另一进程尚未确认的回合 |
| 断电发生在 write 返回之后、内核刷盘之前 | 故障模型是进程退出，不是断电 | outbox 可能缺最后一轮。SQLite 侧仍是 `synchronous=FULL` |
| `memory_propose` 的 `ROLE` 未定义 | 不在 observe/feedback 链上，本批不修 | 主动提议工具仍会在执行时抛 ReferenceError |
| 未在真实 OpenCode / 远程模型上跑 | 环境没有这两样 | 插件事件时序或模型失败形态可能与本地 mock 不同 |
