from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_windows_application.ps1"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_formal_application_builds_and_hashes_current_frontend():
    source = _source()
    assert "Push-Location -LiteralPath $frontendSource" in source
    assert "finally {\n    Pop-Location\n}" in source
    assert "build --configLoader runner --outDir $frontendBuild --emptyOutDir" in source
    assert "Fresh frontend build is missing index.html" in source
    assert "Assert-InventoriesMatch $frontendBuildInventory $frontendStageInventory 'Frontend'" in source
    assert "Remove-Item -LiteralPath $stagedFrontend" in source


def test_formal_application_stages_explicit_current_backend_inventory():
    source = _source()
    assert "foreach ($name in @('config', 'prompts', 'workflows'))" in source
    assert "Copy-ProductTree $backendAppSource" in source
    assert "@('.py')" in source
    assert "__pycache__" in source
    assert "Backend staging inventory is missing required product files" in source
    assert "Assert-InventoriesMatch $backendSourceInventory $backendStageInventory 'Backend'" in source


def test_formal_application_fails_closed_and_records_all_product_components():
    source = _source()
    assert "--list-sdks" in source
    assert ".NET SDK is required for same-run DesktopHost provenance" in source
    assert "Approved .NET SDK 8.0.424 is required for DesktopHost provenance" in source
    assert "Selected .NET SDK base path does not exist" in source
    assert "Frontend production build failed" in source
    assert "Frontend source/stage inventory mismatch" not in source
    assert "source/stage inventory mismatch" in source
    assert "application-provenance.json" in source
    assert "frontend = [ordered]@{" in source
    assert "backend = [ordered]@{" in source
    assert "desktophost = [ordered]@{" in source
    assert "CPython 3.12.10 x64" in source
    assert "PostgreSQL 16.4 x64" in source
    assert "dotnet_executable = $dotnetExecutable" in source
    assert "dotnet_sdk_version = $sdkVersion" in source
    assert "dotnet_sdk_base_path = $sdkBasePath" in source
    assert "target_framework = $hostTargetFramework" in source


def test_historical_base_is_only_frozen_payload_authority():
    source = _source()
    assert "frozen_payload_source" in source
    assert "frozen_payload = @('Runtime', 'PostgreSQL', 'Launcher', 'Licenses', 'Tools', 'ConfigDefaults')" in source
    assert source.index("Copy-Item -LiteralPath $baseApplicationPath") < source.index("$stagedFrontend")
    assert source.index("Copy-Item -LiteralPath $baseApplicationPath") < source.index("$stagedBackend")
