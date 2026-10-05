from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("windows_base", ROOT / "scripts/prepare_windows_base.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def archive(*names: str) -> zipfile.ZipFile:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as value:
        for name in names:
            value.writestr(name, b"synthetic")
    stream.seek(0)
    return zipfile.ZipFile(stream)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "dir\\escape", "dir/../../escape", "CON.txt", "dir/aux", "trailing.", "space ", "dir/./file", "dir//file"])
def test_archive_path_rejected_before_write(name):
    with archive("good/file", name) as value, pytest.raises(ValueError, match="Unsafe archive path"):
        base.safe_members(value)


def test_archive_duplicate_case_is_rejected():
    with archive("file", "FILE") as value, pytest.raises(ValueError, match="Duplicate"):
        base.safe_members(value)


def test_archive_symlink_is_rejected():
    stream = io.BytesIO()
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(stream, "w") as value:
        value.writestr(info, "outside")
    stream.seek(0)
    with zipfile.ZipFile(stream) as value, pytest.raises(ValueError, match="Link/special"):
        base.safe_members(value)


def test_postgres_extract_is_allowlisted_and_retains_notices(tmp_path):
    source = tmp_path / "source.zip"
    with zipfile.ZipFile(source, "w") as value:
        for name in ("pgsql/bin/postgres.exe", "pgsql/lib/pgcrypto.dll", "pgsql/share/extension/pgcrypto.control", "pgsql/doc/license.txt", "pgsql/server_license.txt", "pgsql/pgAdmin 4/unrelated.exe", "pgsql/StackBuilder/unrelated.exe"):
            value.writestr(name, b"synthetic")
    output = tmp_path / "out"
    base.extract(source, output, postgres=True)
    assert (output / "bin/postgres.exe").read_bytes() == b"synthetic"
    assert (output / "server_license.txt").is_file()
    assert not (output / "pgAdmin 4").exists()
    assert not (output / "StackBuilder").exists()


@pytest.mark.parametrize("url", ["http://www.python.org/input.zip", "https://evil.invalid/input.zip", "https://www.python.org.evil.invalid/input.zip", "https://user:secret@www.python.org/input.zip", "https://www.python.org:444/input.zip"])
def test_input_origin_is_fail_closed(url):
    with pytest.raises(ValueError, match="HTTPS"):
        base.checked_url(url)


def test_cache_hash_mismatch_is_never_accepted(tmp_path):
    path = tmp_path / "official.zip"
    path.write_bytes(b"tampered")
    item = {"filename": path.name, "url": "https://www.python.org/official.zip", "size": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
    with pytest.raises(ValueError, match="Cached input digest"):
        base.download(item, tmp_path)
    assert path.read_bytes() == b"tampered"


def test_matching_cache_does_not_require_network(tmp_path):
    path = tmp_path / "official.zip"
    path.write_bytes(b"original")
    item = {"filename": path.name, "url": "https://www.python.org/official.zip", "size": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
    assert base.download(item, tmp_path) == path


def test_fresh_output_and_separate_cache_required(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="fresh"):
        base.prepare(output, tmp_path / "cache", None)
    with pytest.raises(ValueError, match="separate trees"):
        base.prepare(tmp_path / "new", tmp_path / "new/cache", None)


def test_crt_is_external_unless_caller_supplies_licensed_redist(tmp_path):
    assert base.find_vc_redist(None) is None
    with pytest.raises(ValueError, match="REDIST"):
        base.find_vc_redist(tmp_path / "System32")


def test_embedded_import_path_is_relative_and_isolated():
    assert base.PTH_CONTENT.splitlines() == ["python312.zip", ".", "Lib\\site-packages", "..\\..\\Backend", "import site"]
    assert "PYTHONPATH" not in base.PTH_CONTENT


def test_every_locked_wheel_has_exact_origin_digest_and_license():
    manifest = json.loads(base.LOCK.read_text())
    requirements = (ROOT / "packaging/requirements-windows.lock.txt").read_text()
    assert len(manifest["wheels"]) >= 27
    for item in [*manifest["runtime_inputs"], *manifest["wheels"]]:
        base.checked_url(item["url"])
        assert len(item["sha256"]) == 64
        assert item["size"] > 0
        assert item["license_files"]
    for item in manifest["wheels"]:
        assert f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}" in requirements
    assert any(row["name"] == "reportlab" for row in manifest["wheels"])
    assert any(row["name"] == "tzdata" for row in manifest["wheels"])
    assert manifest["external_prerequisites"]["webview2"]["new_runtime_license_accepted"] is False
    assert manifest["external_prerequisites"]["visual_cpp"]["new_runtime_license_accepted"] is False


def test_full_package_forwards_font_and_builds_self_contained_host():
    script = (ROOT / "scripts/package_windows_acceptance.ps1").read_text()
    assert "-VerifiedFontDirectory (Resolve-Absolute $VerifiedFontDirectory 'VerifiedFontDirectory')" in script
    build = (ROOT / "scripts/build_windows_application.ps1").read_text()
    assert "--self-contained true" in build
    assert "restore $hostProjectPath -r win-x64 -p:SelfContained=true" in build
    sdk = json.loads((ROOT / "global.json").read_text())["sdk"]
    assert sdk == {"version": "8.0.424", "rollForward": "disable", "allowPrerelease": False}


def test_native_verification_is_explicit_and_synthetic():
    script = (ROOT / "scripts/verify_windows_base.py").read_text()
    assert 'sys.platform != "win32"' in script
    assert "CREATE EXTENSION pgcrypto" in script
    assert '"--format=custom"' in script
    assert '"--exit-on-error"' in script
    assert '"interactive_desktop": "NOT_RUN"' in script
    assert '"user_acceptance": "NOT_RUN"' in script
    assert '"PATH": str(Path(windows) / "System32")' in script


def test_real_locked_metadata_closes_windows_dependency_markers():
    lock = json.loads(base.LOCK.read_text())
    base.validate_dependency_closure(lock)
    lock["wheels"] = [item for item in lock["wheels"] if item["name"] != "tzdata"]
    with pytest.raises(ValueError, match="tzdata"):
        base.validate_dependency_closure(lock)


def test_runtime_notices_are_copied_from_exact_restored_packages():
    source = (ROOT / "scripts/build_windows_application.ps1").read_text()
    assert "obj\\project.assets.json" in source
    assert "Microsoft.NETCore.App.Runtime.win-x64" in source
    assert "Microsoft.WindowsDesktop.App.Runtime.win-x64" in source
    assert "Full third-party notices missing" in source
    assert "runtime_license_provenance = $runtimeLicenseProvenance" in source
