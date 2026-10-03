"""策略表（P3 通电，H7/H8/H25）：两套状态机收敛后的唯一策略存放处。

收敛说明（P3 只抄现状，不改语义）：
- claim_from：现状两机都是 (pending, ready)，如实记录，供未来 kind 收窄。
- on_exhausted：调查类 + trio 类 → dead；语义类 → requeue（H8）。
- max_attempts：调查类由 worker 调用参数持有（AgentWorker 配置），政策为 None；
  语义类现状无上限（无调用方传 max），政策为 None（H8 的 cap 待调优 PR 引入）；
  trio 类照抄 trio 当前硬编码 5（H8 上限见 KindPolicy）。
- lease_s：调查类由 worker 传入，政策为 None；语义/trio 类默认 120（旧 claim_semantic 默认值）。
- backoff：重试退避公式 `min(300, backoff ** min(8, attempts))` 的底数；
  语义/trio 类为 2.0（旧 retry_semantic 公式）；调查类调用方必传 delay，本值不用。
- daily_cap：调查 worker 持有，政策为 None。
未知 kind 调 policy_for → Fatal（配置错必须 loud；合法流只有 8 种 task kind，
'feedback'/capture 系是回执 kind，不进任务表）。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..errors import Fatal


@dataclass(frozen=True)
class KindPolicy:
    """一类任务的认领与重试策略（静态配置，不可变）。"""

    kinds: tuple[str, ...] = ()
    claim_from: tuple[str, ...] = ("pending", "ready")
    daily_cap: int | None = None
    max_attempts: int | None = None
    max_apply_attempts: int | None = None
    on_exhausted: str = "dead"      # dead | requeue
    lease_s: float | None = None
    backoff: float = 0.0


_INVESTIGATION = KindPolicy(
    kinds=("recall_miss", "extract_due"),
    claim_from=("pending", "ready"),
    daily_cap=None,                 # worker 调用参数持有
    max_attempts=3,                 # INV=3
    max_apply_attempts=3,
    on_exhausted="dead",            # H8：证据/输入问题，重试不改变输入
    lease_s=None,                   # worker 调用参数持有
    backoff=0.0,                    # 调用方必传 delay，本值不用
)

_SEMANTIC = KindPolicy(
    kinds=("conflict_pending", "feedback_pending", "maintenance_due"),
    claim_from=("pending", "ready"),
    daily_cap=None,
    max_attempts=None,              # H8 现状：模型重试无上限（或由调用方指定）
    max_apply_attempts=5,           # SEM=5 (N06)
    on_exhausted="requeue",         # H8：模型瞬时错误，输入依然有效
    lease_s=120.0,                  # 旧 claim_semantic 默认值
    backoff=2.0,                    # 旧 retry_semantic 公式底数
)

_WORKFLOW = KindPolicy(
    kinds=("hauler_due", "selector_due", "reviewer_due"),
    claim_from=("pending", "ready"),
    daily_cap=None,
    max_attempts=5,                 # WF=5 (N06)
    max_apply_attempts=5,
    on_exhausted="dead",            # H8：trio 类归调查类，耗尽即 dead
    lease_s=120.0,                  # 旧 claim_semantic 默认值
    backoff=2.0,                    # 旧 retry_semantic 公式底数
)

POLICIES: dict[str, KindPolicy] = {
    kind: policy
    for policy in (_INVESTIGATION, _SEMANTIC, _WORKFLOW)
    for kind in policy.kinds
}


def policy_for(kind: str) -> KindPolicy:
    """取某 kind 的策略；未知 kind 抛 Fatal（配置错必须 loud）。"""
    try:
        return POLICIES[kind]
    except KeyError:
        raise Fatal(f"unknown task kind: {kind}") from None


def assert_consumers(appliers) -> None:  # noqa: ANN001 — applier 类型 P5 定
    """启动自检（H25/A6/N42）：POLICIES 的每个 kind 必须在 appliers 有真实
    消费者，反向无野项（收据 kind 不是任务 kind，无硬编码豁免）。

    外部循环所有权由 runner 显式声明：dispatch 必须带 callable apply；
    legacy-agent/service 由外部循环消费，apply 可缺省（存在则必须 callable）；
    未知 runner 拒绝启动。"""
    missing = [kind for kind in POLICIES if kind not in appliers]
    if missing:
        raise Fatal(f"task kinds without consumers: {sorted(missing)}")
    wild = [kind for kind in appliers if kind not in POLICIES]
    if wild:
        raise Fatal(f"unknown applier kinds not in POLICIES: {sorted(wild)}")
    for kind, app in appliers.items():
        runner = getattr(app, "runner", None)
        apply_fn = getattr(app, "apply", None)
        if runner == "dispatch":
            if not callable(apply_fn):
                raise Fatal(f"dispatch applier for {kind} must be callable")
        elif runner in ("legacy-agent", "service"):
            # 外部循环所有权：apply 可缺省；存在则必须可调用
            if apply_fn is not None and not callable(apply_fn):
                raise Fatal(f"applier for {kind} has non-callable apply")
        elif callable(app):
            continue  # 裸函数 applier（非 Applier 包装）
        else:
            raise Fatal(f"applier for {kind} declares unknown runner: {runner!r}")
