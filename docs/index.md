# 文档地图

> 状态：现行 · 本页是全部文档的入口与状态总表（P0 落地）。

## 读仓库的顺序

1. [README](../README.md) — 项目入口：30 秒上手、架构、验证状态。
2. [opencode-trio.md](opencode-trio.md) — 现行三 Agent 记忆协议（Hauler / Selector / Reviewer）。
3. [benchmark-design.md](benchmark-design.md) — TIDE 评测框架设计（与 `eval/` 对读）。
4. [analysis/target-architecture.md](../analysis/target-architecture.md) — 唯一目标架构：信号、三 Agent、三池、函数契约与清理决策；[源符号附录](architecture-inventory.md) 随同登记现状，不是第二份架构。
5. [analysis/decision-register.md](../analysis/decision-register.md) — H1–H42 历史依据；当前修订只在目标架构 N01–N28。
6. [analysis/acceptance-criteria.md](../analysis/acceptance-criteria.md) — 现有机械基线 A1–A10 + PENDING；目标新增闸门见唯一架构 §10；
   机械门：`python analysis/acceptance_check.py`（`--full` 含 bench 烟囱，`--freeze` 重冻快照）。

## 状态总表

状态含义：**现行**=行为契约，改行为必须同步改它；**已实现·归档**=该批次已落地，
文档保留为决策记录；**草稿**=方向非承诺；**冻结**=重构终稿，改动需 ADR；
**归档/参考**=只读，不约束行为；**目标·待实施**=已明确方案但未落地；
**历史基线/机械基线**=溯源或已有验证，当前修订以唯一目标为准；**基线登记**=源码符号附录，不自动批准保留。

| 文档 | 状态 | 一句话 |
|---|---|---|
| [README](../README.md) | 现行 | 项目入口与行为摘要（A2 锚定） |
| [opencode-trio](opencode-trio.md) | 现行 | 三 Agent 协议（A2 锚定） |
| [benchmark-design](benchmark-design.md) | 现行 | TIDE 评测框架设计 |
| [durable-tasks](durable-tasks.md) | 现行 | 调查任务持久化/重试/幂等写回 |
| [investigation-context](investigation-context.md) | 现行 | 调查员因果上下文与预算 |
| [persistence](persistence.md) | 现行 | L0 持久化与快照恢复 |
| [observe-recovery](observe-recovery.md) | 已实现·归档 | 第 1 批：L0 逐单元恢复 |
| [semantic-worker-recovery-plan](semantic-worker-recovery-plan.md) | 已实现·归档 | 第 2 批：语义任务持久交接 |
| [capture-delivery](capture-delivery.md) | 已实现·归档 | 第 3 批：可靠交付与幂等 |
| [late-credit](late-credit.md) | 已实现·归档 | 第 4 批：退役/迟到反馈/shadow 信用 |
| [source-authenticity](source-authenticity.md) | 已实现·归档 | 第 5 批：来源正文一致性 |
| [launch-closeout](launch-closeout.md) | 已实现·归档 | 第 6 批：启动声明收口 |
| [ouroboros](ouroboros.md) | 草稿 | 下一阶段方向，非承诺 |
| [cleanup-review](cleanup-review.md) | 归档 | 历史清理审查记录 |
| [opencode-learning](opencode-learning/README.md) | 参考 | 源码阅读笔记 |
| [analysis/target-architecture](../analysis/target-architecture.md) | 目标·待实施 | 唯一架构规范；N01–N28 收口决策及 H 条款修订 |
| [源符号附录](architecture-inventory.md) | 基线登记 | 逐模块/函数输入输出、源码位置、处置与覆盖检查 |
| [analysis/decision-register](../analysis/decision-register.md) | 历史基线 | H1–H42 依据；当前修订在唯一目标 §9 |
| [analysis/acceptance-criteria](../analysis/acceptance-criteria.md) | 机械基线 | 已有 A1–A10 + PENDING；新增闸门在唯一目标 §10 |
| [contract_snapshots](../analysis/contract_snapshots/) | 冻结 | /health、/signals、状态表快照（`--freeze` 更新需注明理由） |
