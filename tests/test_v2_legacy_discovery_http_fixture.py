"""Original HTTP legacy scan/revocation with fixed synthetic existing identities."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.run_v2_checks import isolated_environment


@pytest.mark.parametrize("acceptance", [False, True])
def test_legacy_actual_host_http_scan_revoke_and_other_existing_host_session(tmp_path, acceptance):
    root = Path(__file__).resolve().parents[1]
    owned = tmp_path / "legacy-host-process"
    env = {**os.environ, **isolated_environment(root, owned),
        "V2_DISCOVERY_FIXTURE_ROOT": str(owned), "NOVEL_DATA_PATH": str(owned / "novel-data"),
        "EXPERIMENTAL_FEATURES": "narrative_production_v2" if acceptance else "",
        "V1_ACCEPTANCE_MODE": str(acceptance).lower(), "COLLABORATION_DEV_SESSIONS_JSON": "",
        "FRONTEND_ORIGIN": "http://127.0.0.1:5187", "ENABLE_PROVIDER_FALLBACK": "false",
        "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true"}
    result = subprocess.run([sys.executable, str(root / "tests/v2_discovery_browser_server.py"), "--self-check-legacy-host"],
        env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt["hardware_calls"] == 1 and len(receipt["probe_calls"]) == 5
    assert receipt["scan_status"] == "COMPLETED"
    assert receipt["inference_status"] == receipt["windows_acceptance"] == "NOT_RUN"
    assert receipt["registrations"] == receipt["enabled_registrations"] == receipt["launch_attempts"] == 0
    assert receipt["model_weights_loaded"] is False and receipt["blocked_attempts"] == []
