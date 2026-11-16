# Web UI Architecture: Agent in the Loop

## Design principle

**The agent is never bypassed.** Every quote analysis runs through the full LangGraph agent (`run_agent()`), which plans tool calls, retries on error, and drafts the note. The web form simply constructs the task string for the officer — it doesn't call tools directly.

## Request flow

```
┌──────────────────┐
│ Officer fills    │
│ web form:        │
│ • Buyer          │
│ • Item           │  Constructs natural-language task
│ • Amount         │ ──────────────────────────────────┐
│ • Supplier       │                                    │
└──────────────────┘                                    ▼
                                          ┌─────────────────────────────┐
                                          │ Task string:                │
                                          │ "Buyer X received a quote   │
                                          │ of KES Y from supplier Z    │
                                          │ for: <item>. Compare it     │
                                          │ with published past awards  │
                                          │ and draft a committee note."│
                                          └─────────────────────────────┘
                                                        │
                                                        ▼
                                          ┌─────────────────────────────┐
                                          │ run_agent(task, model)      │
                                          │ ← Same LangGraph function   │
                                          │   as CLI demo               │
                                          └─────────────────────────────┘
                                                        │
        ┌───────────────────────────────────────────────┼───────────────────────────┐
        │                                               │                           │
        ▼                                               ▼                           ▼
┌──────────────────┐                      ┌──────────────────────┐    ┌──────────────────────┐
│ Agent plans      │                      │ Agent calls tool     │    │ Tool returns error   │
│ tool sequence:   │                      │ via MCP:             │    │ → Agent retries with │
│ 1. search_awards │                      │ • search_awards      │    │ corrected arguments  │
│ 2. flag_price... │                      │ • flag_price_outlier │    │                      │
│ 3. draft_note    │                      │ • draft_committee... │    │ (Automatic recovery) │
└──────────────────┘                      └──────────────────────┘    └──────────────────────┘
                                                        │
                                                        ▼
                                          ┌─────────────────────────────┐
                                          │ Draft ready                 │
                                          │ → Note ID returned          │
                                          └─────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Results page shows:                                                     │
│ • Verdict (FLAG / NO FLAG / INSUFFICIENT DATA)                          │
│ • Agent tool history (✓ search_awards, ✓ flag_price_outlier, etc.)     │
│ • Median, ratio, comparable contracts with OCIDs                        │
│ • Supplier history                                                      │
│ • Full committee note text                                              │
│ • Approve button (tied to logged-in officer)                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Why this design

### Hackathon criterion: Agentic depth (30 points)

> Does the agent genuinely plan, call tools, and recover — or is it one model call in a loop?

- ✅ **Plans**: Agent chooses tool sequence from SYSTEM prompt + tool schemas
- ✅ **Calls tools**: Via MCP client in `agent.py` → `awardline/server.py`
- ✅ **Recovers**: Built-in retry logic when tools return errors (e.g. wrong amount)
- ✅ **Not a loop**: LangGraph StateGraph with conditional edges, not a for-loop

### What the web UI does NOT do

❌ Call `tool_flag_price_outlier()` directly  
❌ Call `tool_draft_committee_note()` directly  
❌ Hard-code a tool sequence  
❌ Skip the agent's planning step

### What the web UI DOES do

✅ Constructs a natural-language task string from form inputs  
✅ Calls `run_agent(task)` — the exact same function as the CLI  
✅ Polls agent status in the background  
✅ Shows tool calls in real time as they happen  
✅ Displays results when agent finishes

## Code comparison

### Before (hypothetical direct-tool-call approach — NOT what we built)

```python
# ❌ This bypasses the agent (bad for judging)
@app.post("/check")
async def check_submit(...):
    flag = tool_flag_price_outlier(buyer, query, amount, currency, supplier)
    draft = tool_draft_committee_note(buyer, query, amount, currency, supplier)
    return RedirectResponse(f"/note/{draft['note_id']}")
```

### After (what we actually built)

```python
# ✅ Agent plans, calls tools, recovers (good for judging)
@app.post("/check")
async def check_submit(...):
    task = f"Buyer {buyer} received a quote of KES {amount} from supplier {supplier} " \
           f"for: {item}. Compare it with published past awards and draft a " \
           f"value-for-money committee note. Do not award the tender."
    
    run_id = _start_agent_run(task)  # Calls run_agent() in background
    return RedirectResponse(f"/run/{run_id}")
```

## Agent state tracking

```python
agent_runs: Dict[str, dict] = {}

def _start_agent_run(task: str) -> str:
    run_id = uuid.uuid4().hex[:12]
    agent_runs[run_id] = {"status": "running", "task": task, "messages": [], "draft": None}
    
    async def _run():
        result = await asyncio.to_thread(run_agent, task, OllamaModel())
        agent_runs[run_id]["messages"] = result["messages"]
        agent_runs[run_id]["draft"] = result.get("draft")
        agent_runs[run_id]["status"] = "complete"
    
    asyncio.create_task(_run())
    return run_id
```

Progress page polls `/api/run/{run_id}/status` every 1.5 seconds. When `status == "complete"`, it redirects to the note page.

## Tool call visibility

The results page extracts tool calls from the agent's message history:

```python
tool_history = []
for msg in agent_run["messages"]:
    if msg.get("role") == "tool":
        tool_history.append({"name": msg["name"], "ok": msg["result"]["ok"]})
```

Displayed as badges:

```
Agent tool calls
The agent planned this sequence and recovered from any errors:
✓ search_awards
✓ flag_price_outlier
✓ draft_committee_note
```

## Production considerations (out of scope)

- Swap `agent_runs` dict for Redis/DB
- Use Server-Sent Events instead of polling
- Add WebSocket for streaming tool output
- Queue agent runs with Celery/RQ
- Add timeout handling (kill agent after 5 minutes)

## Summary for judges

| What | CLI | Web UI |
|------|-----|--------|
| Agent function | `run_agent(task, model)` | `run_agent(task, model)` ← **Same** |
| Task input | Typed by user | Constructed from form |
| Tool calls | Visible in terminal | Visible on progress page |
| Planning | LangGraph StateGraph | LangGraph StateGraph ← **Same** |
| Error recovery | Automatic retry | Automatic retry ← **Same** |
| Tool call log | `logs/tool_calls.jsonl` | `logs/tool_calls.jsonl` ← **Same** |
| Approval | `--officer "Name"` CLI flag | Session-based, tied to login |
| Filing | `python -m awardline file` | Click "File" button |

**Key point:** The web UI is a usability wrapper around the agent, not a replacement for it. Every form submission triggers a full agent run.
