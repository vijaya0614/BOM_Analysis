# SENTINEL Industry Data Ingestion & Normalization

## Overview

SENTINEL ingests real-world industry electronic BOMs and reference design packages from `incoming_industry_data/`. The automated importer preserves raw source files, extracts supported archive contents safely, normalizes records, and registers field-level provenance.

## Incoming Industry Files

Supported formats:
- Tabular BOMs: `.csv`, `.xls`, `.xlsx`, `.xlsm`
- Archive Packages: `.zip`
- Documentation & Design Guides: `.pdf`, `.txt`, `.json`

## Direct Importer Pipeline

Command:
```bash
python -m src.industry_data.importer --dry-run
python -m src.industry_data.importer
```

Flow:
1. **File Discovery**: Scans `incoming_industry_data/` for incoming files.
2. **SHA-256 Check**: Computes file hash and skips duplicate processing.
3. **Safe Extraction**: Extracts ZIP archives while preventing path traversal.
4. **Document Classification**: Maps files to products (`beaglebone-black`, `beaglebone-black-wireless`, `beaglebone-ai`, `ti-tida-00222`, `ti-tidep-0050`).
5. **Raw Preservation**: Copies source files into immutable `data/industry/raw/<product>/` subdirectories.
6. **Normalization**: Parses BOM rows, normalizes MPNs, manufacturers, and packages into `data/industry/normalized/`.
7. **Provenance Registration**: Logs source IDs, document paths, line numbers, and confidence ratings in `source_registry.csv` and `field_provenance.csv`.

Use `GET /api/industry/status` to read the current repository counts for incoming files, registered documents, normalized BOM lines, unresolved MPNs, import manifest, and credential-safe provider status. Counts are intentionally read at runtime rather than hard-coded in this document.

## Browser Uploads

The **BOM Materials** page can upload one industry source directly into the controlled importer inbox. Supported files are ZIP, CSV, XLS, XLSX, PDF, TXT, and JSON (maximum decoded file size: 50 MiB). The API accepts a basename and file bytes only; it does not accept browser-supplied paths. It hashes and preserves the original before using the same safe extraction, duplicate detection, parsing, normalization, and provenance process as command-line imports.

`GET /api/industry/components` returns the normalized MPN catalog for Vendor Comparison. BOM columns outside component identity—such as tolerance or voltage rating—are retained as provenance-backed specifications when supplied. A missing tolerance or limit remains unknown; SENTINEL does not infer it.

## Built-in Industry BOM workflow

`GET /api/industry/boms` lists the five imported datasets with their actual normalized BOM-line and unique-MPN counts. The **Industry BOMs** section in the BOM Materials page loads a selected dataset through `POST /api/industry/bom/load`, then runs the existing risk engine over an ephemeral export of the normalized BOM occurrences. It does not duplicate or overwrite the preserved source data.

The Vendor Comparison page can then choose any normalized MPN from the loaded BOM and request a bounded, single-MPN live refresh. Loading a BOM alone makes no external provider calls.

## Data Model & Normalized Schemas

Location: `data/industry/normalized/`

- `products.csv`: Product catalog & manufacturer details.
- `bom_lines.csv`: BOM line occurrences mapped by designator, quantity, and model ID.
- `component_models.csv`: Deduplicated component identity records (`normalized_mpn`, `manufacturer`, `package`).
- `component_specs.csv`: Technical specifications.
- `lifecycle_records.csv`: Historical and current lifecycle evidence.
- `vendors.csv`: Vendor and distributor registry.
- `vendor_supply_records.csv`: Stock, lead time, pricing, and regional offers.
- `source_registry.csv`: Registered documents and raw file paths.
- `field_provenance.csv`: Field-level traceability records.
- `data_quality_report.csv`: Automated data quality audit findings.
