import argparse
import json
from collections import Counter, defaultdict

from awardline.agent import OllamaModel, run_agent
from awardline.awards import load_snapshot, tokens
from awardline.drop import file_committee_note
from awardline.notes import record_approval
from awardline.score import median


def pick_demo_case(awards: list[dict]) -> dict | None:
    index = defaultdict(list)
    for position, award in enumerate(awards):
        for token in tokens(award["title"]):
            index[token].append(position)
    seen = set()
    for award in awards:
        title = award["title"]
        if not title or title in seen:
            continue
        seen.add(title)
        wanted = tokens(title)
        if len(wanted) < 2:
            continue
        counts: Counter[int] = Counter()
        for token in wanted:
            for position in index[token]:
                counts[position] += 1
        hits = [awards[position] for position, count in counts.items() if count >= 2]
        if len(hits) < 4:
            continue
        typical = median([float(row["amount"]) for row in hits[:12]])
        if typical < 1000:
            continue
        return {
            "buyer": award["buyer"],
            "query": title,
            "amount": round(typical * 4, 2),
            "median": round(typical, 2),
            "comparables": len(hits),
        }
    return None


def demo(approve: bool, officer: str) -> int:
    awards = list(load_snapshot())
    case = pick_demo_case(awards)
    if case is None:
        print("No purchase in the snapshot has 4 comparable awards.")
        return 1
    task = (
        f"Buyer {case['buyer']} received a quote of KES {case['amount']:,.2f} for: {case['query']} "
        "Compare it with published past awards and draft a value-for-money committee note. "
        "Do not award the tender."
    )
    print(task)
    print("---")
    result = run_agent(task, OllamaModel())
    draft = result.get("draft")
    if not draft:
        print("The agent stopped without a draft. Last messages:")
        for message in result["messages"][-4:]:
            print(message.get("role"), (message.get("content") or "")[:500])
        return 1
    print(draft["text"])
    if not approve:
        print("---")
        print(f"Not filed. An officer can approve note {draft['note_id']}.")
        return 0
    approval = record_approval(draft["note_id"], officer)
    print("---")
    print("Officer approval:", json.dumps(approval))
    if not approval.get("ok"):
        return 1
    filed = file_committee_note(draft["note_id"])
    print("Filing:", json.dumps(filed))
    return 0 if filed.get("ok") else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Awardline value-for-money agent")
    sub = parser.add_subparsers(dest="command", required=True)

    demo_parser = sub.add_parser("demo", help="Run one quote through the agent")
    demo_parser.add_argument("--approve", action="store_true", help="Record an officer approval and file the note")
    demo_parser.add_argument("--officer", default="Amina Yusuf")

    approve_parser = sub.add_parser("approve", help="Record a named officer's approval")
    approve_parser.add_argument("--note-id", required=True)
    approve_parser.add_argument("--officer", required=True)

    file_parser = sub.add_parser("file", help="File an approved note through the filesystem MCP server")
    file_parser.add_argument("--note-id", required=True)

    sub.add_parser("serve", help="Run the Awardline MCP server on stdio")
    sub.add_parser("eval", help="Run the evaluation tasks and write evals/results.json")

    args = parser.parse_args()
    if args.command == "demo":
        raise SystemExit(demo(args.approve, args.officer))
    if args.command == "approve":
        print(json.dumps(record_approval(args.note_id, args.officer), indent=2))
        return
    if args.command == "file":
        print(json.dumps(file_committee_note(args.note_id), indent=2))
        return
    if args.command == "serve":
        from awardline.server import main as serve

        serve()
        return
    if args.command == "eval":
        from awardline.evaluate import main as evaluate

        raise SystemExit(evaluate())


if __name__ == "__main__":
    main()
