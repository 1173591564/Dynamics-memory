"""兼容 shim（H1/P3）：已移至 `hybrid_memory.store.tasks`（单状态机 + KindPolicy）。

冻结消费者（tests）用；产品代码走 canonical 路径。注意：旧 claim_semantic/
store_semantic_result/complete_semantic/retry_semantic/recover_semantic_expired
方法已删除（P3 exit），调用方切统一 API。
"""
from hybrid_memory.store.tasks import (SEMANTIC_KINDS, WORKFLOW_KINDS,
                                       CaptureConflict, CheckpointConflict,
                                       TaskLeaseLost, TaskQueueFull, TaskStore,
                                       encode)

__all__ = ["SEMANTIC_KINDS", "WORKFLOW_KINDS", "CaptureConflict",
           "CheckpointConflict", "TaskLeaseLost", "TaskQueueFull", "TaskStore",
           "encode"]
