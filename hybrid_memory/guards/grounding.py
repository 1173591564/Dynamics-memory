"""正文接地校验（P2 空壳，P4 通电）：2 汉字 / ≥4 标识命中 / ≥8 标识全出现。"""
from __future__ import annotations

from collections.abc import Callable, Iterable


def content_grounded(candidate_text: str, window_text: str) -> bool:
    """候选正文在窗口内有依据（纯判断，不抛）。"""
    raise NotImplementedError("guards.grounding.content_grounded: P4 通电")


def cited_text(source_ids: Iterable[int],
               get_text: Callable[[int], str]) -> str:
    """取被引来源的正文拼窗（供 content_grounded 用）。"""
    raise NotImplementedError("guards.grounding.cited_text: P4 通电")
