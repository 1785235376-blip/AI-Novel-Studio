from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.packaging.paths import WindowsPackagingPaths, validate_destructive_target
from app.packaging.versioning import (
    VersionMismatch,
    load_release_version,
    validate_manifest_version,
    validate_repository_versions,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_version_contract(tmp_path: Path) -> Path:
    copied = tmp_path / "repo"
    for relative in (
        "release/version.json", "pyproject.toml", "app/__init__.py",
        "frontend/package.json", ".env.example", "README.md", "docs/installation.md",
    ):
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return copied


def test_release_version_has_one_authoritative_source_and_consumers_match():
    release = load_release_version(ROOT / "release" / "version.json")
    assert release.version == "0.7.0"
    assert release.display_version == "0.7.0 Beta"
    assert set(validate_repository_versions(ROOT)) == {
        "backend", "backend_module", "frontend", "environment"
    }


def test_version_and_manifest_mismatches_fail_explicitly(tmp_path: Path):
    release = load_release_version(ROOT / "release" / "version.json")
    with pytest.raises(VersionMismatch, match="manifest app_version mismatch"):
        validate_manifest_version(
            {"app_version": "0.6.9", "backup_format_version": "0.1.0"}, release
        )

    copied = _copy_version_contract(tmp_path)
    package = json.loads((copied / "frontend/package.json").read_text(encoding="utf-8"))
    package["version"] = "0.6.9"
    (copied / "frontend/package.json").write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(VersionMismatch, match="frontend"):
        validate_repository_versions(copied)


def test_backend_and_documentation_mismatches_fail_explicitly(tmp_path: Path):
    backend = _copy_version_contract(tmp_path / "backend")
    pyproject = (backend / "pyproject.toml").read_text(encoding="utf-8")
    (backend / "pyproject.toml").write_text(
        pyproject.replace('version = "0.7.0"', 'version = "0.6.9"'), encoding="utf-8"
    )
    with pytest.raises(VersionMismatch, match="backend"):
        validate_repository_versions(backend)

    documentation = _copy_version_contract(tmp_path / "documentation")
    (documentation / "README.md").write_text("# Unversioned documentation\n", encoding="utf-8")
    with pytest.raises(VersionMismatch, match="README.md"):
        validate_repository_versions(documentation)


def test_format_versions_remain_separate_from_application_version():
    backup = (ROOT / "scripts" / "backup.ps1").read_text(encoding="utf-8")
    export = (ROOT / "scripts" / "export-project.ps1").read_text(encoding="utf-8")
    assert "backup_version='0.1.0'" in backup
    assert "app_version=(Get-ReleaseVersion $root)" in backup
    assert "version='0.1.0'" in export
    assert "app_version=(Get-ReleaseVersion $root)" in export


def test_windows_paths_resolve_to_separated_contract_roots(tmp_path: Path):
    local = tmp_path / "LocalAppData"
    profile = tmp_path / "User"
    paths = WindowsPackagingPaths.resolve(local_app_data=local, user_profile=profile)
    assert paths.application == (local / "Programs" / "AI-Novel-Studio").resolve()
    assert paths.user_data == (local / "AI-Novel-Studio" / "UserData").resolve()
    assert paths.database == paths.user_data / "PostgreSQL"
    assert paths.novel_data == paths.user_data / "NovelData"
    assert paths.backups == (profile / "Documents" / "AI-Novel-Studio" / "Backups").resolve()
    assert not paths.user_data.is_relative_to(paths.application)
    assert set(paths.normal_uninstall_roots).isdisjoint(paths.preserved_roots)


def test_path_contract_rejects_data_inside_application(tmp_path: Path):
    paths = WindowsPackagingPaths.resolve(
        local_app_data=tmp_path / "LocalAppData", user_profile=tmp_path / "User"
    )
    with pytest.raises(ValueError, match="Durable data"):
        replace(paths, novel_data=paths.application / "novels").validate()


def test_destructive_target_requires_explicit_narrow_root(tmp_path: Path):
    paths = WindowsPackagingPaths.resolve(
        local_app_data=tmp_path / "LocalAppData", user_profile=tmp_path / "User"
    )
    cache_item = paths.cache / "generated" / "item.tmp"
    assert validate_destructive_target(
        cache_item, allowed_roots=paths.normal_uninstall_roots
    ) == cache_item
    with pytest.raises(ValueError, match="outside"):
        validate_destructive_target(
            paths.user_data / "novels", allowed_roots=paths.normal_uninstall_roots
        )
    with pytest.raises(ValueError, match="outside"):
        validate_destructive_target(tmp_path, allowed_roots=paths.normal_uninstall_roots)
    with pytest.raises(ValueError, match="outside"):
        validate_destructive_target(paths.cache, allowed_roots=paths.normal_uninstall_roots)
    assert validate_destructive_target(
        paths.cache, allowed_roots=paths.normal_uninstall_roots, allow_root=True
    ) == paths.cache


def test_path_contract_never_contains_secret_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sentinel = "SECRET_SENTINEL_DO_NOT_WRITE"
    monkeypatch.setenv("DEEPSEEK_API_KEY", sentinel)
    paths = WindowsPackagingPaths.resolve(
        local_app_data=tmp_path / "LocalAppData", user_profile=tmp_path / "User"
    )
    serialized = json.dumps(paths.as_public_dict(), ensure_ascii=False)
    assert sentinel not in serialized
    assert "api_key" not in serialized.lower()
