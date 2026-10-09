"""Real mounted authority/API with bounded synthetic discovery adapters only."""
from dataclasses import replace
import time

import pytest
from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.trusted_sessions import TrustedSessionResolver
from test_local_ai_discovery import service, ollama, scan


@pytest.fixture
def onboard(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "settings", replace(main.settings,
        enable_collaboration_runtime=False, enable_packaged_runtime=False))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    monkeypatch.setattr("app.model_center.discovery_environment.common_model_roots", lambda: [])
    sessions = TrustedSessionResolver()
    sessions.register("synthetic-scope-host", SessionContext("session", "host", "author", "workspace"))
    monkeypatch.setattr(main, "trusted_session_resolver", sessions)
    svc = service(tmp_path)
    ollama(svc.client)
    for method in ("snapshot", "preview_scan_scope", "start_consented_scan", "start_legacy_http_scan",
                   "get_scan", "cancel_scan", "configure_roots", "environment_report", "validate",
                   "register", "configure_runtime", "configure_registration", "enable", "disable", "remove"):
        monkeypatch.setattr(main.local_ai_discovery, method, getattr(svc, method))
    return TestClient(main.app), svc, sessions


HEADERS = {"X-Session-Token": "synthetic-scope-host"}


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_preview_and_strict_confirm_share_original_worker_without_implicit_register_or_enable(onboard, prefix):
    client, svc, _ = onboard
    root = prefix + "/model-center/local-ai"
    preview = client.get(root + "/onboarding/scan-scope?include_common_model_dirs=false", headers=HEADERS)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["execution_scope"] == "BACKEND_HOST" and body["inference_status"] == "NOT_RUN"
    assert body["include_common_model_dirs"] is False
    assert body["side_effects"]["registers"] is False and body["side_effects"]["enables"] is False
    assert body["side_effects"]["may_disable_stale_registrations"] is True
    assert body["side_effects"]["persists_registration_safety_updates"] is True
    assert preview.headers["Cache-Control"] == "no-store"
    assert svc.scan is None and svc.client.calls == []
    confirmed = client.post(root + "/onboarding/scan", headers=HEADERS,
        json={"scope_digest": body["scope_digest"], "confirmed": True})
    assert confirmed.status_code == 202, confirmed.text
    scan = confirmed.json()
    assert scan["consent"]["scope_digest"] == body["scope_digest"]
    assert scan["consent"]["execution_scope"] == "BACKEND_HOST"
    deadline = time.monotonic() + 2
    while svc.get_scan(scan["id"])["status"] == "RUNNING" and time.monotonic() < deadline:
        time.sleep(0.005)
    assert svc.get_scan(scan["id"])["status"] != "RUNNING"
    repeated = client.post(root + "/onboarding/scan", headers=HEADERS,
        json={"scope_digest": body["scope_digest"], "confirmed": True})
    assert repeated.status_code == 202 and repeated.json()["id"] == scan["id"]
    assert not svc.registrations
    svc.center.lifecycle.start.assert_not_called()
    assert all(payload is None for _, _, payload in svc.client.calls)
    assert "synthetic-scope-host" not in preview.text + confirmed.text + repeated.text


@pytest.mark.parametrize("confirmed", [False, None, 1, "true", {}, []])
def test_confirmation_is_a_literal_boolean_and_never_reaches_probe(onboard, confirmed):
    client, svc, _ = onboard
    response = client.post("/api/model-center/local-ai/onboarding/scan", headers=HEADERS,
        json={"scope_digest": "a" * 64, "confirmed": confirmed})
    assert response.status_code == 422
    assert svc.scan is None and svc.client.calls == []


def test_unknown_scope_and_arbitrary_scan_expansion_fields_fail_closed(onboard):
    client, svc, _ = onboard
    root = "/api/model-center/local-ai"
    unknown = client.post(root + "/onboarding/scan", headers=HEADERS,
        json={"scope_digest": "a" * 64, "confirmed": True})
    assert unknown.status_code == 409
    expanded = client.post(root + "/onboarding/scan", headers=HEADERS,
        json={"scope_digest": "a" * 64, "confirmed": True, "path": "/synthetic-unapproved", "endpoint": "http://203.0.113.1:1234"})
    assert expanded.status_code == 422
    assert "synthetic-unapproved" not in expanded.text
    assert svc.scan is None and svc.client.calls == []


def test_common_roots_require_explicit_preview_query_and_do_not_mutate_settings(onboard):
    client, svc, _ = onboard
    root = "/api/model-center/local-ai/onboarding/scan-scope"
    before = dict(svc.settings)
    default = client.get(root, headers=HEADERS)
    assert default.status_code == 200 and default.json()["include_common_model_dirs"] is False
    assert client.get(root + "?include_common_model_dirs=1", headers=HEADERS).status_code == 422
    assert client.get(root + "?include_common_model_dirs=true", headers=HEADERS).json()["include_common_model_dirs"] is True
    assert svc.settings == before and svc.scan is None and svc.client.calls == []


def test_legacy_http_cannot_bypass_v2_scope_consent(onboard):
    client, svc, _ = onboard
    response = client.post("/api/model-center/local-ai/scan", headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["code"] == "LOCAL_AI_SCOPE_CONFIRMATION_REQUIRED"
    assert svc.scan is None and svc.client.calls == []


@pytest.mark.parametrize("acceptance", [False, True])
def test_default_off_and_v1_acceptance_reject_new_onboarding_routes(onboard, monkeypatch, acceptance):
    client, svc, _ = onboard
    if acceptance: monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    else: monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    root = "/api/model-center/local-ai/onboarding"
    assert client.get(root + "/scan-scope", headers=HEADERS).status_code == 404
    assert client.post(root + "/scan", headers=HEADERS,
        json={"scope_digest": "a" * 64, "confirmed": True}).status_code == 404
    assert svc.scan is None and svc.client.calls == []


def test_scope_is_bound_to_the_actual_registered_session_incarnation(onboard):
    client, svc, sessions = onboard
    root = "/api/model-center/local-ai/onboarding"
    preview = client.get(root + "/scan-scope", headers=HEADERS).json()
    original = sessions.resolve("synthetic-scope-host").session
    sessions.revoke("synthetic-scope-host")
    sessions.register("synthetic-scope-host", original)
    response = client.post(root + "/scan", headers=HEADERS,
        json={"scope_digest": preview["scope_digest"], "confirmed": True})
    assert response.status_code == 409
    assert response.json()["code"] == "LOCAL_AI_SCOPE_PRINCIPAL_MISMATCH"
    assert svc.scan is None and svc.client.calls == []


@pytest.mark.parametrize("scope_digest", ["", "a" * 63, "a" * 65, "A" * 64, "a" * 64 + "\n", True, 1])
def test_scope_digest_is_an_exact_closed_64_character_receipt(onboard, scope_digest):
    client, svc, _ = onboard
    response = client.post("/api/model-center/local-ai/onboarding/scan", headers=HEADERS,
        json={"scope_digest": scope_digest, "confirmed": True})
    assert response.status_code == 422
    assert svc.scan is None and svc.client.calls == []


def test_revocation_after_config_temp_write_prevents_original_owner_commit(onboard, monkeypatch):
    import app.model_center.discovery as discovery
    client, svc, sessions = onboard
    before_settings = dict(svc.settings)
    before_file = svc.path.read_bytes() if svc.path.exists() else None
    original = discovery.os.fsync
    def revoke_after_flush(fd):
        original(fd)
        sessions.revoke("synthetic-scope-host")
    monkeypatch.setattr(discovery.os, "fsync", revoke_after_flush)
    response = client.put("/api/model-center/local-ai/settings", headers=HEADERS,
        json={"scan_roots": [], "include_common_model_dirs": False})
    assert response.status_code == 401
    assert svc.settings == before_settings
    assert (svc.path.read_bytes() if svc.path.exists() else None) == before_file
    assert not list(svc.path.parent.glob(".discovery-*.tmp"))


def test_revocation_during_validation_rejects_late_provider_metadata_adoption(onboard, monkeypatch):
    client, svc, sessions = onboard
    candidate = scan(svc)["candidates"][0]
    original = svc.client.json
    def late_metadata(*args, **kwargs):
        result = original(*args, **kwargs)
        sessions.revoke("synthetic-scope-host")
        return result
    monkeypatch.setattr(svc.client, "json", late_metadata)
    response = client.post("/api/model-center/local-ai/candidates/" + candidate["id"] + "/validate", headers=HEADERS)
    assert response.status_code == 401
    assert "synthetic-scope-host" not in response.text
    assert svc.get_scan(svc.scan["id"])["candidates"][0] == candidate
    assert not svc.registrations
