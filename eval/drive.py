"""按 memory-bridge 插件的调用顺序驱动 sidecar：
每轮  /search(用户输入) → [模拟 agent 作答] → /observe → /feedback
中途：用户纠正（→ recall_miss）、数字更新（→ tension/update）、泄露密钥（→ 脱敏）、
      agent 主动 log_* / propose / supersedes、/signals、/save。
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 17872
PROJ = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/proj")
PHASE = sys.argv[3] if len(sys.argv) > 3 else "full"
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = (PROJ / ".opencode/memory/.memory-token").read_text().strip()


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}",
        **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


TURNS = [
    ("我们这个记忆项目现在用什么向量模型？",
     "目前决定采用智谱 embedding-3，维度 2048。缓存放在 emb.sqlite3 里。"),
    ("M 池容量设多少合适",
     "已决定把 cap_m 设为 40，θp=1.5，θd=0.8。滞回用来防抖。"),
    ("跑一下测试",
     "pytest 全部通过，共 211 个测试，用时 6 秒。"),
    ("LoCoMo 结果怎么样",
     "LoCoMo 上 acc 只有 0.29，原因是蒸馏丢细节。evidence recall 只有 0.16。"),
    ("我的 key 是 sk-abcdefghijklmnopqrstuvwx123 帮我配一下",
     "已把 ZAI_API_KEY 写入 .env，key 是 sk-abcdefghijklmnopqrstuvwx123，注意不要提交。"),
    ("今天天气不错", "是的，祝你心情愉快！"),
    ("cap_m 还是太大了，改小",
     "已决定把 cap_m 改为 8，θp 保持 1.5。原先是 40。"),
    ("调查员卡在哪了",
     "调查员目前阻塞在 opencode worker 端到端未验证，需要 ZAI_API_KEY 才能跑。"),
    ("M 池容量现在是多少？", "cap_m 是 40。"),               # 答错（旧值）
    ("不对，你记错了，已经改成 8 了", "抱歉，cap_m 现在是 8。"),  # 纠正 → recall_miss
    ("PR 123 合了吗", "PR 123 已合并，修复了 follow_chain 在 id=0 时的 KeyError bug。"),
    ("下一步做什么",
     "下一步必须扩大评测到 100 个点，并加上 LICENSE 与 pyproject。截止 10 月 15 日。"),
]


def turn(i, user, asst):
    s, rec = call("POST", "/search", {"query": user})
    ctx = rec.get("context", "")
    s2, obs = call("POST", "/observe", {"user_text": user, "assistant_text": asst})
    fb = call("POST", "/feedback", {"retrieval_id": rec.get("retrieval_id"),
                                    "question": user, "answer": asst}) if rec.get("n") else (None, {})
    print(f"\n── turn {i}: {user}")
    print(f"   search {s}: n={rec.get('n')}" + ("\n   " + ctx.replace("\n", "\n   ") if ctx else ""))
    print(f"   observe {s2}: cands={obs.get('candidates')} reasons={obs.get('reasons')} "
          f"pool={obs.get('pool')} worker={obs.get('worker')}")
    if fb[0]:
        print(f"   feedback {fb[0]}: {fb[1]}")


def main():
    print("health:", call("GET", "/health"))
    if PHASE in ("full", "turns"):
        for i, (u, a) in enumerate(TURNS):
            turn(i, u, a)

    if PHASE in ("full", "tools"):
        print("\n══ agent 工具面（主 agent 角色，无 signal id）")
        print("log/search:", call("POST", "/log/search", {"query": "cap_m"}))
        print("log/timeline:", call("POST", "/log/timeline", {"entity": "cap_m"}))
        print("log/stats:", call("POST", "/log/stats", {"group_by": "entity"}))
        print("log/window:", call("POST", "/log/window", {"unit_ids": [6], "max_chars": 300}))
        print("miss:", call("POST", "/miss", {"query": "M 池容量现在是多少", "source": "agent_tool"}))
        print("propose(无来源，应拒):", call("POST", "/propose", {"proposals": [{"text": "cap_m=8"}]}))
        print("propose(未来来源，应拒):", call("POST", "/propose", {"proposals": [
            {"text": "cap_m 当前为 8", "source_unit_ids": [9999]}]}))
        print("propose(自指，应拒):", call("POST", "/propose", {"proposals": [
            {"text": "我检索了日志并找到了记忆", "source_unit_ids": [6]}]}))
        old = [m for m in call("POST", "/search", {"query": "cap_m 设为 40", "k": 10})[1]["selected"]
               if "40" in m["text"]]
        sup = [old[0]["id"]] if old else []
        print("待取代旧条目:", old[:1])
        print("propose(合法 + supersedes):", call("POST", "/propose", {"proposals": [
            {"text": "M 池容量 cap_m 当前为 8（原先是 40），θp=1.5",
             "source_unit_ids": [6, 9], "entity_key": "cap_m", "supersedes": sup}]}))
        print("\nsearch after propose:", call("POST", "/search", {"query": "M 池容量是多少"})[1]["context"])
        print("\nconflicts:", json.dumps(call("GET", "/conflicts")[1], ensure_ascii=False)[:800])
        print("\nsignals:", json.dumps(call("GET", "/signals")[1], ensure_ascii=False)[:1500])
        print("\n未授权请求:", urllib_noauth())
        print("save:", call("POST", "/save", {}))
    print("health:", call("GET", "/health"))


def urllib_noauth():
    try:
        urllib.request.urlopen(urllib.request.Request(BASE + "/signals"), timeout=5)
    except urllib.error.HTTPError as e:
        return e.code




def more(n=12):
    """再跑 n 轮，让 tension 老化超过 tension_delay=20 → conflict_pending → judge。"""
    for i in range(n):
        turn(100 + i, f"继续调参第 {i} 轮", f"第 {i} 轮实验完成，recall 为 0.{70 + i}，决定继续。")
    print("\nconflicts:", json.dumps(call("GET", "/conflicts")[1], ensure_ascii=False)[:600])
    print("health:", call("GET", "/health"))


if __name__ == "__main__":
    more() if PHASE == "more" else main()
