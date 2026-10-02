"""三类错误 + 唯一 HTTP 映射（H24，P2 真实现）。"""
from __future__ import annotations

import pytest

from hybrid_memory.errors import (Degraded, Fatal, MemoryError, Rejected,
                                  http_status)


def test_hierarchy_and_attrs():
    assert issubclass(Rejected, MemoryError)
    assert issubclass(Degraded, MemoryError)
    assert issubclass(Fatal, MemoryError)
    e = Rejected("conflict", "已存在")
    assert (e.code, e.message) == ("conflict", "已存在")
    assert str(e) == "已存在"
    assert Degraded("queue_full", detail="d").detail == "d"


def test_http_status_table_covers_current_behavior():
    assert http_status("bad_request") == 400
    assert http_status("unauthorized") == 401
    assert http_status("forbidden") == 403
    assert http_status("direct_write_disabled") == 403
    assert http_status("not_found") == 404
    assert http_status("conflict") == 409
    assert http_status("payload_too_large") == 413
    assert http_status("unsupported_media_type") == 415
    assert http_status("rate_limited") == 429
    assert http_status("queue_full") == 503
    assert http_status("internal") == 500


def test_unknown_code_is_loud():
    with pytest.raises(KeyError):
        http_status("typo_code")
