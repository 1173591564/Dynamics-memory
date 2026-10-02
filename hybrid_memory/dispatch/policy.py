"""策略表（P2：KindPolicy 数据结构先行；POLICIES 与函数 P5 通电，H7/H8/H25）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KindPolicy:
    """一类任务的认领与重试策略（静态配置，不可变）。"""

    kinds: tuple[str, ...] = ()
    claim_from: str = ""
    daily_cap: int = 0
    max_attempts: int = 1
    on_exhausted: str = "dead"      # dead | requeue（调查→dead，语义→requeue）
    lease_s: float = 300.0
    backoff: float = 0.0


POLICIES: dict[str, KindPolicy] = {}  # P5 填实（9 种 kind，H25 启动自检）


def policy_for(kind: str) -> KindPolicy:
    """取某 kind 的策略；未知 kind 抛 `Fatal`（启动自检已保证不会发生）。"""
    raise NotImplementedError("dispatch.policy.policy_for: P5 通电")


def assert_consumers(appliers) -> None:  # noqa: ANN001 — 壳，P5 定类型
    """启动自检：POLICIES 的每个 kind 必须在 appliers 有消费者，否则 Fatal。"""
    raise NotImplementedError("dispatch.policy.assert_consumers: P5 通电")
