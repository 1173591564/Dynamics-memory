# TIDE — 评测平台

**T**emporal **I**ntegrity & **D**emand-aware **E**valuation。与被测记忆引擎**分离**：平台持有时钟、
账本与判分；被测系统只通过 `reset / ingest / serve(query, budget, passive)` 协议交互，真值永不越界。
设计全文见 `../docs/benchmark-design.md`（本目录实现其中的 L1 层 + T1 检索层判分 + 元评测）。

## 快速开始

```bash
cd eval
python -m tide gen   --out data/l1 --seeds 5          # 30 条流 / 390 个探针（data/ 不入库，用时生成）
python -m tide meta  --data data/l1                   # 基准自检：已知缺陷 × 能力特异性矩阵
python -m tide bench --data data/l1 --systems recency,bm25,parsed --out runs/ref
python -m tide bench --data data/l1 --systems dynamics-memory \
       --dm-repo .. --max-streams-per-dim 1 --out runs/dm        # dm-repo = 引擎仓库根
python -m tide report --run runs/dm                   # 重打已有结果
pytest -q
```

## 数据：L1 受控程序化层

先有账本、后有文本。每条流只考一个维度，流内覆盖该维度应力旋钮的全部档位；事实值是
唯一伪词 token（如 `bidemi-4629`），更新/撤回话术**不复述旧值**——所以"上下文里有没有
现值 / 旧值"对任何黑箱系统都能用字符串精确判定，无需 LLM 打分。

| 维度 | 考什么 | 旋钮档位 |
|---|---|---|
| R 保持 | 间隔 Δ 后仍能服务 | Δ = 1, 4, 16, 64, 256 |
| V 修订 | 多次更新后只服务现值 | 更新次数 k = 1, 2, 4, 8 |
| P 传播 | 上游变更后派生值失效 | 依赖深度 d = 1, 2, 3 |
| C 作用域 | 同主体多作用域取对值 | 作用域数 n = 2, 3, 4 |
| F 卫生 | 撤回的内容不再服务 | 撤回后间隔 = 1, 8, 32, 128 |
| I 抗干扰 | 同族相似事实下取准 | 干扰数 m = 0, 4, 16, 64 |

`data/real/` 存放真实语料（本地保留，不入库；L3 真实轨迹层备用）。

## 判分（检索层）

- 探针 t：系统已 ingest `turns[0:t]`，平台发 `serve(query, budget, passive=True)`；返回上下文由平台按同一
  token 规则再截断一次（`approx_tokens`：CJK 单字 / ASCII 词 / 符号各 1）。
- `S` = 现值 token 命中率（金值为空 → 1）；`H` = 含任一失效值 token；`u = S − H`。
- `NTU = (U − U_none) / (U_oracle − U_none)`：0 = 等于不用记忆，1 = 等于同预算下的理想最简上下文；
  负数 = 比不用记忆还糟（有害注入）。按流聚类 bootstrap 给 95% CI。
- 回答层：`score.classify_answer` 把回答映射到账本闭集（current / stale / conflated / OTHER），
  OTHER 才交给 LLM 闭集映射或人工（设计文档 §5.6）。

## 参照系统（`tide/systems/reference.py`）

| 系统 | 角色 |
|---|---|
| none / oracle | NTU 的 0 / 1 锚点（oracle 是唯一可见探针真值的特权系统，不参赛） |
| recency / bm25 | 朴素基线：原始日志按最近 / BM25 塞满预算 |
| parsed | 理想抽取 + 状态表（解析 L1 模板）——健全性上界 |
| parsed-{stale,noscope,nocascade,noretract,hoard,amnesic,fuzzy} | 注入一种已知缺陷，用于元评测 |

## 元评测（`python -m tide meta`）

基准本身先要过检：锚点（none=0、oracle=1、理想≥0.99）+ **干预 × 能力特异性矩阵**（每种缺陷只伤
预期维度 Δu<−0.2，其余 |Δu|<0.05）+ **剂量-反应**（amnesic×R、fuzzy×I 随旋钮单调下降）。
不过检的基准不该拿来比系统。

## 接入新系统

写一个 `MemorySystem` 子类（`tide/protocol.py`），通常 < 100 行；参考
`tide/adapters/dynamics_memory.py`（每条流起一个全新 sidecar 进程，纯 HTTP）。
不支持 `passive`（无副作用查询）的系统：声明 `Capabilities(passive=False)`，平台逐探针重放前缀。

## 已有结果

- `results/v0.1-dm-mock-report.md` — 首次 L1 全量（30 流 / 390 探针 × 预算 {64,256}）：
  dynamics-memory 总 NTU 0.15–0.30，R/C/I 接近满分，**V/P 为负**（旧值仍在被服务）——
  修订与传播是当前最差的两个维度。
- `BASELINE.md` — sidecar 端到端冒烟报告（mock LLM + 真 embedder）：链路全部打通，
  残留 L0 未脱敏、contested 行无上限、信号队列不持久化等问题。证据在 `logs/`。

## 离线冒烟工具（sidecar 级，不进 TIDE 判分）

| 文件 | 作用 |
|---|---|
| `mock_llm.py` | 本地 mock 智谱 API（离线跑通全链路，不花钱） |
| `run_sidecar_offline.py` | 用 mock 端点启动原版 sidecar（进程内改写 base URL） |
| `drive.py` | 按 memory-bridge 插件真实时序驱动 sidecar：`/search → /observe → /feedback`，覆盖纠正→recall_miss、数字更新→tension、密钥脱敏、propose/supersedes、/signals、/save |
| `preview_sidecar.py` | 预览启动器：原版 MemoryService + mock 端点 + 无鉴权调试页 |
| `checks/` | 旧仿真评测的诊断脚本（依赖已移除的旧模块，留作 `diagnosis-of-current-eval.md` 佐证；正式判分由 TIDE 账本裁决） |

```bash
python eval/mock_llm.py 18080 &
MOCK_BASE=http://127.0.0.1:18080 ZAI_API_KEY=mock \
  python -m eval.run_sidecar_offline --project /tmp/proj --no-agent
python -m eval.drive 17872 /tmp/proj full
```

## 局限（v0.1）

- L1 元评测与判分保留冻结；L2/L3 工具链见 [l2l3/REPORT.md](l2l3/REPORT.md)。本轮是 inline 模型跑链、开发日志引述与 Agent 单评，真实会话及独立人工复核仍待验收。

- 只有检索层判分；T1 固定读者回答层、T2/T3 待接。
- 预算用近似 token 计数，不对齐任何具体 tokenizer（对所有系统同一把尺子）。

## L2/L3 本地复核

- 自检：仓库根执行 `python -m eval.l2l3.selftest`，使用本地 mock，无需真实 API key；Windows 的测试启动器与 PATH 已分别兼容。
- 新包资料原样保留于 `.opencode/tmp/workspace-20261004/l2l3-data/`（相对仓库根，Git 忽略）；重导出、原评分重算、待复核工作表在同级 `rechecked/`。运行凭据不复制。
- `export_run` 是离线只读导出：sidecar 必须停止；若 Windows 强制结束后仍有已提交 WAL，只在临时 DB+WAL 副本读取，原库不动；不启动服务，不自动迁移或修复原库。
- `audit.aggregate` 拒绝漏填、未知或重复 ID；读回 `.first-pass` 并合并各 run。57 条历史探针仅作运行证据，不用于能力结论。
- 原版 99.8% 来自 Agent 单评；重绑定后的待复核表不自动沿用 disposition。原始评分和语料不重写。

## 因果探针与模型对照（N53）

`probe.t` 仍是喂第 t 轮之前；每轮写入后等待持久任务和 L0 工作排空，终点探针不遗漏。超时停止后续喂入，`run.json` 保存边界和完整上下文。`pipeline_status` 区分 `not_ready` / `write_failed` / `not_distilled` / `ready`，`retrieval_status` 区分命中、漏召回和有害旧值；F 若未证明旧值曾可见则 `unexercised_retraction`，不进入有效均值。resume 只排空，不把未来池状态用来补答历史题。L2 独立流请用 `--stream-id` 分开项目运行。

Windows 综合验收若发生 UTF-8 子进程输出被 GBK 解码，先在 PowerShell 设置 `$env:PYTHONUTF8='1'` 和 `$env:PYTHONIOENCODING='utf-8'`，再运行 `python analysis/acceptance_check.py --full`；无需改检查逻辑或全局配置。

离线装具检验：`python -m eval.l2l3.selftest --retrieval-smoke`。它使用 CREATE-only mock，分数只证明能观察命中/旧值/串作用域，不证明模型质量或内核收敛。

在仓库 `.env` 加 `DEEPSEEK_API_KEY=...`；现有 `ZAI_API_KEY` 保留。实验固定 **GLM-5.3-Flash max / DeepSeek V4.1 Flash high**，均显式发 effort。生产 `opencode.json`、Agent prompt、embedding 和 Python 语义链不改。

```bash
python -m eval.l2l3.gen_l2 --retrieval-smoke --out .opencode/tmp/probe-ab-next/corpus.json
python -m eval.l2l3.run_audit_chain --corpus .opencode/tmp/probe-ab-next/corpus.json --project .opencode/tmp/probe-ab-next/project-glm --out-dir .opencode/tmp/probe-ab-next/run-glm --agent-provider glm --capture-dir .opencode/tmp/probe-ab-next/cases
python -m eval.l2l3.model_ab --cases .opencode/tmp/probe-ab-next/cases --out-dir .opencode/tmp/probe-ab-next/ab
```

捕获的是实际 runtime payload，而不是从历史最终池猜原调用。载荷、prompt 和验证窗口有 hash，复跑前校验；目录不覆盖旧证据。`records.jsonl` 包含每次尝试、请求/响应时点、实际 API/model、effort 请求值、完整墙钟和 usage；非流式 TTFT 标未测，不能把 requested effort 当 provider 已证明执行。`source_coverage` 只衡量引用窗口单元，不是事实召回率；事实覆盖、faithful、Selector 判罚和 Reviewer 诊断由 `blind.jsonl` 的角色专属题独立复核，映射在 `blind.key.json`。填写后用 `python -m eval.l2l3.model_ab --filled filled.jsonl --out-dir <ab目录>` 结算：ID 必须完整唯一，核心题不能用 na 隐藏；逐角色检查 DS 接地门槛、耗时比 ≤0.5 和盲评不退，不将漏测角色判通过。无 usage/报价时成本为 null；`--glm-input-rate` / `--glm-output-rate` / `--glm-cached-input-rate` 及 DeepSeek 同名参数接受 USD/百万 token，结果是 usage 估算，不是账单。

A/B 通过后以新的空项目/输出/捕获目录运行同一小链 `--agent-provider deepseek`。这仍是 inline 实验；OpenCode provider/effort 转发另需真实 CLI 验证。盲评与真实 V/C/F 小链未确认前不切生产默认，不将 PENDING-11/12 视为已解决。

首轮实测（2026-10-05）结果与三层归因见 `eval/l2l3/REPORT.md` §11：探针时序成立；DS-high 提速 3.2-3.9× 但 reviewer 盲评单项失分未达门槛；三条链共同暴露 PENDING-11/12，DS 链额外暴露 PENDING-13（同批邮戳自碰撞死信）。
