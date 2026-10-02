"""兼容 shim（H1/P1）：已移至 `hybrid_memory.legacy.{candgen,prompt}`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.legacy.candgen import (CandidateGeneration,
                                          CandidateGenerator, MemoryCandidate)
from hybrid_memory.legacy.prompt import (parse_generation,
                                         priority_to_salience, redact_secrets,
                                         serialize_window)

__all__ = [
    "CandidateGeneration",
    "CandidateGenerator",
    "MemoryCandidate",
    "parse_generation",
    "priority_to_salience",
    "redact_secrets",
    "serialize_window",
]
