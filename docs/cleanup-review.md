# 自有代码清理记录

前一轮对照 PR #1 的 `04dc885`；本次追加清理以用户要求二次审查时的工作区快照为对照，不把此前三批功能算作清理成果。

## 合并当前主线后的状态

PR #1 合并主线 `9ee06f6`，保留 `agent/ + hybrid_memory/ + tests/ + eval/` 布局与进程内调查员。
旧 `experiments/`、CLI Runner/语义后端、角色定义不再恢复；下方对此类文件的记录是历史审查结果，相关代码保存在 PR 前序提交中。
持久任务、统一因果/预算、输入校验、缓存及插件修正移植到现有入口。保留主线 `ZAI_BASE_URL`、多轮 chat、passive/token-budget 检索；被动检索复用独立只读引擎视图，不复制含 SQLite 锁的服务对象。
旧实验/CLI 专属测试随组件移除；共享缓存回归迁入存活客户端，保留持久化/故障恢复覆盖，补充进程内工具及被动探针的集成检查。

合并验证：服务/引擎 **302 项**，独立 TIDE **8 项**，插件 **20 项**通过；NumPy 1.26.4 / 2.4.6 均运行服务/引擎套件。
另用本地 mock 模型端点运行真实 sidecar CLI：完成被动抽取、两条持久调查任务、限额被动检索和 checkpoint 重启恢复。不是远程模型质量或真实 OpenCode L3 认证。

## 范围与判据

- 核对 `hybrid_memory/`、全部自有 `experiments/*.py`、桥接插件、agent 定义和配置的调用关系、状态读写及异常路径；检查相关测试并运行完整套件。
- 不改 vendored `opencode/`，不重写历史评测数据。实验代码审查不等于重新认证历史评测结果。
- 删除依据是无实际调用、配置不生效、重复状态或已有实现可替代；不是按代码年龄/静态扫描名单批量删，也不追求删除行数指标。

## 结构性删除与归并

| 位置 | 处理及依据 |
|---|---|
| `signals/server/taskstore` | 调查任务只存 SQLite；删除内存镜像、`Signal.task_id`、镜像同步、持久种类配置。SQL 直接汇总 pending/ready，队列仅管语义信号和遥测 |
| `agent/loop` | 删除每日预算的进程内副本和可配置任务种类；DB 负责计数/原子限额。固定处理 recall_miss/extract_due，thin_recall 不进入调查员 |
| `candgen/prompt`、实验消费者 | 删除 `parse_candidates` 旧入口；在线统一 `parse_generation`，缓存统一 `parse_candidate`/`load_candidates`。保留历史字符串候选读取，不放宽在线 schema |
| 检索、实验公共逻辑 | 共用词法分数、文件哈希、reader prompt；删除重复实现、无效条件与局部变量 |
| `Memory`、检索排序 | 删除未读取的 `shortlisted` 字段和排序元组中的重复相似度；保留对外的 `Retrieval.n_shortlisted` |
| Runner/生成器 | 删除 `scratch_dir` 别名；仓库 workdir 用于发现命名 agent，`payload_dir` 只放附件。标准库私有临时文件替代手写随机前缀/序号状态 |
| 语义适配器 | 删除没有消费者的 `use_agents=False` 旁路；明确使用命名角色，避免意外落入默认 agent |
| 远程评测 | 删除 qa_real/qa_continuity/rejudge_kp 不起作用的 `--offline`；所有远程评测在凭据和数据读取前检查 `--allow-remote`。真正支持缓存离线的 embedding/replay 路径保留 |
| 测试入口/HTTP 工具 | `pytest.ini` 替代手写 runner 和路径补丁；共用已有 HTTP helper，删除四份重复客户端和手动服务关闭代码，保留断言与故障用例 |

前一轮已删除：未接入的 MiniLM 后端、`LogStore.add_units`、`Recorder.to_csv`、`StreamGen.useful/emb`、`ChatGenerator.model`、调查员闲置缓存参数/字段、`collect_text` 包装、`niche_pair` 旧豁免；收紧了 TaskStore 不带版本/checkpoint 的可选分支。

这是内部接口清理，仓库外旧调用需按新签名调整。例如用 `parse_generation(text).candidates` 替代旧解析入口，用 `workdir/payload_dir` 区分项目与附件路径。持久状态的兼容读取没有借此删除。

## 顺带修正的错误路径

- 附件目录不再覆盖仓库 workdir；并发 Runner 调用使用不同的 0600 附件，调用结束清除文件。角色名参与缓存键，角色定义内容不参与，修改定义仍需清缓存。
- benchmark 候选缓存名加入 stride，防止不同窗口划分误用同一缓存；旧命名文件不再自动复用。
- 前轮插件修正保留：403/429/503 不再伪装“无命中”，健康探针不误报 ready，不重复启动 sidecar；非法 JSON 显式失败；上报/observe 失败不继续记去重/feedback。
- 前轮 Runner 修正保留：事件流报错即使已有部分文本也失败且不缓存，忽略非对象事件，畸形字段不触发无关属性异常。

## 追加三轮交叉复查

1. **状态与输入边界**：复核任务/checkpoint/回执路径及入口参数。HTTP 不再将 bool、小数或字符串强转成目标 ID；超大 SQLite 整数、异常反馈字段明确拒绝，非 ASCII 鉴权头不再令连接异常中断。所有 proposal 批次统一限额，删除非持久路径静默截断。共用 ID/显著性解析，坏集合、NaN、超大数不再使整批崩溃或误赋最高分。
2. **模型/传输/调用链**：无法解析的 candgen 产物不再当成成功的空结果，而是触发既有补抽；被动抽取来源固定到实际单窗口。非文本 chat 响应遵循 ZhipuChatError 契约。两个 chat 适配器共用容错缓存读取和原子替换，删除各自的重复读写。向量统一稳定归一化，分块抵消明确失败。插件按 part 保存最新文本、按消息角色筛选助手内容，并清除已结束回合的状态。run_real 补入流尾窗口、保留来源，仅计实际注入的窗口/候选，不回头改变检索结果。
3. **反向验证与复验**：14 个新增 Python 参数化用例在本轮修改前全部失败，修改后全部通过；3375 组异常元数据组合未再产生未预期异常或非法 ID/显著性。复查最终差异、既有故障恢复测试、两套 NumPy、插件以及模拟轨迹。

接口收紧：HTTP 记忆 ID 必须是 JSON 整数；parse_generation 无合法载荷时抛 ValueError（合法空数组仍成功）；超出 50 条的提议整批拒绝。历史缓存字符串候选、十进制来源 ID 和整值浮点来源 ID 仍兼容。插件若缺少角色元数据则不把未知文本当作助手回答；这不等于实现了可靠重传。

## 明确保留

- 旧 Pool 编码、NumPy 版本及状态字段兼容读取；实际实验使用的仿真/metrics、备用语义后端。
- HTTP 回调、协议签名、SQLite row_factory、动态指标、依赖注入：不能因静态工具找不到消费者就判死代码。
- 持久任务、回执、checkpoint、在位回滚及故障恢复测试：它们覆盖不同失败窗口，不是可以随意删去的重复层。

## 合并前历史验证和边界

- NumPy **2.4.6 / 1.26.4**：各 **338 passed**（追加复查前 324 项；未删故障恢复覆盖）。
- Bun：**20 passed / 49 assertions**。运行实际插件模块，但工具注册/外部 I/O 使用 mock，不是 OpenCode/API 的 L3。
- 所有 10 个合成预设 × seeds 0/1 × 220 步：共 **4400 步**，本次清理前后完整逐步指标 JSON 一致；未重写历史产物。
- 全部自有 Python 的 Ruff F/E9、编译和 diff 空白检查通过。
- 语义队列/L0 outbox 的完整持久化、退役与迟到信用、插件可靠重传、来源内容真实性验证、真实 OpenCode/API L3 仍不在本次清理完成范围内。

收敛结论只适用于上述本地复查与回归证据，不表示生产零缺陷；未做真实 OpenCode/API、真实断电或多进程部署认证。
