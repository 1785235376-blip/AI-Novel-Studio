from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_windows_application.ps1"


def test_windows_application_build_stages_same_run_desktophost_publish():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "desktop-host\\AI.NovelStudio.DesktopHost" in source
    assert "dotnetExecutable publish" in source
    assert "Copy-Item -LiteralPath $HostPublishDirectory" in source
    assert "fresh_host_dll_sha256" in source
    assert "staged_host_dll_sha256" in source
    assert "$freshHash -ne $stagedHash" in source
    assert "Staged DesktopHost DLL does not match" in source


def test_windows_application_build_has_no_historical_host_fallback():
    source = SCRIPT.read_text(encoding="utf-8").casefold()

    assert ".phase52-publish" not in source
    assert "host publish directory must be fresh" in source
    assert "desktophost publish failed" in source
