"""Tests for the offline, provenance-first industry importer."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from src.industry_data import importer


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> importer.ImportPaths:
    project = tmp_path / "project"
    paths = importer.ImportPaths(
        incoming=project / "incoming_industry_data",
        raw=project / "data" / "industry" / "raw",
        manifests=project / "data" / "industry" / "manifests",
    )
    import src.industry_data.csv_store as csv_store
    import src.industry_data.provenance as provenance
    import src.industry_data.source_registry as source_registry

    monkeypatch.setattr(importer, "ROOT", project)
    monkeypatch.setattr(csv_store, "NORMALIZED", project / "data" / "industry" / "normalized")
    monkeypatch.setattr(provenance, "ROOT", project)
    monkeypatch.setattr(source_registry, "ROOT", project)
    paths.incoming.mkdir(parents=True)
    return paths


def _write_csv(path: Path, mpn: str = "TPS65217C") -> None:
    path.write_text(
        "Manufacturer Part Number,Manufacturer,Description,Reference,Qty,Package\n"
        f"{mpn},Texas Instruments,PMIC,U1,1,VQFN\n",
        encoding="utf-8",
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_imports_csv_and_writes_manifest_and_provenance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    _write_csv(paths.incoming / "beaglebone_black_bom.csv")

    report = importer.run_import(paths)

    assert report["bom_rows"] == 1
    assert report["errors"] == []
    assert (paths.manifests / f"{report['import_id']}.json").is_file()
    assert _rows(paths.raw.parent / "normalized" / "documents.csv")[0]["file_hash"]
    assert any(row["data_provenance"] == "REAL_PUBLIC_SOURCE" for row in _rows(paths.raw.parent / "normalized" / "field_provenance.csv"))


def test_imports_xlsx_bom(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    book = Workbook()
    sheet = book.active
    sheet.append(["Report title"])
    sheet.append(["MPN", "Mfr", "Description", "RefDes", "Qty", "Footprint"])
    sheet.append(["AM3358BZCZ100", "Texas Instruments", "MPU", "U1", 1, "BGA"])
    book.save(paths.incoming / "beaglebone_black.xlsx")

    report = importer.run_import(paths)

    assert report["bom_rows"] == 1
    assert report["boms_detected"][0]["unique_mpns"] == 1


def test_preserves_bom_tolerance_and_attributes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    (paths.incoming / "custom_bom.csv").write_text(
        "Title row\nMPN,Manufacturer,Description,Reference,Qty,Tolerance,Voltage Rating\nR100,TI,Resistor,R1,1,1%,25V\n",
        encoding="utf-8",
    )

    report = importer.run_import(paths)
    normalized = paths.raw.parent / "normalized"

    assert report["bom_rows"] == 1
    specs = _rows(normalized / "component_specs.csv")
    tolerances = _rows(normalized / "tolerance_records.csv")
    assert {row["parameter_name"] for row in specs} >= {"Tolerance", "Voltage Rating"}
    assert tolerances[0]["tolerance_value"] == "1%"


def test_imports_safe_zip_and_registers_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    archive = paths.incoming / "TIDA-00222.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("design/BOM.csv", "MPN,Manufacturer,Description,RefDes,Qty\nTPS5402DGQ,Texas Instruments,REG,U1,1\n")
        handle.writestr("design/schematic.pdf", b"%PDF-1.4\n")

    report = importer.run_import(paths)
    documents = _rows(paths.raw.parent / "normalized" / "documents.csv")

    assert report["bom_rows"] == 1
    assert any(row["document_type"] == "pdf" and row["extraction_status"] == "EXTRACTED_SAFE" for row in documents)
    assert (paths.raw / "ti_tida_00222" / "TIDA-00222.zip").is_file()


def test_duplicate_hash_does_not_reimport(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    _write_csv(paths.incoming / "beaglebone_black_bom.csv")
    importer.run_import(paths)

    report = importer.run_import(paths)

    assert report["duplicates"] == ["beaglebone_black_bom.csv"]
    assert report["bom_rows"] == 0


def test_dry_run_is_non_mutating(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    _write_csv(paths.incoming / "beaglebone_black_bom.csv")

    report = importer.run_import(paths, dry_run=True)

    assert report["bom_rows"] == 1
    assert not paths.raw.exists()
    assert not paths.manifests.exists()


def test_path_traversal_member_is_never_extracted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    with zipfile.ZipFile(paths.incoming / "TIDEP0050.zip", "w") as handle:
        handle.writestr("../escape.csv", "MPN\nBAD\n")

    report = importer.run_import(paths)

    assert any(item.startswith("ZIP_PATH_TRAVERSAL_SKIPPED") for item in report["warnings"])
    assert not (tmp_path / "escape.csv").exists()


def test_malformed_zip_and_unsupported_file_are_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    (paths.incoming / "broken.zip").write_bytes(b"not a zip")
    (paths.incoming / "runme.exe").write_bytes(b"not executed")

    report = importer.run_import(paths)

    assert any(item.startswith("MALFORMED_ZIP") for item in report["warnings"])
    assert any(item.startswith("UNSUPPORTED_FILE_SKIPPED") for item in report["warnings"])


def test_multiple_products_and_manifest_contents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = _isolate(monkeypatch, tmp_path)
    _write_csv(paths.incoming / "beaglebone_black_bom.csv", "AM3358BZCZ100")
    _write_csv(paths.incoming / "TIDA-00222_BOM.csv", "TPS5402DGQ")

    report = importer.run_import(paths)
    manifest = json.loads((paths.manifests / f"{report['import_id']}.json").read_text(encoding="utf-8"))

    assert {"beaglebone-black", "ti-tida-00222"}.issubset(set(report["products_detected"]))
    assert manifest["bom_rows"] == 2
    assert manifest["input_files"] == sorted(manifest["input_files"], key=str.casefold)
