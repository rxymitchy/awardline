"""LangGraph agent. The model picks tools. The graph retries when a tool returns an error."""

import json
import os
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from awardline.drop import file_committee_note
from awardline.notes import tool_draft_committee_note, tool_flag_price_outlier, tool_search_awards

MODEL = os.environ.get("AWARDLINE_MODEL", "qwen2.5:3b")
OLLAMA = os.environ.get("AWARDLINE_OLLAMA", "http://127.0.0.1:11434")
MAX_STEPS = 8

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
2. If the search is empty, change the query and search again. Do not flag without records.
3. flag_price_outlier with the quoted amount.
4. draft_committee_note with the same buyer, query, and amount.
5. Stop when the draft is ready. You may try file_committee_note, and if it refuses, stop and say the officer must approve.
Every finding must come from tool output.
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
    ),
    "draft_committee_note": lambda args: tool_draft_committee_note(
        buyer=args.get("buyer", ""),
        query=args.get("query", ""),
        amount=args.get("amount"),
        currency=args.get("currency") or "KES",
    ),
    "file_committee_note": lambda args: file_committee_note(args.get("note_id", "")),
}


class OllamaModel:
    def __init__(self, model: str = MODEL, base_url: str = OLLAMA):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(self, messages: list[dict]) -> dict:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "tools": TOOLS, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        message = response.json()["message"]
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            tool_calls.append(
                {
                    "name": function.get("name"),
                    "arguments": function.get("arguments") or {},
                }
            )
        return {"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls}


class AgentState(TypedDict):
    messages: list[dict]
    steps: int


def build_graph(model: Any):
    def plan(state: dict) -> dict:
        messages = state["messages"]
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
            handler = DISPATCH.get(name)
            if handler is None:
                result = {"ok": False, "error": f"Unknown tool {name}. Use one of {list(DISPATCH)}."}
            else:
                try:
                    result = handler(arguments)
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
            followups.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        return {"messages": state["messages"] + followups}

    def route(state: dict) -> str:
        last = state["messages"][-1]
        if state["steps"] >= MAX_STEPS:
            return "end"
        if last.get("role") == "assistant" and last.get("tool_calls"):
            return "tools"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("tools", tools)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route, {"tools": "tools", "end": END})
    graph.add_edge("tools", "plan")
    return graph.compile()


def run_agent(task: str, model: Any | None = None) -> dict:
    chosen = model or OllamaModel()
    graph = build_graph(chosen)
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
            payload = json.loads(message["content"])
            if payload.get("ok"):
                draft = payload
    return {"messages": state["messages"], "draft": draft, "steps": state["steps"]}
