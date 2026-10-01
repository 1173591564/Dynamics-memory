"""窗口序列化 + 候选解析 + 凭据脱敏。prompt 与 backend 解耦。

v2 借鉴 tdb-memory MemoryCore l1-extraction：
- 情境切分：prev_scene 跨批携带，继承或切换，产物带回 scene_name
- 类型标签 + priority（元数据，不进 V）+ source_unit_ids 溯源
"""
from __future__ import annotations

import json
import math
import re

from ..interaction import InteractionWindow
from .base import CandidateGeneration, MemoryCandidate

INSTRUCTION = """\
你是"情境切分与记忆提取专家"。附件是一段对话日志（若干 InteractionUnit，每个 = 一条 user 提问 + 其后全部 assistant 回复），以及【上一个情境】名。

## 任务一：判断当前情境
- 若新消息延续上一情境（同项目/任务/问题），沿用其名字；
- 话题/目标明显变化则新建；
- 命名格式："在围绕[对象]做[活动]"，30-50 字，单句。

## 任务二：提取值得长期记住的原子记忆
原则：
- 覆盖优先：承重信息宁可多记——数字/版本/commit数、实体归属、当前状态、
  已采纳决策、风险与阻塞、约束与规则、实验结论、术语定义；
  丢的只是 storage，丢一条承重事实的代价远大于多存一条；
- 不记的仅限：寒暄闲聊、一次性请求（"这次/本单"）、未被采纳的建议、
  纯情绪表达；记忆系统自身的操作过程（检索/裁决/合并记忆的动作、
  "我查到了什么"）不是项目事实，不记；
- 独立完整：不读原文也能懂，补全实体/时间/路径，写清起因经过结果；
- 归纳合并：强因果关联的内容合为一条，不碎片化；
- 区分场景：同实体不同场景结论不同就分开写，带场景限定；
- 前后矛盾写最新状态，可在句中保留"原先是 X"；
- 绝不输出密钥/token/密码的具体值，凭据值一律写 [REDACTED]。

每条记忆给出：
- content：完整自包含陈述句；
- type：work_fact（事实/决策/状态/约束）| work_task（待办/跟进）| work_method（SOP/禁忌/经验/判断标准）| work_artifact（文档/PR/报告/脚本）| preference（用户偏好/习惯）；
- salience：0.0–1.0，该记忆缺失时的预期下游损失/后悔度——不是紧急度，也不是真值置信度。硬性约束、已采纳决策、当前阻塞、截止时间、不可逆操作护栏为高；容易重建的实现细节为低；
- priority：80-100 核心，60-79 一般，<60 应直接丢弃（兼容字段，可选）；
- source_unit_ids：来源 unit 的 id 列表。

## 输出格式（严格 JSON，不要任何其他文字/代码块标记）
{"scene_name": "...", "memories": [{"content": "...", "type": "...", "salience": 0.8, "source_unit_ids": [0]}]}

没有值得记的：{"scene_name": "...", "memories": []}"""

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9][A-Za-z0-9_\-]{7,}|Bearer\s+[A-Za-z0-9._\-]{16,}|"
    r"api[_-]?key[\"'\s:=]+[A-Za-z0-9._\-]{16,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}|"
    r"(?:password|passwd|secret|token)[\"'\s:=]+[^\s\"']{8,}|"
    # PEM：BEGIN 到 END 整块脱（含密钥本体），END 缺失时至少盖住 BEGIN 行
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"(?:.*?-----END [A-Z ]*PRIVATE KEY-----)?)",
    re.IGNORECASE | re.DOTALL)


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


def parse_salience(value, default: float = 0.5) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or isinstance(value, float) and not math.isfinite(value)):
        return default
    return float(max(0, min(1, value)))


def priority_to_salience(priority, default: float = 0.5) -> float:
    if (isinstance(priority, bool) or not isinstance(priority, (int, float))
            or isinstance(priority, float) and not math.isfinite(priority)):
        return default
    return (max(60, min(100, priority)) - 60) / 40


def parse_ids(values) -> list[int]:
    """模型/旧缓存的 ID 列表：兼容十进制字符串和整值浮点，不截断小数。
    只保留非负 SQLite INTEGER 范围，避免 bool、NaN 和超大整数污染溯源。
    """
    if not isinstance(values, (list, tuple)):
        return []
    out = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, str):
            if not value.strip().isdecimal():
                continue
        elif not (isinstance(value, int) or isinstance(value, float) and value.is_integer()):
            continue
        try:
            uid = int(value)
        except ValueError:
            continue
        if 0 <= uid <= 2**63 - 1:
            out.append(uid)
    return out


def parse_candidate(item: dict | str) -> MemoryCandidate | None:
    if isinstance(item, str):
        item = {"text": item}
    if not isinstance(item, dict):
        return None
    text = item.get("content", item.get("text"))
    if not isinstance(text, str) or not text.strip():
        return None
    src = item.get("source_unit_ids") or item.get("source_message_ids") or ()
    salience = parse_salience(item.get("salience"),
                              priority_to_salience(item.get("priority")))
    return MemoryCandidate(
        text=redact_secrets(text.strip()),
        type=str(item.get("type", "")),
        priority=item.get("priority") if type(item.get("priority")) is int else None,
        source_unit_ids=tuple(parse_ids(src)),
        salience=salience,
    )


def parse_generation(text: str) -> CandidateGeneration:
    """解析 v2/v1，容忍围栏/前言；无合法载荷抛 ValueError，不伪装成空结果。"""
    decoder = json.JSONDecoder()
    offset = 0
    while (match := re.search(r"[\[{]", text[offset:])) is not None:
        offset += match.start()
        try:
            obj, end = decoder.raw_decode(text, offset)
        except json.JSONDecodeError:
            offset += 1
            continue
        offset = end  # 不把无效 envelope 内的 metadata/source 数组当作候选
        scene = str(obj.get("scene_name", "")) if isinstance(obj, dict) else ""
        items = obj.get("memories") if isinstance(obj, dict) else obj
        if isinstance(items, list):
            return CandidateGeneration(
                tuple(c for item in items if isinstance(item, dict)
                      and (c := parse_candidate(item)) is not None), scene)
    raise ValueError("no valid candidate generation JSON")
