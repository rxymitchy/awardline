import json
import re
from hashlib import sha256

from awardline.audit import log_call
from awardline.awards import load_snapshot, search_awards
from awardline.paths import APPROVALS, DRAFTS, FLAGS, ensure_runtime
from awardline.score import flag_price_outlier


def _key(buyer: str, query: str, amount: float, currency: str) -> str:
    raw = f"{buyer.casefold()}|{query.casefold()}|{currency}|{amount:.2f}"
    return "note-" + sha256(raw.encode("utf-8")).hexdigest()[:10]


def _read_json(path) -> dict | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def tool_search_awards(buyer: str = "", query: str = "", limit: int = 8) -> dict:
    result = search_awards(buyer=buyer, query=query, limit=limit)
    log_call("agent", "search_awards", {"buyer": buyer, "query": query, "limit": limit}, result, result["ok"])
    return result


def tool_flag_price_outlier(buyer: str, query: str, amount: float, currency: str = "KES") -> dict:
    ensure_runtime()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        result = {"ok": False, "error": "amount must be a number"}
        log_call("agent", "flag_price_outlier", {"buyer": buyer, "query": query, "amount": amount}, result, False)
        return result
    finding = flag_price_outlier(list(load_snapshot()), buyer, query, amount_f, currency or "KES")
    note_id = _key(buyer, query, amount_f, currency or "KES")
    finding["note_id"] = note_id
    path = FLAGS / f"{note_id}.json"
    path.write_text(json.dumps(finding, ensure_ascii=False, indent=2), encoding="utf-8")
    finding["flag_path"] = str(path)
    log_call(
        "agent",
        "flag_price_outlier",
        {"buyer": buyer, "query": query, "amount": amount_f, "currency": currency},
        finding,
        True,
    )
    return finding


def tool_draft_committee_note(buyer: str, query: str, amount: float, currency: str = "KES") -> dict:
    ensure_runtime()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        result = {"ok": False, "error": "amount must be a number"}
        log_call("agent", "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount}, result, False)
        return result
    note_id = _key(buyer, query, amount_f, currency or "KES")
    finding = _read_json(FLAGS / f"{note_id}.json")
    if finding is None:
        result = {
            "ok": False,
            "error": "No flag exists for this quote. Call flag_price_outlier before drafting.",
            "note_id": note_id,
        }
        log_call("agent", "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount_f}, result, False)
        return result
    text = render_note(finding)
    draft = {"note_id": note_id, "text": text, "finding": finding}
    path = DRAFTS / f"{note_id}.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"ok": True, "note_id": note_id, "text": text, "filed": False}
    log_call("agent", "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount_f}, result, True)
    return result


def render_note(finding: dict) -> str:
    lines = [
        f"# Committee note {finding['note_id']}",
        "",
        "Awardline prepared this note from published Kenya PPIP awards. It does not award a tender.",
        "",
        f"Buyer: {finding['buyer'] or 'not specified'}",
        f"Purchase: {finding['query']}",
        f"Quoted amount: {finding['currency']} {finding['amount']:,.2f}",
        f"Finding: {'FLAG' if finding['flagged'] else 'NO FLAG'} ({finding['reason']})",
    ]
    if finding.get("median") is not None:
        lines.append(
            f"Basis: median of {finding['comparable_count']} past awards is "
            f"{finding['currency']} {finding['median']:,.2f} (quoted / median = {finding['ratio']})."
        )
    else:
        lines.append(
            f"Basis: only {finding['comparable_count']} comparable awards. "
            "A flag needs at least 4. No price flag was raised."
        )
    lines.append("")
    lines.append("Sources:")
    if not finding["sources"]:
        lines.append("- None. An unsourced flag is not allowed.")
    for source in finding["sources"]:
        lines.append(
            f"- {source['ocid']} | {source['buyer']} | {source['title']} | "
            f"{source['currency']} {source['amount']:,.2f} | {source['date']} | {source['source_url']}"
        )
    lines.append("")
    lines.append("A named officer must approve this note before it is filed.")
    return "\n".join(lines)


def record_approval(note_id: str, officer: str) -> dict:
    ensure_runtime()
    officer_name = re.sub(r"\s+", " ", (officer or "")).strip()
    if len(officer_name) < 3 or officer_name.casefold() in {"agent", "awardline", "model"}:
        result = {"ok": False, "error": "A named officer is required."}
        log_call("human", "record_approval", {"note_id": note_id, "officer": officer}, result, False)
        return result
    draft = _read_json(DRAFTS / f"{note_id}.json")
    if draft is None:
        result = {"ok": False, "error": f"No draft for {note_id}."}
        log_call("human", "record_approval", {"note_id": note_id, "officer": officer_name}, result, False)
        return result
    from datetime import datetime, timezone

    approval = {
        "note_id": note_id,
        "officer": officer_name,
        "decision": "approve",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    path = APPROVALS / f"{note_id}.json"
    path.write_text(json.dumps(approval, indent=2), encoding="utf-8")
    result = {"ok": True, **approval}
    log_call("human", "record_approval", {"note_id": note_id, "officer": officer_name}, result, True)
    return result


def approval_for(note_id: str) -> dict | None:
    return _read_json(APPROVALS / f"{note_id}.json")


def draft_for(note_id: str) -> dict | None:
    return _read_json(DRAFTS / f"{note_id}.json")
