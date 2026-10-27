import csv
import re
from typing import List, Optional

from src.models import PartRiskProfile

PART_NUM_HEADERS = ["part number", "mpn", "partnumber", "part", "pn", "component", "part_number"]
REF_HEADERS = [
    "designator", "reference", "refdes", "ref", "designators", "references", "raw_reference",
    "location", "parts", "reference designator", "ref des",
]
QTY_HEADERS = ["qty", "quantity", "count", "num"]

TBD_PATTERNS = {"tbd", "tba", "n/a", "na", "none", "null", "unassigned", "unknown", ""}


def expand_reference_token(token: str) -> List[str]:
    """
    Expands a single token like 'R1-R6' or 'LED1' into individual references.
    """
    token = token.strip()
    if not token:
        return []

    # Match ranges like 'R1-R6', 'LED1-LED5', and variants using en/em dashes.
    range_match = re.match(r"^([A-Za-z]+)(\d+)\s*[-\u2013\u2014]\s*([A-Za-z]+)?(\d+)$", token)
    if range_match:
        prefix1, start_num, prefix2, end_num = range_match.groups()
        prefix = prefix1
        if prefix2 and prefix2 != prefix1:
            # e.g., R1-C5 (unusual, keep as raw)
            return [token]

        start, end = int(start_num), int(end_num)
        if start <= end:
            # Determine padding format if any (e.g. R01-R06)
            pad_len = len(start_num) if start_num.startswith("0") and len(start_num) > 1 else 0
            return [f"{prefix}{str(i).zfill(pad_len)}" for i in range(start, end + 1)]

    return [token]


def expand_reference_range(ref_str: str) -> List[str]:
    """
    Parses a reference designator string (e.g. 'R1-R6, R8, C1-C3') into a flattened list.
    """
    if not ref_str:
        return []

    # Split by comma or space if not inside ranges.
    tokens = re.split(r"[\s,;]+", ref_str.strip())
    expanded = []
    for token in tokens:
        if token:
            expanded.extend(expand_reference_token(token))
    return expanded


def is_tbd_part(pn: Optional[str]) -> bool:
    if not pn:
        return True
    val = pn.strip().lower()
    return val in TBD_PATTERNS or val.startswith("tbd") or val.startswith("tba")


def parse_bom(filepath: str) -> List[PartRiskProfile]:
    """
    Parses a raw BOM CSV file into a list of structured PartRiskProfile objects.
    Expands reference designator ranges while retaining the original reference string and quantity.
    """
    profiles: List[PartRiskProfile] = []

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return []

        header_lower = [h.strip().lower() for h in headers]

        pn_idx = next((i for i, h in enumerate(header_lower) if h in PART_NUM_HEADERS), None)
        ref_idx = next((i for i, h in enumerate(header_lower) if h in REF_HEADERS), None)
        qty_idx = next((i for i, h in enumerate(header_lower) if h in QTY_HEADERS), None)

        for row in reader:
            if not row or not any(field.strip() for field in row):
                continue

            raw_pn = row[pn_idx].strip() if pn_idx is not None and pn_idx < len(row) else None
            raw_ref = row[ref_idx].strip() if ref_idx is not None and ref_idx < len(row) else ""
            raw_qty = row[qty_idx].strip() if qty_idx is not None and qty_idx < len(row) else None

            part_number: Optional[str] = raw_pn
            if is_tbd_part(part_number):
                part_number = None

            expanded_refs = expand_reference_range(raw_ref)

            qty = 1
            if raw_qty:
                try:
                    qty = int(raw_qty)
                except ValueError:
                    qty = len(expanded_refs) if expanded_refs else 1
            elif expanded_refs:
                qty = len(expanded_refs)

            profile = PartRiskProfile(
                part_number=part_number,
                references=expanded_refs,
                raw_reference_str=raw_ref,
                qty=qty,
            )

            if part_number is None:
                profile.missing_fields.append("part_number")
                profile.risk_reasons.append("Missing or unassigned Part Number (TBD placeholder)")

            profiles.append(profile)

    return profiles
