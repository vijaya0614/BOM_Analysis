"""API Route and Integration Tests for PS5 FastAPI application.

Verifies:
- /health and /metrics
- /api/bom/template and /api/bom/synthetic
- /api/bom/validate
- /api/obsolescence/forecast
- /api/market/supply-pressure
- /api/physical/compatibility
- /api/tolerances/analyze
- /api/mission-profile/evaluate
- /api/substitutes/evaluate-gates
- /api/fmea/analyze
- /api/cost/scenarios
- /api/product/risk-summary
- /api/scenarios/compare
- /api/reports/full
"""

import pytest
from starlette.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "PS5 Risk Engine"


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "ps5_requests_total" in response.text


def test_bom_template_and_synthetic_endpoints():
    template_res = client.get("/api/bom/template")
    assert template_res.status_code == 200
    assert "part_number" in template_res.json()["csv_template"]

    synth_res = client.get("/api/bom/synthetic")
    assert synth_res.status_code == 200
    assert synth_res.json()["total_components"] >= 15


def test_bom_validate_endpoint():
    valid_csv = "part_number,reference_designator,qty,unit_cost,lifecycle_status\nTPS5402,U1,1,1.50,ACTIVE\n"
    res = client.post("/api/bom/validate", json={"csv_text": valid_csv})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["valid_rows_count"] == 1


def test_obsolescence_forecast_endpoint():
    payload = {
        "part_number": "TPS5402DGQR",
        "category": "Power Management",
        "lifecycle_status": "ACTIVE",
        "introduction_year": 2018,
    }
    res = client.post("/api/obsolescence/forecast", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "1_year" in data["horizons"]
    assert "3_year" in data["horizons"]
    assert "5_year" in data["horizons"]


def test_market_supply_pressure_endpoint():
    payload = {
        "part_number": "TPS5402DGQR",
        "available_stock": 25000,
        "weekly_demand": 150.0,
        "estimated_lead_time_weeks": 8.0,
        "supplier_count": 3,
    }
    res = client.post("/api/market/supply-pressure", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "supply_pressure_index" in data
    assert len(data["tolerance_checks"]) > 0


def test_physical_compatibility_endpoint():
    payload = {
        "original_part": "TPS5402",
        "candidate_part": "AP63200",
        "orig_package": "SOIC-8",
        "cand_package": "SOIC-8",
        "orig_mounting": "SMD",
        "cand_mounting": "SMD",
        "orig_pin_count": 8,
        "cand_pin_count": 8,
    }
    res = client.post("/api/physical/compatibility", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["classification"] == "DROP_IN_CANDIDATE"


def test_tolerances_analyze_endpoint():
    payload = {
        "circuit_type": "voltage_divider",
        "r1_ohms": 10000.0,
        "r2_ohms": 10000.0,
        "vin_volts": 5.0,
        "sample_count": 500,
    }
    res = client.post("/api/tolerances/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert abs(data["nominal_output"] - 2.50) < 1e-2
    assert len(data["histogram_bins"]) == 15


def test_mission_profile_evaluate_endpoint():
    payload = {
        "component_name": "Step-Down Regulator",
        "part_number": "TPS5402",
        "thermal_resistance_c_per_w": 40.0,
        "phases": [
            {
                "name": "Standard Load",
                "annual_hours": 4000,
                "ambient_temp_c": 35.0,
                "power_dissipation_watts": 1.2,
                "operating_voltage": 5.0,
                "operating_current": 0.24,
            }
        ],
    }
    res = client.post("/api/mission-profile/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["peak_junction_temp_c"] > 35.0
    assert len(data["mitigation_comparisons"]) == 3


def test_substitutes_evaluate_gates_endpoint():
    def citation(value):
        return {
            "source_id": f"SRC-{value}",
            "source_title": "Manufacturer datasheet",
            "source_url": "https://manufacturer.example/datasheet.pdf",
            "source_page": "4",
            "confidence": "HIGH",
            "source_type": "MANUFACTURER_DATASHEET",
            "evidence_summary": str(value),
        }

    def evidence(package, pinout, voltage, current, temperature):
        return {
            "package": citation(package),
            "pinout": citation(pinout),
            "ratings": {
                "voltage_rating": citation(voltage),
                "current_rating": citation(current),
                "temperature_rating": citation(temperature),
            },
        }

    payload = {
        "original_spec": {
            "part_number": "ORIG",
            "category": "Power Management",
            "operating_voltage_max": 28.0,
            "operating_current_max": 2.0,
            "operating_temperature_max": 125.0,
            "package": "SOIC-8",
            "mounting": "SMD",
            "pinout": "1=VIN,2=GND",
            "evidence": evidence("SOIC-8", "1=VIN,2=GND", 28.0, 2.0, 125.0),
        },
        "candidate_specs": [
            {
                "part_number": "CAND_GOOD",
                "category": "Power Management",
                "operating_voltage_max": 30.0,
                "operating_current_max": 2.5,
                "operating_temperature_max": 125.0,
                "package": "SOIC-8",
                "mounting": "SMD",
                "pinout": "1=VIN,2=GND",
                "evidence": evidence("SOIC-8", "1=VIN,2=GND", 30.0, 2.5, 125.0),
            }
        ],
    }
    res = client.post("/api/substitutes/evaluate-gates", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["drop_in_candidates"]) == 1


def test_fmea_analyze_endpoint():
    payload = {
        "part_number": "TPS5402",
        "category": "regulator",
    }
    res = client.post("/api/fmea/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_modes"] >= 2


def test_cost_scenarios_endpoint():
    payload = {
        "part_number": "TPS5402",
        "annual_volume": 5000,
        "horizon_years": 5,
        "current_unit_price": 1.50,
    }
    res = client.post("/api/cost/scenarios", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "STRATEGY_A" in data["strategies"]
    assert "STRATEGY_B" in data["strategies"]
    assert "STRATEGY_C" in data["strategies"]
    assert "STRATEGY_D" in data["strategies"]


def test_product_risk_summary_endpoint():
    payload = {
        "product_name": "Test Assembly",
        "components": [
            {"pn": "IC1", "ref": "U1", "qty": 1, "score": 0.8, "band": "CRITICAL", "lifecycle_status": "EOL"},
            {"pn": "R1", "ref": "R1", "qty": 4, "score": 0.1, "band": "LOW", "lifecycle_status": "ACTIVE"},
        ],
    }
    res = client.post("/api/product/risk-summary", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_components_count"] == 2
    assert data["eol_count"] == 1


def test_scenarios_compare_endpoint():
    payload = {
        "part_number": "TPS5402",
        "category": "Power Management",
        "baseline_inputs": {"ambient_temperature_c": 25.0},
        "scenario_inputs": {"ambient_temperature_c": 40.0, "cooling_type": "FORCED_AIR_COOLING"},
    }
    res = client.post("/api/scenarios/compare", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["deltas"]) >= 4


def test_full_engineering_report_endpoint():
    res = client.get("/api/reports/full")
    assert res.status_code == 200
    data = res.json()
    assert "product_summary" in data
    assert "focused_component_audit" in data


def test_vendor_intelligence_endpoints():
    # Curated component check
    res = client.get("/api/vendor/intelligence/TPS5402DGQR")
    assert res.status_code == 200
    data = res.json()
    assert data["part_number"] == "TPS5402DGQR"
    assert data["manufacturer"] == "Texas Instruments"
    assert "lifecycle" in data
    assert "geological" in data
    assert "market_saturation" in data
    assert "resilience" in data
    assert len(data["market_saturation"]["distributors"]) >= 5
    assert data["geological"]["primary_fab_country"] == "USA"
    assert data["data_source"] == "CURATED_STATIC_DEMO_DATA"
    assert {row["data_provenance"] for row in data["vendor_records"]} == {"SYNTHETIC_DERIVED_DEMO_DATA"}
    assert {row["retrieval_state"] for row in data["vendor_records"]} == {"UNKNOWN"}
    assert all(row["authorized"] is None for row in data["vendor_records"])

    # Industry route returns normalized catalog evidence, not demo vendor quotes.
    res_ind = client.get("/api/industry/component/STM32F401RET6")
    assert res_ind.status_code == 200
    ind_data = res_ind.json()
    assert ind_data["mpn"] == "STM32F401RET6"
    assert ind_data["data_source"] in {"REAL_PUBLIC_SOURCE", "REAL_DISTRIBUTOR_DATA", "MISSING"}

    # Arbitrary uncataloged part dynamic generation check
    res_dyn = client.get("/api/vendor/intelligence/CUSTOM-IC-9900")
    assert res_dyn.status_code == 200
    dyn_data = res_dyn.json()
    assert dyn_data["part_number"] == "CUSTOM-IC-9900"
    assert dyn_data["data_source"] == "SYNTHETIC_DEMO_DATA"
    assert dyn_data["resilience"]["sourcing_security"] > 0
    assert len(dyn_data["market_saturation"]["distributors"]) == 6

