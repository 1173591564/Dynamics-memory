"""兼容 shim（H1/P1）：已移至 `hybrid_memory.legacy.loop`。冻结消费者（tests）用；产品代码走 canonical 路径。"""
# _dt 系旧模块原有全局量，冻结测试 test_ouroboros 经它打"明天"补丁，一并保留。
from hybrid_memory.legacy.loop import ORIGIN_BY_KIND, AgentWorker, _dt

__all__ = ["ORIGIN_BY_KIND", "AgentWorker"]
