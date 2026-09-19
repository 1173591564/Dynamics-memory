"""LLM 裁决 + response-level recognizer：RealChatSemantics 的在线裁判版。

judge 四级：verbatim → 人工标注文件 → LLM 判 → 失败回落 "pending"。
relevant_set：一条调用判一组入选记忆哪些真被答案用上（useful-hit 真值）。
chat_fn 可注入（测试用）；默认走 llm.chat（磁盘缓存，重跑免费）。
"""
from __future__ import annotations

import re
from pathlib import Path

from ..candgen.prompt import redact_secrets
from ..core.types import Event
from ..llm import ZhipuChatError, chat
from .real import RealChatSemantics, VERDICTS, normalize

_JUDGE_SYS = (
    "你是记忆冲突裁判。给你两条关于同一项目长期记忆的文本 A 和 B，"
    "判定它们的关系，只回一个词：\n"
    "synonym —— 同一事实的换措辞/子集关系，保留一条即可；\n"
    "update —— 同一事物的新旧状态，后发生的取代先发生的（如新待办取代旧待办、"
    "方案从A改成B）；\n"
    "contradiction —— 同一事物上说法冲突且不是新旧更替（可能各自有条件的对，"
    "或一方就是错的）；\n"
    "collision —— 只是碰巧像，讲的是不同的事，两条都该留。\n"
    "只回这四个词之一，不要解释。")

_RECOG_SYS = (
    "你是记忆贡献归因器。给你用户问题、助手回答，以及编号 1..N 的注入记忆。"
    "返回支撑该回答的最小充分记忆集合。只有当回答中的具体主张由某条记忆直接支持，"
    "且仅凭用户问题本身不能得到时，才算该记忆被用上。主题相似、仅作背景、"
    "回答未采用其信息，均不算；多条重复时只选提供该信息所需的最少条目。"
    "只回编号，逗号分隔；一条都没用上回 NONE。不要解释。")

_CONSOLIDATE_SYS = (
    "你是项目长期记忆的巩固器。输入是一组按时间标注、已经单独入库的记忆。"
    "仅从这些输入综合出一条更高层的‘当前项目状态’记忆，用于新会话续接。"
    "必须：1) 区分已完成、当前进行中、未解决阻塞和长期约束；"
    "2) 保留会改变行动的编号、数量、截止时间和专名；"
    "3) 若输入含不同时间状态，以最新状态为当前状态并明确旧状态已被取代；"
    "4) 不补充输入外事实；5) 不复制零散过程。"
    "如果这些记忆无法形成一个连贯的项目状态，输出 NONE。"
    "否则只输出一条自包含陈述，不要标题、列表、解释或 JSON。")


def _one_word(out: str) -> str:
    w = re.findall(r"[a-zA-Z]+", out.lower())
    for x in w:
        if x in VERDICTS:
            return x
    return "pending"


def _index_set(out: str, n: int) -> list[bool] | None:
    """解析 "1,3" / "NONE" → bool 列表；解析失败返回 None。"""
    s = out.strip().lower()
    if s == "none" or not s:
        return [False] * n if s == "none" else None
    idx = set()
    for tok in re.findall(r"\d+", s):
        i = int(tok)
        if 1 <= i <= n:
            idx.add(i - 1)
    return [i in idx for i in range(n)] if idx else None


class LLMSemantics(RealChatSemantics):
    def __init__(self, labels_path: str | Path | None = None,
                 chat_fn=None, model: str = "glm-5.3-flash",
                 cache_dir: Path | None = None,
                 api_key: str | None = None):
        super().__init__(labels_path)
        self._fn = chat_fn
        self._model = model
        self._cache = cache_dir
        self._api_key = api_key

    def _chat(self, system: str, user: str) -> str:
        if self._fn is not None:
            return self._fn(system, user)
        return chat(api_key=self._api_key, model=self._model,
                    system=system, user=user, cache_dir=self._cache)

    def judge(self, a_bid: int, a_val: str, b_bid: int, b_val: str) -> str:
        v = super().judge(a_bid, a_val, b_bid, b_val)
        if v != "pending":
            return v
        try:
            return _one_word(self._chat(_JUDGE_SYS, f"A: {a_val}\nB: {b_val}"))
        except ZhipuChatError:
            return "pending"

    def relevant_set(self, texts: list[str], question: str,
                     answer: str) -> list[bool] | None:
        """返回 None = 识别失败（传输错误或输出不可解析）。worker 据此
        计数并退化 selected-hit——失败必须外显，不能静默全记。"""
        mems = "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))
        try:
            out = self._chat(_RECOG_SYS,
                             f"用户问题: {question}\n助手回答: {answer}\n"
                             f"注入记忆:\n{mems}")
        except ZhipuChatError:
            return None
        return _index_set(out, len(texts))

    def consolidate(self, memories, t: int) -> Event | None:
        """巩固回调：按时间标注的记忆 → 一条高层状态 Event；失败/NONE → None。"""
        user = "\n".join(
            f"[memory_id={m.id} | t={m.birth} | scene={m.scene or '未标注'}]"
            f" {m.text}" for m in memories)
        try:
            out = self._chat(_CONSOLIDATE_SYS, user).strip()
        except ZhipuChatError:
            return None
        if not out or out.lower() == "none":
            return None
        text = redact_secrets(out)
        return Event(
            belief_id=self.fingerprint(text), value=normalize(text),
            text=text,
            src=tuple(sorted(frozenset().union(
                *(m.src for m in memories)))),
            salience=max(m.salience for m in memories),
            kind="reflection",
            derived_from=tuple(m.id for m in memories),
            conf_pos=min(m.conf_pos for m in memories),
            conf_neg=max(m.conf_neg for m in memories),
            scene=memories[0].scene)
