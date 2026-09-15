"""真实数据 MemorySemantics：无 ground truth，裁判 = verbatim 规则 + 人工标注文件。

belief_id 被复用为规范化文本的指纹（crc32）：同一规范文本 → 同 belief_id。
judge 三级：
  1. 规范化文本相等 → "synonym"（verbatim 去重，安全自动）
  2. 人工标注文件命中 → 返回标注 verdict
  3. 未标注 → "pending"：ingest 视为非同义（新增候选 + tension），
     maintenance 把该 tension 留在 backlog 等标注。

relevant/valid 无真值可用：relevant 恒 True（信用退化为 selected-hit，
需配 cfg.useful_hit=False 如实记账）；valid 恒 True；scope 恒 ""，
故人工标 "contradiction" 时走同 scope 双方降权路径。
"""
from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[。！？!?,，.;；:：\"'“”‘’、()\[\]（）\-~]")

VERDICTS = {"synonym", "update", "contradiction", "collision"}


def normalize(text: str) -> str:
    return _PUNCT.sub("", _WS.sub("", text)).lower()


class RealChatSemantics:
    """labels_path 指向 JSONL：{"a": textA, "b": textB, "verdict": ...}。
    无文件/未命中 → pending。"""

    def __init__(self, labels_path: str | Path | None = None):
        self.labels: dict[tuple[str, str], str] = {}
        if labels_path and Path(labels_path).exists():
            for line in Path(labels_path).read_text(
                    encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                v = row.get("verdict")
                a, b = normalize(row.get("a", "")), normalize(row.get("b", ""))
                if v in VERDICTS and a and b and a != b:
                    self.labels[tuple(sorted((a, b)))] = v

    @staticmethod
    def fingerprint(text: str) -> int:
        return zlib.crc32(normalize(text).encode("utf-8"))

    # ---- MemorySemantics ----
    def judge(self, a_bid: int, a_val: str, b_bid: int, b_val: str) -> str:
        if a_val == b_val:
            return "synonym"
        return self.labels.get(tuple(sorted((a_val, b_val))), "pending")

    def relevant(self, belief_id: int, value: str, query, t: int) -> bool:
        return True

    def valid(self, belief_id: int, value: str, t: int) -> bool:
        return True

    def embedding_key(self, belief_id: int, value: str) -> tuple:
        return (value,)

    def scope(self, belief_id: int) -> str:
        return ""
