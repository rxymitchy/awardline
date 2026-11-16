# Quick Web UI Test Guide

## Prerequisites

1. Ollama is running: `ollama serve` (or check system tray)
2. Model is ready: `ollama pull qwen2.5:3b`

## Start the server

```powershell
.\start_web.ps1
```

Wait for: `Uvicorn running on http://0.0.0.0:8000`

## Test 1: Login flow

1. Open http://localhost:8000
2. Should redirect to `/login`
3. Enter name: `Test Officer`
4. Click "Sign in"
5. Should redirect to home page showing "Test Officer" in header

**Expected**: Signed in, name in header pill

## Test 2: Check a quote (simple case)

From the home page:

1. Click "Check a quote"
2. Fill form:
   - **Buyer**: `Nairobi City County`
   - **Item**: `Supply of office furniture`
   - **Amount**: `500000` (or `500,000`)
   - **Supplier**: (leave blank)
3. Click "Start agent analysis"
4. Progress page loads:
   - Shows: "Agent is working..."
   - Shows the task string
   - Wait for tool calls to appear:
     - ✓ search_awards
     - ✓ flag_price_outlier
     - ✓ draft_committee_note
5. After 2-3 minutes: "Analysis complete!" → redirects
6. Results page shows:
   - Verdict banner (FLAG / NO FLAG / INSUFFICIENT DATA)
   - Quote details
   - Agent tool calls card
   - Comparable contracts (if any)
   - Full committee note

**Expected**: Agent completes, draft appears, sources cited

## Test 3: Approve and file

From the results page:

1. Review the note
2. Click "Approve as Test Officer"
3. Status changes to "✔ Approved by Test Officer"
4. Click "File to committee folder"
5. Redirects to "Filed Notes" page
6. Table shows the note just filed

**Expected**: Note filed, appears in filings list

## Test 4: View filed notes

1. Click "Filed Notes" in header
2. Table shows all filed notes
3. Click "View" on any note
4. Full note text appears with approval metadata

**Expected**: Filed notes are readable

## Test 5: Logout

1. Click "Log out" in header
2. Session cleared, redirects to `/login`
3. Try visiting `/check` directly
4. Should redirect to `/login`

**Expected**: Protected routes require login

## Verify audit log

```powershell
Get-Content logs\tool_calls.jsonl | Select-Object -Last 20
```

Should show JSON lines with:
- `"tool": "search_awards"`
- `"tool": "flag_price_outlier"`
- `"tool": "draft_committee_note"`
- `"tool": "file_committee_note"`
- `"actor": "agent"` for tool calls
- `"actor": "human"` for approvals

**Expected**: All actions logged

## Verify filings folder

```powershell
Get-ChildItem filings
```

Should show `note-*.md` files.

```powershell
Get-Content filings\note-*.md | Select-Object -First 30
```

Should show committee note text with:
- Buyer, purchase, amount
- Verdict (FLAG / NO FLAG)
- Sources with OCIDs
- Supplier history (if applicable)

**Expected**: Filed notes are valid markdown

## Common issues

### "Connection refused" when opening http://localhost:8000

- Check server is running: look for "Uvicorn running..." in terminal
- Try http://127.0.0.1:8000 instead
- Restart server: `.\start_web.ps1`

### Progress page stuck on "Agent is working..."

- Check Ollama is running: `ollama list` should show `qwen2.5:3b`
- Check server terminal for errors
- Wait longer (first run can take 4-5 minutes)

### "Internal Server Error" on any page

- Check server terminal output for Python traceback
- Likely: template error or missing context variable
- Report the full error

### Agent fails with "Model not found"

```powershell
ollama pull qwen2.5:3b
```

Then restart the web server.

### Form validation errors

- Amount must be a positive number
- Buyer and Item are required
- Supplier is optional

## Performance notes

- First agent run after server start: 3-5 minutes (model loading)
- Subsequent runs: 2-3 minutes
- Progress page polls every 1.5 seconds
- Auto-reload enabled: file changes restart server

## Clean up test data

Remove all filed notes:

```powershell
Remove-Item filings\*.md
```

Remove runtime drafts and flags:

```powershell
Remove-Item runtime\drafts\*.json
Remove-Item runtime\flags\*.json
Remove-Item runtime\approvals\*.json
```

Clear audit log:

```powershell
Clear-Content logs\tool_calls.jsonl
```

## Stop the server

Press `Ctrl+C` in the terminal running `start_web.ps1`

Or:

```powershell
Get-Process -Name python | Where-Object { $_.CommandLine -like "*uvicorn*" } | Stop-Process
```
