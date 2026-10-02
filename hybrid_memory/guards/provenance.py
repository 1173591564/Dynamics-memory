"""来源校验（P2 空壳，P4 通电）：存在性 + 因果上界内。"""
from __future__ import annotations

from collections.abc import Callable, Container, Iterable


def sources_known(ids: Iterable[int], known: Container[int]) -> bool:
    """引用的 id 是否全在已知集合内（纯判断，不抛）。"""
    raise NotImplementedError("guards.provenance.sources_known: P4 通电")


def validate_sources(ids: Iterable[int], *,
                     exists: Callable[[int], bool]) -> None:
    """未知 id 抛 `Rejected(\"bad_request\")`。"""
    raise NotImplementedError("guards.provenance.validate_sources: P4 通电")


def ensure_within_before(ids: Iterable[int], *, before: int | None,
                         birth_of: Callable[[int], int | None]) -> None:
    """引用不得超出因果上界 `before`；越界抛 `Rejected(\"bad_request\")`。"""
    raise NotImplementedError("guards.provenance.ensure_within_before: P4 通电")
