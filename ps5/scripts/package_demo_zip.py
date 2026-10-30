"""Build a minimal demo ZIP without credentials, caches, or generated data."""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SENTINEL_demo_ready_validated.zip"

SKIP_DIR_NAMES = {
    ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    "node_modules", "dist", "dist-ssr", "build", "coverage", ".next", ".turbo",
    "venv", ".venv", "__pycache__", "api_cache", "api_raw", "api_status",
    "api_reports", "api_uploads", "real_data_output", "raw", "extracted", "manifests",
}
SKIP_FILE_SUFFIXES = {
    ".pyc", ".pyo", ".zip", ".db", ".sqlite", ".sqlite3", ".log", ".tmp",
    ".bak", ".orig", ".swp", ".lock~",
}
SKIP_FILE_NAMES = {
    ".env", "credentials.json", "secrets.json", "api_raw_responses.csv",
    "ps5.db", "DEMO_READINESS_REPORT.md", "DEMO_VALIDATION_RESULTS.json",
}
SKIP_RELATIVE_DIRS = {
    "data/real_data_output", "data/industry/manifests", "outputs/api_reports",
    "outputs/api_uploads", "outputs",
}
SECRET_NAME_PARTS = (
    "credential", "secret", "private_key", "id_rsa", "id_ed25519",
    "service_account", "access_token",
)
SECRET_CONTENT_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9_-]{16,}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
)
SECRET_ASSIGNMENT = re.compile(
    rb"(?im)\b(?:api[_-]?key|client[_-]?secret|password|access[_-]?token|jwt[_-]?secret)"
    rb"\s*[:=]\s*[\"']([^\"'\r\n]{8,})[\"']"
)
SAFE_SECRET_PLACEHOLDERS = (b"your_", b"change_me", b"placeholder", b"example", b"test_")


def skip_dir(name: str) -> bool:
    return name.lower() in SKIP_DIR_NAMES or name.lower().endswith(".egg-info")


def keep_file(path: Path) -> bool:
    lower_name = path.name.lower()
    if lower_name in {name.lower() for name in SKIP_FILE_NAMES}:
        return False
    if any(part in lower_name for part in SECRET_NAME_PARTS):
        return False
    if path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return False
    if ".env" in lower_name or lower_name.endswith((".pem", ".key", ".p12", ".pfx")):
        return False
    relative = path.relative_to(ROOT).as_posix().lower()
    if any(relative == item or relative.startswith(item + "/") for item in SKIP_RELATIVE_DIRS):
        return False
    if relative.startswith("data/industry/normalized/") and lower_name == "api_raw_responses.csv":
        return False
    return True


def secret_archive_members(names: list[str]) -> list[str]:
    """Return ZIP paths forbidden by filename policy (without exposing contents)."""
    blocked_names = {name.lower() for name in SKIP_FILE_NAMES}
    found = []
    for name in names:
        parts = PurePosixPath(name).parts
        lowered = [part.lower() for part in parts]
        if any(".env" in part or part in blocked_names for part in lowered):
            found.append(name)
        elif any(any(marker in part for marker in SECRET_NAME_PARTS) for part in lowered):
            found.append(name)
        elif any(part.endswith((".pem", ".key", ".p12", ".pfx")) for part in lowered):
            found.append(name)
    return found


def content_secret_members(files: list[Path]) -> list[str]:
    """Detect common credential formats in package candidates without printing values."""
    found = []
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            found.append(path.name)
            continue
        signature_match = any(pattern.search(data) for pattern in SECRET_CONTENT_PATTERNS)
        assignment_match = any(
            not assignment.group(1).lower().startswith(SAFE_SECRET_PLACEHOLDERS)
            for assignment in SECRET_ASSIGNMENT.finditer(data)
        )
        if signature_match or assignment_match:
            try:
                found.append(path.relative_to(ROOT).as_posix())
            except ValueError:
                found.append(path.name)
    return found


def iter_files() -> list[Path]:
    include_roots = [
        ROOT / "src", ROOT / "tests", ROOT / "web", ROOT / "docs", ROOT / "scripts",
        ROOT / "data" / "sample_projects", ROOT / "data" / "demo",
        ROOT / "data" / "industry" / "normalized",
        ROOT / "README.md", ROOT / "requirements.txt", ROOT / "run_tests.py",
    ]
    # These small curated CSVs are the demo catalog and risk-engine inputs.
    include_roots.extend(
        ROOT / "data" / name
        for name in (
            "component_specs.csv", "component_specs_reliability.csv", "criticality.csv",
            "degradation_profiles.csv", "evidence_sources.csv", "lead_times.csv",
            "lifecycle.csv", "reliability_data.csv", "second_source.csv", "stock.csv",
            "synthetic_bom_components.csv", "unit_costs.csv",
        )
    )

    files: set[Path] = set()
    for root in include_roots:
        if root.is_file():
            if keep_file(root):
                files.add(root)
            continue
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if not skip_dir(name)]
            current = Path(dirpath)
            for name in filenames:
                path = current / name
                if keep_file(path):
                    files.add(path)
    return sorted(files)


def main() -> None:
    files = iter_files()
    secrets = content_secret_members(files)
    if secrets:
        raise SystemExit("refusing to package files matching credential signatures: " + ", ".join(secrets))

    # Write atomically so a failed validation never leaves a release-looking ZIP.
    with tempfile.NamedTemporaryFile(prefix="sentinel-demo-", suffix=".zip", dir=ROOT, delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(temp_path) as archive:
            names = archive.namelist()
            blocked = secret_archive_members(names)
            if blocked:
                raise SystemExit("refusing to distribute secret files: " + ", ".join(blocked))
            with tempfile.TemporaryDirectory(prefix=".demo-archive-check-", dir=ROOT) as tmp:
                dest = Path(tmp) / "extracted"
                dest.mkdir()
                archive.extractall(dest)
                required = [
                    "README.md", "requirements.txt", "src/risk_api.py",
                    "tests/test_pipeline_repair.py", "web/src/App.tsx",
                    "data/industry/normalized/component_specs.csv",
                    "data/sample_projects/bom_burglar_alarm.csv",
                ]
                missing = [name for name in required if not (dest / name).exists()]
                if missing:
                    raise SystemExit("missing from package: " + ", ".join(missing))
        temp_path.replace(OUT)
    finally:
        temp_path.unlink(missing_ok=True)

    print(f"zip={OUT}")
    print(f"bytes={OUT.stat().st_size}")
    print(f"files={len(files)}")
    print("credential_scan=passed")
    print("extract_check=passed")


if __name__ == "__main__":
    main()
