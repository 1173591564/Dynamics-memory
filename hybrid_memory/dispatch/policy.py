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
    on_exhausted: str = "dead"      # dead | requeue（调查→dead，语义→requeue）
    lease_s: float | None = None
    backoff: float = 0.0


_INVESTIGATION = KindPolicy(
    kinds=("recall_miss", "extract_due"),
    claim_from=("pending", "ready"),
    daily_cap=None,                 # worker 调用参数持有
    max_attempts=None,              # worker 调用参数持有
    on_exhausted="dead",            # H8：证据/输入问题，重试不改变输入
    lease_s=None,                   # worker 调用参数持有
    backoff=0.0,                    # 调用方必传 delay，本值不用
)

_SEMANTIC = KindPolicy(
    kinds=("conflict_pending", "feedback_pending", "maintenance_due"),
    claim_from=("pending", "ready"),
    daily_cap=None,
    max_attempts=None,              # H8 现状：无调用方传 max，即无上限
    on_exhausted="requeue",         # H8：模型瞬时错误，输入依然有效
    lease_s=120.0,                  # 旧 claim_semantic 默认值
    backoff=2.0,                    # 旧 retry_semantic 公式底数
)

_WORKFLOW = KindPolicy(
    kinds=("hauler_due", "selector_due", "reviewer_due"),
    claim_from=("pending", "ready"),
    daily_cap=None,
    max_attempts=5,                 # 照抄 trio 当前硬编码（H8 上限见 KindPolicy）
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
    """启动自检（H25/A6）：POLICIES 的每个 kind 必须在 appliers 有消费者，否则 Fatal。"""
    missing = [kind for kind in POLICIES if kind not in appliers]
    if missing:
        raise Fatal(f"task kinds without consumers: {sorted(missing)}")
