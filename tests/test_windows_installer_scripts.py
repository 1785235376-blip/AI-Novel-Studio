from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "installer"
PACKAGE_SCRIPT = ROOT / "scripts" / "package_windows_acceptance.ps1"


def _text(name: str) -> str:
    return (INSTALLER / name).read_text(encoding="utf-8")


def test_launcher_isolated_and_supports_both_staged_layouts():
    source = _text("Launch-AI-Novel-Studio.ps1")
    assert "Resolve-AbsolutePath" in source
    assert "Join-Path $launcherRoot 'Application'" in source
    assert "Join-Path $launcherRoot '..'" in source
    assert "Push-Location -LiteralPath $backend" in source
    assert "'-I', '-m', 'app.packaging.packaged_desktop_launcher'" in source
    assert "$env:PYTHONPATH" not in source
    assert "DesktopHost\\AI-Novel-Studio.DesktopHost.exe" in source
    assert "PostgreSQL\\bin\\postgres.exe" in source


def test_installer_and_uninstaller_bound_destructive_paths():
    install = _text("Install-AI-Novel-Studio.ps1")
    uninstall = _text("Uninstall-AI-Novel-Studio.ps1")
    assert "Assert-UnderRoot" in install
    assert "InstallRoot parent" in install
    assert "movedExisting" in install
    assert "Move-Item -LiteralPath $backup -Destination $destination" in install
    assert "Assert-NoReparsePoint" in install
    assert "Assert-NoReparsePoint" in uninstall
    assert "InstallRoot must remain under %LOCALAPPDATA%\\Programs." in uninstall
    assert "$RemoveUserData" in uninstall


def test_acceptance_packaging_uses_literal_iexpress_paths_and_cleans_temp():
    source = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    assert "public_release = $false" in source
    assert "$sourceRoot = $iexpressSource" in source
    # Keep IExpress paths literal.  The script may use a temporary target
    # (copied to the requested output only after makecab settles) or assign
    # the output path directly; both forms are safe as long as no additional
    # backslash escaping is introduced into the SED.
    assert (
        "$targetTemp = Join-Path $iexpressWork" in source
        or "$targetEscaped = $targetExe" in source
    )
    assert "rmdir /s /q \"%ROOT%\"" in source
    assert "set \"PAYLOAD_ZIP=%~dp0payload.zip\"" in source
    assert "$env:PAYLOAD_ZIP" in source
    assert "if errorlevel 1 (" in source
    assert "goto :cleanup" in source
    assert "API_KEY" not in source


def test_windows_installer_scripts_parse_without_mutation():
    powershell = shutil.which("powershell.exe")
    if not powershell:
        return
    files = [
        INSTALLER / "Install-AI-Novel-Studio.ps1",
        INSTALLER / "Launch-AI-Novel-Studio.ps1",
        INSTALLER / "Uninstall-AI-Novel-Studio.ps1",
        PACKAGE_SCRIPT,
    ]
    script = r'''
$files = @(%s)
foreach ($file in $files) {
  $tokens = $null; $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors.Count -gt 0) { exit 1 }
}
''' % ",".join('"' + str(path).replace('"', '""') + '"' for path in files)
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr or result.stdout
