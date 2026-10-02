"""integration 命名空间(P4):把 tests/ 放入 sys.path,沿用旧测试的裸模块互引
(`from test_server import _service` 等);H38 再把 helper 收敛到 fakes。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
