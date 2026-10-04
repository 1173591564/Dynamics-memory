"""L2/L3 抽检工具链（PENDING-08 执行资产；设计见 eval/README 与 target-architecture §8）。

- L2：L1 模板语料 → LLM 改写成自然话术（值 token 逐字保留、update/retract
  不复述旧值）→ 走**原版** sidecar 子进程（真实 opencode CLI + 真实 provider）
  → 自动判分（TIDE score_context）+ 人工抽检六问；
- L3：真实项目轨迹（本地 jsonl，不入库）→ 同一条跑链 → 人工抽检六问。

本包只做评测资产，不改生产代码；语料/运行产物/评分表放仓库外
（默认 /home/user/l2l3-data/），遵循 eval/README"data/real 本地保留"约定。
"""
