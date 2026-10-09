"""Owned browser-test host: original File/API/UI, synthetic discovery adapters.

This module is never imported by the product. It does not contact model ports,
read installed models, collect real hardware, launch programs or run inference.
The original discovery service, authority, consent and worker remain in use.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
from fastapi import HTTPException, Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURE_TOKEN = "synthetic-m3-browser-existing-host"
FIXTURE_ACTOR = "synthetic-m3-browser-author"
SECOND_FIXTURE_TOKEN = "synthetic-m3-browser-second-host"
SECOND_FIXTURE_ACTOR = "synthetic-m3-browser-author-second"
LABEL = "ORIGINAL_FILE_HTTP_UI_WITH_SYNTHETIC_DISCOVERY_ADAPTER"


class SyntheticDiscoveryFixture:
    """Closed metadata-only adapter; there is deliberately no HTTP transport."""
    timeout = 0.2
    payloads = {
        ("http://127.0.0.1:11434", "/api/tags"): {"models": []},
        ("http://127.0.0.1:11434", "/api/version"): {"version": "synthetic-fixture"},
        ("http://127.0.0.1:8188", "/system_stats"): {"system": {"comfyui_version": "synthetic-fixture"}},
        ("http://127.0.0.1:8188", "/object_info"): {},
        ("http://127.0.0.1:7860", "/sdapi/v1/sd-models"): [{"title": "synthetic-consent-fixture.ckpt", "sha256": "a" * 64}],
        ("http://127.0.0.1:1234", "/v1/models"): {"data": []},
        ("http://127.0.0.1:8080", "/v1/models"): {"data": []},
    }

    def __init__(self, directory: Path, delay_seconds=1.25):
        self.directory = directory.resolve()
        self.common = self.directory / "synthetic-common-models"
        self.common.mkdir(parents=True, exist_ok=False)
        self.delay_seconds = delay_seconds
        self.lock = threading.RLock()
        self.calls, self.blocked = [], []
        self.hardware_calls = self.launch_attempts = 0
        self.metadata_fixtures = []

    def json(self, endpoint, path, *, body=None):
        with self.lock:
            if body is not None or (endpoint, path) not in self.payloads:
                self.blocked.append("UNAPPROVED_PROBE")
                raise AssertionError("SYNTHETIC_FIXTURE_UNAPPROVED_PROBE")
            self.calls.append({"endpoint": endpoint, "path": path, "method": "GET", "body": None})
            return copy.deepcopy(self.payloads[(endpoint, path)])

    def hardware(self):
        with self.lock:
            self.hardware_calls += 1
        # Keep one real worker poll observable without probing or loading a model.
        time.sleep(self.delay_seconds)
        unknown = {"status": "NOT_RUN", "source": "SYNTHETIC_FIXTURE", "inference_verified": False}
        return {"platform": "SYNTHETIC_BROWSER_FIXTURE", "architecture": "SYNTHETIC", "cpu": "Synthetic consent fixture CPU",
                "logical_cpu_count": 4, "ram_bytes": 16 * 1024 ** 3, "gpus": [], "status": "NOT_VERIFIED",
                "notes": ["SYNTHETIC_FIXTURE_NOT_REAL_HARDWARE"], "cuda": dict(unknown), "directml": dict(unknown)}

    def require_path(self, path):
        # Only this newly created owned directory can enter an inventory plan.
        value = Path(path).resolve()
        if value != self.common:
            with self.lock:
                self.blocked.append("UNAPPROVED_FILESYSTEM_TARGET")
            raise AssertionError("SYNTHETIC_FIXTURE_UNAPPROVED_FILESYSTEM_TARGET")
        return value

    def forbid_launch(self, *args, **kwargs):
        with self.lock:
            self.launch_attempts += 1
        raise AssertionError("SYNTHETIC_FIXTURE_PROGRAM_LAUNCH_FORBIDDEN")

    def seed_model_metadata(self, discovery, guard):
        """Explicit test action: three fixed metadata files, no executable/model payload."""
        def string(value):
            raw = value.encode("utf-8")
            return struct.pack("<Q", len(raw)) + raw
        tensor_header = json.dumps({"empty": {"dtype": "F32", "shape": [0], "data_offsets": [0, 0]}}).encode()
        payloads = {
            # The original bounded checker requires a positive declared tensor
            # count. This header fixture has no tensor payload and cannot infer.
            "synthetic-metadata.gguf": b"GGUF" + struct.pack("<IQQ", 3, 1, 1)
                + string("general.architecture") + struct.pack("<I", 8) + string("qwen3"),
            "synthetic-metadata.safetensors": struct.pack("<Q", len(tensor_header)) + tensor_header,
            "model_index.json": json.dumps({"_class_name": "SyntheticMetadataPipeline"}).encode(),
        }
        with self.lock, discovery.lock:
            guard()
            self.require_path(self.common)
            if discovery.scan and discovery.scan["status"] == "RUNNING":
                raise ValueError("SYNTHETIC_FIXTURE_SCAN_ACTIVE")
            if self.metadata_fixtures or any((self.common / name).exists() for name in payloads):
                raise ValueError("SYNTHETIC_FIXTURE_METADATA_ALREADY_EXISTS")
            for name, payload in payloads.items():
                guard()
                with (self.common / name).open("xb") as handle:
                    handle.write(payload)
                self.metadata_fixtures.append({"name": name, "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest()})
            return copy.deepcopy(self.metadata_fixtures)

    def install(self, discovery):
        # Reuse the mounted product owner; do not construct a replacement registry.
        with discovery.lock:
            if discovery.scan or discovery.registrations:
                raise AssertionError("SYNTHETIC_FIXTURE_REQUIRES_EMPTY_DISCOVERY")
            discovery.settings = {"scan_roots": [], "runtimes": [], "include_common_model_dirs": False}
            discovery.configured_runtime_sources = []
            discovery.client, discovery.hardware_probe = self, self.hardware
            discovery.center.runtimes.clear()
            discovery.center.models.clear()
            discovery.center.pipelines.clear()
            discovery.center.lifecycle.start = self.forbid_launch

    def receipt(self, discovery):
        with self.lock, discovery.lock:
            return {"fixture": LABEL, "synthetic": True, "probe_calls": copy.deepcopy(self.calls),
                    "hardware_calls": self.hardware_calls, "launch_attempts": self.launch_attempts,
                    "blocked_attempts": list(self.blocked), "registrations": len(discovery.registrations),
                    "enabled_registrations": sum(bool(row.get("enabled")) for row in discovery.registrations.values()),
                    "scan_id": discovery.scan["id"] if discovery.scan else None,
                    "scan_status": discovery.scan["status"] if discovery.scan else None,
                    "synthetic_metadata_fixtures": copy.deepcopy(self.metadata_fixtures),
                    "inference_status": "NOT_RUN", "windows_acceptance": "NOT_RUN", "model_weights_loaded": False}


def model_mutation_forbidden(path, method):
    if path.startswith("/api/v1/"): path = "/api/" + path[len("/api/v1/"):]
    if not path.startswith("/api/model-center/") or method in {"GET", "HEAD", "OPTIONS"}:
        return False
    return not (path in {"/api/model-center/local-ai/scan", "/api/model-center/local-ai/onboarding/scan"}
                or (path.startswith("/api/model-center/local-ai/scan/") and path.endswith("/cancel")))


def application(root: Path, *, delay_seconds=1.25):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "owned-synthetic-discovery-fixture.json"
    # Never overwrite, clear or reuse an earlier process's fixture or user data.
    with marker.open("x", encoding="utf-8") as handle:
        json.dump({"fixture": LABEL, "process": os.getpid()}, handle)
    expected_data = root / "novel-data"
    if Path(os.environ.get("NOVEL_DATA_PATH", "")).resolve() != expected_data:
        raise AssertionError("SYNTHETIC_FIXTURE_REQUIRES_OWNED_FILE_ROOT")
    if expected_data.exists() and any(expected_data.iterdir()):
        raise AssertionError("SYNTHETIC_FIXTURE_REQUIRES_EMPTY_FILE_ROOT")
    from app import main
    from app.actor_context import SessionContext
    from app.model_center import discovery_environment, discovery_scope
    if main.settings.storage_backend != "file" or main.settings.enable_collaboration_runtime or main.settings.enable_packaged_runtime:
        raise AssertionError("SYNTHETIC_FIXTURE_REQUIRES_LOCAL_FILE_MODE")
    fixture = SyntheticDiscoveryFixture(root / "adapter", delay_seconds)
    fixture.install(main.local_ai_discovery)
    main.trusted_session_resolver.register(FIXTURE_TOKEN, SessionContext("synthetic-m3-browser-session", "synthetic-browser", FIXTURE_ACTOR, "synthetic-workspace"))
    main.trusted_session_resolver.register(SECOND_FIXTURE_TOKEN, SessionContext("synthetic-m3-browser-session-second", "synthetic-browser", SECOND_FIXTURE_ACTOR, "synthetic-workspace"))
    original_identity, original_scandir = discovery_scope.path_identity, discovery_environment._scoped_scandir
    discovery_environment.common_model_roots = lambda **_kwargs: [str(fixture.common)]
    def scoped_identity(path, **kwargs):
        fixture.require_path(path)
        return original_identity(path, **kwargs)
    def scoped_scandir(path, cancel=None, **kwargs):
        fixture.require_path(path)
        return original_scandir(path, cancel, **kwargs)
    discovery_scope.path_identity = scoped_identity
    discovery_environment._scoped_scandir = scoped_scandir

    @main.app.middleware("http")
    async def no_model_execution(request, call_next):
        if model_mutation_forbidden(request.url.path, request.method):
            fixture.blocked.append("UNAPPROVED_MODEL_MUTATION")
            from fastapi.responses import JSONResponse
            return JSONResponse({"code": "SYNTHETIC_FIXTURE_MODEL_MUTATION_FORBIDDEN"}, status_code=409)
        return await call_next(request)

    @main.app.get("/api/__tests__/v2-discovery-fixture")
    def receipt(request: Request):
        token = request.headers.get("X-Session-Token")
        if token not in {FIXTURE_TOKEN, SECOND_FIXTURE_TOKEN}:
            raise HTTPException(401)
        authority = main._local_discovery_host_authority(request, token)
        authority.guard()
        from fastapi.responses import JSONResponse
        return JSONResponse(fixture.receipt(main.local_ai_discovery), headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})

    @main.app.post("/api/__tests__/v2-discovery-fixture/revoke-current-host")
    async def revoke_current_host(request: Request):
        token = request.headers.get("X-Session-Token")
        if token not in {FIXTURE_TOKEN, SECOND_FIXTURE_TOKEN}:
            raise HTTPException(401)
        authority = main._local_discovery_host_authority(request, token)
        authority.guard()
        try:
            payload = await request.json()
        except ValueError:
            raise HTTPException(422)
        if payload != {"confirmed": True} or type(payload.get("confirmed")) is not bool:
            raise HTTPException(422)
        authority.guard()
        # Only the caller's fixed synthetic test identity can be revoked. No
        # arbitrary credential, user identity or persistent access is accepted.
        main.trusted_session_resolver.revoke(token)
        from fastapi import Response
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @main.app.post("/api/__tests__/v2-discovery-fixture/seed-metadata")
    async def seed_metadata(request: Request):
        if request.headers.get("X-Session-Token") != FIXTURE_TOKEN:
            raise HTTPException(401)
        authority = main._local_discovery_host_authority(request, FIXTURE_TOKEN)
        authority.guard()
        from app.experimental.flags import enabled_flags
        if "narrative_production_v2" not in enabled_flags():
            raise HTTPException(404)
        try:
            payload = await request.json()
        except ValueError:
            raise HTTPException(422)
        if payload != {"fixture": "metadata-only-v1", "confirmed": True} or type(payload.get("confirmed")) is not bool:
            raise HTTPException(422)
        try:
            rows = fixture.seed_model_metadata(main.local_ai_discovery, authority.guard)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        from fastapi.responses import JSONResponse
        return JSONResponse({"synthetic": True, "metadata_fixtures": rows, "model_weights_loaded": False},
            status_code=201, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

    return main.app, fixture


def self_check(app, fixture):
    from fastapi.testclient import TestClient
    from app import main
    headers = {"X-Session-Token": FIXTURE_TOKEN}
    with TestClient(app) as client:
        root = "/api/model-center/local-ai"
        assert client.get('/api/__tests__/v2-discovery-fixture').status_code == 401
        private_receipt = client.get('/api/__tests__/v2-discovery-fixture', headers=headers)
        assert private_receipt.status_code == 200 and private_receipt.headers['Cache-Control'] == 'no-store'
        preview = client.get(root + "/onboarding/scan-scope?include_common_model_dirs=false", headers=headers)
        from app.experimental.flags import enabled_flags
        if 'narrative_production_v2' not in enabled_flags():
            assert preview.status_code == 404, preview.text
            assert client.post(root + '/onboarding/scan', headers=headers,
                              json={'scope_digest': 'a' * 64, 'confirmed': True}).status_code == 404
            result = fixture.receipt(main.local_ai_discovery)
            assert result['hardware_calls'] == 0 and result['probe_calls'] == [] and result['scan_id'] is None
            print(json.dumps(result, sort_keys=True))
            return
        assert preview.status_code == 200, preview.text
        assert not preview.json()["roots"] and not preview.json()["metadata_inspections"]
        assert fixture.receipt(main.local_ai_discovery)["probe_calls"] == []
        assert client.post(root + "/scan", headers=headers).status_code == 409
        response = client.post(root + "/onboarding/scan", headers=headers, json={"scope_digest": preview.json()["scope_digest"], "confirmed": True})
        assert response.status_code == 202, response.text
        deadline = time.monotonic() + 5
        while main.local_ai_discovery.get_scan(response.json()["id"])["status"] == "RUNNING" and time.monotonic() < deadline:
            time.sleep(.005)
        report = client.get(root + "/environment", headers=headers)
        assert report.status_code == 200 and report.json()["status"] == "COMPLETED", report.text
        result = fixture.receipt(main.local_ai_discovery)
        assert result["hardware_calls"] == 1 and len(result["probe_calls"]) == 7
        assert not result["registrations"] and not result["launch_attempts"] and not result["blocked_attempts"]
        print(json.dumps(result, sort_keys=True))


def self_check_files(app, fixture):
    from fastapi.testclient import TestClient
    from app import main
    from app.experimental.flags import enabled_flags
    headers = {"X-Session-Token": FIXTURE_TOKEN}
    seed_path = "/api/__tests__/v2-discovery-fixture/seed-metadata"
    payload = {"fixture": "metadata-only-v1", "confirmed": True}
    with TestClient(app) as client:
        assert client.post(seed_path, json=payload).status_code == 401
        if "narrative_production_v2" not in enabled_flags():
            assert client.post(seed_path, headers=headers, json=payload).status_code == 404
            assert not fixture.metadata_fixtures
            print(json.dumps(fixture.receipt(main.local_ai_discovery), sort_keys=True))
            return
        for invalid in ({}, {**payload, "confirmed": 1}, {**payload, "path": "unapproved"}):
            assert client.post(seed_path, headers=headers, json=invalid).status_code == 422
        seeded = client.post(seed_path, headers=headers, json=payload)
        assert seeded.status_code == 201, seeded.text
        assert len(seeded.json()["metadata_fixtures"]) == 3
        assert client.post(seed_path, headers=headers, json=payload).status_code == 409
        root = "/api/model-center/local-ai"
        preview = client.get(root + "/onboarding/scan-scope?include_common_model_dirs=true", headers=headers)
        assert preview.status_code == 200, preview.text
        confirmed = client.post(root + "/onboarding/scan", headers=headers,
            json={"scope_digest": preview.json()["scope_digest"], "confirmed": True})
        assert confirmed.status_code == 202, confirmed.text
        deadline = time.monotonic() + 5
        while main.local_ai_discovery.get_scan(confirmed.json()["id"])["status"] == "RUNNING" and time.monotonic() < deadline:
            time.sleep(.005)
        report = client.get(root + "/environment", headers=headers).json()
        assert report["status"] == "COMPLETED", report
        assert {row["format"] for row in report["model_files"]} == {"GGUF", "SAFETENSORS", "DIFFUSERS"}
        assert all(row["header_valid"] and not row["inference_verified"] for row in report["model_files"])
        assert len(next(row for row in report["model_files"] if row["format"] == "GGUF")["candidate_ids"]) == 1
        result = fixture.receipt(main.local_ai_discovery)
        assert result["hardware_calls"] == 1 and len(result["probe_calls"]) == 7
        assert not result["registrations"] and not result["launch_attempts"] and not result["blocked_attempts"]
        print(json.dumps(result, sort_keys=True))


def self_check_legacy_host(app, fixture):
    from fastapi.testclient import TestClient
    from app import main
    from app.experimental.flags import enabled_flags
    assert "narrative_production_v2" not in enabled_flags()
    first = {"X-Session-Token": FIXTURE_TOKEN}
    second = {"X-Session-Token": SECOND_FIXTURE_TOKEN}
    root = "/api/model-center/local-ai"
    with TestClient(app) as client:
        assert client.get(root).status_code == 401
        assert client.get(root, headers=first).status_code == 200
        assert client.get(root + "/onboarding/scan-scope", headers=first).status_code == 404
        job = client.post(root + "/scan", headers=first, json={})
        assert job.status_code == 202, job.text
        deadline = time.monotonic() + 5
        while main.local_ai_discovery.get_scan(job.json()["id"])["status"] == "RUNNING" and time.monotonic() < deadline:
            time.sleep(.005)
        cached = client.get(root, headers=first).json()
        assert cached["scan"]["status"] == "COMPLETED"
        assert "environment_schema_version" not in cached["scan"]
        revoke = "/api/__tests__/v2-discovery-fixture/revoke-current-host"
        assert client.post(revoke, headers=first, json={"confirmed": 1}).status_code == 422
        assert client.post(revoke, headers=first, json={"confirmed": True, "token": SECOND_FIXTURE_TOKEN}).status_code == 422
        assert client.post(revoke, headers=first, json={"confirmed": True}).status_code == 204
        assert client.get(root, headers=first).status_code == 401
        assert client.post(root + "/scan", headers=first, json={}).status_code == 401
        assert client.get(root, headers=second).json() == cached
        result = fixture.receipt(main.local_ai_discovery)
        assert result["hardware_calls"] == 1 and len(result["probe_calls"]) == 5
        assert not result["registrations"] and not result["launch_attempts"] and not result["blocked_attempts"]
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8027)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--self-check-files", action="store_true")
    parser.add_argument("--self-check-legacy-host", action="store_true")
    args = parser.parse_args()
    root = Path(os.environ["V2_DISCOVERY_FIXTURE_ROOT"])
    app, fixture = application(root, delay_seconds=0 if args.self_check or args.self_check_files or args.self_check_legacy_host else 1.25)
    if args.self_check_legacy_host:
        self_check_legacy_host(app, fixture)
    elif args.self_check_files:
        self_check_files(app, fixture)
    elif args.self_check:
        self_check(app, fixture)
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", proxy_headers=False)
