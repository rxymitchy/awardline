import json
from datetime import datetime, timezone
from typing import Any

from awardline.paths import LOGS, ensure_runtime


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
