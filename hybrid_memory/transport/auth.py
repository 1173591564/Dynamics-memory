"""HTTP 鉴权检查（P5 从 server.py 迁入）：bearer 统一校验。

H36 双 token：.memory-token 管读写，.human-review-token 管人审决定，
人审端点要求双 header（现状冻结）。token 文件的创建/0600 落在 service
侧（门面 __init__ 期创建；service 层不能反向依赖 transport），本模块只做
请求期的校验侧；0600 权限由 test_http_contract 断言。
"""
from __future__ import annotations

import secrets


def authorized(headers, token: str) -> bool:
    return secrets.compare_digest(
        (headers.get("Authorization") or "").encode("utf-8"),
        f"Bearer {token}".encode("utf-8"))
