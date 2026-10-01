"""运行器：平台持有时钟，逐轮回放，在探针时刻做被动查询。

探针 t 的语义：系统已 ingest turns[0:t]，在 ingest turns[t] 之前被问。
平台对返回的上下文再按同一 token 规则截断一次（超预算记违规，不信任系统自报）。
不支持 passive 的系统：每个探针重放一次前缀（慢，但结果干净）。
"""
from __future__ import annotations

import time

from .ledger import Stream
from .protocol import MemorySystem
from .score import score_context
from .text import truncate_lines


def _record(system: MemorySystem, stream: Stream, probe, budget: int,
            raw: str, dt: float) -> dict:
    ctx, used, cut = truncate_lines(raw or "", budget)
    rec = {"system": system.name, "budget": budget, "stream": stream.id,
           "dimension": stream.dimension, "probe": probe.id, "knob": probe.knob,
           "t": probe.t, "context": ctx, "tokens": used, "over_budget": cut,
           "latency_s": round(dt, 4)}
    rec.update(score_context(ctx, probe.gold, probe.harmful))
    return rec


def _serve(system, stream, probe, budget):
    t0 = time.perf_counter()
    raw = system.serve(probe.query, probe.t, budget, passive=True,
                       probe=probe if system.caps.privileged else None)
    return _record(system, stream, probe, budget, raw, time.perf_counter() - t0)


def run_stream(system: MemorySystem, stream: Stream, budgets: list[int]) -> list[dict]:
    out = []
    probes = sorted(stream.probes, key=lambda p: p.t)
    if system.caps.passive:
        system.reset(stream.id)
        i = 0
        for t, turn in enumerate(stream.turns + [None]):
            while i < len(probes) and probes[i].t == t:
                out += [_serve(system, stream, probes[i], b) for b in budgets]
                i += 1
            if turn is not None:
                system.ingest(turn.user, turn.assistant, turn.t)
    else:
        for p in probes:
            system.reset(stream.id)
            for turn in stream.turns[:p.t]:
                system.ingest(turn.user, turn.assistant, turn.t)
            out += [_serve(system, stream, p, b) for b in budgets]
    return out


def run(system: MemorySystem, streams: list[Stream], budgets: list[int],
        progress: bool = False) -> list[dict]:
    out = []
    for k, s in enumerate(streams):
        t0 = time.perf_counter()
        out += run_stream(system, s, budgets)
        if progress:
            print(f"  [{system.name}] {k + 1}/{len(streams)} {s.id} "
                  f"({time.perf_counter() - t0:.1f}s)", flush=True)
    return out
