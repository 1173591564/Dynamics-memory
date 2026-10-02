# 衔尾蛇：引擎驱动的 agent 式记忆提取

> 状态：草稿 · 下一阶段方向（引擎驱动的 agent 式提取），非行为承诺。

> 下一阶段核心任务：让 opencode agent 在引擎信号驱动下**主动操作日志**提取记忆，
> 产物经操作面回流引擎；同时主 agent 既是记忆的消费者也是生产者——闭环。
> 本文基于当前 HEAD（`f7306c1`）的真实骨架写，每一节都对应到具体文件。

---

## 0. 一句话

**引擎是头（决定何时、为何、查什么），agent 是手（用工具拉证据），操作面是嘴（吃回产物）。
日志永远不进 prompt，只经计量的 `log_window` 按需回展。**

## 1. 现状：推式流水线及其结构性盲区

```
memory-bridge.ts                 server.py                      engine
session.idle ──/observe──▶ InteractionUnit(单轮) ──▶ candgen(整轮文本进 prompt) ──▶ Event ──▶ C 池
                                      │
                                      └── unit 被丢弃，src 指向虚空
```

| 盲区 | 根因 | 后果（README 自述） |
|---|---|---|
| 只见单窗口 | candgen 输入 = 当前 K 单元 | 跨窗口规律不可见；实体演化链断裂 |
| 没有需求信号 | 抽取发生在"用"之前 | 只能猜将来有用什么 → 覆盖率 ~18% |
| 漏记不可逆 | 日志不落盘 | prompt 被迫"覆盖优先、宁可多记" → 池噪声 |
| 裁判无证据 | judge 只看两段文本 | `scope()` 恒空，条件化合并从未触发 |
| worker 无手 | 四个 agent 壳 `tools:"*":false` | 语义工作退化为一次性 LLM 调用 |

**关键推论**：有了 L0 存储 + 需求驱动的修复回路，"漏记"就从不可逆损失变成可回填的
缓存缺页。抽取器可以从"宁可多记"变成"宁可少记"——这是整个架构最大的红利，
不是附带好处。

## 2. 目标形态

```
                 ┌────────────── 主 agent（消费者 + 机会生产者）──────────────┐
                 │ 收到 <relevant-memories> → 作答                               │
                 │ 记忆不够时：log_search / log_timeline / log_window 自己下钻      │
                 │ 日志里有、记忆没有：memory_propose（带 src）                    │
                 └──────┬─────────────────────────────────────────▲──────────┘
     observe / feedback / 工具使用痕迹                                  /search 注入
                        ▼                                               │
                 ┌────────── 引擎（头）：L0 索引 + 动力学 + 信号 ──────────────┐
                 │ observe：unit 落 logstore（确定性索引，不调 LLM）+ 触发扫描     │
                 │ 信号：recall_miss / extract_due / conflict_pending / mining_due │
                 │ 操作面：/propose /resolve /diagnose（校验 src、因果、脱敏）      │
                 └──────┬─────────────────────────────────────────▲──────────┘
       信号（小载荷：问题/场景/已召回/线索，无原文）                    结构化提议
                        ▼                                               │
                 ┌────────── investigator agent（手）─────────────────────────┐
                 │ sidecar 进程内 function-calling 循环（agent/inline.py）          │
                 │ 只拿到信号 → 用 log_* 工具拉证据 → JSON 提议 → 回报              │
                 └────────────────────────────────────────────────────────────┘
```

三条不变量：
1. **引擎不调 LLM**（现有原则，保持）。它只发信号、只收结构化结果。
2. **agent 看不到引擎内部**，只经工具面/操作面交互。
3. **日志原文只经 `log_window` 进 prompt**，每次调用计量、每信号封顶。

## 3. L0 logstore（先决条件）

`hybrid_memory/logstore.py`（新），落在 `<project>/.opencode/memory/log.sqlite`：

```sql
units(id INTEGER PRIMARY KEY, t INT, scene TEXT, ts REAL,
      user_text TEXT, assistant_text TEXT, assistant_turns INT)
units_fts  -- FTS5(user_text, assistant_text, tokenize='trigram')  ← CJK 子串检索
mentions(entity TEXT, kind TEXT, unit_id INT, PRIMARY KEY(entity, unit_id))
unit_emb(unit_id INTEGER PRIMARY KEY, vec BLOB)   -- 可选，复用 embed 缓存
```

- `mentions` 由确定性正则填充：路径 / PR# / commit hash / 版本号 / 标识符 /
  URL / 环境变量名。`retrieval._ASCII_TOK` 就是它的雏形。CJK 实体不在这层做，
  交给 agent 提议时以 `entity_key` 回填。
- `observe()` 改为：**先写 logstore（同步、确定性、毫秒级），再决定是否抽取**。
- `before=t` 参数实现因果上界——回放时 agent 物理上查不到 t 之后的单元。

## 4. 工具面（agent 能做什么）

| 工具 | 返回 | 设计意图 |
|---|---|---|
| `log_search(query, before?, scene?, k=8)` | `[{unit_id, t, scene, snippet(±120字)}]` | 混合 FTS5 + 向量；**只给片段** |
| `log_timeline(entity, before?)` | 该实体全部提及，按 t 排序，每条一个片段 | 实体演化链，裁决与 update 的证据 |
| `log_stats(group_by=scene\|entity\|week, before?)` | 计数表 | 只给聚合，mining 的入口 |
| `log_window(unit_ids, max_chars=2000)` | 原文 | **唯一回展原文的通道**，每信号总量封顶 |
| `memory_search(query)` | 现有 | 避免重复提议 |
| `memory_propose(proposals[])` | `{accepted, rejected[reason]}` | 唯一写入通道 |
| `memory_resolve(left, right, verdict, entity_key?, scope?)` | 现有 + 结构化扩展 | |
| `memory_diagnose(miss_type, note)` | ack | 抽取器健康仪表 |

端点：`/log/search` `/log/timeline` `/log/stats` `/log/window` `/propose` `/diagnose`，
全部走现有 Bearer 鉴权，HTTP 面只服务主 agent（不计量）。调查员在进程内直接调服务方法并带 `signal_id`，
由服务端按信号计量与施加因果上界。

## 5. 信号面（引擎何时唤手）

| 信号 | 触发点（代码位置） | 载荷（小） | agent 任务 |
|---|---|---|---|
| `recall_miss` | ① `retrieval` 的 `thin_recall`；② recognizer 回 NONE 且问题非闲聊；③ 下一轮 user_text 命中纠正模式（`observe` 内确定性检测）；④ 主 agent 调用了 `log_*` 工具（插件侧上报） | `{q, t, scene, retrieved:[{id,t,text}], hint, entities_in_q}` | 在 `before=t` 的日志里找证据 → propose + diagnose |
| `extract_due` | `observe` 的触发扫描：新实体首次出现 / 决策词汇 / 纠正 / 数量·日期·截止 | `{unit_id, t, scene, reasons[], entities[]}` | 以该 unit 为锚，先 `log_timeline` 看实体历史，再抽取（**带上下文的抽取**，与盲抽的本质区别） |
| `conflict_pending` | 现有 | 现有 + `entity_key` 提示 | 先 `log_timeline(entity)` 再裁决，输出结构化 verdict |
| `mining_due` | `maintenance` 每 N 单元 / 每日 | `{since_t, scenes[]}` | 只读 `log_stats` / 聚类代表样本，下钻高频簇 → SOP / 偏好 / 震荡 |

信号合并用现有 `SignalQueue` 的 key 机制：`recall_miss` 按规范化问题去重，
`extract_due` 按 unit 去重，busy 时累积不重发。

### 触发扫描（替代"一股脑"的那一步）

`observe` 里新增确定性扫描，**零 LLM**：

```python
REASONS = {
  "correction": r"^(不对|不是|错了|别|不要|我说过|之前是|应该是|改回)",
  "decision":   r"(决定|改成|采用|放弃|定为|以后都|不再|必须|禁止|统一用)",
  "quant":      r"(\d+(\.\d+)?\s*(个|条|次|天|小时|GB|MB|ms|%)|\d{4}-\d{2}-\d{2}|截止|deadline)",
  "new_entity": "mentions 中首次出现的 ASCII 实体",
}
```

命中 → `extract_due`；不命中 → **不抽取**，unit 仅留在 L0。
这就是"宁可少记"的落地：漏了，`recall_miss` 会补。

## 6. investigator agent 契约

`.opencode/agent/investigator.md`：

```yaml
---
description: 记忆调查员——在引擎信号驱动下操作日志索引提取/修复记忆
mode: primary
hidden: true
model: zhipu-env/glm-5.3-flash
temperature: 0
tools:
  "*": false
  log_search: true
  log_timeline: true
  log_stats: true
  log_window: true
  memory_search: true
  memory_propose: true
  memory_resolve: true
  memory_diagnose: true
permission:
  edit: deny
  bash: deny
---
你只通过工具接触日志。附件是一个信号，不是日志。
规则：先 search/timeline 定位，再 window 回展，回展总量不超过预算。
每条提议必须带 source_unit_ids，且只能引用你实际看过的 unit。
完成后只输出 JSON。
```

**输入**（附件，< 1k tokens）：信号载荷 + 预算 `{tool_calls: 8, window_chars: 4000}`。
**输出**（严格 JSON）：

```json
{"proposals": [{"text": "...", "kind": "work_fact", "salience": 0.7,
                "source_unit_ids": [12, 15], "entity_key": "proxy/handler.ts",
                "supersedes": [memory_id]}],
 "verdicts":  [{"left": 3, "right": 9, "verdict": "update", "entity_key": "..."}],
 "diagnosis": {"miss_type": "dropped_by_candgen", "note": "..."}}
```

`miss_type ∈ {not_in_window, dropped_by_candgen, too_coarse, wrong_scene, never_logged, no_miss}`
——每一类对应不同的药，这是抽取器的健康仪表。

## 7. 操作面校验（嘴不是什么都吃）

`/propose` 在 server 侧：
1. `source_unit_ids` 非空、全部存在于 logstore、且 `unit.t < signal.t`（因果）→ 否则 422
2. `redact_secrets(text)`（现有）
3. 文本命中"记忆系统自身操作"模式（"我检索了""已裁决""合并记忆"）→ 拒收
4. 经 `engine.observe` 正常入 C 池，走同一套动力学；`Memory.origin` 记
   `passive | repair | extract | mining | user_confirmed`
5. **不给 origin 特殊 V 加成**——需求来源是否值得初始加分，交给消融决定
   （与 README"拿不出证据的不进默认路径"一致）

## 8. 火墙：衔尾蛇不能把自己吃死

| 风险 | 机制 |
|---|---|
| 递归捕获（investigator 的会话又被 observe） | 调查员是 sidecar 进程内循环，不产生 opencode 会话、从不调 observe，按构造不可能被捕获 |
| 自指记忆 | candgen prompt 已禁；`/propose` 再加模式拒收；`origin` 可审计 |
| 风暴 | 每信号 tool-call ≤ 8、window ≤ 4k 字、单次 LLM 请求超时 + 轮数上限 tool_calls+2（末轮不给工具，强制收尾）；同时只跑 1 个 investigator；每日 LLM 调用总预算；`SignalQueue` 有界（现有） |
| 幂等 | `recall_miss` key = 规范化问题；同 key 24h 内不重复修 |
| 阻塞 | worker 移出 `observe` 的锁：后台线程 `drain(锁内) → agent(锁外) → submit(锁内)`。信号里的 `Retrieval` 对象改为按 `retrieval_id` 引用 |
| 回放非确定 | 按 `(signal 指纹, prompt_version)` 缓存最终 JSON（未实现） |

## 9. 主 agent 侧（闭环的另一半）

主 agent 也拿到 `log_search / log_timeline / log_window / memory_propose`，
但**同步预算很小**（tool-call ≤ 3，window ≤ 1.5k 字）。用途：

- 用户说"接着搞"、注入的记忆明显不够 → 自己下钻两步，比等后台快
- 主 agent **调用 `log_*` 本身就是一次 miss 信号**：插件上报 `recall_miss{q, hint: tool_calls}`，
  后台 investigator 拿大预算做系统性修复
- 主 agent 在日志里找到答案后 `memory_propose` → 消费者直接成为生产者，
  这是衔尾蛇最纯粹的形态

推荐的 system 提示追加一句：
"若注入记忆不足以回答且问题涉及项目历史，先用 log_search / log_timeline 查证，
再作答；查到的事实用 memory_propose 存下来。"

## 10. 被动 candgen 的命运（分阶段，不一刀切）

| 阶段 | 被动 candgen | 理由 |
|---|---|---|
| P1 | 原样保留 | 它是对照组，也是目前唯一被证明有效的东西 |
| P2 | 仅在 `extract_due` 命中时跑，且改为"带 timeline 上下文的抽取" | 触发扫描 + L0 使"少记"安全 |
| P3 | 由 investigator 完全接管 | 前提：P1→P2 的三方评测赢了 |

## 11. 评测：有一个基线不打就不算数

三臂、同 token 预算 B（含所有 LLM 调用与注入 context）：

| 臂 | 说明 |
|---|---|
| A. passive | 现状 |
| B. passive + pull loop | 本文架构 |
| C. raw-log-at-budget | 不抽取，按相关性把原始日志片段塞满预算 B |

**赢不了 C，整个方向不成立**——因为本方向的全部论证是"agent 有选择地读日志 > 无差别读日志"。

三臂在 TIDE 评测平台上比较（独立仓库，见 [`benchmark-design.md`](benchmark-design.md)）：
A/C 走 T1 固定读者赛道的预算档，B 的修复收益（repair yield）只能在 T3 闭环赛道测；
C 即平台内置参照系统 `raw-bm25`。

## 12. 实施状态（feat/ouroboros-p1）

| 项 | 状态 | 位置 |
|---|---|---|
| L0 LogStore（FTS5 trigram + mentions + 向量 RRF + before 因果上界） | ✅ | `hybrid_memory/logstore.py` |
| 触发扫描（correction/decision/quant/new_entity/long_turn） | ✅ | `hybrid_memory/triggers.py` |
| 信号 recall_miss / extract_due；`engine.propose`；`SignalQueue.take` | ✅ | `core/engine.py` `core/signals.py` |
| `/log/*` 四端点 + 按信号预算计量 + 429/403 | ✅ | `server.py` |
| `/propose` 校验（溯源/因果/脱敏/自指/长度/supersedes） | ✅ | `server.py` |
| `/miss` `/diagnose` `/signals`；diagnoses.jsonl | ✅ | `server.py` |
| AgentWorker（预算、重试/放弃、日限额、去重、锁外调查） | ✅ | `agent/loop.py` |
| investigator 契约（提示、载荷、解析） | ✅ | `agent/investigator.py` |
| 进程内调查员（6 个只读工具的 function-calling 循环，写入只走最终 JSON） | ✅ | `agent/inline.py` |
| 插件（主 agent：捕获/注入/记账 + 工具 + log_* → /miss） | ✅ | `.opencode/plugin/memory-bridge.ts` |
| 语义 worker 两阶段锁（LLM 在锁外） | ✅ | `worker.py` |
| 旧 state.pkl 迁移（origin/entity 默认值） | ✅ | `server.py::_load` |
| recognizer NONE → recall_miss | ✅ 默认关 | `Cfg.miss_on_recognizer_none` |
| 评测接口：`/recall` 的 `passive`（引擎副本检索）与 `budget_tokens` | ✅ | `server.py::recall` |
| 三臂评测（passive / pull / raw-at-budget）、repair yield | ⏳ 在 TIDE 上做 | T1 需真实 LLM 抽取才有意义；T3 闭环未实现 |
| P2（extract_due 接管被动抽取）、mining | ⏳ 等评测 | — |

已离线验证：187 条单测（含 HTTP 往返、预算 429、提议拒绝原因、
纠正→修复→召回改善的整条回路、线程起停、重启迁移）；sidecar 进程级
冒烟（SIGTERM 存盘）；官方 opencode CLI + 插件自动拉起 + mock LLM 的
进程级端到端（捕获 → 注入 → 纠正 → 进程内调查员 → 提议入库）。
未验证：接真 `ZAI_API_KEY` 的调查质量。

## 13. 与项目原则的对齐

- 引擎不做语义判定 ✔（信号/操作面模式原封不动，只是手变强了）
- 有界 ✔（信号队列、预算、logstore 在盘上不在 context）
- 溯源 ✔（`src` 第一次真正可解引用）
- 证据分级 ✔（origin 不加成，三臂评测决定）
- 诚实口径 ✔（`miss_type` 让"抽取器为什么漏"成为可测量的东西）
