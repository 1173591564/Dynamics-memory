"""启动声明：进程在不在，不等于数据已干净恢复或已经远程验证。"""
from pathlib import Path

from test_server import _http, _service


def _close(svc):
    svc.stop_unit_recovery()
    svc.tasks.close()
    svc.log.close()


def test_health_does_not_claim_remote_validation_and_retry_is_read_only(tmp_path):
    svc = _service(tmp_path, texts=())
    try:
        with _http(svc) as (_, get, _):
            status, health = get("/health")
            again = get("/health")
            assert status == 200 and health["ok"] is True
            assert health == again[1]
            assert health["validation"] == "unverified"
            assert health["validation"] not in ("remote", "l3", "L3")
            assert health["snapshot"] == "absent"
            assert health["units_pending"] == 0
            assert health["corrupt_file"] is False
        assert svc.log.count() == 0
        assert svc.save()["saved"] is True
        assert svc.health_view()["snapshot"] == "loaded"
    finally:
        _close(svc)


def test_pending_unit_is_visible_and_not_reported_done(tmp_path):
    svc = _service(tmp_path, texts=())
    try:
        svc.log.append_unit(0, user_text="以后统一用 bun", assistant_text="好的")
        with _http(svc) as (_, get, _):
            status, health = get("/health")
        assert status == 200 and health["ok"] is True
        assert health["units_pending"] == 1
        assert health["validation"] == "unverified"
        assert svc.log.work(0)["state"] == "pending"
    finally:
        _close(svc)


def test_quarantine_survives_restart_and_save_does_not_launder_it(tmp_path):
    (tmp_path / "state.pkl").write_bytes(b"broken snapshot")
    svc = _service(tmp_path, texts=())
    try:
        with _http(svc) as (_, get, _):
            status, health = get("/health")
            assert status == 200 and health["ok"] is True
            assert health["snapshot"] == "quarantined"
            assert health["corrupt_file"] is True
            assert health["validation"] == "unverified"
            assert not svc.engine.mems
        svc.save()
        with _http(svc) as (_, get, _):
            assert get("/health")[1]["snapshot"] == "quarantined"
    finally:
        _close(svc)
    assert (tmp_path / "state.corrupt").exists()
    # 不保存新快照时，重启不能把隔离显示成合法空目录。
    (tmp_path / "state.pkl").unlink()
    again = _service(tmp_path, texts=())
    try:
        view = again.health_view()
        assert view["ok"] is True
        assert view["snapshot"] == "quarantined"
        assert view["corrupt_file"] is True
        assert view["validation"] == "unverified"
        assert not again.engine.mems
    finally:
        _close(again)


def test_checkpoint_fault_does_not_become_a_validation_claim(tmp_path):
    svc = _service(tmp_path, texts=())
    try:
        svc._checkpoint_fault = True
        view = svc.health_view()
        assert view["ok"] is False
        assert view["checkpoint_fault"] is True
        assert view["validation"] == "unverified"
    finally:
        _close(svc)


def test_leftover_corrupt_file_does_not_override_a_successful_load(tmp_path):
    svc = _service(tmp_path, texts=())
    svc.save()
    _close(svc)
    (tmp_path / "state.corrupt").write_bytes(b"old failure")
    again = _service(tmp_path, texts=())
    try:
        view = again.health_view()
        assert view["ok"] is True
        assert view["snapshot"] == "loaded"
        assert view["corrupt_file"] is True
        assert again._snapshot_quarantined is False
    finally:
        _close(again)


def test_readme_does_not_advertise_a_stale_pass_count_or_remote_validation():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "302 passed" not in text
    assert "验证状态" in text and "运行" in text
    assert "不是远程验证" in text
    assert "L3" in text and "未做" in text
