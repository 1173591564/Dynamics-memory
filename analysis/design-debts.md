# Dynamics-memory 三笔设计债研究报告

> 范围：`/home/user/dynmem`（HEAD=6be60fc，已 rebase 到用户远端 9205601 之上）。
> 性质：**研究与分析，不动仓库**。唯一规格 `analysis/target-architecture.md`（下称"规范"）；
> 本文不构成第二套架构文档，所有断言尽量给出规范章节或代码坐标。
> 数字均为 Linux 沙箱实测（方法附在各节）。
> **入库注记**：文中『N46』（propose 直写效果事务化）在仓库内重排为 **N47**——与工程章程采纳的 N46 撞号，合并时按后到原则重排；见 target-architecture.md §9.3。


---

## 0. 结论先行

| 债 | 现状量化 | 真正的触发线 | 建议动作 | 估算成本 |
|---|---|---|---|---|
| ① legacy 双管线 | 7 文件 985 行 + 顶层 8 个 shim + 13 个测试文件涉及 | **PENDING-08（真实 opencode CLI 验证）完成之日**就是删除窗口打开之日 | 对拍 → 开关收敛 → 删除（PENDING-05 ADR） | 1–2 周 |
| ② checkpoint 全量 pickle | 500 条记忆 ≈ **301 KB/次**全量写（每条 ~600 B） | 单次 dump_state > 2 MB（≈3500 条）或效果频率持续 > 10/s | 先登记预算线；到线做**分段 pickle**（I5 唯一入口已备好单点接入） | 登记半天；分段 3–5 天 |
| ③ 运维画像 | 固定默认端口、单项目、人审依赖、无 OpenAPI | 多项目同机部署；或长期无人值守 | 端口分配 ADR > pin 占用指标与告警 > 备份 runbook >（最后才）OpenAPI | 2–4 天 |

一句话：三笔债都**还没到利息超过本金的时候**，但各自的"到线条件"都清晰可判。
其中 ① 的前置条件（PENDING-08）恰好是整个系统最大的一块未兑现验证——**做 PENDING-08 一石二鸟**。

---

## ① legacy 双管线：活着的平行路径（PENDING-05）

### 1.1 现状量化（实测）

- `hybrid_memory/legacy/`：**7 个文件、985 行**（investigator、AgentWorker 回路、旧 prompt/candgen 等）。
- 顶层兼容 shim：**8 个**（`server.py`、`logstore.py`、`taskstore.py`、`llm.py`、`telemetry.py`、
  `interaction.py`、`investigation_context.py`、`__init__` 再导出）——每个只做转发，但都是契约
  登记在册的"认可冗余"。
- 测试面：**13 个测试文件**引用 legacy/AgentWorker/investigator 相关符号。
- 开关：`MEMORY_PIPELINE`（config.py:110，N01 后）只支持 `opencode | legacy`，未知值拒绝启动。

### 1.2 债务的真实构成（三层，性质不同）

1. **平行执行路径**（真正的债）：信号 → 调查员（inline LLM）→ propose/resolve/diagnose 的
   legacy 回路，与信号 → 三 Agent（Hauler/Selector/Reviewer）的 opencode 路线并存。
   "什么该进记忆"在两条路上由**两套规则**决定（调查员代码 vs agent prompt+guards）。
2. **兼容垫片**（低成本债）：顶层 8 个转发文件。删除是机械劳动，风险接近零。
3. **看似 legacy 实则核心**（不是债，别误删）：signals 队列仍是活的核心设施（语义信号经
   `on_emit` 进任务库，observe 的封存交接靠它）；`InvestigationContext` 是两条路共用的上下文
   类型；`/propose` 直写端点是**长期接口**（N46 刚给它补上立即 checkpoint），删的是调查员
   回路、不是端点。

### 1.3 为什么现在还没删（规范的记账）

PENDING-05 解冻条件 = "裸引擎退役删除 ADR"。合理的删除门槛：

- **opencode 路线要先在真实环境验证过**（PENDING-08）。否则删掉 legacy 才发现真实 CLI
  路径有问题，就没有退路了。这是 ① 与 ③ 相互咬合的地方。
- 直写端点语义已稳定（N46 补齐 checkpoint 后，直写/任务两路提交语义一致）。

### 1.4 建议的收敛路径（四阶段，可中断可回退）

1. **冻结**（已在做）：legacy 不加新功能，只修 bug——工程章程的例外条款延续。
2. **对拍基建**（3–5 天）：同一信号流喂两路，产物按天 diff 归档。目的不是对齐，
   而是**量化两路分歧率**——给删除 ADR 提供证据而不是拍脑袋。
3. **开关收敛**（1 天）：默认 `opencode`，`legacy` 改为显式 opt-in 并在日志打退役倒计时。
4. **删除**（2–3 天）：legacy/ 7 文件 + 8 shim 内联转发 + 13 个测试文件的 legacy 用例
   清理；`MEMORY_PIPELINE` 白名单收窄为 `opencode`。

**红线**：删除前必须有真实 opencode CLI 端到端的通过记录（当前唯一未验证项）。

---

## ② checkpoint 全量 pickle：有界的 O(N)，不是无限债

### 2.1 现状量化（实测）

```
500 条记忆（满 cap_context）→ dump_state = 301,303 字节 ≈ 300 KB（每条 ~600 B：
64 维 float32 emb 256 B + 文本 + 元数据 + pickle 框架）
```

- 每次效果事务（observe / propose / 语义任务应用 / feedback）**全量**写一次 checkpoint 行。
- 写放大估算：1,000 次/天的效果 → ~300 MB/天 SQLite 写。SSD 上无感，但不是零成本。
- cap_context=500 是**设计上的规模墙**：规范 §4.2 把容量收口做成了硬不变量，
  这让全量 pickle 天生"有界"——这是当初选择最简正确解的合理性所在。

### 2.2 两个真实痛点（都不是"慢"）

1. **O(N) 增长**：cap 若升到 5000 → ~3 MB/次 → 每千次效果 3 GB 写；50,000 条不可行。
2. **pickle 脆弱性**：类重构（改字段名/移动类）破坏旧档。`store/state.py` 的
   RestrictedUnpickler 白名单 + STATE_KEYS 校验就是为此打的补丁——补丁有效，
   但每次动 `Memory`/引擎字段都要记得同步，这是持续心智税。

### 2.3 备选方案对比

| 方案 | 解决什么 | 代价 | 判定 |
|---|---|---|---|
| A. **分段 pickle**（mems 按哈希分段，事务只写脏段） | 写放大降 5–10× | 回滚语义重设计：`_rollback_effect` 依赖"原 Memory 对象身份不变"，跨段引用要小心；分段边界 = 效果局部性假设 | **中期正解**；I5 唯一入口（`effect_transaction`）+ N46 把 propose 直写也收进来之后，重构面已收敛到**单点** |
| B. 事件溯源（L0 已是事件源，checkpoint 只存派生态） | 彻底去全量 | 与"checkpoint 优先、损坏拒绝空启动"的崩溃语义冲突（§10.2 IO 门）；回放成本进热路径 | 否决：改动面 ≈ 重写 |
| C. 换格式（orjson/msgpack + schema 版本号） | pickle 脆弱性 | 不解决 O(N)；numpy emb 要自定义编解码；RestrictedUnpickler 那套校验要重写 | 可与 A 叠加，单独做不值 |
| D. **现状 + 预算线登记** | 明确触发条件 | 半天 | **立即做**：把"单次 dump_state > 2 MB 或持续 > 10 效果/s"写进规范运维节，超线显式拒收（吵闹失败哲学的延续，而不是悄悄变慢） |

### 2.4 建议

先 D 后 A。A 的实施前提已经成熟——这正是收尾轮的隐性收益：
**I5 把"引擎变更+checkpoint"收敛到 `effect_transaction` 单入口，N46 又把最后的直写漏洞收编**，
换 checkpoint 实现从"全仓散改"变成了"单点替换"。触发线不到就不动，到了也只需动一处。

---

## ③ 运维画像：刹车是设计，让刹车被看见是工程

### 3.1 现状清单（规范如实登记的延期项）

| 项 | 现状 | 规范记账 |
|---|---|---|
| 端口 | 默认 17872（`config.py:92`）；`--port` 可覆盖（bootstrap/review_cli 均有）但**无分配方案**，第二个项目默认撞车 | PENDING-06：解冻=端口分配方案 ADR |
| 多项目 | 每项目一个 sidecar 进程；无聚合视图、无多租户 | 规范登记为延期 |
| 人审 | `conflict_ledger`（N37）→ `review_cli.py` 拿独立 token 决定；**pin 不过期是红线**（等价于让机器裁事实矛盾） | §4.2 pin roots |
| API 发现 | 无 OpenAPI；调用方只有 opencode 桥一个 | 规范登记为延期 |
| 备份/恢复 | durable checkpoint + state.pkl 双档，损坏行为已定义（拒绝空启动/隔离 corrupt），**无 runbook** | §10.2 IO 门 |
| 真实验证 | L3 / 真实 provider / 真实 CLI 端到端未做（**Windows 侧 A1-bun 已 26 例全过**，见 §10.4 执行记录） | PENDING-08 |

### 3.2 无人值守漂移推演（这是 503 的因果链）

```
CONFLICT/张力矛盾累积 → human_reviews 队列增长 → pin roots 常驻
→ 容量收口可用空间收缩 → enforce_capacity 全 pin → Degraded(503) 拒写
```

- 503 **不是故障是刹车**：设计选择"宁可拒写，不破容量与保护"（§4.2）。
- 运维课题是**在刹车踩下之前有人看见**。当前系统的冲突产生率取决于真实负载下
  Selector 的 CONFLICT 率与张力的 contradiction 率——这恰是 PENDING-08 的空白：
  没有真实负载数据，漂移时间线无法推演。又一次指向 PENDING-08。

### 3.3 缓解选项（按性价比排序，均不碰设计红线）

1. **pin 占用率指标 + 阈值告警**（1 天）：health_view / stats 暴露
   `pin_roots 数 / cap_context`，超 70% 告警。让 503 从"突然"变"可预期"。
2. **端口分配 ADR**（0.5 天文档 + 1 天实现）：三选一——
   a) 项目目录哈希 → 动态端口段 + 落盘端口注册表；
   b) Unix domain socket（同机单用户场景最干净，桥已走 HTTP 需改）；
   c) 单 sidecar 多库路由（改动最大，多租户才需要）。
   推荐 a)：改动最小、与"每项目一 sidecar"的形态正交。
3. **备份/恢复 runbook**（1 天）：checkpoint+state.pkl+WAL 的一致性拷贝顺序、
   损坏时的"拒绝空启动"处置步骤、schema_version 升级路径（N45 已备好）。
4. **人审效率**（可选）：review_cli 已是完整闭环；可加"未决人审数"进告警，不做 pin TTL。

### 3.4 OpenAPI 为什么排最后

调用方是**一个**（opencode 桥），且协议是冻结契约（`architecture_contract.py` +
checker 强制）。OpenAPI 的价值在多消费者生态，当前不存在；等有第二个消费者再生成不迟。

---

## 4. 总排序与相互依赖

```
PENDING-08 真实验证（一石二鸟：补最大空白 + 打开 ① 删除窗口）
  └→ ① legacy 对拍→删除（PENDING-05 ADR）
② 预算线登记（半天，立即）→ 分段 pickle（触发线到再做）
③ pin 指标+告警 → 端口 ADR → runbook（与上面并行，互不依赖）
```

三笔债没有一项需要"现在就动大手术"；需要现在动的只有两件小事：
②的预算线登记和 ③ 的 pin 指标。其余都在等各自的触发条件，而条件是可观测、可判定的。

---

*方法注：legacy 规模/测试面为 `wc -l`+`grep -rl` 实测；pickle 大小为 500 条
真实 Memory 引擎注入后 `dump_state()` 三次取值（301,303 B 稳定）；端口/开关/人审
入口为代码坐标（config.py:92/110、transport/bootstrap.py:58、transport/review_cli.py:11）。*
