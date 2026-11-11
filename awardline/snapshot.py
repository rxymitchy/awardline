"""Build, and optionally re-download, the PPIP award snapshot the tools search."""

import json
from datetime import datetime, timezone
from pathlib import Path

from awardline.paths import ROOT

DATA_DIR = ROOT / "data"
OUT = DATA_DIR / "awards.json"
SOURCE = "https://tenders.go.ke/storage/OCDS/"
# Local file name -> PPIP release package published for that financial year.
PACKAGES = {
    "ppip-2025-2026.json": SOURCE + "2025-2026.json",
    "ppip-2026-2027.json": SOURCE + "2026-2027.json",
}


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


def build_snapshot(data_dir: Path = DATA_DIR, out: Path = OUT, retrieved_at: str | None = None) -> dict:
    rows = []
    used = []
    for name in PACKAGES:
        path = data_dir / name
        if not path.exists():
            continue
        batch = awards_from_package(path)
        rows.extend(batch)
        used.append({"file": name, "awards": len(batch)})
    # Later financial years win when PPIP repeats an award id.
    deduped = {}
    for row in rows:
        deduped[(row["ocid"], row["award_id"])] = row
    awards = list(deduped.values())
    payload = {
        "source": "Kenya PPIP OCDS release packages, Public Procurement Regulatory Authority",
        "source_pages": list(PACKAGES.values()),
        "files": used,
        "retrieved_at": retrieved_at,
        "award_count": len(awards),
        "awards": awards,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return {"ok": True, "path": str(out), "award_count": len(awards), "files": used, "retrieved_at": retrieved_at}


def refresh(data_dir: Path = DATA_DIR, out: Path = OUT, client=None) -> dict:
    """Download the current PPIP release packages, then rebuild the snapshot.

    Each package is written to a temporary file and only replaces the old copy once it
    has downloaded completely and parsed as JSON, so a failed download keeps the last
    good snapshot.
    """
    import httpx

    owns_client = client is None
    client = client or httpx.Client(timeout=300, follow_redirects=True)
    downloaded = []
    try:
        for name, url in PACKAGES.items():
            target = data_dir / name
            partial = target.with_suffix(".part")
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
            with partial.open(encoding="utf-8") as handle:
                json.load(handle)
            partial.replace(target)
            downloaded.append({"file": name, "url": url, "bytes": target.stat().st_size})
    except Exception as exc:
        for name in PACKAGES:
            (data_dir / name).with_suffix(".part").unlink(missing_ok=True)
        return {"ok": False, "error": f"Download failed, snapshot unchanged: {exc}", "downloaded": downloaded}
    finally:
        if owns_client:
            client.close()
    result = build_snapshot(data_dir, out, retrieved_at=datetime.now(timezone.utc).isoformat())
    result["downloaded"] = downloaded
    from awardline.awards import load_snapshot

    load_snapshot.cache_clear()
    return result
