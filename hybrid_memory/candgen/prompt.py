"""兼容 shim（H1/P1）：已移至 `hybrid_memory.legacy.prompt`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.legacy.prompt import (INSTRUCTION, parse_candidate,
                                         parse_generation, parse_ids,
                                         parse_salience, priority_to_salience,
                                         redact_secrets, serialize_window)

__all__ = ["INSTRUCTION", "parse_candidate", "parse_generation", "parse_ids",
           "parse_salience", "priority_to_salience", "redact_secrets",
           "serialize_window"]
