"""调查员（investigator）：引擎信号 → 小载荷任务 → opencode agent 用工具
操作日志 → 严格 JSON 回报。

本模块只负责三件事，模型执行交给外部 agent：
  build_payload(signal, ctx)  把信号翻译成调查员的附件（< 1k tokens，
                              不含日志原文，只含问题/场景/已召回/线索/预算）
  parse_investigation(text)   解析并规整 agent 输出（提议/裁决/诊断），
                              形状不对的条目丢弃而不是让整批失败
  OpencodeInvestigator        把上面两步接到 OpencodeRunner：以
                              MEMORY_BRIDGE_ROLE=worker 拉起 opencode，插件
                              只注册工具、不挂捕获钩子（火墙）

调查员看不到引擎内部，只经工具面（/log/*、/search）和操作面（/propose、
/resolve、/diagnose）交互。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

from ..candgen.prompt import parse_ids, parse_salience
from ..llm import ZhipuChatError
from .opencode import OpencodeRunner

MISS_TYPES = ("not_in_window", "dropped_by_candgen", "too_coarse",
              "wrong_scene", "never_logged", "no_miss")
KINDS = ("work_fact", "work_task", "work_method", "work_artifact",
         "preference")
VERDICTS = ("synonym", "update", "contradiction", "collision", "pending")

INVESTIGATOR_SYS = """\
你是项目长期记忆的调查员。附件是引擎发来的一个信号，不是日志。
日志只能通过工具接触：先 log_search / log_timeline 定位，需要原文再 log_window
回展；回展总量不得超过附件 budget.window_chars，工具调用不超过 budget.tool_calls。
memory_search / memory_conflicts / memory_propose / memory_resolve / memory_diagnose
也计入同一份工具次数。收到 429 后不要重试工具，把尚未提交的产物放在最终 JSON；
最终 JSON 不额外消耗工具次数，但仍受原因果上界限制。工具已成功提交的条目不要重复提交。

任务按信号种类：
- recall_miss：记忆没接住问题 q。在 before=t 之前的日志里找能回答 q 的证据；
  找到 → 以 memory_propose 提交自包含的原子记忆；没找到 → diagnosis 说明。
  附件 retrieved 是当时已召回的记忆，不要重复提议同样内容。
- extract_due：unit_id 这轮交互命中了触发条件（reasons）。先对 entities 做
  log_timeline 看历史，再 log_window 回展该 unit，提取值得长期记住的事实/决策/
  待办/方法。若与已有记忆是新旧关系，在 proposal 里填 supersedes。

提议规则：
- 每条 text 独立完整（补全实体/时间/路径），只写你在工具结果里看到的事实；
- source_unit_ids 必须是你实际看过（search/timeline/window 返回过）的 unit；
- 绝不写入密钥/token 的具体值；不记录记忆系统自身的操作过程；
- kind ∈ work_fact | work_task | work_method | work_artifact | preference；
- salience 0–1：该记忆缺失时的预期下游损失。

诊断 miss_type ∈ not_in_window（答案在别的窗口）| dropped_by_candgen（同窗口
但被动抽取漏了）| too_coarse（有记忆但粒度不够）| wrong_scene（记忆归错场景）|
never_logged（日志里根本没有）| no_miss（问题本身无需记忆/闲聊）。

完成后只输出一个 JSON 对象，不要任何其他文字：
{"proposals":[{"text":"...","kind":"work_fact","salience":0.7,
  "source_unit_ids":[12],"entity_key":"可选","supersedes":[可选 memory id]}],
 "verdicts":[{"left":3,"right":9,"verdict":"update"}],
 "diagnosis":{"miss_type":"dropped_by_candgen","note":"一句话"}}"""

_CLI_INSTRUCTION = ("读取附件中的信号，按其中说明用工具调查日志并完成任务，"
                    "最后只输出 JSON 对象。")


@dataclass
class Budget:
    tool_calls: int = 8
    window_chars: int = 4000
    timeout_s: int = 300


@dataclass
class Investigation:
    proposals: list[dict] = field(default_factory=list)
    verdicts: list[tuple[int, int, str]] = field(default_factory=list)
    diagnosis: dict | None = None
    raw: str = ""


# ---------------------------------------------------------------- 载荷
def build_payload(signal, *, signal_id: str, t: int, scene: str,
                  budget: Budget, entity_hints: dict | None = None) -> dict:
    """信号 → 调查员附件。只放引擎已经知道的小信息 + 确定性线索。"""
    p = signal.payload if isinstance(signal.payload, dict) else {}
    base = {"signal_id": signal_id, "kind": signal.kind, "t": t,
            "before": t, "scene_now": scene,
            "budget": {"tool_calls": budget.tool_calls,
                       "window_chars": budget.window_chars}}
    if signal.kind == "recall_miss":
        base.update({
            "q": p.get("q", ""),
            "hints": p.get("hints", []),
            "sources": p.get("sources", []),
            "retrieved": p.get("retrieved", [])[:8],
            "entities": p.get("entities", []),
        })
    elif signal.kind == "extract_due":
        base.update({
            "unit_id": p.get("unit_id"),
            "reasons": p.get("reasons", []),
            "entities": p.get("entities", []),
            "scene": p.get("scene", ""),
        })
    if entity_hints:
        base["entity_mentions"] = entity_hints
    return base


# ---------------------------------------------------------------- 解析
def _first_json_object(text: str) -> dict | None:
    start = text.find("{")
    dec = json.JSONDecoder()
    while start != -1:
        try:
            obj, _ = dec.raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(obj, dict) and any(
                k in obj for k in ("proposals", "verdicts", "diagnosis")):
            return obj
        start = text.find("{", start + 1)
    return None


def parse_investigation(text: str) -> Investigation | None:
    """→ Investigation；找不到合法对象返回 None（调用方计失败）。
    单条形状不对只丢那一条。"""
    obj = _first_json_object(text or "")
    if obj is None:
        return None
    inv = Investigation(raw=text)
    proposals = obj.get("proposals")
    for item in proposals if isinstance(proposals, list) else []:
        if not isinstance(item, dict):
            continue
        txt = item.get("text", item.get("content"))
        if not isinstance(txt, str) or not txt.strip():
            continue
        src = parse_ids(item.get("source_unit_ids") or item.get("src") or [])
        kind = str(item.get("kind") or item.get("type") or "work_fact")
        if kind not in KINDS:
            kind = "work_fact"
        ek = item.get("entity_key")
        inv.proposals.append({
            "text": txt.strip(),
            "kind": kind,
            "salience": parse_salience(item.get("salience")),
            "source_unit_ids": src,
            "entity_key": ek.strip() if isinstance(ek, str) and ek.strip() else "",
            "supersedes": parse_ids(item.get("supersedes") or []),
        })
    verdicts = obj.get("verdicts")
    for item in verdicts if isinstance(verdicts, list) else []:
        if not isinstance(item, dict):
            continue
        pair = parse_ids([item.get("left"), item.get("right")])
        if len(pair) != 2:
            continue
        left, right = pair
        verdict = str(item.get("verdict", "")).strip().lower()
        if verdict in VERDICTS and left != right:
            inv.verdicts.append((left, right, verdict))
    diag = obj.get("diagnosis")
    if isinstance(diag, dict):
        mt = str(diag.get("miss_type", "")).strip()
        if mt in MISS_TYPES:
            note = diag.get("note", "")
            inv.diagnosis = {"miss_type": mt,
                             "note": note.strip()[:500]
                             if isinstance(note, str) else ""}
    return inv


# ---------------------------------------------------------------- 传输
class OpencodeInvestigator:
    """可调用对象：payload dict → Investigation | None（失败）。

    runner 可注入（测试）；默认以 pure=False 拉起 opencode，让插件加载并
    以 worker 角色只注册工具。每次调用把 signal_id 经 MEMORY_BRIDGE_SIGNAL
    传给插件，插件给每个请求带 X-Signal-Id——窗口预算按信号计量，不依赖
    LLM 记得传参。"""

    def __init__(self, *, port: int, token: str,
                 model: str = "zhipu-env/glm-5.3-flash",
                 runner: OpencodeRunner | None = None,
                 timeout_s: int = 300, env_extra: dict | None = None,
                 workdir=None):
        env = {"MEMORY_BRIDGE_ROLE": "worker",
               "MEMORY_BRIDGE_PORT": str(int(port)),
               "MEMORY_BRIDGE_TOKEN": token, **(env_extra or {})}
        self._runner = runner or OpencodeRunner(
            model=model, timeout_s=timeout_s, env_extra=env, pure=False,
            workdir=workdir)
        self.n_calls = 0
        self.n_failed = 0

    def __call__(self, payload: dict) -> Investigation | None:
        self.n_calls += 1
        user = json.dumps(payload, ensure_ascii=False, indent=1)
        try:
            out = self._runner.run(
                system=INVESTIGATOR_SYS, user=user,
                instruction=_CLI_INSTRUCTION, agent="investigator",
                env_extra={"MEMORY_BRIDGE_SIGNAL": str(payload.get("signal_id", ""))})
        except ZhipuChatError as exc:
            self.n_failed += 1
            if self.n_failed == 1:
                print(f"[investigator] opencode 调用失败（第 1 次）: {exc}",
                      file=sys.stderr, flush=True)
            return None
        inv = parse_investigation(out)
        if inv is None:
            self.n_failed += 1
        return inv
