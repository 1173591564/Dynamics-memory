"""最小智谱 chat 客户端（标准库 urllib）：reader / 未来的 LLM judge 共用。

cache_dir 非 None 时按 (model,system,user,temperature) 做 JSON 磁盘缓存，
实验重跑不再重复调远程。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# 智谱 OpenAI 兼容端点。ZAI_BASE_URL 可覆盖（代理 / 本地 mock / 其他兼容服务）
BASE_URL = os.environ.get("ZAI_BASE_URL",
                          "https://open.bigmodel.cn/api/paas/v4").rstrip("/")


class ZhipuChatError(RuntimeError):
    pass


def _post_chat(key: str, body: dict, timeout: float, max_retries: int) -> dict:
    """POST /chat/completions → choices[0].message（dict）。失败抛 ZhipuChatError。"""
    req = Request(f"{BASE_URL}/chat/completions",
                  data=json.dumps(body).encode("utf-8"), method="POST",
                  headers={"Content-Type": "application/json",
                           "Authorization": f"Bearer {key}"})
    raw = b""
    for attempt in range(max_retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            break
        except HTTPError as exc:
            if (exc.code == 429 or exc.code >= 500) and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise ZhipuChatError(f"HTTP {exc.code}") from exc
        except (URLError, TimeoutError, ConnectionError) as exc:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise ZhipuChatError(f"transport: {type(exc).__name__}") from exc
    try:
        msg = json.loads(raw)["choices"][0]["message"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ZhipuChatError("invalid chat response") from exc
    if not isinstance(msg, dict):
        raise ZhipuChatError("invalid chat response")
    return msg


def chat_messages(messages: list, *, tools: list | None = None,
                  api_key: str | None = None, model: str = "glm-5.3-flash",
                  timeout: float = 120.0, max_retries: int = 2,
                  temperature: float = 0.0) -> dict:
    """多轮 + function calling：返回 assistant message（可能带 tool_calls）。
    调查员回路用；不缓存（载荷含唯一 signal_id，缓存永不命中）。"""
    key = api_key or os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise ZhipuChatError("ZAI_API_KEY is not set")
    body = {"model": model, "messages": messages, "temperature": temperature}
    if tools:
        body["tools"] = tools
    return _post_chat(key, body, timeout, max_retries)


def _cache_lookup(cache_dir: Path, ck: str) -> str | None:
    try:
        out = json.loads((cache_dir / f"{ck}.json").read_text(encoding="utf-8"))["out"]
        return out if isinstance(out, str) else None
    except (ValueError, KeyError, TypeError, OSError):
        return None



def _cache_store(cache_dir: Path, ck: str, out: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=cache_dir, prefix=".chat-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"out": out}, f, ensure_ascii=False)
        os.replace(name, cache_dir / f"{ck}.json")
    finally:
        Path(name).unlink(missing_ok=True)


def chat(api_key: str | None = None, model: str = "glm-5.3-flash",
         system: str = "", user: str = "", timeout: float = 60.0,
         max_retries: int = 4, temperature: float = 0.0,
         cache_dir: Path | None = None) -> str:
    """单轮对话 → content 文本。失败抛 ZhipuChatError。"""
    key = api_key or os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise ZhipuChatError("ZAI_API_KEY is not set")
    ck = None
    if cache_dir is not None:
        raw = f"{model}\0{system}\0{user}\0{temperature}".encode("utf-8")
        ck = hashlib.sha256(raw).hexdigest()
        hit = _cache_lookup(cache_dir, ck)
        if hit is not None:
            return hit
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": user}]
    msg = _post_chat(key, {"model": model, "messages": msgs,
                           "temperature": temperature}, timeout, max_retries)
    out = msg.get("content")
    if not isinstance(out, str):
        raise ZhipuChatError("invalid chat response")
    out = out.strip()
    if cache_dir is not None and ck is not None:
        _cache_store(cache_dir, ck, out)
    return out
