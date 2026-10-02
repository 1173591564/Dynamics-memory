# OpenCode 三 Agent 记忆协议（源码交付版）

> 状态：现行 · OpenCode 三 Agent 记忆协议；关键断言由 A2 验到测试。

本版默认启用 `MEMORY_PIPELINE=opencode`。旧的被动 candgen + 进程内调查员可通过 `MEMORY_PIPELINE=legacy` 显式启用；**不要把旧的单轮抽取结果当作三 Agent 验证结果**。OpenCode Hauler、Selector、Reviewer 的定义在 `.opencode/agent/`，sidecar 通过真正的 `opencode run --pure --agent <name> --format json` 调用它们，不在 Python 中仿造语义判断。

## 安装与运行

- 安装 OpenCode CLI，配置可用的 provider/model（使用 OpenCode 自身的配置）。`opencode` 必须在启动 sidecar 的 PATH 内，或用 `MEMORY_OPENCODE_BIN=/absolute/path/to/opencode` 指定；源码目录 `.opencode/agent/*.md` 必须保留。OpenCode 子进程的工作目录是本源码目录，不是用户项目目录；三份定义均采用 `"*": deny`，禁止工具访问；`--pure` 不加载第三方插件（仍加载本地 agent 定义），内部会话另有环境变量隔离。
- 在源码目录按原 README 安装 Python 依赖，并配置原引擎的 `ZAI_API_KEY`（向量编码／已有检索链仍需它）；示例：`python -m hybrid_memory.server --project /path/to/project --port 17872`。原插件 `.opencode/plugin/memory-bridge.ts` 依旧须在真实的 OpenCode/Bun 环境中运行。子 agent 会话设置 `DYNAMICS_MEMORY_INTERNAL_AGENT=1`，插件不会捕获其输出作为用户交互。
- 默认的每个 L0 交互持久投递 `hauler_due`；Hauler 看到不晚于该交互、至多六个单元的窗口，给每条候选标注来源单元 ID；Selector 根据当前未退役记忆（包括归档）在 CREATE、EXIST、UPDATE、CONFLICT、REJECT 中逐条决策。重复来源不能增加同一条记忆的 evidence；完全相同的候选即使被误判 CREATE 也按 EXIST 处理，归档等价项会重新激活。明确的用户纠正且 Selector 确认过的 UPDATE 才退役旧版本；否则改走人审冲突。CONFLICT 不能由 agent 自行审批。
- 用户明确表达不满／纠正时投递 `reviewer_due`：Reviewer 给出诊断、持久写入 Hauler/Selector 的作用规则，并可提交修复候选，但修复候选仍经 Selector。Reviewer 收到过去窗口中已持久完成的 Hauler/Selector 输出、效果回执和已捕获的上一轮召回摘要；在投诉后才完成的任务只标记“投诉时尚未完成”，不冒充过去的决定。规则在 `tasks.sqlite` 的 `agent_rules` 表中按 ID 版本化，`scope=project|entity:<literal>` 在当前单元或候选上匹配；每次给 agent 提供规则 ID 及使用记录。运行 `python -m hybrid_memory.transport.review_cli --project /path/to/project --list-rules` 查使用次数，`--disable-rule ID` 人工禁用并留下审计记录。Reviewer 可在后续投诉中基于已观察的规则使用及交接记录提交 `rule_reviews`；判为 `ineffective` 会在同一任务事务内停用规则并留下审计记录，`uncertain` 不自动回退。使用次数或再次投诉**不等于效果改善／失败的因果证据**，规则效果仍需人工复核。
- 接力任务及领取租约、agent 输出、记忆 checkpoint 和完成回执存于同一 `tasks.sqlite`；失败指数退避，最多 5 次后任务留为 `dead`（须人工检查 `last_error`、原始输出）。存储结果后重启会复用结果，租约失效会重新调用模型，因此模型调用并不保证只执行一次。没有 OpenCode CLI 或配置不可用时任务会失败，**不会悄悄回退为固定规则或假模型**。`MEMORY_AGENT=off` / `--no-agent` 可暂停后台调用，队列仍保留。

## 人审

待审记录可运行（源码目录下）：

```sh
python -m hybrid_memory.transport.review_cli --project /path/to/project --port 17872
```

它从 `/path/to/project/.opencode/memory/` 读取仅本地保存的 `.memory-token` 和独立的 `.human-review-token`，在终端展示旧记忆正文及其来源、待审候选和原因，选择 `accept_new`、`keep_old` 或 `skip`。若要直接使用 HTTP：带正常 bearer 请求 `POST /human-reviews`（空 JSON）；提交 `POST /human-review` JSON `{"review_id": 1, "decision": "keep_old"}` 时另带 `X-Human-Review-Token: <.human-review-token>`。端口只绑定 loopback；不要把审核 token 给普通 agent。`accept_new` 与更新 checkpoint 同事务写入、退役旧版本；`keep_old` 关闭该待审记录。旧版本一旦退役，针对它的其他待审记录标记 stale，不可继续批准。待审期间召回旧记忆会标注“待人审冲突，不可断言为当前事实”。

## 恢复、迁移、边界

- 升级前备份 **整个** `/path/to/project/.opencode/memory/`，尤其 `log.sqlite`、`tasks.sqlite`、`state.pkl`、向量缓存和两份 token；不要只回滚其中一个库。新增表用 `CREATE TABLE IF NOT EXISTS` 自动建立，不迁移既有历史候选为新的 trio 任务。回滚到旧代码应恢复配套备份；仅切换 `MEMORY_PIPELINE=legacy` 不会自动消费尚未完成的 trio 任务。
- 调度不满事件使用宽松的文本触发器，是否真有记忆问题仍由 Reviewer 判断；通用的情绪／隐晦表达可能漏触发，需人工复核。Hauler/Reviewer 窗口超过 12000 字符、Selector 未退役记忆超过 500 条时显式失败；当前没有分页/增量索引。来源检查验证引用的 L0 单元与浅层文本一致性，**不保证语义蕴含或事实正确**。归档记忆会进入 Selector 快照，已退役版本不会；当前同义判定仍取决于模型质量，不能保证误判时不产生语义重复。历史 L0 及任务完成记录无自动清理。
- Python 测试以假模型边界覆盖协议、持久 SQLite、HTTP、重启和人审；Bun 测试覆盖插件、内部会话隔离以及默认模式隐藏旧的绕行写入工具。OpenCode CLI 1.18.11 的 `agent list --pure` 已实际确认三份定义为 primary 且最终通配工具权限为 deny；没有配置真实模型凭据，已用 `tests/manual_opencode_smoke.py` 让真实 CLI 1.18.11 依次调用三份 agent 定义，并通过**本地假 OpenAI 接口**完成 SQLite 任务交接；这证明 CLI 启动与协议接线，**不证明真实模型的推理质量或生产凭据／provider 接入**。本环境尝试过公开免费模型，但 OpenCode 的出站请求报 TLS 证书验证错误；没有禁用证书检查或声称真实模型通过。在自己的 provider 环境端到端运行 `opencode run --pure --agent hauler --format json ...` 等命令并审核输出后再上线。
- Trio 模式下，主会话不提供原 `memory_propose`、`memory_resolve`、`memory_diagnose` 工具，HTTP 也拒绝这些旧直写入口；`/miss` 不再制造无人消费的旧调查任务。切换到 `MEMORY_PIPELINE=legacy` 后仍可按旧模式使用它们。

健康接口的 `agent: true` 表示有工作线程挂载，**不**代表模型账号可用、任务成功或审核完成；实际任务错误请看 `tasks.sqlite` 的 `state`、`last_error`，留意 `dead`。
