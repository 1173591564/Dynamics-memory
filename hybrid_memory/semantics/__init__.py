"""MemorySemantics 实现：sim/world.py 是 ground-truth 版；real.py 是真实数据版。"""
from .real import RealChatSemantics, normalize

__all__ = ["RealChatSemantics", "normalize"]
