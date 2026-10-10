"""Bounded diagnostic: add transaction latency without replacing M4 owners."""
from hashlib import sha256
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_v2_ai_execution_runtime as target

original_refresh = target.refresh
refresh_calls = 0


def slow_refresh(*args, **kwargs):
    global refresh_calls
    refresh_calls += 1
    time.sleep(0.25)
    return original_refresh(*args, **kwargs)


target.refresh = slow_refresh
print("Diagnostic harness SHA256:", sha256(Path(__file__).read_bytes()).hexdigest(), flush=True)
print("Added latency per real refresh: 0.25 seconds; provider wait remains 6 seconds", flush=True)
try:
    result = pytest.main(sys.argv[1:])
finally:
    print("Real refresh calls:", refresh_calls, flush=True)
raise SystemExit(result)
