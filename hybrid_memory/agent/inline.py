"""兼容 shim（H1/P1）：已移至 `hybrid_memory.legacy.inline`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
from hybrid_memory.legacy.inline import TOOLS, InlineInvestigator

__all__ = ["TOOLS", "InlineInvestigator"]
