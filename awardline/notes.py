import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from awardline.audit import caller, log_call
from awardline.awards import load_snapshot, search_awards, snapshot_info, supplier_key
from awardline.paths import APPROVALS, DRAFTS, FLAGS, ensure_runtime
from awardline.score import MIN_COVERAGE, MIN_HISTORY, flag_price_outlier


def _key(buyer: str, query: str, amount: float, currency: str, supplier: str = "") -> str:
    raw = f"{buyer.casefold()}|{query.casefold()}|{currency}|{amount:.2f}"
    # A quote with no supplier keeps the note_id it had before suppliers were tracked.
    if supplier_key(supplier):
        raw += f"|{supplier_key(supplier)}"
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
    buyer: str, query: str, amount: float, currency: str = "KES", supplier: str = ""
) -> dict:
    ensure_runtime()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        result = {"ok": False, "error": "amount must be a number"}
        log_call(caller(), "flag_price_outlier", {"buyer": buyer, "query": query, "amount": amount}, result, False)
        return result
    finding = flag_price_outlier(list(load_snapshot()), buyer, query, amount_f, currency or "KES", supplier or "")
    note_id = _key(buyer, query, amount_f, currency or "KES", supplier or "")
    finding["note_id"] = note_id
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
        {"buyer": buyer, "query": query, "amount": amount_f, "currency": currency, "supplier": supplier},
        finding,
        True,
    )
    return finding


def tool_draft_committee_note(
    buyer: str, query: str, amount: float, currency: str = "KES", supplier: str = ""
) -> dict:
    ensure_runtime()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        result = {"ok": False, "error": "amount must be a number"}
        log_call(caller(), "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount}, result, False)
        return result
    note_id = _key(buyer, query, amount_f, currency or "KES", supplier or "")
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
        log_call(caller(), "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount_f, "supplier": supplier}, result, False)
        return result
    text = render_note(finding)
    # Every draft gets a fresh revision, so an approval given for an earlier draft
    # with the same note_id does not carry over to this one.
    draft = {
        "note_id": note_id,
        "revision": uuid4().hex[:12],
        "drafted_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "finding": finding,
    }
    path = DRAFTS / f"{note_id}.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"ok": True, "note_id": note_id, "revision": draft["revision"], "text": text, "filed": False}
    log_call(caller(), "draft_committee_note", {"buyer": buyer, "query": query, "amount": amount_f, "supplier": supplier}, result, True)
    return result


def render_note(finding: dict) -> str:
    currency = finding["currency"]
    lines = [
        f"# Committee note {finding['note_id']}",
        "",
        "Awardline prepared this note from published Kenya PPIP awards. It does not award a tender.",
        "",
        f"Buyer: {finding['buyer'] or 'not specified'}",
        f"Purchase: {finding['query']}",
    ]
    if finding.get("supplier"):
        lines.append(f"Quoting supplier: {finding['supplier']}")
    lines += [
        f"Quoted amount: {currency} {finding['amount']:,.2f}",
        f"Finding: {'FLAG' if finding['flagged'] else 'NO FLAG'} ({finding['reason']})",
    ]
    if finding.get("median") is not None:
        lines.append(
            f"Basis: median of {finding['comparable_count']} past awards is "
            f"{currency} {finding['median']:,.2f} (quoted / median = {finding['ratio']})."
        )
    else:
        lines.append(
            f"Basis: only {finding['comparable_count']} comparable awards. "
            f"A flag needs at least {MIN_HISTORY}. No price flag was raised."
        )
    lines += [
        "",
        "How sources were chosen: a past award is included when its title shares at least two "
        f"content words with the purchase and those words carry at least {int(MIN_COVERAGE * 100)}% "
        "of the purchase description's weight. Rare words such as a product name count for more "
        "than common words such as \"motor\" or \"vehicles\".",
        "",
        "Sources:",
    ]
    if not finding["sources"]:
        lines.append("- None. An unsourced flag is not allowed.")
    for source in finding["sources"]:
        matched = ", ".join(source.get("matched_words") or []) or "n/a"
        same = " | SAME SUPPLIER" if source.get("same_supplier") else ""
        lines.append(
            f"- {source['ocid']} | {source['buyer']} | {source['title']} | {source['supplier']} | "
            f"{source['currency']} {source['amount']:,.2f} | {source['date']} | {source['source_url']} | "
            f"matched on: {matched}{same}"
        )
    history = finding.get("supplier_history")
    if history is not None:
        lines += ["", f"Supplier history for {history['supplier']}:"]
        if not history["award_count"]:
            lines.append("- No past PPIP awards to this supplier in the snapshot.")
        else:
            lines.append(
                f"- {history['award_count']} past PPIP awards, total {currency} {history['total_amount']:,.2f}."
            )
            if len(history["names_merged"]) > 1:
                lines.append(
                    "- Names treated as the same firm (only case, punctuation, \"M/S\", a postal address, "
                    "and Ltd/Limited/Co/Company/PLC were ignored): " + "; ".join(history["names_merged"])
                )
            else:
                lines.append(f"- Published under one name: {history['names_merged'][0]}")
            for award in history["awards"]:
                lines.append(
                    f"- {award['ocid']} | {award['buyer']} | {award['title']} | {award['supplier']} | "
                    f"{award['currency']} {award['amount']:,.2f} | {award['date']}"
                )
    snapshot = finding.get("snapshot")
    if snapshot:
        when = (snapshot.get("retrieved_at") or "")[:10] or "date not recorded"
        lines += [
            "",
            f"Data: Kenya PPIP snapshot of {snapshot['award_count']:,} awards "
            f"({', '.join(snapshot.get('files') or [])}), downloaded {when}. "
            "Run `python -m awardline refresh` to update it.",
        ]
    lines += [
        "",
        "Caveats for the committee:",
        "- PPIP award amounts are contract totals. They carry no quantities or units, so check that "
        "each source is the same kind and size of purchase before relying on the median.",
        "- A past award may itself have been overpriced. The median is a reference point, not a fair price.",
        "",
        "A named officer must approve this note before it is filed.",
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
