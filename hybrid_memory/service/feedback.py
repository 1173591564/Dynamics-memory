"""延迟记账（P4 从 server.py 原样迁入）：feedback。

幂等 + 锁外判裁：capture 回执去重，模型调用（process_semantic_tasks）
在服务锁外执行，效果已提交则交付失败也不翻转 accepted。
"""
from __future__ import annotations

from ..guards.bounds import capture_fingerprint as _capture_fingerprint
from ..guards.bounds import validate_request_id as _validate_request_id
from ..store.tasks import CaptureConflict


def feedback(svc, retrieval_id: int, question: str, answer: str,
             request_id: str | None = None) -> dict:
    request_id = _validate_request_id(request_id)
    fingerprint = _capture_fingerprint({
        "retrieval_id": retrieval_id, "question": question, "answer": answer})
    with svc._lock:
        svc._ensure_healthy()
        ret = svc._retrievals.get(retrieval_id)
        if request_id:
            old = svc.tasks.read_capture(request_id)
            if old is not None:
                if old["fingerprint"] != fingerprint:
                    raise CaptureConflict(f"request_id {request_id} 已绑定不同请求")
                # 回执已存在就不再跑模型；检索对象后来被挤出也不影响这次回放。
                return dict(old["response"], replayed=True, accepted=True,
                            request_id=request_id)
        if ret is None:
            return {"error": f"unknown retrieval_id {retrieval_id}"}
        if not ret.selected:
            response = {"n_useful": 0, "pending": False, "worker": {},
                        "accepted": True, "retrieval_id": retrieval_id}
            if request_id:
                stored, replayed = svc.tasks.remember_capture(
                    request_id, "feedback", fingerprint, response)
                response = dict(stored, accepted=True, request_id=request_id)
                if replayed:
                    response["replayed"] = True
            return response
        if ret.credited or ret.feedback_sent:
            # 同一次检索重复反馈（插件重试/多会话共用）：幂等拒绝，
            # 不让引擎的 RuntimeError 变成 500。accepted 表示效果已存在，
            # 不是邀请客户端换一个 request-id 再投。
            return {"error": f"retrieval_id {retrieval_id} already "
                             f"credited", "code": "already_credited",
                    "n_useful": ret.n_useful,
                    "pending": ret.feedback_sent and not ret.credited,
                    "accepted": True}

        def mutate():
            svc.engine.feedback(ret, question, answer, svc._t)
            if svc._last_turn is not None:
                svc._last_turn = {"user": question, "retrieval_id": retrieval_id}
            return {"n_useful": 0, "pending": True, "accepted": True,
                    "retrieval_id": retrieval_id,
                    **({"request_id": request_id} if request_id else {})}
        capture = ({"request_id": request_id, "kind": "feedback",
                    "fingerprint": fingerprint} if request_id else None)
        result = svc._commit_sidecar_effect(mutate, capture=capture)
        if isinstance(result, dict) and result.get("replayed"):
            return result
        base = result if isinstance(result, dict) else {}
    svc._unit_wake.set()
    try:
        wstats = svc.process_semantic_tasks()  # 模型调用在服务锁外
    except Exception as exc:  # noqa: BLE001  效果已提交，不能把交付回执变成未接受
        wstats = {"error": f"{type(exc).__name__}: {exc}"}
    with svc._lock:
        return {**base, "n_useful": ret.n_useful, "pending": not ret.credited,
                "worker": wstats, "accepted": True,
                **({"request_id": request_id} if request_id else {})}
