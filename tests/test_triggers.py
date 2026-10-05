"""触发扫描：零 LLM 的确定性判断，宁可漏发也不把闲聊推给调查员。"""

import pytest


from hybrid_memory.triggers import LONG_TURN_CHARS, is_correction, scan_unit


@pytest.mark.parametrize("text", [
    "不对，我们后来把它移出去了",
    "不是的，端口是 8080",
    "你记错了，那是上周的事",
    "我说过不要用 pickle",
    "“错了”——应该是 B 服务器",
    "No, that's the old one",
    "Actually we switched to bun",
])
def test_correction_positive(text):
    assert is_correction(text)


@pytest.mark.parametrize("text", [
    "好的，谢谢",
    "这个不对称加密怎么实现",       # "不对" 出现在句中而非句首
    "帮我看看 handler.ts",
    "",
])
def test_correction_negative(text):
    assert not is_correction(text)


def test_scan_unit_reasons():
    assert scan_unit("以后统一用 bun 跑脚本", "好的") == ["decision"]
    assert scan_unit("截止 2026-10-01 上线", "收到") == ["quant"]
    assert scan_unit("看看这个", "嗯", new_entities=["handler.ts"]) == ["new_entity"]
    assert scan_unit("讲讲方案", "x" * (LONG_TURN_CHARS + 1)) == ["long_turn"]
    assert scan_unit("不对，改成 8 并发", "好") == ["correction", "decision", "quant"]


@pytest.mark.parametrize("text,mode", [
    ("网关模块的端口最新定为 gate-4200。", "set"),
    ("网关模块的端口目前是 gate-4200。", "assert"),
    ("日志级别设定（原值 trace-6100）已作废，暂不使用。", "retract")])
def test_real_model_temporal_and_parenthetical_claim_forms(text, mode):
    from hybrid_memory.core.triggers import claims_in
    claims = claims_in(text)
    assert len(claims) == 1
    assert claims[0]["key"][1] == ("日志级别" if mode == "retract" else "端口")
    assert claims[0]["mode"] == mode


def test_document_entity_is_not_mistaken_for_quoted_document_evidence():
    from hybrid_memory.core.triggers import claims_in
    declaration = claims_in("文档模块的输出目录改为 docs-7101。", authoritative=True)
    assert declaration and declaration[0]["key"] == ("文档模块", "输出目录")
    assert not claims_in("我引用文档：‘文档模块的输出目录改为 docs-7101’。", authoritative=True)


def test_scan_unit_chitchat_is_empty():
    assert scan_unit("在吗", "在的，有什么可以帮你") == []
    assert scan_unit("谢谢", "不客气") == []
