# Demo Video Checklist

## Before recording

- [ ] Ollama is running: `ollama serve` (or check system tray)
- [ ] Model is pulled: `ollama pull qwen2.5:3b`
- [ ] Web server is running: `.\start_web.ps1`
- [ ] Browser is open at http://localhost:8000
- [ ] Clear any old filings if you want a clean demo: `Remove-Item filings\*.md`
- [ ] Screen recording software ready (OBS, Loom, QuickTime, etc.)
- [ ] Microphone works if you're narrating

## Recording: Web UI flow (90 seconds)

**Show the agent in the loop — this is the 30-point judging criterion.**

### 1. Login (5 sec)
- Navigate to http://localhost:8000
- Enter your name: "Amina Yusuf"
- Click "Sign in"
- **Say**: "Officers sign in with their name — this ties approvals to a real person."

### 2. Check a quote form (10 sec)
- Click "Check a quote"
- Fill the form:
  - Buyer: `Nairobi City County`
  - Item: `Supply and delivery of office furniture`
  - Amount: `1,250,000`
  - Supplier: `Kioli Investments Limited`
- **Say**: "The form just captures structured data. The agent does the work."
- Click "Start agent analysis"

### 3. Progress screen — **KEY MOMENT** (30 sec)
- **Show tool calls appearing in real time:**
  - ✓ search_awards
  - ✓ flag_price_outlier
  - ✓ draft_committee_note
- **Say**: "The LangGraph agent plans tool calls, searches PPIP contracts, flags outliers, checks supplier history, and drafts the note. Same agent as the CLI demo. This takes 2-3 minutes on Qwen 2.5 3B."
- **Wait for "Analysis complete!"** — do NOT cut this short, judges need to see the agent working

### 4. Results page (30 sec)
- **Verdict banner** appears (FLAG / NO FLAG / INSUFFICIENT DATA)
- Scroll down to show:
  - **Agent tool calls** card (proves it ran the agent)
  - Quote details (buyer, item, amount, median, ratio)
  - Comparable contracts (OCIDs, amounts, suppliers, matched words)
  - Supplier history table
  - Full committee note text
- **Say**: "Every source has an OCID. The agent cites its findings. No unsourced flags."

### 5. Approve & file (10 sec)
- Click "Approve as Amina Yusuf"
- Status badge changes to "✔ Approved by Amina Yusuf"
- Click "File to committee folder"
- **Say**: "Approval gate. A named officer must approve before filing."

### 6. Filed notes list (5 sec)
- Redirects to "Filed Notes"
- Table shows the note just filed
- **Say**: "All filed notes in one place. The committee's audit trail."

## Recording: CLI agent demo (optional, 30 seconds)

If you have time, show the CLI too:

```powershell
.\.venv\Scripts\python -m awardline demo
```

- Terminal output shows tool calls, model thinking, final note
- **Say**: "CLI and web UI run the same agent. Both show tool calls. Both cite sources."

## What to emphasize

### For "Agentic depth and MCP craft" (30 points)

- ✅ **"The agent plans tool calls"** — show progress screen with tools appearing
- ✅ **"Not a chatbot"** — say "the agent searches, flags, drafts — multi-step autonomous work"
- ✅ **"Retries on error"** — mention "if a tool fails, the agent corrects itself and retries"
- ✅ **"MCP servers"** — say "our MCP server (search, flag, draft) + filesystem MCP (file write)"

### For "Fit to the tender cycle" (20 points)

- ✅ **"Procurement officers don't type natural language"** — form does it for them
- ✅ **"Named officer approval"** — show the approval step
- ✅ **"Committee audit trail"** — show filed notes list

### For "Defensibility" (10 points)

- ✅ **"Every finding has an OCID"** — point to the sources on results page
- ✅ **"Tool call log"** — say "every action is logged with timestamp and inputs/outputs"
- ✅ **"Approval on record"** — show officer name on note

## What NOT to do

❌ Skip the progress screen — judges need to see the agent working  
❌ Cut to results instantly — looks like you faked it  
❌ Say "it's fast" — it's not, and that's okay (2-3 min is realistic for local models)  
❌ Hide tool calls — that's the main judging criterion  
❌ Use slides — demo says "unedited agent run with tool calls on screen"

## Technical details to mention

- **Model**: Qwen 2.5 3B via Ollama (open-weights, runs locally)
- **Orchestration**: LangGraph (open-source, not a closed builder)
- **MCP**: Our server (search/flag/draft) + filesystem server (file write)
- **Data**: 4,956 Kenya PPIP awards from 2025/2026 and 2026/2027 release files
- **Audit log**: Every tool call in `logs/tool_calls.jsonl` with timestamp and actor

## After recording

- [ ] Upload to YouTube or Vimeo, set to Public
- [ ] Check video is under 3 minutes
- [ ] Add title: "Awardline: Agentic value-for-money checks for Kenya PPIP"
- [ ] Add description with repo link
- [ ] Test the link works in an incognito window

## Backup plan

If Ollama is slow or crashes during recording:

1. Record the web flow up to "Start agent analysis"
2. Record the CLI demo instead: `python -m awardline demo`
3. Then record the results page (visit a note you drafted earlier)
4. Edit the three clips together

The judges want to see tool calls happening. CLI output is just as valid as web UI progress screen.

## Final check

- [ ] Video shows agent planning tool calls (not a direct API call)
- [ ] Video shows tool output with OCIDs and sources
- [ ] Video shows approval gate with officer name
- [ ] Video is unedited (no cuts during agent run)
- [ ] Video is under 3 minutes
- [ ] Repo link in video description
