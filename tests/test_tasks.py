import json
from pathlib import Path

import awardline.notes as notes
from awardline.agent import build_graph
from awardline.awards import same_supplier, search_awards
from awardline.drop import file_committee_note
from awardline.evaluate import (
    history,
    task_draft_cites_every_source,
    task_loosely_related_award_is_excluded,
    task_supplier_history_merges_spellings,
    task_supplier_suffix_is_one_firm,
)
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


def test_approval_for_an_earlier_draft_does_not_file_a_redraft(tmp_path: Path, monkeypatch):
    drafts = tmp_path / "drafts"
    approvals = tmp_path / "approvals"
    drafts.mkdir()
    approvals.mkdir()
    monkeypatch.setattr(notes, "DRAFTS", drafts)
    monkeypatch.setattr(notes, "APPROVALS", approvals)
    (drafts / "note-x.json").write_text(
        json.dumps({"note_id": "note-x", "revision": "rev-1", "text": "draft"}), encoding="utf-8"
    )
    assert notes.record_approval("note-x", "Amina Yusuf")["ok"]
    # The agent drafts the same quote again: same note_id, new revision.
    (drafts / "note-x.json").write_text(
        json.dumps({"note_id": "note-x", "revision": "rev-2", "text": "draft"}), encoding="utf-8"
    )
    result = file_committee_note("note-x")
    assert result["ok"] is False
    assert "earlier draft" in result["error"]
    assert list(tmp_path.rglob("*.md")) == []


def test_a_changed_quote_is_sent_back_to_the_model():
    class Once:
        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "flag_price_outlier",
                            "arguments": {"buyer": "Kitui", "query": "fuel", "amount": 200000},
                        }
                    ],
                }
            return {"role": "assistant", "content": "stopped", "tool_calls": []}

    result = build_graph(Once()).invoke(
        {
            "messages": [{"role": "user", "content": "Quote of KES 2,000,000.00 for fuel."}],
            "steps": 0,
        }
    )
    tool_messages = [message for message in result["messages"] if message["role"] == "tool"]
    payload = json.loads(tool_messages[0]["content"])
    assert payload["ok"] is False
    assert "2,000,000.00" in payload["error"]


def test_live_agent_calls_the_mcp_server():
    from awardline.agent import call_awardline_tool

    result = call_awardline_tool("search_awards", {"buyer": "", "query": ""})
    assert result["ok"] is False
    assert "buyer" in result["error"].lower()


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


def test_supplier_suffix_is_one_firm():
    assert same_supplier("KIOLI INVESTMENTS LIMITED", "Kioli Investments Ltd")
    task_supplier_suffix_is_one_firm()


def test_loosely_related_award_is_excluded():
    task_loosely_related_award_is_excluded()


def test_supplier_history_merges_spellings():
    task_supplier_history_merges_spellings()


def test_supplier_merges_on_the_real_snapshot():
    """Real PPIP spellings of one firm merge, and a country qualifier keeps firms apart."""
    from collections import defaultdict

    from awardline.awards import load_snapshot, supplier_key

    groups = defaultdict(set)
    for award in load_snapshot():
        groups[supplier_key(award["supplier"])].add(award["supplier"])
    assert {"KIOLI INVESTMENTS LIMITED", "M/S KIOLI INVESTMENTS LIMITED"} <= groups["kioli investments"]
    assert supplier_key("BRITAM GENERAL INSURANCE COMPANY (KENYA ) LIMITED") != supplier_key(
        "BRITAM GENERAL INSURANCE COMPANY LIMITED"
    )


def test_refresh_keeps_last_snapshot_when_download_fails(tmp_path: Path):
    import httpx

    from awardline.snapshot import refresh

    out = tmp_path / "awards.json"
    out.write_text('{"awards": []}', encoding="utf-8")
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    result = refresh(data_dir=tmp_path, out=out, client=client)
    assert result["ok"] is False
    assert out.read_text(encoding="utf-8") == '{"awards": []}'
    assert not list(tmp_path.glob("*.part"))


def test_refresh_rebuilds_snapshot_from_downloaded_packages(tmp_path: Path):
    import httpx

    from awardline.snapshot import refresh

    package = {
        "releases": [
            {
                "ocid": "ocds-test-9",
                "date": "2026-07-01T00:00:00Z",
                "buyer": {"name": "Example County"},
                "tender": {"title": "Fresh milk"},
                "awards": [
                    {"id": "a1", "value": {"amount": 1000, "currency": "KES"}, "suppliers": [{"name": "Dairy Ltd"}]}
                ],
            }
        ]
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=package)))
    out = tmp_path / "awards.json"
    result = refresh(data_dir=tmp_path, out=out, client=client)
    assert result["ok"], result
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["retrieved_at"]
    # Both financial-year packages returned the same award; it is kept once.
    assert payload["award_count"] == 1
    assert payload["awards"][0]["supplier"] == "Dairy Ltd"


def test_a_dropped_supplier_is_sent_back_to_the_model():
    calls = []

    class Scripted:
        def chat(self, messages):
            calls.append(len(calls))
            if len(calls) == 1:
                arguments = {"buyer": "Kitui", "query": "fuel", "amount": 2000000}
                return {"role": "assistant", "content": "", "tool_calls": [{"name": "flag_price_outlier", "arguments": arguments}]}
            return {"role": "assistant", "content": "stopped", "tool_calls": []}

    request = "Quote of KES 2,000,000.00 from supplier Kioli Investments Ltd for: fuel."
    result = build_graph(Scripted()).invoke({"messages": [{"role": "user", "content": request}], "steps": 0})
    payload = json.loads([m for m in result["messages"] if m["role"] == "tool"][0]["content"])
    assert payload["ok"] is False
    assert 'supplier set to "Kioli Investments Ltd"' in payload["error"]


def test_a_supplier_spelling_variant_is_accepted():
    from awardline.agent import _stated_supplier_error

    messages = [{"role": "user", "content": "Quote of KES 10.00 from supplier Kioli Investments Ltd for: fuel."}]
    assert _stated_supplier_error("flag_price_outlier", {"supplier": "KIOLI INVESTMENTS LIMITED"}, messages) is None
    assert _stated_supplier_error("search_awards", {}, messages) is None
    assert _stated_supplier_error("flag_price_outlier", {}, [{"role": "user", "content": "Quote of KES 10.00 for fuel."}]) is None


def test_model_sees_a_compact_flag_and_the_draft_keeps_full_sources(tmp_path: Path, monkeypatch):
    from awardline.agent import for_model

    monkeypatch.setattr(notes, "FLAGS", tmp_path)
    monkeypatch.setattr(notes, "DRAFTS", tmp_path)
    monkeypatch.setattr(notes, "load_snapshot", lambda path=None: tuple(history()))
    flag = notes.tool_flag_price_outlier("Example County", "fresh milk school feeding", 500000)
    compact = for_model("flag_price_outlier", flag)
    assert "sources" not in compact and compact["flagged"] is True and compact["note_id"] == flag["note_id"]
    assert len(json.dumps(compact)) < len(json.dumps(flag)) / 2
    draft = notes.tool_draft_committee_note("Example County", "fresh milk school feeding", 500000)
    assert "text" not in for_model("draft_committee_note", draft)
    assert all(source["ocid"] in draft["text"] for source in flag["sources"])
    error = {"ok": False, "error": "amount must be a number"}
    assert for_model("flag_price_outlier", error) is error
