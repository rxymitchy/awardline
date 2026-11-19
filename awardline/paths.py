from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "awards.json"

# Use /tmp for runtime files on serverless platforms
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    RUNTIME = Path("/tmp/awardline")
else:
    RUNTIME = ROOT / "runtime"

LOGS = RUNTIME / "logs" / "tool_calls.jsonl"
FILINGS = RUNTIME / "filings"
DRAFTS = RUNTIME / "drafts"
FLAGS = RUNTIME / "flags"
APPROVALS = RUNTIME / "approvals"


def ensure_runtime() -> None:
    """Create runtime directories. On serverless, uses /tmp."""
    try:
        for path in (RUNTIME, DRAFTS, FLAGS, APPROVALS, FILINGS, LOGS.parent):
            path.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        # Read-only filesystem - log but don't crash
        print(f"Warning: Could not create runtime directories: {e}", file=__import__('sys').stderr)
        pass

