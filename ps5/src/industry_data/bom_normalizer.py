"""Normalize industry BOM rows without collapsing duplicate MPN occurrences."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.industry_data.csv_store import find_model_by_mpn, stable_id, upsert_by_key, upsert_rows
from src.industry_data.mpn_resolver import resolve_mpn
from src.industry_data.provenance import ProvenanceStore
from src.industry_data.source_registry import SourceRegistry

PRODUCTS = {
    "beaglebone_black": {
        "product_id": "beaglebone-black",
        "product_name": "BeagleBone Black",
        "manufacturer": "BeagleBoard.org",
        "product_family": "BeagleBone",
        "description": "Open BeagleBone Black single-board computer",
    },
    "beaglebone_black_wireless": {
        "product_id": "beaglebone-black-wireless",
        "product_name": "BeagleBone Black Wireless",
        "manufacturer": "BeagleBoard.org",
        "product_family": "BeagleBone",
        "description": "BeagleBone Black Wireless",
    },
    "beaglebone_ai": {
        "product_id": "beaglebone-ai",
        "product_name": "BeagleBone AI",
        "manufacturer": "BeagleBoard.org",
        "product_family": "BeagleBone",
        "description": "BeagleBone AI",
    },
    "ti_tida_00222": {
        "product_id": "ti-tida-00222",
        "product_name": "TI TIDA-00222",
        "manufacturer": "Texas Instruments",
        "product_family": "TI Reference Design",
        "description": "TIDA-00222 reference design",
    },
    "ti_tidep_0050": {
        "product_id": "ti-tidep-0050",
        "product_name": "TI TIDEP0050",
        "manufacturer": "Texas Instruments",
        "product_family": "TI Reference Design",
        "description": "TIDEP0050 reference design",
    },
}

# BOM identity/metadata columns must not be stored as electrical specifications.
BOM_IDENTITY_ATTRIBUTES = {
    "item", "embest p/n", "part type", "qty", "quantity", "location", "parts",
    "manufacturer", "manufacture p/n", "description", "refdes", "reference",
    "mpn", "part number", "designator",
}


def infer_component_class(description: str, mpn: str) -> str:
    text = f"{description} {mpn}".lower()
    mapping = [
        ("mcu", "MCU"), ("mpu", "MPU"), ("sitara", "MPU"), ("am33", "MPU"),
        ("mosfet", "MOSFET"), ("bjt", "BJT"), ("diode", "DIODE"),
        ("regulator", "REGULATOR"), ("ldo", "REGULATOR"), ("tps", "REGULATOR"),
        ("op amp", "OP_AMP"), ("opamp", "OP_AMP"), ("adc", "ADC"),
        ("capacitor", "CAPACITOR"), ("cap ", "CAPACITOR"),
        ("resistor", "RESISTOR"), ("res ", "RESISTOR"),
        ("connector", "CONNECTOR"), ("header", "CONNECTOR"),
        ("crystal", "CRYSTAL"), ("oscillator", "CLOCK"),
        ("memory", "MEMORY"), ("ddr", "MEMORY"), ("emmc", "MEMORY"),
        ("ethernet", "TRANSCEIVER"), ("phy", "TRANSCEIVER"),
        ("sensor", "SENSOR"),
    ]
    for needle, klass in mapping:
        if needle in text:
            return klass
    return "ETC"


def normalize_rows(
    product_key: str,
    rows: List[Dict[str, Any]],
    source_id: str,
    revision: str = "A",
    product_metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, int]:
    # Known products retain their existing metadata.  The optional metadata
    # makes the importer usable for future reference designs without adding
    # a hard-coded product entry to this module.
    meta = product_metadata or PRODUCTS[product_key]
    registry = SourceRegistry()
    provenance = ProvenanceStore()
    upsert_by_key("products.csv", "product_id", {**meta, "source_id": source_id})
    revision_id = f"{meta['product_id']}-rev-{revision}"
    upsert_by_key(
        "product_revisions.csv",
        "revision_id",
        {
            "revision_id": revision_id,
            "product_id": meta["product_id"],
            "revision": revision,
            "version": revision,
            "release_date": "",
            "lifecycle_status": "UNKNOWN",
            "source_id": source_id,
        },
    )
    unresolved = []
    bom_rows = []
    type_rows = []
    spec_rows = []
    tolerance_rows = []
    seen_types = set()
    counts = {"bom_lines": 0, "models": 0, "unresolved": 0}
    for row in rows:
        resolution = resolve_mpn(
            str(row.get("mpn") or ""),
            str(row.get("manufacturer") or ""),
            str(row.get("package") or ""),
        )
        if resolution.resolution_status != "RESOLVED":
            unresolved.append(
                {
                    "original_mpn": resolution.original_mpn,
                    "original_manufacturer": resolution.original_manufacturer,
                    "product_id": meta["product_id"],
                    "source_file": row.get("source_file", ""),
                    "reason": resolution.reason,
                    "resolution_status": "UNRESOLVED",
                }
            )
            counts["unresolved"] += 1
            model_id = ""
        else:
            existing = find_model_by_mpn(resolution.normalized_mpn, resolution.normalized_manufacturer)
            if existing:
                model_id = existing["component_model_id"]
            else:
                model_id = stable_id("mdl", resolution.normalized_mpn, resolution.normalized_manufacturer)
                upsert_by_key(
                    "component_models.csv",
                    "component_model_id",
                    {
                        "component_model_id": model_id,
                        "manufacturer": resolution.normalized_manufacturer,
                        "mpn": resolution.original_mpn,
                        "normalized_mpn": resolution.normalized_mpn,
                        "description": str(row.get("description") or ""),
                        "package": resolution.normalized_package,
                        "mounting_type": "",
                        "component_category": infer_component_class(str(row.get("description") or ""), resolution.original_mpn),
                        "datasheet_url": "",
                        "lifecycle_status": "UNKNOWN",
                    },
                )
            attributes = row.get("attributes") or {}
            if isinstance(attributes, dict):
                for parameter_name, value in attributes.items():
                    text = str(value or "").strip()
                    name = str(parameter_name or "").strip()
                    if not name or not text:
                        continue
                    if name.lower() in BOM_IDENTITY_ATTRIBUTES:
                        continue
                    spec_rows.append(
                        {
                            "spec_id": stable_id("sp", model_id, name, text),
                            "component_model_id": model_id,
                            "parameter_name": name,
                            "nominal_value": text,
                            "min_value": "",
                            "max_value": "",
                            "unit": "",
                            "condition": "",
                            "source_document": str(row.get("source_file") or ""),
                            "source_page": str(row.get("source_page") or ""),
                            "confidence": "HIGH",
                            "provenance": "REAL_PUBLIC_SOURCE",
                        }
                    )
                    if "toleran" in name.lower():
                        tolerance_rows.append(
                            {
                                "tolerance_id": stable_id("tol", model_id, name, text),
                                "component_model_id": model_id,
                                "normalized_mpn": resolution.normalized_mpn,
                                "parameter": name,
                                "nominal": "",
                                "min_value": "",
                                "max_value": "",
                                "tolerance_value": text,
                                "tolerance_type": "AS_SUPPLIED",
                                "unit": "",
                                "condition": "",
                                "source": str(row.get("source_file") or ""),
                                "source_type": "BOM_ATTRIBUTE",
                                "confidence": "HIGH",
                                "provenance": "REAL_PUBLIC_SOURCE",
                            }
                        )
            counts["models"] += 1
            provenance.record(
                source_id=source_id,
                entity_type="component_model",
                entity_id=model_id,
                field_name="normalized_mpn",
                source_type="BOM",
                data_provenance="NORMALIZED",
                source_document=str(row.get("source_file") or ""),
                source_page=str(row.get("source_page") or ""),
                confidence="HIGH",
            )
        klass = infer_component_class(str(row.get("description") or ""), resolution.original_mpn)
        type_id = f"type_{klass.lower()}"
        if type_id not in seen_types:
            seen_types.add(type_id)
            type_rows.append(
                {
                    "component_type_id": type_id,
                    "component_class": klass,
                    "subcategory": "",
                    "description": klass,
                }
            )
        bom_rows.append(
            {
                "bom_line_id": stable_id(
                    "bl",
                    meta["product_id"],
                    revision_id,
                    resolution.original_mpn,
                    str(row.get("reference_designator") or ""),
                ),
                "product_id": meta["product_id"],
                "revision_id": revision_id,
                "subsystem_id": str(row.get("subsystem_id") or ""),
                "reference_designator": str(row.get("reference_designator") or ""),
                "component_type_id": type_id,
                "component_model_id": model_id,
                "quantity": str(row.get("quantity") or "1"),
                "unit": str(row.get("unit") or "ea"),
                "position": str(row.get("position") or ""),
                "parent_assembly": str(row.get("parent_assembly") or ""),
                "original_manufacturer": resolution.original_manufacturer,
                "original_mpn": resolution.original_mpn,
                "original_description": str(row.get("description") or ""),
                "source_id": source_id,
            }
        )
        # Preserve the source assertions separately from the normalized key.
        # This keeps original ordering suffixes and manufacturer spelling
        # auditable instead of presenting normalization as manufacturer data.
        line_id = bom_rows[-1]["bom_line_id"]
        for field_name, value in (
            ("original_mpn", resolution.original_mpn),
            ("original_manufacturer", resolution.original_manufacturer),
            ("original_description", str(row.get("description") or "")),
            ("package", str(row.get("package") or "")),
        ):
            if value:
                provenance.record(
                    source_id=source_id,
                    entity_type="bom_line",
                    entity_id=line_id,
                    field_name=field_name,
                    source_type="BOM",
                    data_provenance="REAL_PUBLIC_SOURCE",
                    source_document=str(row.get("source_file") or ""),
                    source_page=str(row.get("source_page") or ""),
                    confidence="HIGH",
                )
        counts["bom_lines"] += 1
    if type_rows:
        upsert_rows("component_types.csv", ["component_type_id"], type_rows)
    if bom_rows:
        upsert_rows(
            "bom_lines.csv",
            ["product_id", "revision_id", "original_mpn", "reference_designator"],
            bom_rows,
        )
    if spec_rows:
        upsert_rows("component_specs.csv", ["spec_id"], spec_rows)
    if tolerance_rows:
        upsert_rows("tolerance_records.csv", ["tolerance_id"], tolerance_rows)
    if unresolved:
        upsert_rows("unresolved_mpns.csv", ["original_mpn", "product_id", "source_file", "reason"], unresolved)
    _ = registry
    return counts
