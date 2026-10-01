"""预览用启动器：原版 MemoryService（build_default_service）+ 本地 mock 智谱端点，
监听 0.0.0.0 供预览访问。不修改仓库代码。

- 原有 JSON 端点照旧（除 /health 外需 Bearer token）。
- 额外挂一个无鉴权的调试页 "/"，以及 /ui/observe、/ui/recall、/ui/state 三个
  页面专用端点：它们在服务端直接调 service 方法，token 不会暴露到浏览器。

用法（仓库根目录下）：
  python /home/user/dm-run/mock_llm.py 18080 &
  ZAI_BASE_URL=http://127.0.0.1:18080 ZAI_API_KEY=mock \
      python /home/user/dm-run/preview_sidecar.py --project /home/user/dm-run/preview-proj --port 8000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from hybrid_memory import server as S

PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>Dynamics-memory sidecar（mock 预览）</title>
<style>
body{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1f2328}
h1{font-size:20px;margin:0 0 4px} .sub{color:#666;font-size:13px;margin-bottom:16px}
.card{border:1px solid #d0d7de;border-radius:8px;padding:14px;margin:12px 0}
.card h2{font-size:15px;margin:0 0 10px}
textarea,input{width:100%;box-sizing:border-box;font:inherit;padding:6px;border:1px solid #d0d7de;border-radius:6px}
textarea{height:60px} button{margin-top:8px;padding:6px 14px;border:0;border-radius:6px;background:#1f6feb;color:#fff;cursor:pointer}
pre{background:#f6f8fa;padding:10px;border-radius:6px;overflow:auto;font-size:12px;max-height:360px;white-space:pre-wrap}
.kv{display:flex;flex-wrap:wrap;gap:8px}.kv span{background:#eef3ff;border-radius:6px;padding:4px 8px;font-size:13px}
.warn{background:#fff8c5;border:1px solid #e3c200;border-radius:6px;padding:8px;font-size:13px}
</style></head><body>
<h1>Dynamics-memory sidecar</h1>
<div class="sub">原版 MemoryService · LLM/嵌入走本地 mock（bge 本地嵌入 + 规则化抽取）· 调查员关闭</div>
<div class="warn">这是 mock 环境：候选抽取与裁判由规则化假 LLM 完成，只用于观察管线与状态流转，不代表真实质量。</div>
<div class="card"><h2>状态 <button onclick="state()" style="margin:0 0 0 8px;padding:2px 10px">刷新</button></h2>
<div class="kv" id="kv"></div><pre id="mems"></pre></div>
<div class="card"><h2>喂入一轮对话（/observe）</h2>
<label>user</label><textarea id="u">我们的前端构建从 webpack 换成 vite 了，以后 dev 端口用 5173</textarea>
<label>assistant</label><textarea id="a">好的，已记录：构建工具改为 vite，开发端口 5173。</textarea>
<button onclick="observe()">observe</button><pre id="obs"></pre></div>
<div class="card"><h2>召回（/recall）</h2>
<input id="q" value="前端用什么构建工具？"><button onclick="recall()">recall</button><pre id="rec"></pre></div>
<script>
async function j(r){const t=await r.text();try{return JSON.stringify(JSON.parse(t),null,2)}catch(e){return t}}
async function state(){const r=await fetch('ui/state');const d=await r.json();
 const h=d.health;document.getElementById('kv').innerHTML=
 ['t','tensions','signals','log_units'].map(k=>`<span>${k}: ${h[k]}</span>`).join('')+
 Object.entries(h.mems||{}).map(([k,v])=>`<span>池 ${k}: ${v}</span>`).join('');
 document.getElementById('mems').textContent=d.memories.length?d.memories.map(m=>
 `#${m.id} [${m.pool}] V=${m.V} ${m.text}`).join('\\n'):'（暂无记忆）'}
async function observe(){document.getElementById('obs').textContent='…';
 const r=await fetch('ui/observe',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user_text:u.value,assistant_text:a.value})});
 document.getElementById('obs').textContent=await j(r);state()}
async function recall(){const r=await fetch('ui/recall?q='+encodeURIComponent(q.value));
 document.getElementById('rec').textContent=await j(r);state()}
state();
</script></body></html>"""


def _mem_rows(service) -> list[dict]:
    rows = []
    with service._lock:
        for m in sorted(service.engine.mems.values(), key=lambda m: m.id):
            pool = getattr(m.pool, "name", str(m.pool))
            rows.append({"id": m.id, "pool": pool,
                         "V": round(float(m.v), 3),
                         "text": m.text[:160]})
    return rows


class PreviewHandler(S._Handler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        svc = self.service
        if u.path in ("/", "/index.html"):
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/ui/state":
            with svc._lock:
                health = {"t": svc._t, "mems": svc.engine.pool_sizes(),
                          "tensions": len(svc.engine.tensions),
                          "signals": len(svc.engine.signals),
                          "log_units": svc.log.count()}
            return self._json({"health": health, "memories": _mem_rows(svc)})
        if u.path == "/ui/recall":
            q = (parse_qs(u.query).get("q") or [""])[0]
            if not q:
                return self._json({"error": "q required"}, 400)
            return self._json(svc.recall(q, None))
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/ui/observe":
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            user, asst = body.get("user_text", ""), body.get("assistant_text", "")
            if not (user.strip() or asst.strip()):
                return self._json({"error": "empty turn"}, 400)
            return self._json(self.service.observe(user, asst))
        return super().do_POST()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="/home/user/dm-run/preview-proj")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    Path(args.project).mkdir(parents=True, exist_ok=True)

    service = S.build_default_service(args.project)
    handler = type("_PreviewBound", (PreviewHandler,), {"service": service})
    httpd = S.ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"[preview-sidecar] http://0.0.0.0:{args.port}  project={args.project} "
          f"mems={len(service.engine.mems)} log_units={service.log.count()} "
          f"token_file={service.state_path.parent / '.memory-token'}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.save()
        httpd.server_close()


if __name__ == "__main__":
    sys.exit(main())
