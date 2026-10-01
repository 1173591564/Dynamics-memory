"""退役后的迟到信用，以及延迟 shadow 在 checkpoint 提交后进程死亡。"""
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from hybrid_memory.config import Cfg
from hybrid_memory.core.types import Pool
from hybrid_memory.semantics import RealChatSemantics
from hybrid_memory.server import MemoryService
from test_server import _FixedGenerator, _TableEmbedder, _service


def _close(svc):
    svc.stop_unit_recovery()
    svc.tasks.close()
    svc.log.close()


def _suppressed(tmp_path):
    emb = _TableEmbedder({
        "问": np.array([1.0, 0.0]),
        "在任": np.array([1.0, 0.0]),
        "挑战": np.array([1.0, 0.0]),
        "后继": np.array([0.0, 1.0]),
    })
    cfg = Cfg(theta=0, k=5, suppression_on=True, tau_sim=0.5, defer_credit=True,
              shadow_credit=True, tension_delay=100)
    gen = _FixedGenerator(["在任"])
    svc = MemoryService(cfg, emb, RealChatSemantics(None), gen, state_dir=tmp_path)
    svc.observe("问", "在任")
    gen.texts = ["挑战"]
    svc.observe("问", "挑战")
    svc.recall("问")
    assert len(svc.engine._shadow_pending) == 1
    return svc


def test_shadow_pending_survives_restart_and_settles_once(tmp_path):
    script = r'''
import os, sys
sys.path.insert(0, "tests")
from test_late_credit import _suppressed
svc = _suppressed(sys.argv[1])
assert svc.engine.mems[1].d_shadow == 0
os._exit(17)
'''
    out = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, timeout=30, check=False)
    assert out.returncode == 17, out.stderr.decode()
    svc = MemoryService(Cfg(), _TableEmbedder({}), RealChatSemantics(None),
                        _FixedGenerator([]), state_dir=tmp_path)
    try:
        assert len(svc.engine._shadow_pending) == 1
        key, mid, _, rel = svc.engine._shadow_pending[0]
        assert rel is True
        assert svc.resolve(key[0], key[1], "pending")["resolved"] == 0
        assert svc.engine.mems[mid].d_shadow == 1.0
        assert svc.engine._shadow_pending == []
    finally:
        _close(svc)
    again = MemoryService(Cfg(), _TableEmbedder({}), RealChatSemantics(None),
                          _FixedGenerator([]), state_dir=tmp_path)
    try:
        credited = next(m for m in again.engine.mems.values() if m.d_shadow)
        assert credited.d_shadow == 1.0
        again.engine.submit_verdicts([(0, 1, "pending")], again._t)
        assert credited.d_shadow == 1.0
    finally:
        _close(again)


def test_late_shadow_credits_successor_not_retired_member(tmp_path):
    svc = _suppressed(tmp_path)
    try:
        mid = svc.engine._shadow_pending[0][1]
        retired = svc.engine.mems[mid]
        gen = svc.generator
        gen.texts = ["后继"]
        svc.observe("问", "后继")
        successor = next(m for m in svc.engine.mems.values() if m.text == "后继")
        retired.superseded_by = successor.id
        retired.pool = Pool.ARCHIVE
        pair = svc.engine._shadow_pending[0][0]
        svc.resolve(pair[0], pair[1], "pending")
        assert retired.pool is Pool.ARCHIVE and retired.superseded_by == successor.id
        assert retired.d_shadow == 0
        assert successor.d_shadow == 1.0
    finally:
        _close(svc)


def test_feedback_after_registry_retirement_credits_once(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        rid = svc.recall("部署在哪")["retrieval_id"]
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B 服务器")
        shown = svc.engine.mems[0]
        svc._retrievals.pop(rid)
        del svc.process_semantic_tasks
        assert type(svc).process_semantic_tasks(svc)["credited"] == 1
        assert shown.hits == 1
        assert type(svc).process_semantic_tasks(svc)["credited"] == 0
        assert shown.hits == 1
    finally:
        _close(svc)


def test_late_feedback_does_not_revive_superseded_memory(tmp_path):
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        rid = svc.recall("部署在哪")["retrieval_id"]
        svc.process_semantic_tasks = lambda: {}
        svc.feedback(rid, "部署在哪", "B 服务器")
        old = svc.engine.mems[0]
        successor = type(old)(id=7, belief_id=old.belief_id, value="new",
                              text="后继事实", emb=old.emb.copy(), birth=2)
        svc.engine.mems[7] = successor
        old.superseded_by = 7
        old.pool = Pool.ARCHIVE
        del svc.process_semantic_tasks
        assert type(svc).process_semantic_tasks(svc)["credited"] == 1
        assert old.pool is Pool.ARCHIVE and old.hits == 0
        assert successor.hits == 1
    finally:
        _close(svc)


def test_old_checkpoint_without_shadow_pending_loads_empty(tmp_path):
    svc = _service(tmp_path)
    try:
        state = svc._state()
        del state["shadow_pending"]
        svc._load(pickle.dumps(state))
        assert svc.engine._shadow_pending == []
        state["shadow_pending"] = [((0,), 1, 1, True)]
        with pytest.raises(ValueError, match="shadow_pending"):
            svc._load(pickle.dumps(state))
    finally:
        _close(svc)
