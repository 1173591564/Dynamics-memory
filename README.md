<div align="center">

# Dynamics-memory

**LLM agent 的有界长期记忆层**

把连续、嘈杂、前后矛盾的项目交互，蒸馏成一个不会堆成"史山"的记忆库。<br/>
新会话里一句"接着搞"，agent 就知道进行到哪、上次卡在哪。

![tests](https://img.shields.io/badge/tests-211%20passed-brightgreen?style=flat-square)
![engine](https://img.shields.io/badge/engine-LLM--free-blue?style=flat-square)
![status](https://img.shields.io/badge/status-research%20preview-orange?style=flat-square)

[架构](#架构推式捕获--拉式修复) · [动力学](#记忆动力学) · [验证状态](#验证状态) · [运行](#运行) · [设计文档](docs/ouroboros.md)

</div>

---

## 30 秒上手

```bash
pip install numpy pytest
cp .env.example .env          # ZAI_API_KEY=...

python -m pytest tests/                          # 187 passed
python -m hybrid_memory.server --project <dir>   # 或被 opencode 插件自动拉起
```

接入 opencode（官方 CLI 即可，无需源码）：

```bash
npm i -g opencode-ai
cd <本仓库> && opencode        # .opencode/plugin/memory-bridge.ts 自动加载并拉起 sidecar
```

<sub>给别的项目用：把 `memory-bridge.ts` 软链到 `<项目>/.opencode/plugin/`。插件的
`@opencode-ai/plugin` 依赖按软链的真实路径解析，所以要先在本仓库里跑一次 opencode
（或 `cd .opencode && npm i @opencode-ai/plugin`）让依赖装好。</sub>

```text
交互回合 ──observe──→ L0 日志 + candgen 蒸馏 → 记忆池
问答     ──search───→ top-k 记忆注入（<relevant-memories> 块）
miss    ──信号──────→ 后台调查员翻日志 → propose 写回
```

## 为什么不用现成的两条路

| 路线 | 死因 |
|---|---|
| 全量 log 塞 context | 每轮付 O(log) 的 prefill+KV 扫描，随项目历史线性变贵 |
| 原文入向量库 | 冗余、过期、互相矛盾的副本堆成史山，旧状态压过新状态 |

**log 不是记忆，log 是证据。** 记忆是蒸馏产物，进池要过动力学与置信门控；
日志留在 L0 冷层，只在需要时按计量回展——永不整段进 prompt。

## 架构：推式捕获 + 拉式修复

```mermaid
flowchart LR
    subgraph PUSH["推 · 被动捕获（每轮自动）"]
        direction TB
        U["交互回合"] --> L0[("L0 日志库<br/>SQLite · FTS5")]
        L0 --> CG["candgen<br/>LLM 蒸馏"]
    end

    CG --> CP[("候选池")]
    CP -->|"V &gt; θp"| MP[("记忆池<br/>容量封顶")]
    MP --> INJ["top-k 注入<br/>agent context"]

    subgraph PULL["拉 · 信号驱动修复"]
        direction TB
        SIG["recall_miss<br/>extract_due"] --> AW["AgentWorker<br/>预算 · 日限额"]
        AW --> INV["调查员 agent"]
    end

    INV -->|"log_* 工具<br/>before=t 因果上界"| L0
    INV -->|"propose"| CP
    INJ -. "用户纠正 / agent 翻日志" .-> SIG
    L0 --> TR["触发扫描<br/>零 LLM"] --> SIG

    classDef store fill:#E8F4FD,stroke:#2B8CBF,color:#0B4F6C
    classDef llm fill:#FFF3E0,stroke:#E8963C,color:#7A4A00
    classDef signal fill:#FDECEF,stroke:#D65F7F,color:#8A2444
    classDef agent fill:#EFE9FB,stroke:#8B6FDB,color:#4A3791
    classDef io fill:#E9F7EF,stroke:#3E9B6A,color:#1E5E3C
    class L0,CP,MP store
    class CG,TR llm
    class SIG signal
    class AW,INV agent
    class U,INJ io
```

两条回路共享同一个 L0 与 ingest 通道：

- **推·保覆盖**——每轮先落 L0 再蒸馏，不靠 agent 自觉；candgen 失败不丢
  单元，转 `extract_due` 交修复回路
- **拉·补漏**——`recall_miss`（用户纠正 / agent 用了 log_*）与 `extract_due`
  （决策·数字·新实体触发）驱动后台调查员翻日志、核实、`/propose` 写回——
  **走同一条 ingest，无任何特权**
- **闸在服务端**——log_* 只给片段与统计，原文按字符预算回展；
  按信号计量工具调用（超限拒绝）；`before=t` 因果上界物理上锁死未来
- **火墙**——调查员是 sidecar 进程内的 function-calling 循环
  （`agent/inline.py`），只有 6 个只读工具，不经过 opencode、不调 observe，
  它的工作天然不会被记成记忆；写入只走最终 JSON → 服务端校验

## 记忆动力学

```mermaid
flowchart LR
    C[("C 候选池")] -->|"V &gt; θp"| M[("M 记忆池<br/>容量封顶")]
    M -->|"V &lt; θd"| C
    C -->|"闲置"| A[("A 归档")]
    M -. "检索压制对" .-> T["tension backlog"]
    T --> J["judge:<br/>synonym → merge · update → 新替旧<br/>contradiction → 聚合 · collision → 都留"]

    classDef pool fill:#E8F4FD,stroke:#2B8CBF,color:#0B4F6C
    classDef cold fill:#F5F5F5,stroke:#9E9E9E,color:#424242
    classDef hot fill:#FDECEF,stroke:#D65F7F,color:#8A2444
    classDef judge fill:#FFF3E0,stroke:#E8963C,color:#7A4A00
    class C,M pool
    class A cold
    class T hot
    class J judge
```

| 机制 | 一句话 |
|---|---|
| 价值 × 置信分离 | `V ← V·e^(−λ) + η·hit + η_s·shadow`；高价值定半衰期，置信达标才服务——高价值低置信"活着但不用" |
| 滞回 + 驱逐 + 归档 | θp>θd 防抖，容量封顶，闲置进冷层——M 池有界且自我更新 |
| 压制即检测 | 过相似未入选对自动进 tension backlog，冲突检索时自然暴露 |
| 矛盾不静默 | 同实体矛盾聚合收编（全版本+时间戳），未决 conflict 不许自信出场（contested co-serve） |
| 可溯源 | 每条记忆携带源单元 id，可回 L0 查证；`origin` 纯审计不给 V 加成 |

## 评测

评测平台 **TIDE** 与引擎完全分离（独立仓库，只经 HTTP 协议通信，真值不越过边界）。
设计见 [`docs/benchmark-design.md`](docs/benchmark-design.md)。

sidecar 为评测提供的两个能力：

| 参数 | 端点 | 作用 |
|---|---|---|
| `passive` | `GET /recall?passive=1` / `POST /search {"passive": true}` | 在引擎副本上检索：不改任何状态、不登记 retrieval_id（评测探针用） |
| `budget_tokens` | 同上 | 上下文按 `approx_tokens` 计数截断整行（CJK 单字 / ASCII 词 / 符号各记 1） |

<sub>旧的 experiments/ 评测已整体移除：其仿真与引擎共用真值对象、口径无法识别聚合输出、
样本量不足以支持结论，数字不再引用。</sub>

## 配置

| 环境变量 | 默认 | 作用 |
|---|---|---|
| `MEMORY_AGENT` | on | `off` 只跑被动链路 |
| `MEMORY_AGENT_DAILY_CAP` | 200 | 调查员日调用上限 |
| `MEMORY_AGENT_MODEL` | glm-5.3-flash | 调查员模型（旧 `provider/model` 写法兼容） |
| `MEMORY_BRIDGE_PORT` | 17872 | sidecar 端口 |
| `ZAI_API_KEY` | — | LLM 凭证（candgen / judge / recognizer / 调查员） |
| `ZAI_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | OpenAI 兼容端点（chat / embeddings），可换代理或本地 mock |

<sub>调查员默认启用：有 API key 就自动消费信号（不依赖 opencode）。
`GET /signals` 看队列、预算用量与 miss_type 分布；诊断落 `diagnoses.jsonl`。</sub>

<details>
<summary><b>目录结构</b></summary>

```text
hybrid_memory/
  core/          引擎：types / engine / ingest / retrieval / maintenance / signals
  logstore.py    L0 日志层：SQLite + FTS5 + mentions 倒排 + 可选向量 RRF
  triggers.py    确定性触发扫描（零 LLM）
  worker.py      judge / recognizer / consolidator 两阶段锁调度
  agent/         调查员：investigator（契约）/ inline（进程内工具循环）/ loop（AgentWorker）
  candgen/       被动蒸馏器
  interaction.py 对话单元 / 窗口类型
  server.py      sidecar HTTP 面
.opencode/       plugin/memory-bridge.ts（主 agent 桥）
docs/            ouroboros.md（pull 回路设计）+ benchmark-design.md（TIDE 评测设计）+ opencode-learning/
tests/           pytest（sim_world.py / sim_embed.py 是引擎单测夹具，不是评测）
```
</details>
