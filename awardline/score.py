import math
from collections import Counter

from awardline.awards import same_supplier, supplier_key, tokens

# A past award is comparable when it shares at least MIN_SHARED content words with
# the quote AND those shared words carry at least MIN_COVERAGE of the quote's
# word weight. Words are weighted by rarity across the snapshot, so a fuel quote
# is not matched to a tyre contract just because both say "motor vehicles".
MIN_SHARED = 2
MIN_COVERAGE = 0.5
MIN_HISTORY = 4
MAX_SOURCES = 12
SUPPLIER_HISTORY_LIMIT = 8


def median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return float(ordered[mid])
    return float(ordered[mid - 1] + ordered[mid]) / 2


def word_weights(awards: list[dict]) -> dict[str, float]:
    """Smoothed inverse document frequency of each title word in the snapshot."""
    frequency: Counter[str] = Counter()
    for award in awards:
        frequency.update(tokens(award.get("title") or ""))
    total = len(awards)
    return {word: math.log((total + 1) / (count + 1)) + 1 for word, count in frequency.items()}


def _weight(word: str, weights: dict[str, float], total: int) -> float:
    # A word that never appears in the snapshot is as rare as a word can be.
    return weights.get(word, math.log(total + 1) + 1)


def comparables(awards: list[dict], query: str, currency: str = "KES") -> list[dict]:
    """Return comparable awards, each with the words that matched and the coverage."""
    wanted = tokens(query)
    if not wanted:
        return []
    weights = word_weights(awards)
    total = len(awards)
    wanted_weight = sum(_weight(word, weights, total) for word in wanted)
    needed = min(MIN_SHARED, len(wanted))
    scored: list[tuple[float, dict]] = []
    for award in awards:
        if (award.get("currency") or "KES") != currency:
            continue
        shared = wanted & tokens(award.get("title") or "")
        if len(shared) < needed:
            continue
        coverage = sum(_weight(word, weights, total) for word in shared) / wanted_weight
        if coverage < MIN_COVERAGE:
            continue
        scored.append((coverage, {**award, "matched_words": sorted(shared), "coverage": round(coverage, 2)}))
    scored.sort(key=lambda item: (item[0], item[1].get("date") or ""), reverse=True)
    return [award for _, award in scored[:MAX_SOURCES]]


def supplier_history(awards: list[dict], supplier: str) -> dict | None:
    """Past awards to the same firm, with every spelling of its name that was merged."""
    if not supplier_key(supplier):
        return None
    rows = [award for award in awards if same_supplier(award.get("supplier") or "", supplier)]
    rows.sort(key=lambda award: award.get("date") or "", reverse=True)
    return {
        "supplier": supplier,
        "key": supplier_key(supplier),
        "award_count": len(rows),
        "total_amount": round(sum(float(award["amount"]) for award in rows), 2),
        # Names that differ only by spacing are shown once.
        "names_merged": sorted({" ".join(award["supplier"].split()) for award in rows}),
        "awards": [_source(award) for award in rows[:SUPPLIER_HISTORY_LIMIT]],
    }


def flag_price_outlier(
    awards: list[dict],
    buyer: str,
    query: str,
    amount: float,
    currency: str = "KES",
    supplier: str = "",
) -> dict:
    history = comparables(awards, query, currency)
    sources = [_source(row) for row in history]
    for source in sources:
        source["same_supplier"] = bool(supplier) and same_supplier(source["supplier"], supplier)
    base = {
        "ok": True,
        "buyer": buyer,
        "query": query,
        "amount": float(amount),
        "currency": currency,
        "supplier": supplier or "",
        "supplier_history": supplier_history(awards, supplier) if supplier else None,
        "comparable_count": len(history),
        "sources": sources,
    }
    if len(history) < MIN_HISTORY:
        return {**base, "flagged": False, "reason": "insufficient_history", "median": None, "ratio": None}
    typical = median([float(row["amount"]) for row in history])
    ratio = None if typical == 0 else round(float(amount) / typical, 2)
    flagged = typical > 0 and float(amount) >= typical * 2
    return {
        **base,
        "flagged": flagged,
        "reason": "above_twice_median" if flagged else "within_range",
        "median": round(typical, 2),
        "ratio": ratio,
    }


def _source(award: dict) -> dict:
    source = {
        "ocid": award["ocid"],
        "buyer": award["buyer"],
        "title": award["title"],
        "supplier": award["supplier"],
        "amount": award["amount"],
        "currency": award["currency"],
        "date": award["date"],
        "source_url": award["source_url"],
    }
    if "matched_words" in award:
        source["matched_words"] = award["matched_words"]
        source["coverage"] = award["coverage"]
    return source
