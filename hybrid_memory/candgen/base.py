"""兼容 shim（H1/P1）：已并入 `hybrid_memory.legacy.candgen`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.legacy.candgen import (CandidateGeneration,
                                          CandidateGenerator, MemoryCandidate)

__all__ = ["CandidateGeneration", "CandidateGenerator", "MemoryCandidate"]
