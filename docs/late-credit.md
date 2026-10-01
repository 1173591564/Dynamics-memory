# 第 4 批：退役、迟到反馈、延迟 shadow 信用

基点是第 3 批 `3ba2f95`。本批只修信用在退役和重启之后的归属与存活。不改来源正文校验，不改 `agent/`，不声称远程模型或 OpenCode L3。

## 决策账本

| 问题 | 选择与理由 | 放弃的方案 | 受影响调用方 | 选错后的失败模式 | 验证 |
|---|---|---|---|---|---|
| shadow 何时算被接受 | 检索把待结算条目写入与检索效果同一份 checkpoint。信用要等非 synonym 裁决才入账 | 检索时立刻入账（破坏恒延迟，现有测试会失败） | `retrieve`、`submit_verdicts`、`/resolve`、语义冲突应用 | 重启后裁决成功但信用消失，记忆被当成闲置退役 | 检索提交后 `os._exit`，重启再裁决，`d_shadow == 1` 且再裁决不加 |
| 队列满的待结算项 | 仍按 `shadow_pending_cap` 丢最旧并计 `n_shadow_dropped`。丢掉的不能重建 | 容量满时拒绝检索 | 压制路径 | 静默丢信用或检索整体失败 | 既有有界测试仍在；本批不把丢弃说成可恢复 |
| 裁决后谁有提交权 | `/resolve` 与语义冲突应用把消解和待结算列表同一事务写入。任务路径仍由外层回执事务提交，内层不再另开事务 | 只改内存，等下次 `/save` | `resolve`、`complete_semantic` | 裁决已返回但崩溃后续跑同一对，信用记两次 | 裁决返回后杀进程，重启只见一次信用 |
| 退役后的迟到信用 | 沿 superseded/aggregated 追到当前代表并记在代表上。链断裂则不记、不复活尸体。纯闲置归档仍复活 | 记在原对象并把它拉回候选池；或一律丢弃 | `submit_relevance`、`_issue_shadow_credit` | 已取代条目重新出场，或后继者永远拿不到这次使用 | 先 update 取代，再结算 shadow：尸体仍归档且 `superseded_by` 不变，代表 `d_shadow == 1` |
| 反馈注册表被退役 | 任务载荷里的 selected id / used 是依据。注册表对象缺失或 id 不一致时按载荷记账，任务完成回执防止再记。缺失 id 记 0 并完成，不无限重试 | 继续抛错直到任务死掉 | `_apply_semantic` | 反馈已接受但注册表挤出后信用丢失，或热重试 | 接受反馈后删掉注册表对象再跑 worker，命中一次；再跑不加 |
| 旧快照 | 没有 `shadow_pending` 的 checkpoint 当作空列表启动。字段在但格式坏则拒绝启动，不用旧 `state.pkl` 顶上 | 缺字段也拒绝启动 | 启动加载 | 旧档无法启动，或坏列表被当成没有待结算 | 缺字段能开；坏字段启动失败 |
| 模型结果迟到 | 仍以任务租约和完成回执为准。shadow 列表跟着 checkpoint 版本走，不单独按模型输出覆盖 | 用模型返回的旧 pair 直接改 V | 语义 worker | 过期裁决把已前进的信用再加一遍 | 完成回执之后再应用，信用不变 |

## 不变量

1. checkpoint 里有待结算 shadow，且随后非 synonym 裁决提交，则代表恰好获得 1 次 `d_shadow`，包括进程在两条记录之间死亡。维护点：`_state` / `_load` / `_settle_shadow`。故障测试：`os._exit`。
2. 已取代或已收编的记忆不会因迟到信用被复活。维护点：`_credit_hit` / `_issue_shadow_credit`。故障测试：先 `update` 再结算。
3. 已完成的 feedback 任务在注册表对象消失后不会第二次记账。维护点：`complete_semantic` 回执 + 载荷记账。故障测试：删除注册表后应用，再应用。

纯闲置归档被有用命中复活的旧行为保持不变。

## 自查（不是独立审查）

| 目标 | 实现 | 测试 | 剩余风险 |
|---|---|---|---|
| 重启后未结算的 shadow 仍能记一次 | checkpoint 带 `shadow_pending`；缺字段当空列表，坏字段拒绝加载 | `test_shadow_pending_survives_restart_and_settles_once`（`os._exit`） | 超过 cap 丢掉的条目不能重建 |
| 迟到信用记在当前代表，不复活尸体 | `_credit_hit` 沿 superseded/aggregated 追链 | `test_late_shadow_credits_successor_not_retired_member` | 链断裂则记 0，不补发 |
| 注册表消失后反馈仍按载荷记一次 | `credit_shown` + 完成回执 | `test_feedback_after_registry_pop_credits_once` | 记忆本身已被删除时记 0 并完成 |
