from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "portable" / "AI-Novel-Studio-Portable.cmd"
README = ROOT / "packaging" / "portable" / "README.md"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_portable_entry_is_a_fixed_staged_application_launcher():
    source = _source()
    assert 'set "APPLICATION_ROOT=%~dp0Application"' in source
    assert '"%PYTHON%" -I -m app.packaging.packaged_desktop_launcher --application-root "%APPLICATION_ROOT%"' in source
    assert "Backend\\app\\packaging\\packaged_desktop_launcher.py" in source
    assert "DesktopHost\\AI-Novel-Studio.DesktopHost.exe" in source
    assert "Frontend\\dist\\index.html" in source
    assert "PostgreSQL\\bin\\postgres.exe" in source
    assert "PostgreSQL\\bin\\initdb.exe" in source
    assert "release\\version.json" in source
    # Never hand arbitrary arguments or a caller-selected application root to
    # the packaged launcher from a double-click entry point.
    assert "%*" not in source
    assert "start " not in source.casefold()


def test_portable_entry_has_no_secret_or_installer_claims():
    source = (SCRIPT.read_text(encoding="utf-8") + README.read_text(encoding="utf-8")).casefold()
    assert "api_key" not in source
    assert "installer" in source
    assert "not an installer" in source
    assert "-i" in source
