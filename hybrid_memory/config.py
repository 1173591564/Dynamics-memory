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
    lex_weight: float = 0.0      # >0 → s = cos + w·lex（词法加分，稀有词门控）

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
    defer_credit: bool = False   # True → 检索不结清，等 feedback(answer) 后
                                 # recognizer 判定哪些记忆真被用上才发 d_hit
    confidence_on: bool = False
    conf_prior_alpha: float = 1.0
    conf_prior_beta: float = 1.0
    conf_write_evidence: float = 1.0
    conf_confirm_evidence: float = 1.0
    conf_negative_evidence: float = 1.0
    conf_half_life: float = 50.0
    theta_conf: float = 0.62
    provisional_margin: float = 0.08
    provisional_k: int = 1
    salience_on: bool = False
    salience_default: float = 0.5
    salience_retention_floor: float = 0.5
    salience_retention_weight: float = 3.0
    novelty_on: bool = False
    novelty_bonus: float = 0.25
    consolidation_on: bool = False
    consolidation_salience_budget: float = 6.0
    consolidation_min_items: int = 5
    consolidation_max_items: int = 12
    signal_queue_cap: int = 256   # 引擎→LLM 信号队列容量（超限丢最旧+计数）
    shadow_defer: bool = False    # True → 压制时不裁判，shadow 信用延迟到
                                  # verdict 到达（submit_verdicts/同步裁决）时结算
    shadow_pending_cap: int = 256  # 延迟记账待结算队列容量（超限丢最旧+计数）
    capacity_on: bool = True     # False → M 池无界
    suppression_on: bool = True
    tension_on: bool = True
    archive_retrieval: bool = True
