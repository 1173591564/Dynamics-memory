# L2+L3 记忆抽检报告（PENDING-08 真实 provider 验证）

- **日期**：2026-10-04
- **跑法**：inline runner（协议等价进程内直连，见 §7 偏差声明）
- **模型**：glm-5.3-flash（智谱，temperature 0.0，无 thinking 字段=默认 max 档）
- **评分**：单评（Agent 逐条盲评），rubric 见 §2
- **对齐基线**：1ebb432（=origin/main）；代码分支 dev/l2l3-audit
- **本机复核状态（N52）**：以下 499/500 是原版 Agent 单评分数，不是人工验收。提交回执关联修正后，`d199d1712834` 的裁决信息改变（修正后为 task 138 的 CREATE；原表显示的 CONFLICT 系文本键错配），同主张另有 3 次 CONFLICT 进人审（review id 2 待决），§3/§5-2 表述已按修正更新，该行 disposition 需重新审查；其他题原评分保留。原始库和评分不改，离线重导出及待复核表另存。

---

## 1. 结论速览

| 指标 | 结果 |
|---|---|
| Agent 单评总合格率 | **499/500 = 99.8%**（l3 250/250=100%；l2 249/250=99.6%） |
| 缺陷数 | **1**（grounded：引用不覆盖全部主张，无编造型缺陷） |
| 五链任务 | 873 任务：811 done、62 dead（7.1%；末次错误 53 个接地拒收、9 个超时/租约/重试耗尽） |
| 记忆产出 | 292 条（l3 131 / R 32 / V 60 / C 42 / F 27） |
| faithful / atomic / disposition / relevant | **零缺陷** |
| 探针自动指标 | **本轮不具判别力**（时点探针被排空滞后竞态淹没，§4） |
| PENDING-08 判定建议 | **待独立人工复核，不消项**（附改进登记项，§9） |

## 2. 抽检设计

- **六问**（audit.py 既定 rubric，每问 pass/fail）：
  grounded=主张能在所引 L0 原文找到依据；atomic=一条一个自足主张；
  faithful=用户拍板与助手推测区分正确；disposition=Selector 裁决正确
  （该 EXIST 没 CREATE、该 CONFLICT 没静默、UPDATE 有据）；
  relevant=与项目记忆定位相关；reflection=仅 kind=reflection（本轮全为 fact，无适用样本）。
- **盲法**：worksheet 不含链路标签，audit_id→(链路,run,mem_id) 映射单独存 key.json，结算时解盲。
- **抽样**：按链路预算——L3 池 50/131；L2 四流（R/V/C/F 为同一链路的分片）合并池 50/161
  （seed=7，实际分布 V20/C16/R9/F5）；nonce 含 run 目录防跨目录 id 碰撞。
- **评分口径**：grounded 以"引用单元覆盖全部主张"为准（严于生产 `_content_grounded`，
  见 §5-⑥）。跨流同型记忆（四流重放同场景语料）不判重复；同流配对逐一核查。

## 3. Agent 单评结算（解盲后）

| 链路 | n | grounded | atomic | faithful | disposition | relevant | 总合格率 |
|---|---|---|---|---|---|---|---|
| l3 | 50 | 100% | 100% | 100% | 100% | 100% | **100.00%**（250/250） |
| l2 | 50 | 98% | 100% | 100% | 100% | 100% | **99.60%**（249/250） |

### 唯一缺陷

| audit_id | 链路/流 | 问题 | 记忆 | 说明 |
|---|---|---|---|---|
| 802f9546eedc | l2/V | grounded | "配置端口已改为 fodoge-4100（…覆盖此前的 tale-2287、derono-3650）" | 括注历史值 tale-2287/derono-3650 不在其唯一引用单元 67 中——主张有据但引用不覆盖全部主张。对照组：#26（rikuzo 链）历史值全部有引用单元支撑，判罚一致。 |

### 正面样本（值得点名）

- **偏好归纳**（#38/#41/#43/#81）：从 2-4 次重复请求正确泛化出"用户偏好具体命名/简洁代码/PR 突出动机与影响"，与单次事件记忆正确分立。
- **配置项判别**（#83/#9/#53）：mobile 部署保留天数 vs 网关保留天数、测试地址 vs 测试级别、告警前缀 vs 告警级别——同域不同项全部判对，selector 理由中引用了具体记忆 id 做比对。
- **同源单元去重**（#91/#94）：同一单元的两个分面（改写 vs 判分、片段规则 vs 标识规则）各自成条且理由明确指出同源既有记忆。
- **纠正轮捕获**（#15）：L3 纠正轮"你记错了"后的新数字被正确记录并与旧时点数据区分。
- **update 裁决实证**（#60）：旧 checker 数字记忆已迁 ARCHIVE 池（superseded），证明 update 旧方迁 A 流程在 L3 实际发生。
- **CONFLICT 不静默（N52 修正）**：docs 鉴权版本链在 l2-C 链有 3 次 CONFLICT 尝试（task 134/135/136 → 目标记忆 39，人审 review id 2 待决）；本样本记忆（id 41）实际由 task 138 的 CREATE 建立——原表"全表唯一 CONFLICT 裁决"是文本键错配的产物；全链已提交效果共 145 次 CONFLICT、1142 次 EXIST。

## 4. 自动指标（时点探针）：本轮不具判别力

- R/V/C 首轮探针 20/12/9 条：context 全空（n=0），S=0；
- F 流 16 条：context 全空，S=1.0（但其 gold 列表为空，空 context 平凡得分）。
- **根因=排空滞后竞态**：探针在喂入期按轮放置，inline 单并发排空 30-90s/任务，
  喂入 ~1s/轮——探针时刻记忆池几乎全空。S=0 测得的是"记忆还没建好"，
  S=1 测得的是"未喂入内容确实没被端出"（平凡真）。两者都不是检索质量。
- **方法论教训**：时点探针要求"该时点的排空已完成"（同步等待或 drain 后放置）；
  inline 慢排空跑法下应改设计或弃用该指标。本轮检索质量由记忆侧（§3）与
  N48 真实 CLI 冒烟侧证，探针指标如实记为无效。

## 5. 系统级发现（不计入六问缺陷，登记为改进项）

1. **值链旧值记忆滞留（最重要）**：L2-V 流端口链 solezo→dime→fodoge→tenavu→nobito→vako
   产生多代"当前值"记忆并存于 CANDIDATE 池（抽样即见 dime/fodoge/nobito/vako 四代），
   旧值未迁 A。测试上限链同理（≥4 代）。对照：L3 的 checker 数字链旧值已迁 ARCHIVE——
   L3 有纠正轮+显式张力素材，L2 纯喂入无检索无纠正轮 → 张力裁决不触发。
   **检索期若命中旧代会端出过期值**。改进方向：值变更 CREATE 后主动入队张力检查，
   或检索期对同实体多代"当前值"声明做冲突消解。
2. **值变更判罚口径不统一（N52 修正后证据更强）**：同一主张（docs 鉴权
   raretu-4857）在 l2-C 链先 3 次 CONFLICT（task 134/135/136 → 人审 review
   id 2），随后 task 138 又以 CREATE 新建记忆 41 直入候选池——同一值变更两种
   判罚并存，人审待决期间同义新记忆已可被检索。端口/上限链则一律走 CREATE。
   口径漂移意味着值链一致性处理不确定（与发现 1 叠加放大风险）。
3. **引用精确度**：#78 的 src 混入与主张无关的单元（变量改名轮）——主张有据、
   不构成编造，但溯源信噪比下降。生产校验不检查"引用最小性"。
4. **redact_secrets 误伤**：#12 把 flag 名 `--task-queue-cap` 吞成 `--ta[REDACTED]`，
   #7 出现 `取值 [REDACTED]`——脱敏正则过宽，破坏正文可读性/可用性。
5. **低价值分面**：#87"补了几个测试用例"独立成条（原场景的顺带动作）——
   无害但稀释记忆密度，hauler 的"值得提议"门槛偏松。
6. **生产校验盲区实证**：#58 类缺陷（跨单元历史主张无引用支撑）生产
   `_content_grounded` 拦不住——标识规则不匹配带连字符的值 token（tale-2287），
   仅需一个真片段即可通过。抽检标准严于生产校验，属预期互补。
7. **过程/状态配对重叠**（#3 vs #39，同流 C）：同一 README 安装场景的
   "曾重复处理"过程记忆与"已完成"状态记忆并存，信息部分重叠——
   selector 以断言类型不同为由分别建条，边界案例，不算缺陷。

## 6. 模型行为备注（glm-5.3-flash）

- **思考恒开**：`thinking.type` 仅收 `enabled`；`disabled/low/LOW` 均 400
  （code 1210"该模型始终思考"）。**力度开关是 `reasoning_effort`**（low/high/max，默认 **max**）。
- **三档 hauler 实测**（N=10 真实载荷 A/B，生产 `_content_grounded` 同尺判分）：

  | 档 | 耗时/任务 | grounding 通过率 | 密度 | 事实覆盖率 |
  |---|---|---|---|---|
  | low | 7.1s | **55.6%** | 59% | 35% |
  | high | 11.1s | **71.4%** | 55% | 36% |
  | max（现役） | 47.6-49.2s | 98.9-100% | 基准 | 基准 |

  low/high 呈"固定 6 条槽位"退化模式且成批 grounding 报废——**只有 max 可用**，
  无便宜中间档。此前"thinking 参数不可提速"的结论系字段用错，已修正。
- **temp=0 仍有漂移**：同载荷 max 档两次运行候选 6→0、10→0 条。思考模型推理路径
  非确定性；审计测的是单次实跑行为，不受影响，但复现性小节如实标注。
- **API 偶发冻结**：连接建立后状态行永不到达，urllib socket 超时在 SSL 阻塞读上
  不触发（实测挂 24min+）。已加 300s 墙钟硬上限（inline_runner._chat 线程+join），
  冻结降级为一次失败→worker 重试。冻结期间对新请求仍正常（服务端选择性饿死）。

## 7. inline 偏差与限制声明

1. **不经真实 opencode CLI**：agent 调用为进程内直连智谱 chat/completions
   （system=.opencode/agent/*.md 正文，user="Protocol message:"+JSON，
   复用生产 `_parse_text` 拒收规则）。真实 CLI 通道由 N48+冒烟覆盖。
2. **每链单并发**：DispatchWorker 串行（协议等价），非生产并行度。
3. **排空速度**：max 档 hauler 30-90s/次，五链合计净跑约 4.5 小时
   （06:00 首启→13:01 收官，含故障恢复）。
4. **时点探针失效**（§4）为 inline 慢排空的直接产物。
5. **评分者单一**（Agent 盲评，无第二评分者交叉）；grounded 判罚口径严于生产校验。
6. 运行故障与恢复全程：3 次沙箱平台重启（进程全灭，DB 无损，看门狗自动 resume）、
   2 波 API 冻结（墙钟补丁自愈）、1 次 V 链静默死亡（疑 OOM，1 分钟内救活）。

## 8. 运行账目

| 链 | 任务 | done | dead | 记忆 | 喂入单元 |
|---|---|---|---|---|---|
| l3 | 173 | 166 | 7（4.0%） | 131 | 85 |
| l2-R | 180 | 156 | 24（13.3%） | 32 | 89 |
| l2-V | 210 | 194 | 16（7.6%） | 60 | 105 |
| l2-C | 142 | 132 | 10（7.0%） | 42 | 70 |
| l2-F | 168 | 163 | 5（3.0%） | 27 | 83 |
| 合计 | 873 | 811 | 62（7.1%） | 292 | 432 |

- SQLite 末次错误复核：`ungrounded_content` 53、`attempt limit exhausted` 5、`lease expired` 1、读取超时 3。不能把 62 个 dead 全归因于接地拒收。
- R 13.3% 与 F 3.0% 是占各流全部任务的观察比例，不是 Selector 拒收率；未做显著性检验。dead 候选不在存留记忆抽样中，误拒需另行抽检。
- 基础设施：watchdog.py 保活（进程死亡自动 resume、20min 卡死兜底重启、
  l3 完成自动接力 F、F 喂轮中断整链重跑防护）；探针记录 first-pass 备份保全。

## 9. PENDING-08 解冻判定建议

PENDING-08 的完成定义（analysis/acceptance-criteria.md）：真实 provider + 人工抽检。

- **真实 provider 跑链**：五链经 inline runner；811 任务 done、62 dead。它不验证五链真实 CLI 行为；N48 仅提供独立 CLI 小样本证据。
- **L3 来源**：85 条均为 `devlog-quote`，逐字真实会话为 0，不能冒称真实会话 L3。
- **评分**：100 行原版 Agent 单评为 499/500；只反映原评分文件。修正后的裁决关联需要独立人工复核，尤其是 `d199d1712834`。
- **建议**：保留 PENDING-08；§5-1 值链收敛触发盲区与 §5-2 判罚口径已登记为 **PENDING-11 / PENDING-12**（acceptance 白名单，2026-10-04）；§5-4 脱敏误伤与场景多样性为下一轮设计/测评项；本次不修改记忆语义，也不启动 legacy 删除。
- **最终判定权归用户**。

## 10. 复现指南

```bash
# 跑链（五目录已产出，重跑需自备 key）
python -m eval.l2l3.run_audit_chain --corpus l3_corpus.json \
  --project proj-l3 --out-dir runs/l3 --inline --no-probes --drain-timeout 9000
# 断点续跑：--resume；L2 分流：--stream-id L1-R-s0；保活：watchdog.py
# 抽检
python -m eval.l2l3.audit worksheet --runs runs/l3 runs/l2-L1-*-s0 \
  --n 50 --seed 7 --out worksheet.md --key-out worksheet.key.json
# 填表（verdicts 六问 pass/fail）→ 解盲
python -m eval.l2l3.audit aggregate --filled worksheet.filled.jsonl \
  --key worksheet.key.json --runs runs/l3 runs/l2-L1-*-s0 --out aggregate.md
# 工具链自检（mock，不需要 key）
python3 eval/l2l3/selftest.py
```

产物清单：/home/user/l2l3-data/{worksheet.md, worksheet.filled.jsonl, worksheet.key.json,
aggregate.md, runs/*, watchdog.py, 各链 log}；本报告=工作区 `L2L3-抽检报告.md`
（仓库副本 eval/l2l3/REPORT.md）。

---

*评分明细见 worksheet.filled.jsonl（100 行含逐条 verdicts 与 note）。本报告待验收。*
