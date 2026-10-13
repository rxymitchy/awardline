# Awardline

Awardline prepares a value-for-money note for a Kenyan procuring entity. It compares a quote with published [Kenya PPIP](https://tenders.go.ke/ocds) awards, flags a price that is at least twice the median of similar awards, and drafts a committee note. A named officer approves the note before it is filed. The agent does not award a tender.

The snapshot in `data/awards.json` is 4,956 awards with a price, taken from the PPIP release packages `2025-2026.json` and `2026-2027.json`. PPIP does not publish bid documents, budgets, or invoice payments, so those checks are out of scope.

## Run

One command, from this directory, after [Ollama](https://ollama.com) is installed and `ollama pull qwen2.5:3b` has finished:

```powershell
npm install; python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt; .\.venv\Scripts\python -m awardline demo
```

The demo picks a real purchase that has at least four comparable awards, asks Qwen 2.5 3B to check a quote at four times the median, and prints the note. It does not file the note.

To file it, an officer has to be named:

```powershell
.\.venv\Scripts\python -m awardline demo --approve --officer "Amina Yusuf"
```

The note is written by the official filesystem MCP server into `filings/`. Every tool call is appended to `logs/tool_calls.jsonl`.

## What is unfinished

- Supplier names that differ only by `Ltd` and `Limited` are not treated as the same firm. See `EVALS.md` task T9.
- Award amounts have no unit. A per-litre price and a lump-sum contract can be compared if their titles share two words.
- There is no budget or unpaid-invoice check. PPIP does not publish those figures.

## Layout

| Path | Role |
| --- | --- |
| `awardline/server.py` | Our MCP server |
| `awardline/agent.py` | LangGraph loop over Qwen 2.5 |
| `awardline/drop.py` | Filing, via `@modelcontextprotocol/server-filesystem` |
| `data/awards.json` | PPIP awards used by the tools |
| `ARCHITECTURE.md` | How the pieces connect |
| `EVALS.md` | Test tasks, including the one we did not fix |
