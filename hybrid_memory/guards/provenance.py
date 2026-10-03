"""来源校验（P4/N18）：存在性 + 因果上界内。"""
from __future__ import annotations

from collections.abc import Callable, Container, Iterable

from ..errors import Rejected


def sources_known(ids: Iterable[int], known: Container[int]) -> bool:
    """引用的 id 是否全在已知集合内（纯判断，不抛）。"""
    items = list(ids)
    return bool(items and all(i in known for i in items))


def validate_sources(ids: Iterable[int], *,
                     exists: Callable[[int], bool]) -> None:
    """未知 id 抛 `Rejected("bad_request")`。"""
    items = list(ids)
    if not items:
        raise Rejected("bad_request", "empty source ids")
    for i in items:
        if not exists(i):
            raise Rejected("bad_request", f"unknown source unit {i}")


def ensure_within_before(ids: Iterable[int], *, before: int | None,
                         birth_of: Callable[[int], int | None]) -> None:
    """引用不得超出因果上界 `before`；越界抛 `Rejected("bad_request")`。"""
    if before is None:
        return
    for i in ids:
        b = birth_of(i)
        if b is None or b >= before:
            raise Rejected("bad_request", f"source {i} born at {b} is not before {before}")
