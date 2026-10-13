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


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {word for word in words if len(word) > 2 and word not in BOILERPLATE}


def same_supplier(left: str, right: str) -> bool:
    """Case-only match. Legal-suffix spelling is an unfixed gap."""
    return (left or "").casefold().strip() == (right or "").casefold().strip()


@lru_cache(maxsize=1)
def load_snapshot(path: str | None = None) -> tuple[dict, ...]:
    source = path or str(DATA)
    with open(source, encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(payload["awards"])


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
