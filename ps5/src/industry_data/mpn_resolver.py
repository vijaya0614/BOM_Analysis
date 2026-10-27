"""MPN / manufacturer / package normalization. Never guess identity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

MANUFACTURER_ALIASES = {
    "ti": "Texas Instruments",
    "texas instruments": "Texas Instruments",
    "texas instr.": "Texas Instruments",
    "texas instr": "Texas Instruments",
    "texas instruments inc": "Texas Instruments",
    "texas instruments incorporated": "Texas Instruments",
    "microchip": "Microchip Technology",
    "microchip tech": "Microchip Technology",
    "microchip technology": "Microchip Technology",
    "st": "STMicroelectronics",
    "stmicro": "STMicroelectronics",
    "stmicroelectronics": "STMicroelectronics",
    "nxp": "NXP Semiconductors",
    "nxp semiconductors": "NXP Semiconductors",
    "analog devices": "Analog Devices",
    "adi": "Analog Devices",
    "on semi": "onsemi",
    "onsemi": "onsemi",
    "on semiconductor": "onsemi",
    "murata": "Murata",
    "tdk": "TDK",
    "yageo": "Yageo",
    "vishay": "Vishay",
    "molex": "Molex",
    "amphenol": "Amphenol",
    "te": "TE Connectivity",
    "te connectivity": "TE Connectivity",
}

PACKAGE_EQUIV = {
    "qfn32": "QFN-32",
    "qfn-32": "QFN-32",
    "32-qfn": "QFN-32",
    "qfn 32": "QFN-32",
    "soic8": "SOIC-8",
    "soic-8": "SOIC-8",
    "8-soic": "SOIC-8",
    "sot23": "SOT-23",
    "sot-23": "SOT-23",
    "tssop16": "TSSOP-16",
    "tssop-16": "TSSOP-16",
}

UNRESOLVED = "UNRESOLVED"
RESOLVED = "RESOLVED"


@dataclass
class MpnResolution:
    original_mpn: str
    normalized_mpn: str
    original_manufacturer: str
    normalized_manufacturer: str
    original_package: str
    normalized_package: str
    resolution_status: str
    reason: str = ""


def normalize_mpn(mpn: str) -> str:
    return re.sub(r"\s+", "", (mpn or "").strip().upper())


def normalize_manufacturer(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    return MANUFACTURER_ALIASES.get(re.sub(r"\.$", "", raw.lower()), raw)


def normalize_package(package: str) -> str:
    raw = (package or "").strip()
    if not raw:
        return ""
    key = re.sub(r"\s+", "", raw.lower())
    key = key.replace("/", "-")
    return PACKAGE_EQUIV.get(key, raw)


def resolve_mpn(
    mpn: str,
    manufacturer: str = "",
    package: str = "",
) -> MpnResolution:
    original_mpn = (mpn or "").strip()
    original_mfr = (manufacturer or "").strip()
    original_pkg = (package or "").strip()
    if not original_mpn:
        return MpnResolution(
            original_mpn="",
            normalized_mpn="",
            original_manufacturer=original_mfr,
            normalized_manufacturer=normalize_manufacturer(original_mfr),
            original_package=original_pkg,
            normalized_package=normalize_package(original_pkg),
            resolution_status=UNRESOLVED,
            reason="missing_mpn",
        )
    if original_mpn.lower() in {"tbd", "n/a", "na", "unknown", "none"}:
        return MpnResolution(
            original_mpn=original_mpn,
            normalized_mpn="",
            original_manufacturer=original_mfr,
            normalized_manufacturer=normalize_manufacturer(original_mfr),
            original_package=original_pkg,
            normalized_package=normalize_package(original_pkg),
            resolution_status=UNRESOLVED,
            reason="placeholder_mpn",
        )
    return MpnResolution(
        original_mpn=original_mpn,
        normalized_mpn=normalize_mpn(original_mpn),
        original_manufacturer=original_mfr,
        normalized_manufacturer=normalize_manufacturer(original_mfr),
        original_package=original_pkg,
        normalized_package=normalize_package(original_pkg),
        resolution_status=RESOLVED,
    )
