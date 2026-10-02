"""兼容 shim（H1/P1）：已移至 `hybrid_memory.core.triggers`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.core.triggers import (CORRECTION_RE, DECISION_RE,
                                         DISSATISFACTION_RE, LONG_TURN_CHARS,
                                         QUANT_RE, is_correction,
                                         is_dissatisfaction, scan_unit)

__all__ = ["CORRECTION_RE", "DECISION_RE", "DISSATISFACTION_RE",
           "LONG_TURN_CHARS", "QUANT_RE", "is_correction",
           "is_dissatisfaction", "scan_unit"]
