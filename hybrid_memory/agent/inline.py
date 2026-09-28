"""进程内调查员：sidecar 自己跑 function-calling 循环，直接调服务层。

- 火墙天然成立：这个循环从不调用 observe，调查过程不可能被捕获成记忆；
- 预算/因果上界仍由服务端按 signal_id 计量（log_* 每次调用都记账，
  超限抛 PermissionError → 作为工具结果回给模型，让它收尾），
  本地再加一道轮数上限兜底。

工具面只读：log_search / log_timeline / log_stats / log_window /
memory_search / memory_conflicts。写入（proposals / verdicts / diagnosis）
只走最终 JSON（parse_investigation），由 AgentWorker 经 service.propose 等做
溯源/因果/脱敏校验。
"""
from __future__ import annotations

import json
import sys
from typing import Callable

from ..llm import ZhipuChatError, chat_messages
from .investigator import (_CLI_INSTRUCTION, INVESTIGATOR_SYS, Investigation,
                           parse_investigation)


def _fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props,
                       "required": required}}}


TOOLS = [
    _fn("log_search",
        "在原始交互日志里检索（词法+向量，只返回片段）。先用它定位，再用 log_window 回展原文。",
        {"query": {"type": "string", "description": "查询文本；PR 号/文件名/标识符命中最准"},
         "scene": {"type": "string", "description": "限定情境名（可选）"},
         "k": {"type": "integer", "description": "返回条数，默认 8"}},
        ["query"]),
    _fn("log_timeline",
        "某个实体（文件路径/PR#/commit/标识符/概念）在日志里的全部提及，按时间排列。",
        {"entity": {"type": "string"},
         "limit": {"type": "integer", "description": "最多条数，默认 30"}},
        ["entity"]),
    _fn("log_stats",
        "日志聚合统计（不含原文）：按情境 / 实体 / 周计数。",
        {"group_by": {"type": "string", "enum": ["scene", "entity", "week"]},
         "limit": {"type": "integer"}},
        ["group_by"]),
    _fn("log_window",
        "回展指定日志单元的原文（唯一能看到全文的通道，按字符预算截断）。",
        {"unit_ids": {"type": "array", "items": {"type": "integer"},
                      "description": "要回展的 unit id（≤20）"},
         "max_chars": {"type": "integer"}},
        ["unit_ids"]),
    _fn("memory_search", "检索现有长期记忆，避免重复提议、找出可被取代的旧条目（返回 id）。",
        {"query": {"type": "string"}}, ["query"]),
    _fn("memory_conflicts", "列出未裁决的记忆冲突对（left/right id 与文本）。", {}, []),
]


def _hits(hits: list) -> str:
    if not hits:
        return "（无命中）"
    return "\n".join(
        f"[unit {h['unit_id']} | t={h['t']}{' | ' + h['scene'] if h.get('scene') else ''}] "
        f"{h['snippet']}" for h in hits)


class InlineInvestigator:
    """可调用对象：payload dict → Investigation | None（失败），供 AgentWorker 调用。"""

    def __init__(self, service, *, model: str = "glm-5.3-flash",
                 api_key: str | None = None,
                 chat_fn: Callable[..., dict] | None = None,
                 max_turns: int | None = None):
        self.svc = service
        self.model = model.split("/", 1)[-1]   # 兼容旧的 "provider/model" 写法
        self.api_key = api_key
        self._chat = chat_fn or self._default_chat
        self.max_turns = max_turns
        self.n_calls = 0
        self.n_failed = 0

    def _default_chat(self, messages: list, tools: list) -> dict:
        return chat_messages(messages, tools=tools, api_key=self.api_key,
                             model=self.model)

    # ---- 工具分发：直接调服务层，signal_id 负责计量与因果上界 ----
    def _tool(self, name: str, args: dict, sid: str) -> str:
        svc = self.svc
        if name == "log_search":
            return _hits(svc.log_search(str(args.get("query", "")),
                                        scene=args.get("scene") or None,
                                        k=int(args.get("k") or 8),
                                        signal_id=sid)["hits"])
        if name == "log_timeline":
            r = svc.log_timeline(str(args.get("entity", "")),
                                 limit=int(args.get("limit") or 30), signal_id=sid)
            return f"{r['entity']} 时间线（{r['n']} 处）：\n{_hits(r['timeline'])}"
        if name == "log_stats":
            gb = args.get("group_by", "scene")
            if gb not in ("scene", "entity", "week"):
                return "group_by 必须是 scene | entity | week"
            r = svc.log_stats(gb, limit=int(args.get("limit") or 30), signal_id=sid)
            return (f"共 {r['units_total']} 个单元\n"
                    + "\n".join(json.dumps(x, ensure_ascii=False) for x in r["rows"]))
        if name == "log_window":
            ids = [int(i) for i in (args.get("unit_ids") or [])
                   if isinstance(i, (int, float)) and not isinstance(i, bool)][:20]
            if not ids:
                return "unit_ids 必须是非空整数列表"
            r = svc.log_window(ids, max_chars=args.get("max_chars"), signal_id=sid)
            parts = [f"### unit {u['unit_id']} (t={u['t']})"
                     f"{' [已截断]' if u.get('truncated') else ''}\n"
                     f"[user]\n{u['user_text']}\n\n[assistant]\n{u['assistant_text']}"
                     for u in r.get("units", [])]
            tail = []
            if r.get("missing"):
                tail.append(f"不存在/越界: {r['missing']}")
            if r.get("omitted"):
                tail.append(f"预算不足未回展: {r['omitted']}")
            if isinstance(r.get("budget_left"), int):
                tail.append(f"剩余回展预算: {r['budget_left']} 字")
            return "\n\n".join(parts) + (f"\n\n（{'；'.join(tail)}）" if tail else "")
        if name == "memory_search":
            svc._charge_call(sid)
            rec = svc.recall(str(args.get("query", "")))
            return "\n".join(f"[id={m['id']} | t={m['birth']}] {m['text']}"
                             for m in rec["selected"]) or "（无相关记忆）"
        if name == "memory_conflicts":
            svc._charge_call(sid)
            cs = svc.conflicts()["conflicts"]
            return "\n".join(f"[{c['left']} vs {c['right']}] {c['left_text']} ⚔ "
                             f"{c['right_text']}" for c in cs) or "（无未决冲突）"
        return f"未知工具 {name}"

    def __call__(self, payload: dict) -> Investigation | None:
        self.n_calls += 1
        sid = str(payload.get("signal_id", ""))
        budget = (payload.get("budget") or {}).get("tool_calls", 8)
        max_turns = self.max_turns or int(budget) + 2
        messages = [
            {"role": "system", "content": INVESTIGATOR_SYS},
            {"role": "user", "content": _CLI_INSTRUCTION + "\n\n附件（信号）：\n"
             + json.dumps(payload, ensure_ascii=False, indent=1)},
        ]
        try:
            for turn in range(max_turns):
                # 最后一轮不给工具，逼模型收尾输出 JSON
                tools = TOOLS if turn < max_turns - 1 else None
                msg = self._chat(messages, tools)
                calls = msg.get("tool_calls") or []
                if calls and tools is None:
                    break                     # 末轮仍要工具：不执行，判失败
                if not calls:
                    inv = parse_investigation(msg.get("content") or "")
                    if inv is None:
                        self.n_failed += 1
                    return inv
                messages.append({"role": "assistant",
                                 "content": msg.get("content") or "",
                                 "tool_calls": calls})
                for c in calls:
                    fn = c.get("function") or {}
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                        if not isinstance(args, dict):
                            args = {}
                        out = self._tool(str(fn.get("name", "")), args, sid)
                    except PermissionError as exc:      # 预算用尽：告诉模型收尾
                        out = f"（{exc}）"
                    except Exception as exc:            # noqa: BLE001 工具错误回给模型
                        out = f"（工具失败 {type(exc).__name__}: {exc}）"
                    messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                                     "content": out[:8000]})
                if turn == max_turns - 2:
                    messages.append({"role": "user", "content":
                                     "工具轮数已到上限，请立即只输出最终 JSON 对象。"})
        except ZhipuChatError as exc:
            self.n_failed += 1
            if self.n_failed == 1:
                print(f"[investigator] LLM 调用失败（第 1 次）: {exc}",
                      file=sys.stderr, flush=True)
            return None
        self.n_failed += 1
        return None
