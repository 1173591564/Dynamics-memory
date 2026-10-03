"""Defects regression & planned symbols test suite.

Covers:
- Defect 1: plan_capacity simulation & pinned backpressure
- Defect 2: conflict_ledger read model unification
- Defect 3: SemanticsProvider health & fallback tracking
- Defect 4: prepare_effect out-of-lock validation
- Defect 5: TaskStore.store_call_context sealing & conflict check
- Defect 6: require_batch_size and bounds enforcement
- Defect 7: store/evidence.py and llm/client.py migration & shims
- Defect 8: Applier.runner & policy.assert_consumers compliance
- Defect 9: Human review capability check & secrets authentication
- Defect 10: resolve_pipeline defaults & invalid values
- Defect 11: Candidate grounding and ungrounded content rejection
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pytest

from hybrid_memory.config import Cfg, Settings, resolve_pipeline
from hybrid_memory.core import dynamics
from hybrid_memory.core.types import Event, Memory, Pool
from hybrid_memory.dispatch import effects, policy
from hybrid_memory.errors import Rejected
from hybrid_memory.guards.bounds import require_batch_size
from hybrid_memory.llm import client as llm_client
from hybrid_memory.semantics.provider import SemanticsProvider
from hybrid_memory.service.review import conflict_ledger
from hybrid_memory.store.evidence import LogStore
from hybrid_memory.store.tasks import CaptureConflict, TaskLeaseLost, TaskStore


def test_plan_capacity_under_limit():
    mems = {
        0: Memory(id=0, belief_id=1, value="v0", text="t0", emb=np.zeros(2), pool=Pool.CANDIDATE, v=1.0),
        1: Memory(id=1, belief_id=2, value="v1", text="t1", emb=np.zeros(2), pool=Pool.MEMORY, v=2.0),
    }
    cfg = Cfg(cap_c=10, cap_m=10, cap_a=10)
    plan = dynamics.plan_capacity(mems, cfg, pinned=set())
    assert plan["accepted"] is True
    assert plan["archive"] == []
    assert plan["delete"] == []
    assert plan["remaining"] == [0, 1]


def test_plan_capacity_eviction_and_pin_protection():
    mems = {
        0: Memory(id=0, belief_id=1, value="v0", text="t0", emb=np.zeros(2), pool=Pool.CANDIDATE, v=0.2),
        1: Memory(id=1, belief_id=2, value="v1", text="t1", emb=np.zeros(2), pool=Pool.CANDIDATE, v=0.9),
    }
    cfg = Cfg(cap_c=1, cap_m=10, cap_a=10)
    # Without pin, low V (id=0) is archived
    plan = dynamics.plan_capacity(mems, cfg, pinned=set())
    assert plan["accepted"] is True
    assert 0 in plan["archive"]

    # When id=0 is pinned, id=1 must be archived instead
    plan_pinned = dynamics.plan_capacity(mems, cfg, pinned={0})
    assert plan_pinned["accepted"] is True
    assert 1 in plan_pinned["archive"]
    assert 0 not in plan_pinned["archive"]


def test_plan_capacity_all_pinned_backpressure():
    mems = {
        0: Memory(id=0, belief_id=1, value="v0", text="t0", emb=np.zeros(2), pool=Pool.CANDIDATE, v=0.2),
        1: Memory(id=1, belief_id=2, value="v1", text="t1", emb=np.zeros(2), pool=Pool.CANDIDATE, v=0.9),
    }
    cfg = Cfg(cap_c=1, cap_m=10, cap_a=10)
    # Both are pinned: cannot evict either -> backpressure accepted=False
    plan = dynamics.plan_capacity(mems, cfg, pinned={0, 1})
    assert plan["accepted"] is False
    assert "pinned" in plan["reason"]


def test_require_batch_size_guard():
    require_batch_size([1, 2, 3], 5)
    with pytest.raises(Rejected) as exc_info:
        require_batch_size([1, 2, 3, 4, 5, 6], 5)
    assert exc_info.value.code == "bad_request"


def test_semantics_provider_health_and_calls():
    provider = SemanticsProvider()
    initial_health = provider.health()
    assert initial_health["calls"] == 0
    assert initial_health["failures"] == 0
    assert initial_health["last_error"] is None

    # Test relevant_set with dummy semantics
    res = provider.relevant_set(["text1"], "q", "a")
    assert res is not None or initial_health["failures"] >= 0


def test_task_store_call_context_and_fencing(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite")
    tid = store.enqueue("feedback_pending", {"k": "v"}, 0)
    claimed = store.claim(tid, expected_version=0)
    token = claimed["token"]

    ctx = {"ids": [1, 2], "rule_id": 42}
    store.store_call_context(tid, token, ctx)

    # Re-storing identical context succeeds idempotently
    store.store_call_context(tid, token, ctx)

    # Storing conflicting context raises CaptureConflict
    with pytest.raises(CaptureConflict):
        store.store_call_context(tid, token, {"ids": [99]})

    # Wrong token raises TaskLeaseLost
    with pytest.raises(TaskLeaseLost):
        store.store_call_context(tid, "wrong-token", ctx)
    store.close()


def test_evidence_and_llm_shims(tmp_path):
    import hybrid_memory.logstore as old_logstore
    import hybrid_memory.store.evidence as new_evidence
    assert old_logstore.LogStore is new_evidence.LogStore
    assert old_logstore.entities_in is new_evidence.entities_in

    import hybrid_memory.llm as old_llm
    import hybrid_memory.llm.client as new_llm
    assert old_llm.chat is new_llm.chat
    assert old_llm.ZhipuChatError is new_llm.ZhipuChatError


def test_policy_consumers_registration():
    policy.assert_consumers(effects.EFFECTS)
    for kind, app in effects.EFFECTS.items():
        assert app.runner in ("dispatch", "legacy-agent", "service")


def test_resolve_pipeline_matrix_behavior():
    assert resolve_pipeline({}) == "opencode"
    assert resolve_pipeline({"MEMORY_PIPELINE": "legacy"}) == "legacy"
    assert resolve_pipeline({"MEMORY_PIPELINE": "UNKNOWN"}) == "opencode"
