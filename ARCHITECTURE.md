# Architecture

Awardline is a LangGraph loop in front of two MCP servers. Qwen 2.5 3B, via Ollama on this machine, chooses the next tool. Procurement records are not sent to a hosted model.

## Agent

`awardline/agent.py` compiles a two-node graph. `plan` calls Qwen with the tool list. `tools` sends each call to the Awardline MCP server over stdio and appends the result, including errors. The graph goes back to `plan` until the model stops or eight steps pass. An unknown tool name, an empty search, and a quoted amount that does not match the request all come back as errors so the model can try again. Tool calls made through the server are logged with `"actor": "mcp"`. The model is told to stop when the draft exists, and that filing will be refused until an officer approves.

## MCP server we wrote

`awardline/server.py` exposes four tools:

| Tool | Effect |
| --- | --- |
| `search_awards` | Reads the PPIP snapshot |
| `flag_price_outlier` | Writes a sourced flag under `runtime/flags/` |
| `draft_committee_note` | Writes a draft whose citations are copied from that flag |
| `file_committee_note` | Files the note, or refuses |

`draft_committee_note` will not invent a source. If `flag_price_outlier` has not been called for the same buyer, description, and amount, the draft is refused. A flag needs at least four awards that share two content words with the quote and use the same currency. The quote is flagged when it is at least twice their median.

## MCP server we did not write

Filing calls `@modelcontextprotocol/server-filesystem` and allows it to see only `filings/`. If `npm install` has put that package in `node_modules`, Awardline runs that copy. Otherwise it uses `npx`. We use that server because the directory allow-list is already its job. A write path outside `filings/` is that server's problem to reject, rather than a second check we would have to keep correct.

`file_committee_note` does not call it unless `runtime/approvals/<note_id>.json` contains `decision: approve` and a human officer's name. The approval record is written by `python -m awardline approve`, which is not a tool the model can call. The log line for that step has `"actor": "human"`.

## Log

Every tool call, the human approval, and the filesystem write are appended to `logs/tool_calls.jsonl` with inputs, outputs, a timestamp, and whether it succeeded.
