"""凭据脱敏：`redact_secrets` 唯一实现（原 candgen/prompt.py，原样搬运）。"""
from __future__ import annotations

import re

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9][A-Za-z0-9_\-]{7,}|Bearer\s+[A-Za-z0-9._\-]{16,}|"
    r"api[_-]?key[\"'\s:=]+[A-Za-z0-9._\-]{16,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}|"
    r"(?:password|passwd|secret|token)[\"'\s:=]+[^\s\"']{8,}|"
    # PEM：BEGIN 到 END 整块脱（含密钥本体），END 缺失时至少盖住 BEGIN 行
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"(?:.*?-----END [A-Z ]*PRIVATE KEY-----)?)",
    re.IGNORECASE | re.DOTALL)


def redact_secrets(text: str) -> str:
    """输出层兜底：凭据模式替换为 [REDACTED]，事实陈述保留。"""
    return _SECRET_RE.sub("[REDACTED]", text)
