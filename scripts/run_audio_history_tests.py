"""Run this task's synthetic tests with every app data path isolated."""
from __future__ import annotations
import os
from pathlib import Path
import sys

def main():
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime' / 'audio-history-20261025'
    runtime.mkdir(parents=True, exist_ok=True)
    # Only this child process uses a synthetic profile; no real credentials or
    # previous projects are read or changed.
    os.environ.update({
        'USERPROFILE': str(runtime / 'profile'),
        'NOVEL_DATA_PATH': str(runtime / 'data'),
        'LOCALAPPDATA': str(runtime / 'local'),
        'APPDATA': str(runtime / 'roaming'),
        'XDG_DATA_HOME': str(runtime / 'xdg-data'),
        'XDG_CONFIG_HOME': str(runtime / 'xdg-config'),
        'XDG_CACHE_HOME': str(runtime / 'xdg-cache'),
        'STORAGE_BACKEND': 'file', 'ENABLE_CLOUD': 'false',
        'MOCK_PROVIDER': 'true', 'CREDENTIAL_VAULT_BACKEND': 'memory',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    os.chdir(root)
    sys.path.insert(0, str(root))
    import pytest
    return pytest.main(sys.argv[1:])

if __name__ == '__main__':
    raise SystemExit(main())
