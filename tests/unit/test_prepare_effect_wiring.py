"""prepare_effect 接线回归（P0-1.4 / N08 / §2.5）。

覆盖：
- prepare_effect 用服务真实 embedder（svc.emb）批量预计算，不再引用不存在的
  svc.embedder、不再把单个字符串传给 embed；
- engine.propose/run_ingest 接受可选 vectors=，admit_reflection/add_reflection
  接受可选 vector=；裸调用 None 维持兼容；
- DispatchWorker.process_once（selector 路径）与 apply_semantic（maintenance
  路径）真的把预计算向量穿进效果事务：候选正文只 embed 一次；
- prepare 的目标邮戳在事务内复核：漂移整批拒绝（stale 重判，不沿旧 id）。
"""
from __future__ import annotations

import numpy as np
import pytest

from hybrid_memory.core import consolidation, ingest
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.types import Event, Memory, Pool
from hybrid_memory.dispatch import effects
from hybrid_memory.dispatch.worker import DispatchWorker
from hybrid_memory.errors import ProposalRejected
from test_ouroboros import _svc, _HashEmbedder


class _CountingEmbedder(_HashEmbedder):
    def __init__(self):
        super().__init__()
        self.calls = []

    def embed(self, texts, keys=None):
        self.calls.append(list(texts))
        return super().embed(texts, keys=keys)


# ------------------------------------------------------- 向量参数（core 层）

def test_run_ingest_accepts_precomputed_vectors():
    from hybrid_memory.config import Cfg
    from tests.fakes import FakeWorld
    world = FakeWorld()
    eng = MemoryEngine.__new__(MemoryEngine)   # 绕过构造直接拼最小引擎
    eng.cfg = Cfg()
    eng.semantics = world
    emb = _CountingEmbedder()
    eng.emb = emb
    eng.mems = {}
    eng._next_id = 0
    eng.tensions = {}
    eng.add_tension = lambda *a: None

    ev = world.event(0)
    vec = emb.embed([ev.text], keys=[world.embedding_key(0, ev.value)])[0]
    before = len(emb.calls)
    ingest.run_ingest(eng, [ev], 0, vectors=[vec])
    assert len(eng.mems) == 1
    assert np.allclose(eng.mems[0].emb, vec)
    assert eng.mems[0].pool is Pool.CANDIDATE
    # 预计算路径不再触发 embedder
    assert len(emb.calls) == before


def test_admit_reflection_accepts_precomputed_vector():
    from hybrid_memory.config import Cfg
    from tests.fakes import FakeWorld
    world = FakeWorld()
    eng = MemoryEngine.__new__(MemoryEngine)
    eng.cfg = Cfg()
    eng.semantics = world
    emb = _CountingEmbedder()
    eng.emb = emb
    eng.mems = {}
    eng._next_id = 0
    eng.signals = type("Q", (), {"emit": lambda *a, **k: None})()
    eng._consolidation_pending = set()
    eng._consolidation_deferred = {}
    eng.n_consolidate = 0

    ev = Event(7, "反思", "项目当前状态反思", src=(0,), kind="reflection")
    vec = emb.embed([ev.text], keys=[world.embedding_key(7, "反思")])[0]
    m = consolidation.admit_reflection(eng, ev, [], 3, vector=vec)
    assert m.kind == "reflection" and np.allclose(m.emb, vec)
    assert m.id == 0
    # 裸调用（vector=None）维持旧路径：内部 embed
    ev2 = Event(8, "反思2", "另一条反思", src=(0,), kind="reflection")
    m2 = eng.add_reflection(ev2, [], 4) if hasattr(eng, "add_reflection") else None


def test_engine_propose_and_add_reflection_vector_params():
    from hybrid_memory.config import Cfg
    from tests.fakes import FakeWorld
    world = FakeWorld()
    eng = MemoryEngine.__new__(MemoryEngine)
    eng.cfg = Cfg()
    eng.semantics = world
    emb = _CountingEmbedder()
    eng.emb = emb
    eng.mems = {}
    eng._next_id = 0
    eng.tensions = {}
    eng.n_consolidate = 0
    eng.signals = type("Q", (), {"emit": lambda *a, **k: None})()
    eng._consolidation_pending = set()
    eng._consolidation_deferred = {}

    ev = Event(1, "v", "带向量的提议", src=(0,), origin="agent")
    vec = emb.embed([ev.text], keys=[world.embedding_key(1, "v")])[0]
    ids = eng.propose([ev], 0, vectors=[vec])
    assert ids == [0] and np.allclose(eng.mems[0].emb, vec)

    rev = Event(2, "r", "带向量的反思", src=(0,), kind="reflection")
    rvec = emb.embed([rev.text], keys=[world.embedding_key(2, "r")])[0]
    m = eng.add_reflection(rev, [0], 1, vector=rvec)
    assert np.allclose(m.emb, rvec)


# ------------------------------------------------------- prepare_effect 修复

def _selector_row(svc, uid, candidates):
    return {"kind": "selector_due", "id": 99, "t": 0,
            "payload": {"unit_id": uid, "candidates": candidates,
                        "parent_task": 1}}


def test_prepare_effect_precomputes_vectors_from_service_embedder(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    emb = _CountingEmbedder()
    svc.emb = emb
    svc.engine.emb = emb
    try:
        svc.observe("以后统一用 bun", "好的")
        cand = {"text": "以后统一用 bun", "source_unit_ids": [0]}
        row = _selector_row(svc, 0, [cand])
        plan = effects.prepare_effect(svc, row)
        assert len(plan["events"]) == 1
        assert plan["events"][0].text == "以后统一用 bun"
        assert len(plan["vectors"]) == 1, "旧实现 svc.embedder 不存在，向量分支恒空"
        key = svc.semantics.embedding_key(plan["events"][0].belief_id,
                                          plan["events"][0].value)
        expect = emb.embed(["以后统一用 bun"], keys=[key])[0]
        assert np.allclose(plan["vectors"][0], expect)
        assert plan["expected_revision"] == svc._checkpoint_revision
    finally:
        svc.tasks.close()
        svc.log.close()


def test_prepare_effect_rejects_bad_candidates_before_transaction(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.observe("正常一轮", "好的")
        row = _selector_row(svc, 0, [{"text": "幽灵事实", "source_unit_ids": [999]}])
        with pytest.raises(ProposalRejected):
            effects.prepare_effect(svc, row)
    finally:
        svc.tasks.close()
        svc.log.close()


# ------------------------------------------------------- worker 接线（向量只算一次）

def _fake_agents(calls):
    def fake(name, payload):
        calls.append((name, payload))
        if name == "hauler":
            return {"candidates": [{"text": "项目统一使用 bun 工具",
                                    "source_unit_ids": [payload["unit_id"]]}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
    return fake


def test_worker_selector_path_embeds_once(tmp_path):
    calls = []
    svc = _svc(tmp_path)
    svc.trio_mode = True
    emb = _CountingEmbedder()
    svc.emb = emb
    svc.engine.emb = emb
    worker = DispatchWorker(svc, _fake_agents(calls))
    try:
        svc.observe("以后统一用 bun", "好的")
        for _ in range(6):
            if not worker.process_once():
                break
        assert len(svc.engine.mems) == 1
        text = "项目统一使用 bun 工具"
        n = sum(1 for c in emb.calls if text in c)
        assert n == 1, f"候选正文应只 embed 一次（prepare 预计算），实际 {n} 次"
        ev_text_emb = emb.embed([text])[0]
        assert np.allclose(svc.engine.mems[0].emb, ev_text_emb)
    finally:
        svc.tasks.close()
        svc.log.close()


def test_worker_maintenance_path_embeds_once(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    emb = _CountingEmbedder()
    svc.emb = emb
    svc.engine.emb = emb
    ids = []
    try:
        svc.observe("第一轮", "好的")
        svc.observe("第二轮", "好的")
        from hybrid_memory.core.types import Event as _Ev
        svc.engine.propose([_Ev(svc.semantics.fingerprint("第一轮事实"),
                                "第一轮事实", "第一轮事实", (0,), origin="agent")], 0)
        svc.engine.propose([_Ev(svc.semantics.fingerprint("第二轮事实"),
                                "第二轮事实", "第二轮事实", (1,), origin="agent")], 1)
        ids = sorted(svc.engine.mems)
        assert ids, "前置：已有关联记忆"
        event = {"belief_id": 99, "value": "反思", "text": "项目状态反思一条",
                 "src": [], "kind": "reflection"}
        svc._semantic_model = lambda row: {
            "event": event,
            "sources": [[i, svc.engine.mems[i].last_seen,
                         svc.engine.mems[i].pool.value,
                         svc.engine.mems[i].superseded_by,
                         svc.engine.mems[i].aggregated_into] for i in ids]}
        svc.tasks.enqueue("maintenance_due", {"scene": "s", "ids": ids}, 0)
        stats = svc.process_semantic_tasks()
        assert stats["reflected"] == 1
        n = sum(1 for c in emb.calls if "项目状态反思一条" in c)
        assert n == 1, f"reflection 正文应只 embed 一次，实际 {n} 次"
    finally:
        svc.tasks.close()
        svc.log.close()


# ------------------------------------------------------- 目标邮戳复核

def test_prepare_effect_target_stamp_drift_rejected(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    try:
        svc.observe("以后统一用 bun", "好的")
        cand = {"text": "以后统一用 bun", "source_unit_ids": [0]}
        svc.engine.propose([Event(svc.semantics.fingerprint("以后统一用 bun"),
                                  "以后统一用 bun", "以后统一用 bun", (0,),
                                  origin="agent")], 0)
        target = next(iter(svc.engine.mems.values()))
        row = _selector_row(svc, 0, [cand])
        row["result"] = {"decisions": [{"candidate_index": 0, "action": "EXIST",
                                        "target_id": target.id}]}
        plan = effects.prepare_effect(svc, row)
        assert plan["targets"] and plan["targets"][0]["target_id"] == target.id
        # prepare 与事务之间目标被并发推进（last_seen 漂移）→ 整批拒绝重判
        target.last_seen += 5
        conn = None
        with pytest.raises(ValueError):
            effects.apply_selector(svc, row, row["result"], conn, plan=plan)
    finally:
        svc.tasks.close()
        svc.log.close()
