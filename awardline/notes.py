import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from awardline.audit import caller, log_call
from awardline.awards import load_snapshot, search_awards, snapshot_info, supplier_key
from awardline.paths import APPROVALS, DRAFTS, FLAGS, ensure_runtime
from awardline.score import MIN_COVERAGE, MIN_HISTORY, flag_price_outlier


def _key(buyer: str, query: str, amount: float, currency: str, supplier: str = "", officer: str = "") -> str:
    raw = f"{buyer.casefold()}|{query.casefold()}|{currency}|{amount:.2f}"
    # A quote with no supplier keeps the note_id it had before suppliers were tracked.
    if supplier_key(supplier):
        raw += f"|{supplier_key(supplier)}"
    # Each officer gets their own independent note so one user's filing never
    # blocks or overwrites another user checking the same quote.
    if officer.strip():
        raw += f"|{officer.strip().casefold()}"
    return "note-" + sha256(raw.encode("utf-8")).hexdigest()[:10]


def _read_json(path) -> dict | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def tool_search_awards(buyer: str = "", query: str = "", limit: int = 8) -> dict:
    result = search_awards(buyer=buyer, query=query, limit=limit)
    log_call(caller(), "search_awards", {"buyer": buyer, "query": query, "limit": limit}, result, result["ok"])
    return result


def tool_flag_price_outlier(
    buyer: str, query: str, amount: float, currency: str = "KES", supplier: str = "", officer: str = ""
) -> dict:
    ensure_runtime()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        result = {"ok": False, "error": "amount must be a number"}
        log_call(caller(), "flag_price_outlier", {"buyer": buyer, "query": query, "amount": amount}, result, False)
        return result
    finding = flag_price_outlier(list(load_snapshot()), buyer, query, amount_f, currency or "KES", supplier or "")
    note_id = _key(buyer, query, amount_f, currency or "KES", supplier or "", officer or "")
    finding["note_id"] = note_id
    finding["officer"] = officer.strip() if officer else ""
    try:
        finding["snapshot"] = snapshot_info()
    except (OSError, ValueError):
        finding["snapshot"] = None
    path = FLAGS / f"{note_id}.json"
    path.write_text(json.dumps(finding, ensure_ascii=False, indent=2), encoding="utf-8")
    finding["flag_path"] = str(path)
    log_call(
        caller(),
        "flag_price_outlier",
        {"buyer": buyer, "query": query, "amount": amount_f, "currency": currency, "supplier": supplier, "officer": officer},
        finding,
        True,
    )
    return finding


def tool_draft_committee_note(
    buyer: str, query: str, amount: float, currency: str = "KES", supplier: str = "", officer: str = ""
) -> dict:
    ensure_runtime()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        result = {"ok": False, "error": "amount must be a number"}
        log_call(caller(), "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount}, result, False)
        return result
    note_id = _key(buyer, query, amount_f, currency or "KES", supplier or "", officer or "")
    finding = _read_json(FLAGS / f"{note_id}.json")
    if finding is None:
        result = {
            "ok": False,
            "error": (
                "No flag exists for this quote. Call flag_price_outlier with the same "
                "buyer, query, amount, and supplier before drafting."
            ),
            "note_id": note_id,
        }
        log_call(caller(), "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount_f, "supplier": supplier, "officer": officer}, result, False)
        return result
    text = render_note(finding)
    draft = {
        "note_id": note_id,
        "revision": uuid4().hex[:12],
        "drafted_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "finding": finding,
        "officer": officer.strip() if officer else "",
    }
    path = DRAFTS / f"{note_id}.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"ok": True, "note_id": note_id, "revision": draft["revision"], "text": text, "filed": False}
    log_call(caller(), "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount_f, "supplier": supplier, "officer": officer}, result, True)
    return result


def render_note(finding: dict) -> str:
    currency = finding["currency"]
    lines = [
        "COMMITTEE VALUE-FOR-MONEY NOTE",
        f"Note ID: {finding['note_id']}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "=" * 80,
        "EXECUTIVE SUMMARY",
        "=" * 80,
        "",
    ]
    
    # Clear verdict section
    if finding['flagged']:
        lines += [
            "PRICE FLAG RAISED",
            "",
            f"The quoted amount of {currency} {finding['amount']:,.2f} is {finding['ratio']}x the median",
            f"of {finding['comparable_count']} comparable past awards (median: {currency} {finding.get('median', 0):,.2f}).",
            "",
            "Recommendation: Committee should request justification from the supplier or seek",
            "alternative quotes before award.",
        ]
    elif finding.get("median") is not None:
        lines += [
            "NO PRICE FLAG",
            "",
            f"The quoted amount of {currency} {finding['amount']:,.2f} is {finding['ratio']}x the median",
            f"of {finding['comparable_count']} comparable past awards (median: {currency} {finding.get('median', 0):,.2f}).",
            "",
            "The quote falls within reasonable range based on published PPIP awards.",
        ]
    else:
        lines += [
            "INSUFFICIENT DATA",
            "",
            f"Only {finding['comparable_count']} comparable awards found in the snapshot.",
            f"At least {MIN_HISTORY} awards are needed to calculate a reliable median and flag outliers.",
            "",
            "Recommendation: Proceed with standard due diligence. No automated flag was raised.",
        ]
    
    lines += [
        "",
        "-" * 80,
        "QUOTE DETAILS",
        "-" * 80,
        "",
        f"Procuring Entity:     {finding['buyer'] or 'Not specified'}",
        f"Purchase Description: {finding['query']}",
    ]
    
    if finding.get("supplier"):
        lines.append(f"Quoting Supplier:     {finding['supplier']}")
    
    lines.append(f"Quoted Amount:        {currency} {finding['amount']:,.2f}")
    
    lines += [
        "",
        "-" * 80,
        "COMPARABLE PPIP AWARDS",
        "-" * 80,
        "",
        "Source Selection Criteria:",
        f"Awards are included when their title shares at least 2 content words with the purchase",
        f"description, where those words carry >={int(MIN_COVERAGE * 100)}% of the description's word weight.",
        "Rare/specific words (product names) count more than common words (\"supply\", \"motor\").",
        "",
    ]
    
    if not finding["sources"]:
        lines.append("No comparable awards found. An unsourced price flag cannot be raised.")
    else:
        lines.append(f"Found {len(finding['sources'])} comparable awards:")
        lines.append("")
        
        # Numbered source table with clear structure
        for idx, source in enumerate(finding["sources"], 1):
            same_tag = " [SAME SUPPLIER]" if source.get("same_supplier") else ""
            matched = ", ".join(source.get("matched_words") or [])
            
            lines += [
                f"[{idx}] {source['ocid']}{same_tag}",
                f"    Buyer:    {source['buyer']}",
                f"    Title:    {source['title']}",
                f"    Supplier: {source['supplier'] or '(not recorded)'}",
                f"    Amount:   {source['currency']} {source['amount']:,.2f}",
                f"    Date:     {source['date']}",
                f"    Matched:  {matched}",
                f"    Source:   {source['source_url']}",
                "",
            ]
    
    # Supplier history section
    history = finding.get("supplier_history")
    if history is not None and history.get("award_count", 0) > 0:
        lines += [
            "-" * 80,
            f"SUPPLIER HISTORY: {history['supplier']}",
            "-" * 80,
            "",
            f"Total Past PPIP Awards: {history['award_count']} contracts",
            f"Total Value:            {currency} {history['total_amount']:,.2f}",
            "",
        ]
        
        if len(history["names_merged"]) > 1:
            lines += [
                "Name Variants Merged:",
                "(Case, punctuation, M/S prefix, postal addresses, and Ltd/Limited/Co/Company/PLC ignored)",
            ]
            for name in history["names_merged"]:
                lines.append(f"  - {name}")
            lines.append("")
        
        lines.append("Past Awards:")
        lines.append("")
        
        for idx, award in enumerate(history["awards"], 1):
            lines += [
                f"[{idx}] {award['ocid']}",
                f"    Buyer:    {award['buyer']}",
                f"    Title:    {award['title']}",
                f"    Amount:   {award['currency']} {award['amount']:,.2f}",
                f"    Date:     {award['date']}",
                "",
            ]
    
    # Data source section
    snapshot = finding.get("snapshot")
    if snapshot:
        when = (snapshot.get("retrieved_at") or "")[:10] or "date not recorded"
        lines += [
            "-" * 80,
            "DATA SOURCE",
            "-" * 80,
            "",
            f"Snapshot:   Kenya PPIP, {snapshot['award_count']:,} awards",
            f"Files:      {', '.join(snapshot.get('files') or [])}",
            f"Downloaded: {when}",
            f"Note:       Run 'python -m awardline refresh' to update the snapshot.",
        ]
    
    lines += [
        "",
        "=" * 80,
        "IMPORTANT CAVEATS",
        "=" * 80,
        "",
        "Contract Totals vs. Unit Prices:",
        "  PPIP awards show only contract totals, not quantities or units. Verify that each",
        "  comparable source represents the same kind and scale of purchase before relying on",
        "  the median.",
        "",
        "Past Awards May Be Overpriced:",
        "  A past PPIP award may itself have been inflated. The median is a reference point",
        "  for reasonableness, not a certified fair price.",
        "",
        "Human Judgment Required:",
        "  This note is a decision support tool. The committee retains full responsibility",
        "  for the award decision.",
        "",
        "=" * 80,
        "",
        "Prepared by: Awardline agent (MCP-based procurement analysis tool)",
        f"Approved by: {finding.get('officer') or '[Officer name recorded upon approval]'}",
        "Status:      This note does not award a tender. Officer approval required before filing.",
        "",
    ]
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
    approval = {
        "note_id": note_id,
        "draft_revision": draft.get("revision"),
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


def approval_error(draft: dict, approval: dict | None) -> str | None:
    """Return why the approval does not cover this draft, or None if it does."""
    if approval is None or approval.get("decision") != "approve":
        return "Officer approval required before this note can be filed."
    revision = draft.get("revision")
    if not revision or approval.get("draft_revision") != revision:
        return (
            "The approval on file is for an earlier draft of this note. "
            "An officer must approve the current draft before it can be filed."
        )
    return None


def draft_for(note_id: str) -> dict | None:
    return _read_json(DRAFTS / f"{note_id}.json")
