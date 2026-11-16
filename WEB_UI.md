# Awardline Web UI

## What it does

The web interface wraps the existing LangGraph agent in a form-driven UI suitable for procurement officers. **The agent stays fully in the loop** — every quote analysis runs through `run_agent()`, which plans tool calls, retries on errors, and drafts the note.

## Why it matters for the hackathon

From the [judging criteria](https://agentic-africa-challenge.lovable.app/tracks/governance):

> **Agentic depth and MCP craft (30 points)**: Does the agent genuinely plan, call tools, and recover — or is it one model call in a loop?

The web UI preserves all agentic behavior:
- ✅ Agent plans the tool sequence (search → flag → draft)
- ✅ Agent retries when a tool returns an error
- ✅ Agent nudges itself forward if it stops before drafting
- ✅ All tool calls logged and visible in real time
- ✅ Same LangGraph state machine as the CLI demo

## Flow

```
Officer fills form → Task string constructed → run_agent(task) starts
                                                      ↓
                                         Agent running in background
                                                      ↓
                                      Progress page polls /api/run/{id}/status
                                                      ↓
                                         Tool calls appear as badges:
                                         ✓ search_awards
                                         ✓ flag_price_outlier
                                         ✓ draft_committee_note
                                                      ↓
                                         Redirect to /note/{note_id}
                                                      ↓
                          Results page shows verdict, sources, tool history
                                                      ↓
                                    Officer clicks Approve → File
                                                      ↓
                                      Note lands in filings/ folder
```

## Key files

| File | What it does |
|------|-------------|
| `web/app.py` | FastAPI routes — `/check` constructs task and calls `run_agent()` in background |
| `web/templates/progress.html` | Polls agent status API, shows tool calls in real time |
| `web/templates/note.html` | Results page with verdict, sources, tool history, approve/file controls |
| `web/templates/login.html` | Session auth — officer name → approval audit trail |
| `start_web.ps1` | One-command startup |

## Technical decisions

### Agent in the loop, not bypassed
The form doesn't call the tools directly — it constructs a natural-language task string like:

> "Buyer Nairobi City County received a quote of KES 1,250,000 from supplier Kioli Investments Limited for: Supply and delivery of office furniture. Compare it with published past awards and draft a value-for-money committee note. Do not award the tender."

Then it calls `run_agent(task, OllamaModel())` — the exact same function the CLI uses.

### Async background execution
Uses `asyncio.create_task()` + in-memory run tracking. The progress page polls `/api/run/{run_id}/status` every 1.5 seconds and redirects when status changes to `complete`.

In production, swap the dict for Redis/DB and use Server-Sent Events for real-time updates.

### Session-based approval
Officer name stored in signed session cookie (via `SessionMiddleware` + `itsdangerous`). When they click Approve, `record_approval(note_id, officer)` logs their name — no `--officer "..."` flag needed.

### Same audit log
Every tool call (search, flag, draft, file) goes through `log_call()` and lands in `logs/tool_calls.jsonl`, just like the CLI.

## Start it

```powershell
.\start_web.ps1
```

Then open http://localhost:8000

Default port is 8000. To change: `.\start_web.ps1 -Port 8080`

## Demo flow for video

1. Navigate to http://localhost:8000
2. Sign in as "Amina Yusuf"
3. Click "Check a quote"
4. Fill the form:
   - **Buyer**: Nairobi City County
   - **Item**: Supply and delivery of office furniture
   - **Amount**: 1,250,000
   - **Supplier**: Kioli Investments Limited
5. Click "Start agent analysis"
6. **Progress screen** shows tool calls appearing:
   - ✓ search_awards
   - ✓ flag_price_outlier
   - ✓ draft_committee_note
7. **Results page** loads:
   - Verdict banner (FLAG / NO FLAG / INSUFFICIENT DATA)
   - Quote details, median, ratio
   - Agent tool history card
   - Comparable contracts (source OCIDs, amounts, suppliers)
   - Supplier history (past PPIP awards)
   - Full committee note text
8. Click "Approve as Amina Yusuf"
9. Status changes to "✔ Approved by Amina Yusuf"
10. Click "File to committee folder"
11. Note lands in `filings/note-abc123def4.md`
12. Navigate to "Filed Notes" — see table of all filed notes
13. Click "View" on the note — see full text with approval metadata

## How it scores against judging criteria

| Criterion | How the web UI addresses it |
|-----------|---------------------------|
| **Agentic depth and MCP craft (30 pts)** | Runs `run_agent()` — same LangGraph loop that plans tool sequence, retries on error, nudges itself forward. Not a direct tool call. Tool history visible on results page. |
| **Open-source rigour (20 pts)** | Web code in `web/` folder, documented in README. One command to start: `.\start_web.ps1` |
| **Fit to the tender cycle (20 pts)** | Form-driven for officers who don't type natural language, but agent still does the work. Approval tied to logged-in officer. |
| **Evaluation and reliability (15 pts)** | Same agent, same evals. Web UI doesn't change the agent logic. |
| **Defensibility (10 pts)** | Every tool call logged. Officer name on approval. Full source citations in note. |
| **Demo (5 pts)** | Progress screen shows tool calls happening. Results page shows agent planned the sequence. |

## Production considerations (out of scope for hackathon)

- Swap in-memory `agent_runs` dict for Redis or database
- Use Server-Sent Events instead of polling for real-time tool call updates
- Replace session middleware with organisation SSO (SAML, OIDC)
- Add proper error recovery UI when Ollama is down
- Rate-limit agent runs per user
- Queue long-running agents with Celery/RQ
- Add WebSocket for live tool output streaming
