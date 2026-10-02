"""Embedder 协议与相似度工具（P4：定义已迁至 `core.types`，此处 re-export）。

core 零越层（I1）：向量契约属于领域层；旧导入路径保留兼容。
"""
from ..core.types import Embedder, cosine

__all__ = ["Embedder", "cosine"]
