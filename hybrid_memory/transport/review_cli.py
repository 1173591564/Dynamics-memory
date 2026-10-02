"""Human-only CLI for reviewing conflicting memory candidates; uses sidecar HTTP."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--port", type=int, default=17872)
    ap.add_argument("--list-rules", action="store_true", help="list Reviewer rules and usage")
    ap.add_argument("--disable-rule", type=int, help="disable a Reviewer rule by version ID")
    args = ap.parse_args()
    root = Path(args.project) / ".opencode" / "memory"
    if args.list_rules or args.disable_rule is not None:
        from ..store.tasks import TaskStore
        store = TaskStore(root / "tasks.sqlite")
        try:
            if args.disable_rule is not None:
                print("disabled" if store.disable_rule(args.disable_rule) else "rule not found or already disabled")
            for row in store.rule_report():
                print(json.dumps(row, ensure_ascii=False))
        finally:
            store.close()
        return
    bearer = (root / ".memory-token").read_text().strip()
    capability = (root / ".human-review-token").read_text().strip()

    def post(path, payload, *, privileged=False):
        req = Request(f"http://127.0.0.1:{args.port}{path}",
            data=json.dumps(payload).encode(), method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {bearer}",
                **({"X-Human-Review-Token": capability} if privileged else {})})
        with urlopen(req, timeout=30) as response:
            return json.load(response)

    for item in post("/human-reviews", {})["reviews"]:
        print(f"\nReview #{item['id']} existing memory #{item['target_id']}")
        print("Existing:", item["existing"])
        print("Candidate:", item["candidate"])
        print("Reason:", item["reason"])
        choice = input("Choose accept_new / keep_old / skip: ").strip()
        if choice in ("accept_new", "keep_old"):
            print(post("/human-review", {"review_id": item["id"],
                                         "decision": choice}, privileged=True))


if __name__ == "__main__":
    main()
