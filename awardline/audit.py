import json
import os
from datetime import datetime, timezone
from typing import Any

from awardline.paths import LOGS, ensure_runtime


def caller() -> str:
    return os.environ.get("AWARDLINE_ACTOR", "agent")


def log_call(actor: str, tool: str, inputs: dict, outputs: Any, ok: bool) -> dict:
    ensure_runtime()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "tool": tool,
        "inputs": inputs,
        "outputs": outputs,
        "ok": ok,
    }
    with LOGS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
