"""离线 Mock：模拟智谱 bigmodel.cn 的 /embeddings 与 /chat/completions。

目的：没有 ZAI_API_KEY 时也能把 sidecar 的**真实代码路径**（HTTP 客户端、
缓存、解析、worker、信号、持久化）完整跑一遍。输出是规则生成的，
不代表真实 LLM 质量——只验证"管道通不通"。

- embeddings：本地 bge-small-zh-v1.5（fastembed），补零到 2048 维
- chat：按 system prompt 识别角色
    candgen     → 从 assistant 回复里抽"承重句"（含数字/决定/改为/阻塞等）
    judge       → 同实体不同数字 → update；高度重合 → synonym；否则 collision
    recognizer  → 与答案 token 重合度高的记忆编号
    consolidate → NONE
- 也支持 OpenAI 兼容流式（stream=true）以便给 opencode 用（纯文本回复）
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

DIM = 2048
STATS = {"embed_calls": 0, "embed_texts": 0, "chat": {}}
_LOCK = threading.Lock()


def _toks(text: str) -> list[str]:
    t = text.lower()
    out = re.findall(r"[a-z0-9_#.+-]{2,}", t)
    for run in re.findall(r"[一-鿿]+", t):
        out += [run[i:i + 2] for i in range(len(run) - 1)] or [run]
    return out


_BGE = None


def embed_batch(texts):
    """真实本地中文向量模型 bge-small-zh-v1.5（512 维，补零到 2048，余弦不变）。
    装不上 fastembed 时退化为哈希词袋。"""
    global _BGE
    try:
        if _BGE is None:
            from fastembed import TextEmbedding
            _BGE = TextEmbedding("BAAI/bge-small-zh-v1.5")
        out = []
        for v in _BGE.embed(list(texts)):
            pad = np.zeros(DIM)
            pad[:len(v)] = v
            out.append(pad.tolist())
        return out
    except ImportError:
        return [embed(t) for t in texts]


def embed(text: str) -> list[float]:
    v = np.zeros(DIM)
    for tok in _toks(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0 if (h >> 12) & 1 else -1.0
        v[(h >> 20) % DIM] += 0.5
    n = np.linalg.norm(v)
    if n == 0:
        v[0] = 1.0
        n = 1.0
    return (v / n).tolist()


_KEY = re.compile(r"\d|决定|改为|改成|采用|阻塞|卡在|截止|版本|完成|失败|通过|原因|约束|不要|必须|PR|commit|bug|修复",
                  re.I)


def candgen(user: str) -> str:
    units = re.split(r"### Unit (\d+)[^\n]*\n", user)
    mems = []
    for i in range(1, len(units) - 1, 2):
        uid = int(units[i])
        body = units[i + 1]
        m = re.search(r"\[assistant\]\n(.*)", body, re.S)
        asst = m.group(1) if m else body
        for s in re.split(r"(?<=[。！？.!?])\s*|\n", asst):
            s = s.strip()
            if 8 <= len(s) <= 200 and _KEY.search(s):
                mems.append({"content": s, "type": "work_fact",
                             "salience": 0.8 if re.search(r"\d", s) else 0.6,
                             "source_unit_ids": [uid]})
    prev = re.search(r"【上一个情境】：(.*)", user)
    scene = prev.group(1).strip() if prev and prev.group(1).strip() != "无" \
        else "在围绕 mock 项目做开发与调试"
    return json.dumps({"scene_name": scene, "memories": mems[:4]},
                      ensure_ascii=False)


def judge(user: str) -> str:
    m = re.match(r"A: (.*)\nB: (.*)", user, re.S)
    if not m:
        return "collision"
    a, b = m.group(1), m.group(2)
    ta, tb = set(_toks(a)), set(_toks(b))
    j = len(ta & tb) / max(1, len(ta | tb))
    na, nb = re.findall(r"\d+(?:\.\d+)?", a), re.findall(r"\d+(?:\.\d+)?", b)
    if j > 0.3 and na and nb and na != nb:
        return "update"
    if j > 0.75:
        return "synonym"
    return "collision"


def recognizer(user: str) -> str:
    ans = re.search(r"助手回答: (.*?)\n注入记忆:", user, re.S)
    ans_t = set(_toks(ans.group(1))) if ans else set()
    hits = []
    for idx, text in re.findall(r"\[(\d+)\] (.*)", user):
        mt = set(_toks(text))
        if mt and len(mt & ans_t) / len(mt) > 0.35:
            hits.append(idx)
    return ",".join(hits) or "NONE"


def route_chat(system: str, user: str) -> tuple[str, str]:
    if "情境切分与记忆提取" in system:
        return "candgen", candgen(user)
    if "记忆冲突裁判" in system:
        return "judge", judge(user)
    if "记忆贡献归因器" in system:
        return "recognizer", recognizer(user)
    if "巩固器" in system:
        return "consolidate", "NONE"
    return "other", "（mock 回复）好的，我已了解当前项目状态。"


def investigator_step(body: dict):
    """脚本化的调查员：真的发 tool_calls，走插件 worker 角色的工具面。
    返回 ("tool", name, args) 或 ("text", str)。"""
    msgs = body.get("messages", [])
    blob = json.dumps(msgs, ensure_ascii=False)
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    def _c(m):
        c = m.get("content")
        return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
    kind = "recall_miss" if "recall_miss" in blob else "extract_due" if "extract_due" in blob else ""
    q = re.search(r'\\?"q\\?": \\?"([^"\\]+)', blob)
    uid = re.search(r'\\?"unit_id\\?": (\d+)', blob)
    if not tool_msgs:
        if kind == "extract_due" and uid:
            return ("tool", "log_window", {"unit_ids": [int(uid.group(1))], "max_chars": 800})
        return ("tool", "log_search", {"query": q.group(1) if q else "cap_m"})
    last = _c(tool_msgs[-1])
    units = [int(x) for x in re.findall(r"unit[ _]?(?:id)?[\"': ]*?(\d+)", last)]
    if len(tool_msgs) == 1 and units:
        snippet = re.sub(r"^.*?\] ", "", last.splitlines()[1] if len(last.splitlines()) > 1 else last)[:120]
        return ("text", json.dumps({
            "proposals": [{"text": f"（调查员核实）{snippet}", "kind": "work_fact", "salience": 0.7,
                           "source_unit_ids": units[:1]}],
            "diagnosis": {"miss_type": "dropped_by_candgen", "note": "mock investigator"}},
            ensure_ascii=False))
    return ("text", json.dumps({"proposals": [], "diagnosis": {"miss_type": "never_logged", "note": "mock: 无命中"}},
                               ensure_ascii=False))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/stats"):
            with _LOCK:
                return self._json(200, STATS)
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": "glm-5.3-flash", "object": "model"}]})
        self._json(404, {"error": "nope"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            return self._json(401, {"error": "no auth"})
        if self.path.endswith("/embeddings"):
            inp = body.get("input", [])
            inp = [inp] if isinstance(inp, str) else inp
            with _LOCK:
                STATS["embed_calls"] += 1
                STATS["embed_texts"] += len(inp)
            return self._json(200, {"data": [
                {"index": i, "embedding": e} for i, e in enumerate(embed_batch(inp))],
                "usage": {"prompt_tokens": sum(len(t) for t in inp)}})
        if self.path.endswith("/chat/completions"):
            msgs = body.get("messages", [])

            def _txt(c):
                if isinstance(c, list):
                    return "".join(p.get("text", "") for p in c if isinstance(p, dict))
                return c or ""
            system = "\n".join(_txt(m.get("content")) for m in msgs if m.get("role") == "system")
            user = "\n".join(_txt(m.get("content")) for m in msgs if m.get("role") == "user")
            role, out = route_chat(system, user)
            tool_names = [t.get("function", {}).get("name") for t in body.get("tools", [])]
            step = None
            if role == "other" and "log_search" in tool_names and "调查员" in system + user:
                role = "investigator"
                step = investigator_step(body)
                if step[0] == "text":
                    out = step[1]
                with open("/tmp/mock_investigator.log", "a") as f:
                    f.write(json.dumps({"tools_allowed": tool_names, "step": step}, ensure_ascii=False) + "\n")
            if role == "other":
                with open("/tmp/mock_last_agent_request.json", "w") as f:
                    json.dump({"system": system, "user": user,
                               "tools": [t.get("function", {}).get("name") for t in body.get("tools", [])]},
                              f, ensure_ascii=False, indent=1)
            with _LOCK:
                STATS["chat"][role] = STATS["chat"].get(role, 0) + 1
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                cid = f"chatcmpl-{int(time.time()*1000)}"
                def ev(d):
                    self.wfile.write(f"data: {json.dumps(d, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                base = {"id": cid, "object": "chat.completion.chunk",
                        "created": int(time.time()), "model": body.get("model")}
                ev({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}}]})
                finish = "stop"
                if step and step[0] == "tool":
                    finish = "tool_calls"
                    ev({**base, "choices": [{"index": 0, "delta": {"tool_calls": [{
                        "index": 0, "id": f"call_{cid}", "type": "function",
                        "function": {"name": step[1], "arguments": json.dumps(step[2], ensure_ascii=False)}}]}}]})
                else:
                    ev({**base, "choices": [{"index": 0, "delta": {"content": out}}]})
                ev({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return
            if step and step[0] == "tool":
                message = {"role": "assistant", "content": None, "tool_calls": [{
                    "id": f"call_{int(time.time()*1000)}", "type": "function",
                    "function": {"name": step[1], "arguments": json.dumps(step[2], ensure_ascii=False)}}]}
                finish = "tool_calls"
            else:
                message = {"role": "assistant", "content": out}
                finish = "stop"
            return self._json(200, {"id": "x", "object": "chat.completion",
                                    "model": body.get("model"),
                                    "choices": [{"index": 0, "finish_reason": finish,
                                                 "message": message}],
                                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})
        self._json(404, {"error": f"no route {self.path}"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
    print(f"[mock-llm] http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
