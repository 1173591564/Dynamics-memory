"""信号层测试：发射点、队列有界/合并、worker 消费与操作面等价性。

P2 后引擎不做语义判定：conflict 信号由 maintenance 对老化 tension 发射，
feedback_pending 由 engine.feedback 发射，shadow 信用恒延迟结算。
"""
import math

import numpy as np
import pytest


from hybrid_memory.config import Cfg
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.core.signals import SignalQueue
from hybrid_memory.core.types import Event, Memory, Pool, Query
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen
from hybrid_memory.worker import SignalWorker


def make(seed=0, cfg=None):
    emb = SyntheticEmbedder(seed=seed)
    world = StreamGen(seed=seed)
    return emb, world, MemoryEngine(cfg or Cfg(), emb, world)


class _Judge:
    """judge 固定 verdict（或 fail=True 被调即炸），其余委托 StreamGen。"""

    def __init__(self, inner, verdict="synonym", fail=False):
        self._inner = inner
        self._verdict = verdict
        self._fail = fail

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def judge(self, *args):
        if self._fail:
            raise AssertionError("defer 模式下不应调用 judge")
        return self._verdict


def _suppression_setup(cfg, verdict=None, fail=False):
    """构造压制场景：rival 先入选，m 与 rival 相似度 0.99 > tau_sim。
    verdict/fail 在检索前注入 judge stub。"""
    emb, world, eng = make(cfg=cfg)
    if verdict is not None or fail:
        eng.semantics = _Judge(world, verdict=verdict or "synonym",
                               fail=fail)
    b = world.beliefs[0]
    rival = Memory(0, b.id, b.value, "rival", np.array([1.0, 0.0]), v=0.6)
    m = Memory(1, b.id, b.value, "suppressed",
               np.array([0.99, math.sqrt(1 - 0.99 ** 2)]), v=0.5)
    eng.mems[0], eng.mems[1] = rival, m
    eng._next_id = 2
    ret = eng.retrieve(np.array([1.0, 0.0]), Query(b.id, "q"), 0)
    return eng, ret, rival, m


def test_queue_bound_and_drop_counter():
    q = SignalQueue(cap=3)
    for i in range(5):
        q.emit("feedback_pending", {"i": i}, t=i)
    assert len(q) == 3
    assert q.n_dropped == 2
    sigs = q.drain()
    assert [s.payload["i"] for s in sigs] == [2, 3, 4]   # 丢最旧
    assert len(q) == 0


def test_conflict_signal_emits_aged_pairs_at_step():
    emb, world, eng = make(cfg=Cfg(tension_delay=0))
    b = world.beliefs[0]
    for i in range(3):
        eng.mems[i] = Memory(i, b.id, b.value, f"m{i}",
                             np.array([1.0, 0.0]))
    eng._next_id = 3
    eng.add_tension(0, 1, 0)
    eng.add_tension(1, 2, 0)
    # add_tension 不直接发射；maintenance 对老化未决对统一发射
    assert eng.drain_signals() == []
    eng.step(0)
    sigs = [s for s in eng.drain_signals() if s.kind == "conflict_pending"]
    assert len(sigs) == 1
    assert sigs[0].payload == [(0, 1), (1, 2)]
    # 未决对下一步仍重发（worker retry 通道），pair 不重复
    eng.step(1)
    sigs = [s for s in eng.drain_signals() if s.kind == "conflict_pending"]
    assert len(sigs) == 1
    assert sigs[0].payload == [(0, 1), (1, 2)]


def test_conflict_signal_respects_tension_delay():
    emb, world, eng = make(cfg=Cfg(tension_delay=5))
    b = world.beliefs[0]
    for i in range(2):
        eng.mems[i] = Memory(i, b.id, b.value, f"m{i}",
                             np.array([1.0, 0.0]))
    eng._next_id = 2
    eng.add_tension(0, 1, 3)
    eng.step(4)
    assert not [s for s in eng.drain_signals()
                if s.kind == "conflict_pending"]   # 未老化不发
    eng.step(8)
    sigs = [s for s in eng.drain_signals() if s.kind == "conflict_pending"]
    assert sigs[0].payload == [(0, 1)]


def test_thin_recall_deduped_per_step():
    emb, world, eng = make()
    q = Query(-1, "anything")
    qv = emb.embed(["anything"])[0]
    eng.retrieve(qv, q, 0)
    eng.retrieve(qv, q, 0)
    eng.retrieve(qv, q, 1)
    kinds = [s.kind for s in eng.drain_signals()]
    assert kinds.count("thin_recall") == 2   # t=0 合并成一条，t=1 一条


def test_feedback_pending_emitted_by_feedback_call():
    emb, world, eng = make(cfg=Cfg(defer_credit=True))
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(b.entity, b.id, b.value),
                       Query(b.id, "q"), 0)
    # retrieve 不发 feedback_pending（还没有答案可判）
    assert not [s for s in eng.drain_signals()
                if s.kind == "feedback_pending"]
    eng.feedback(ret, "问题", "回答", 0)
    sigs = [s for s in eng.drain_signals() if s.kind == "feedback_pending"]
    assert len(sigs) == 1
    assert sigs[0].payload["retrieval"] is ret
    assert sigs[0].payload["question"] == "问题"
    assert sigs[0].payload["answer"] == "回答"
    # defer 关闭：retrieve 就地结清 → feedback 直接报错
    emb2, world2, eng2 = make(cfg=Cfg(defer_credit=False))
    eng2.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    ret2 = eng2.retrieve(emb2.vec_for(b.entity, b.id, b.value),
                         Query(b.id, "q"), 0)
    with pytest.raises(RuntimeError):
        eng2.feedback(ret2, "q", "a", 0)


def test_submit_relevance_matches_feedback_effects():
    emb, world, eng = make(cfg=Cfg(defer_credit=True, suppression_on=False))
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(b.entity, b.id, b.value),
                       Query(b.id, "q"), 0)
    n = eng.submit_relevance(ret, [True] * len(ret.selected), 0)
    assert n == 1
    assert ret.selected[0].hits == 1 and ret.selected[0].d_hit == 1.0
    assert ret.credited
    with pytest.raises(RuntimeError):
        eng.submit_relevance(ret, [True], 0)


def test_submit_verdicts_synonym_matches_worker_path():
    def _setup(seed):
        emb, world, eng = make(seed=seed, cfg=Cfg(tension_delay=0))
        b = world.beliefs[0]
        a = Memory(0, b.id, b.value, "a", np.array([1.0, 0.0]), v=0.6)
        bb = Memory(1, b.id, b.value, "b", np.array([0.0, 1.0]), v=0.4)
        eng.mems[0], eng.mems[1] = a, bb
        eng._next_id = 2
        eng.add_tension(0, 1, 0)
        return world, eng, a, bb

    world_w, eng_w, a1, b1 = _setup(0)
    eng_w.step(0)   # 老化发 conflict_pending
    stats = SignalWorker(eng_w, _Judge(world_w, verdict="synonym")).process(0)
    assert stats["resolved"] == 1
    world_op, eng_op, a2, b2 = _setup(0)
    n = eng_op.submit_verdicts([(0, 1, "synonym")], 0)

    assert n == 1
    for eng, a, b in ((eng_w, a1, b1), (eng_op, a2, b2)):
        assert b.superseded_by == a.id and b.pool is Pool.ARCHIVE
        assert a.evid == 1 + 1
        assert eng.n_merge == 1 and eng.n_resolve == 1
        assert not eng.tensions


def test_submit_verdicts_pending_keeps_backlog():
    emb, world, eng = make(cfg=Cfg(tension_delay=0))
    b = world.beliefs[0]
    eng.mems[0] = Memory(0, b.id, b.value, "a", np.array([1.0, 0.0]))
    eng.mems[1] = Memory(1, b.id, b.value, "b", np.array([0.0, 1.0]))
    eng._next_id = 2
    eng.add_tension(0, 1, 0)
    n = eng.submit_verdicts([(0, 1, "pending")], 0)
    assert n == 0
    assert (0, 1) in eng.tensions and eng.n_resolve == 0


def test_submit_verdicts_stale_pair_dropped():
    emb, world, eng = make()
    eng.mems[0] = Memory(0, world.beliefs[0].id, world.beliefs[0].value,
                         "a", np.array([1.0, 0.0]))
    eng.add_tension(0, 1, 0)
    n = eng.submit_verdicts([(0, 1, "synonym")], 0)   # 1 不存在
    assert n == 0 and not eng.tensions


def test_maintenance_due_emitted_without_callback():
    cfg = Cfg(consolidation_on=True, consolidation_min_items=2,
              consolidation_salience_budget=1.0)
    emb, world, eng = make(cfg=cfg)
    b = world.beliefs[0]
    for i in range(2):
        eng.mems[i] = Memory(i, b.id, b.value, f"m{i}",
                             np.array([1.0, 0.0]), salience=0.8, scene="s1")
    eng._next_id = 2
    eng._consolidation_pending = {0, 1}
    eng.step(0)   # StreamGen 无 consolidate 回调，信号仍应发射
    sigs = eng.drain_signals()
    assert [s.kind for s in sigs] == ["maintenance_due"]
    assert sigs[0].payload["scene"] == "s1"
    assert sorted(sigs[0].payload["ids"]) == [0, 1]


def test_add_reflection_admits_memory():
    emb, world, eng = make()
    b = world.beliefs[0]
    ev = Event(b.id, b.value, "scene 汇总：进行到 X")
    m = eng.add_reflection(ev, [], 0)
    assert m.kind == "reflection" and eng.mems[m.id] is m
    assert eng.n_consolidate == 1
    assert m.derived_from == ()


def test_shadow_records_pending_without_judge():
    # 压制路径恒延迟记账：引擎全程不调 judge（fail=True 被调即炸）
    eng, ret, rival, m = _suppression_setup(Cfg(), fail=True)
    assert m.d_shadow == 0.0                          # 未结算
    assert len(eng._shadow_pending) == 1
    key, mid, t_ret, rel = eng._shadow_pending[0]
    assert key == (0, 1) and mid == 1 and t_ret == 0 and rel
    assert eng.tensions                              # backlog 照常


def test_shadow_settles_on_update_verdict():
    eng, ret, rival, m = _suppression_setup(Cfg())
    n = eng.submit_verdicts([(1, 0, "update")], 5)
    assert n == 1 and eng._shadow_pending == []
    assert m.d_shadow == 1.0 and m.last_hit == 0      # 结算用检索时刻
    # 两条同 birth：update 以 id 定新旧（后入库者新）→ 保留 m(1)，归档 rival(0)
    assert rival.superseded_by == 1 and rival.pool is Pool.ARCHIVE
    assert m.superseded_by is None and m.pool is not Pool.ARCHIVE


def test_shadow_synonym_no_credit():
    eng, ret, rival, m = _suppression_setup(Cfg())
    eng.submit_verdicts([(1, 0, "synonym")], 5)
    assert m.d_shadow == 0.0 and eng._shadow_pending == []


def test_shadow_pending_verdict_credits_keeps_backlog():
    eng, ret, rival, m = _suppression_setup(Cfg())
    n = eng.submit_verdicts([(1, 0, "pending")], 5)
    assert n == 0
    assert m.d_shadow == 1.0                          # 非 synonym → 发信用
    assert eng._shadow_pending == []
    assert (0, 1) in eng.tensions                     # backlog 保留


def test_shadow_settles_via_worker():
    eng, ret, rival, m = _suppression_setup(Cfg(tension_delay=0))
    eng.step(0)   # 老化发 conflict_pending
    SignalWorker(eng, _Judge(eng.semantics, verdict="update")).process(0)
    assert m.d_shadow == 1.0 and eng._shadow_pending == []
    assert eng.n_resolve == 1 and not eng.tensions


def test_shadow_pending_bounded():
    eng, ret, rival, m = _suppression_setup(
        Cfg(shadow_pending_cap=1))
    eng._record_shadow_pending(m, rival, 5, True)
    assert len(eng._shadow_pending) == 1 and eng.n_shadow_dropped == 1


def test_worker_absent_system_operates_and_queue_bounded():
    emb, world, eng = make(cfg=Cfg(defer_credit=True, signal_queue_cap=8))
    for t in range(30):
        b = world.beliefs[t % len(world.beliefs)]
        eng.observe([Event(b.id, b.value,
                           b.phrasings[b.value][0])], t)
        qv = emb.vec_for(b.entity, b.id, b.value)
        eng.retrieve(qv, Query(b.id, "q"), t)
        eng.step(t)
    assert len(eng.signals) <= 8
    assert eng.signals.n_dropped > 0            # 无人消费 → 有界丢弃计数
    assert eng.pool_sizes()["M"] >= 0           # 引擎照常运转


class _RecogStub:
    """relevant_set 返回指定值（None=失败 / 长度不齐=违约），其余委托。"""

    def __init__(self, inner, ret):
        self._inner = inner
        self._ret = ret

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def relevant_set(self, texts, question, answer):
        return self._ret


def _feedback_setup(sem_wrap=None):
    """一次 defer 检索 + feedback 信号已入队的场景。"""
    emb, world, eng = make(cfg=Cfg(defer_credit=True, useful_hit=True))
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    ret = eng.retrieve(emb.vec_for(b.entity, b.id, b.value),
                       Query(b.id, "q"), 0)
    eng.feedback(ret, "q", "a", 0)
    w = SignalWorker(eng, sem_wrap(world) if sem_wrap else world)
    return eng, ret, w


def test_worker_recog_fail_counts_and_degrades():
    # relevant_set 返 None = 识别失败：计数外显 + 退化 selected-hit 全记
    eng, ret, w = _feedback_setup(lambda world: _RecogStub(world, None))
    stats = w.process(0)
    assert stats["recog_fail"] == 1 and w.n_recog_fail == 1
    assert stats["credited"] == 1 and ret.credited
    assert ret.n_useful == len(ret.selected)      # 退化全记


def test_worker_recog_bad_length_is_failure_not_crash():
    # 长度不齐 = 违反协议：同样计数退化，不再抛 RuntimeError 丢整批信号
    # （selected 可能只有 1 条，用空列表保证长度必不齐）
    eng, ret, w = _feedback_setup(lambda world: _RecogStub(world, []))
    stats = w.process(0)
    assert stats["recog_fail"] == 1
    assert ret.credited and ret.n_useful == len(ret.selected)


def test_worker_error_containment_requeues_failed_signal():
    # 毒信号（judge 炸）不能拖垮同批其他信号：feedback 照常结算，
    # 失败信号回队重试而不是随 drain 蒸发
    emb, world, eng = make(cfg=Cfg(defer_credit=True, tension_delay=0))
    b = world.beliefs[0]
    eng.observe([Event(b.id, b.value, b.phrasings[b.value][0])], 0)
    eng.mems[1] = Memory(1, b.id, b.value, "m1", emb.embed(["m1"])[0])
    eng._next_id = 2
    eng.add_tension(0, 1, 0)
    ret = eng.retrieve(emb.vec_for(b.entity, b.id, b.value),
                       Query(b.id, "q"), 0)
    eng.feedback(ret, "q", "a", 0)
    eng.step(0)   # conflict_pending 与 feedback_pending 同批在队
    w = SignalWorker(eng, _Judge(world, fail=True))
    stats = w.process(0)
    assert stats["errors"] == 1                   # 毒信号被隔离计数
    assert stats["credited"] >= 1 and ret.credited  # 同批好信号照常落地
    left = [s.kind for s in eng.drain_signals()]
    assert left == ["conflict_pending"]           # 失败信号回队未丢


# ================================================== 衔尾蛇信号：recall_miss / extract_due / 操作面 propose
class _HashEmbedder:
    """字符哈希词袋：真实文本可嵌入、确定、无网络。"""
    def embed(self, texts, keys=None):
        out = []
        for t in texts:
            v = np.zeros(32)
            for ch in t:
                v[hash(ch) % 32] += 1
            out.append(v / (np.linalg.norm(v) or 1.0))
        return np.array(out, dtype=np.float32)


def _plain_engine():
    from hybrid_memory.semantics import RealChatSemantics
    return MemoryEngine(Cfg(), _HashEmbedder(), RealChatSemantics(None))


def test_take_only_removes_requested_kinds_in_order():
    q = SignalQueue()
    q.emit("conflict_pending", {}, 0)
    q.emit("recall_miss", {"q": "a"}, 1, key="miss:a")
    q.emit("extract_due", {"unit_id": 3}, 2, key="unit:3")
    q.emit("feedback_pending", {}, 3)
    got = q.take(("recall_miss", "extract_due"))
    assert [s.kind for s in got] == ["recall_miss", "extract_due"]
    assert [s.kind for s in q.drain()] == ["conflict_pending", "feedback_pending"]
    assert q.peek_kinds() == {}


def test_take_releases_keys_so_signal_can_be_re_emitted():
    q = SignalQueue()
    q.emit("recall_miss", {"q": "a"}, 1, key="miss:a")
    q.take(("recall_miss",))
    q.emit("recall_miss", {"q": "a"}, 2, key="miss:a")
    assert q.peek_kinds() == {"recall_miss": 1}


def test_report_miss_dedupes_by_question_and_merges_payload():
    eng = _plain_engine()
    eng.report_miss("端口 是多少", 1, hint="不对", source="correction")
    eng.report_miss("端口是多少", 2, hint="用了日志工具", source="agent_tool",
                    entities=("handler.ts",))
    eng.report_miss("", 3, source="external")          # 空问题忽略
    sigs = eng.signals.take(("recall_miss",))
    assert len(sigs) == 1
    p = sigs[0].payload
    assert p["hints"] == ["不对", "用了日志工具"]
    assert p["sources"] == ["correction", "agent_tool"]
    assert p["entities"] == ["handler.ts"] and p["first_t"] == 1
    assert sigs[0].t == 2                              # 刷新到最新


def test_report_unit_dedupes_by_unit_and_unions_reasons():
    eng = _plain_engine()
    eng.report_unit(7, 1, reasons=("decision",), entities=("a.ts",))
    eng.report_unit(7, 2, reasons=("quant", "decision"), entities=("b.ts",))
    eng.report_unit(8, 2, reasons=())                  # 无原因不发
    sigs = eng.signals.take(("extract_due",))
    assert len(sigs) == 1
    assert sigs[0].payload["reasons"] == ["decision", "quant"]
    assert sigs[0].payload["entities"] == ["a.ts", "b.ts"]


def test_engine_propose_requires_non_passive_origin_and_keeps_it():
    eng = _plain_engine()
    ev = Event("x", "x", "x", (0,))                    # 默认 origin=passive
    with pytest.raises(ValueError):
        eng.propose([ev], 0)
    ev2 = Event("hermes 现为 form agent", "hermes 现为 form agent",
                "hermes 现为 form agent", (0,), origin="repair", entity="hermes")
    ids = eng.propose([ev2], 0)
    assert ids and eng.mems[ids[0]].origin == "repair"
    assert eng.mems[ids[0]].entity == "hermes"


def test_semantic_worker_leaves_agent_signals_in_queue():
    from hybrid_memory.semantics import RealChatSemantics
    eng = _plain_engine()
    eng.report_miss("q", 0, source="external")
    eng.report_unit(1, 0, reasons=("decision",))
    SignalWorker(eng, RealChatSemantics(None)).process(0)
    assert eng.signals.peek_kinds() == {"recall_miss": 1, "extract_due": 1}


def test_worker_two_phase_lock_does_not_hold_lock_during_semantics():
    """worker 持服务锁时只做引擎读写；调 semantics 时锁必须是放开的。"""
    import threading
    emb, world, eng = make()
    lock = threading.RLock()
    seen = []

    class _Probe:
        def __getattr__(self, name):
            return getattr(world, name)

        def judge(self, *args):
            # 若 worker 在锁内调我们，这里 acquire 会因 RLock 可重入而成功，
            # 所以改用另一线程探测：另一线程能拿到锁 ⇔ worker 没持锁
            got = []

            def probe():
                ok = lock.acquire(timeout=0.5)
                got.append(ok)
                if ok:
                    lock.release()
            th = threading.Thread(target=probe)
            th.start()
            th.join()
            seen.append(bool(got and got[0]))
            return world.judge(*args)

    eng.semantics = _Probe()
    worker = SignalWorker(eng, eng.semantics, lock=lock)
    eng.signals.emit("conflict_pending", [(0, 1)], 0, key="conflict")
    b = world.beliefs[0]
    eng.mems[0] = Memory(0, b.id, b.value, "a", np.array([1.0, 0.0]), v=0.6)
    eng.mems[1] = Memory(1, b.id, b.value, "b", np.array([0.99, 0.14]), v=0.5)
    eng._next_id = 2
    eng.add_tension(0, 1, 0)
    worker.process(1)
    assert seen and all(seen)
