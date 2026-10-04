"""HTTP 稳定错误码与收据类型分离回归（P0-2 / N42）。

覆盖：
- 所有 HTTP 错误响应带机器 code；源码中出现的每个 code 都注册在
  errors._STATUS（无 KeyError→500 兜底）；扫描器对伪造违规样本必须拒绝
  （负向探针）；
- feedback 重复 → 409 + code="already_credited"（与 memory-bridge.ts 的
  `r.data?.code === "already_credited"` 检查一致）；
- 收据 kind 与任务 kind 分离：EFFECTS 表不再含 "feedback"（零消费者的
  硬编码豁免删除）；assert_consumers 真 callable 检查、无恒真死分支、
  显式外部循环所有权（legacy-agent/service runner 声明）。
"""
from __future__ import annotations

import re

import pytest

from hybrid_memory.dispatch import effects, policy
from hybrid_memory.errors import _STATUS
from hybrid_memory.errors import Fatal


# ------------------------------------------------------- 错误码全量注册

_CODE_PATTERNS = [
    re.compile(r'code="([a-z_]+)"'),                 # HttpError(..., code="x")
    re.compile(r'"code": "([a-z_]+)"'),              # 字面量回包
    re.compile(r'\{"error": str\(exc\), "code": "([a-z_]+)"\)'),
]


def scan_codes(source: str) -> list[str]:
    """扫描源码文本中的错误码字面量（供负向探针复用）。"""
    out: set[str] = set()
    for pat in _CODE_PATTERNS:
        out.update(pat.findall(source))
    return sorted(out)


def test_all_http_codes_in_status():
    from pathlib import Path
    import hybrid_memory
    root = Path(hybrid_memory.__file__).parent
    files = ["transport/http.py", "transport/dto.py", "service/feedback.py"]
    bad = {}
    for rel in files:
        codes = scan_codes((root / rel).read_text(encoding="utf-8"))
        unregistered = [c for c in codes if c not in _STATUS]
        if unregistered:
            bad[rel] = unregistered
    assert not bad, f"未注册错误码（会 KeyError→500 或对不上插件）: {bad}"


def test_code_scanner_rejects_fake_violation():
    """负向探针：伪造未注册 code 的源码样本，扫描器必须抓到。"""
    fake = 'raise HttpError(409, "x", code="definitely_not_registered")'
    codes = scan_codes(fake)
    assert "definitely_not_registered" in codes
    assert "definitely_not_registered" not in _STATUS


def test_feedback_duplicate_gives_already_credited_code(tmp_path):
    from test_server import _http, _service
    svc = _service(tmp_path)
    try:
        svc.observe("部署在哪", "已改到 B 服务器")
        rid = svc.recall("部署在哪")["retrieval_id"]
        with _http(svc) as (post, get, _):
            first = post("/feedback", {"retrieval_id": rid,
                                       "question": "部署在哪",
                                       "answer": "B 服务器"})
            assert first[0] == 200
            status, body = post("/feedback", {"retrieval_id": rid,
                                              "question": "部署在哪",
                                              "answer": "B 服务器"})
            assert status == 409
            assert body["code"] == "already_credited", \
                "与 memory-bridge.ts 的 code 检查保持一致"
            assert "already" in body["error"]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_receipt_kind_separated_from_task_kinds():
    """收据 kind（feedback）不再是任务 kind：EFFECTS 无该键。"""
    assert "feedback" not in effects.EFFECTS
    assert set(effects.EFFECTS) == set(policy.POLICIES), \
        "任务面 = POLICIES ∪ EFFECTS 逐一对齐，无豁免"


def test_assert_consumers_no_hardcoded_exemption():
    """多余 kind 必须拒绝——即便它叫 feedback（豁免已删）。"""
    fake = dict(effects.EFFECTS)
    fake["feedback"] = effects.Applier("feedback", "service")
    with pytest.raises(Fatal, match="unknown applier kinds"):
        policy.assert_consumers(fake)


def test_assert_consumers_callable_and_ownership():
    from collections import namedtuple
    # dispatch applier：apply 必须 callable（真检查，非 hasattr 恒真）
    broken = dict(effects.EFFECTS)
    broken["hauler_due"] = effects.Applier("hauler_due", "dispatch", None)
    with pytest.raises(Fatal, match="callable"):
        policy.assert_consumers(broken)
    # 外部循环所有权显式声明：legacy-agent/service 无 apply 合法
    ext = dict(effects.EFFECTS)
    ext["recall_miss"] = effects.Applier("recall_miss", "legacy-agent")
    ext["feedback_pending"] = effects.Applier("feedback_pending", "service")
    policy.assert_consumers(ext)
    # 未知 runner 拒绝启动（原实现恒真死分支放行）
    bogus = dict(effects.EFFECTS)
    bogus["hauler_due"] = effects.Applier("hauler_due", "mystery-loop")
    with pytest.raises(Fatal, match="unknown runner"):
        policy.assert_consumers(bogus)
    # 非 Applier 对象也必须被 callable 检查覆盖（原 elif 死分支放行）
    notcall = dict(effects.EFFECTS)
    notcall["hauler_due"] = object()
    with pytest.raises(Fatal):
        policy.assert_consumers(notcall)


def test_checkpoint_over_budget_code_registered():
    """N49/PENDING-09：预算闸 code 必须有 _STATUS 映射（章程 N46 规则）。"""
    from hybrid_memory.errors import http_status
    assert http_status("checkpoint_over_budget") == 503
