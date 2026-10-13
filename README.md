# Awardline

Awardline prepares a value-for-money note for a Kenyan procuring entity. It compares a quote with published [Kenya PPIP](https://tenders.go.ke/ocds) awards, flags a price that is at least twice the median of similar awards, and drafts a committee note. A named officer approves the note before it is filed. The agent does not award a tender.

## Problem statement

A Kenyan procuring entity's evaluation committee has to judge whether a quote is reasonable before it recommends an award. The practical check is what similar purchases cost last time. That history is on the Public Procurement Information Portal, which publishes thousands of award notices, but an officer still searches titles by hand and writes down the contracts they compared. A price several times a recent award can pass because nobody lined the figures up.

## Solution overview

The officer gives the buyer, the purchase, and the quoted amount. The agent searches 4,956 Kenya PPIP awards from the 2025/2026 and 2026/2027 release files. It keeps awards in the same currency whose titles share at least two content words with the quote. When at least four of those exist, it compares the quote with their median. A quote at least twice that median is flagged. Each source is listed with its OCID, buyer, title, amount, date, and the PPIP file it came from. If the history is too thin, no flag is raised. The agent then drafts a committee note from that flag. It cannot invent an OCID or an amount.

## Target users

Procurement officers and evaluation committees at Kenyan procuring entities that already publish on PPIP. The committee still decides. The public benefits when a high quote is questioned with cited awards.

## Architecture

One local agent sits in front of two MCP servers. Qwen 2.5 3B, through Ollama on the same machine, chooses each tool. The Awardline MCP server reads the PPIP snapshot and writes the flag and the draft. After a named officer approves, `file_committee_note` calls the official filesystem MCP server, which writes the note into `filings/`. Procurement records stay on the machine. A diagram of this path is in `docs/architecture.png`. See also `ARCHITECTURE.md`.

| Path | Role |
| --- | --- |
| `awardline/server.py` | Our MCP server |
| `awardline/agent.py` | LangGraph loop over Qwen 2.5 |
| `awardline/drop.py` | Filing, via `@modelcontextprotocol/server-filesystem` |
| `data/awards.json` | PPIP awards used by the tools |
| `logs/tool_calls.jsonl` | Every tool call, approval, and file write |
| `ARCHITECTURE.md` | How the pieces connect |
| `EVALS.md` | Test tasks, including the one we did not fix |

## Setup/installation instructions

From this directory, after [Ollama](https://ollama.com) is installed and `ollama pull qwen2.5:3b` has finished:

```powershell
npm install; python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt; .\.venv\Scripts\python -m awardline demo
```

`npm install` fetches `@modelcontextprotocol/server-filesystem`. The Python packages are `mcp`, `langgraph`, `httpx`, `pydantic`, and `pytest`.

## Usage instructions

The demo picks a real purchase that has at least four comparable awards, asks Qwen 2.5 3B to check a quote at four times the median, and prints the note. It does not file the note.

To file it, an officer has to be named:

```powershell
.\.venv\Scripts\python -m awardline demo --approve --officer "Amina Yusuf"
```

Approve and file an existing note separately:

```powershell
.\.venv\Scripts\python -m awardline approve --note-id note-505b1626d7 --officer "Amina Yusuf"
.\.venv\Scripts\python -m awardline file --note-id note-505b1626d7
```

Other commands: `python -m awardline serve` starts the Awardline MCP server on stdio, and `python -m awardline eval` runs the evaluation tasks.

## Technology stack

Python, the MCP Python SDK, LangGraph, httpx, Pydantic, and pytest. Node.js runs `@modelcontextprotocol/server-filesystem`. The model is Qwen 2.5 3B through Ollama's local chat API. Awards, flags, drafts, and approvals are JSON files. There is no database server and no hosted model.

## Agent architecture

Awardline is a single agent. Working memory is the message list LangGraph keeps for the current quote. `plan` asks Qwen for the next action. `tools` sends that call to the Awardline MCP server over stdio and appends the result, including errors. The loop returns to `plan` until the model stops or eight steps pass. An unknown tool name, an empty search, and a quoted amount that does not match the request all come back so the model can try again. The model is told to stop when the draft exists.

## MCP implementation

Both servers speak stdio. The LangGraph tools node is the MCP client: it starts `python -m awardline.server`, opens a client session, and calls the tool Qwen named. The result goes back to Qwen. Filing is a second hop. `file_committee_note` checks the approval file, then calls the filesystem server's `write_file` tool with an absolute path inside `filings/`. Awardline runs the copy in `node_modules` when `npm install` has put it there. Calls made through the Awardline server are logged with `"actor": "mcp"`. Neither server publishes MCP resources. These are tools only.

## MCP tools/servers

Awardline's own server exposes four tools:

| Tool | Effect |
| --- | --- |
| `search_awards` | Reads the PPIP snapshot |
| `flag_price_outlier` | Writes a sourced flag under `runtime/flags/` |
| `draft_committee_note` | Writes a draft whose citations are copied from that flag |
| `file_committee_note` | Files the note, or refuses |

`draft_committee_note` refuses when no flag exists for the same buyer, description, and amount. A flag needs at least four awards that share two content words with the quote and use the same currency. The quote is flagged when it is at least twice their median.

The server we did not write is `@modelcontextprotocol/server-filesystem`. It can see only `filings/`. We use it because the directory allow-list is already its job.

## Human-in-the-loop workflow

1. The officer states the quote.
2. The agent searches, flags, and drafts. It does not award the tender.
3. Filing is refused until `runtime/approvals/<note_id>.json` contains `decision: approve` and a human officer's name.
4. The officer runs `python -m awardline approve --note-id <id> --officer "<name>"`. That command is not a tool the model can call. Names shorter than 3 characters, and the names `agent`, `awardline`, and `model`, are rejected. The log line has `"actor": "human"`.
5. `python -m awardline file --note-id <id>` calls the filesystem MCP server, which writes `filings/<note_id>.md`.

## Limitations

- Supplier names that differ only by `Ltd` and `Limited` are not treated as the same firm. See `EVALS.md` task T9. That failure is left unfixed on purpose.
- Award amounts have no unit. The 2025/2026 and 2026/2027 PPIP packages contain no line items, quantities, or units, so a per-litre price and a lump-sum contract can be compared when their titles share two words.
- There is no budget or unpaid-invoice check. Those packages contain no budgets and no payments.
- Title matching can include a loosely related award. A fuel contract and a tyre contract can both match on "motor vehicles".
- The snapshot is downloaded once. A run does not call the PPIP portal again.
- A small model can drop a zero on the quoted amount. The graph rejects that call and asks for the amount in the request.

## Future improvements

- Strip `Ltd`, `Limited`, and `Company` before comparing supplier names, then check the result against known pairs before using it in a finding. That is the next attempt for T9. It is not done here, because a bad merge would attach a price flag to the wrong firm.
- Show the shared words that caused each past award to be included, and state on the note that a past award may itself have been high.
- If PPIP starts publishing quantities and units, compare unit prices instead of lump sums.
