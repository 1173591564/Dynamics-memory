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
    for t in range(T):
        events, queries = world.step(t); eng.observe(events, t)
        for q in queries:
            b = world.beliefs[q.target]
            ret = eng.retrieve(emb.embed([q.text], keys=[world.embedding_key(q.target, b.value)])[0], q, t)
            def ok(m):
                if world.relevant(m.belief_id, m.value, q, t): return True
                return bool(m.agg_members) and any(world.relevant(eng.mems[i].belief_id, eng.mems[i].value, q, t) for i in m.agg_members if i in eng.mems)
            ph = world.phase(t)
            for key in (ph, "all"):
                acc[key][0] += 1; acc[key][1] += ret.n_useful > 0; acc[key][2] += any(ok(m) for m in ret.selected)
        eng.step(t); worker.process(t)
print(f"{'preset':20s} {'all 原':>7s} {'all 修':>7s} {'drift':>6s} {'noise':>6s} {'conf 原':>7s} {'conf 修':>7s}")
for name in PRESETS:
    acc = defaultdict(lambda: [0,0,0])
    for s in range(10): run(name, s, acc)
    f = lambda k,i: acc[k][i]/acc[k][0]
    print(f"{name:20s} {f('all',1):7.3f} {f('all',2):7.3f} {f('drift',2):6.3f} {f('noise',2):6.3f} {f('conflict',1):7.3f} {f('conflict',2):7.3f}")
