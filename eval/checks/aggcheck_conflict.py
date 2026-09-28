"""反事实评分：冲突相位里，聚合记忆(成员含目标 belief)是否被 ground truth 当成 miss。"""
import sys; sys.path.insert(0,'.')
from experiments.run import PRESETS, T
from hybrid_memory.core.engine import MemoryEngine
from hybrid_memory.embed.synthetic import SyntheticEmbedder
from hybrid_memory.sim.world import StreamGen
from hybrid_memory.worker import SignalWorker

def run(name, seed):
    cfg = PRESETS[name]; emb = SyntheticEmbedder(seed=seed); world = StreamGen(emb, seed=seed)
    eng = MemoryEngine(cfg, emb, world); worker = SignalWorker(eng, world)
    n = hit_orig = hit_agg = agg_seen = 0
    for t in range(T):
        events, queries = world.step(t); eng.observe(events, t)
        for q in queries:
            b = world.beliefs[q.target]
            ret = eng.retrieve(emb.embed([q.text], keys=[world.embedding_key(q.target, b.value)])[0], q, t)
            if world.phase(t) != "conflict": continue
            n += 1
            orig = ret.n_useful > 0
            def ok(m):
                if world.relevant(m.belief_id, m.value, q, t): return True
                if m.agg_members:   # 聚合体：任一成员是目标且有效，即视为给出了正确(条件化)答案
                    return any(world.relevant(eng.mems[i].belief_id, eng.mems[i].value, q, t) for i in m.agg_members if i in eng.mems)
                return False
            agg = any(ok(m) for m in ret.selected)
            agg_seen += any(m.agg_members for m in ret.selected)
            hit_orig += orig; hit_agg += agg
        eng.step(t); worker.process(t)
    return n, hit_orig, hit_agg, agg_seen

for name in ["ours", "abl_no_tension", "decay_only"]:
    tot = [0,0,0,0]
    for s in range(10):
        r = run(name, s); tot = [a+b for a,b in zip(tot, r)]
    n,o,a,g = tot
    print(f"{name:15s} conflict queries={n}  recall(原口径)={o/n:.3f}  recall(聚合计入)={a/n:.3f}  含聚合体的检索={g/n:.3f}")
