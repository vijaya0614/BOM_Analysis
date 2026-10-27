"""Safe, provenance-first import of downloaded industry design material.

The importer deliberately performs no network activity unless ``--enrich`` is
requested.  It preserves originals, treats archive contents as data (never as
executables), and passes only parsed BOM rows to the established normalizer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from src.bom_parser import PART_NUM_HEADERS, QTY_HEADERS, REF_HEADERS
from src.industry_data.bom_normalizer import PRODUCTS, normalize_rows
from src.industry_data.csv_store import delete_where, ensure_headers, read_csv, upsert_by_key, upsert_rows
from src.industry_data.provenance import ProvenanceStore
from src.industry_data.source_registry import SourceRegistry
from src.providers.settings import ROOT


SUPPORTED_SUFFIXES = {".zip", ".csv", ".xls", ".xlsx", ".pdf", ".txt", ".json"}
TABULAR_SUFFIXES = {".csv", ".xls", ".xlsx"}
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024

MANUFACTURER_HEADERS = ["manufacturer", "manufacture", "manu.", "mfr", "mfg", "vendor", "maker"]
DESC_HEADERS = ["description", "descriptivetext", "desc", "comment", "value", "part description"]
PACKAGE_HEADERS = ["package", "footprint", "pkg", "case"]
PART_NUMBER_HEADERS = PART_NUM_HEADERS + [
    "manufacturer part number", "mfr pn", "mfr part number", "mfr part#", "mfg part number",
    "mfg part#", "manufacture p/n", "manufacturer's part number", "mfrnum", "part no", "part #", "p/n",
    "manufacturer and part number",
]
COMBINED_MPN_HEADERS = {"manufacturer and part number"}

# These aliases improve recognition for known material without making them the
# only accepted products.  Unknown designs get a stable identifier from their
# filename/path and need no source change to ingest.
KNOWN_PRODUCT_HINTS: Sequence[Tuple[Sequence[str], str]] = (
    (("beaglebone black wireless", "beaglebone_black_wireless", "black_wireless"), "beaglebone_black_wireless"),
    (("beaglebone black", "beaglebone_black", "bbb-industrial"), "beaglebone_black"),
    (("beaglebone ai", "beaglebone_ai", "beagleboard-ai"), "beaglebone_ai"),
    (("tida-00222", "tida_00222", "tida00222", "tidrb"), "ti_tida_00222"),
    (("tidep0050", "tidep-0050", "tidep_0050", "am437x_industrial_evm", "tidrc"), "ti_tidep_0050"),
)


@dataclass(frozen=True)
class ImportPaths:
    incoming: Path
    raw: Path
    manifests: Path

    @classmethod
    def defaults(cls) -> "ImportPaths":
        return cls(
            incoming=ROOT / "incoming_industry_data",
            raw=ROOT / "data" / "industry" / "raw",
            manifests=ROOT / "data" / "industry" / "manifests",
        )


@dataclass
class Candidate:
    path: Path
    relative_path: str
    file_hash: str
    product_key: str
    product_meta: Dict[str, str]
    document_type: str
    archive_member: str = ""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unclassified-design"


def product_metadata(product_key: str, title_hint: str = "") -> Dict[str, str]:
    if product_key in PRODUCTS:
        return dict(PRODUCTS[product_key])
    title = re.sub(r"[_-]+", " ", title_hint or product_key).strip().title()
    return {
        "product_id": slugify(product_key),
        "product_name": title or "Unclassified industry design",
        "manufacturer": "",
        "product_family": "Imported industry design",
        "description": "Automatically identified from imported source material",
    }


def detect_product(text: str, fallback_name: str) -> Tuple[str, Dict[str, str], float]:
    normalized = text.lower().replace("\\", "/")
    for hints, key in KNOWN_PRODUCT_HINTS:
        if any(hint in normalized for hint in hints):
            return key, product_metadata(key), 0.95
    key = slugify(Path(fallback_name).stem)
    return key, product_metadata(key, Path(fallback_name).stem), 0.45


def document_type_for(name: str, is_bom: bool = False) -> str:
    suffix = Path(name).suffix.lower()
    lower = name.lower()
    if suffix in TABULAR_SUFFIXES:
        return "bom" if is_bom or "bom" in lower else "tabular"
    if suffix == ".pdf":
        return "bom_pdf" if "bom" in lower else "pdf"
    if suffix == ".zip":
        return "archive"
    if suffix == ".txt":
        return "text"
    if suffix == ".json":
        return "json"
    return "unsupported"


def _header_index(headers: Sequence[str], names: Sequence[str]) -> Optional[int]:
    lookup = [str(header or "").strip().lower() for header in headers]
    for name in names:
        if name in lookup:
            return lookup.index(name)
    return None


def _cell(row: Sequence[Any], index: Optional[int]) -> str:
    return "" if index is None or index >= len(row) else str(row[index] or "").strip()


def split_combined_manufacturer_mpn(value: str) -> tuple[str, str]:
    """Split a source 'MANUFACTURER AND PART NUMBER' cell without inventing identity.

    The last whitespace-delimited token is treated as the MPN when it contains a
    digit; the remainder is the manufacturer. If that pattern does not hold, the
    entire cell is the original MPN and manufacturer stays blank.
    """
    text = str(value or "").strip().strip('"')
    if not text:
        return "", ""
    if "," in text and not any(token.isdigit() for token in text.rsplit(" ", 1)[-1]):
        left, right = text.rsplit(",", 1)
        right = right.strip()
        left = left.strip()
        if right:
            return left, right
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and any(char.isdigit() for char in parts[1]):
        return parts[0].strip(), parts[1].strip()
    return "", text


def _rows_from_table(headers: Sequence[str], body: Iterable[Sequence[Any]], source_file: str, source_page_prefix: str = "") -> List[Dict[str, str]]:
    pn_index = _header_index(headers, PART_NUMBER_HEADERS)
    if pn_index is None:
        return []
    header_names = [str(header or "").strip().lower() for header in headers]
    combined = header_names[pn_index] in COMBINED_MPN_HEADERS if pn_index < len(header_names) else False
    ref_index = _header_index(headers, REF_HEADERS)
    qty_index = _header_index(headers, QTY_HEADERS)
    mfr_index = _header_index(headers, MANUFACTURER_HEADERS)
    desc_index = _header_index(headers, DESC_HEADERS)
    package_index = _header_index(headers, PACKAGE_HEADERS)
    identity_columns = {index for index in (pn_index, ref_index, qty_index, mfr_index, desc_index, package_index) if index is not None}
    parsed: List[Dict[str, str]] = []
    for number, row in enumerate(body, start=2):
        if not row or not any(str(value or "").strip() for value in row):
            continue
        attributes = {
            str(header).strip(): _cell(row, index)
            for index, header in enumerate(headers)
            if index not in identity_columns and str(header or "").strip() and _cell(row, index)
        }
        raw_pn = _cell(row, pn_index)
        manufacturer = _cell(row, mfr_index)
        if combined and raw_pn:
            split_mfr, split_mpn = split_combined_manufacturer_mpn(raw_pn)
            manufacturer = manufacturer or split_mfr
            raw_pn = split_mpn or raw_pn
        parsed.append(
            {
                "mpn": raw_pn,
                "reference_designator": _cell(row, ref_index),
                "quantity": _cell(row, qty_index) or "1",
                "manufacturer": manufacturer,
                "description": _cell(row, desc_index),
                "package": _cell(row, package_index),
                "source_file": source_file,
                "source_page": f"{source_page_prefix}{number}",
                # Preserve non-identity BOM columns (for example tolerance,
                # voltage rating, package notes, or operating temperature) so
                # the normalizer can retain real source evidence instead of
                # discarding it or inventing a value later.
                "attributes": attributes,
            }
        )
    return parsed


def parse_tabular(path: Path, source_file: Optional[str] = None) -> List[Dict[str, str]]:
    """Parse BOM-like CSV/XLS/XLSX files; macros and scripts are never run."""
    source = source_file or path.as_posix()
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            table = list(csv.reader(handle))
        return _parse_matrix(table, source, "") if table else []
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        return _parse_workbook_sheets(workbook, source)
    if suffix == ".xls":
        try:
            import xlrd
        except ImportError as exc:  # pragma: no cover - depends on local installation
            raise ValueError("XLS_READER_UNAVAILABLE: install xlrd>=2.0.1") from exc
        book = xlrd.open_workbook(path, on_demand=True)
        rows: List[Dict[str, str]] = []
        for sheet in book.sheets():
            matrix = [sheet.row_values(index) for index in range(sheet.nrows)]
            rows.extend(_parse_matrix(matrix, source, f"{sheet.name}:"))
        return rows
    return []


def parse_tabular_bytes(content: bytes, suffix: str, source_file: str) -> List[Dict[str, str]]:
    """Read a table from an archive member without extracting it in dry-run mode."""
    suffix = suffix.lower()
    if suffix == ".csv":
        matrix = list(csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace"))))
        return _parse_matrix(matrix, source_file, "") if matrix else []
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        return _parse_workbook_sheets(
            load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False), source_file
        )
    if suffix == ".xls":
        try:
            import xlrd
        except ImportError as exc:  # pragma: no cover - depends on local installation
            raise ValueError("XLS_READER_UNAVAILABLE: install xlrd>=2.0.1") from exc
        book = xlrd.open_workbook(file_contents=content, on_demand=True)
        rows: List[Dict[str, str]] = []
        for sheet in book.sheets():
            rows.extend(_parse_matrix([sheet.row_values(index) for index in range(sheet.nrows)], source_file, f"{sheet.name}:"))
        return rows
    return []


def _parse_workbook_sheets(workbook: Any, source: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for sheet in workbook.worksheets:
        matrix = [list(values) for values in sheet.iter_rows(values_only=True)]
        rows.extend(_parse_matrix(matrix, source, f"{sheet.title}:"))
    return rows


def _parse_matrix(matrix: Sequence[Sequence[Any]], source: str, page_prefix: str) -> List[Dict[str, str]]:
    # Reference-design workbooks often include title/revision rows before the
    # actual header.  Search a bounded prefix rather than assuming row one.
    for index, headers in enumerate(matrix[:30]):
        if _header_index(headers, PART_NUMBER_HEADERS) is not None:
            return _rows_from_table(headers, matrix[index + 1 :], source, f"{page_prefix}{index + 1}+")
    return []


def _is_safe_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename.replace("\\", "/")
    part = PurePosixPath(name)
    return not (part.is_absolute() or ".." in part.parts or ":" in part.parts[0])


def inspect_archive(path: Path) -> Tuple[List[zipfile.ZipInfo], List[str]]:
    warnings: List[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                return [], [f"ARCHIVE_TOO_MANY_MEMBERS:{path.name}"]
            total = sum(info.file_size for info in infos)
            if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                return [], [f"ARCHIVE_TOO_LARGE:{path.name}"]
            safe = []
            for info in infos:
                if not _is_safe_member(info):
                    warnings.append(f"ZIP_PATH_TRAVERSAL_SKIPPED:{path.name}:{info.filename}")
                elif info.flag_bits & 0x1:
                    warnings.append(f"ZIP_ENCRYPTED_MEMBER_SKIPPED:{path.name}:{info.filename}")
                else:
                    safe.append(info)
            return safe, warnings
    except zipfile.BadZipFile:
        return [], [f"MALFORMED_ZIP:{path.name}"]


def _existing_hashes() -> set[str]:
    return {row.get("file_hash", "") for row in read_csv("documents.csv") if row.get("file_hash")}


def _copy_preserved(source: Path, destination_dir: Path, file_hash: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    name = source.name
    candidate = destination_dir / name
    if candidate.exists() and sha256_file(candidate) == file_hash:
        return candidate
    if candidate.exists():
        candidate = destination_dir / f"{source.stem}-{file_hash[:12]}{source.suffix.lower()}"
    shutil.copy2(source, candidate)
    return candidate


def _extract_member(archive: Path, info: zipfile.ZipInfo, destination_root: Path) -> Path:
    destination = destination_root / PurePosixPath(info.filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source, source.open(info) as input_handle, destination.open("wb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle)
    return destination


def _register_document(
    candidate: Candidate,
    *,
    source_id: str,
    source_path: str,
    extraction_status: str,
    confidence: float,
) -> None:
    upsert_rows(
        "documents.csv",
        ["file_hash"],
        [
            {
                "document_id": f"doc_{candidate.file_hash[:12]}",
                "component_model_id": "",
                "product_id": candidate.product_meta["product_id"],
                "document_type": candidate.document_type,
                "title": Path(candidate.archive_member or candidate.path.name).stem,
                "url": "",
                "revision": "",
                "publication_date": "",
                "source_id": source_id,
                "filename": candidate.archive_member or candidate.path.name,
                "file_hash": candidate.file_hash,
                "source_path": source_path,
                "imported_at": utc_now(),
                "extraction_status": extraction_status,
                "confidence": f"{confidence:.2f}",
                "source_page": "",
            }
        ],
    )


def _register_product(meta: Dict[str, str], source_id: str) -> None:
    upsert_by_key("products.csv", "product_id", {**meta, "source_id": source_id})


def discover(paths: ImportPaths) -> List[Path]:
    if not paths.incoming.is_dir():
        return []
    return sorted(
        (path for path in paths.incoming.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(paths.incoming).as_posix().casefold(),
    )


def _archive_product_hint(path: Path, infos: Sequence[zipfile.ZipInfo]) -> str:
    names = " ".join(info.filename for info in infos[:500])
    return f"{path.name} {names}"


def _candidate_for_file(path: Path, relative: str, content_hash: str, hint: str = "") -> Tuple[Candidate, float]:
    key, meta, confidence = detect_product(f"{relative} {hint}", path.name)
    return Candidate(path, relative, content_hash, key, meta, document_type_for(path.name)), confidence


def _summarize_rows(rows: Sequence[Dict[str, str]]) -> Dict[str, int]:
    mpns = [row.get("mpn", "").strip() for row in rows]
    resolved = [mpn for mpn in mpns if mpn]
    return {"rows": len(rows), "unique_mpns": len(set(resolved)), "unresolved": sum(1 for mpn in mpns if not mpn)}


def run_import(
    paths: Optional[ImportPaths] = None,
    *,
    dry_run: bool = False,
    enrich: bool = False,
) -> Dict[str, Any]:
    """Import every supported file below ``incoming_industry_data``.

    A dry run reads metadata and tables only; it does not create directories,
    write registries/manifests, preserve files, or call enrichment providers.
    """
    paths = paths or ImportPaths.defaults()
    report: Dict[str, Any] = {
        "import_id": f"imp_{uuid.uuid4().hex[:12]}",
        "timestamp": utc_now(),
        "dry_run": dry_run,
        "input_files": [],
        "duplicates": [],
        "products_detected": [],
        "files_classified": [],
        "boms_detected": [],
        "bom_rows": 0,
        "warnings": [],
        "errors": [],
        "enrichment": None,
    }
    files = discover(paths)
    if not files:
        report["warnings"].append(f"NO_INPUT_FILES:{paths.incoming}")
        return report

    if not dry_run:
        ensure_headers()
    existing_hashes = _existing_hashes() if not dry_run else set()
    seen_hashes: set[str] = set()
    imported_product_ids: set[str] = set()
    registry = SourceRegistry()
    provenance = ProvenanceStore()

    def process_document(candidate: Candidate, raw_path: Optional[Path], confidence: float, extraction_status: str) -> None:
        report["files_classified"].append(
            {"file": candidate.relative_path, "product_id": candidate.product_meta["product_id"], "document_type": candidate.document_type}
        )
        if candidate.product_meta["product_id"] not in report["products_detected"]:
            report["products_detected"].append(candidate.product_meta["product_id"])
        if dry_run:
            rows: List[Dict[str, str]] = []
            if candidate.document_type == "bom":
                try:
                    rows = parse_tabular(candidate.path, candidate.relative_path)
                except Exception as exc:
                    report["errors"].append(f"BOM_PARSE_FAILED:{candidate.relative_path}:{type(exc).__name__}")
                summary = _summarize_rows(rows)
                report["boms_detected"].append({"file": candidate.relative_path, **summary})
                report["bom_rows"] += summary["rows"]
            return
        assert raw_path is not None
        source_path = str(raw_path.relative_to(ROOT)).replace("\\", "/")
        source_id = registry.register(
            source_type="REAL_PUBLIC_SOURCE",
            title=candidate.archive_member or candidate.path.name,
            local_path=source_path,
            notes=f"SHA-256={candidate.file_hash}; extraction_status={extraction_status}",
        )
        _register_product(candidate.product_meta, source_id)
        _register_document(candidate, source_id=source_id, source_path=source_path, extraction_status=extraction_status, confidence=confidence)
        provenance.record(
            source_id=source_id,
            entity_type="document",
            entity_id=candidate.file_hash,
            field_name="file_hash",
            source_type="IMPORTER",
            data_provenance="REAL_PUBLIC_SOURCE",
            source_document=source_path,
            confidence="HIGH",
        )
        imported_product_ids.add(candidate.product_meta["product_id"])
        if candidate.document_type != "bom":
            return
        try:
            rows = parse_tabular(raw_path, source_path)
        except Exception as exc:
            report["errors"].append(f"BOM_PARSE_FAILED:{candidate.relative_path}:{type(exc).__name__}")
            return
        summary = _summarize_rows(rows)
        report["boms_detected"].append({"file": candidate.relative_path, **summary})
        report["bom_rows"] += summary["rows"]
        product_id = candidate.product_meta["product_id"]
        existing_count = sum(1 for row in read_csv("bom_lines.csv") if row.get("product_id") == product_id)
        stub_name = Path(candidate.archive_member or candidate.path.name).name.lower() == "bom.csv"
        if stub_name and summary["rows"] <= 12 and existing_count > summary["rows"]:
            report["warnings"].append(f"STUB_BOM_SKIPPED:{candidate.relative_path}")
            return
        if summary["rows"] >= 20 and 0 < existing_count <= 12:
            delete_where("bom_lines.csv", lambda row: row.get("product_id") == product_id)
        normalize_rows(candidate.product_key, rows, source_id, product_metadata=candidate.product_meta)

    for path in files:
        relative = str(path.relative_to(paths.incoming)).replace("\\", "/")
        suffix = path.suffix.lower()
        report["input_files"].append(relative)
        if suffix not in SUPPORTED_SUFFIXES:
            report["warnings"].append(f"UNSUPPORTED_FILE_SKIPPED:{relative}")
            continue
        file_hash = sha256_file(path)
        if file_hash in seen_hashes or file_hash in existing_hashes:
            report["duplicates"].append(relative)
            continue
        seen_hashes.add(file_hash)
        if suffix != ".zip":
            candidate, confidence = _candidate_for_file(path, relative, file_hash)
            if candidate.document_type == "tabular":
                try:
                    candidate.document_type = "bom" if parse_tabular(path, relative) else "tabular"
                except Exception as exc:
                    report["warnings"].append(f"TABULAR_CLASSIFICATION_FAILED:{relative}:{type(exc).__name__}")
            raw_path = None if dry_run else _copy_preserved(path, paths.raw / candidate.product_key, file_hash)
            process_document(candidate, raw_path, confidence, "ORIGINAL")
            continue

        infos, warnings = inspect_archive(path)
        report["warnings"].extend(warnings)
        archive_hint = _archive_product_hint(path, infos)
        archive_candidate, confidence = _candidate_for_file(path, relative, file_hash, archive_hint)
        raw_archive = None if dry_run else _copy_preserved(path, paths.raw / archive_candidate.product_key, file_hash)
        process_document(archive_candidate, raw_archive, confidence, "PRESERVED_ARCHIVE")
        if not infos:
            continue
        for info in infos:
            if info.is_dir():
                continue
            member_name = info.filename.replace("\\", "/")
            member_suffix = Path(member_name).suffix.lower()
            if member_suffix not in SUPPORTED_SUFFIXES - {".zip"}:
                continue
            with zipfile.ZipFile(path) as archive:
                content = archive.read(info)
            member_hash = sha256_bytes(content)
            if member_hash in existing_hashes or member_hash in seen_hashes:
                report["duplicates"].append(f"{relative}:{member_name}")
                continue
            seen_hashes.add(member_hash)
            key, meta, member_confidence = detect_product(f"{archive_hint} {member_name}", member_name)
            candidate = Candidate(path, f"{relative}:{member_name}", member_hash, key, meta, document_type_for(member_name), member_name)
            # Filename is only a hint.  Promote a table to BOM if its headers
            # actually contain a component identifier column.
            if member_suffix in TABULAR_SUFFIXES:
                try:
                    if member_suffix == ".csv":
                        matrix = list(csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace"))))
                        candidate.document_type = "bom" if matrix and _rows_from_table(matrix[0], matrix[1:], candidate.relative_path) else "tabular"
                    elif member_suffix == ".xlsx":
                        from openpyxl import load_workbook

                        candidate.document_type = "bom" if _parse_workbook_sheets(load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False), candidate.relative_path) else "tabular"
                except Exception as exc:
                    report["warnings"].append(f"TABULAR_CLASSIFICATION_FAILED:{candidate.relative_path}:{type(exc).__name__}")
            if dry_run:
                report["files_classified"].append({"file": candidate.relative_path, "product_id": meta["product_id"], "document_type": candidate.document_type})
                if meta["product_id"] not in report["products_detected"]:
                    report["products_detected"].append(meta["product_id"])
                if candidate.document_type == "bom":
                    try:
                        summary = _summarize_rows(parse_tabular_bytes(content, member_suffix, candidate.relative_path))
                        report["boms_detected"].append({"file": candidate.relative_path, **summary})
                        report["bom_rows"] += summary["rows"]
                    except Exception as exc:
                        report["errors"].append(f"BOM_PARSE_FAILED:{candidate.relative_path}:{type(exc).__name__}")
                continue
            extraction_root = paths.raw / candidate.product_key / "extracted" / file_hash[:16]
            raw_member = _extract_member(path, info, extraction_root)
            if candidate.document_type == "tabular":
                try:
                    candidate.document_type = "bom" if parse_tabular(raw_member, candidate.relative_path) else "tabular"
                except Exception as exc:
                    report["warnings"].append(f"TABULAR_CLASSIFICATION_FAILED:{candidate.relative_path}:{type(exc).__name__}")
            process_document(candidate, raw_member, member_confidence, "EXTRACTED_SAFE")

    if enrich and not dry_run and imported_product_ids:
        from src.industry_data.enrichment_service import run_enrichment

        report["enrichment"] = run_enrichment(product_ids=sorted(imported_product_ids))
    if not dry_run:
        paths.manifests.mkdir(parents=True, exist_ok=True)
        manifest = paths.manifests / f"{report['import_id']}.json"
        manifest.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        report["manifest"] = str(manifest.relative_to(ROOT)).replace("\\", "/")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Safely import downloaded industry BOM/document packages")
    parser.add_argument("--dry-run", action="store_true", help="Inspect only; do not modify project files")
    parser.add_argument("--enrich", action="store_true", help="Opt in to existing DigiKey/Nexar enrichment after import")
    parser.add_argument("--incoming", type=Path, default=ImportPaths.defaults().incoming, help="Input directory (default: incoming_industry_data)")
    args = parser.parse_args(argv)
    defaults = ImportPaths.defaults()
    report = run_import(ImportPaths(args.incoming, defaults.raw, defaults.manifests), dry_run=args.dry_run, enrich=args.enrich)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
