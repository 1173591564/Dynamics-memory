"""触发扫描：一轮交互值不值得定向抽取——零 LLM 的确定性判断。

被动 candgen 之所以"宁可多记"，是因为漏记不可逆。有了 L0 logstore 和
recall_miss 修复回路后，漏记只是可回填的缓存缺页，抽取可以保守：
只有命中下面任一信号的单元才发 extract_due，其余仅留在 L0。

  correction  用户开头就在纠正（"不对/不是/错了/我说过…"）——上一轮记忆
              大概率有误或缺失，同时也是 recall_miss 的来源
  decision    决策/约束词汇（决定/改成/采用/放弃/必须/禁止/统一用…）
  quant       数量·日期·截止·版本号等会改变行动的硬数字
  new_entity  日志里首次出现的 ASCII 硬实体（路径/PR/hash/标识符）
  long_turn   超长回复：通常是排障/方案陈述，信息密度高

模式刻意保守：宁可漏发（有修复回路兜底）也不把闲聊推给调查员。
"""
from __future__ import annotations

import re

CORRECTION_RE = re.compile(
    r"^\s*[\"'“”‘’(（\[]*\s*(?:"
    r"不对|不是这样|不是的|不是吧|不是|错了|你错了|搞错了|记错了|"
    r"别这样|别再|不要再|不要|我说过|之前说的是|之前是|应该是|改回|"
    r"你记错|你搞错|并不是|其实不是|不，|不。|no[,.\s]|nope|wrong|actually|"
    r"that's (?:not|wrong)|incorrect"
    r")", re.IGNORECASE)

DECISION_RE = re.compile(
    r"(?:决定|定下来|敲定|最终方案|改成|改为|换成|切到|迁移到|采用|选用|"
    r"放弃|弃用|废弃|不再|以后都|以后统一|统一用|一律|必须|禁止|不允许|"
    r"约定|规定|默认改|默认用|deprecated?|we (?:will|should) (?:use|switch)|"
    r"decided|from now on|must not|always use|never use)",
    re.IGNORECASE)

QUANT_RE = re.compile(
    r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}月\d{1,2}[日号]|截止|deadline|ddl\b|"
    r"\d+(?:\.\d+)?\s*(?:个|条|次|天|小时|分钟|周|月|GB|MB|KB|ms|s\b|%|"
    r"qps|rps|并发|台|核|G\b|k\b|w\b|万|亿)|"
    r"\bv?\d+\.\d+\.\d+\b|上限|下限|最多|最少|至多|至少|不超过)",
    re.IGNORECASE)

LONG_TURN_CHARS = 2500

CLAIM_RE = re.compile(
    r"^(?P<head>[\w\u3400-\u9fff ./:'-]{1,100}?)"
    r"(?:(?:由|从)\s*(?P<old>[A-Za-z0-9_.:/+-]+)\s*(?:改为|改成|调整为|变更为)|"
    r"(?P<set>定为|设为|设置为|调整为|改为|改成|变更为| is set to | set to )|"
    r"(?P<assert>现在是|目前是|当前是|应该是|应为|是|为| is | = |:=))\s*"
    r"(?P<value>[^\s，,。；;！？?!（）()]{1,120})$", re.IGNORECASE)
RETRACT_RE = re.compile(
    r"^(?:之前的|先前的|原来的|此前的)?(?P<head>[\w\u3400-\u9fff ./:'-]{1,100}?)"
    r"(?:设定|设置)?(?:\s+[（(]?(?P<value>[A-Za-z0-9_][A-Za-z0-9_.:/+-]{0,119})[）)]?)?"
    r"\s*(?:已经|已)?(?:被)?(?:作废|撤回|废弃|弃用|停用|取消|withdrawn|retracted)$", re.IGNORECASE)
UNSAFE_CLAIM_RE = re.compile(
    r"[?？\"“”‘’`]|如果|假设|可能|建议|考虑|例如|据说|引用|"
    r"\b(?:if|maybe|could|should|suggest|example|quote)\b", re.IGNORECASE)


def claim_key(head: str) -> tuple[str, str]:
    head = re.sub(r"(?:最初|最早|原先|原本|目前|当前|现在|最新|已|那个|这个)$", "", head.strip())
    parts = head.rsplit("的", 1) if "的" in head else ["", head]
    if not parts[0] and parts[1].startswith("项目"):
        parts[1] = parts[1][2:]
    return tuple(re.sub(r"\s+", "", part) for part in parts)


def claims_in(text: str, *, authoritative: bool = False) -> list[dict]:
    if not isinstance(text, str) or (authoritative and UNSAFE_CLAIM_RE.search(text)):
        return []
    claims = []
    for clause in re.split(r"[，,。；;！!\n]+", text):
        clause = re.sub(r"\s*了$", "", clause.strip().rstrip("."))
        clause = re.sub(r"[（(](?:原值|旧值|原为|原)?\s*([A-Za-z0-9_.:/+-]+)[）)]", r" \1", clause)
        withdrawn = RETRACT_RE.fullmatch(clause)
        match = withdrawn or CLAIM_RE.fullmatch(clause)
        if not match:
            continue
        key = claim_key(match["head"])
        if not key[1] or any(word in key[1] for word in ("不", "可能", "建议")):
            continue
        value = (match["value"] or "").rstrip(".")
        mode = ("retract" if withdrawn else "change" if match["old"] else
                "set" if match["set"] else "assert")
        if authoritative and mode == "assert" and is_correction(text):
            mode = "correction"
        claims.append({"key": key, "value": value, "mode": mode,
                       "text": clause, "old_value": "" if withdrawn else match["old"] or ""})
    return claims

# Reviewer routing is broader than the strict correction test used to authorize
# UPDATE. This only schedules an agent; it does not decide a fact.
DISSATISFACTION_RE = re.compile(
    r"(?:我之前|我早就|我明明|之前我).{0,50}(?:说过|讲过|告诉过|提过|强调过)|"
    r"(?:你又|你怎么|你是不是).{0,35}(?:忘了|记错|漏掉|没记住)|"
    r"(?:这|你).{0,35}(?:不对|错了|没按我说的|不是我说的)|"
    r"(?:记忆|记住|漏记|召回|检索).{0,35}(?:不满意|没用|不好|失败|错误|漏了|忘了)|"
    r"(?:不满意|很失望).{0,35}(?:记忆|记住|漏记|召回|检索)|"
    r"(?:I (?:already|previously) (?:said|told|explained)|"
    r"you (?:forgot|missed|misremembered) (?:what|that|my))",
    re.IGNORECASE)


def is_dissatisfaction(user_text: str) -> bool:
    """A scheduling hint, never evidence that the old memory is incorrect."""
    return bool(user_text) and (is_correction(user_text) or
        DISSATISFACTION_RE.search(user_text[:500]) is not None)


def is_correction(user_text: str) -> bool:
    return bool(user_text) and CORRECTION_RE.search(user_text[:80]) is not None


def scan_unit(user_text: str, assistant_text: str,
              new_entities: list[str] | tuple = ()) -> list[str]:
    """→ 命中的原因列表（可能为空 = 不抽取）。"""
    reasons: list[str] = []
    if is_correction(user_text):
        reasons.append("correction")
    both = (user_text or "") + "\n" + (assistant_text or "")
    if DECISION_RE.search(both):
        reasons.append("decision")
    if QUANT_RE.search(both):
        reasons.append("quant")
    if new_entities:
        reasons.append("new_entity")
    if len(assistant_text or "") >= LONG_TURN_CHARS:
        reasons.append("long_turn")
    return reasons
