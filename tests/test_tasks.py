import json
from pathlib import Path

import pytest

import awardline.notes as notes
from awardline.agent import build_graph
from awardline.awards import same_supplier, search_awards
from awardline.drop import file_committee_note
from awardline.evaluate import history, task_draft_cites_every_source
from awardline.score import flag_price_outlier


def test_search_finds_buyer():
    result = search_awards(buyer="Example County", query="milk", awards=history())
    assert result["ok"]
    assert result["awards"]


def test_search_with_no_clue_fails_closed():
    result = search_awards("", "", awards=history())
    assert result["ok"] is False


def test_high_quote_is_sourced_flag():
    finding = flag_price_outlier(history(), "Example County", "fresh milk school feeding", 500000)
    assert finding["flagged"] is True
    assert all(row["ocid"] for row in finding["sources"])


def test_typical_quote_is_not_flagged():
    finding = flag_price_outlier(history(), "Example County", "fresh milk school feeding", 100000)
    assert finding["flagged"] is False
    assert finding["sources"]


def test_thin_history_does_not_flag():
    finding = flag_price_outlier(history()[:3], "Example County", "fresh milk school feeding", 900000)
    assert finding["reason"] == "insufficient_history"


def test_draft_cites_sources(tmp_path: Path):
    flags = tmp_path / "flags"
    flags.mkdir()
    task_draft_cites_every_source(flags)


def test_file_without_officer_writes_nothing(tmp_path: Path, monkeypatch):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    monkeypatch.setattr(notes, "DRAFTS", drafts)
    monkeypatch.setattr(notes, "APPROVALS", tmp_path / "approvals")
    (drafts / "note-x.json").write_text(json.dumps({"note_id": "note-x", "text": "draft"}), encoding="utf-8")
    result = file_committee_note("note-x")
    assert result["ok"] is False
    assert list(tmp_path.glob("*.md")) == []


def test_agent_recovers_from_an_unknown_tool():
    replies = [
        {"role": "assistant", "content": "", "tool_calls": [{"name": "award_tender", "arguments": {}}]},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": "search_awards", "arguments": {"buyer": "", "query": ""}}],
        },
        {"role": "assistant", "content": "Search needs a buyer or a description. Stopping.", "tool_calls": []},
    ]

    class Scripted:
        def chat(self, messages):
            return replies.pop(0)

    result = build_graph(Scripted()).invoke(
        {"messages": [{"role": "user", "content": "Check a quote."}], "steps": 0}
    )
    names = [message.get("name") for message in result["messages"] if message.get("role") == "tool"]
    assert names == ["award_tender", "search_awards"]
    assert "Unknown tool" in result["messages"][2]["content"] or "unknown" in result["messages"][2]["content"].lower()


@pytest.mark.xfail(reason="Ltd and Limited are not treated as one supplier. EVALS.md T9.", strict=True)
def test_supplier_suffix_still_unresolved():
    assert same_supplier("KIOLI INVESTMENTS LIMITED", "Kioli Investments Ltd")
