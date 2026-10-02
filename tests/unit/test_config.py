"""Settings/resolve_settings/resolve_pipeline/load_env_key/cap_*（P2 新增，真实现）。"""
from __future__ import annotations

import pytest

from hybrid_memory.config import (Cfg, Settings, load_env_key,
                                  resolve_pipeline, resolve_settings)


def test_pool_caps_default():
    assert Cfg.cap_m == 40 and Cfg.cap_c == 200 and Cfg.cap_a == 2000


def test_settings_defaults_and_state_dir():
    s = resolve_settings([], {})
    assert s == Settings()
    assert s.state_dir.name == "memory"
    assert s.state_dir.parent.name == ".opencode"


def test_resolve_pipeline_matrix():
    assert resolve_pipeline({}) == "opencode"
    assert resolve_pipeline({"MEMORY_PIPELINE": "legacy"}) == "legacy"
    assert resolve_pipeline({"MEMORY_PIPELINE": "LEGACY"}) == "legacy"
    # 未知值沿用现状：非 legacy 即 opencode
    assert resolve_pipeline({"MEMORY_PIPELINE": "???"}) == "opencode"


def test_cli_beats_env_beats_default():
    s = resolve_settings(["--port", "9999", "--agent-model", "cli-model"],
                         {"MEMORY_AGENT_MODEL": "env-model",
                          "MEMORY_AGENT_DAILY_CAP": "7",
                          "MEMORY_PIPELINE": "legacy"})
    assert s.port == 9999
    assert s.agent_model == "cli-model"      # CLI 压过 env
    assert s.agent_daily_cap == 7            # env 压过默认
    assert s.pipeline == "legacy"
    assert s.model == "glm-5.3-flash"        # 默认


def test_no_agent_flag_and_env():
    assert resolve_settings(["--no-agent"], {}).no_agent is True
    assert resolve_settings([], {"MEMORY_AGENT": "off"}).no_agent is True
    assert resolve_settings([], {"MEMORY_AGENT": "ON"}).no_agent is False


def test_invalid_values_raise():
    with pytest.raises(ValueError):
        resolve_settings(["--task-queue-cap", "0"], {})
    with pytest.raises(ValueError):
        resolve_settings(["--agent-retry-delay", "-1"], {})
    with pytest.raises(ValueError):
        resolve_settings([], {"MEMORY_AGENT_DAILY_CAP": "abc"})


def test_load_env_key_prefers_process_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAI_API_KEY", "from-env")
    assert load_env_key(tmp_path) == "from-env"


def test_load_env_key_reads_project_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text('OTHER=1\nZAI_API_KEY="file-key"\n')
    assert load_env_key(tmp_path) == "file-key"


def test_load_env_key_missing_is_none(tmp_path, monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    assert load_env_key(tmp_path) is None
