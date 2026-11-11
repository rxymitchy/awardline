# Awardline

Awardline prepares a value-for-money note for a Kenyan procuring entity. It compares a quote with published [Kenya PPIP](https://tenders.go.ke/ocds) awards, flags a price that is at least twice the median of similar awards, and drafts a committee note. A named officer approves the note before it is filed. The agent does not award a tender.

## Problem statement

A Kenyan procuring entity's evaluation committee has to judge whether a quote is reasonable before it recommends an award. The practical check is what similar purchases cost last time. That history is on the Public Procurement Information Portal, which publishes thousands of award notices, but an officer still searches titles by hand and writes down the contracts they compared. A price several times a recent award can pass because nobody lined the figures up.

## Solution overview

The officer gives the buyer, the purchase, the quoted amount, and, if known, the quoting supplier. The agent searches 4,956 Kenya PPIP awards from the 2025/2026 and 2026/2027 release files. It keeps awards in the same currency whose titles share at least two content words with the quote, where those shared words carry at least half of the description's weight. Rare words count for more than common ones, so a fuel quote is not compared with tyre contracts just because both say "motor vehicles". When at least four comparable awards exist, it compares the quote with their median. A quote at least twice that median is flagged. Each source is listed with its OCID, buyer, title, supplier, amount, date, the PPIP file it came from, and the words that matched. If the history is too thin, no flag is raised. When a supplier is named, the note also lists that firm's past PPIP awards, merging spellings such as `Ltd` and `Limited` and showing every name it merged. The agent then drafts a committee note from that flag. It cannot invent an OCID or an amount.

## Target users

Procurement officers and evaluation committees at Kenyan procuring entities that already publish on PPIP. The committee still decides. The public benefits when a high quote is questioned with cited awards.

## Architecture

One local agent sits in front of two MCP servers. Qwen 2.5 3B, through Ollama on the same machine, chooses each tool. The Awardline MCP server reads the PPIP snapshot and writes the flag and the draft. After a named officer approves, `file_committee_note` calls the official filesystem MCP server, which writes the note into `filings/`. Procurement records stay on the machine. A diagram of this path is in `docs/architecture.png`. See also `ARCHITECTURE.md`.

| Path | Role |
| --- | --- |
| `awardline/server.py` | Our MCP server |
| `awardline/agent.py` | LangGraph loop over Qwen 2.5 |
| `awardline/drop.py` | Filing, via `@modelcontextprotocol/server-filesystem` |
| `awardline/score.py` | Comparable awards, median, and supplier history |
| `awardline/snapshot.py` | Downloads PPIP packages and builds the snapshot |
| `data/awards.json` | PPIP awards used by the tools |
| `logs/tool_calls.jsonl` | Every tool call, approval, and file write |
| `ARCHITECTURE.md` | How the pieces connect |
| `EVALS.md` | Evaluation tasks and results |

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

Other commands: `python -m awardline serve` starts the Awardline MCP server on stdio, `python -m awardline eval` runs the evaluation tasks, and `python -m awardline refresh` downloads the current PPIP release packages and rebuilds `data/awards.json`. A failed download leaves the last good snapshot in place. Each note states how many awards the snapshot holds and when it was downloaded.

## Technology stack

Python, the MCP Python SDK, LangGraph, httpx, Pydantic, and pytest. Node.js runs `@modelcontextprotocol/server-filesystem`. The model is Qwen 2.5 3B through Ollama's local chat API. Awards, flags, drafts, and approvals are JSON files. There is no database server and no hosted model.

## Agent architecture

Awardline is a single agent. Working memory is the message list LangGraph keeps for the current quote. `plan` asks Qwen for the next action. `tools` sends that call to the Awardline MCP server over stdio and appends the result, including errors. The loop returns to `plan` until the model stops or eight steps pass. An unknown tool name, an empty search, a quoted amount that does not match the request, and a supplier that the request names but the call leaves out or changes all come back so the model can try again. A different spelling of the same supplier is accepted. The model is told to stop when the draft exists.

Qwen 2.5 3B runs on CPU with a 4,096-token context. The model sees a short summary of each tool result: the note ID, whether the quote was flagged, the median, the ratio, and how many comparables and past supplier awards were found. The full result, with every source, stays in the graph state and the log, and the note is built from the saved flag, so nothing the committee reads passes through the model.

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

`flag_price_outlier` and `draft_committee_note` take an optional `supplier`. `draft_committee_note` refuses when no flag exists for the same buyer, description, amount, and supplier. A flag needs at least four awards in the same currency that share two content words with the quote, carrying at least half of the description's word weight. The quote is flagged when it is at least twice their median.

The server we did not write is `@modelcontextprotocol/server-filesystem`. It can see only `filings/`. We use it because the directory allow-list is already its job.

## Human-in-the-loop workflow

1. The officer states the quote.
2. The agent searches, flags, and drafts. It does not award the tender.
3. Filing is refused until `runtime/approvals/<note_id>.json` contains `decision: approve`, a human officer's name, and the revision of the current draft. Each draft gets a new revision, so an approval does not carry over when the agent drafts the same quote again.
4. The officer runs `python -m awardline approve --note-id <id> --officer "<name>"`. That command is not a tool the model can call. Names shorter than 3 characters, and the names `agent`, `awardline`, and `model`, are rejected. The log line has `"actor": "human"`.
5. `python -m awardline file --note-id <id>` calls the filesystem MCP server, which writes `filings/<note_id>.md`.

## Limitations

- Award amounts have no unit. The 2025/2026 and 2026/2027 PPIP packages contain no line items, quantities, or units, so the median compares contract totals. Every note says so, and lists the words that matched each source so the committee can drop one that is a different size of purchase.
- There is no budget or unpaid-invoice check. Those packages contain no budgets and no payments.
- Title matching is better but not perfect. Weighting words by rarity keeps a fuel quote away from tyre contracts, but two titles can still share rare words and describe different purchases. Every note states that a past award may itself have been overpriced.
- Supplier matching ignores only case, punctuation, a leading `M/S`, a trailing postal address, and `Ltd`, `Limited`, `Co`, `Company`, and `PLC`. It does not merge `(K)` or `Kenya` variants, or abbreviations such as `Intl`, because those can be different firms. Supplier history is shown for context. It never raises or removes a price flag.
- The snapshot only changes when someone runs `python -m awardline refresh`. A run does not call the PPIP portal.
- A small model can drop a zero on the quoted amount or leave out the supplier. The graph rejects that call and asks for the amount or supplier in the request.

## Future improvements

- If PPIP starts publishing quantities and units, compare unit prices instead of contract totals.
- Use a supplier's KRA PIN as the matching key if PPIP starts publishing it, instead of the name.
- Let the officer exclude a source from the note and record who excluded it and why.
