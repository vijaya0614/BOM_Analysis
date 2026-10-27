import csv
from collections import Counter

from src.schemas import BomComponent, LifecycleStatus
from data.generate_synthetic_bom import CSV_FIELDS, generate_components, lifecycle_quota, write_csv


def test_lifecycle_quota_is_70_20_10_for_500():
    statuses = lifecycle_quota(500)
    counts = Counter(statuses)
    assert counts[LifecycleStatus.ACTIVE] == 350
    assert counts[LifecycleStatus.NRND] == 100
    assert counts[LifecycleStatus.OBSOLETE] == 50


def test_generated_rows_match_pydantic_schema_and_csv_headers(tmp_path):
    components = generate_components(count=500, seed=42)
    assert len(components) == 500
    assert all(isinstance(row, BomComponent) for row in components)
    assert len({row.part_number for row in components}) == 500

    counts = Counter(row.lifecycle_status for row in components)
    assert counts[LifecycleStatus.ACTIVE] == 350
    assert counts[LifecycleStatus.NRND] == 100
    assert counts[LifecycleStatus.OBSOLETE] == 50

    out = tmp_path / "synthetic_bom_components.csv"
    write_csv(components, out)
    with out.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == CSV_FIELDS
        csv_rows = list(reader)
    assert len(csv_rows) == 500
    BomComponent.model_validate(csv_rows[0])
