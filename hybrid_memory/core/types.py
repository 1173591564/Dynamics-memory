"""核心数据类型：Memory/Pool + Event/Query/Retrieval。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np


class Pool(Enum):
    CANDIDATE = "C"
    MEMORY = "M"
    ARCHIVE = "A"


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


@dataclass
class Event:
    belief_id: int
    value: str
    text: str
    src: tuple = ()             # 溯源：源单元 id（基准证据映射用）


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
    n_shortlisted: int = 0
    n_useful: int = 0
