from awardline.awards import tokens


def median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return float(ordered[mid])
    return float(ordered[mid - 1] + ordered[mid]) / 2


def comparables(awards: list[dict], query: str, currency: str = "KES") -> list[dict]:
    wanted = tokens(query)
    if len(wanted) < 1:
        return []
    scored: list[tuple[int, dict]] = []
    for award in awards:
        if (award.get("currency") or "KES") != currency:
            continue
        shared = wanted & tokens(award.get("title") or "")
        if len(shared) < 2:
            continue
        scored.append((len(shared), award))
    scored.sort(key=lambda item: (item[0], item[1].get("date") or ""), reverse=True)
    return [award for _, award in scored[:12]]


def flag_price_outlier(
    awards: list[dict],
    buyer: str,
    query: str,
    amount: float,
    currency: str = "KES",
) -> dict:
    history = comparables(awards, query, currency)
    sources = [_source(row) for row in history]
    if len(history) < 4:
        return {
            "ok": True,
            "flagged": False,
            "reason": "insufficient_history",
            "buyer": buyer,
            "query": query,
            "amount": amount,
            "currency": currency,
            "comparable_count": len(history),
            "median": None,
            "ratio": None,
            "sources": sources,
        }
    typical = median([float(row["amount"]) for row in history])
    ratio = None if typical == 0 else round(float(amount) / typical, 2)
    flagged = typical > 0 and float(amount) >= typical * 2
    return {
        "ok": True,
        "flagged": flagged,
        "reason": "above_twice_median" if flagged else "within_range",
        "buyer": buyer,
        "query": query,
        "amount": float(amount),
        "currency": currency,
        "comparable_count": len(history),
        "median": round(typical, 2),
        "ratio": ratio,
        "sources": sources,
    }


def _source(award: dict) -> dict:
    return {
        "ocid": award["ocid"],
        "buyer": award["buyer"],
        "title": award["title"],
        "supplier": award["supplier"],
        "amount": award["amount"],
        "currency": award["currency"],
        "date": award["date"],
        "source_url": award["source_url"],
    }
