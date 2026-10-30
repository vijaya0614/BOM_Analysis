# Data ownership, freshness, and report integrity

## Source of truth

| Data | Authoritative store | Update rule |
|---|---|---|
| Received BOMs, schematics, datasheets, and supplier files | `incoming_industry_data/` is staging only; `data/industry/raw/` holds preserved originals; `data/industry/manifests/` records each import | Never edit normalized rows by hand to correct an original. Add a corrected source package and import it; retain the prior package and manifest for audit. |
| Industry BOM identity, revisions, normalized engineering attributes, lifecycle evidence, supplier records, unresolved MPNs, conflicts, and provenance | `data/industry/normalized/*.csv` | This CSV catalog is the current application system of record because importer, enrichment, reports, and API adapters read and write it. Upserts update current keyed records; `vendor_stock_snapshots.csv`, source registry, and manifests retain observations/history. |
| Demonstration fixtures and generic engineering examples | `data/*.csv` and code-defined demo fixtures | Demo-only. They must not overwrite or silently fill industry records. |
| User/project workflow state, approvals, and saved decision runs | SQL database configured by `DATABASE_URL` | The database is reserved for transactional application state. The current SQLAlchemy tables are prototype BOM/substitute tables and are not authoritative for the industry catalog or evidence; they lack source lineage and freshness fields. Do not dual-write catalog facts there until a migration adds source IDs, observed/expiry times, conflict state, and audit history. |
| Generated reports | `outputs/` | Derived snapshots. Each report must identify its input source IDs, observation/freshness state, unresolved conflicts, missing evidence, and selected BOM revision. Regenerate after changing inputs; old reports are not live views. |

## Freshness and resolution rules

- **BOM revision:** Select one revision for an analysis, never concatenate rows across revisions. The current importer records an observed revision and source observation time; it does not establish that the package is the latest manufacturer release. A revision without a source release date is labeled unverified. Reports show the selected revision and source observation time.
- **Distributor offers:** A live/cached offer is eligible for numeric stock, price, and lead-time overlays only until `expires_at` (24 hours by default). Missing or invalid expiry is `UNKNOWN`; expired rows are `STALE`. Unknown, stale, synthetic, or conflicting rows are excluded from numeric overlays and remain visible with counts/status. Historical snapshots stay available for audit and are never treated as current offers.
- **Lifecycle:** A source-backed lifecycle record is eligible for the current lifecycle overlay for 180 days after source observation. Missing observation time is `UNKNOWN`; conflicting statuses are `CONFLICT`; expired records are `STALE`. All three are withheld from the decision value while the record and status remain visible.
- **Engineering specs and provenance:** A value without a resolvable source remains incomplete. Import time is not a substitute for manufacturer publication/revision date. Conflicts are not resolved by “last row wins”; they must be reviewed and explicitly marked resolved.
- **Partial enrichment:** A report may use current fields and still report `INCOMPLETE` when sibling records are stale/unknown or unresolved. It must report how many records were used and excluded. A missing value is not backfilled from demo data.
- **Refresh behavior:** BOM/document updates are explicit imports. On the first accepted BOM for a product in an import run, the importer replaces that product’s active normalized BOM lines and unresolved-MPN rows; it then accumulates any other accepted BOM files in that same package. Duplicate files and detected stub BOMs do not replace the active normalized set. Preserved source files and manifests remain as history. Provider updates are explicit enrichment runs (or an explicitly scheduled job), and `force_refresh` bypasses provider cache. Refresh writes a new observation/snapshot and updates the current keyed record; it does not delete observation history. Reports are generated from a single read snapshot and carry that snapshot’s metadata.

## Status vocabulary

`CURRENT` means the configured source-backed freshness window has not expired. `STALE` means it has expired. `UNKNOWN` means timing or provenance is missing. `INCOMPLETE` means some eligible records exist but others were withheld. `CONFLICT` means incompatible unresolved source claims exist. `REVISION_UNVERIFIED` means a report selected one imported revision but cannot prove it is the manufacturer’s current release. `INSUFFICIENT_DATA` means no eligible source-backed record exists.

