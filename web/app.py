"""Awardline web application.

Runs on FastAPI + Jinja2. Every quote analysis runs through the full LangGraph
agent — the agent plans, calls tools, retries on error, exactly as it does from
the CLI. The web form just constructs the task string for the officer.

Start with:
    python -m uvicorn web.app:app --reload --port 8000
or:
    .\\start_web.ps1
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Dict

# Make sure the project root is on the path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from awardline.agent import OllamaModel, GroqModel, run_agent
from awardline.notes import approval_for, draft_for, record_approval
from awardline.drop import file_committee_note
from awardline.paths import FILINGS, ensure_runtime

# ── App setup ──────────────────────────────────────────────────────────────

import secrets

# Generate a secure random secret if not provided
SECRET = os.environ.get("AWARDLINE_SECRET")
if not SECRET:
    SECRET = secrets.token_urlsafe(32)
    print(f"⚠️  No AWARDLINE_SECRET set. Generated random secret for this session.", file=sys.stderr)

app = FastAPI(title="Awardline")
app.add_middleware(SessionMiddleware, secret_key=SECRET)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

ensure_runtime()

# ── Agent run tracking ──────────────────────────────────────────────────────
# In-memory store: run_id → agent state (messages, draft, status)
# In production, use Redis or a database.

agent_runs: Dict[str, dict] = {}


def _start_agent_run(task: str) -> str:
    """Start an agent run in the background, return the run_id."""
    run_id = uuid.uuid4().hex[:12]
    agent_runs[run_id] = {
        "status": "running",
        "task": task,
        "messages": [],
        "draft": None,
        "error": None,
    }

    async def _run():
        try:
            # Choose model: Groq if API key is set, otherwise Ollama
            if os.environ.get("GROQ_API_KEY"):
                model = GroqModel()
            else:
                model = OllamaModel()
            
            result = await asyncio.to_thread(run_agent, task, model)
            agent_runs[run_id]["messages"] = result["messages"]
            agent_runs[run_id]["draft"] = result.get("draft")
            agent_runs[run_id]["error"] = result.get("error")  # Use the error from agent
            agent_runs[run_id]["status"] = "complete" if result.get("draft") else "failed"
        except Exception as exc:
            agent_runs[run_id]["status"] = "failed"
            agent_runs[run_id]["error"] = f"Agent crashed: {str(exc)}"

    asyncio.create_task(_run())
    return run_id


# ── Helper: render template (Starlette 1.x compat) ─────────────────────────

def _t(request: Request, name: str, ctx: dict | None = None, status_code: int = 200):
    """Render a Jinja2 template, compatible with Starlette 0.x and 1.x."""
    context = dict(ctx or {})
    context["request"] = request
    return templates.TemplateResponse(request=request, name=name, context=context, status_code=status_code)


# ── Auth helpers ────────────────────────────────────────────────────────────

def _officer(request: Request) -> str | None:
    return request.session.get("officer")


def _require_officer(request: Request):
    officer = _officer(request)
    if not officer:
        return RedirectResponse("/login", status_code=303)
    return None


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    redirect = _require_officer(request)
    if redirect:
        return redirect
    return _t(request, "index.html", {"officer": _officer(request)})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _t(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, officer: str = Form(...)):
    name = " ".join(officer.strip().split())
    if len(name) < 3 or name.casefold() in {"agent", "awardline", "model"}:
        return _t(request, "login.html", {"error": "Please enter your full name (at least 3 characters)."})
    request.session["officer"] = name
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/check", response_class=HTMLResponse)
async def check_form(request: Request):
    redirect = _require_officer(request)
    if redirect:
        return redirect
    return _t(request, "check.html", {"officer": _officer(request)})


@app.post("/check", response_class=HTMLResponse)
async def check_submit(
    request: Request,
    buyer: str = Form(...),
    item: str = Form(...),
    amount: str = Form(...),
    supplier: str = Form(""),
):
    redirect = _require_officer(request)
    if redirect:
        return redirect

    base_ctx = {
        "officer": _officer(request),
        "buyer": buyer,
        "item": item,
        "amount": amount,
        "supplier": supplier,
    }

    # Parse amount — accept commas as thousands separators.
    try:
        amount_f = float(amount.replace(",", ""))
        if amount_f <= 0:
            raise ValueError
    except ValueError:
        return _t(request, "check.html", {**base_ctx, "error": "Amount must be a positive number."})

    # Build the task string for the agent, just like the CLI demo does.
    task_parts = [
        f"Buyer {buyer.strip()} received a quote of KES {amount_f:,.2f}"
    ]
    if supplier.strip():
        task_parts[0] += f" from supplier {supplier.strip()}"
    task_parts.append(f"for: {item.strip()}")
    task_parts.append(
        "Compare it with published past awards and draft a value-for-money committee note. "
        "Do not award the tender."
    )
    task = " ".join(task_parts)

    # Start the agent run in the background.
    run_id = _start_agent_run(task)

    # Redirect to the progress page that polls for completion.
    return RedirectResponse(f"/run/{run_id}", status_code=303)


@app.get("/run/{run_id}", response_class=HTMLResponse)
async def agent_progress(request: Request, run_id: str):
    """Progress page: polls /api/run/{run_id}/status until complete."""
    redirect = _require_officer(request)
    if redirect:
        return redirect

    run = agent_runs.get(run_id)
    if run is None:
        return _t(request, "error.html", {"officer": _officer(request), "message": "Run not found."}, 404)

    return _t(request, "progress.html", {
        "officer": _officer(request),
        "run_id": run_id,
        "task": run["task"],
    })


@app.get("/api/run/{run_id}/status")
async def agent_status_api(request: Request, run_id: str):
    """API endpoint: poll this to track agent progress."""
    run = agent_runs.get(run_id)
    if run is None:
        return JSONResponse({"status": "not_found"}, status_code=404)

    # Extract tool calls from messages for progress display.
    tool_calls = []
    for msg in run["messages"]:
        if msg.get("role") == "tool":
            tool_calls.append({
                "name": msg.get("name"),
                "ok": msg.get("result", {}).get("ok", False),
            })

    response = {
        "status": run["status"],
        "tool_calls": tool_calls,
    }

    if run["status"] == "complete" and run["draft"]:
        response["note_id"] = run["draft"]["note_id"]
    elif run["status"] == "failed":
        response["error"] = run.get("error", "Unknown error")

    return JSONResponse(response)


@app.get("/note/{note_id}", response_class=HTMLResponse)
async def note_detail(request: Request, note_id: str):
    redirect = _require_officer(request)
    if redirect:
        return redirect

    draft = draft_for(note_id)
    if draft is None:
        return _t(request, "error.html", {"officer": _officer(request), "message": "Note not found."}, 404)

    approval = approval_for(note_id)
    finding = draft.get("finding", {})
    already_filed = (FILINGS / f"{note_id}.md").exists()

    # Find agent run for this note_id to show tool history
    agent_run = None
    for run in agent_runs.values():
        if run.get("draft", {}).get("note_id") == note_id:
            agent_run = run
            break

    # Extract tool call summary
    tool_history = []
    if agent_run:
        for msg in agent_run.get("messages", []):
            if msg.get("role") == "tool":
                tool_history.append({
                    "name": msg.get("name"),
                    "ok": msg.get("result", {}).get("ok", False),
                })

    return _t(request, "note.html", {
        "officer": _officer(request),
        "draft": draft,
        "finding": finding,
        "approval": approval,
        "already_filed": already_filed,
        "note_id": note_id,
        "tool_history": tool_history,
    })


@app.post("/note/{note_id}/approve", response_class=HTMLResponse)
async def approve_note(request: Request, note_id: str):
    redirect = _require_officer(request)
    if redirect:
        return redirect

    officer = _officer(request)
    result = record_approval(note_id, officer)
    if not result.get("ok"):
        draft = draft_for(note_id)
        finding = draft.get("finding", {}) if draft else {}
        return _t(request, "note.html", {
            "officer": officer,
            "draft": draft,
            "finding": finding,
            "approval": None,
            "already_filed": False,
            "note_id": note_id,
            "approve_error": result.get("error"),
        })
    return RedirectResponse(f"/note/{note_id}", status_code=303)


@app.post("/note/{note_id}/approve-and-file", response_class=HTMLResponse)
async def approve_and_file_note(request: Request, note_id: str):
    """Streamlined workflow: approve and file in one action."""
    redirect = _require_officer(request)
    if redirect:
        return redirect

    officer = _officer(request)
    
    # Step 1: Approve
    approval_result = record_approval(note_id, officer)
    if not approval_result.get("ok"):
        draft = draft_for(note_id)
        finding = draft.get("finding", {}) if draft else {}
        return _t(request, "note.html", {
            "officer": officer,
            "draft": draft,
            "finding": finding,
            "approval": None,
            "already_filed": False,
            "note_id": note_id,
            "approve_error": approval_result.get("error"),
        })
    
    # Step 2: File (run in thread to avoid event loop conflict)
    file_result = await asyncio.to_thread(file_committee_note, note_id)
    if not file_result.get("ok"):
        draft = draft_for(note_id)
        finding = draft.get("finding", {}) if draft else {}
        approval = approval_for(note_id)
        return _t(request, "note.html", {
            "officer": officer,
            "draft": draft,
            "finding": finding,
            "approval": approval,
            "already_filed": False,
            "note_id": note_id,
            "file_error": file_result.get("error"),
        })
    
    # Success: redirect to filings list
    return RedirectResponse("/filings", status_code=303)


@app.post("/note/{note_id}/file", response_class=HTMLResponse)
async def file_note(request: Request, note_id: str):
    redirect = _require_officer(request)
    if redirect:
        return redirect

    # Run in thread to avoid event loop conflict
    result = await asyncio.to_thread(file_committee_note, note_id)
    if not result.get("ok"):
        draft = draft_for(note_id)
        finding = draft.get("finding", {}) if draft else {}
        approval = approval_for(note_id)
        return _t(request, "note.html", {
            "officer": _officer(request),
            "draft": draft,
            "finding": finding,
            "approval": approval,
            "already_filed": False,
            "note_id": note_id,
            "file_error": result.get("error"),
        })
    return RedirectResponse("/filings", status_code=303)


@app.get("/filings", response_class=HTMLResponse)
async def filings_list(request: Request):
    redirect = _require_officer(request)
    if redirect:
        return redirect

    officer = _officer(request)
    ensure_runtime()
    filed = []
    for path in sorted(FILINGS.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        note_id = path.stem
        approval = approval_for(note_id)
        # Only show notes this officer approved
        if not approval or approval.get("officer") != officer:
            continue
        draft = draft_for(note_id)
        filed.append({
            "note_id": note_id,
            "officer": approval["officer"] if approval else "—",
            "approved_at": (approval.get("approved_at") or "")[:10] if approval else "—",
            "buyer": draft.get("finding", {}).get("buyer", "—") if draft else "—",
            "item": draft.get("finding", {}).get("query", "—") if draft else "—",
            "amount": draft.get("finding", {}).get("amount") if draft else None,
            "flagged": draft.get("finding", {}).get("flagged") if draft else None,
        })

    return _t(request, "filings.html", {"officer": officer, "filed": filed})


@app.get("/filings/{note_id}", response_class=HTMLResponse)
async def view_filing(request: Request, note_id: str):
    redirect = _require_officer(request)
    if redirect:
        return redirect

    path = FILINGS / f"{note_id}.md"
    if not path.exists():
        return _t(request, "error.html", {"officer": _officer(request), "message": "Filing not found."}, 404)

    text = path.read_text(encoding="utf-8")
    approval = approval_for(note_id)
    return _t(request, "filing_detail.html", {
        "officer": _officer(request),
        "note_id": note_id,
        "text": text,
        "approval": approval,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
