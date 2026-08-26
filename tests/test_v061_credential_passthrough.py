from __future__ import annotations

import json
import subprocess
import sys

from scripts import v061_acceptance_environment as acceptance


SENTINEL = "TEST_ONLY_DEEPSEEK_SECRET_SENTINEL"


def test_parent_provider_secret_reaches_child_but_not_manifest(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", SENTINEL)
    monkeypatch.setenv("REAL_PROVIDER_VERIFICATION", "true")
    manifest = acceptance.build_manifest()
    child = acceptance.build_child_environment(manifest["environment"], dict(acceptance.os.environ))
    serialized = json.dumps(manifest)
    diagnostics = json.dumps(acceptance.safe_environment_diagnostics(child))

    assert child["DEEPSEEK_API_KEY"] == SENTINEL
    assert child["REAL_PROVIDER_VERIFICATION"] == "true"
    assert SENTINEL not in serialized
    assert SENTINEL not in diagnostics
    assert "DEEPSEEK_API_KEY" not in manifest["environment"]


def test_composed_environment_is_inherited_by_fastapi_style_python_child(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", SENTINEL)
    monkeypatch.setenv("REAL_PROVIDER_VERIFICATION", "true")
    manifest = acceptance.build_manifest()
    child = acceptance.build_child_environment(manifest["environment"], dict(acceptance.os.environ))
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os;"
                "print('CREDENTIAL_PRESENT='+str(bool(os.environ.get('DEEPSEEK_API_KEY'))));"
                "print('REAL_PROVIDER_VERIFICATION='+os.environ.get('REAL_PROVIDER_VERIFICATION','UNSET'))"
            ),
        ],
        env=child,
        text=True,
        capture_output=True,
        check=True,
    )
    assert probe.stdout.splitlines() == [
        "CREDENTIAL_PRESENT=True",
        "REAL_PROVIDER_VERIFICATION=true",
    ]
    assert SENTINEL not in probe.stdout
    assert SENTINEL not in probe.stderr


def test_empty_manifest_placeholder_cannot_erase_process_only_secret():
    manifest_environment = {"DEEPSEEK_API_KEY": "", "APP_ENV": "acceptance"}
    child = acceptance.build_child_environment(
        manifest_environment,
        {"DEEPSEEK_API_KEY": SENTINEL, "APP_ENV": "parent"},
    )
    assert child["DEEPSEEK_API_KEY"] == SENTINEL
    assert child["APP_ENV"] == "acceptance"


def test_missing_parent_secret_remains_absent_even_if_manifest_contains_stale_value():
    child = acceptance.build_child_environment(
        {"DEEPSEEK_API_KEY": SENTINEL, "APP_ENV": "acceptance"},
        {},
    )
    assert "DEEPSEEK_API_KEY" not in child


def test_mock_and_real_verification_modes_remain_isolated(monkeypatch):
    monkeypatch.delenv("REAL_PROVIDER_VERIFICATION", raising=False)
    mock_manifest = acceptance.build_manifest()
    assert mock_manifest["environment"]["MOCK_PROVIDER"] == "true"

    monkeypatch.setenv("REAL_PROVIDER_VERIFICATION", "true")
    real_manifest = acceptance.build_manifest()
    real_child = acceptance.build_child_environment(real_manifest["environment"], dict(acceptance.os.environ))
    assert real_manifest["environment"]["MOCK_PROVIDER"] == "false"
    assert real_child["MOCK_PROVIDER"] == "false"
    assert real_child["REAL_PROVIDER_VERIFICATION"] == "true"


def test_all_approved_provider_secrets_are_process_only(monkeypatch):
    for key in acceptance.PROVIDER_SECRET_ENVIRONMENT_KEYS:
        monkeypatch.setenv(key, f"{key}_SENTINEL")
    manifest = acceptance.build_manifest()
    serialized = json.dumps(manifest)
    child = acceptance.build_child_environment(manifest["environment"], dict(acceptance.os.environ))
    diagnostics = json.dumps(acceptance.safe_environment_diagnostics(child))
    for key in acceptance.PROVIDER_SECRET_ENVIRONMENT_KEYS:
        assert key not in manifest["environment"]
        assert f"{key}_SENTINEL" not in serialized
        assert f"{key}_SENTINEL" not in diagnostics
        assert child[key] == f"{key}_SENTINEL"
