"""最小智谱 chat 客户端（标准库 urllib）：reader / 未来的 LLM judge 共用。

cache_dir 非 None 时按 (model,system,user,temperature) 做 JSONL 磁盘缓存，
实验重跑不再重复调远程。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ZhipuChatError(RuntimeError):
    pass


def _cache_lookup(cache_dir: Path, ck: str) -> str | None:
    path = cache_dir / f"{ck}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))["out"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None
    return None


def chat(api_key: str | None = None, model: str = "glm-5.3-flash",
         system: str = "", user: str = "", timeout: float = 60.0,
         max_retries: int = 2, temperature: float = 0.0,
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
    body = json.dumps({"model": model, "messages": msgs,
                       "temperature": temperature}).encode("utf-8")
    req = Request("https://open.bigmodel.cn/api/paas/v4/chat/completions",
                  data=body, method="POST",
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
        except (URLError, TimeoutError) as exc:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise ZhipuChatError(f"transport: {type(exc).__name__}") from exc
    try:
        out = json.loads(raw)["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ZhipuChatError("invalid chat response") from exc
    if cache_dir is not None and ck is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{ck}.json").write_text(
            json.dumps({"out": out}, ensure_ascii=False), encoding="utf-8")
    return out
