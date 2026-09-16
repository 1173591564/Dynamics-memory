"""cand-gen 层：InteractionWindow → CandidateGeneration（候选 + 情境名）。

backend 可换：opencode CLI / dsh / 纯 chat API，只承诺同一协议。
"""
from .base import (CandidateGeneration, CandidateGenerator, MemoryCandidate)
from .prompt import (parse_candidates, parse_generation, priority_to_salience,
                     redact_secrets, serialize_window)
from .opencode import OpencodeCliGenerator

__all__ = [
    "CandidateGeneration",
    "CandidateGenerator",
    "MemoryCandidate",
    "OpencodeCliGenerator",
    "parse_candidates",
    "parse_generation",
    "priority_to_salience",
    "redact_secrets",
    "serialize_window",
]
