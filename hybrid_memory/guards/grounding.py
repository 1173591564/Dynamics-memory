"""正文接地校验（P4：content_grounded 通电；cited_text 随 propose 在 P5 落地）。"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable


def content_grounded(candidate_text, window_text: str) -> bool:
    """正文至少有一个可核对片段出现在所引原文中。

    可核对片段是连续两个汉字，或长度 ≥ 4 的 ASCII/数字串。长度 ≥ 8 的标识
    （脱敏占位 REDACTED 除外）必须全部出现，不能靠一个真片段夹带假标识。
    没有任何可核对片段时拒绝：无法区分空话和编造。

    P4 从 server 原样迁入（仅参数改名对齐 §2.8）。
    """
    if not isinstance(candidate_text, str) or not isinstance(window_text, str):
        return False
    prop = "".join(candidate_text.split())
    src = "".join(window_text.split())
    src_l = src.lower()
    matched = False
    for i in range(len(prop) - 1):
        a, b = prop[i], prop[i + 1]
        if "\u4e00" <= a <= "\u9fff" and "\u4e00" <= b <= "\u9fff" and prop[i:i + 2] in src:
            matched = True
            break
    # 标识按原文切分。先去空白会把 “handler.ts cannot” 粘成一个假长标识。
    tokens = re.findall(r"[A-Za-z0-9_]{4,}", candidate_text)
    long = [tok for tok in tokens if len(tok) >= 8 and tok.lower() != "redacted"]
    if any(tok.lower() not in src_l for tok in long):
        return False
    if any(tok.lower() in src_l for tok in tokens if tok.lower() != "redacted"):
        matched = True
    return matched


def cited_text(source_ids: Iterable[int],
               get_text: Callable[[int], str]) -> str:
    """取被引来源的正文拼窗（供 content_grounded 用）。"""
    raise NotImplementedError("guards.grounding.cited_text: P5 通电")
