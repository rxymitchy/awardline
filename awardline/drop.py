"""Committee drop folder, written only through the official filesystem MCP server."""

import asyncio
import os
from pathlib import Path

from awardline.audit import log_call
from awardline.paths import FILINGS, ROOT, ensure_runtime


def _server_command(directory: str) -> tuple[str, list[str]]:
    local = ROOT / "node_modules" / "@modelcontextprotocol" / "server-filesystem" / "dist" / "index.js"
    if local.exists():
        return "node", [str(local), directory]
    command = "npx.cmd" if os.name == "nt" else "npx"
    return command, ["-y", "@modelcontextprotocol/server-filesystem", directory]


async def _write_via_mcp(filename: str, content: str) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    ensure_runtime()
    directory = str(FILINGS.resolve())
    command, args = _server_command(directory)
    params = StdioServerParameters(command=command, args=args)
    target = str((FILINGS / filename).resolve())
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("write_file", {"path": target, "content": content})
    if getattr(result, "isError", False):
        detail = _tool_text(result)
        raise RuntimeError(detail or "filesystem MCP refused the write")
    return target


def _tool_text(result) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def write_committee_file(filename: str, content: str) -> str:
    if Path(filename).name != filename:
        raise ValueError("filename must not include a directory")
    try:
        path = asyncio.run(_write_via_mcp(filename, content))
    except RuntimeError:
        raise
    except Exception as exc:
        log_call(
            "borrowed-mcp",
            "filesystem.write_file",
            {"filename": filename},
            {"error": str(exc)},
            False,
        )
        raise
    log_call(
        "borrowed-mcp",
        "filesystem.write_file",
        {"filename": filename},
        {"path": path},
        True,
    )
    return path


def file_committee_note(note_id: str) -> dict:
    from awardline.notes import approval_for, draft_for

    draft = draft_for(note_id)
    approval = approval_for(note_id)
    inputs = {"note_id": note_id}
    if draft is None:
        result = {"ok": False, "error": "No draft to file."}
        log_call("agent", "file_committee_note", inputs, result, False)
        return result
    if approval is None or approval.get("decision") != "approve":
        result = {
            "ok": False,
            "error": "Officer approval required before this note can be filed.",
            "note_id": note_id,
        }
        log_call("agent", "file_committee_note", inputs, result, False)
        return result
    try:
        path = write_committee_file(f"{note_id}.md", draft["text"])
    except Exception as exc:
        result = {"ok": False, "error": f"Filesystem MCP write failed: {exc}", "note_id": note_id}
        log_call("agent", "file_committee_note", inputs, result, False)
        return result
    result = {
        "ok": True,
        "note_id": note_id,
        "path": path,
        "officer": approval["officer"],
        "approved_at": approval["approved_at"],
    }
    log_call("agent", "file_committee_note", inputs, result, True)
    return result
