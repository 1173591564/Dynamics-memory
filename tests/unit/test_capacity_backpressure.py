"""容量背压全链路回归（P0-1.1 / N12 / N17 / N06 应用耗尽）。

覆盖：
- plan_capacity：迁 A 打戳用当前 t（新迁入不再是"最旧"）；cap_context 模拟；
  全 pin 背压；retired 删除不减少上下文。
- apply_selector：批内超限走 plan_capacity；全 pin 整批拒收/回滚；
  合法产物留 ready、退避、应用 5 次后 dead 且保留产物。
- apply_maintenance / decide_human_review：新增 reflection / 人审 accept_new
  同样在 commit 前收口。
- apply_resolution：archived_at 只在真正入 A 时写（synonym/update），
  contradiction 聚合成员不写。
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from hybrid_memory.config import Cfg
from hybrid_memory.core import dynamics, maintenance
from hybrid_memory.core.types import Memory, Pool
from hybrid_memory.dispatch.worker import DispatchWorker
from hybrid_memory.errors import Degraded
from test_ouroboros import _svc


def _mem(i, pool=Pool.CANDIDATE, v=0.5, archived_at=None, **kw):
    kw.setdefault("birth", 0)
    kw.setdefault("last_seen", 0)
    return Memory(id=i, belief_id=i + 1, value=f"v{i}", text=f"t{i}",
                  emb=np.zeros(64), pool=pool, v=v,
                  archived_at=archived_at, **kw)


# ---------------------------------------------------------------- plan_capacity

def test_plan_capacity_fifo_uses_current_t_for_new_archives():
    """cap_c=1/cap_a=1：C 溢出 1 条迁 A 后 A 共 2 条，须删"存量最旧"，
    新迁入者（打当前 t）必须存活——旧实现 None→-1 把新迁入当最旧先删（FIFO 反了）。"""
    cfg = Cfg(cap_c=1, cap_m=10, cap_a=1, cap_context=100)
    mems = {0: _mem(0, v=0.1), 1: _mem(1, v=0.9),
            2: _mem(2, pool=Pool.ARCHIVE, v=0.5, archived_at=5)}
    plan = dynamics.plan_capacity(mems, cfg, frozenset(), t=100)
    assert plan["archive"] == [0]
    assert plan["delete"] == [2], "存量最旧 A 先删；新迁入(=t100)必须留下"
    assert plan["accepted"] is True
    assert set(plan["remaining"]) == {0, 1}


def test_plan_capacity_without_t_treats_new_archive_as_newest():
    """t 缺省时新迁入按"最新"处理（不允许被优先删除）；存量缺戳仍视为最旧。"""
    cfg = Cfg(cap_c=1, cap_m=10, cap_a=1, cap_context=100)
    mems = {0: _mem(0, v=0.1), 1: _mem(1, v=0.9),
            2: _mem(2, pool=Pool.ARCHIVE, v=0.5, archived_at=None)}
    plan = dynamics.plan_capacity(mems, cfg, frozenset())
    assert plan["delete"] == [2], "存量缺戳(=最旧)先删，新迁入不受影响"


def test_plan_capacity_cap_context_simulation():
    """cap_context 超限：即使 A 池未满，也要按 FIFO 补删无保护非退役 A；
    retired 条目的删除不减少上下文。"""
    cfg = Cfg(cap_c=10, cap_m=10, cap_a=10, cap_context=2)
    mems = {
        0: _mem(0, v=0.9), 1: _mem(1, v=0.8),           # C 非退役（不可删，只可迁）
        2: _mem(2, pool=Pool.ARCHIVE, v=0.5, archived_at=3),   # A 非退役 → 可减上下文
        3: _mem(3, pool=Pool.ARCHIVE, v=0.5, archived_at=4,
                superseded_by=0),                        # A retired → 删了也不减上下文
    }
    plan = dynamics.plan_capacity(mems, cfg, frozenset())
    # 上下文 4（0,1,2 非退役 + 0? 计：非退役=0,1,2）超 cap_context=2 → 补删 2
    assert plan["accepted"] is True
    assert plan["delete"] == [2]
    assert set(plan["remaining"]) == {0, 1, 3}


def test_plan_capacity_cap_context_all_pinned_backpressure():
    cfg = Cfg(cap_c=10, cap_m=10, cap_a=10, cap_context=1)
    mems = {0: _mem(0, v=0.9), 1: _mem(1, v=0.8),
            2: _mem(2, pool=Pool.ARCHIVE, v=0.5, archived_at=3)}
    plan = dynamics.plan_capacity(mems, cfg, frozenset({0, 1, 2}))
    assert plan["accepted"] is False
    assert "pinned" in plan["reason"]


# ---------------------------------------------------------------- apply_selector 背压

def _fake_agents(calls):
    def fake(name, payload):
        calls.append((name, payload))
        if name == "hauler":
            return {"candidates": [{"text": "项目统一使用 bun 工具",
                                    "source_unit_ids": [payload["unit_id"]]}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
    return fake


def _pinned_pair_service(tmp_path, **cfg):
    svc = _svc(tmp_path, **cfg)
    svc.trio_mode = True
    eng = svc.engine
    eng.mems[0] = _mem(0, v=0.9)
    eng.mems[1] = _mem(1, v=0.8)
    eng._next_id = max(eng._next_id, 2)   # 手工建档必须推进 id 游标
    eng.add_tension(0, 1, 0)      # 两端均 pin；cap_c=1 无法收口
    return svc


def test_apply_selector_backpressure_rejects_and_preserves_result(tmp_path):
    calls = []
    svc = _pinned_pair_service(tmp_path, cap_c=1, cap_a=10, cap_context=100)
    worker = DispatchWorker(svc, _fake_agents(calls))
    now = [0.0]
    svc.tasks.clock = lambda: now[0]
    try:
        svc.observe("以后统一用 bun", "好的")
        worker.process_once()   # hauler 完成（selector_due 同事务接力）
        worker.process_once()   # selector 模型段完成 → 应用段首次背压
        selector = [t for t in svc.tasks.list_tasks(kinds=("selector_due",))
                    if t["state"] in ("ready", "applying")][0]
        assert selector["state"] == "ready" and selector["result"], "产物必须已持久化"
        # 应用段反复失败：背压 Degraded → 留 ready 退避，不清产物
        for i in range(5):
            now[0] += 10.0       # 越过退避窗口
            worker.process_once()
        row = svc.tasks.get(selector["id"])
        assert row["state"] == "dead", "应用 5 次耗尽进 dead"
        assert row["result"], "dead 保留旧产物"
        assert "capacity cannot be closed" in row["last_error"]
        # 整批拒收：引擎状态未被污染
        assert set(svc.engine.mems) == {0, 1}
        assert svc.engine.mems[0].pool is Pool.CANDIDATE
    finally:
        svc.tasks.close()
        svc.log.close()


def test_apply_selector_capacity_closes_under_unpinned(tmp_path):
    """可收口时：新条目正常落库，C 溢出按 V 最低迁 A 并打戳（非背压路径）。"""
    calls = []
    svc = _svc(tmp_path, cap_c=1, cap_a=10, cap_context=100)
    svc.trio_mode = True
    worker = DispatchWorker(svc, _fake_agents(calls))
    try:
        svc.observe("以后统一用 bun", "好的")
        for _ in range(6):
            if not worker.process_once():
                break
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].pool is Pool.CANDIDATE
    finally:
        svc.tasks.close()
        svc.log.close()


# ---------------------------------------------------------------- maintenance / 人审收口

def test_apply_maintenance_backpressure(tmp_path):
    svc = _pinned_pair_service(tmp_path, cap_c=1, cap_a=1, cap_context=100)
    ids = [0, 1]
    svc._semantic_model = lambda row: {
        "event": {"belief_id": 99, "value": "反思", "text": "项目状态反思",
                  "src": [], "kind": "reflection"},
        "sources": [[i, svc.engine.mems[i].last_seen,
                     svc.engine.mems[i].pool.value,
                     svc.engine.mems[i].superseded_by,
                     svc.engine.mems[i].aggregated_into] for i in ids]}
    svc.tasks.enqueue("maintenance_due", {"scene": "s", "ids": ids}, 0)
    now = [0.0]
    svc.tasks.clock = lambda: now[0]
    stats = svc.process_semantic_tasks()
    assert stats["errors"] >= 1, "单任务失败不杀整批，但必须外显"
    row = [t for t in svc.tasks.list_tasks(kinds=("maintenance_due",))][0]
    assert row["state"] in ("ready", "applying") and row["result"], "产物保留待退避"
    assert "capacity cannot be closed" in row["last_error"]
    assert set(svc.engine.mems) == {0, 1}, "reflection 已回滚"
    now[0] += 10.0
    svc.process_semantic_tasks()   # 退避后重试仍背压；SEM 耗尽 dead 由 N06 回归锁定
    row = svc.tasks.get(row["id"])
    assert row["state"] in ("ready", "applying") and row["result"], "合法产物保留"
    svc.tasks.close()
    svc.log.close()


def test_decide_human_review_backpressure(tmp_path):
    """accept_new 的新增同样 commit 前收口：target 因未决 tension 保持 pin、
    cap_a=0 收不了口 → 拒绝并回滚（同 target 的其余待审会被 stale，不能
    用来钉住 target；这里用 tension 钉）。"""
    svc = _svc(tmp_path, cap_c=10, cap_a=0, cap_context=100)
    svc.trio_mode = True
    try:
        svc.observe("旧方案用 webpack", "说明")
        eng = svc.engine
        eng.mems[0] = _mem(0, v=0.9)
        eng.mems[0].pending_review = True
        eng.mems[2] = _mem(2, v=0.9)
        eng._next_id = max(eng._next_id, 3)
        eng.add_tension(0, 2, 0)     # 未决张力：target 退役后仍被钉住
        cand = {"text": "旧方案用 webpack", "source_unit_ids": [0]}
        with svc.tasks.transaction() as conn:
            conn.execute(
                "INSERT INTO human_reviews(source_task,target_id,candidate,reason,created_at)"
                " VALUES(?,?,?,?,?)", (1, 0, json.dumps(cand, ensure_ascii=False),
                                       "test", 0.0))
        with pytest.raises(Degraded) as exc:
            svc.decide_human_review(1, "accept_new", svc.human_review_token)
        assert exc.value.code == "capacity_backpressure"
        # 回滚：target 未退役、待审仍在、A 未越限写入
        assert eng.mems[0].superseded_by is None
        assert eng.mems[0].pending_review is True
        assert len(svc.tasks.pending_reviews()) == 1
        assert all(m.pool is not Pool.ARCHIVE for m in eng.mems.values())
    finally:
        svc.tasks.close()
        svc.log.close()


# ---------------------------------------------------------------- apply_resolution 戳语义

class _ScopeSem:
    def __init__(self, scopes):
        self._scopes = scopes

    def scope(self, bid):
        return self._scopes.get(bid, "")


def test_apply_resolution_stamps_only_real_archive_moves():
    from hybrid_memory.core.engine import MemoryEngine
    eng = MemoryEngine(Cfg(), None, None)
    eng.semantics = _ScopeSem({})
    a, b = _mem(0, v=1.0), _mem(1, v=0.5)
    eng.mems.update({0: a, 1: b})
    maintenance.apply_resolution(eng, a, b, "synonym", 7)
    assert b.pool is Pool.ARCHIVE and b.archived_at == 7
    assert a.pool is Pool.CANDIDATE and a.archived_at is None

    c, d = _mem(2, v=1.0, birth=1), _mem(3, v=0.5, birth=0)
    eng.mems.update({2: c, 3: d})
    maintenance.apply_resolution(eng, c, d, "update", 9)
    assert d.pool is Pool.ARCHIVE and d.archived_at == 9
    assert c.pool is Pool.CANDIDATE and c.archived_at is None

    # contradiction：双方被聚合收编（aggregated_into），不进 A、不打戳
    eng.semantics = _ScopeSem({10: "s1", 11: "s2"})
    e, f = _mem(4, v=1.0, birth=2), _mem(5, v=0.5, birth=1)
    eng.mems.update({4: e, 5: f})
    maintenance.apply_resolution(eng, e, f, "contradiction", 11)
    assert e.aggregated_into is not None and f.aggregated_into is not None
    assert e.pool is Pool.CANDIDATE and f.pool is Pool.CANDIDATE
    assert e.archived_at is None and f.archived_at is None
    agg = eng.mems[e.aggregated_into]
    assert agg.agg_members == (4, 5)

    # collision：留痕，双方不动
    g, h = _mem(6, v=1.0), _mem(7, v=0.5)
    eng.mems.update({6: g, 7: h})
    maintenance.apply_resolution(eng, g, h, "collision", 13)
    assert g.pool is Pool.CANDIDATE and h.pool is Pool.CANDIDATE
    assert g.archived_at is None and h.archived_at is None
