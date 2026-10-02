"""冻结的旧管线：legacy candgen + 进程内调查员 + 内存信号 worker。只修严重回归，不再演进。"""
import warnings as _warnings

DEPRECATED = True
_warned = False


def warn_once() -> None:
    """sidecar 以 legacy 管线启动时调一次（stderr 提示，不改行为）。"""
    global _warned
    if _warned:
        return
    _warned = True
    _warnings.warn("MEMORY_PIPELINE=legacy：旧管线已冻结，请迁移到默认 trio 管线",
                   DeprecationWarning, stacklevel=2)
