"""Package SENTINEL_demo_ready_validated.zip without secrets or bulky extracts."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SENTINEL_demo_ready_validated.zip"

SKIP_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "incoming_industry_data",
}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".zip", ".env"}
SKIP_FILE_NAMES = {".env", "credentials.json", "secrets.json"}
KEEP_EXTRACTED_NAMES = {
    "BeagleBone_Black_Wireless_BOM.csv",
    "BeagleBone-AI_bom.csv",
}


def skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.endswith(".egg-info")


def keep_file(path: Path) -> bool:
    if path.name in SKIP_FILE_NAMES:
        return False
    if path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return False
    if path.name.startswith(".env"):
        return False
    if "extracted" in path.parts:
        return path.name in KEEP_EXTRACTED_NAMES
    return True


def iter_files() -> list[Path]:
    include_roots = [
        ROOT / "src",
        ROOT / "tests",
        ROOT / "web",
        ROOT / "docs",
        ROOT / "scripts",
        ROOT / "data",
        ROOT / "outputs" / "DEMO_READINESS_REPORT.md",
        ROOT / "outputs" / "DEMO_VALIDATION_RESULTS.json",
        ROOT / "README.md",
        ROOT / "requirements.txt",
        ROOT / "run_tests.py",
    ]
    files: list[Path] = []
    for root in include_roots:
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if not skip_dir(name)]
            current = Path(dirpath)
            for name in filenames:
                path = current / name
                if keep_file(path):
                    files.append(path)
    return files


def main() -> None:
    files = iter_files()
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "extracted"
        dest.mkdir()
        with zipfile.ZipFile(OUT) as archive:
            archive.extractall(dest)
            namelist = archive.namelist()
        required = [
            "README.md",
            "requirements.txt",
            "src/risk_api.py",
            "tests/test_pipeline_repair.py",
            "web/src/App.tsx",
            "data/industry/normalized/component_specs.csv",
            "outputs/DEMO_READINESS_REPORT.md",
            "outputs/DEMO_VALIDATION_RESULTS.json",
        ]
        missing = [name for name in required if not (dest / name).exists()]
        print(f"zip={OUT}")
        print(f"bytes={OUT.stat().st_size}")
        print(f"files={len(namelist)}")
        print(f"extract_ok={not missing}")
        if missing:
            raise SystemExit("missing from extract: " + ", ".join(missing))


if __name__ == "__main__":
    main()
