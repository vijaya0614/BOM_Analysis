from src.industry_data import revision_selection


def test_selects_one_latest_observed_revision_without_merging_lines(monkeypatch):
    tables = {
        "bom_lines.csv": [
            {"product_id": "board", "revision_id": "board-rev-A", "original_mpn": "OLD", "source_id": "src_a"},
            {"product_id": "board", "revision_id": "board-rev-B", "original_mpn": "NEW", "source_id": "src_b"},
        ],
        "product_revisions.csv": [
            {"product_id": "board", "revision_id": "board-rev-A", "revision": "A", "source_id": "src_a", "release_date": ""},
            {"product_id": "board", "revision_id": "board-rev-B", "revision": "B", "source_id": "src_b", "release_date": ""},
        ],
        "source_registry.csv": [
            {"source_id": "src_a", "retrieved_at": "2025-01-01T00:00:00Z"},
            {"source_id": "src_b", "retrieved_at": "2026-01-01T00:00:00Z"},
        ],
    }
    monkeypatch.setattr(revision_selection, "read_csv", lambda name: tables[name])

    lines, quality = revision_selection.select_product_bom("board")
    assert [row["original_mpn"] for row in lines] == ["NEW"]
    assert quality["selected_revision"] == "B"
    assert quality["status"] == "REVISION_UNVERIFIED"


def test_ambiguous_revisions_without_source_times_return_no_rows(monkeypatch):
    tables = {
        "bom_lines.csv": [
            {"product_id": "board", "revision_id": "board-rev-A", "original_mpn": "A"},
            {"product_id": "board", "revision_id": "board-rev-B", "original_mpn": "B"},
        ],
        "product_revisions.csv": [
            {"product_id": "board", "revision_id": "board-rev-A", "revision": "A", "source_id": "src_a"},
            {"product_id": "board", "revision_id": "board-rev-B", "revision": "B", "source_id": "src_b"},
        ],
        "source_registry.csv": [],
    }
    monkeypatch.setattr(revision_selection, "read_csv", lambda name: tables[name])

    lines, quality = revision_selection.select_product_bom("board")
    assert lines == []
    assert quality["status"] == "AMBIGUOUS_REVISION"
