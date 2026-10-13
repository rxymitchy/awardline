from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "awards.json"
RUNTIME = ROOT / "runtime"
LOGS = ROOT / "logs" / "tool_calls.jsonl"
FILINGS = ROOT / "filings"
DRAFTS = RUNTIME / "drafts"
FLAGS = RUNTIME / "flags"
APPROVALS = RUNTIME / "approvals"


def ensure_runtime() -> None:
    for path in (RUNTIME, DRAFTS, FLAGS, APPROVALS, FILINGS, LOGS.parent):
        path.mkdir(parents=True, exist_ok=True)
