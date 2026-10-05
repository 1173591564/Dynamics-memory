"""检索回路（P4 从 server.py 原样迁入）：recall/主检索/结果整形/行渲染/因果集。

H29 contested 上界：在 context_lines 修掉——每条入选记忆至多带 1 个
对手、总 contested 行不超过 CONTESTED_K，超限截断并经 truncated 标志
上报（与 budget_tokens 整行截断共用同一标志位）。
"""
from __future__ import annotations

import copy
import json
import re

from ..core.engine import MemoryEngine
from ..core.types import Query, Retrieval

_RETRIEVAL_KEEP = 512   # retrieval 注册表上限（feedback 用，防无界增长）

# H29 contested 上界（决策 H29 称 contested_k）：BASELINE #3 的 top-k=5
# 注入 16 行中有 11 行未决冲突，违背"注入块有界"承诺；现每条入选记忆
# 至多 1 对手、总 contested 行 ≤ 3，超限截断 + truncated=true。
CONTESTED_K = 3

# [^>]* 单趟即可：匹配内部不含 '>'，嵌套 payload 被整体吃掉，
# 任何残留的 "relevant-memories" 片段都凑不成完整 tag
_MEM_TAG_RE = re.compile(r"<\s*/?\s*relevant-memories[^>]*>", re.IGNORECASE)

_TOKEN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


def _safe_mem_text(text: str) -> str:
    """记忆文本进 <relevant-memories> 包裹块前的消毒：中和同名分隔符
    （含嵌套/带属性/自闭合变体），防存储型注入破 tag 逃逸污染
    system prompt。"""
    return _MEM_TAG_RE.sub(" ", text)


def approx_tokens(text: str) -> int:
    """与 TIDE 平台一致的近似 token 计数：CJK 单字 = 1，ASCII 词 = 1，
    其余非空白符号 = 1。只用于预算截断，不追求与具体 tokenizer 对齐。"""
    return len(_TOKEN_RE.findall(text))


def context_lines(ret: Retrieval) -> tuple[list[tuple[str, object]], bool]:
    """渲染注入行；返回 (lines, truncated)。

    H29/N20：contested 按入选记忆去重（首个对手胜出），总行数不超过
    CONTESTED_K；有任何 contested 对被丢弃即 truncated=True。
    对手被省略的入选条目，在主条目显式标注“[有未决冲突，不可断言为当前事实]”。
    """
    prov_ids = {m.id for m in ret.provisional}
    shown: set[int] = set()
    emitted = 0
    emitted_m_ids: set[int] = set()
    contested_m_ids = {m.id for m, _ in ret.contested}
    for m, rival in ret.contested:
        if m.id in shown or emitted >= CONTESTED_K:
            continue
        shown.add(m.id)
        emitted += 1
        emitted_m_ids.add(m.id)

    lines = []
    for m in ret.selected:
        has_omitted_rival = (m.id in contested_m_ids and m.id not in emitted_m_ids)
        conflict_prefix = (
            "[待人审冲突，不可断言为当前事实] " if m.pending_review
            else ("[有未决冲突，不可断言为当前事实] " if has_omitted_rival else "")
        )
        lines.append((
            f"- {'[未确认] ' if m.id in prov_ids else ''}"
            f"{conflict_prefix}"
            f"{'[项目状态汇总] ' if m.kind == 'reflection' else ''}"
            f"[t={m.birth}] {_safe_mem_text(m.text)}", m))

    emitted_set = set(emitted_m_ids)
    for m, rival in ret.contested:
        if m.id in emitted_set:
            emitted_set.remove(m.id)
            lines.append((f"- ⚠️未决冲突：[t={rival.birth}] "
                          f"{_safe_mem_text(rival.text)}"
                          f"（与 t={m.birth} 条目冲突）", None))
    review_targets = set()
    review_count = 0
    for dispute in ret.disputes:
        if dispute["target_id"] in shown or dispute["target_id"] in review_targets or emitted + review_count >= CONTESTED_K:
            continue
        review_targets.add(dispute["target_id"])
        review_count += 1
        lines.append((f"- [待人审提案，非当前事实] {_safe_mem_text(dispute['text'])}", None))
    return lines, emitted != len(ret.contested) or review_count != len(ret.disputes)


def attach_disputes(svc, ret, before=None) -> None:
    selected = {m.id for m in ret.selected}
    ret.disputes = []
    for review in svc.tasks.pending_reviews():
        if review["target_id"] not in selected:
            continue
        candidate = json.loads(review["candidate"])
        sources = candidate.get("source_unit_ids", [])
        if set(sources) <= set(svc.log.exists(sources, before=before)):
            ret.disputes.append({"review_id": review["id"], "target_id": review["target_id"],
                                 "text": candidate["text"], "src": sources})


def causal_memory_ids(svc, before: int | None) -> set[int]:
    """保守的当前版本过滤，不冒充历史版本重建；调用方持 service lock。
    birth 不够：旧记忆也可能在未来被确认/合并，或携带未来来源。
    """
    if before is None:
        return set(svc.engine.mems)
    candidates = [m for m in svc.engine.mems.values()
                  if m.birth < before and m.last_seen < before]
    src = {uid for m in candidates for uid in m.src}
    known = set(svc.log.exists(src, before=before)) if src else set()
    eligible = {m.id for m in candidates if set(m.src) <= known}
    # submit_verdicts 会沿替代/聚合链找当前代表，不能借旧 id 写到未来。
    while True:
        blocked = {mid for mid in eligible
                   if any(ref is not None and ref not in eligible
                          for ref in (svc.engine.mems[mid].superseded_by,
                                      svc.engine.mems[mid].aggregated_into))}
        if not blocked:
            return eligible
        eligible -= blocked


def causal_tensions(svc, ids: set[int], before: int | None) -> dict:
    return {pair: tension for pair, tension in svc.engine.tensions.items()
            if all(mid in ids for mid in pair)
            and (before is None or tension.last_seen < before)}


def recall(svc, q: str, k: int | None = None, *,
           signal_id: str | None = None, budget_tokens: int | None = None,
           passive: bool = False) -> dict:
    if budget_tokens is not None and (type(budget_tokens) is not int or budget_tokens < 0):
        raise ValueError("budget_tokens must be a non-negative int")
    if not isinstance(passive, bool):
        raise ValueError("passive must be bool")
    ctx, _, _ = svc._admit(signal_id)
    if signal_id is None and not passive:
        return recall_main(svc, q, k, budget_tokens)
    qv = svc.emb.embed([q])[0]  # 未准入的请求不会触发 embedding
    with svc._lock:
        svc._ensure_healthy()
        ids = causal_memory_ids(svc, ctx.before)
        cfg = copy.copy(svc.cfg)
        if k is not None:
            cfg.k = k
        cfg.defer_credit, cfg.shadow_credit = True, False
        view = MemoryEngine(cfg, svc.emb, svc.semantics)
        view.mems = copy.deepcopy({i: svc.engine.mems[i] for i in ids})
        view.tensions = copy.deepcopy(causal_tensions(svc, ids, ctx.before))
        # 沿用原排序/压制算法，但在筛选后的副本中运行；不改原记忆、
        # 不复活/记信用、不发主引擎信号，也不登记可被 feedback 的 rid。
        ret = view.retrieve(qv, Query(-1, q), svc._t if ctx.before is None else min(svc._t, ctx.before - 1))
        attach_disputes(svc, ret, ctx.before)
        return recall_result(ret, None, budget_tokens)


def recall_main(svc, q: str, k: int | None = None,
                budget_tokens: int | None = None) -> dict:
    qv = svc.emb.embed([q])[0]
    with svc._lock:
        svc._ensure_healthy()

        def mutate():
            if k is not None:
                old_k, svc.cfg.k = svc.cfg.k, k
                try:
                    ret = svc.engine.retrieve(qv, Query(-1, q), svc._t)
                finally:
                    svc.cfg.k = old_k
            else:
                ret = svc.engine.retrieve(qv, Query(-1, q), svc._t)
            rid = svc._next_retrieval
            svc._next_retrieval += 1
            svc._retrievals[rid] = ret
            while len(svc._retrievals) > _RETRIEVAL_KEEP:
                # 已持久接受的反馈不能因为后续检索挤出引用对象。
                evictable = [i for i, r in svc._retrievals.items()
                             if not r.feedback_sent or r.credited]
                if not evictable:
                    break
                svc._retrievals.pop(min(evictable))
            # /search 发生在回答前；/feedback 再关联上一轮。
            attach_disputes(svc, ret)
            return recall_result(ret, rid, budget_tokens)

        out = svc._commit_sidecar_effect(mutate)
        svc._unit_wake.set()
        return out


def recall_result(ret: Retrieval, rid: int | None,
                  budget_tokens: int | None = None) -> dict:
    lines, kept, used = [], [], 0
    raw, contested_truncated = context_lines(ret)
    budget_cut = False
    for line, memory in raw:
        cost = approx_tokens(line) + (1 if lines else 0)
        if budget_tokens is not None and used + cost > budget_tokens:
            budget_cut = True
            break
        lines.append(line)
        used += cost
        if memory is not None:
            kept.append(memory)
    # 延迟反馈只给实际送入上下文的记忆记账。
    ret.selected = kept
    ret.presented_texts = tuple(m.text for m in kept)
    return {"retrieval_id": rid, "context": "\n".join(lines),
            "n": len(kept), "tokens": used,
            "truncated": contested_truncated or budget_cut,
            "selected": [{"id": m.id, "text": m.text,
                          "birth": m.birth, "kind": m.kind,
                          "origin": m.origin, "src": sorted(m.src)}
                         for m in ret.selected]}
