from pathlib import Path

from scripts.package_demo_zip import (
    ROOT,
    content_secret_members,
    keep_file,
    secret_archive_members,
    skip_dir,
)


def test_demo_packager_omits_cache_and_generated_paths():
    assert skip_dir("node_modules")
    assert skip_dir("api_cache")
    assert skip_dir("raw")
    assert not skip_dir("sample_projects")
    assert not keep_file(ROOT / "data" / "ps5.db")
    assert not keep_file(ROOT / "outputs" / "risk_analysis.json")
    assert keep_file(ROOT / "README.md")


def test_demo_packager_rejects_secret_paths_and_signatures(tmp_path):
    assert secret_archive_members([
        "src/app.py", "config/.env", "certs/private_key.pem", "data/secrets.json"
    ]) == ["config/.env", "certs/private_key.pem", "data/secrets.json"]

    candidate = tmp_path / "credential.txt"
    candidate.write_bytes(("sk" + "_live_" + "A" * 20).encode())
    assert content_secret_members([candidate]) == [candidate.relative_to(ROOT).as_posix()]

