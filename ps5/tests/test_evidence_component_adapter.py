from src.evidence_component_adapter import INSUFFICIENT_DATA, adapt_evidence_row


def test_evidence_adapter_preserves_unknown_values_without_synthetic_supply_data():
    component = adapt_evidence_row(
        {"mpn": "BSS138", "manufacturer": "onsemi", "component_type": "MOSFET", "description": "Test", "package": "SOT-23", "tolerance": ""},
        "Q1",
    )
    assert component.component_id == "Q1"
    assert component.part_number == "BSS138"
    assert component.specs["tolerance"] == INSUFFICIENT_DATA
    assert component.stock is None and component.lead_time_weeks is None
