"""conflict_ledger 修复与接线回归（P0-1.2 / §4.4 / A7 字段只增）。

覆盖：
- aggregates = 待裁决聚合容器及其成员（pending_review），不是 kind=="reflection"；
- truncated 真实反映有界输出（不再是恒 False）；
- tools.conflicts 兼容旧字段（left/right/left_text/right_text/first_seen/
  observations/t）并新增统一 ledger 字段；正文有界（≤200 字符）不泄超界；
- HTTP /conflicts 端到端返回统一 ledger；
- signal_id 路径维持因果界过滤。
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from hybrid_memory.core.types import Memory, Pool
from hybrid_memory.service.review import conflict_ledger
from hybrid_memory.service.tools import conflicts as tools_conflicts
from test_ouroboros import _svc


def _mem(i, pool=Pool.CANDIDATE, v=0.5, **kw):
    kw.setdefault("birth", 0)
    kw.setdefault("last_seen", 0)
    return Memory(id=i, belief_id=i + 1, value=f"v{i}", text=f"记忆正文{i}",
                  emb=np.zeros(64), pool=pool, v=v, **kw)


def _ledger_service(tmp_path, **cfg):
    svc = _svc(tmp_path, **cfg)
    eng = svc.engine
    # 0-1：未决张力对；2：待裁决聚合容器（members 3,4）；5：普通 reflection
    eng.mems[0] = _mem(0)
    eng.mems[1] = _mem(1)
    eng.add_tension(0, 1, 0)
    eng.mems[2] = _mem(2, pending_review=True, agg_members=(3, 4))
    eng.mems[3] = _mem(3, aggregated_into=2)
    eng.mems[4] = _mem(4, aggregated_into=2)
    eng.mems[5] = _mem(5, kind="reflection")
    eng._next_id = max(eng._next_id, 6)
    return svc


def test_conflict_ledger_aggregates_are_pending_containers_and_members(tmp_path):
    svc = _ledger_service(tmp_path)
    try:
        out = conflict_ledger(svc)
        assert set(out["aggregates"]) == {2, 3, 4}, "聚合容器+成员，不是 reflection"
        assert 5 not in out["aggregates"], "kind==reflection 不再冒充聚合台账"
        assert out["pin_roots"] and set(out["pin_roots"]) >= {0, 1, 2, 3, 4}
        assert out["truncated"] is False
        assert [(c["left"], c["right"]) for c in out["conflicts"]] == [(0, 1)]
        assert out["pending_reviews"] == []
    finally:
        svc.tasks.close()
        svc.log.close()


def test_conflict_ledger_truncated_is_real(tmp_path):
    svc = _svc(tmp_path)
    eng = svc.engine
    n = 205
    for i in range(n * 2):
        eng.mems[i] = _mem(i)
    eng._next_id = n * 2
    for i in range(n):
        eng.add_tension(i * 2, i * 2 + 1, 0)
    try:
        out = conflict_ledger(svc)
        assert out["truncated"] is True, "超界必须如实标注，不能恒 False"
        assert len(out["conflicts"]) == 200
    finally:
        svc.tasks.close()
        svc.log.close()


def test_conflict_ledger_before_filter_and_stale(tmp_path):
    svc = _ledger_service(tmp_path)
    try:
        out = conflict_ledger(svc, before=1)
        assert out["conflicts"] == [] or all(
            c["left"] < 1 and c["right"] < 1 for c in out["conflicts"])
        # 目标缺失 → stale 标注而不是隐藏
        del svc.engine.mems[1]
        out2 = conflict_ledger(svc)
        assert out2["conflicts"][0]["stale"] is True
    finally:
        svc.tasks.close()
        svc.log.close()


def test_tools_conflicts_returns_old_fields_plus_ledger(tmp_path):
    svc = _ledger_service(tmp_path)
    long_text = "长正文" * 120
    svc.engine.mems[0].text = long_text
    try:
        out = tools_conflicts(svc)
        # 旧字段保持（A7：字段只增）
        assert "conflicts" in out and "t" in out
        c = out["conflicts"][0]
        assert c["left"] == 0 and c["right"] == 1
        assert c["first_seen"] == 0 and c["observations"] == 1
        assert len(c["left_text"]) <= 200, "统一 ledger 口径：正文有界"
        # 新增统一 ledger 字段
        assert set(out["aggregates"]) == {2, 3, 4}
        assert out["pending_reviews"] == []
        assert out["pin_roots"] and out["truncated"] is False
    finally:
        svc.tasks.close()
        svc.log.close()


def test_http_conflicts_returns_ledger(tmp_path):
    from test_server import _http
    svc = _ledger_service(tmp_path)
    try:
        with _http(svc) as (post, get, _):
            status, body = get("/conflicts")
            assert status == 200
            assert "aggregates" in body and "pin_roots" in body \
                and "truncated" in body and "pending_reviews" in body
            assert body["conflicts"][0]["first_seen"] == 0
    finally:
        svc.tasks.close()
        svc.log.close()


def test_tools_conflicts_signal_path_stays_causal(tmp_path):
    svc = _ledger_service(tmp_path)
    try:
        with pytest.raises(Exception):
            # 未登记的 signal_id 必须被 admission 拒绝（403），不是静默全量
            tools_conflicts(svc, signal_id="nope")
    finally:
        svc.tasks.close()
        svc.log.close()
