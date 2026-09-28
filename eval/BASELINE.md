# Dynamics-memory 跑通报告

- 测试对象：`main` 分支 @ `fedf72b`（2026-09-27）
- 环境：Python 3.13 · opencode 1.18.33（**上游 npm 版**，不是仓库里 vendored 的 fork）
- 限制：沙箱里**没有 `ZAI_API_KEY`**，所以用本地 mock 替代智谱 API。向量用的是真实本地模型 bge-small-zh-v1.5，LLM 输出由规则生成。
  **这次只验证"管道通不通"，不评估记忆质量。**

## 结论

| 链路 | 结果 |
|---|---|
| `pytest`（211 项） | ✅ 全部通过，约 6 秒 |
| 合成仿真 `experiments.run`（10 种子 × 10 预设） | ✅ 可复现，约 2.5 分钟 |
| sidecar HTTP 全部接口（observe/search/feedback/miss/log_*/propose/conflicts/signals/save） | ✅ |
| 持久化：SIGTERM 时存盘 → 重启后恢复 | ✅ 记忆、L0 日志、token 都能恢复 ⚠️ 信号队列丢失 |
| opencode 主 agent：捕获 → 注入 `<relevant-memories>` → observe → feedback | ✅ 上游 opencode 直接可用 |
| **插件自动拉起 sidecar** | ❌ **有 bug，永远不会拉起**（修复见下） |
| 调查员 pull 回路：信号 → AgentWorker → `opencode run --agent investigator` → 工具调用 → propose → diagnoses.jsonl | ✅ 可以跑通（mock 模型发出真实的 tool_calls） |
| 火墙：调查员会话不被 observe、工具白名单只有 9 个 | ✅ |
| key 错误或 API 401 时降级 | ✅ candgen 失败后单元保留在 L0，并发 `extract_due` |

## 发现的问题（按严重程度排序）

### 1. 🔴 插件永远不会自动拉起 sidecar（30dee49 引入的回归）
`call()` 失败时返回 `{ok:false, data:{error:"sidecar 不可达..."}}`，而
`get = async (p) => (await call("GET", p)).data` 取的是 `.data`，它是一个非空对象，
所以 `ready = !!(await get("/health"))` **永远为 true**。
插件打印"sidecar already up（复用）"后直接跳过 spawn，之后所有 observe 都返回 null。
**README 里"或被 opencode 插件自动拉起"这条路径现在走不通**（见 `logs/opencode_autospawn_before_fix.log`）。
30dee49 之前的 `get` 在失败时返回 null，是这次重构把它弄坏的。
修复见 `fix-plugin-health-check.patch`（4 行）。修复后自动拉起、SIGTERM 存盘、退出时 kill 都正常（见 `logs/opencode_autospawn_after_fix.log`）。

### 2. 🟠 L0 日志没有脱敏，密钥会通过 log_* 工具流到 LLM
记忆文本里的密钥被替换成了 `[REDACTED]` ✅。但原始交互原样写进了 `log.sqlite`：
- `log_search` 返回的 snippet 里有完整的 `sk-...`
- `log_stats(group_by=entity)` 把 `sk-abcdef...` 当成了一个实体
- 调查员会拿到这些内容，并发给外部 LLM

建议在 `LogStore.add_unit` 入库前先调用 `redact_secrets`，至少要在工具输出层脱敏。另外 `log.sqlite`、`state.pkl` 的权限是 644，只有 token 文件是 600。

### 3. 🟠 contested 冲突行没有上限，注入块会膨胀
`retrieval.py` 会把"入选记忆的所有未决 tension 对手"全部端出来，没有数量上限。
测试中 top-k=5，注入块却有 **16 行**，其中 11 行是 ⚠️未决冲突。
和 README 说的"有界"相矛盾。建议加上 `contested_k`，比如每条入选记忆最多带 1 个对手、总共最多 3 行。

### 4. 🟡 信号队列不持久化
`save()` 没有保存 `signals` 和 `_shadow_pending`。重启后，排队中的 `recall_miss` / `extract_due` 全部丢失（实测 22 条变成 0 条）。
插件在每次 opencode 退出时都会 kill sidecar，所以这不是边缘情况。
tension 会从状态里重新老化出来，但 pull 回路的输入丢了就是丢了，`candgen_failed` 单元也就不会再被补抽。

### 5. 🟡 多个项目同时开，只有第一个有记忆
端口固定是 17872。第二个项目的插件会把第一个项目的 sidecar 当成"已存在"来复用，然后 token 不匹配返回 401，记忆功能就停了，只在 stderr 打一行日志（见 `logs/opencode_second_project.log`）。
好在 token 机制挡住了跨项目串数据。建议端口按项目路径哈希生成，或者 `/health` 返回 project 路径，由插件核对。

### 6. 🟡 其他
- 插件 spawn 写死了 `python`，只有 `python3` 的系统（macOS、较新的 Ubuntu）会直接失败
- API 地址写死成 `open.bigmodel.cn`，没有 base URL 配置项（这次只能在进程内改 URL 才能测）
- propose 的溯源校验只检查"unit 存在且不来自未来"，不检查"内容确实出自这个 unit"。mock 调查员把 unit 3 的内容挂到了 unit 32 上，也被接受了
- 助手**答错的内容**也会被蒸馏成记忆（实测"cap_m 是 40"、"evidence recall 大约是 0.5"都进了池子）。用户纠正会触发 recall_miss，但不会压低那条错误记忆
- 36 轮之后 M 池仍然是 0，所有注入都来自 C 池，和第一次分析的结论一致

### 7. 仿真结果（用你自己的仿真器和当前代码跑的）
```
ours          recall=0.792 eff=0.691 pollM=0.102 maxM=8
decay_only    recall=0.837 eff=0.746                 ← 两项都高于 ours
abl_no_dedup  recall=0.849 eff=0.752 pollM=0.080     ← 两项都高于 ours
abl_no_tension recall=0.833 eff=0.725 pollM=0.103    ← 两项都高于 ours
flat          recall=0.917 eff=0.227 maxM=706
```
在你自己设计的仿真环境里，去掉强化（decay_only）、去掉 dedup、或去掉 tension，都在 recall 和 ctx_eff 上同时高于完整版。这值得在 README 里正面回应。

## 复现
```bash
git clone https://github.com/1173591564/Dynamics-memory && cd Dynamics-memory
pip install numpy pytest fastembed
python /path/to/dm-run/mock_llm.py 18080 &                       # mock 智谱
MOCK_BASE=http://127.0.0.1:18080 ZAI_API_KEY=mock \
  python /path/to/dm-run/run_sidecar_offline.py --project /tmp/proj --no-agent &
python /path/to/dm-run/drive.py 17872 /tmp/proj full            # 按插件时序驱动
```
opencode 端到端测试：在项目目录的 `opencode.json` 里把 `zhipu-env.baseURL` 指向 mock，并把插件复制或软链到 `.opencode/plugin/`，然后运行 `opencode run "..."`。
