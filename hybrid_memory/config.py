"""Cfg: 全部常数 + 功能开关收一处。engine 代码里不出现"消融"概念——
评测平台（TIDE，独立仓库）通过适配器传入具体 Cfg。

P2 新增 Settings（进程级配置）+ resolve_settings/resolve_pipeline/load_env_key：
只加不启用，旧调用一律不动（P5 通电）。
"""
from __future__ import annotations

import argparse
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cfg:
    # ---- 检索 ----
    k: int = 5                   # top-K
    theta: float = 0.35          # 质量门 s(m,q) 下限
    tau_dup: float = 0.90        # 压制/合并阈值
    tau_sim: float = 0.80        # 软冗余带
    pi_m: float = 0.05           # M 池先验（π_C=0 基准）
    pi_a: float = -0.30          # 归档参与分（负先验，只在没更好候选时浮出）
    fresh_alpha: float = 0.10    # 新鲜度探索项强度
    shortlist_n: int = 30        # ANN shortlist 大小
    lex_weight: float = 0.0      # >0 → s = cos + w·lex（词法加分，稀有词门控）

    # ---- 动力学 ----
    lam: float = 0.02            # 衰减率/步
    eta: float = 0.30            # useful-hit 强化
    eta_shadow: float = 0.10     # shadow-hit 部分增益
    v_init: float = 0.50         # 新候选初始 V
    theta_p: float = 1.50        # 晋升阈值
    theta_d: float = 0.80        # 降级阈值（滞回 θ_p>θ_d）
    idle_p: int = 50             # C 池闲置步数 → archive
    cap_m: int = 40              # M 池容量
    cap_c: int = 200             # C 池容量（P2 新增，未启用；H11/H12）
    cap_a: int = 2000            # A 池容量（P2 新增，未启用；H11/H12）
    eta_c: float = 0.60          # merge 继承折损
    tension_delay: int = 20

    # ---- 机制开关（评测消融用） ----
    two_pool: bool = True        # False → 单层：全在 M，无 π 差无滞回
    shadow_credit: bool = True   # False → shadow 不计增益
    ingest_dedup: bool = True    # False → 新候选全部独立成条
    useful_hit: bool = True      # False → 入选即强化（无相关性判据时如实记账）
    defer_credit: bool = False   # True → 检索不结清，等 feedback(answer) 后
                                 # recognizer 判定哪些记忆真被用上才发 d_hit
    confidence_on: bool = False
    conf_prior_alpha: float = 1.0
    conf_prior_beta: float = 1.0
    conf_write_evidence: float = 1.0
    conf_confirm_evidence: float = 1.0
    conf_negative_evidence: float = 1.0
    conf_half_life: float = 50.0
    theta_conf: float = 0.62
    provisional_margin: float = 0.08
    provisional_k: int = 1
    salience_on: bool = False
    salience_default: float = 0.5
    salience_retention_floor: float = 0.5
    salience_retention_weight: float = 3.0
    novelty_on: bool = False
    novelty_bonus: float = 0.25
    consolidation_on: bool = False
    consolidation_salience_budget: float = 6.0
    consolidation_min_items: int = 5
    consolidation_max_items: int = 12
    signal_queue_cap: int = 256   # 引擎→LLM 信号队列容量（超限丢最旧+计数）
    shadow_pending_cap: int = 256  # 延迟记账待结算队列容量（超限丢最旧+计数）
    capacity_on: bool = True     # False → M 池无界
    suppression_on: bool = True
    tension_on: bool = True
    archive_retrieval: bool = True

    # ---- 衔尾蛇：recall_miss 的信号源 ----
    # 纠正检测（用户开口就在纠正）与 agent 工具痕迹（主 agent 自己去查了
    # 日志）恒开——精度高。recognizer 回 NONE 精度低（闲聊也是 NONE），
    # 每次都要花一次调查员调用，默认关；拿到 miss_type 分布证据后再定。
    miss_on_recognizer_none: bool = False


@dataclass(frozen=True)
class Settings:
    """进程级配置（§2 config）。经 `resolve_settings` 构造；不可变。"""

    project: str = "."
    port: int = 17872
    model: str = "glm-5.3-flash"
    pipeline: str = "opencode"      # resolve_pipeline 结果：opencode | legacy
    task_capacity: int = 4096
    no_agent: bool = False
    agent_model: str = "glm-5.3-flash"
    agent_daily_cap: int = 200
    agent_tool_calls: int = 8
    agent_window_chars: int = 4000
    agent_retry_delay: float = 2.0

    @property
    def state_dir(self) -> Path:
        """派生：<project>/.opencode/memory（与 server.build 默认一致）。"""
        return Path(self.project) / ".opencode" / "memory"


def resolve_pipeline(env: Mapping[str, str] | None = None) -> str:
    """唯一读 `MEMORY_PIPELINE` 的地方（I2）。未知值沿用现状：非 legacy 即 opencode。"""
    source = os.environ if env is None else env
    return ("legacy" if source.get("MEMORY_PIPELINE", "opencode").lower() == "legacy"
            else "opencode")


def resolve_settings(argv: list[str] | None = None,
                     env: Mapping[str, str] | None = None) -> Settings:
    """CLI > env > 默认，唯一解析点；argv/env 为 None 时才读进程状态（import 时不求值）。

    与 `server.main()` 的 argparse 保持数值一致（含环境变量名与非法值语义）；
    非法值抛 ValueError（P5 bootstrap 转 argparse error）。P2 不通电。
    """
    source = os.environ if env is None else env
    ap = argparse.ArgumentParser(prog="memory-sidecar")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--agent-model", default=None)
    ap.add_argument("--no-agent", action="store_true", default=None)
    ap.add_argument("--agent-daily-cap", type=int, default=None)
    ap.add_argument("--agent-tool-calls", type=int, default=None)
    ap.add_argument("--agent-window-chars", type=int, default=None)
    ap.add_argument("--task-queue-cap", type=int, default=None)
    ap.add_argument("--agent-retry-delay", type=float, default=None)
    args = ap.parse_args(argv)
    dflt = Settings()

    def pick(cli, env_key: str | None, cast, default):
        if cli is not None:
            return cli
        if env_key is not None and source.get(env_key) is not None:
            return cast(source[env_key])
        return default

    no_agent = args.no_agent
    if no_agent is None:
        no_agent = source.get("MEMORY_AGENT", "").lower() in ("off", "0", "false")
    task_capacity = pick(args.task_queue_cap, None, int, dflt.task_capacity)
    if task_capacity < 1:
        raise ValueError("--task-queue-cap must be positive")
    retry_delay = pick(args.agent_retry_delay, None, float, dflt.agent_retry_delay)
    if not math.isfinite(retry_delay) or retry_delay < 0:
        raise ValueError("--agent-retry-delay must be finite and non-negative")
    return Settings(
        project=pick(args.project, None, str, dflt.project),
        port=pick(args.port, None, int, dflt.port),
        model=pick(args.model, None, str, dflt.model),
        pipeline=resolve_pipeline(source),
        task_capacity=task_capacity,
        no_agent=no_agent,
        agent_model=pick(args.agent_model, "MEMORY_AGENT_MODEL", str,
                         dflt.agent_model),
        agent_daily_cap=pick(args.agent_daily_cap, "MEMORY_AGENT_DAILY_CAP", int,
                             dflt.agent_daily_cap),
        agent_tool_calls=pick(args.agent_tool_calls, None, int,
                              dflt.agent_tool_calls),
        agent_window_chars=pick(args.agent_window_chars, None, int,
                                dflt.agent_window_chars),
        agent_retry_delay=retry_delay,
    )


def load_env_key(project_dir: str | Path) -> str | None:
    """`.env` 读取（与 `server._load_env_key` 同逻辑的 canonical 版；P5 替换旧调用）。

    顺序：进程环境 `ZAI_API_KEY` → `<project>/.env` → 仓库根 `.env`。
    """
    key = os.environ.get("ZAI_API_KEY")
    if key:
        return key
    for env_file in (Path(project_dir) / ".env",
                     Path(__file__).resolve().parents[1] / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ZAI_API_KEY="):
                    val = (line.split("=", 1)[1].strip()
                           .strip('"').strip("'"))
                    if val:
                        return val
    return None
