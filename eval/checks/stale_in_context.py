import sys; sys.path.insert(0,'.')
from experiments.run import PRESETS, T
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen
from hybrid_memory.worker import SignalWorker
from collections import defaultdict
def run(name, seed, acc):
    cfg = PRESETS[name]; emb = SyntheticEmbedder(seed=seed); world = StreamGen(emb, seed=seed)
    eng = MemoryEngine(cfg, emb, world); worker = SignalWorker(eng, world)
    drifted = set()
    for t in range(T):
        events, queries = world.step(t); eng.observe(events, t)
        if t == world.t_drift:
            drifted = {b.id for b in world.beliefs.values() if b.value.endswith("'")}
        for q in queries:
            if q.target not in drifted or t < world.t_drift: continue
            b = world.beliefs[q.target]
            ret = eng.retrieve(emb.embed([q.text], keys=[world.embedding_key(q.target, b.value)])[0], q, t)
            sel = ret.selected
            cur = any(m.belief_id == q.target and m.value == b.value for m in sel)
            stale = any(m.belief_id == q.target and m.value != b.value and not m.agg_members for m in sel)
            a = acc
            a["n"] += 1; a["cur"] += cur; a["stale"] += stale; a["stale_only"] += stale and not cur
            a["cur_clean"] += cur and not stale
            a["ctx"] += len(sel)
        eng.step(t); worker.process(t)
print(f"{'preset':16s} {'查询':>5s} {'含现值':>6s} {'含旧值':>6s} {'只有旧值':>7s} {'现值且无旧值':>9s} {'平均注入条数':>8s}")
for name in ["ours","flat","decay_only","abl_no_tension","abl_no_dedup"]:
    acc = defaultdict(int)
    for s in range(10): run(name, s, acc)
    n = acc["n"]
    print(f"{name:16s} {n:5d} {acc['cur']/n:6.3f} {acc['stale']/n:6.3f} {acc['stale_only']/n:7.3f} {acc['cur_clean']/n:9.3f} {acc['ctx']/n:8.2f}")
