"""记忆引擎 sidecar：把 MemoryEngine + L0 logstore HTTP 服务化，供 opencode
插件调用——既服务主 agent（消费记忆），也服务调查员 agent（生产记忆）。

端点（JSON，除 /health 外一律要求 `Authorization: Bearer <token>`；
token 持久化在 state_dir/.memory-token，插件侧同路径读取或经环境变量注入）：

  读记忆
  GET  /health              → 状态（池规模/时间步/信号/agent），免鉴权
  GET  /recall?q=..&k=..    → {retrieval_id, context, selected}
  POST /search              → {query, k} 同 /recall（CJK 长查询走 body）
  GET  /conflicts           → 未决 tension 列表
  GET  /signals             → 信号队列与 agent worker 遥测

  写记忆（主回路）
  POST /observe             → {user_text, assistant_text}：先落 L0 并建索引，
                              触发扫描 → extract_due / recall_miss；再 candgen
                              蒸馏（失败不丢单元）；蒸馏产物进池
  POST /feedback            → {retrieval_id, question, answer} 延迟记账
  POST /resolve             → {left, right, verdict, entity_key?} 裁决回报
  POST /miss                → {query, hint?, source?} 上报一次记忆缺失
                              （主 agent 用了 log_* 工具 = 记忆没接住）

  操作日志（agent 工具面；只给片段/聚合，原文只经 /log/window 计量回展）
  POST /log/search          → {query, before?, scene?, k?}
  POST /log/timeline        → {entity, before?, limit?}
  POST /log/stats           → {group_by, before?, limit?}
  POST /log/window          → {unit_ids, max_chars?}

  操作面（agent 产物回流；服务端校验溯源/因果/脱敏/自指）
  POST /propose             → {proposals:[{text, kind, salience,
                               source_unit_ids, entity_key?, supersedes?}],
                               origin?} → {accepted, new_ids, rejected}
  POST /diagnose            → {miss_type, note?}
  POST /save                → 落盘状态快照

请求头 X-Signal-Id（调查员插件自动附带）：按信号计量工具调用次数与回展
字符预算，并对该信号统一施加因果上界 before——不靠 LLM 自觉。

状态：内存引擎 + <project>/.opencode/memory/state.pkl 快照（启动加载、
/save 与退出时保存）+ log.sqlite（L0，追加写）。pickle 反序列化走白名单
Unpickler。依赖注入（cfg/emb/semantics/generator/logstore）便于测试。
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import secrets
import signal as _signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import triggers
from .candgen.base import CandidateGenerator
from .candgen.chat import ChatGenerator
from .candgen.prompt import redact_secrets
from .config import Cfg
from .core.engine import MemoryEngine
from .core.types import Event, Query, Retrieval
from .datasets.real_chat import InteractionUnit, InteractionWindow
from .embed.base import Embedder
from .llm import chat
from .logstore import LogStore, entities_in
from .semantics import normalize
from .semantics.llm import LLMSemantics
from .worker import SignalWorker

_RETRIEVAL_KEEP = 512   # retrieval 注册表上限（feedback 用，防无界增长）
# [^>]* 单趟即可：匹配内部不含 '>'，嵌套 payload 被整体吃掉，
# 任何残留的 "relevant-memories" 片段都凑不成完整 tag
_MEM_TAG_RE = re.compile(r"<\s*/?\s*relevant-memories[^>]*>", re.IGNORECASE)
# 自指：记忆系统自身的操作过程不是项目事实（candgen prompt 已禁，
# 这里是操作面的第二道闸）
_SELF_REF_RE = re.compile(
    r"(?:memory_(?:search|propose|resolve|diagnose|conflicts)|"
    r"log_(?:search|timeline|stats|window)|relevant-memories|"
    r"(?:我|已|刚|调查员|系统)(?:已经)?(?:检索|查询|查阅|回展|裁决|合并|归档|提议|"
    r"调查)了?(?:一下|一遍|相关)?(?:记忆|日志|冲突)|"
    r"(?:记忆|日志)(?:里|中)(?:没有|未)(?:找到|查到|记录)|"
    r"(?:signal_id|recall_miss|extract_due))", re.IGNORECASE)
_MAX_PROPOSAL_CHARS = 1200
_MAIN_WINDOW_CAP = 1500          # 无信号上下文（主 agent）的单次回展上限
_ORIGINS = {"repair", "extract", "mining", "agent", "user_confirmed"}
_VERDICTS = {"synonym", "update", "contradiction", "collision", "pending"}
_MISS_SOURCES = {"recognizer_none", "correction", "agent_tool", "thin",
                 "external"}


def _safe_mem_text(text: str) -> str:
    """记忆文本进 <relevant-memories> 包裹块前的消毒：中和同名分隔符
    （含嵌套/带属性/自闭合变体），防存储型注入破 tag 逃逸污染
    system prompt。"""
    return _MEM_TAG_RE.sub(" ", text)


_COUNTERS = ("n_promote", "n_demote", "n_evict", "n_archive", "n_revive",
             "n_merge", "n_collision", "n_tension", "n_resolve", "n_agg",
             "n_consolidate", "n_shadow_dropped", "n_chain_broken")

_STATE_KEYS = {"mems", "tensions", "next_id", "consolidation_pending",
               "consolidation_deferred", "counters", "t", "unit_id", "scene"}

# Memory 后加字段：旧 state.pkl 反序列化出来的对象没有这些属性，
# 加载时按默认值补齐（dataclass 的 __dict__ 直接落盘，不会走 __init__）
_MEMORY_FIELD_DEFAULTS = {"origin": "passive", "entity": ""}

# state.pkl 受限反序列化白名单：state 只含内置容器/标量 + Memory/Tension/
# Pool + numpy 数组重建函数，其余 global 一律拒绝（pickle RCE 防线）
_PICKLE_SAFE = {
    ("builtins", n) for n in
    ("dict", "list", "tuple", "set", "frozenset", "bytes", "bytearray",
     "str", "int", "float", "bool", "complex", "slice", "range",
     "NoneType", "object")
} | {
    ("collections", "OrderedDict"), ("collections", "defaultdict"),
    ("collections", "Counter"),
    ("hybrid_memory.core.types", "Memory"),
    ("hybrid_memory.core.types", "Tension"),
    ("hybrid_memory.core.types", "Pool"),
    ("hybrid_memory.core.types", "Retrieval"),
    ("numpy._core.multiarray", "_reconstruct"),
    ("numpy.core.multiarray", "_reconstruct"),   # numpy<2 兼容
    ("numpy", "dtype"), ("numpy", "ndarray"),
}


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if (module, name) in _PICKLE_SAFE:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"state.pkl 含未授权 global: {module}.{name}")


class SignalClosed(Exception):
    """带了 X-Signal-Id 但该调查已结束/不存在（不用 KeyError：它是
    LookupError 子类，会把别处的 bug 误报成 403）。"""


class ProposalRejected(ValueError):
    pass


class MemoryService:
    def __init__(self, cfg: Cfg, emb: Embedder, semantics, generator:
                 CandidateGenerator, state_dir: Path | None = None,
                 logstore: LogStore | None = None):
        self.cfg = cfg
        self.emb = emb
        self.semantics = semantics
        self.generator = generator
        self.engine = MemoryEngine(cfg, emb, semantics)
        self._lock = threading.RLock()
        # 语义 worker 持服务锁：引擎读写锁内、LLM 锁外（不再卡 /search）
        self.worker = SignalWorker(self.engine, semantics, lock=self._lock)
        self.state_path = (Path(state_dir) / "state.pkl"
                           if state_dir else None)
        self.log = logstore or LogStore(
            Path(state_dir) / "log.sqlite" if state_dir else None)
        self.token = self._load_or_create_token()
        self.agent = None                 # AgentWorker，attach_agent 挂上
        self._t = 0
        self._unit_id = 0
        self._scene = ""
        self._retrievals: dict[int, Retrieval] = {}
        self._next_retrieval = 0
        self._last_turn: dict | None = None   # 上一轮 {user, retrieval_id}
        self._budgets: dict[str, dict] = {}   # signal_id → 预算/因果上界
        self.miss_counts: dict[str, int] = {}
        self.n_candgen_fail = 0
        self.n_missed = 0
        self.n_proposals = 0
        self.n_rejected = 0
        if self.state_path and self.state_path.exists():
            try:
                self._load()
            except Exception as exc:  # noqa: BLE001
                # 损坏/恶意 state 不能让 sidecar 启动即死（桥会整体瘫痪）：
                # 隔离坏文件后空启动，损失状态好过丢记忆服务
                corrupt = self.state_path.with_suffix(".corrupt")
                try:
                    os.replace(self.state_path, corrupt)
                except OSError:
                    pass
                print(f"[memory-sidecar] state.pkl 损坏已隔离为 "
                      f"{corrupt.name}（{exc}）——空启动",
                      file=sys.stderr, flush=True)

    # 供 AgentWorker 使用的最小接口
    @property
    def lock(self):
        return self._lock

    def current(self) -> tuple[int, str]:
        return self._t, self._scene

    def attach_agent(self, agent) -> None:
        self.agent = agent

    def _kick(self) -> None:
        if self.agent is not None:
            self.agent.notify()

    def _load_or_create_token(self) -> str:
        """HTTP 鉴权令牌：持久化在 state_dir/.memory-token（插件侧同路径
        读取），无 state_dir 时临时生成。防浏览器 CSRF 写与端口占位复用。"""
        p = (self.state_path.parent / ".memory-token"
             if self.state_path else None)
        if p and p.exists():
            tok = p.read_text(encoding="utf-8").strip()
            if tok:
                return tok
            # 空/全空白 token 文件 = 坏状态：当作不存在，重写一个
        tok = secrets.token_hex(16)
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(tok, encoding="utf-8")
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        return tok

    # ================================================== 主回路
    def observe(self, user_text: str, assistant_text: str) -> dict:
        # 1) 锁内：分配 unit/t，落 L0 并建索引（确定性、毫秒级），触发扫描
        with self._lock:
            uid = self._unit_id
            self._unit_id += 1
            t, scene = self._t, self._scene
            idx = self.log.add_unit(uid, t, user_text=user_text,
                                    assistant_text=assistant_text, scene=scene)
            reasons = triggers.scan_unit(user_text, assistant_text,
                                         idx["new_entities"])
            prev = self._last_turn
            if triggers.is_correction(user_text) and prev:
                # 用户在纠正上一轮 → 上一轮的记忆没接住（或接错）
                ret = self._retrievals.get(prev.get("retrieval_id", -1))
                self.engine.report_miss(
                    prev["user"], t, hint=user_text[:300], source="correction",
                    retrieval=ret,
                    entities=tuple(e for e, _ in entities_in(prev["user"])))
                self.n_missed += 1
            self._last_turn = {"user": user_text, "retrieval_id": None}
        # 2) 锁外：被动 candgen（LLM）。失败不丢单元——L0 已落盘，
        #    以 extract_due(candgen_failed) 交给调查员补抽
        unit = InteractionUnit(id=uid, start_time=t, end_time=t,
                               user_text=user_text,
                               assistant_text=assistant_text,
                               assistant_turns=1)
        window = InteractionWindow(id=uid, start_unit_id=uid, end_unit_id=uid,
                                   start_time=t, end_time=t, units=(unit,))
        try:
            gen = self.generator.generate(window, scene)
            cands, new_scene = list(gen.candidates), gen.scene_name
        except Exception as exc:          # noqa: BLE001
            self.n_candgen_fail += 1
            cands, new_scene = [], ""
            reasons = list(dict.fromkeys(list(reasons) + ["candgen_failed"]))
            print(f"[memory-sidecar] candgen 失败（unit {uid}，已留 L0，"
                  f"交调查员补抽）: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
        # 3) 锁内：产物入池、发信号、推进时间
        with self._lock:
            self._scene = new_scene or self._scene
            if reasons:
                self.engine.report_unit(uid, t, scene=self._scene,
                                        reasons=tuple(reasons),
                                        entities=tuple(idx["entities"][:12]))
            evs = [Event(self.semantics.fingerprint(normalize(c.text)),
                         normalize(c.text), c.text, c.source_unit_ids or (uid,),
                         salience=c.salience, scene=self._scene)
                   for c in cands]
            if evs:
                self.engine.observe(evs, self._t)   # 提交时刻的 t，保单调
            self.engine.step(self._t)
            t_used = self._t
            self._t += 1
            pool = self.engine.pool_sizes()
            scene_out = self._scene
        # 4) 锁外：语义 worker（LLM 锁外、引擎锁内）；唤醒 agent worker
        wstats = self.worker.process(t_used)
        self._kick()
        return {"unit_id": uid, "candidates": len(evs), "scene": scene_out,
                "reasons": list(reasons), "pool": pool, "t": self._t,
                "worker": wstats}

    def _format_context(self, ret: Retrieval) -> str:
        prov_ids = {m.id for m in ret.provisional}
        lines = []
        for m in ret.selected:
            lines.append(
                f"- {'[未确认] ' if m.id in prov_ids else ''}"
                f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
                f"[t={m.birth}] {_safe_mem_text(m.text)}")
        for m, rival in ret.contested:
            lines.append(f"- ⚠️未决冲突：[t={rival.birth}] "
                         f"{_safe_mem_text(rival.text)}"
                         f"（与 t={m.birth} 条目冲突）")
        return "\n".join(lines)

    def recall(self, q: str, k: int | None = None) -> dict:
        qv = self.emb.embed([q])[0]
        with self._lock:
            if k is not None:
                old_k, self.cfg.k = self.cfg.k, k
                try:
                    ret = self.engine.retrieve(qv, Query(-1, q), self._t)
                finally:
                    self.cfg.k = old_k
            else:
                ret = self.engine.retrieve(qv, Query(-1, q), self._t)
            rid = self._next_retrieval
            self._next_retrieval += 1
            self._retrievals[rid] = ret
            while len(self._retrievals) > _RETRIEVAL_KEEP:
                self._retrievals.pop(min(self._retrievals))
            # 不在这里把 retrieval 关联到 _last_turn：/search 发生在回答
            # 之前，此刻 _last_turn 还是上一轮；关联由 /feedback 完成
            return {"retrieval_id": rid, "context": self._format_context(ret),
                    "n": len(ret.selected),
                    "selected": [{"id": m.id, "text": m.text,
                                  "birth": m.birth, "kind": m.kind,
                                  "origin": m.origin,
                                  "src": sorted(m.src)}
                                 for m in ret.selected]}

    def feedback(self, retrieval_id: int, question: str, answer: str) -> dict:
        with self._lock:
            ret = self._retrievals.get(retrieval_id)
            if ret is None:
                return {"error": f"unknown retrieval_id {retrieval_id}"}
            if ret.credited or ret.feedback_sent:
                # 同一次检索重复反馈（插件重试/多会话共用）：幂等拒绝，
                # 不让引擎的 RuntimeError 变成 500
                return {"error": f"retrieval_id {retrieval_id} already "
                                 f"credited", "n_useful": ret.n_useful}
            self.engine.feedback(ret, question, answer, self._t)
            # 记下"这一轮用了哪次检索"，纠正检测时能把已召回内容带给调查员
            if self._last_turn is not None:
                self._last_turn = {"user": question, "retrieval_id": retrieval_id}
            t = self._t
        wstats = self.worker.process(t)   # 排空 feedback_pending 等信号（LLM 锁外）
        with self._lock:
            # recognizer 说一条都没用上 → 记忆没接住这个问题
            if (ret.credited and ret.n_useful == 0 and ret.selected
                    and self.cfg.miss_on_recognizer_none):
                self.engine.report_miss(question, t, source="recognizer_none",
                                        retrieval=ret,
                                        entities=tuple(
                                            e for e, _ in entities_in(question)))
                self.n_missed += 1
                self._kick()
            return {"n_useful": ret.n_useful, "worker": wstats}

    def report_miss(self, query: str, hint: str = "",
                    source: str = "agent_tool") -> dict:
        if source not in _MISS_SOURCES:
            source = "external"
        with self._lock:
            self.engine.report_miss(query, self._t, hint=hint[:300],
                                    source=source,
                                    entities=tuple(e for e, _ in entities_in(query)))
            self.n_missed += 1
            n = len(self.engine.signals)
        self._kick()
        return {"queued": n, "t": self._t}

    def conflicts(self) -> dict:
        with self._lock:
            out = []
            for (left, right), tension in self.engine.tensions.items():
                a, b = self.engine.mems.get(left), self.engine.mems.get(right)
                out.append({
                    "left": left, "right": right,
                    "left_text": a.text if a else None,
                    "right_text": b.text if b else None,
                    "first_seen": tension.first_seen,
                    "observations": tension.observations})
            return {"conflicts": out, "t": self._t}

    def resolve(self, left: int, right: int, verdict: str,
                entity_key: str = "", ensure_tension: bool = False) -> dict:
        """裁决回报。ensure_tension=True（调查员/主 agent 主动裁决两条此前
        没被判为张力的记忆）时先登记 tension 再消解；entity_key 回填到双方。"""
        if verdict not in _VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(_VERDICTS)}")
        with self._lock:
            a, b = self.engine.mems.get(left), self.engine.mems.get(right)
            if ensure_tension and a is not None and b is not None:
                self.engine.add_tension(left, right, self._t)
            if entity_key:
                for m in (a, b):
                    if m is not None and not m.entity:
                        m.entity = entity_key[:120]
            n = self.engine.submit_verdicts([(left, right, verdict)], self._t)
            return {"resolved": n, "t": self._t}

    # ================================================== 日志工具面
    def _bound(self, signal_id: str | None, before) -> int | None:
        """请求给的 before 与信号因果上界取更严者。"""
        b = None if before is None else int(before)
        sb = self._budgets.get(signal_id or "", {}).get("before")
        if sb is not None:
            b = sb if b is None else min(b, sb)
        return b

    def _charge_call(self, signal_id: str | None) -> None:
        if not signal_id:
            return
        with self._lock:
            bud = self._budgets.get(signal_id)
            if bud is None:
                # 调查已结束（超时/放弃）后迟到的工具调用，或伪造的信号号
                raise SignalClosed(f"signal {signal_id} 已关闭或不存在")
            bud["calls"] += 1
            if bud["calls"] > bud["tool_calls"]:
                raise PermissionError(
                    f"该信号工具调用预算 {bud['tool_calls']} 已用尽，请立即汇总输出")

    def log_search(self, query: str, *, before=None, scene=None, k=8,
                   signal_id: str | None = None) -> dict:
        self._charge_call(signal_id)
        hits = self.log.search(query, before=self._bound(signal_id, before),
                               scene=scene or None, k=min(int(k), 20))
        return {"hits": hits, "n": len(hits)}

    def log_timeline(self, entity: str, *, before=None, limit=30,
                     signal_id: str | None = None) -> dict:
        self._charge_call(signal_id)
        rows = self.log.timeline(entity, before=self._bound(signal_id, before),
                                 limit=min(int(limit), 100))
        return {"entity": entity, "timeline": rows, "n": len(rows)}

    def log_stats(self, group_by: str = "scene", *, before=None, limit=30,
                  signal_id: str | None = None) -> dict:
        self._charge_call(signal_id)
        rows = self.log.stats(group_by, before=self._bound(signal_id, before),
                              limit=min(int(limit), 200))
        return {"group_by": group_by, "rows": rows, "n": len(rows),
                "units_total": self.log.count(self._bound(signal_id, before))}

    def log_window(self, unit_ids, *, max_chars=None,
                   signal_id: str | None = None) -> dict:
        self._charge_call(signal_id)
        with self._lock:
            bud = self._budgets.get(signal_id or "")
            if bud is not None:
                cap = bud["window_chars"] - bud["window_used"]
                if cap <= 0:
                    raise PermissionError(
                        f"该信号回展预算 {bud['window_chars']} 字已用尽")
                req = int(max_chars) if max_chars else cap
                cap = min(cap, req)
            else:
                cap = min(int(max_chars) if max_chars else _MAIN_WINDOW_CAP,
                          _MAIN_WINDOW_CAP)
            before = self._bound(signal_id, None)
        out = self.log.window(unit_ids, max_chars=cap, before=before)
        with self._lock:
            bud = self._budgets.get(signal_id or "")
            if bud is not None:
                bud["window_used"] += out["chars"]
                out["budget_left"] = bud["window_chars"] - bud["window_used"]
        return out

    def open_budget(self, signal_id: str, *, tool_calls: int,
                    window_chars: int, before: int | None,
                    origin: str | None = None) -> None:
        """为一次调查开预算。origin 记下这次调查产出该打的来源标签：带
        X-Signal-Id 的 /propose 不信任请求体里的 origin，一律用它。"""
        with self._lock:
            self._budgets[signal_id] = {"tool_calls": int(tool_calls),
                                        "window_chars": int(window_chars),
                                        "calls": 0, "window_used": 0,
                                        "before": before, "origin": origin,
                                        "opened": time.time()}

    def close_budget(self, signal_id: str) -> dict:
        with self._lock:
            bud = self._budgets.pop(signal_id, None)
        if bud is None:
            return {}
        return {"calls": bud["calls"], "window_used": bud["window_used"],
                "elapsed_s": round(time.time() - bud["opened"], 1)}

    # ================================================== 操作面
    def _validate_proposal(self, p: dict, before: int | None) -> tuple[Event, list[int]]:
        text = p.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ProposalRejected("empty_text")
        text = redact_secrets(text.strip())
        if len(text) > _MAX_PROPOSAL_CHARS:
            raise ProposalRejected(f"too_long>{_MAX_PROPOSAL_CHARS}")
        if _SELF_REF_RE.search(text):
            raise ProposalRejected("self_reference")
        src_raw = p.get("source_unit_ids") or p.get("src") or []
        src = []
        for v in src_raw if isinstance(src_raw, list) else []:
            if isinstance(v, bool):
                continue
            if isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit()):
                src.append(int(v))
        if not src:
            raise ProposalRejected("no_source")
        known = self.log.exists(src, before=before)
        bad = sorted(set(src) - set(known))
        if bad:
            raise ProposalRejected(f"unknown_or_future_source:{bad}")
        sal = p.get("salience", 0.5)
        if isinstance(sal, bool) or not isinstance(sal, (int, float)):
            sal = 0.5
        ek = p.get("entity_key")
        sup = [int(v) for v in (p.get("supersedes") or [])
               if isinstance(v, int) and not isinstance(v, bool)]
        ev = Event(self.semantics.fingerprint(normalize(text)), normalize(text),
                   text, tuple(sorted(set(src))),
                   salience=max(0.0, min(1.0, float(sal))),
                   kind="fact", scene=self._scene,
                   entity=(ek.strip()[:120] if isinstance(ek, str) else ""))
        return ev, sup

    def propose(self, proposals: list, *, origin: str = "agent",
                signal_id: str | None = None, before: int | None = None) -> dict:
        """agent 提议入库。逐条校验（溯源非空且存在、因果、脱敏、自指、长度），
        通过的走引擎同一条 ingest 回路；supersedes 经 update 裁决把旧条目
        取代。返回逐条结果。"""
        if not isinstance(proposals, list):
            raise ValueError("proposals must be a list")
        accepted, new_ids, rejected = 0, [], []
        with self._lock:
            bud = self._budgets.get(signal_id or "", {})
            bound = before
            sb = bud.get("before")
            if sb is not None:
                bound = sb if bound is None else min(bound, sb)
            if bud.get("origin"):
                origin = bud["origin"]        # 信号上下文说了算
            if origin not in _ORIGINS:
                origin = "agent"
            t = self._t
            for i, p in enumerate(proposals[:50]):
                if not isinstance(p, dict):
                    rejected.append({"index": i, "reason": "not_an_object"})
                    continue
                try:
                    ev, sup = self._validate_proposal(p, bound)
                except ProposalRejected as exc:
                    rejected.append({"index": i, "reason": str(exc)})
                    self.n_rejected += 1
                    continue
                ev.origin = origin
                ids = self.engine.propose([ev], t)
                accepted += 1
                self.n_proposals += 1
                new_ids.extend(ids)
                if ids and sup:
                    new = ids[-1]
                    for old in sup:
                        if old in self.engine.mems and old != new:
                            self.engine.add_tension(new, old, t)
                            self.engine.submit_verdicts([(new, old, "update")], t)
            pool = self.engine.pool_sizes()
        return {"accepted": accepted, "new_ids": new_ids,
                "merged": accepted - len(new_ids), "rejected": rejected,
                "origin": origin, "pool": pool, "t": t}

    def diagnose(self, miss_type: str, note: str = "", *,
                 signal_id: str | None = None, kind: str = "",
                 usage: dict | None = None) -> dict:
        from .agent.investigator import MISS_TYPES
        if miss_type not in MISS_TYPES:
            raise ValueError(f"miss_type must be one of {MISS_TYPES}")
        with self._lock:
            self.miss_counts[miss_type] = self.miss_counts.get(miss_type, 0) + 1
            counts = dict(self.miss_counts)
        if self.state_path is not None:
            rec = {"ts": round(time.time(), 1), "t": self._t,
                   "signal_id": signal_id, "kind": kind,
                   "miss_type": miss_type, "note": (note or "")[:500],
                   "usage": usage or {}}
            try:
                with open(self.state_path.parent / "diagnoses.jsonl", "a",
                          encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError:
                pass
        return {"miss_counts": counts}

    def signals(self) -> dict:
        with self._lock:
            q = self.engine.signals
            return {"queued": q.peek_kinds(), "n_emitted": q.n_emitted,
                    "n_dropped": q.n_dropped,
                    "open_budgets": sorted(self._budgets),
                    "missed": self.n_missed, "proposals": self.n_proposals,
                    "rejected": self.n_rejected,
                    "candgen_fail": self.n_candgen_fail,
                    "miss_counts": dict(self.miss_counts),
                    "log_units": self.log.count(),
                    "agent": self.agent.stats() if self.agent else None,
                    "t": self._t}

    # ================================================== 持久化
    def save(self) -> dict:
        if self.state_path is None:
            return {"saved": False, "reason": "no state_dir"}
        with self._lock:
            state = {
                "mems": self.engine.mems, "tensions": self.engine.tensions,
                "next_id": self.engine._next_id,
                "consolidation_pending": self.engine._consolidation_pending,
                "consolidation_deferred": self.engine._consolidation_deferred,
                "counters": {k: getattr(self.engine, k) for k in _COUNTERS},
                "retrievals": self._retrievals,
                "next_retrieval": self._next_retrieval,
                "miss_counts": dict(self.miss_counts),
                "service_counters": {"n_candgen_fail": self.n_candgen_fail,
                                     "n_missed": self.n_missed,
                                     "n_proposals": self.n_proposals,
                                     "n_rejected": self.n_rejected},
                "t": self._t, "unit_id": self._unit_id, "scene": self._scene}
            tmp = self.state_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump(state, f)
            os.replace(tmp, self.state_path)
        return {"saved": True, "mems": len(self.engine.mems)}

    def _load(self) -> None:
        with open(self.state_path, "rb") as f:
            state = _RestrictedUnpickler(f).load()
        if not isinstance(state, dict):
            raise ValueError(f"state.pkl 顶层类型异常: {type(state).__name__}")
        missing = _STATE_KEYS - state.keys()
        if missing:
            raise ValueError(f"state.pkl 缺字段: {sorted(missing)}")
        eng = self.engine
        eng.mems = state["mems"]
        for m in eng.mems.values():
            for k, v in _MEMORY_FIELD_DEFAULTS.items():
                if not hasattr(m, k):
                    setattr(m, k, v)
        eng.tensions = state["tensions"]
        eng._next_id = state["next_id"]
        eng._consolidation_pending = state["consolidation_pending"]
        eng._consolidation_deferred = state["consolidation_deferred"]
        for k, v in state["counters"].items():
            setattr(eng, k, v)
        # 后加字段：旧存档没有，.get 兼容
        self._retrievals = state.get("retrievals", {})
        self._next_retrieval = state.get("next_retrieval", 0)
        self.miss_counts = dict(state.get("miss_counts", {}))
        for k, v in state.get("service_counters", {}).items():
            setattr(self, k, v)
        self._t = state["t"]
        self._unit_id = state["unit_id"]
        self._scene = state["scene"]


# ============================ HTTP ============================

_MAX_BODY = 4 * 1024 * 1024          # 请求体上限 4MiB
_GET_PATHS = {"/recall", "/conflicts", "/signals"}   # /health 单列免鉴权
_POST_PATHS = {"/observe", "/feedback", "/resolve", "/search", "/save",
               "/miss", "/log/search", "/log/timeline", "/log/stats",
               "/log/window", "/propose", "/diagnose"}


class _HttpError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


def _opt_int(body: dict, key: str, *, positive: bool = False):
    v = body.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int):
        raise _HttpError(400, f"{key} must be int")
    if positive and v <= 0:
        raise _HttpError(400, f"{key} must be positive")
    return v


def _req_str(body: dict, key: str) -> str:
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise _HttpError(400, f"{key} required")
    return v


class _Handler(BaseHTTPRequestHandler):
    service: MemoryService

    def log_message(self, *args) -> None:   # 静默访问日志
        pass

    def _reply(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return secrets.compare_digest(
            self.headers.get("Authorization") or "",
            f"Bearer {self.service.token}")

    def _body(self) -> dict:
        ct = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ct != "application/json":
            raise _HttpError(415, "Content-Type must be application/json")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise _HttpError(400, "bad Content-Length")
        if n < 0:
            raise _HttpError(400, "bad Content-Length")
        if n > _MAX_BODY:
            raise _HttpError(413, "body too large")
        if not n:
            return {}
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            raise _HttpError(400, "malformed JSON body")
        if not isinstance(body, dict):
            raise _HttpError(400, "body must be a JSON object")
        return body

    def _dispatch(self, path: str, q: dict, body: dict) -> None:
        svc = self.service
        sid = (self.headers.get("X-Signal-Id") or "").strip() or None
        if path == "/health":
            with svc._lock:   # pool_sizes 迭代 mems，与 observe 并发会炸
                self._reply(200, {"ok": True, "t": svc._t,
                                  "mems": svc.engine.pool_sizes(),
                                  "tensions": len(svc.engine.tensions),
                                  "signals": len(svc.engine.signals),
                                  "log_units": svc.log.count(),
                                  "agent": bool(svc.agent)})
        elif path == "/recall":
            try:
                k = int(q["k"]) if q.get("k") else None
            except ValueError:
                raise _HttpError(400, "k must be int")
            if k is not None and k <= 0:
                raise _HttpError(400, "k must be positive")
            query = q.get("q", "")
            if not query:
                raise _HttpError(400, "q required")
            self._reply(200, svc.recall(query, k))
        elif path == "/conflicts":
            self._reply(200, svc.conflicts())
        elif path == "/signals":
            self._reply(200, svc.signals())
        elif path == "/observe":
            user = body.get("user_text", "")
            assistant = body.get("assistant_text", "")
            if not isinstance(user, str) or not isinstance(assistant, str):
                raise _HttpError(400, "user_text/assistant_text must be strings")
            if not user.strip() and not assistant.strip():
                raise _HttpError(400, "empty turn")
            self._reply(200, svc.observe(user, assistant))
        elif path == "/feedback":
            try:
                rid = int(body.get("retrieval_id", -1))
            except (TypeError, ValueError):
                raise _HttpError(400, "retrieval_id must be int")
            out = svc.feedback(rid, body.get("question", ""),
                               body.get("answer", ""))
            if "error" in out:
                code = 409 if "already" in out["error"] else 404
                raise _HttpError(code, out["error"])
            self._reply(200, out)
        elif path == "/resolve":
            try:
                left = int(body.get("left", -1))
                right = int(body.get("right", -1))
            except (TypeError, ValueError):
                raise _HttpError(400, "left/right must be int")
            verdict = str(body.get("verdict", "pending"))
            if verdict not in _VERDICTS:
                raise _HttpError(400, f"verdict must be one of "
                                      f"{sorted(_VERDICTS)}")
            ek = body.get("entity_key", "")
            self._reply(200, svc.resolve(
                left, right, verdict,
                entity_key=ek if isinstance(ek, str) else "",
                ensure_tension=bool(body.get("ensure_tension", False))))
        elif path == "/search":
            k = _opt_int(body, "k", positive=True)
            query = body.get("query", "")
            if not isinstance(query, str) or not query:
                raise _HttpError(400, "query required")
            self._reply(200, svc.recall(query, k))
        elif path == "/miss":
            query = _req_str(body, "query")
            hint = body.get("hint", "")
            source = body.get("source", "agent_tool")
            self._reply(200, svc.report_miss(
                query, hint if isinstance(hint, str) else "",
                source if isinstance(source, str) else "agent_tool"))
        elif path == "/log/search":
            query = _req_str(body, "query")
            scene = body.get("scene")
            self._reply(200, svc.log_search(
                query, before=_opt_int(body, "before"),
                scene=scene if isinstance(scene, str) else None,
                k=_opt_int(body, "k", positive=True) or 8, signal_id=sid))
        elif path == "/log/timeline":
            entity = _req_str(body, "entity")
            self._reply(200, svc.log_timeline(
                entity, before=_opt_int(body, "before"),
                limit=_opt_int(body, "limit", positive=True) or 30,
                signal_id=sid))
        elif path == "/log/stats":
            gb = body.get("group_by", "scene")
            if gb not in ("scene", "entity", "week"):
                raise _HttpError(400, "group_by must be scene | entity | week")
            self._reply(200, svc.log_stats(
                gb, before=_opt_int(body, "before"),
                limit=_opt_int(body, "limit", positive=True) or 30,
                signal_id=sid))
        elif path == "/log/window":
            ids = body.get("unit_ids")
            if (not isinstance(ids, list) or not ids or len(ids) > 20
                    or not all(isinstance(i, int) and not isinstance(i, bool)
                               for i in ids)):
                raise _HttpError(400, "unit_ids must be a non-empty int list (≤20)")
            self._reply(200, svc.log_window(
                ids, max_chars=_opt_int(body, "max_chars", positive=True),
                signal_id=sid))
        elif path == "/propose":
            props = body.get("proposals")
            if not isinstance(props, list):
                raise _HttpError(400, "proposals must be a list")
            origin = body.get("origin", "agent")
            self._reply(200, svc.propose(
                props, origin=origin if isinstance(origin, str) else "agent",
                signal_id=sid, before=_opt_int(body, "before")))
        elif path == "/diagnose":
            mt = _req_str(body, "miss_type")
            note = body.get("note", "")
            try:
                self._reply(200, svc.diagnose(
                    mt, note if isinstance(note, str) else "", signal_id=sid,
                    kind=str(body.get("kind", ""))))
            except ValueError as exc:
                raise _HttpError(400, str(exc))
        elif path == "/save":
            self._reply(200, svc.save())
        else:
            self._reply(404, {"error": f"no such path: {path}"})

    def _run(self, path: str, q: dict, body: dict) -> None:
        try:
            self._dispatch(path, q, body)
        except _HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
        except PermissionError as exc:          # 预算用尽
            self._reply(429, {"error": str(exc)})
        except SignalClosed as exc:             # 信号号无效/已关闭
            self._reply(403, {"error": str(exc)})
        except ValueError as exc:
            self._reply(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self) -> None:    # noqa: N802
        u = urlparse(self.path)
        if u.path == "/health":
            self._run(u.path, {}, {})
            return
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        if u.path not in _GET_PATHS:
            self._reply(405, {"error": f"{u.path} requires POST"})
            return
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self._run(u.path, q, {})

    def do_POST(self) -> None:   # noqa: N802
        u = urlparse(self.path)
        if not self._authorized():
            self._reply(401, {"error": "unauthorized"})
            return
        if u.path not in _POST_PATHS:
            self._reply(405, {"error": f"{u.path} requires GET"})
            return
        try:
            body = self._body()
        except _HttpError as exc:
            self._reply(exc.code, {"error": str(exc)})
            return
        self._run(u.path, {}, body)


def serve(service: MemoryService, port: int,
          host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = type("_BoundHandler", (_Handler,), {"service": service})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd


# ============================ 默认组装 ============================

def _load_env_key(project_dir: Path) -> str | None:
    key = os.environ.get("ZAI_API_KEY")
    if key:
        return key
    for env_file in (Path(project_dir) / ".env",
                     Path(__file__).resolve().parents[1] / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ZAI_API_KEY="):
                    val = (line.split("=", 1)[1].strip()
                           .strip('"').strip("'"))
                    if val:
                        return val
    return None


def build_default_service(project_dir: str | Path,
                          model: str = "glm-5.3-flash",
                          embed_log: bool = True) -> MemoryService:
    from .embed.cache import SqliteEmbeddingCache
    from .embed.zhipu import ZhipuEmbedder

    mem_dir = Path(project_dir) / ".opencode" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    # 目录内含 bearer token + 全量记忆语料 + 原始日志：用户项目里通常没有
    # gitignore 覆盖它——自己写一个，防 `git add .` 把 token/state/日志提交进库
    gi = mem_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    key = _load_env_key(Path(project_dir))

    def chat_fn(system: str, user: str) -> str:
        return chat(api_key=key, model=model, system=system, user=user,
                    cache_dir=mem_dir / "chat-cache")

    emb = ZhipuEmbedder(api_key=key,
                        cache=SqliteEmbeddingCache(mem_dir / "emb.sqlite3"))
    semantics = LLMSemantics(None, chat_fn=chat_fn, model=model)
    cfg = Cfg(theta=0.35, cap_m=8, k=5, tau_dup=0.85, tau_sim=0.78,
              useful_hit=True, defer_credit=True)
    log = LogStore(mem_dir / "log.sqlite", embedder=emb if embed_log else None)
    return MemoryService(cfg, emb, semantics, ChatGenerator(chat_fn),
                         state_dir=mem_dir, logstore=log)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=17872)
    ap.add_argument("--project", default=".")
    ap.add_argument("--model", default="glm-5.3-flash")
    # 插件拉起 sidecar 时不传参，调查员相关配置允许走环境变量
    ap.add_argument("--agent-model",
                    default=os.environ.get("MEMORY_AGENT_MODEL",
                                           "zhipu-env/glm-5.3-flash"),
                    help="调查员 agent 的 opencode 模型（provider/model）")
    ap.add_argument("--no-agent", action="store_true",
                    default=os.environ.get("MEMORY_AGENT", "").lower()
                    in ("off", "0", "false"),
                    help="不启动调查员（仅被动 candgen；信号有界堆积可观测）；"
                         "环境变量 MEMORY_AGENT=off 等价")
    ap.add_argument("--agent-daily-cap", type=int,
                    default=int(os.environ.get("MEMORY_AGENT_DAILY_CAP", "200")))
    ap.add_argument("--agent-tool-calls", type=int, default=8)
    ap.add_argument("--agent-window-chars", type=int, default=4000)
    args = ap.parse_args()

    service = build_default_service(args.project, model=args.model)
    httpd = serve(service, args.port)
    port = httpd.server_address[1]

    agent = None
    if not args.no_agent:
        from .agent.investigator import Budget, OpencodeInvestigator
        from .agent.loop import AgentWorker
        try:
            key = _load_env_key(Path(args.project))
            # 不给调查员开 chat 缓存：载荷含唯一 signal_id 永不命中，只会
            # 无界堆文件；诊断与用量已落 diagnoses.jsonl
            inv = OpencodeInvestigator(
                port=port, token=service.token, model=args.agent_model,
                env_extra={"ZAI_API_KEY": key} if key else None,
                timeout_s=300,
                workdir=Path(__file__).resolve().parents[1])
            agent = AgentWorker(service, inv, daily_cap=args.agent_daily_cap,
                                budget=Budget(tool_calls=args.agent_tool_calls,
                                              window_chars=args.agent_window_chars))
            service.attach_agent(agent)
            agent.start()
        except RuntimeError as exc:      # opencode CLI 不在 PATH
            print(f"[memory-sidecar] 调查员未启动: {exc}", file=sys.stderr,
                  flush=True)

    print(f"[memory-sidecar] http://127.0.0.1:{port} "
          f"project={Path(args.project).resolve()} "
          f"mems={len(service.engine.mems)} log_units={service.log.count()} "
          f"agent={'on' if agent else 'off'}", flush=True)

    def _term(*_):          # 插件 kill 发 SIGTERM：走 finally 存盘
        raise SystemExit(0)

    _signal.signal(_signal.SIGTERM, _term)
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if agent is not None:
            agent.stop()
        service.save()
        httpd.server_close()


if __name__ == "__main__":
    main()
