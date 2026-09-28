# v0.1 结果（2026-09-28）

- `v0.1-meta.md`：元评测，B=64，30 条流 / 390 探针，**PASS**（锚点 3 项 + 特异性 42 格 + 剂量-反应 2 项）。
- `v0.1-dm-mock-report.md`：Dynamics-memory（`tide-eval` 分支，`--no-agent`）vs 参照系统，B=64/256。

**⚠️ Dynamics-memory 这组数字跑在规则化 mock LLM 上**（candgen 只抽含数字/决策关键词的助手句，
judge 用 Jaccard + 数字差异规则），不代表真实模型下的质量；能读的是**结构性**结论：

1. **V（修订）u<0**：新值在，旧值也在——以"⚠️未决冲突"行被一起端出。`tension_delay=20`
   而探针在更新后 10 轮，judge 还没轮到。检索层按账本记为有害注入；冲突标记对读者是否有用，
   要到 T1 回答层（固定读者）才能判。
2. **P（传播）≈ −0.5~−0.9**：引擎没有依赖失效机制，上游改了，派生值照常服务。
3. **F（卫生）短间隔 0、Δ=128 才 0.8**：撤回语句没被抽取（mock 限制），引擎也无撤回语义，
   只能靠衰减慢慢淡出。
4. **R（保持）**：Δ≤16 满分，Δ=64 掉到 0.35（B=64）——`α·e^(−λΔt)` 近因项压过相关性。
5. **C、I 满分**，但 bm25 也满分：L1 模板下精确主体名的词面匹配就够了，**I 维在 L1 太容易**，
   需要 L2（改写话术、同义主体）才有区分度。

复现：
```bash
python /home/user/dm-run/mock_llm.py 18080 &
ZAI_BASE_URL=http://127.0.0.1:18080 ZAI_API_KEY=mock python -m tide bench --data data/l1 \
  --systems recency,bm25,parsed,dynamics-memory --dm-repo ../Dynamics-memory --out runs/dm
```
