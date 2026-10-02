"""共享 pytest 夹具（P2 先行）。

旧测试文件的局部 helper（`_service`/`_http`/`_fake` 等）在 H38 重组时再迁入；
此处只放新架构测试的共享底座：仓库根定位。
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
