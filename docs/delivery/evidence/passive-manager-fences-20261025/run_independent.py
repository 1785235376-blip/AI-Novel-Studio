"""Portable replay of the unchanged independent probe source, not new coverage."""
import sys
from pathlib import Path
# Importing the delivered primary runner sets isolation and blocks sockets.
from run_tests import root
sys.path.insert(0, str(root / 'tests'))
import pytest
if __name__ == '__main__':
    raise SystemExit(pytest.main(['-q', str(Path(__file__).parent / 'independent/test_independent.py'), *sys.argv[1:]]))
