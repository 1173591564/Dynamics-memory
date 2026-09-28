# OpenCode 行为清单（学习用）

按「用户/系统触发的一条完整链路」列行为，不是按源码文件列。

路径链接相对本文件（`learning-line/`）→ 仓库根下的 `packages/...`。在 Cursor 里 Ctrl/Cmd+点击即可跳转。

## 审查结论

上一版口头列了约 **43** 条。对照 `packages/protocol` 公开 API、`SessionPrompt` 入口、内置工具后：

| 判断 | 说明 |
|---|---|
| **主干行为就这些量级** | Session 生命周期 + `runLoop` 分支 + 权限/问题打断 + 压缩/回滚 + 子代理，大约 **30 条核心** |
| **不是「全世界只有 43 个」** | CLI 外壳、console、stats、企业功能、每个 MCP 工具、每个 slash command 都可以无限增生 |
| **工具不必各算一条主行为** | `read/grep/glob` 是同一类「只读工具循环」；学透一类即可 |
| **真正该吃透的约 12 条** | 见文末「学习优先级」 |

本文件：**B01–B30 核心** + **T01–T10 工具族** + **S01–S12 壳/集成**（合计 52）。下面以 **B 表为勾选真源**。

---

## 图例

- **难度**：★ → ★★★★★
- **必学**：✓ 入门 / ✓✓ 主干热路径
- **链接**：契约 → handler → 实现（从左读到右）

---

## B — 核心 30 条（推荐勾选）

| ID | 行为 | 难度 | 必学 | 链接 |
|---|---|---|---|---|
| B01 | 列/读元数据（health、provider、model、agent） | ★ | | [health](../packages/protocol/src/groups/health.ts) · [provider](../packages/protocol/src/groups/provider.ts) · [model](../packages/protocol/src/groups/model.ts) · [agent](../packages/protocol/src/groups/agent.ts) · [handlers](../packages/server/src/handlers/) |
| B02 | Session CRUD（create/list/get） | ★ | ✓ 入门 | [protocol/session](../packages/protocol/src/groups/session.ts) · [server handler](../packages/server/src/handlers/session.ts) · [core SessionV2](../packages/core/src/session.ts) · [opencode Session](../packages/opencode/src/session/session.ts) |
| B03 | 读 history / context / message | ★ | ✓ 入门 | [protocol/session](../packages/protocol/src/groups/session.ts) · [server handler](../packages/server/src/handlers/session.ts) · [history](../packages/core/src/session/history.ts) · [schema message](../packages/schema/src/session-message.ts) |
| B04 | switchAgent / switchModel | ★ | | [protocol](../packages/protocol/src/groups/session.ts) · [SessionV2](../packages/core/src/session.ts) · [opencode setAgentModel](../packages/opencode/src/session/session.ts) · [agent 面具](../packages/opencode/src/agent/agent.ts) |
| B05 | session.wait / session.active | ★★ | | [protocol](../packages/protocol/src/groups/session.ts) · [SessionV2.wait/active](../packages/core/src/session.ts) · [execution](../packages/core/src/session/execution.ts) · [run-coordinator](../packages/core/src/session/run-coordinator.ts) |
| B06 | **纯文本一轮 prompt** | ★★ | ✓✓ | [protocol prompt](../packages/protocol/src/groups/session.ts) · [server](../packages/server/src/handlers/session.ts) · [V2Session.prompt](../packages/core/src/session.ts) · [SessionInput.admit](../packages/core/src/session/input.ts) · [V1 SessionPrompt](../packages/opencode/src/session/prompt.ts) · [processor](../packages/opencode/src/session/processor.ts) · [llm](../packages/opencode/src/session/llm.ts) |
| B07 | 附件 prompt | ★★ | ✓ | [prompt-input schema](../packages/schema/src/prompt-input.ts) · [createUserMessage](../packages/opencode/src/session/prompt.ts) |
| B08 | noReply / resume:false（只 admit） | ★★ | ✓（V2） | [session-delivery](../packages/schema/src/session-delivery.ts) · [session-input](../packages/schema/src/session-input.ts) · [SessionInput.admit](../packages/core/src/session/input.ts) · [V2Session.prompt](../packages/core/src/session.ts) · [prompt noReply](../packages/opencode/src/session/prompt.ts) |
| B09 | 自动标题 | ★ | | [ensureTitle](../packages/opencode/src/session/prompt.ts) · [title agent](../packages/opencode/src/agent/agent.ts) |
| B10 | **只读工具循环** | ★★★ | ✓✓ | [processor](../packages/opencode/src/session/processor.ts) · [SessionTools](../packages/opencode/src/session/tools.ts) · [tool registry](../packages/opencode/src/tool/registry.ts) · [core registry](../packages/core/src/tool/registry.ts) · [read](../packages/opencode/src/tool/read.ts) · [grep](../packages/opencode/src/tool/grep.ts) · [glob](../packages/opencode/src/tool/glob.ts) |
| B11 | **写盘 + snapshot/patch** | ★★★★ | ✓✓ | [edit](../packages/opencode/src/tool/edit.ts) · [write](../packages/opencode/src/tool/write.ts) · [apply_patch](../packages/opencode/src/tool/apply_patch.ts) · [snapshot](../packages/opencode/src/snapshot/index.ts) · [processor step/patch](../packages/opencode/src/session/processor.ts) |
| B12 | bash 工具 | ★★★ | ✓ | [shell.ts](../packages/opencode/src/tool/shell.ts) · [shell/id](../packages/opencode/src/tool/shell/id.ts) · [shell/prompt](../packages/opencode/src/tool/shell/prompt.ts) |
| B13 | 多工具并行 | ★★★ | ✓ | [processor toolcalls](../packages/opencode/src/session/processor.ts) · [runLoop](../packages/opencode/src/session/prompt.ts) |
| B14 | hosted / providerExecuted 工具 | ★★★ | | [processor ensureToolCall](../packages/opencode/src/session/processor.ts) · [native-runtime](../packages/opencode/src/session/llm/native-runtime.ts) · [llm AGENTS](../packages/opencode/src/session/llm/AGENTS.md) |
| B15 | doom_loop | ★★★ | ✓ | [processor doom_loop](../packages/opencode/src/session/processor.ts) · [agent permission](../packages/opencode/src/agent/agent.ts) |
| B16 | permission ask/reply | ★★★ | ✓✓ | [protocol](../packages/protocol/src/groups/permission.ts) · [server](../packages/server/src/handlers/permission.ts) · [core permission](../packages/core/src/permission.ts) · [opencode permission](../packages/opencode/src/permission/index.ts) · [schema](../packages/schema/src/permission.ts) |
| B17 | question ask/reply | ★★★ | ✓ | [protocol](../packages/protocol/src/groups/question.ts) · [server](../packages/server/src/handlers/question.ts) · [core question](../packages/core/src/question.ts) · [question tool](../packages/opencode/src/tool/question.ts) · [opencode question](../packages/opencode/src/question/index.ts) |
| B18 | interrupt/cancel | ★★★ | ✓✓ | [protocol interrupt](../packages/protocol/src/groups/session.ts) · [V2Session.interrupt](../packages/core/src/session.ts) · [execution](../packages/core/src/session/execution.ts) · [SessionPrompt.cancel](../packages/opencode/src/session/prompt.ts) · [run-state](../packages/opencode/src/session/run-state.ts) |
| B19 | delivery=steer | ★★★★ | ✓✓ | [session-delivery](../packages/schema/src/session-delivery.ts) · [SessionInput.promoteSteers](../packages/core/src/session/input.ts) · [V2Session.prompt](../packages/core/src/session.ts) · [CONTEXT.md](../CONTEXT.md) |
| B20 | delivery=queue | ★★★★ | ✓✓ | [session-delivery](../packages/schema/src/session-delivery.ts) · [SessionInput.promoteNextQueued](../packages/core/src/session/input.ts) · [run-coordinator](../packages/core/src/session/run-coordinator.ts) |
| B21 | LLM retry | ★★★ | ✓ | [retry.ts](../packages/opencode/src/session/retry.ts) · [llm.ts](../packages/opencode/src/session/llm.ts) · [processor](../packages/opencode/src/session/processor.ts) |
| B22 | plan/build 模式 | ★★★ | ✓ | [agent.ts](../packages/opencode/src/agent/agent.ts) · [plan tool](../packages/opencode/src/tool/plan.ts) · [reminders](../packages/opencode/src/session/reminders.ts) · [plan.txt](../packages/opencode/src/session/prompt/plan.txt) |
| B23 | slash command | ★★★ | ✓ | [SessionPrompt.command](../packages/opencode/src/session/prompt.ts) · [command index](../packages/opencode/src/command/index.ts) · [protocol command](../packages/protocol/src/groups/command.ts) |
| B24 | SessionPrompt.shell（非工具） | ★★★ | | [prompt.shell](../packages/opencode/src/session/prompt.ts) · [run-state.startShell](../packages/opencode/src/session/run-state.ts) |
| B25 | system / instruction / skills 注入 | ★★★ | ✓✓ | [instruction.ts](../packages/opencode/src/session/instruction.ts) · [system.ts](../packages/opencode/src/session/system.ts) · [runLoop 拼装](../packages/opencode/src/session/prompt.ts) · [CONTEXT.md](../CONTEXT.md) |
| B26 | **自动 compaction** | ★★★★ | ✓✓ | [compaction.ts](../packages/opencode/src/session/compaction.ts) · [overflow.ts](../packages/opencode/src/session/overflow.ts) · [runLoop 分支](../packages/opencode/src/session/prompt.ts) · [core compaction](../packages/core/src/session/compaction.ts) |
| B27 | 手动 compact + prune | ★★★★ | ✓ | [protocol compact](../packages/protocol/src/groups/session.ts) · [V2Session.compact](../packages/core/src/session.ts) · [compaction.create/prune](../packages/opencode/src/session/compaction.ts) |
| B28 | **前台 task 子代理** | ★★★★★ | ✓✓ | [task.ts](../packages/opencode/src/tool/task.ts) · [task.txt](../packages/opencode/src/tool/task.txt) · [handleSubtask](../packages/opencode/src/session/prompt.ts) · [subagent-permissions](../packages/opencode/src/agent/subagent-permissions.ts) · [agent explore/general](../packages/opencode/src/agent/agent.ts) |
| B29 | **后台 task + 回注** | ★★★★★ | ✓✓ | [task.ts](../packages/opencode/src/tool/task.ts) · [background job](../packages/opencode/src/background/job.ts) · [run-state](../packages/opencode/src/session/run-state.ts) |
| B30 | revert stage/clear/commit + fork | ★★★★★ | ✓✓ | [protocol revert](../packages/protocol/src/groups/session.ts) · [schema revert](../packages/schema/src/revert.ts) · [opencode revert](../packages/opencode/src/session/revert.ts) · [Session.fork](../packages/opencode/src/session/session.ts) · [snapshot](../packages/opencode/src/snapshot/index.ts) |

**核心就是 B01–B30。** 相对旧清单，补得最明显的是 **B08/B19/B20（admit + steer/queue）** 和 **B21（retry）**。

---

## T — 工具族（变体，挂在 B10/B11/B12… 上）

| ID | 工具族 | 学习建议 | 链接 |
|---|---|---|---|
| T01 | 读取 | 跟 B10 | [read.ts](../packages/opencode/src/tool/read.ts) · [read.txt](../packages/opencode/src/tool/read.txt) |
| T02 | 搜索 | 跟 B10 | [grep.ts](../packages/opencode/src/tool/grep.ts) · [glob.ts](../packages/opencode/src/tool/glob.ts) |
| T03 | 写入 | 跟 B11 | [edit.ts](../packages/opencode/src/tool/edit.ts) · [write.ts](../packages/opencode/src/tool/write.ts) · [apply_patch.ts](../packages/opencode/src/tool/apply_patch.ts) |
| T04 | 执行 | 跟 B12 | [shell.ts](../packages/opencode/src/tool/shell.ts) · [shell/id.ts](../packages/opencode/src/tool/shell/id.ts) |
| T05 | 网络 | 可选 | [webfetch.ts](../packages/opencode/src/tool/webfetch.ts) · [websearch.ts](../packages/opencode/src/tool/websearch.ts) |
| T06 | 任务/子代理 | 跟 B28/B29 | [task.ts](../packages/opencode/src/tool/task.ts) |
| T07 | 交互 | 跟 B17 | [question.ts](../packages/opencode/src/tool/question.ts) |
| T08 | 计划 | 跟 B22 | [plan.ts](../packages/opencode/src/tool/plan.ts) · [plan-enter.txt](../packages/opencode/src/tool/plan-enter.txt) · [plan-exit.txt](../packages/opencode/src/tool/plan-exit.txt) |
| T09 | 技能/待办/LSP | 可选 | [skill.ts](../packages/opencode/src/tool/skill.ts) · [todo.ts](../packages/opencode/src/tool/todo.ts) · [lsp.ts](../packages/opencode/src/tool/lsp.ts) |
| T10 | CodeMode / MCP / invalid | 进阶 | [code-mode.ts](../packages/opencode/src/tool/code-mode.ts) · [mcp](../packages/opencode/src/mcp/index.ts) · [invalid.ts](../packages/opencode/src/tool/invalid.ts) · [tool.ts](../packages/opencode/src/tool/tool.ts) |

---

## S — 壳 / 集成（后学）

| ID | 行为 | 难度 | 链接 |
|---|---|---|---|
| S01 | `opencode serve` + HTTP API | ★★★★ | [serve.ts](../packages/opencode/src/cli/cmd/serve.ts) · [protocol groups](../packages/protocol/src/groups/) · [server handlers](../packages/server/src/handlers/) · [server api](../packages/server/src/api.ts) |
| S02 | 全局/会话事件 SSE | ★★★ | [protocol event](../packages/protocol/src/groups/event.ts) · [event handler](../packages/server/src/handlers/event.ts) · [session.events](../packages/protocol/src/groups/session.ts) · [core event](../packages/core/src/event.ts) |
| S03 | TUI / `run` 交互壳 | ★★★ | [run.ts](../packages/opencode/src/cli/cmd/run.ts) · [run/](../packages/opencode/src/cli/cmd/run/) · [prompt.shared](../packages/opencode/src/cli/cmd/run/prompt.shared.ts) |
| S04 | Web app / Desktop 连后端 | ★★★★ | [app](../packages/app/) · [desktop](../packages/desktop/) · [ui](../packages/ui/) · [session-ui](../packages/session-ui/) |
| S05 | PTY 创建与 connect | ★★★★ | [protocol pty](../packages/protocol/src/groups/pty.ts) · [pty handler](../packages/server/src/handlers/pty.ts) |
| S06 | ACP（IDE Agent Client Protocol） | ★★★★★ | [acp cmd](../packages/opencode/src/cli/cmd/acp.ts) · [acp/](../packages/opencode/src/acp/) · [acp/session](../packages/opencode/src/acp/session.ts) · [acp/agent](../packages/opencode/src/acp/agent.ts) |
| S07 | MCP 配置与鉴权 | ★★★ | [mcp cmd](../packages/opencode/src/cli/cmd/mcp.ts) · [mcp/](../packages/opencode/src/mcp/index.ts) |
| S08 | Integration / credential | ★★★ | [integration](../packages/protocol/src/groups/integration.ts) · [credential](../packages/protocol/src/groups/credential.ts) · [handlers](../packages/server/src/handlers/) |
| S09 | Project copy / location / fs | ★★★ | [project-copy](../packages/protocol/src/groups/project-copy.ts) · [location](../packages/protocol/src/groups/location.ts) · [fs](../packages/protocol/src/groups/fs.ts) |
| S10 | Import / Export / Share | ★★★ | [export](../packages/opencode/src/cli/cmd/export.ts) · [import](../packages/opencode/src/cli/cmd/import.ts) · [share/session](../packages/opencode/src/share/session.ts) |
| S11 | Plugin 钩子 | ★★★★ | [plugin/](../packages/opencode/src/plugin/index.ts) · [plugin pkg](../packages/plugin/) |
| S12 | GitHub / PR / account 等 CLI | ★★ | [cli/cmd](../packages/opencode/src/cli/cmd/) · [index 入口](../packages/opencode/src/index.ts) |

---

## 旧 C 编号对照（已弃用勾选，仅防迷路）

旧 C1–C8 ≈ B01–B05；C9–C13 ≈ B06–B09；C14–C20 ≈ B10–B15；C21–C26 ≈ B16–B21；C27–C30 ≈ B22–B24 + 部分 B25。请一律用 **Bxx**。

---

## 上一版遗漏 / 易混点

1. **V2 `session.prompt` 的 admit + `delivery`（steer/queue）+ `resume`** — 见 B08/B19/B20；对照 V1 [`prompt.ts`](../packages/opencode/src/session/prompt.ts) 与 [`SessionInput`](../packages/core/src/session/input.ts)。
2. **`session.wait` / `active` / SSE** — B05、S02。
3. **LLM retry** — B21。
4. **plan_enter / plan_exit 是工具** — T08，和 B04 切换 agent 不完全同一条链。
5. **fork** 并入 B30；深挖可从 [`Session.fork`](../packages/opencode/src/session/session.ts) 拆笔记。
6. **子代理 resume（task_id）** 是 B28 变体，见 [`task.ts`](../packages/opencode/src/tool/task.ts)。
7. **永远列不完的**：自定义 agent、用户 slash、MCP tools。

---

## 学习优先级

1. B02 → B03 → **[B06](../packages/opencode/src/session/prompt.ts)**
2. **[B10](../packages/opencode/src/session/processor.ts)** → **[B16](../packages/opencode/src/permission/index.ts)** → **[B18](../packages/opencode/src/session/run-state.ts)**
3. **[B11](../packages/opencode/src/tool/edit.ts)** → **[B25](../packages/opencode/src/session/instruction.ts)**
4. **[B26](../packages/opencode/src/session/compaction.ts)**
5. **[B19/B20](../packages/core/src/session/input.ts)**
6. **[B28/B29](../packages/opencode/src/tool/task.ts)**
7. **[B30](../packages/opencode/src/session/revert.ts)**
8. 接 IDE/桌面再学 [S01](../packages/opencode/src/cli/cmd/serve.ts) / [S02](../packages/protocol/src/groups/event.ts) / [S04](../packages/app/) / [S06](../packages/opencode/src/acp/)

---

## 怎么用本文件

对每一条必学行为，在同目录另开笔记（例如 `B06-plain-prompt.md`）：

```
触发
调用链（文件::函数）  ← 从本表「链接」列抄起点
持久化 / 事件
我还讲不清的行
```

状态：`[ ]` 未学 / `[~]` 跟过调用链 / `[x]` 能复述到行级。

---

## 数量总结

| 集合 | 条数 | 角色 |
|---|---|---|
| B01–B30 | 30 | **主要行为，学习主干** |
| T01–T10 | 10 | 工具族变体 |
| S01–S12 | 12 | 壳与集成 |
| **合计** | **52** | 覆盖主产品；不是宇宙全集 |

**结论：主要就这些（尤其 B06–B30）。** 按行为学时盯 B 表；点链接从契约走到实现。
