"""L2 半合成语料：L1 模板流 → LLM 改写 → 自然话术语料（账本/金值不变）。

改写硬约束（违反即重试，再违反保留原文并打标，绝不静默腐蚀语料）：
1. 本轮涉及的事实值 token（如 zorvex-4821）必须逐字出现在改写文本中；
2. 操作语义不变（设定/更新/撤回/派生）；
3. 更新与撤回**不复述旧值**——旧值 token 出现即判分有害（L1 判分约束）；
4. 口语自然、贴近真实项目对话，长度与原文同量级；
5. 只输出 JSON。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

_EVAL = str(Path(__file__).resolve().parents[1])
_REPO = str(Path(__file__).resolve().parents[2])
for _p in (_EVAL, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tide.gen_l1 import generate as gen_l1_generate  # noqa: E402
from tide.ledger import Stream  # noqa: E402
from tide.text import has_token  # noqa: E402

_SYS = (
    "你是中文项目对话的话术改写器。把给定的模板化对话轮改写成自然、口语、"
    "像真实开发者的说法，严格遵守：\n"
    "1. 指定的值 token（形如 word-1234）必须逐字保留，一个都不能少；\n"
    "2. 不改变事实操作的语义（设定/更新/撤回/派生关系照旧）；\n"
    "3. 被列为禁用的旧值 token 绝对不能出现（用户更新/撤回时不复述旧值）；\n"
    "4. 用户句与助手句都改写，长度与原文相近（用户句 10~40 字为宜）；\n"
    "5. 只输出 JSON：{\"user\": \"...\", \"assistant\": \"...\"}"
)
_SYS_Q = (
    "把模板化的项目提问改写成自然口语提问。要求：主体名称逐字保留、"
    "指定的值 token（若有）逐字保留、仍是一个问题。只输出 JSON："
    "{\"query\": \"...\"}"
)


def _chat_json(llm, messages: list, api_key: str | None) -> dict | None:
    # hybrid_memory.llm.chat_messages 返回 {"content": str, "reasoning_content": ...}
    resp = llm.chat_messages(messages, api_key=api_key) if api_key else \
        llm.chat_messages(messages)
    content = resp.get("content") if isinstance(resp, dict) else resp
    if not isinstance(content, str) or not content.strip():
        return None
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def _rewrite_turn(llm, api_key, turn, facts_by_id, attempt=0) -> dict:
    vals, banned = [], []
    for fid in turn.facts:
        f = facts_by_id.get(fid)
        if f is None:
            continue
        if turn.op == "retract":
            banned.append(f.value)
        else:
            vals.append(f.value)
        if f.supersedes and f.supersedes in facts_by_id:
            banned.append(facts_by_id[f.supersedes].value)
    hint = (f"操作类型：{turn.op}；必须保留的值 token：{vals or '无'}；"
            f"禁用的旧值 token：{banned or '无'}")
    messages = [{"role": "system", "content": _SYS},
                {"role": "user", "content":
                 f"{hint}\n原文：\n用户：{turn.user}\n助手：{turn.assistant}"}]
    out = _chat_json(llm, messages, api_key)
    ok = False
    if out and isinstance(out.get("user"), str) and isinstance(out.get("assistant"), str):
        blob = f"{out['user']}\n{out['assistant']}"
        ok = (all(has_token(blob, v) for v in vals)
              and not any(has_token(blob, b) for b in banned)
              and len(out["user"]) > 3)
    if ok:
        return {"user": out["user"], "assistant": out["assistant"],
                "rewritten": True}
    if attempt < 1:
        time.sleep(1.0)
        return _rewrite_turn(llm, api_key, turn, facts_by_id, attempt + 1)
    # 兜底：保留模板原文并显式打标——语料完整性优先于改写覆盖率
    return {"user": turn.user, "assistant": turn.assistant, "rewritten": False}


def _rewrite_probe(llm, api_key, probe, facts_by_id) -> dict:
    messages = [{"role": "system", "content": _SYS_Q},
                {"role": "user", "content": f"原文：{probe.query}"}]
    out = _chat_json(llm, messages, api_key)
    q = out.get("query") if isinstance(out, dict) else None
    # 校验：改写仍是问题，且主体至少共享一个汉字 bigram（防改丢主体）
    import re as _re
    subj = _re.sub(r"(现在是什么|现在几|是多少|\?|？|。|吗)", "", probe.query)
    bigrams = {subj[i:i + 2] for i in range(len(subj) - 1)
               if "\u4e00" <= subj[i] <= "\u9fff" and "\u4e00" <= subj[i + 1] <= "\u9fff"}
    if isinstance(q, str) and 4 < len(q) < 200 and \
            any(b in q for b in bigrams):
        return {"query": q, "rewritten": True}
    return {"query": probe.query, "rewritten": False}


def trim_stream(st: Stream, filler_every: int = 5):
    """事实轮裁剪（audit 语料用）：保留全部事实轮（facts 非空）+ 每
    filler_every 个噪声轮留 1 个；t 与 probe.t 重排。事实序列与相对顺序
    不变，探针金值语义保持；TIDE 维度曲线不适用裁剪流（本工具只做
    抽检语料，不跑曲线）。"""
    import dataclasses
    kept = [t for t in st.turns if t.facts or t.t % filler_every == 0]
    old_ts = [t.t for t in kept]
    turns = [dataclasses.replace(t, t=i) for i, t in enumerate(kept)]
    probes = []
    for p_ in st.probes:
        new_t = sum(1 for ot in old_ts if ot < p_.t)
        probes.append(dataclasses.replace(p_, t=new_t))
    return dataclasses.replace(st, turns=turns, probes=probes)


def build(api_key: str | None, seeds: int, out_path: str,
          mock: bool = False, trim: bool = False,
          dims: tuple | None = None) -> dict:
    streams: list[Stream] = gen_l1_generate(seeds=seeds)
    if dims:
        want = set(dims)
        streams = [st for st in streams if st.dimension in want]
    if trim:
        streams = [trim_stream(st) for st in streams]
    from hybrid_memory import llm  # 延迟导入：repo 路径就绪后再取
    corpus = {"kind": "l2", "mock": mock, "seeds": seeds,
              "streams": []}
    for st in streams:
        facts_by_id = {f.id: f for f in st.facts}
        srow = {"id": st.id, "dimension": st.dimension, "seed": st.seed,
                "facts": [f.__dict__ for f in st.facts], "turns": [], "probes": []}
        for turn in st.turns:
            r = ({"user": turn.user, "assistant": turn.assistant, "rewritten": False}
                 if mock else _rewrite_turn(llm, api_key, turn, facts_by_id))
            srow["turns"].append({
                "t": turn.t, "op": turn.op, "fact_ids": list(turn.facts),
                "user": r["user"], "assistant": r["assistant"],
                "orig_user": turn.user, "orig_assistant": turn.assistant,
                "rewritten": r["rewritten"]})
        for probe in st.probes:
            r = ({"query": probe.query, "rewritten": False} if mock
                 else _rewrite_probe(llm, api_key, probe, facts_by_id))
            srow["probes"].append({
                "id": probe.id, "t": probe.t, "dimension": probe.dimension,
                "knob": probe.knob, "query": r["query"],
                "orig_query": probe.query, "gold": list(probe.gold),
                "harmful": list(probe.harmful), "rewritten": r["rewritten"]})
        corpus["streams"].append(srow)
        print(f"[l2] 流 {st.id}（{st.dimension}）改写完成："
              f"{sum(1 for t in srow['turns'] if t['rewritten'])}/{len(srow['turns'])} 轮"
              f"、{sum(1 for p in srow['probes'] if p['rewritten'])}/{len(srow['probes'])} 探针",
              flush=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return corpus


def retrieval_smoke() -> dict:
    texts = [
        "网关模块的端口定为 gate-4100。",
        "网关模块的端口改成 gate-4200 了。",
        "部署模块的端口定为 deploy-5100。",
        "日志级别定为 trace-6100。",
        "以后写 PR 描述请保持简洁，先写动机，再写影响范围。",
        "恢复机制要求 checkpoint 和效果在同一事务提交，失败时一起回滚。",
        "日志级别那个设定作废了，先别用。",
        "部署模块的端口改成 deploy-5200 了。",
        "不对，你记错了，网关模块的端口是 gate-4200，部署模块的端口是 deploy-5200，不要混淆。",
    ]
    specs = [
        (1, "R", "网关模块的端口现在是什么？", ["gate-4100"], [], "current_value"),
        (2, "V", "网关模块的端口现在是什么？", ["gate-4200"], ["gate-4100"], "obsolete_suppression"),
        (3, "C", "部署模块的端口现在是什么？", ["deploy-5100"], ["gate-4100", "gate-4200"], "scope"),
        (4, "R", "日志级别现在是什么？", ["trace-6100"], [], "retraction_precondition"),
        (5, "R", "用户偏好 PR 描述采用什么结构？", ["简洁", "动机", "影响范围"], [], "preference"),
        (6, "R", "checkpoint 与效果在失败时怎样恢复？", ["同一事务", "回滚"], [], "mechanism"),
        (7, "F", "日志级别现在是什么？", [], ["trace-6100"], "retraction"),
        (8, "V", "部署模块的端口现在是什么？", ["deploy-5200"], ["deploy-5100", "gate-4200"], "update_scope"),
        (9, "C", "网关模块的端口现在是什么？", ["gate-4200"], ["gate-4100", "deploy-5200"], "reviewer_correction"),
    ]
    return {"kind": "l2", "purpose": "retrieval-smoke-not-TIDE-curves", "streams": [{
        "id": "retrieval-smoke", "turns": [{"t": i, "user": text, "assistant": "收到。"}
                                               for i, text in enumerate(texts)],
        "probes": [{"id": f"smoke-p{i}", "t": t, "dimension": dim, "knob": i,
                    "query": query, "gold": gold, "harmful": harmful, "scenario": scenario}
                   for i, (t, dim, query, gold, harmful, scenario) in enumerate(specs)]}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mock", action="store_true",
                    help="自检模式：不做 LLM 改写，直通模板原文")
    ap.add_argument("--trim", action="store_true",
                    help="事实轮裁剪（audit 语料；TIDE 曲线不适用）")
    ap.add_argument("--dims", default=None,
                    help="逗号分隔维度过滤，如 R,V,C,F")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--retrieval-smoke", action="store_true")
    args = ap.parse_args()
    if args.retrieval_smoke:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(retrieval_smoke(), ensure_ascii=False, indent=1), encoding="utf-8")
        return
    key = args.api_key or __import__("os").environ.get("ZAI_API_KEY")
    dims = tuple(args.dims.split(",")) if args.dims else None
    build(key, args.seeds, args.out, mock=args.mock, trim=args.trim, dims=dims)


if __name__ == "__main__":
    main()
