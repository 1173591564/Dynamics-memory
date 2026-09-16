"""贝叶斯置信证据：Beta(α+pos, β+neg) 均值投影 + 证据时间折损。

discount_to 只折证据计数（pos/neg），不动 Beta 先验；
half_life<=0 表示不做时间折损。confidence_on=False 时全部 no-op。
"""
from __future__ import annotations


def discount_to(m, t: int, cfg) -> None:
    if not cfg.confidence_on:
        return
    dt = t - m.conf_updated_at
    if dt > 0 and cfg.conf_half_life > 0:
        decay = 2.0 ** (-dt / cfg.conf_half_life)
        m.conf_pos *= decay
        m.conf_neg *= decay
    m.conf_updated_at = t


def projected(m, cfg) -> float:
    return (cfg.conf_prior_alpha + m.conf_pos) / (
        cfg.conf_prior_alpha + cfg.conf_prior_beta + m.conf_pos + m.conf_neg)
