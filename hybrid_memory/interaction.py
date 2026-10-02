"""兼容 shim（H1/P1）：已移至 `hybrid_memory.core.interaction`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.core.interaction import InteractionUnit, InteractionWindow

__all__ = ["InteractionUnit", "InteractionWindow"]
