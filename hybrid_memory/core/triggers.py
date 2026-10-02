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
