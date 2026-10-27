"""Algorithm tests use a labeled in-memory fixture, never a demo BOM graph."""

from src.component_intelligence import INSUFFICIENT_DATA, get_downstream_impact
from src.dependency_graph import load_component_graph, traverse_downstream


FIXTURE_GRAPH_ROWS = [
    {
        "edge_id": "fixture-1", "product_id": "fixture-board", "source_node": "U1",
        "target_node": "VDD_3V3", "relationship_type": "POWERS", "function": "3.3 V rail",
        "confidence": "HIGH", "source": "fixture-netlist",
    },
    {
        "edge_id": "fixture-2", "product_id": "fixture-board", "source_node": "VDD_3V3",
        "target_node": "U2", "relationship_type": "POWERS", "function": "MCU supply",
        "confidence": "HIGH", "source": "fixture-netlist",
    },
    {
        "edge_id": "fixture-3", "product_id": "fixture-board", "source_node": "U2",
        "target_node": "UNKNOWN", "relationship_type": "FEEDS_SIGNAL", "function": "unresolved output",
        "confidence": "LOW", "source": "fixture-netlist",
    },
]


def test_traversal_preserves_explicit_paths_and_unresolved_segments():
    graph = load_component_graph("fixture-board", "U1", rows=FIXTURE_GRAPH_ROWS)
    affected = traverse_downstream(graph, "U1")

    assert affected[1]["node_id"] == "U2"
    assert affected[1]["path"] == ["U1", "VDD_3V3", "U2"]
    assert affected[2]["node_id"] == INSUFFICIENT_DATA
    assert affected[2]["status"] == INSUFFICIENT_DATA
    assert affected[2]["path"] == ["U1", "VDD_3V3", "U2", INSUFFICIENT_DATA]


def test_downstream_impact_returns_the_real_beaglebone_black_graph():
    impact = get_downstream_impact("U1")

    assert impact["status"] == "FOUND"
    assert impact["product_id"] == "beaglebone-black"
    assert any(item["path"] == ["U1", "U12"] for item in impact["data"])


def test_downstream_impact_stays_insufficient_for_unmapped_beaglebone_component():
    impact = get_downstream_impact("U5", product_id="beaglebone-black")

    assert impact["status"] == INSUFFICIENT_DATA


def test_downstream_impact_returns_fixture_paths_when_graph_evidence_exists(monkeypatch):
    monkeypatch.setattr("src.dependency_graph.read_csv", lambda _: FIXTURE_GRAPH_ROWS)

    impact = get_downstream_impact("U1", product_id="fixture-board")

    assert impact["status"] == "FOUND"
    assert impact["confidence"] == INSUFFICIENT_DATA
    assert impact["product_id"] == "fixture-board"
    assert impact["data"][1]["path"] == ["U1", "VDD_3V3", "U2"]
