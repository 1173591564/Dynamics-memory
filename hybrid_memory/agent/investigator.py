"""兼容 shim（H1/P1）：已移至 `hybrid_memory.legacy.investigator`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.legacy.investigator import (INVESTIGATOR_SYS, KINDS,
                                               MISS_TYPES, VERDICTS, Budget,
                                               Investigation, build_payload,
                                               parse_investigation)

__all__ = ["INVESTIGATOR_SYS", "KINDS", "MISS_TYPES", "VERDICTS", "Budget",
           "Investigation", "build_payload", "parse_investigation"]
