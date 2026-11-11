import json
import re
from functools import lru_cache

from awardline.paths import DATA

BOILERPLATE = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "that",
    "this",
    "proposed",
    "supply",
    "delivery",
    "provision",
    "services",
    "service",
    "works",
    "goods",
    "tender",
    "reserved",
    "youth",
    "women",
    "persons",
    "disabilities",
    "comprehensive",
    "ltd",
    "limited",
    "company",
}


def _singular(word: str) -> str:
    """Fold a simple English plural so 'vehicles' matches 'vehicle'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    kept = set()
    for word in words:
        if len(word) <= 2 or word in BOILERPLATE:
            continue
        word = _singular(word)
        if word not in BOILERPLATE:
            kept.add(word)
    return kept


# Legal-form words that PPIP buyers spell several ways for the same firm.
LEGAL_SUFFIXES = {"ltd", "limited", "company", "co", "plc", "inc", "llc"}
SUPPLIER_PREFIXES = (("m", "s"), ("messrs",))


def supplier_key(name: str) -> str:
    """Normalise a supplier name for matching.

    Only formatting that does not identify the firm is removed: case, punctuation,
    a leading "M/S" or "Messrs", a trailing postal address ("P.O. Box ..."), and
    trailing legal-form words (Ltd, Limited, Co, Company, PLC). Words that can
    distinguish two firms, such as "Kenya", "Holdings" or "(K)", are kept.
    """
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    for prefix in SUPPLIER_PREFIXES:
        if tuple(words[: len(prefix)]) == prefix and len(words) > len(prefix):
            words = words[len(prefix) :]
            break
    for index in range(len(words)):
        if words[index : index + 3] == ["p", "o", "box"] or words[index : index + 2] == ["po", "box"]:
            words = words[:index]
            break
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def same_supplier(left: str, right: str) -> bool:
    """True when two PPIP supplier names refer to the same firm.

    "KIOLI INVESTMENTS LIMITED", "M/S KIOLI INVESTMENTS LIMITED" and
    "Kioli Investments Ltd" match. An empty name never matches anything.
    """
    left_key, right_key = supplier_key(left), supplier_key(right)
    return bool(left_key) and left_key == right_key


@lru_cache(maxsize=1)
def load_snapshot(path: str | None = None) -> tuple[dict, ...]:
    source = path or str(DATA)
    with open(source, encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(payload["awards"])


@lru_cache(maxsize=1)
def snapshot_info(path: str | None = None) -> dict:
    """How many awards the snapshot holds and when it was downloaded, if recorded."""
    source = path or str(DATA)
    with open(source, encoding="utf-8") as handle:
        payload = json.load(handle)
    return {
        "award_count": payload.get("award_count", len(payload.get("awards") or [])),
        "retrieved_at": payload.get("retrieved_at"),
        "files": [entry.get("file") for entry in payload.get("files") or []],
    }


def search_awards(buyer: str = "", query: str = "", limit: int = 8, awards: list[dict] | None = None) -> dict:
    buyer_q = (buyer or "").casefold().strip()
    query_tokens = tokens(query)
    if not buyer_q and not query_tokens:
        return {
            "ok": False,
            "error": "Provide a buyer name or a purchase description.",
            "awards": [],
        }
    rows = list(awards) if awards is not None else list(load_snapshot())
    matched = []
    for award in rows:
        buyer_ok = not buyer_q or buyer_q in award["buyer"].casefold()
        shared = query_tokens & tokens(award["title"]) if query_tokens else set()
        query_ok = not query_tokens or len(shared) >= 1
        if buyer_ok and query_ok:
            matched.append((len(shared), award))
    matched.sort(key=lambda item: (item[0], item[1].get("date") or ""), reverse=True)
    limit = max(1, min(int(limit), 20))
    chosen = [row for _, row in matched[:limit]]
    return {"ok": True, "count": len(chosen), "awards": [_public(row) for row in chosen]}


def _public(award: dict) -> dict:
    return {
        "ocid": award["ocid"],
        "award_id": award["award_id"],
        "buyer": award["buyer"],
        "title": award["title"],
        "category": award["category"],
        "supplier": award["supplier"],
        "amount": award["amount"],
        "currency": award["currency"],
        "date": award["date"],
        "source_url": award["source_url"],
    }
