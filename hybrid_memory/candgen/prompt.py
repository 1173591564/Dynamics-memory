"""窗口序列化 + 候选解析 + 凭据脱敏。prompt 与 backend 解耦。

v2 借鉴 tdb-memory MemoryCore l1-extraction：
- 情境切分：prev_scene 跨批携带，继承或切换，产物带回 scene_name
- 类型标签 + priority（元数据，不进 V）+ source_unit_ids 溯源
"""
from __future__ import annotations

import json
import re

from ..datasets.real_chat import InteractionWindow
from .base import CandidateGeneration, MemoryCandidate

INSTRUCTION = """\
你是"情境切分与记忆提取专家"。附件是一段对话日志（若干 InteractionUnit，每个 = 一条 user 提问 + 其后全部 assistant 回复），以及【上一个情境】名。

## 任务一：判断当前情境
- 若新消息延续上一情境（同项目/任务/问题），沿用其名字；
- 话题/目标明显变化则新建；
- 命名格式："在围绕[对象]做[活动]"，30-50 字，单句。

## 任务二：提取值得长期记住的原子记忆
原则：
- 宁缺毋滥：不记寒暄、一次性请求、过程性细节、未被采纳的建议；
- 独立完整：不读原文也能懂，补全实体/时间/路径；
- 归纳合并：强因果关联的内容合为一条，不碎片化；
- 区分场景：同实体不同场景结论不同就分开写，带场景限定；
- 前后矛盾写最新状态，可在句中保留"原先是 X"；
- 绝不输出密钥/token/密码的具体值，凭据值一律写 [REDACTED]。

每条记忆给出：
- content：完整自包含陈述句；
- type：work_fact（事实/决策/状态/约束）| work_task（待办/跟进）| work_method（SOP/禁忌/经验/判断标准）| work_artifact（文档/PR/报告/脚本）| preference（用户偏好/习惯）；
- priority：80-100 核心，60-79 一般，<60 应直接丢弃；
- source_unit_ids：来源 unit 的 id 列表。

## 输出格式（严格 JSON，不要任何其他文字/代码块标记）
{"scene_name": "...", "memories": [{"content": "...", "type": "...", "priority": 80, "source_unit_ids": [0]}]}

没有值得记的：{"scene_name": "...", "memories": []}"""

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._\-]{16,}|"
    r"api[_-]?key[\"'\s:=]+[A-Za-z0-9._\-]{16,})",
    re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """输出层兜底：凭据模式替换为 [REDACTED]，事实陈述保留。"""
    return _SECRET_RE.sub("[REDACTED]", text)


def serialize_window(window: InteractionWindow, prev_scene: str = "") -> str:
    head = (f"【上一个情境】：{prev_scene or '无'}\n\n"
            f"【待提取的新消息】（unit id 供 source_unit_ids 引用）：\n\n")
    parts = []
    for u in window.units:
        parts.append(
            f"### Unit {u.id} (t={u.start_time}~{u.end_time})\n"
            f"[user]\n{u.user_text}\n\n[assistant]\n{u.assistant_text}")
    return head + "\n\n".join(parts)


def _candidate_from(item: dict) -> MemoryCandidate | None:
    text = item.get("content", item.get("text"))
    if not isinstance(text, str) or not text.strip():
        return None
    src = item.get("source_unit_ids") or item.get("source_message_ids") or ()
    return MemoryCandidate(
        text=redact_secrets(text.strip()),
        type=str(item.get("type", "")),
        priority=item.get("priority") if isinstance(item.get("priority"), int) else None,
        source_unit_ids=tuple(int(x) for x in src
                              if isinstance(x, (int, float))),
    )


def parse_generation(text: str) -> CandidateGeneration:
    """解析 v2 对象 {"scene_name","memories":[...]}；兼容 v1 裸数组。"""
    # v2: 找第一个 JSON 对象
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(obj, dict) and isinstance(obj.get("memories"), list):
            cands = [c for it in obj["memories"]
                     if isinstance(it, dict)
                     for c in [_candidate_from(it)] if c]
            return CandidateGeneration(
                candidates=tuple(cands),
                scene_name=str(obj.get("scene_name", "")))
        start = text.find("{", start + 1)
    # v1 兼容：裸数组
    return CandidateGeneration(candidates=tuple(parse_candidates(text)))


def parse_candidates(text: str) -> list[MemoryCandidate]:
    """v1 兼容：从输出中抽第一个 JSON 数组。"""
    start = text.find("[")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("[", start + 1)
            continue
        if isinstance(obj, list):
            out: list[MemoryCandidate] = []
            for item in obj:
                if isinstance(item, dict):
                    c = _candidate_from(item)
                    if c:
                        out.append(c)
            return out
        start = text.find("[", start + 1)
    return []
