"""来源 id 存在不够：正文必须在所引原文里有可核对片段。"""
from hybrid_memory.candgen.chat import ChatGenerator
from hybrid_memory.server import _content_grounded
from test_server import _service


def _close(svc):
    svc.stop_unit_recovery()
    svc.tasks.close()
    svc.log.close()


def test_existing_source_id_does_not_authenticate_unrelated_text():
    svc = _service()
    try:
        svc.observe("端口是多少", "8080")
        out = svc.propose([
            {"text": "部署在 B 服务器", "source_unit_ids": [0]},
            {"text": "端口是 8080", "source_unit_ids": [0]},
        ])
        assert out["accepted"] == 1
        assert out["rejected"] == [{"index": 0, "reason": "ungrounded_content"}]
        assert list(svc.engine.mems.values())[0].text == "端口是 8080"
        assert svc.engine.mems[out["new_ids"][0]].src == {0}
    finally:
        _close(svc)


def test_long_identifier_cannot_ride_on_a_real_span():
    svc = _service()
    try:
        svc.observe("端口是多少", "8080")
        out = svc.propose([{"text": "端口是 NOTAKEY9999", "source_unit_ids": [0]}])
        assert out["accepted"] == 0
        assert out["rejected"][0]["reason"] == "ungrounded_content"
        assert not svc.engine.mems
    finally:
        _close(svc)


def test_ungrounded_candgen_is_not_stored_as_window_memory():
    svc = _service(texts=())
    try:
        svc.generator = ChatGenerator(lambda *_: '{"memories":[{"text":"fact","source_unit_ids":[999]}]}')
        out = svc.observe("q", "a")
        assert out["candidates"] == 0 and not svc.engine.mems
        assert svc.n_ungrounded == 1
        assert "extract_due" not in svc.tasks.queued_counts()
    finally:
        _close(svc)


def test_grounding_rule_rejects_unverifiable_short_text():
    assert _content_grounded("端口", "问端口是多少") is True
    assert _content_grounded("ab", "ab") is False
    assert _content_grounded("8080", "端口 8080") is True
    assert _content_grounded("", "端口") is False
