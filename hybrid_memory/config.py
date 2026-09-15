"""Cfg: 全部常数 + 消融开关收一处。engine 代码里不出现"消融"概念——
experiments/run.py 把预设翻译成具体 Cfg。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Cfg:
    # ---- 检索 ----
    k: int = 5                   # top-K
    theta: float = 0.35          # 质量门 s(m,q) 下限
    tau_dup: float = 0.90        # 压制/合并阈值
    tau_sim: float = 0.80        # 软冗余带
    pi_m: float = 0.05           # M 池先验（π_C=0 基准）
    pi_a: float = -0.30          # 归档参与分（负先验，只在没更好候选时浮出）
    fresh_alpha: float = 0.10    # 新鲜度探索项强度
    shortlist_n: int = 30        # ANN shortlist 大小

    # ---- 动力学 ----
    lam: float = 0.02            # 衰减率/步
    decay_mode: str = "exponential"
    eta: float = 0.30            # useful-hit 强化
    eta_shadow: float = 0.10     # shadow-hit 部分增益
    v_init: float = 0.50         # 新候选初始 V
    theta_p: float = 1.50        # 晋升阈值
    theta_d: float = 0.80        # 降级阈值（滞回 θ_p>θ_d）
    idle_p: int = 50             # C 池闲置步数 → archive
    cap_m: int = 40              # M 池容量
    eta_c: float = 0.60          # merge 继承折损
    tension_delay: int = 20

    # ---- SF-AMS 式冗余门（Ψ_div，可选） ----
    div_gate: bool = False
    alpha_div: float = 0.5
    beta_div: float = 8.0
    tau_div: float = 0.70

    # ---- 消融开关 ----
    two_pool: bool = True        # False → 单层：全在 M，无 π 差无滞回
    shadow_credit: bool = True   # False → shadow 不计增益
    ingest_dedup: bool = True    # False → 新候选全部独立成条
    useful_hit: bool = True      # False → 入选即强化（SF-AMS 语义）
    capacity_on: bool = True     # False → M 池无界
    suppression_on: bool = True
    tension_on: bool = True
    archive_retrieval: bool = True
