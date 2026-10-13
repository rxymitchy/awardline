"""Turn PPIP release packages into the compact award snapshot the tools search."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = [
    ROOT / "data" / "ppip-2025-2026.json",
    ROOT / "data" / "ppip-2026-2027.json",
]
OUT = ROOT / "data" / "awards.json"
SOURCE = "https://tenders.go.ke/storage/OCDS/"


def awards_from_package(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        package = json.load(handle)
    found = []
    for release in package.get("releases") or []:
        tender = release.get("tender") or {}
        buyer = ((release.get("buyer") or {}).get("name") or "").strip()
        for award in release.get("awards") or []:
            value = award.get("value") or {}
            amount = value.get("amount")
            try:
                amount_f = float(amount)
            except (TypeError, ValueError):
                continue
            if amount_f <= 0:
                continue
            suppliers = award.get("suppliers") or []
            supplier = ""
            if suppliers:
                supplier = (suppliers[0].get("name") or "").strip()
            found.append(
                {
                    "ocid": release.get("ocid") or "",
                    "award_id": str(award.get("id") or ""),
                    "buyer": buyer,
                    "title": (award.get("title") or tender.get("title") or "").strip(),
                    "category": (tender.get("mainProcurementCategory") or "").strip(),
                    "method": (tender.get("procurementMethod") or "").strip(),
                    "supplier": supplier,
                    "amount": amount_f,
                    "currency": (value.get("currency") or "KES").strip() or "KES",
                    "date": (release.get("date") or "")[:10],
                    "source_url": SOURCE + path.name,
                }
            )
    return found


def main() -> None:
    rows = []
    used = []
    for path in RAW:
        if not path.exists():
            continue
        batch = awards_from_package(path)
        rows.extend(batch)
        used.append({"file": path.name, "awards": len(batch)})
    # Later financial years win when PPIP repeats an award id.
    deduped = {}
    for row in rows:
        deduped[(row["ocid"], row["award_id"])] = row
    awards = list(deduped.values())
    payload = {
        "source": "Kenya PPIP OCDS release packages, Public Procurement Regulatory Authority",
        "source_pages": [SOURCE + name for name in ("2025-2026.json", "2026-2027.json")],
        "files": used,
        "award_count": len(awards),
        "awards": awards,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    print(f"wrote {len(awards)} awards to {OUT}")


if __name__ == "__main__":
    main()
