"""Manual real-CLI protocol smoke, with a local *fake* OpenAI-compatible model.

Run from the source root:
  python tests/manual_opencode_smoke.py /absolute/path/to/opencode
This proves CLI loading/JSON parsing/SQLite handoffs, NOT model reasoning quality.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid_memory.agent.trio import OpenCodeRunner, TrioWorker  # noqa: E402
from test_ouroboros import _svc  # noqa: E402


class MockModel(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length'])).decode()
        request = json.loads(raw)
        def texts(obj):
            if isinstance(obj, str):
                return [obj]
            if isinstance(obj, list):
                return [item for x in obj for item in texts(x)]
            if isinstance(obj, dict):
                return [item for x in obj.values() for item in texts(x)]
            return []
        prompt = '\n'.join(texts(request.get('messages', [])))
        prompt = prompt.replace('\\"', '"')  # SDK serializes content as JSON text
        if '"kind": "reviewer_due"' in prompt:
            reply = {"diagnosis": "mock: verify handoff only", "rules": [{
                "target": "hauler", "scope": "entity:bun", "instruction": "Check bun decisions."}],
                "repair_candidates": []}
        elif '"kind": "selector_due"' in prompt:
            reply = {"decisions": [{"candidate_index": 0, "action": "CREATE"}]}
        elif '"kind": "hauler_due"' in prompt and '"unit_id": 0' in prompt:
            reply = {"candidates": [{"text": "项目统一使用 bun 工具", "source_unit_ids": [0]}]}
        else:
            reply = {"candidates": []}
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        def chunk(delta, reason):
            return {"id": "local-mock", "object": "chat.completion.chunk", "created": 1,
                    "model": request.get('model', 'echo'), "choices": [{"index": 0,
                    "delta": delta, "finish_reason": reason}]}
        for event in (chunk({"role": "assistant"}, None),
                      chunk({"content": json.dumps(reply)}, None), chunk({}, 'stop')):
            self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()


def main(executable):
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), MockModel)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    old = os.environ.get('OPENCODE_CONFIG_CONTENT')
    os.environ['OPENCODE_CONFIG_CONTENT'] = json.dumps({
        'model': 'local-mock/echo', 'provider': {'local-mock': {
            'name': 'Local Mock', 'npm': '@ai-sdk/openai-compatible', 'env': [],
            'models': {'echo': {'name': 'Echo', 'tool_call': False,
                                'limit': {'context': 8192, 'output': 2048}}},
            'options': {'apiKey': 'local-test-only',
                        'baseURL': f'http://127.0.0.1:{httpd.server_address[1]}/v1'}}}})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            svc = _svc(Path(tmp))
            svc.trio_mode = True
            worker = TrioWorker(svc, OpenCodeRunner(Path(tmp), executable, timeout=50))
            try:
                svc.observe('项目统一使用 bun 工具', '好的')
                for _ in range(4):
                    worker.process_once()
                assert svc.engine.mems[0].text == '项目统一使用 bun 工具'
                svc.observe('这个事情我之前明明讲过', '抱歉')
                for _ in range(4):
                    worker.process_once()
                assert len(svc.tasks.rule_report()) == 1
                done = svc.tasks.list_tasks(states=('done',), kinds={
                    'hauler_due', 'selector_due', 'reviewer_due'})
                assert {t['kind'] for t in done} == {
                    'hauler_due', 'selector_due', 'reviewer_due'}
                print('Real OpenCode CLI: three agents loaded, SQLite handoffs committed; model=fake local API')
            finally:
                svc.tasks.close()
                svc.log.close()
    finally:
        if old is None:
            os.environ.pop('OPENCODE_CONFIG_CONTENT', None)
        else:
            os.environ['OPENCODE_CONFIG_CONTENT'] = old
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python tests/manual_opencode_smoke.py /path/to/opencode')
    main(sys.argv[1])
