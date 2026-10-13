# Submission note

Awardline serves a procuring entity's committee on the value-for-money theme of the Bid Box track. The officer brings a quote. The agent searches Kenya PPIP awards for 2025/2026 and 2026/2027, flags the quote when it is at least twice the median of similar awards, and drafts a note that cites each award's OCID, buyer, title, amount, and source file. The committee decides. The agent never awards a tender.

The institution is any Kenyan procuring entity already publishing on the Public Procurement Information Portal. The workflow replaces the part of bid evaluation where someone looks up what the same kind of purchase cost last time. PPIP publishes notices and awards, not bid documents, so the agent stays on price history.

The stack is an MCP server with four tools, the official filesystem MCP server for the committee folder, LangGraph for the tool loop, and Qwen 2.5 3B running locally through Ollama.
