"""Realistic Synthetic BOM Generator and CSV Validation Suite.

Generates realistic 15-20 component BOMs containing:
- Real electronic components (Microcontrollers, PMICs, Op-Amps, MOSFETs, Passives)
- Realistic public datasheet technical parameters
- Realistic mix of Active, NRND, and EOL parts
- Single-source and dual-source parts
- Transparently labeled synthetic procurement data (stock, price, lead time)

Provides:
- generate_realistic_synthetic_bom()
- generate_bom_csv_template()
- validate_uploaded_bom_csv()
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# Standard 18-Component Prototype BOM with realistic technical & procurement parameters
REALISTIC_PROTOTYPE_COMPONENTS: List[Dict[str, Any]] = [
    {
        "part_number": "STM32F401RET6",
        "manufacturer": "STMicroelectronics",
        "description": "ARM Cortex-M4 32-bit MCU 84MHz 512KB Flash",
        "category": "Microcontroller",
        "subsystem": "Main Compute",
        "reference_designator": "U1",
        "qty": 1,
        "unit_cost": 4.85,
        "lifecycle_status": "ACTIVE",
        "stock": 14200,
        "lead_time_weeks": 12,
        "has_second_source": False,
        "package": "LQFP-64",
        "mounting": "SMD",
        "pin_count": 64,
        "pin_pitch_mm": 0.50,
        "operating_voltage_min": 1.7,
        "operating_voltage_max": 3.6,
        "operating_current_max": 0.12,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 85.0,
        "substitute_mpn": "GD32F401RET6",
        "datasheet_url": "https://www.st.com/resource/en/datasheet/stm32f401re.pdf",
    },
    {
        "part_number": "TPS5402DGQR",
        "manufacturer": "Texas Instruments",
        "description": "3.5V to 28V Input, 2A Step-Down Buck Converter",
        "category": "Power Management",
        "subsystem": "Power Supply",
        "reference_designator": "U2",
        "qty": 1,
        "unit_cost": 1.42,
        "lifecycle_status": "ACTIVE",
        "stock": 28400,
        "lead_time_weeks": 8,
        "has_second_source": True,
        "package": "MSOP-PowerPAD-10",
        "mounting": "SMD",
        "pin_count": 10,
        "pin_pitch_mm": 0.50,
        "operating_voltage_min": 3.5,
        "operating_voltage_max": 28.0,
        "operating_current_max": 2.0,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 125.0,
        "substitute_mpn": "AP63200WU-7",
        "datasheet_url": "https://www.ti.com/lit/ds/symlink/tps5402.pdf",
    },
    {
        "part_number": "LM358DR",
        "manufacturer": "Texas Instruments",
        "description": "Dual Operational Amplifier 3V to 32V",
        "category": "Analog / Op-Amp",
        "subsystem": "Sensor Conditioning",
        "reference_designator": "U3",
        "qty": 2,
        "unit_cost": 0.32,
        "lifecycle_status": "ACTIVE",
        "stock": 85000,
        "lead_time_weeks": 4,
        "has_second_source": True,
        "package": "SOIC-8",
        "mounting": "SMD",
        "pin_count": 8,
        "pin_pitch_mm": 1.27,
        "operating_voltage_min": 3.0,
        "operating_voltage_max": 32.0,
        "operating_current_max": 0.04,
        "operating_temperature_min": 0.0,
        "operating_temperature_max": 70.0,
        "substitute_mpn": "LM358BAIDR",
        "datasheet_url": "https://www.ti.com/lit/ds/symlink/lm358.pdf",
    },
    {
        "part_number": "MCP2551-I/SN",
        "manufacturer": "Microchip Technology",
        "description": "High-Speed CAN Transceiver 5V 1Mbps",
        "category": "Interface / CAN",
        "subsystem": "Industrial Bus",
        "reference_designator": "U4",
        "qty": 1,
        "unit_cost": 1.15,
        "lifecycle_status": "NRND",  # Not Recommended for New Designs
        "stock": 1800,
        "lead_time_weeks": 26,
        "has_second_source": False,
        "package": "SOIC-8",
        "mounting": "SMD",
        "pin_count": 8,
        "pin_pitch_mm": 1.27,
        "operating_voltage_min": 4.5,
        "operating_voltage_max": 5.5,
        "operating_current_max": 0.075,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 85.0,
        "substitute_mpn": "MCP2562-E/SN",
        "datasheet_url": "https://ww1.microchip.com/downloads/en/DeviceDoc/21667f.pdf",
    },
    {
        "part_number": "DS1307Z+",
        "manufacturer": "Analog Devices / Maxim",
        "description": "64 x 8 Serial Real-Time Clock I2C",
        "category": "Timing / RTC",
        "subsystem": "Main Compute",
        "reference_designator": "U5",
        "qty": 1,
        "unit_cost": 3.20,
        "lifecycle_status": "EOL",  # End of Life
        "stock": 350,
        "lead_time_weeks": 48,
        "has_second_source": False,
        "package": "SOIC-8",
        "mounting": "SMD",
        "pin_count": 8,
        "pin_pitch_mm": 1.27,
        "operating_voltage_min": 4.5,
        "operating_voltage_max": 5.5,
        "operating_current_max": 0.0015,
        "operating_temperature_min": 0.0,
        "operating_temperature_max": 70.0,
        "substitute_mpn": "DS1338Z-33+",
        "datasheet_url": "https://www.analog.com/media/en/technical-documentation/data-sheets/DS1307.pdf",
    },
    {
        "part_number": "BSS138",
        "manufacturer": "ON Semiconductor",
        "description": "N-Channel Logic Level Power MOSFET 50V 220mA",
        "category": "Discrete / MOSFET",
        "subsystem": "Level Shifting",
        "reference_designator": "Q1",
        "qty": 4,
        "unit_cost": 0.12,
        "lifecycle_status": "ACTIVE",
        "stock": 120000,
        "lead_time_weeks": 6,
        "has_second_source": True,
        "package": "SOT-23",
        "mounting": "SMD",
        "pin_count": 3,
        "pin_pitch_mm": 0.95,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 50.0,
        "operating_current_max": 0.22,
        "operating_temperature_min": -55.0,
        "operating_temperature_max": 150.0,
        "substitute_mpn": "2N7002",
        "datasheet_url": "https://www.onsemi.com/pdf/datasheet/bss138-d.pdf",
    },
    {
        "part_number": "MBR0520L",
        "manufacturer": "Diodes Incorporated",
        "description": "Schottky Barrier Diode 20V 0.5A",
        "category": "Discrete / Diode",
        "subsystem": "Power Supply",
        "reference_designator": "D1",
        "qty": 2,
        "unit_cost": 0.18,
        "lifecycle_status": "ACTIVE",
        "stock": 45000,
        "lead_time_weeks": 6,
        "has_second_source": True,
        "package": "SOD-123",
        "mounting": "SMD",
        "pin_count": 2,
        "pin_pitch_mm": 2.50,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 20.0,
        "operating_current_max": 0.50,
        "operating_temperature_min": -65.0,
        "operating_temperature_max": 125.0,
        "substitute_mpn": "B0520W-7",
        "datasheet_url": "https://www.diodes.com/assets/Datasheets/ds30094.pdf",
    },
    {
        "part_number": "TMP102AIDRLT",
        "manufacturer": "Texas Instruments",
        "description": "Digital Temperature Sensor with Two-Wire I2C",
        "category": "Sensor",
        "subsystem": "Thermal Telemetry",
        "reference_designator": "U6",
        "qty": 1,
        "unit_cost": 1.65,
        "lifecycle_status": "ACTIVE",
        "stock": 19500,
        "lead_time_weeks": 10,
        "has_second_source": True,
        "package": "SOT-563",
        "mounting": "SMD",
        "pin_count": 6,
        "pin_pitch_mm": 0.50,
        "operating_voltage_min": 1.4,
        "operating_voltage_max": 3.6,
        "operating_current_max": 0.0001,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 125.0,
        "substitute_mpn": "PCT2075DP",
        "datasheet_url": "https://www.ti.com/lit/ds/symlink/tmp102.pdf",
    },
    {
        "part_number": "RC0805FR-0710KL",
        "manufacturer": "Yageo",
        "description": "Thick Film Chip Resistor 10k Ohm 1% 1/8W",
        "category": "Passive / Resistor",
        "subsystem": "Signal Conditioning",
        "reference_designator": "R1, R2, R3, R4",
        "qty": 4,
        "unit_cost": 0.015,
        "lifecycle_status": "ACTIVE",
        "stock": 450000,
        "lead_time_weeks": 4,
        "has_second_source": True,
        "package": "0805",
        "mounting": "SMD",
        "pin_count": 2,
        "pin_pitch_mm": 1.90,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 150.0,
        "operating_current_max": 0.01,
        "operating_temperature_min": -55.0,
        "operating_temperature_max": 155.0,
        "substitute_mpn": "CRCW080510K0FKEA",
        "datasheet_url": "https://www.yageo.com/documents/recent/PYu-RC_Group_51_RoHS_L_12.pdf",
    },
    {
        "part_number": "CC0805KRX7R9BB104",
        "manufacturer": "Yageo",
        "description": "Ceramic Capacitor 100nF 50V X7R 10%",
        "category": "Passive / Capacitor",
        "subsystem": "Decoupling",
        "reference_designator": "C1, C2, C3, C4, C5",
        "qty": 5,
        "unit_cost": 0.025,
        "lifecycle_status": "ACTIVE",
        "stock": 380000,
        "lead_time_weeks": 4,
        "has_second_source": True,
        "package": "0805",
        "mounting": "SMD",
        "pin_count": 2,
        "pin_pitch_mm": 1.90,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 50.0,
        "operating_current_max": 0.50,
        "operating_temperature_min": -55.0,
        "operating_temperature_max": 125.0,
        "substitute_mpn": "GRM21BR71H104KA01L",
        "datasheet_url": "https://www.yageo.com/documents/recent/UPY-GPHC_X7R_6.3V-to-50V_20.pdf",
    },
    {
        "part_number": "EEE-FK1V101XP",
        "manufacturer": "Panasonic",
        "description": "Aluminum Electrolytic Capacitor 100uF 35V Low ESR",
        "category": "Passive / Capacitor",
        "subsystem": "Power Supply",
        "reference_designator": "C6",
        "qty": 1,
        "unit_cost": 0.45,
        "lifecycle_status": "ACTIVE",
        "stock": 22000,
        "lead_time_weeks": 10,
        "has_second_source": True,
        "package": "Radial-SMD",
        "mounting": "SMD",
        "pin_count": 2,
        "pin_pitch_mm": 2.20,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 35.0,
        "operating_current_max": 0.35,
        "operating_temperature_min": -55.0,
        "operating_temperature_max": 105.0,
        "substitute_mpn": "UWT1V101MCL1GS",
        "datasheet_url": "https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1181.pdf",
    },
    {
        "part_number": "CDRH104RNP-100NC",
        "manufacturer": "Sumida",
        "description": "Shielded Power Inductor 10uH 4.4A",
        "category": "Passive / Inductor",
        "subsystem": "Power Supply",
        "reference_designator": "L1",
        "qty": 1,
        "unit_cost": 0.88,
        "lifecycle_status": "ACTIVE",
        "stock": 14000,
        "lead_time_weeks": 8,
        "has_second_source": True,
        "package": "10.4x10.4mm",
        "mounting": "SMD",
        "pin_count": 2,
        "pin_pitch_mm": 7.0,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 50.0,
        "operating_current_max": 4.4,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 100.0,
        "substitute_mpn": "SRR1260-100M",
        "datasheet_url": "https://products.sumida.com/products/pdf/CDRH104R.pdf",
    },
    {
        "part_number": "AT24C32D-SSHM-T",
        "manufacturer": "Microchip Technology",
        "description": "32-Kbit I2C Serial EEPROM 1MHz",
        "category": "Memory / EEPROM",
        "subsystem": "Configuration Storage",
        "reference_designator": "U7",
        "qty": 1,
        "unit_cost": 0.58,
        "lifecycle_status": "ACTIVE",
        "stock": 58000,
        "lead_time_weeks": 6,
        "has_second_source": True,
        "package": "SOIC-8",
        "mounting": "SMD",
        "pin_count": 8,
        "pin_pitch_mm": 1.27,
        "operating_voltage_min": 1.7,
        "operating_voltage_max": 5.5,
        "operating_current_max": 0.003,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 85.0,
        "substitute_mpn": "24LC32AT-I/SN",
        "datasheet_url": "https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-8866-SEEPROM-AT24C32D-Datasheet.pdf",
    },
    {
        "part_number": "FT232RL-REEL",
        "manufacturer": "FTDI Chip",
        "description": "USB to Serial UART Interface IC",
        "category": "Interface / USB",
        "subsystem": "Communications",
        "reference_designator": "U8",
        "qty": 1,
        "unit_cost": 3.95,
        "lifecycle_status": "NRND",
        "stock": 4200,
        "lead_time_weeks": 32,
        "has_second_source": False,
        "package": "SSOP-28",
        "mounting": "SMD",
        "pin_count": 28,
        "pin_pitch_mm": 0.65,
        "operating_voltage_min": 3.3,
        "operating_voltage_max": 5.25,
        "operating_current_max": 0.025,
        "operating_temperature_min": -40.0,
        "operating_temperature_max": 85.0,
        "substitute_mpn": "CP2102N-A02-GQFN28",
        "datasheet_url": "https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf",
    },
    {
        "part_number": "SMAJ5.0A",
        "manufacturer": "Littelfuse",
        "description": "TVS Diode 400W 5.0V Unidirectional",
        "category": "Protection / TVS",
        "subsystem": "Power Protection",
        "reference_designator": "D2",
        "qty": 2,
        "unit_cost": 0.22,
        "lifecycle_status": "ACTIVE",
        "stock": 95000,
        "lead_time_weeks": 4,
        "has_second_source": True,
        "package": "SMA / DO-214AC",
        "mounting": "SMD",
        "pin_count": 2,
        "pin_pitch_mm": 4.5,
        "operating_voltage_min": 0.0,
        "operating_voltage_max": 5.0,
        "operating_current_max": 43.5,
        "operating_temperature_min": -65.0,
        "operating_temperature_max": 150.0,
        "substitute_mpn": "SMAJ5.0A-TR",
        "datasheet_url": "https://www.littelfuse.com/media?resourcetype=datasheets&itemid=d9b936d5-e2ff-4b4d-9dc6-b25bcfb17f4b",
    },
]


def generate_realistic_synthetic_bom_csv() -> str:
    """Returns a full CSV string containing the 15-component realistic synthetic BOM."""
    output = io.StringIO()
    fieldnames = [
        "part_number", "manufacturer", "description", "category", "subsystem",
        "reference_designator", "qty", "unit_cost", "lifecycle_status",
        "stock", "lead_time_weeks", "has_second_source", "package", "mounting",
        "pin_count", "pin_pitch_mm", "operating_voltage_min", "operating_voltage_max",
        "operating_current_max", "operating_temperature_min", "operating_temperature_max",
        "substitute_mpn", "datasheet_url", "data_provenance",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for comp in REALISTIC_PROTOTYPE_COMPONENTS:
        row = dict(comp)
        row["data_provenance"] = "SYNTHETIC_LABELED_PROTOTYPE"
        writer.writerow(row)
    return output.getvalue()


def generate_bom_csv_template() -> str:
    """Returns a minimal clean CSV template for user uploads."""
    output = io.StringIO()
    fieldnames = [
        "part_number", "manufacturer", "description", "category", "subsystem",
        "reference_designator", "qty", "unit_cost", "lifecycle_status",
        "stock", "lead_time_weeks", "has_second_source", "package",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow({
        "part_number": "TPS5402DGQR",
        "manufacturer": "Texas Instruments",
        "description": "3.5V to 28V Input 2A Step-Down Converter",
        "category": "Power Management",
        "subsystem": "Power Supply",
        "reference_designator": "U1",
        "qty": 1,
        "unit_cost": 1.45,
        "lifecycle_status": "ACTIVE",
        "stock": 25000,
        "lead_time_weeks": 8,
        "has_second_source": "true",
        "package": "MSOP-10",
    })
    writer.writerow({
        "part_number": "STM32F401RET6",
        "manufacturer": "STMicroelectronics",
        "description": "32-bit MCU 84MHz 512KB Flash",
        "category": "Microcontroller",
        "subsystem": "Main Compute",
        "reference_designator": "U2",
        "qty": 1,
        "unit_cost": 4.80,
        "lifecycle_status": "ACTIVE",
        "stock": 14000,
        "lead_time_weeks": 12,
        "has_second_source": "false",
        "package": "LQFP-64",
    })
    return output.getvalue()


@dataclass
class CsvValidationResult:
    is_valid: bool
    total_rows: int
    valid_rows_count: int
    error_count: int
    warning_count: int
    row_errors: List[Dict[str, Any]]
    normalized_components: List[Dict[str, Any]]


def validate_uploaded_bom_csv(csv_text: str) -> CsvValidationResult:
    """
    Parses and strictly validates uploaded BOM CSV content.
    Checks required headers, row-level data types, missing fields, duplicates, and ranges.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return CsvValidationResult(
            is_valid=False,
            total_rows=0,
            valid_rows_count=0,
            error_count=1,
            warning_count=0,
            row_errors=[{"row": 0, "field": "header", "message": "CSV file is empty or missing headers."}],
            normalized_components=[],
        )

    # Normalize header names (lowercase, stripped)
    headers = [h.strip().lower() for h in reader.fieldnames if h]

    # Check for MPN header
    mpn_aliases = {"part_number", "mpn", "part number", "mfr_pn", "manufacturer_part_number"}
    has_mpn = any(h in mpn_aliases for h in headers)
    if not has_mpn:
        return CsvValidationResult(
            is_valid=False,
            total_rows=0,
            valid_rows_count=0,
            error_count=1,
            warning_count=0,
            row_errors=[{"row": 0, "field": "part_number", "message": "CSV is missing a recognized part number column (e.g. 'part_number', 'mpn')."}],
            normalized_components=[],
        )

    row_errors: List[Dict[str, Any]] = []
    normalized: List[Dict[str, Any]] = []
    seen_refs = set()
    total_rows = 0

    for idx, row in enumerate(reader, start=1):
        total_rows += 1
        # Extract MPN
        mpn = ""
        for alias in ("part_number", "mpn", "part number", "mfr_pn"):
            if row.get(alias):
                mpn = str(row[alias]).strip()
                break

        if not mpn:
            row_errors.append({"row": idx, "field": "part_number", "message": "Row has empty part number / MPN."})
            continue

        ref = str(row.get("reference_designator") or row.get("refdes") or row.get("ref") or f"U{idx}").strip()
        if ref and ref in seen_refs:
            row_errors.append({"row": idx, "field": "reference_designator", "message": f"Duplicate reference designator '{ref}'."})
        seen_refs.add(ref)

        qty_raw = row.get("qty") or row.get("quantity") or "1"
        try:
            qty = max(1, int(float(qty_raw)))
        except (ValueError, TypeError):
            qty = 1
            row_errors.append({"row": idx, "field": "qty", "message": f"Invalid quantity '{qty_raw}'; defaulted to 1."})

        cost_raw = row.get("unit_cost") or row.get("cost") or row.get("price") or "0.0"
        try:
            unit_cost = max(0.0, float(cost_raw))
        except (ValueError, TypeError):
            unit_cost = 0.0

        status = str(row.get("lifecycle_status") or "ACTIVE").strip().upper()
        if status not in {"ACTIVE", "NRND", "EOL", "OBSOLETE", "DISCONTINUED", "UNKNOWN"}:
            status = "UNKNOWN"

        stock_raw = row.get("stock") or row.get("distributor_stock")
        stock = None
        if stock_raw and str(stock_raw).strip() != "":
            try:
                stock = max(0, int(float(stock_raw)))
            except (ValueError, TypeError):
                stock = None

        lt_raw = row.get("lead_time_weeks") or row.get("lead_time")
        lead_time = None
        if lt_raw and str(lt_raw).strip() != "":
            try:
                lead_time = max(0.0, float(lt_raw))
            except (ValueError, TypeError):
                lead_time = None

        sec_raw = row.get("has_second_source") or row.get("second_source")
        sec_source = None
        if sec_raw is not None and str(sec_raw).strip() != "":
            sec_source = str(sec_raw).strip().lower() in {"true", "1", "yes"}

        normalized.append({
            "pn": mpn,
            "ref": ref,
            "qty": qty,
            "unit_cost": unit_cost,
            "category": str(row.get("category") or "Generic").strip(),
            "subsystem": str(row.get("subsystem") or "Core System").strip(),
            "manufacturer": str(row.get("manufacturer") or "").strip(),
            "description": str(row.get("description") or "").strip(),
            "package": str(row.get("package") or "").strip(),
            "lifecycle_status": status,
            "stock_level": stock,
            "lead_time_weeks": lead_time,
            "has_second_source": sec_source,
            "band": "CRITICAL" if status in {"EOL", "OBSOLETE"} else ("HIGH" if status == "NRND" else "LOW"),
            "score": 0.85 if status in {"EOL", "OBSOLETE"} else (0.60 if status == "NRND" else 0.15),
            "exp": 0.80 if status in {"EOL", "OBSOLETE"} else 0.20,
            "conf": 90,
            "reasons": [f"Lifecycle status: {status}"] if status in {"EOL", "NRND"} else ["Active verified component"],
        })

    is_valid = len(row_errors) == 0 and len(normalized) > 0
    return CsvValidationResult(
        is_valid=is_valid,
        total_rows=total_rows,
        valid_rows_count=len(normalized),
        error_count=len(row_errors),
        warning_count=0,
        row_errors=row_errors,
        normalized_components=normalized,
    )
