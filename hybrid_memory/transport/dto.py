"""HTTP 请求解析（P5 从 server.py 原样迁入）：错误/路径表/字段/载荷。

请求身份（request_id 指纹）复用 guards/bounds 的原语，不重复实现。
"""
from __future__ import annotations

import json

from ..guards.bounds import validate_request_id as _validate_request_id


class HttpError(Exception):
    """HTTP 层可预见错误：状态码 + 机器 code（N42，回包必带 code）。"""

    def __init__(self, code: int, msg: str, mcode: str = "bad_request"):
        super().__init__(msg)
        self.code = code
        self.mcode = mcode


SIGNAL_PATHS = {"/recall", "/search", "/conflicts", "/resolve", "/propose",
                "/diagnose", "/log/search", "/log/timeline", "/log/stats", "/log/window"}

MAX_BODY = 4 * 1024 * 1024          # 请求体上限 4MiB
GET_PATHS = {"/recall", "/conflicts", "/signals"}   # /health 单列免鉴权
POST_PATHS = {"/observe", "/feedback", "/resolve", "/human-reviews", "/human-review", "/search", "/save",
              "/miss", "/log/search", "/log/timeline", "/log/stats",
              "/log/window", "/propose", "/diagnose"}


def opt_int(body: dict, key: str, *, positive: bool = False):
    v = body.get(key)
    if v is None:
        return None
    if type(v) is not int or not -(2**63) <= v < 2**63:
        raise HttpError(400, f"{key} must be a 64-bit int")
    if positive and v <= 0:
        raise HttpError(400, f"{key} must be positive")
    return v


def req_str(body: dict, key: str) -> str:
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise HttpError(400, f"{key} required")
    return v


def parse_body(headers, rfile) -> dict:
    ct = (headers.get("Content-Type") or "").split(";")[0].strip()
    if ct != "application/json":
        raise HttpError(415, "Content-Type must be application/json", "unsupported_media_type")
    try:
        n = int(headers.get("Content-Length") or 0)
    except ValueError:
        raise HttpError(400, "bad Content-Length")
    if n < 0:
        raise HttpError(400, "bad Content-Length")
    if n > MAX_BODY:
        raise HttpError(413, "body too large", "payload_too_large")
    if not n:
        return {}
    try:
        body = json.loads(rfile.read(n).decode("utf-8"))
    except ValueError:
        raise HttpError(400, "malformed JSON body")
    if not isinstance(body, dict):
        raise HttpError(400, "body must be a JSON object")
    return body


def capture_request_id(headers, body: dict) -> str | None:
    header = headers.get("X-Request-Id")
    if header is not None:
        header = header.strip()
    if header == "":
        raise HttpError(400, "X-Request-Id must not be empty")
    if "request_id" in body and not isinstance(body.get("request_id"), str):
        raise HttpError(400, "request_id must be a string")
    body_id = body.get("request_id")
    if body_id == "":
        raise HttpError(400, "request_id must not be empty")
    if header and body_id and header != body_id:
        raise HttpError(400, "X-Request-Id and request_id disagree")
    chosen = body_id or header or None
    if chosen is None:
        return None
    try:
        return _validate_request_id(chosen)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc


def observe_payload(body: dict, headers) -> dict:
    user = body.get("user_text", "")
    assistant = body.get("assistant_text", "")
    if not isinstance(user, str) or not isinstance(assistant, str):
        raise HttpError(400, "user_text/assistant_text must be strings")
    if not user.strip() and not assistant.strip():
        raise HttpError(400, "empty turn")
    return {"user_text": user, "assistant_text": assistant,
            "request_id": capture_request_id(headers, body)}


def feedback_payload(body: dict, headers) -> dict:
    rid = opt_int(body, "retrieval_id")
    if rid is None:
        raise HttpError(400, "retrieval_id required")
    question, answer = body.get("question", ""), body.get("answer", "")
    if not isinstance(question, str) or not isinstance(answer, str):
        raise HttpError(400, "question/answer must be strings")
    return {"retrieval_id": rid, "question": question, "answer": answer,
            "request_id": capture_request_id(headers, body)}
