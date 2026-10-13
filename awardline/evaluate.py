"""Eight passing checks and one failure we did not fix."""

import json
from pathlib import Path

from awardline.awards import same_supplier, search_awards
from awardline.drop import file_committee_note
from awardline.notes import render_note, tool_draft_committee_note, tool_flag_price_outlier
from awardline.score import flag_price_outlier

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results.json"


def _award(number: int, amount: float, title: str = "Fresh milk for school feeding") -> dict:
    return {
        "ocid": f"ocds-test-{number}",
        "award_id": str(number),
        "buyer": "Example County",
        "title": title,
        "category": "goods",
        "method": "open",
        "supplier": f"Supplier {number} Ltd",
        "amount": amount,
        "currency": "KES",
        "date": "2025-06-01",
        "source_url": "https://tenders.go.ke/storage/OCDS/2025-2026.json",
    }


def history() -> list[dict]:
    return [_award(index, amount) for index, amount in enumerate([90000, 100000, 110000, 105000], start=1)]


def task_search_finds_buyer() -> None:
    rows = history()
    result = search_awards(buyer="Example County", query="milk", awards=rows)
    assert result["ok"]
    assert result["awards"][0]["ocid"] == "ocds-test-1"


def task_search_requires_a_clue() -> None:
    result = search_awards(buyer="", query="", awards=history())
    assert result["ok"] is False
    assert "buyer" in result["error"]


def task_high_quote_is_flagged() -> None:
    finding = flag_price_outlier(history(), "Example County", "fresh milk school feeding", 500000)
    assert finding["flagged"] is True
    assert len(finding["sources"]) >= 4
    assert all(source["ocid"].startswith("ocds-") for source in finding["sources"])


def task_typical_quote_is_not_flagged() -> None:
    finding = flag_price_outlier(history(), "Example County", "fresh milk school feeding", 100000)
    assert finding["flagged"] is False
    assert finding["reason"] == "within_range"
    assert finding["sources"]


def task_thin_history_does_not_flag() -> None:
    finding = flag_price_outlier(history()[:3], "Example County", "fresh milk school feeding", 900000)
    assert finding["flagged"] is False
    assert finding["reason"] == "insufficient_history"


def task_draft_cites_every_source(tmp_flags: Path) -> None:
    import awardline.notes as notes

    original = notes.FLAGS
    notes.FLAGS = tmp_flags
    try:
        notes.load_snapshot.cache_clear()
        original_load = notes.load_snapshot

        def _load(path=None):
            return tuple(history())

        notes.load_snapshot = _load
        flag = tool_flag_price_outlier("Example County", "fresh milk school feeding", 500000)
        draft = tool_draft_committee_note("Example County", "fresh milk school feeding", 500000)
        assert draft["ok"]
        for source in flag["sources"]:
            assert source["ocid"] in draft["text"]
        missing = tool_draft_committee_note("Example County", "diesel for generators", 500000)
        assert missing["ok"] is False
    finally:
        notes.FLAGS = original
        notes.load_snapshot = original_load


def task_file_refuses_without_officer(tmp_root: Path) -> None:
    import awardline.notes as notes

    notes.DRAFTS = tmp_root / "drafts"
    notes.APPROVALS = tmp_root / "approvals"
    notes.DRAFTS.mkdir()
    note_id = "note-testrefuse"
    (notes.DRAFTS / f"{note_id}.json").write_text(
        json.dumps({"note_id": note_id, "text": "draft"}),
        encoding="utf-8",
    )
    result = file_committee_note(note_id)
    assert result["ok"] is False
    assert "approval" in result["error"].lower()
    assert not (tmp_root / f"{note_id}.md").exists()


def task_approved_note_can_be_filed(tmp_root: Path) -> None:
    import awardline.drop as drop
    import awardline.notes as notes

    notes.DRAFTS = tmp_root / "drafts"
    notes.APPROVALS = tmp_root / "approvals"
    notes.DRAFTS.mkdir()
    notes.APPROVALS.mkdir()
    note_id = "note-testfile"
    text = render_note(
        {
            "note_id": note_id,
            "buyer": "Example County",
            "query": "fresh milk",
            "amount": 500000,
            "currency": "KES",
            "flagged": True,
            "reason": "above_twice_median",
            "comparable_count": 4,
            "median": 102500,
            "ratio": 4.88,
            "sources": [
                {
                    "ocid": "ocds-test-1",
                    "buyer": "Example County",
                    "title": "Fresh milk",
                    "supplier": "Supplier 1 Ltd",
                    "amount": 100000,
                    "currency": "KES",
                    "date": "2025-06-01",
                    "source_url": "https://tenders.go.ke/storage/OCDS/2025-2026.json",
                }
            ],
        }
    )
    (notes.DRAFTS / f"{note_id}.json").write_text(json.dumps({"note_id": note_id, "text": text}), encoding="utf-8")
    (notes.APPROVALS / f"{note_id}.json").write_text(
        json.dumps(
            {
                "note_id": note_id,
                "officer": "Amina Yusuf",
                "decision": "approve",
                "approved_at": "2026-10-13T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    target = tmp_root / "filings"

    def _write(filename: str, content: str) -> str:
        target.mkdir(exist_ok=True)
        path = target / filename
        path.write_text(content, encoding="utf-8")
        return str(path)

    original = drop.write_committee_file
    drop.write_committee_file = _write
    try:
        result = file_committee_note(note_id)
    finally:
        drop.write_committee_file = original
    assert result["ok"]
    assert result["officer"] == "Amina Yusuf"
    assert "ocds-test-1" in (target / f"{note_id}.md").read_text(encoding="utf-8")


def task_supplier_suffix_still_unresolved() -> None:
    # Desired, not implemented: treat Ltd and Limited as the same supplier.
    assert same_supplier("KIOLI INVESTMENTS LIMITED", "Kioli Investments Ltd")


TASKS = [
    ("T1 search finds a buyer", task_search_finds_buyer, True),
    ("T2 search with no clue asks again", task_search_requires_a_clue, True),
    ("T3 a quote at 4x median is flagged and sourced", task_high_quote_is_flagged, True),
    ("T4 a quote near the median is not flagged", task_typical_quote_is_not_flagged, True),
    ("T5 thin history does not flag", task_thin_history_does_not_flag, True),
    ("T6 draft cites flag sources and refuses to invent", None, True),
    ("T7 filing without an officer is refused", None, True),
    ("T8 an approved note can be filed", None, True),
    ("T9 supplier Ltd and Limited are still different", task_supplier_suffix_still_unresolved, False),
]


def main() -> int:
    import tempfile

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flags = root / "flags"
        flags.mkdir()
        runners = {
            "T6 draft cites flag sources and refuses to invent": lambda: task_draft_cites_every_source(flags),
            "T7 filing without an officer is refused": lambda: task_file_refuses_without_officer(root / "t7"),
            "T8 an approved note can be filed": lambda: task_approved_note_can_be_filed(root / "t8"),
        }
        (root / "t7").mkdir()
        (root / "t8").mkdir()
        for name, function, should_pass in TASKS:
            runner = runners.get(name, function)
            try:
                runner()
                status = "pass"
                detail = ""
            except Exception as exc:
                status = "fail"
                detail = str(exc)
            results.append(
                {
                    "task": name,
                    "status": status,
                    "expected": "pass" if should_pass else "fail",
                    "detail": detail,
                }
            )
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for row in results:
        print(f"{row['status'].upper():4} {row['task']}")
        if row["detail"]:
            print(f"     {row['detail']}")
    unexpected = [row for row in results if (row["status"] == "pass") != (row["expected"] == "pass")]
    return 1 if unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
