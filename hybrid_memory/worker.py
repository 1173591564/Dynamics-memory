"""兼容 shim（H1/P1）：已移至 `hybrid_memory.legacy.worker`。冻结消费者（tests/eval）用；产品代码走 canonical 路径。"""
from hybrid_memory.legacy.worker import KINDS, SignalWorker

__all__ = ["KINDS", "SignalWorker"]
