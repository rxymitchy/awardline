import argparse
import json
from collections import Counter, defaultdict

from awardline.agent import OllamaModel, run_agent
from awardline.awards import load_snapshot, same_supplier, tokens
from awardline.drop import file_committee_note
from awardline.notes import record_approval
from awardline.score import MIN_HISTORY, comparables, median


def pick_demo_case(awards: list[dict]) -> dict | None:
    """Pick a real purchase with enough genuinely comparable awards to judge a quote."""
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
        # Cheap pre-filter on shared words before running the weighted matcher.
        counts: Counter[int] = Counter()
        for token in wanted:
            for position in index[token]:
                counts[position] += 1
        if sum(1 for count in counts.values() if count >= 2) < MIN_HISTORY:
            continue
        history = comparables(awards, title)
        if len(history) < MIN_HISTORY:
            continue
        typical = median([float(row["amount"]) for row in history])
        if typical < 1000:
            continue
        # Quote from a supplier with more than one PPIP award, so the note shows supplier history.
        supplier = next(
            (row["supplier"] for row in history if sum(1 for a in awards if same_supplier(a["supplier"], row["supplier"])) > 1),
            history[0]["supplier"],
        )
        return {
            "buyer": award["buyer"],
            "query": title,
            "supplier": supplier,
            "amount": round(typical * 4, 2),
            "median": round(typical, 2),
            "comparables": len(history),
        }
    return None


def demo(approve: bool, officer: str) -> int:
    awards = list(load_snapshot())
    case = pick_demo_case(awards)
    if case is None:
        print("No purchase in the snapshot has 4 comparable awards.")
        return 1
    task = (
        f"Buyer {case['buyer']} received a quote of KES {case['amount']:,.2f} "
        f"from supplier {case['supplier']} for: {case['query']} "
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
    print("---")
    for message in result["messages"]:
        if message.get("role") == "tool" and message.get("name") == "file_committee_note":
            outcome = message.get("result") or json.loads(message["content"])
            if outcome.get("ok"):
                print(f"The agent filed the note: {outcome['path']} (approved by {outcome['officer']}).")
            else:
                print(f"The agent tried to file the note and was refused: {outcome.get('error')}")
    if not approve:
        print(f"Not filed by this demo. An officer can approve note {draft['note_id']}.")
        return 0
    approval = record_approval(draft["note_id"], officer)
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
    sub.add_parser("refresh", help="Download the current PPIP release packages and rebuild the snapshot")

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
    if args.command == "refresh":
        from awardline.snapshot import refresh

        result = refresh()
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
