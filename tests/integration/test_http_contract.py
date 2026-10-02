"""HTTP 契约（P5 新增）：ROUTES/方法表一致性 + shim 身份 + H36 双 token 0600。"""
import os
import stat
import urllib.request

import pytest

from hybrid_memory import server as shim
from hybrid_memory.service.service import MemoryService
from hybrid_memory.transport import auth, bootstrap, dto
from hybrid_memory.transport.dto import HttpError
from hybrid_memory.transport.http import TRIO_DISABLED, Handler, ROUTES, serve
from test_server import _http, _service


def test_routes_cover_method_tables():
    assert set(ROUTES) == dto.GET_PATHS | dto.POST_PATHS | {"/health"}
    for path, name in ROUTES.items():
        assert callable(getattr(Handler, name, None)), path
    assert set(TRIO_DISABLED) <= set(ROUTES)


def test_shim_reexports_canonical():
    assert shim.MemoryService is MemoryService
    assert shim.serve is serve
    assert shim.main is bootstrap.main


def test_auth_bearer():
    assert auth.authorized({"Authorization": "Bearer abc"}, "abc") is True
    assert auth.authorized({"Authorization": "Bearer abc"}, "abd") is False
    assert auth.authorized({}, "abc") is False


def test_dto_observe_rejects_empty_turn():
    with pytest.raises(HttpError) as err:
        dto.observe_payload({"user_text": " ", "assistant_text": ""}, {})
    assert err.value.code == 400


def test_token_files_are_0600(tmp_path):
    if os.name != "posix":
        pytest.skip("0600 仅 POSIX 有意义")
    svc = _service(tmp_path)
    assert svc.human_review_token
    for name in (".memory-token", ".human-review-token"):
        mode = stat.S_IMODE(os.stat(tmp_path / name).st_mode)
        assert mode == 0o600, (name, oct(mode))


def test_live_health_open_and_recall_guarded(tmp_path):
    svc = _service(tmp_path)
    with _http(svc) as (post, get, httpd):
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        with urllib.request.urlopen(base + "/health", timeout=10) as r:
            assert r.status == 200
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + "/recall?q=x", timeout=10)
        assert err.value.code == 401
        err.value.close()
        assert post("/save", {})[0] == 200
