"""核心数据类型：Memory/Pool + Event/Query/Retrieval。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

import numpy as np


class Pool(Enum):
    CANDIDATE = "C"
    MEMORY = "M"
    ARCHIVE = "A"


def is_visible(m: "Memory") -> bool:
    """可出场的活跃记忆：未归档、未被取代、未被聚合收编。

    去重近邻、检索候选、contested 对手、consolidation 代表、lex DF
    共用此口径；生命周期维护（maintenance）对隐藏成员仍要管衰减，
    不用本谓词。"""
    return (m.pool is not Pool.ARCHIVE
            and m.superseded_by is None
            and m.aggregated_into is None)


@dataclass
class Memory:
    id: int
    belief_id: int          # 仿真 ground truth 锚点：useful-hit/死活判据
    value: str              # 生成时刻的 belief 值（漂移后比对 staleness 用）
    text: str
    emb: np.ndarray
    pool: Pool = Pool.CANDIDATE
    v: float = 0.5
    # 终身计数（统计用）
    hits: int = 0
    shadow_hits: int = 0
    shortlisted: int = 0
    evid: int = 1           # 独立重新生成确认次数
    birth: int = 0
    last_hit: int | None = None  # 最近一次 selected（进 context）
    last_seen: int = 0      # 最近一次被生成/确认
    suppressed_by: int | None = None
    superseded_by: int | None = None
    niche_pair: int | None = None   # 已判定的异 scope 矛盾对（豁免后续压制）
    aggregated_into: int | None = None  # 被收编进聚合 memory（冲突容器代其出场）
    agg_members: tuple = ()         # 聚合 memory 持有的成员 id
    pending_review: bool = False    # 聚合体内的冲突未裁决，等人工/LLM 终裁
    src: frozenset = frozenset()    # 溯源：产生该记忆的源单元 id（candgen v2）
    # 本步增量（maintenance 消费后清零）
    d_hit: float = 0.0
    d_shadow: float = 0.0
    # 置信证据（Beta 计数，confidence_on 时才累积）
    conf_pos: float = 0.0
    conf_neg: float = 0.0
    conf_updated_at: int = 0
    salience: float = 0.5
    novelty: float = 1.0
    kind: str = "fact"
    derived_from: tuple[int, ...] = ()
    scene: str = ""


@dataclass
class Event:
    belief_id: int
    value: str
    text: str
    src: tuple = ()                   # 溯源：源单元 id（基准证据映射用）
    salience: float = 0.5
    kind: str = "fact"
    derived_from: tuple[int, ...] = ()
    conf_pos: float | None = None
    conf_neg: float | None = None
    scene: str = ""


@dataclass
class Query:
    target: int             # 目标 belief_id
    text: str


class MemorySemantics(Protocol):
    def judge(self, a_bid: int, a_val: str, b_bid: int, b_val: str) -> str: ...
    def relevant(self, belief_id: int, value: str, query: Query, t: int) -> bool: ...
    def valid(self, belief_id: int, value: str, t: int) -> bool: ...
    def embedding_key(self, belief_id: int, value: str) -> tuple: ...
    def scope(self, belief_id: int) -> str: ...


@runtime_checkable
class FeedbackSemantics(Protocol):
    """可选能力：response-level recognizer。
    实现了它，engine.feedback 才会只给真被答案用上的记忆发 useful-hit；
    缺失时退化为 selected-hit 全记。返回 None 表示识别失败——worker
    计数告警后同样退化全记，失败不静默。"""
    def relevant_set(self, texts: list, question: str,
                     answer: str) -> list | None: ...


@runtime_checkable
class ConsolidationSemantics(Protocol):
    """可选能力：scene 级巩固回调。
    实现了它，consolidation 回路才能把 pending 组蒸馏成
    kind="reflection" 记忆；缺失时该回路不产 reflection（pending
    照常修剪，不堆积）。"""
    def consolidate(self, memories: list, t: int): ...


@dataclass
class Tension:
    left: int
    right: int
    first_seen: int
    last_seen: int
    observations: int = 1


@dataclass
class Retrieval:
    selected: list[Memory] = field(default_factory=list)
    suppressed: list[tuple[int, int]] = field(default_factory=list)  # (被压, 压制者)
    contested: list[tuple[Memory, Memory]] = field(default_factory=list)
    # 入选记忆携带未决 tension 时，(入选者, 对手版本) 一并端出，不许单独自信出场
    provisional: list[Memory] = field(default_factory=list)
    # selected 中低于置信阈值的子集，下游必须标注
    n_shortlisted: int = 0
    n_useful: int = 0
    credited: bool = False    # 信用是否已结清（retrieve 就地结算或
                            # submit_relevance 置位，防重复记账）
    feedback_sent: bool = False   # 已发 feedback_pending 信号（防重复发射：
                            # 信号被丢弃时 credited 仍是 False，只靠它不够）
