"""cand-gen 层：InteractionWindow → CandidateGeneration（候选 + 情境名）。

后端只承诺 CandidateGenerator 协议；在线默认 ChatGenerator。
"""
from .base import (CandidateGeneration, CandidateGenerator, MemoryCandidate)
from .prompt import (parse_generation, priority_to_salience,
                     redact_secrets, serialize_window)

__all__ = [
    "CandidateGeneration",
    "CandidateGenerator",
    "MemoryCandidate",
    "parse_generation",
    "priority_to_salience",
    "redact_secrets",
    "serialize_window",
]
