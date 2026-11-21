# Awardline

Awardline prepares a value-for-money note for a Kenyan procuring entity. It compares a quote with published [Kenya PPIP](https://tenders.go.ke/ocds) awards, flags a price that is at least twice the median of similar awards, and drafts a committee note. A named officer approves the note before it is filed. The agent does not award a tender.

**Two interfaces:**
- **CLI** — give it a task in natural language, watch it plan, call tools, retry on errors, and draft a note
- **Web UI** — same agent, form-driven; officer fills buyer/item/amount, agent runs in background, results appear when ready

Both use the same LangGraph agent. The web form constructs the task string for the agent.

## How it works

The officer provides the buyer, the purchase description, the quoted amount, and optionally the quoting supplier. The agent searches Kenya PPIP awards from the 2025/2026 and 2026/2027 release files. It keeps awards in the same currency whose titles share at least two content words with the quote, where those shared words carry at least half of the description's weight. Rare words count more than common ones, so a fuel quote is not compared with tyre contracts just because both mention "motor vehicles."

When at least four comparable awards exist, it compares the quote with their median. A quote at least twice that median is flagged. Each source is listed with its OCID, buyer, title, supplier, amount, date, source file, and the words that matched. When a supplier is named, the note also shows that firm's past PPIP awards, merging name variants like `Ltd` and `Limited`. The agent then drafts a committee note from that flag. It cannot invent an OCID or an amount — all citations come from the saved flag file, not from model output.

Each officer's notes are independent: two officers checking the same quote each get their own draft, approval, and filing.

## Architecture

| Path | Role |
|---|---|
| `awardline/server.py` | Awardline MCP server |
| `awardline/agent.py` | LangGraph loop |
| `awardline/drop.py` | Filing to committee folder |
| `awardline/score.py` | Comparable awards, median, supplier history |
| `awardline/snapshot.py` | Downloads PPIP packages and builds the snapshot |
| `web/app.py` | FastAPI web UI |
| `web/templates/` | Jinja2 templates |
| `data/awards.json` | PPIP awards snapshot |
| `runtime/logs/tool_calls.jsonl` | Every tool call, approval, and file write |
| `ARCHITECTURE.md` | How the pieces connect |
| `EVALS.md` | Evaluation tasks and results |

One local agent sits in front of two MCP servers. The agent (via Ollama or Groq) chooses each tool. The Awardline MCP server reads the PPIP snapshot and writes flags and drafts. After a named officer approves, `file_committee_note` writes the note into `runtime/filings/`. See `ARCHITECTURE.md` for a full diagram.

## Setup

Requires [Ollama](https://ollama.com) with `qwen2.5:3b` pulled, or a Groq API key.

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

`npm install` fetches `@modelcontextprotocol/server-filesystem`. Python dependencies are `mcp`, `langgraph`, `httpx`, `pydantic`, and `pytest`.

**To use Groq instead of Ollama**, copy `.env.example` to `.env` and add your `GROQ_API_KEY`.

## Usage

### Web UI

```powershell
.\start_web.ps1
```

Open [http://localhost:8000](http://localhost:8000).

1. Sign in with your name
2. Fill the form — buyer, item, amount, and optionally the supplier
3. Watch the agent work — tool calls appear as it searches PPIP, compares prices, and drafts the note
4. Review the verdict, sources, and committee note
5. Click **Approve & File** to record your approval and file the note

Each officer only sees notes they approved. Notes filed by other officers are not visible.

### CLI

```powershell
.\.venv\Scripts\python -m awardline demo
```

To file the note, approve it with a named officer:

```powershell
.\.venv\Scripts\python -m awardline demo --approve --officer "Amina Yusuf"
```

Approve and file an existing note separately:

```powershell
.\.venv\Scripts\python -m awardline approve --note-id <note_id> --officer "Amina Yusuf"
.\.venv\Scripts\python -m awardline file --note-id <note_id>
```

Other commands:
- `python -m awardline serve` — start the Awardline MCP server on stdio
- `python -m awardline eval` — run evaluation tasks
- `python -m awardline refresh` — download the current PPIP release packages and rebuild `data/awards.json`

## MCP tools

Awardline exposes four tools:

| Tool | Effect |
|---|---|
| `search_awards` | Reads the PPIP snapshot |
| `flag_price_outlier` | Writes a sourced flag under `runtime/flags/` |
| `draft_committee_note` | Writes a draft whose citations are copied from the flag |
| `file_committee_note` | Files the note, or refuses until an officer has approved it |

`flag_price_outlier` and `draft_committee_note` accept optional `supplier` and `officer` parameters. `draft_committee_note` refuses when no flag exists for the same buyer, description, amount, supplier, and officer. The official `@modelcontextprotocol/server-filesystem` server handles the actual file write to `runtime/filings/`; Awardline falls back to a direct write if the MCP subprocess cannot be spawned.

## Human-in-the-loop

1. The officer states the quote.
2. The agent searches, flags, and drafts. It does not award the tender.
3. Filing is refused until `runtime/approvals/<note_id>.json` contains `decision: approve`, the officer's name, and the revision of the current draft. Each draft gets a new revision, so an older approval does not carry forward.
4. The officer approves through the web UI or the CLI `approve` command. Names shorter than 3 characters, and the reserved names `agent`, `awardline`, and `model`, are rejected. The log records `"actor": "human"`.
5. `file_committee_note` writes `runtime/filings/<note_id>.md`.

## Technology stack

Python, MCP Python SDK, LangGraph, httpx, Pydantic, pytest. Node.js runs `@modelcontextprotocol/server-filesystem`. The model is Qwen 2.5 3B through Ollama, or any Groq-hosted model via `GROQ_API_KEY`. Awards, flags, drafts, and approvals are JSON files. No database server. No hosted model required.

## Limitations

- **No unit prices.** PPIP awards show contract totals only, not quantities or units. The median compares total contract values. Every note says so and lists the words that matched each source.
- **No budget or payment data.** PPIP packages contain neither budgets nor payment records.
- **Title matching is approximate.** Two titles can share rare words while describing different purchases. Every note states that a past award may itself have been overpriced.
- **Supplier matching is fuzzy but not universal.** Case, punctuation, a leading `M/S`, trailing postal addresses, and `Ltd/Limited/Co/Company/PLC` are ignored. Variants like `(K)` or `Intl` are not merged because they can be different firms.
- **Snapshot is static.** It only updates when someone runs `python -m awardline refresh`.

## Future work

- Compare unit prices if PPIP adds quantities and units.
- Use KRA PIN as the supplier matching key if PPIP publishes it.
- Let officers exclude a source from a note and record the reason.
