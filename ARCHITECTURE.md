# Architecture

Awardline is a LangGraph loop in front of two MCP servers. Qwen 2.5 3B, via Ollama on this machine, chooses the next tool. Procurement records are not sent to a hosted model.

## Agent

`awardline/agent.py` compiles a two-node graph. `plan` calls Qwen with the tool list. `tools` sends each call to the Awardline MCP server over stdio and appends the result, including errors. The graph goes back to `plan` until the model stops or eight steps pass. An unknown tool name, an empty search, a quoted amount that does not match the request, and a named supplier the call leaves out all come back as errors, with a `retry_with` corrected call, so the model can try again. If the model stops before a draft exists, a `nudge` node reminds it to continue, at most twice. The model sees a compact summary of each successful result (`for_model` in `agent.py`), so a long list of sources does not overflow Qwen's 4,096-token context; the full result stays in the graph state. Tool calls made through the server are logged with `"actor": "mcp"`. The model is told to stop when the draft exists, and that filing will be refused until an officer approves.

## MCP server we wrote

`awardline/server.py` exposes four tools:

| Tool | Effect |
| --- | --- |
| `search_awards` | Reads the PPIP snapshot |
| `flag_price_outlier` | Writes a sourced flag under `runtime/flags/` |
| `draft_committee_note` | Writes a draft whose citations are copied from that flag |
| `file_committee_note` | Files the note, or refuses |

`draft_committee_note` will not invent a source. If `flag_price_outlier` has not been called for the same buyer, description, amount, and supplier, the draft is refused. A flag needs at least four awards in the same currency that share two content words with the quote, where those words carry at least half of the description's weight. Words are weighted by how rare they are in the snapshot (`awardline/score.py`). The quote is flagged when it is at least twice their median. When a supplier is named, the flag also carries that firm's past awards, matched by `supplier_key` in `awardline/awards.py`, with every merged spelling listed on the note.

## MCP server we did not write

Filing calls `@modelcontextprotocol/server-filesystem` and allows it to see only `filings/`. If `npm install` has put that package in `node_modules`, Awardline runs that copy. Otherwise it uses `npx`. We use that server because the directory allow-list is already its job. A write path outside `filings/` is that server's problem to reject, rather than a second check we would have to keep correct.

`file_committee_note` does not call it unless `runtime/approvals/<note_id>.json` contains `decision: approve`, a human officer's name, and the revision of the current draft. Every draft gets a new revision, so an approval covers only the draft the officer saw. The approval record is written by `python -m awardline approve`, which is not a tool the model can call. The log line for that step has `"actor": "human"`.

## Log

Every tool call, the human approval, and the filesystem write are appended to `logs/tool_calls.jsonl` with inputs, outputs, a timestamp, and whether it succeeded.

## Snapshot

`python -m awardline refresh` (`awardline/snapshot.py`) downloads the PPIP release packages, checks each one parses before it replaces the old copy, and rebuilds `data/awards.json` with a `retrieved_at` time. Each note states the snapshot size and that time.
