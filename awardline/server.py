"""Awardline MCP server. Stdout is the protocol stream. Do not print."""

import json

from mcp.server.mcpserver import MCPServer

from awardline.drop import file_committee_note as commit_note
from awardline.notes import tool_draft_committee_note, tool_flag_price_outlier, tool_search_awards

mcp = MCPServer("awardline")


@mcp.tool()
def search_awards(buyer: str = "", query: str = "", limit: int = 8) -> str:
    """Find published Kenya PPIP awards by buyer name, purchase description, or both."""
    return json.dumps(tool_search_awards(buyer=buyer, query=query, limit=limit), ensure_ascii=False)


@mcp.tool()
def flag_price_outlier(buyer: str, query: str, amount: float, currency: str = "KES") -> str:
    """Compare a quoted amount with past awards and write a sourced flag. Does not file anything."""
    return json.dumps(
        tool_flag_price_outlier(buyer=buyer, query=query, amount=amount, currency=currency),
        ensure_ascii=False,
    )


@mcp.tool()
def draft_committee_note(buyer: str, query: str, amount: float, currency: str = "KES") -> str:
    """Draft a committee note from an existing flag. Citations come from the flag, not from the model."""
    return json.dumps(
        tool_draft_committee_note(buyer=buyer, query=query, amount=amount, currency=currency),
        ensure_ascii=False,
    )


@mcp.tool()
def file_committee_note(note_id: str) -> str:
    """File a drafted note into the committee folder. Refuses unless a named officer has approved it."""
    return json.dumps(commit_note(note_id), ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
