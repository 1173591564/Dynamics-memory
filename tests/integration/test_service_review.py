"""人审闭环(P4:从 tests/test_trio_protocol.py 抽出,与 trio 驱动解耦)。

覆盖 service/review.py:冲突隔离 → human_reviews 台账 → decide 终裁
(accept_new/keep_old/鉴权/幂等回放)。
"""
import json

import pytest

from hybrid_memory.dispatch.worker import DispatchWorker
from test_ouroboros import _svc


def drain(worker, n=6):
    for _ in range(n):
        if not worker.process_once():
            break


def test_conflict_quarantined_until_human_review_and_stale_version_stays_hidden(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True

    def fake(name, p):
        if name == "hauler":
            text = "端口现在是 8080" if p["unit_id"] == 0 else "端口现在是 9090"
            return {"candidates": [{"text": text, "source_unit_ids": [p["unit_id"]]}]}
        return {"decisions": [{"candidate_index": 0,
                "action": "CREATE" if p["unit_id"] == 0 else "CONFLICT",
                **({"target_id": 0} if p["unit_id"] else {})}]}

    worker = DispatchWorker(svc, fake)
    try:
        svc.observe("项目端口是 8080", "记下了")
        drain(worker)
        svc.observe("项目端口是 9090", "记下了")
        drain(worker)
        reviews = svc.human_reviews()
        assert len(reviews) == 1
        assert reviews[0]["existing"]["text"] == "端口现在是 8080"
        assert len(svc.engine.mems) == 1
        assert svc.engine.mems[0].pending_review
        with pytest.raises(PermissionError):
            svc.decide_human_review(reviews[0]["id"], "accept_new", "bad")
        applied = svc.decide_human_review(reviews[0]["id"], "accept_new", svc.human_review_token)
        assert applied["new_ids"] == [1]
        assert svc.engine.mems[0].superseded_by == 1
        assert svc.engine.mems[0].pending_review is False
        assert not svc.human_reviews()
        assert svc.decide_human_review(reviews[0]["id"], "accept_new", svc.human_review_token)["replayed"]
        from hybrid_memory.core import retrieval
        from hybrid_memory.core.types import Query
        ret = svc.engine.retrieve(svc.emb.embed(["端口现在是 8080"])[0], Query(-1, "端口现在是 8080"), svc._t)
        assert 0 not in [m.id for m in ret.selected]
    finally:
        svc.tasks.close()
        svc.log.close()


def test_review_http_requires_independent_human_capability(tmp_path):
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from hybrid_memory.server import serve
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def fake(name, p):
        if name == "hauler":
            return {"candidates": [{"text": f"端口现在是 {8080 if p['unit_id'] == 0 else 9090}",
                                    "source_unit_ids": [p["unit_id"]]}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE" if p["unit_id"] == 0 else "CONFLICT",
                              **({"target_id": 0} if p["unit_id"] else {})}]}
    svc.observe("端口现在是 8080", "好")
    drain(DispatchWorker(svc, fake))
    svc.observe("端口现在是 9090", "好")
    drain(DispatchWorker(svc, fake))
    httpd = serve(svc, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    def call(path, data, token=""):
        req = Request(f"http://127.0.0.1:{httpd.server_address[1]}{path}",
                      data=json.dumps(data).encode(), method="POST", headers={
                          "Content-Type": "application/json",
                          "Authorization": "Bearer " + svc.token,
                          "X-Human-Review-Token": token})
        try:
            with urlopen(req, timeout=4) as r:
                return r.status, json.load(r)
        except HTTPError as exc:
            return exc.code, json.load(exc)
    try:
        code, result = call("/human-reviews", {})
        assert code == 200 and len(result["reviews"]) == 1
        rid = result["reviews"][0]["id"]
        assert call("/human-review", {"review_id": rid, "decision": "keep_old"})[0] != 200
        assert svc.engine.mems[0].pending_review
        assert call("/human-review", {"review_id": rid, "decision": "keep_old"}, svc.human_review_token)[0] == 200
        assert call("/human-reviews", {})[1]["reviews"] == []
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)
        svc.tasks.close()
        svc.log.close()


def test_repeated_conflict_has_one_proposal_and_durable_review_consumer(tmp_path):
    svc = _svc(tmp_path)
    svc.trio_mode = True
    def runner(name, payload):
        if name == "hauler":
            unit = payload["window"][-1]
            return {"candidates": [{"text": unit["user_text"], "source_unit_ids": [unit["unit_id"]]}]}
        return {"decisions": [{"candidate_index": 0, "action": "CREATE" if not payload["memories"] else "CONFLICT",
                               **({"target_id": 0} if payload["memories"] else {})}]}
    worker = DispatchWorker(svc, runner)
    try:
        for text in ("网关模块的端口定为 gate-4100。", "网关模块的端口是 gate-4200。",
                     "网关模块的端口是 gate-4200。"):
            svc.observe(text, "好的")
            drain(worker)
            svc.process_semantic_tasks()
        reviews = svc.human_reviews()
        assert len(reviews) == 1
        assert json.loads(reviews[0]["candidate"])["source_unit_ids"] == [1, 2]
        assert reviews[0]["review_key"] and reviews[0]["target_stamp"]
        jobs = svc.tasks.list_tasks(kinds={"conflict_pending"})
        assert jobs and all(job["state"] == "done" for job in jobs)
        assert all(job["result"]["reviews"][0]["outcome"] == "needs_human" for job in jobs)
        assert svc.engine.mems[0].pending_review
        revision = svc._checkpoint_revision
        result = svc.recall("网关模块的端口现在是多少？", passive=True)
        assert "gate-4100" in result["context"] and "gate-4200" in result["context"]
        assert "待人审" in result["context"]
        assert svc._checkpoint_revision == revision
        svc.tasks.close()
        svc.log.close()
        svc = _svc(tmp_path)
        svc.trio_mode = True
        assert len(svc.human_reviews()) == 1
        review_id = svc.human_reviews()[0]["id"]
        accepted = svc.decide_human_review(review_id, "accept_new", svc.human_review_token)
        assert accepted["new_ids"]
        assert not svc.human_reviews()
        assert "gate-4100" not in svc.recall("网关模块的端口现在是多少？", passive=True)["context"]
        assert svc.decide_human_review(review_id, "accept_new", svc.human_review_token)["replayed"]
    finally:
        svc.tasks.close()
        svc.log.close()
