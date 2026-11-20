"""LangGraph agent. The model picks tools. The graph retries when a tool returns an error."""

import asyncio
import json
import os
import re
import sys
from typing import Any, Callable, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from awardline.awards import same_supplier
from awardline.drop import file_committee_note
from awardline.notes import tool_draft_committee_note, tool_flag_price_outlier, tool_search_awards

MODEL = os.environ.get("AWARDLINE_MODEL", "qwen2.5:3b")
OLLAMA = os.environ.get("AWARDLINE_OLLAMA", "http://127.0.0.1:11434")
MAX_STEPS = 8
MAX_NUDGES = 2
NUDGE = (
    "No committee note has been drafted yet. Continue with the next tool call: "
    "fix the last call if a tool returned an error (use retry_with when it is given), "
    "otherwise call flag_price_outlier, then draft_committee_note."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_awards",
            "description": "Find published Kenya PPIP awards for a buyer and a purchase description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "buyer": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_price_outlier",
            "description": "Write a sourced price flag for a quote. Call this after search_awards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "buyer": {"type": "string"},
                    "query": {"type": "string"},
                    "amount": {"type": "number"},
                    "currency": {"type": "string"},
                    "supplier": {"type": "string", "description": "The quoting supplier, if the request names one."},
                    "officer": {"type": "string", "description": "The name of the officer who submitted the request. Copy it exactly from the request."},
                },
                "required": ["buyer", "query", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_committee_note",
            "description": "Draft the committee note from the flag. Call this after flag_price_outlier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "buyer": {"type": "string"},
                    "query": {"type": "string"},
                    "amount": {"type": "number"},
                    "currency": {"type": "string"},
                    "supplier": {"type": "string", "description": "The quoting supplier, if the request names one."},
                    "officer": {"type": "string", "description": "The name of the officer who submitted the request. Copy it exactly from the request."},
                },
                "required": ["buyer", "query", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_committee_note",
            "description": "File the note. This fails until a named officer approves it. Do not award a tender.",
            "parameters": {
                "type": "object",
                "properties": {"note_id": {"type": "string"}},
                "required": ["note_id"],
            },
        },
    },
]

SYSTEM = """You are Awardline, preparing a value-for-money note for a Kenyan procuring entity.
Use published award records only. Never award a tender. Never invent an OCID or an amount.
Plan, then call tools:
1. search_awards for the buyer and the purchase.
2. If the search returns 0 or very few results (<4), you can try ONE more time with a simpler query 
   (e.g., "furniture" instead of "office furniture", "vehicles" instead of "motor vehicles").
3. After at most 2 searches, ALWAYS call flag_price_outlier with the quoted amount, even if you 
   found fewer than 4 comparable awards. The tool will handle the "insufficient data" case.
4. draft_committee_note with the same buyer, query, amount, and supplier.
5. Stop when the draft is ready. You may try file_committee_note, and if it refuses, stop and say the officer must approve.

If the request names the quoting supplier, pass it as supplier to both flag_price_outlier and draft_committee_note.
If the request names the officer (e.g. "Officer: Amina Yusuf"), pass their name as officer to both flag_price_outlier and draft_committee_note. This ensures each officer's note is filed independently.
Every finding must come from tool output.
Copy the quoted amount exactly. Do not round it or drop a zero.
"""

DISPATCH = {
    "search_awards": lambda args: tool_search_awards(
        buyer=args.get("buyer", ""),
        query=args.get("query", ""),
        limit=int(args.get("limit", 8) or 8),
    ),
    "flag_price_outlier": lambda args: tool_flag_price_outlier(
        buyer=args.get("buyer", ""),
        query=args.get("query", ""),
        amount=args.get("amount"),
        currency=args.get("currency") or "KES",
        supplier=args.get("supplier") or "",
        officer=args.get("officer") or "",
    ),
    "draft_committee_note": lambda args: tool_draft_committee_note(
        buyer=args.get("buyer", ""),
        query=args.get("query", ""),
        amount=args.get("amount"),
        currency=args.get("currency") or "KES",
        supplier=args.get("supplier") or "",
        officer=args.get("officer") or "",
    ),
    "file_committee_note": lambda args: file_committee_note(args.get("note_id", "")),
}


def _tool_calls_from_text(content: str) -> list[dict]:
    """Recover a tool call when a small model writes JSON instead of using the tool channel."""
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return []
    name = payload.get("name") or payload.get("tool")
    if name not in DISPATCH:
        return []
    arguments = payload.get("arguments") or payload.get("parameters") or {}
    if not isinstance(arguments, dict):
        return []
    return [{"name": name, "arguments": arguments}]


def _wire(message: dict) -> dict:
    """The fields Ollama needs. The full tool result kept under "result" stays local."""
    return {key: value for key, value in message.items() if key not in ("result", "nudge")}


_SEARCH_FIELDS = ("ocid", "buyer", "title", "supplier", "amount", "date")


def for_model(name: str, result: dict) -> dict:
    """A compact view of a tool result for the model's context window.

    Qwen 2.5 3B runs with a 4,096-token context. The full flag and draft carry every
    source, the matched words, and the supplier history; the model needs none of that
    to choose its next step, because the draft is built from the saved flag, not from
    model text. Errors are passed through unchanged so the model can correct itself.
    """
    if not isinstance(result, dict) or not result.get("ok"):
        return result
    if name == "search_awards":
        return {
            "ok": True,
            "count": result.get("count"),
            "awards": [{field: row.get(field) for field in _SEARCH_FIELDS} for row in result.get("awards") or []],
        }
    if name == "flag_price_outlier":
        history = result.get("supplier_history") or {}
        return {
            "ok": True,
            "note_id": result.get("note_id"),
            "flagged": result.get("flagged"),
            "reason": result.get("reason"),
            "amount": result.get("amount"),
            "median": result.get("median"),
            "ratio": result.get("ratio"),
            "comparable_count": result.get("comparable_count"),
            "supplier": result.get("supplier"),
            "supplier_past_awards": history.get("award_count"),
            "next": "Call draft_committee_note with the same buyer, query, amount, and supplier.",
        }
    if name == "draft_committee_note":
        return {
            "ok": True,
            "note_id": result.get("note_id"),
            "revision": result.get("revision"),
            "filed": False,
            "next": "The draft is ready. Stop. Filing needs a named officer's approval.",
        }
    return result


class OllamaModel:
    def __init__(self, model: str = MODEL, base_url: str = OLLAMA):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(self, messages: list[dict]) -> dict:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": [_wire(message) for message in messages], "tools": TOOLS, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        message = response.json()["message"]
        content = message.get("content") or ""
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            tool_calls.append(
                {
                    "name": function.get("name"),
                    "arguments": function.get("arguments") or {},
                }
            )
        if not tool_calls:
            tool_calls = _tool_calls_from_text(content)
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}


class GroqModel:
    """Groq cloud API model - fast and free during beta."""
    
    def __init__(self, model: str = None, api_key: str = None):
        # Use models that are currently active as of Nov 2024
        # Check https://console.groq.com/docs/models for current list
        self.model = model or os.environ.get("GROQ_MODEL", "llama3-groq-70b-8192-tool-use-preview")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is required for GroqModel")
        self.base_url = "https://api.groq.com/openai/v1"
    
    def chat(self, messages: list[dict]) -> dict:
        # Fetch available models and pick the best one for tool calling
        try:
            models_response = httpx.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30
            )
            if models_response.status_code == 200:
                available = [m.get("id") for m in models_response.json().get("data", [])]
                print(f"Available Groq models: {available}", file=__import__('sys').stderr)
                
                # Priority list of known good chat/tool-use models
                preferred = [
                    "qwen/qwen3.8-27b",
                    "allam-2-7b",
                    "openai/gpt-oss-120b",
                    "openai/gpt-oss-20b",
                ]
                for candidate in preferred:
                    if candidate in available:
                        self.model = candidate
                        print(f"Selected model: {self.model}", file=__import__('sys').stderr)
                        break
        except Exception as e:
            print(f"Could not fetch models list: {e}", file=__import__('sys').stderr)

        # Convert tools to OpenAI format
        groq_tools = []
        for tool in TOOLS:
            groq_tools.append({
                "type": "function",
                "function": tool["function"]
            })
        
        # Prepare messages - filter out internal fields and handle tool calls properly
        groq_messages = []
        tool_call_id_counter = 0
        
        print(f"GroqModel.chat called with {len(messages)} messages", file=__import__('sys').stderr)
        
        for msg in messages:
            role = msg["role"]
            
            if role == "system":
                groq_messages.append({
                    "role": "system",
                    "content": msg.get("content", "")
                })
            elif role == "user":
                groq_messages.append({
                    "role": "user",
                    "content": msg.get("content", "")
                })
            elif role == "assistant":
                # Assistant messages with tool calls
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.get("content") or None
                }
                if msg.get("tool_calls"):
                    assistant_msg["tool_calls"] = []
                    for tc in msg["tool_calls"]:
                        tool_call_id_counter += 1
                        assistant_msg["tool_calls"].append({
                            "id": f"call_{tool_call_id_counter}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else tc["arguments"]
                            }
                        })
                groq_messages.append(assistant_msg)
            elif role == "tool":
                # Tool result messages need proper tool_call_id
                tool_call_id_counter += 1
                groq_messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{tool_call_id_counter}",
                    "name": msg.get("name", "unknown"),
                    "content": msg.get("content", "")
                })
        
        print(f"Sending {len(groq_messages)} messages to Groq with {len(groq_tools)} tools", file=__import__('sys').stderr)
        print(f"Messages: {json.dumps(groq_messages, indent=2)[:1000]}", file=__import__('sys').stderr)
        
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": groq_messages,
                    "tools": groq_tools,
                    "temperature": 0.1,
                    "max_tokens": 512
                },
                timeout=180,
            )
            response.raise_for_status()
            
            # Log the response for debugging
            resp_json = response.json()
            print(f"Groq response: {json.dumps(resp_json, indent=2)[:500]}", file=__import__('sys').stderr)
            
        except httpx.HTTPError as e:
            # Log the error and return empty response
            print(f"Groq API error: {e}", file=__import__('sys').stderr)
            if hasattr(e, 'response') and e.response:
                print(f"Response body: {e.response.text}", file=__import__('sys').stderr)
            return {"role": "assistant", "content": f"API Error: {str(e)}", "tool_calls": []}
        
        choice = resp_json["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        
        # Parse tool calls from Groq response
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            args = function.get("arguments") or "{}"
            # Parse arguments if they're a string
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append({
                "name": function.get("name"),
                "arguments": args
            })
        
        if not tool_calls:
            tool_calls = _tool_calls_from_text(content)
        
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}


class AgentState(TypedDict):
    messages: list[dict]
    steps: int


def call_awardline_tool(name: str, arguments: dict) -> dict:
    """Call one tool on the Awardline MCP server over stdio."""

    async def _call() -> dict:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        env = os.environ.copy()
        env["AWARDLINE_ACTOR"] = "mcp"
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "awardline.server"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
        if getattr(result, "isError", False):
            return {"ok": False, "error": _tool_text(result) or f"{name} failed"}
        text = _tool_text(result)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"ok": False, "error": text or f"{name} returned nothing"}
        return parsed if isinstance(parsed, dict) else {"ok": True, "result": parsed}

    return asyncio.run(_call())


def _tool_text(result) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


_KES_AMOUNT = re.compile(r"KES\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
_AMOUNT_TOOLS = {"flag_price_outlier", "draft_committee_note"}


def _stated_quotes(messages: list[dict]) -> list[float]:
    amounts = []
    for message in messages:
        if message.get("role") != "user":
            continue
        for match in _KES_AMOUNT.finditer(message.get("content") or ""):
            amounts.append(float(match.group(1).replace(",", "")))
    return amounts


def _quoted_amount_error(name: str, arguments: dict, messages: list[dict]) -> dict | None:
    if name not in _AMOUNT_TOOLS:
        return None
    quotes = _stated_quotes(messages)
    if not quotes:
        return None
    try:
        passed = float(arguments.get("amount"))
    except (TypeError, ValueError):
        passed = None
    if passed is not None and any(abs(passed - quote) <= max(1.0, quote * 0.001) for quote in quotes):
        return None
    shown = ", ".join(f"{quote:,.2f}" for quote in quotes)
    corrected = {**arguments, "amount": quotes[0]}
    return {
        "ok": False,
        "error": (
            f"The request quotes KES {shown}. Call {name} again with that amount. "
            "Do not round it or drop a zero."
        ),
        "retry_with": {"tool": name, "arguments": corrected},
    }


_SUPPLIER = re.compile(r"\bfrom supplier\s+(.+?)\s+for\b|\bsupplier:\s*(.+?)\s*(?:\n|$)", re.IGNORECASE)


def _stated_suppliers(messages: list[dict]) -> list[str]:
    names = []
    for message in messages:
        if message.get("role") != "user":
            continue
        for match in _SUPPLIER.finditer(message.get("content") or ""):
            name = (match.group(1) or match.group(2) or "").strip().rstrip(".,")
            if name:
                names.append(name)
    return names


def _stated_supplier_error(name: str, arguments: dict, messages: list[dict]) -> dict | None:
    """Send the call back when the request names a supplier and the call drops or changes it."""
    if name not in _AMOUNT_TOOLS:
        return None
    stated = _stated_suppliers(messages)
    if not stated:
        return None
    passed = str(arguments.get("supplier") or "")
    if any(same_supplier(passed, supplier) for supplier in stated):
        return None
    corrected = {**arguments, "supplier": stated[0]}
    return {
        "ok": False,
        "error": (
            f"The request names the quoting supplier {stated[0]}. "
            f"Call {name} again with supplier set to \"{stated[0]}\"."
        ),
        "retry_with": {"tool": name, "arguments": corrected},
    }


def _run_tool(name: str, arguments: dict, call_tool: Callable[[str, dict], dict] | None) -> dict:
    if call_tool is not None:
        try:
            return call_tool(name, arguments)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    handler = DISPATCH.get(name)
    if handler is None:
        return {"ok": False, "error": f"Unknown tool {name}. Use one of {list(DISPATCH)}."}
    try:
        return handler(arguments)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _needs_nudge(messages: list[dict]) -> bool:
    """True when the model stopped before any draft exists and has nudges left.

    Only runs that already called a tool are nudged: a model that answers a request
    without trying any tool (for example, one asking it to award a tender) may stop.
    """
    if not any(message.get("role") == "tool" for message in messages):
        return False
    for message in messages:
        if message.get("role") == "tool" and message.get("name") == "draft_committee_note":
            payload = message.get("result") or {}
            if payload.get("ok"):
                return False
    used = sum(1 for message in messages if message.get("nudge"))
    return used < MAX_NUDGES


def _is_stuck_in_loop(messages: list[dict]) -> bool:
    """Detect if agent is calling search_awards repeatedly without progressing."""
    # Count recent tool calls (last 6 messages, which is 3 assistant+tool pairs)
    recent_tools = [
        (msg.get("name"), msg.get("result", {}).get("count", 0)) 
        for msg in messages[-6:] 
        if msg.get("role") == "tool"
    ]
    
    # If we've seen search_awards 2+ times, check if we should progress
    search_calls = [name for name, count in recent_tools if name == "search_awards"]
    
    # If 2+ searches and no flag call yet, we're potentially stuck
    if len(search_calls) >= 2:
        has_flag = any(msg.get("role") == "tool" and msg.get("name") == "flag_price_outlier" for msg in messages)
        if not has_flag:
            # Check if latest searches are returning empty or very few results
            recent_search_counts = [count for name, count in recent_tools if name == "search_awards"]
            if recent_search_counts and all(c < 4 for c in recent_search_counts[-2:]):
                # Two searches in a row with <4 results each = stuck
                return True
    
    return False


def build_graph(model: Any, call_tool: Callable[[str, dict], dict] | None = None):
    def plan(state: dict) -> dict:
        messages = state["messages"]
        
        # Check if stuck in loop - FORCE TOOL CALLS DIRECTLY
        if _is_stuck_in_loop(messages):
            # Extract task details from original user message
            task_message = next((m for m in messages if m.get("role") == "user" and not m.get("nudge")), None)
            
            if task_message:
                import re
                content = task_message.get("content", "")
                
                # Extract buyer, query, amount, supplier, officer
                buyer_match = re.search(r'Buyer\s+([^r][^\n]+?)(?:\s+received)', content, re.IGNORECASE)
                amount_match = re.search(r'KES\s+([\d,]+(?:\.\d{2})?)', content)
                for_match = re.search(r'for:\s*(.+?)(?:\s+Compare|\s*$)', content, re.IGNORECASE)
                supplier_match = re.search(r'from supplier\s+(.+?)\s+for', content, re.IGNORECASE)
                officer_match = re.search(r'Officer:\s*(.+?)(?:\s*$)', content, re.IGNORECASE | re.MULTILINE)
                
                if buyer_match and amount_match and for_match:
                    buyer = buyer_match.group(1).strip()
                    amount_str = amount_match.group(1).replace(',', '')
                    amount = float(amount_str)
                    query = for_match.group(1).strip()
                    supplier = supplier_match.group(1).strip() if supplier_match else ""
                    officer = officer_match.group(1).strip() if officer_match else ""
                    
                    # FORCE flag_price_outlier call directly as if model called it
                    forced_assistant = {
                        "role": "assistant",
                        "content": "Calling flag_price_outlier to handle this case.",
                        "tool_calls": [{
                            "name": "flag_price_outlier",
                            "arguments": {
                                "buyer": buyer,
                                "query": query,
                                "amount": amount,
                                "currency": "KES",
                                "supplier": supplier,
                                "officer": officer,
                            }
                        }]
                    }
                    return {"messages": messages + [forced_assistant], "steps": state["steps"] + 1}
        
        try:
            reply = model.chat(messages)
        except Exception as exc:
            reply = {
                "role": "assistant",
                "content": f"Model call failed: {exc}",
                "tool_calls": [],
            }
        return {"messages": messages + [reply], "steps": state["steps"] + 1}

    def tools(state: dict) -> dict:
        last = state["messages"][-1]
        followups = []
        for call in last.get("tool_calls") or []:
            name = call.get("name")
            arguments = call.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            result = _quoted_amount_error(name, arguments, state["messages"])
            if result is None:
                result = _stated_supplier_error(name, arguments, state["messages"])
            if result is None:
                result = _run_tool(name, arguments, call_tool)
            followups.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(for_model(name, result), ensure_ascii=False),
                    "result": result,
                }
            )
        return {"messages": state["messages"] + followups}

    def nudge(state: dict) -> dict:
        return {"messages": state["messages"] + [{"role": "user", "content": NUDGE, "nudge": True}]}

    def route(state: dict) -> str:
        last = state["messages"][-1]
        if state["steps"] >= MAX_STEPS:
            return "end"
        if last.get("role") == "assistant" and last.get("tool_calls"):
            return "tools"
        if _needs_nudge(state["messages"]):
            return "nudge"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("tools", tools)
    graph.add_node("nudge", nudge)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route, {"tools": "tools", "nudge": "nudge", "end": END})
    graph.add_edge("tools", "plan")
    graph.add_edge("nudge", "plan")
    return graph.compile()


def run_agent(task: str, model: Any | None = None) -> dict:
    chosen = model or OllamaModel()
    # Don't use MCP on serverless - call tools directly via DISPATCH
    use_mcp = not (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    graph = build_graph(chosen, call_awardline_tool if use_mcp else None)
    state = graph.invoke(
        {
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": task},
            ],
            "steps": 0,
        }
    )
    draft = None
    for message in state["messages"]:
        if message.get("role") == "tool" and message.get("name") == "draft_committee_note":
            payload = message.get("result") or json.loads(message["content"])
            if payload.get("ok"):
                draft = payload
    
    # Detailed error analysis
    error_msg = None
    if draft is None:
        # Check what happened
        searches = [m for m in state["messages"] if m.get("role") == "tool" and m.get("name") == "search_awards"]
        flags = [m for m in state["messages"] if m.get("role") == "tool" and m.get("name") == "flag_price_outlier"]
        
        if len(searches) >= 2 and len(flags) == 0:
            # Got stuck searching
            last_search_count = searches[-1].get("result", {}).get("count", 0)
            if last_search_count == 0:
                error_msg = "No PPIP awards found for this buyer and purchase description. Try: (1) Use a more general description (e.g., 'office furniture' instead of specific items), or (2) Check if the buyer name matches what's published on PPIP."
            else:
                error_msg = f"Agent searched multiple times (found {last_search_count} awards) but didn't progress. Try simplifying the purchase description."
        elif _is_stuck_in_loop(state["messages"]):
            error_msg = "Agent got stuck in a search loop. Try simplifying the purchase description to match common PPIP terminology."
        elif state["steps"] >= MAX_STEPS:
            error_msg = "Agent reached maximum steps without completing the note. Try a simpler, more general purchase description."
        else:
            error_msg = "Agent stopped without drafting a note. This may be due to the model not understanding the request."
    
    return {
        "messages": state["messages"], 
        "draft": draft, 
        "steps": state["steps"],
        "error": error_msg
    }
