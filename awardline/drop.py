"""Committee drop folder.

Files are written directly to the filings directory. The optional filesystem
MCP server is used when available, with a direct-write fallback so the system
works even when Node.js / npx is absent or the subprocess cannot be spawned
(e.g. inside a serverless container or a nested async context).
"""

import asyncio
import os
from pathlib import Path

from awardline.audit import caller, log_call
from awardline.paths import FILINGS, ROOT, ensure_runtime


def _server_command(directory: str) -> tuple[str, list[str]] | None:
    """Return (command, args) for the filesystem MCP server, or None if unavailable."""
    local = ROOT / "node_modules" / "@modelcontextprotocol" / "server-filesystem" / "dist" / "index.js"
    if local.exists():
        return "node", [str(local), directory]
    # npx.cmd is the Windows wrapper; plain npx is the POSIX script
    npx = "npx.cmd" if os.name == "nt" else "npx"
    # Only return the npx path if the executable actually exists
    import shutil
    if shutil.which(npx):
        return npx, ["-y", "@modelcontextprotocol/server-filesystem", directory]
    return None


async def _write_via_mcp(filename: str, content: str) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    ensure_runtime()
    directory = str(FILINGS.resolve())
    server_cmd = _server_command(directory)
    if server_cmd is None:
        raise RuntimeError("filesystem MCP server not available")
    command, args = server_cmd
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


def _write_direct(filename: str, content: str) -> str:
    """Write content directly to the filings directory (no MCP subprocess)."""
    ensure_runtime()
    target = FILINGS / filename
    target.write_text(content, encoding="utf-8")
    return str(target.resolve())


def write_committee_file(filename: str, content: str) -> str:
    if Path(filename).name != filename:
        raise ValueError("filename must not include a directory")

    # Try MCP server first; fall back to a direct write.
    try:
        # asyncio.run() raises RuntimeError when called inside a running loop.
        # In that case (FastAPI / uvicorn), skip straight to the direct write.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            raise RuntimeError("running loop — skip MCP, use direct write")

        path = asyncio.run(_write_via_mcp(filename, content))
        log_call(
            "filesystem-mcp",
            "filesystem.write_file",
            {"filename": filename},
            {"path": path},
            True,
        )
        return path
    except Exception as mcp_exc:
        # MCP route failed — write directly.
        try:
            path = _write_direct(filename, content)
        except Exception as direct_exc:
            log_call(
                "filesystem-direct",
                "filesystem.write_file",
                {"filename": filename},
                {"error": str(direct_exc)},
                False,
            )
            raise RuntimeError(str(direct_exc)) from direct_exc
        log_call(
            "filesystem-direct",
            "filesystem.write_file",
            {"filename": filename},
            {"path": path, "mcp_skipped": str(mcp_exc)},
            True,
        )
        return path


def file_committee_note(note_id: str) -> dict:
    from awardline.notes import approval_error, approval_for, draft_for

    draft = draft_for(note_id)
    approval = approval_for(note_id)
    inputs = {"note_id": note_id}
    if draft is None:
        result = {"ok": False, "error": "No draft to file."}
        log_call(caller(), "file_committee_note", inputs, result, False)
        return result
    refusal = approval_error(draft, approval)
    if refusal is not None:
        result = {"ok": False, "error": refusal, "note_id": note_id}
        log_call(caller(), "file_committee_note", inputs, result, False)
        return result
    try:
        path = write_committee_file(f"{note_id}.md", draft["text"])
    except Exception as exc:
        result = {"ok": False, "error": f"Filesystem MCP write failed: {exc}", "note_id": note_id}
        log_call(caller(), "file_committee_note", inputs, result, False)
        return result
    result = {
        "ok": True,
        "note_id": note_id,
        "path": path,
        "officer": approval["officer"],
        "approved_at": approval["approved_at"],
    }
    log_call(caller(), "file_committee_note", inputs, result, True)
    return result
