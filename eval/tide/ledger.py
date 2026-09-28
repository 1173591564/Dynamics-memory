"""数据模型：事实账本、对话轮、探针、流。全部可 JSON 往返。

真值（facts / probes 的 gold / harmful / oracle_context）只在平台一侧使用，
永远不越过协议边界——被测系统只拿到 turns 里的文本和时间。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DIMENSIONS = ("R", "V", "P", "C", "F", "I")
DIM_NAMES = {
    "R": "保持（间隔 Δ 后仍能服务）",
    "V": "修订（多次更新后只服务现值）",
    "P": "传播（上游变更后派生值失效）",
    "C": "作用域（同主体多作用域取值）",
    "F": "卫生（撤回的内容不再服务）",
    "I": "抗干扰（相似事实数 m）",
}
KNOB_NAMES = {"R": "Δ(turn)", "V": "更新次数 k", "P": "依赖深度 d",
              "C": "作用域数 n", "F": "撤回后间隔", "I": "干扰数 m"}


@dataclass
class Fact:
    id: str
    subject: str
    scope: str                 # "" = 无作用域
    value: str                 # 唯一 token
    t_valid: list              # [start, end)；end=None 表示流结束时仍有效
    kind: str = "fact"         # fact / derived
    supersedes: str | None = None
    depends_on: str | None = None
    status: str = "valid"      # valid / superseded / retracted / invalidated


@dataclass
class Turn:
    t: int
    user: str
    assistant: str
    op: str = "filler"         # 生成用元数据（不发给被测系统）
    facts: list = field(default_factory=list)


@dataclass
class Probe:
    id: str
    t: int                     # 在 ingest 第 t 轮之前提问（已见 turns[0:t]）
    dimension: str
    knob: int
    query: str
    gold: list                 # 必须出现在上下文里的 token（空 = 无需支持）
    harmful: list              # 出现即有害的 token（失效值）
    oracle_context: str        # 理想最简上下文（Oracle 参照系统用）
    candidates: dict = field(default_factory=dict)  # 回答层闭集：token → 结果类别
    weight: float = 1.0


@dataclass
class Stream:
    id: str
    dimension: str
    seed: int
    turns: list
    probes: list
    facts: list

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Stream":
        return Stream(id=d["id"], dimension=d["dimension"], seed=d["seed"],
                      turns=[Turn(**x) for x in d["turns"]],
                      probes=[Probe(**x) for x in d["probes"]],
                      facts=[Fact(**x) for x in d["facts"]])


def save_streams(streams: list[Stream], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for s in streams:
        (out / f"{s.id}.json").write_text(
            json.dumps(s.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")


def load_streams(data_dir: str | Path) -> list[Stream]:
    files = sorted(Path(data_dir).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"{data_dir} 下没有流文件（先跑 python -m tide gen）")
    return [Stream.from_json(json.loads(f.read_text(encoding="utf-8"))) for f in files]
