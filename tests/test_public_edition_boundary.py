"""Public-edition boundary: build invariants, default-off surfaces and non-leak checks.

SPEC-2026.10.19-r1 release gate 10 requires the public distribution and the internal
research edition to be separated. This suite covers the part that is genuinely implemented
here: the static public-build invariants, fail-closed default-off runtime surfaces and the
absence of credential/config leakage in public metadata routes. The internal research
deployment isolation is declared BLOCKED by the edition manifest and this suite asserts that
declaration instead of pretending it exists.

No server process, model, provider, database or network is used.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_public_edition.py"
MANIFEST = ROOT / "docs" / "v2" / "engineering" / "edition_manifest.json"
SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY)")


def run_verifier(env_edition: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("V1_ACCEPTANCE_MODE", None)
    env.pop("EXPERIMENTAL_FEATURES", None)
    env["POEMSEED_STUDIO_EDITION"] = env_edition or "PUBLIC"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, str(VERIFIER)], cwd=ROOT, env=env,
                          text=True, encoding="utf-8", errors="replace", capture_output=True)


def test_public_edition_verifier_passes_all_checks() -> None:
    result = run_verifier("PUBLIC")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["edition"] == "PUBLIC"
    assert not report["failed"]
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    for required in (
        "flags.no_wildcard_literal",
        "packaged.cloud_false",
        "packaged.experimental_closed_list",
        "launcher.isolated_python",
        "inputs.no_secret_or_weight_files",
        "internal_boundary.declared_blocked",
    ):
        assert statuses.get(required) == "PASS", required


def test_internal_research_edition_is_blocked_not_claimed_as_implemented() -> None:
    result = run_verifier("INTERNAL_RESEARCH")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "BLOCKED"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    boundary = manifest["internal_research_boundary"]
    assert boundary["status"] == "BLOCKED" and boundary["implemented"] is False
    assert boundary["missing"], "blocked boundary must list the concrete missing separation work"


def test_default_public_runtime_exposes_no_experimental_surface(monkeypatch) -> None:
    monkeypatch.delenv("EXPERIMENTAL_FEATURES", raising=False)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    from app.main import app

    client = TestClient(app)
    features = client.get("/api/experimental/features")
    assert features.status_code == 200
    body = features.json()
    assert body["default_enabled"] is False
    assert all(value is False for value in body["features"].values())
    # A V2 experimental owner route is feature-disabled (404) without an explicit opt-in.
    gated = client.get("/api/novels/synthetic/experimental/workspace/search?q=gate")
    assert gated.status_code == 404
    assert gated.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"
    assert client.get("/api/local-interop/health").status_code in {404, 401}
    # The same gate applies through the versioned prefix; it cannot be bypassed there.
    versioned = client.get("/api/v1/experimental/features")
    assert versioned.status_code == 200
    assert versioned.json()["default_enabled"] is False
    assert all(value is False for value in versioned.json()["features"].values())


def test_public_metadata_routes_do_not_leak_credentials(monkeypatch) -> None:
    monkeypatch.delenv("EXPERIMENTAL_FEATURES", raising=False)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    from app.main import app

    client = TestClient(app)
    for path in ("/api/health", "/api/providers", "/api/models"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        text = response.text
        assert not SECRET_PATTERN.search(text), path
        lowered = text.lower()
        for forbidden in ("api_key", "api-key", "client_secret", "authorization:", "password="):
            assert forbidden not in lowered, (path, forbidden)


def test_v1_acceptance_mode_keeps_experimental_routes_disabled(monkeypatch) -> None:
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,workspace_tools_v2")
    from app.main import app

    client = TestClient(app)
    features = client.get("/api/experimental/features").json()
    assert features["default_enabled"] is False
    assert all(value is False for value in features["features"].values())
    assert client.get("/api/novels/missing/experimental/workspace/search?q=x").status_code in {401, 404}
    assert client.get("/api/v1/experimental/features").json()["default_enabled"] is False


def test_edition_module_fails_closed(monkeypatch) -> None:
    from app import edition

    monkeypatch.setenv("POEMSEED_STUDIO_EDITION", "NOT_A_REAL_EDITION")
    assert edition.current_edition() == edition.PUBLIC
    monkeypatch.setenv("POEMSEED_STUDIO_EDITION", "INTERNAL_RESEARCH")
    assert edition.current_edition() == edition.INTERNAL_RESEARCH
    monkeypatch.delenv("POEMSEED_STUDIO_EDITION", raising=False)
    assert edition.current_edition() == edition.PUBLIC
    manifest = edition.load_manifest()
    assert manifest["spec"] == "SPEC-2026.10.19-r1"
