"""Owned M4 browser host: original File/API/JobManager and exact built-in MockProvider.

Never imported by the product. No model registry seeding, weights, runtime launch,
real provider calls, discovery, installs, or paid APIs belong to this fixture.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TOKEN = "synthetic-m4-browser-existing-host"
ACTOR = "synthetic-m4-browser-author"
LABEL = "ORIGINAL_FILE_HTTP_UI_JOBMANAGER_WITH_BUILTIN_MOCK_ONLY"
FLAGS = "ai_execution_v2,narrative_production_v2,model_broker_v2,author_context_inspector_v2"
PRIVATE = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}


class SyntheticExecutionFixture:
    def __init__(self):
        self.lock = threading.RLock()
        self.mock_calls = 0
        self.metadata_probe_attempts = 0
        self.blocked_attempts = []

    def forbid(self, category):
        def blocked(*_args, **_kwargs):
            with self.lock:
                self.blocked_attempts.append(category)
            raise AssertionError("M4_FIXTURE_FORBIDDEN_" + category)
        return blocked

    def install(self, runtime, discovery, center):
        from app.providers import MockProvider
        from app.model_runtime import LegacyTextProviderAdapter
        provider = runtime.providers["mock"]
        adapter = runtime.provider_registry.resolve("mock")
        assert type(provider) is MockProvider and type(adapter) is LegacyTextProviderAdapter and adapter.provider is provider
        original_stream = provider.stream

        def counted_stream(prompt, model, **kwargs):
            if model != "mock-writer":
                return self.forbid("UNEXPECTED_MOCK_ROUTE")()
            with self.lock:
                self.mock_calls += 1
            yield from original_stream(prompt, model, **kwargs)

        # Preserve the exact registered adapter/provider types and original output.
        provider.stream = counted_stream
        for name, other in runtime.providers.items():
            if other is provider:
                continue
            for method in ("generate", "stream", "health_check", "list_models"):
                if hasattr(other, method):
                    setattr(other, method, self.forbid("REAL_PROVIDER"))
            if hasattr(other, "local_model_metadata"):
                def blocked_metadata(*_args, **_kwargs):
                    # The unchanged NOVEL bootstrap reads /text-models. Its
                    # original catch projects NOT_VERIFIED after this trap.
                    with self.lock:
                        self.metadata_probe_attempts += 1
                    raise AssertionError("M4_FIXTURE_LEGACY_METADATA_READ_BLOCKED")
                other.local_model_metadata = blocked_metadata
        discovery.client.json = self.forbid("DISCOVERY_PROBE")
        discovery.hardware_probe = self.forbid("HARDWARE_PROBE")
        center.lifecycle.start = self.forbid("RUNTIME_LAUNCH")

    def receipt(self):
        with self.lock:
            return {"fixture": LABEL, "synthetic": True, "mock_calls": self.mock_calls,
                    "metadata_probe_attempts": self.metadata_probe_attempts,
                    "blocked_attempts": list(self.blocked_attempts), "quality_verification": "NOT_RUN",
                    "real_inference": "NOT_RUN", "model_weights_loaded": False,
                    "cloud_calls": 0, "automatic_retry": False}


def validate_environment(root):
    root = Path(root).resolve()
    if Path(os.environ.get("V2_AI_EXECUTION_FIXTURE_ROOT", "")).resolve() != root:
        raise AssertionError("M4_FIXTURE_ROOT_REQUIRED")
    if Path(os.environ.get("NOVEL_DATA_PATH", "")).resolve() != root / "novel-data":
        raise AssertionError("M4_FIXTURE_OWNED_FILE_ROOT_REQUIRED")
    for key, folder in (("HOME", "home"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                        ("XDG_CONFIG_HOME", "config"), ("LOCALAPPDATA", "local"), ("TMPDIR", "tmp")):
        if Path(os.environ.get(key, "")).resolve() != root / folder:
            raise AssertionError("M4_FIXTURE_ENVIRONMENT_ISOLATION_REQUIRED")
    required = {"STORAGE_BACKEND": "file", "ENABLE_COLLABORATION_RUNTIME": "false", "ENABLE_PACKAGED_RUNTIME": "false",
                "MOCK_PROVIDER": "true", "ENABLE_CLOUD": "false", "ENABLE_PROVIDER_FALLBACK": "false",
                "CREDENTIAL_VAULT_BACKEND": "memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true",
                "COLLABORATION_DEV_SESSIONS_JSON": "", "V1_ACCEPTANCE_MODE": "false"}
    if any(os.environ.get(key) != value for key, value in required.items()) or set(os.environ.get("EXPERIMENTAL_FEATURES", "").split(",")) != set(FLAGS.split(",")):
        raise AssertionError("M4_FIXTURE_LOCAL_SYNTHETIC_FLAGS_REQUIRED")
    data = root / "novel-data"
    if data.exists() and any(data.iterdir()):
        raise AssertionError("M4_FIXTURE_EMPTY_ROOT_REQUIRED")
    return root


def application(root):
    root = validate_environment(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "owned-synthetic-ai-execution-fixture.json").open("x", encoding="utf-8") as handle:
        json.dump({"fixture": LABEL, "process": os.getpid()}, handle)
    from app import main
    from app.actor_context import SessionContext
    from app.dependencies import runtime
    assert main.settings.storage_backend == "file" and not main.settings.enable_collaboration_runtime and not main.settings.enable_packaged_runtime
    fixture = SyntheticExecutionFixture()
    fixture.install(runtime, main.local_ai_discovery, main.model_center_service)
    main.trusted_session_resolver.register(TOKEN, SessionContext("synthetic-m4-browser-session", "synthetic-m4-browser", ACTOR, "synthetic-m4-workspace"))

    def authority(request):
        token = request.headers.get("X-Session-Token")
        if token != TOKEN:
            raise HTTPException(401)
        value = main._local_discovery_host_authority(request, token)
        value.guard()
        return value

    @main.app.get("/api/__tests__/v2-ai-execution-fixture")
    def receipt(request: Request):
        guard = authority(request)
        result = fixture.receipt()
        guard.guard()
        return JSONResponse(result, headers=PRIVATE)

    @main.app.post("/api/__tests__/v2-ai-execution-fixture/revoke-current-host")
    async def revoke(request: Request):
        guard = authority(request)
        try:
            value = await request.json()
        except ValueError:
            raise HTTPException(422)
        if value != {"confirmed": True} or type(value.get("confirmed")) is not bool:
            raise HTTPException(422)
        guard.guard()
        main.trusted_session_resolver.revoke(TOKEN)
        return Response(status_code=204, headers=PRIVATE)

    return main.app, fixture


def self_check(app, fixture):
    """Mounted original HTTP handlers, File persistence and real worker, no browser."""
    from fastapi.testclient import TestClient
    headers = {"X-Session-Token": TOKEN}
    receipt_path = "/api/__tests__/v2-ai-execution-fixture"
    with TestClient(app) as client:
        def checked(response, status=200):
            assert response.status_code == status, response.text
            return response.json()
        assert client.get(receipt_path).status_code == 401
        assert client.get(receipt_path, headers={"X-Session-Token": "not-the-fixture-host"}).status_code == 401
        assert client.get(receipt_path, headers={**headers, "Origin": "https://untrusted.invalid"}).status_code == 403
        assert checked(client.get(receipt_path, headers=headers))["mock_calls"] == 0
        assert checked(client.get("/api/local-session", headers=headers)) == {"session_mode": "LOCAL_HOST", "actor_id": ACTOR}
        text_models = checked(client.get("/api/text-models"))["items"]
        assert all(not row["available"] for row in text_models if row["provider_id"] == "ollama")
        assert fixture.metadata_probe_attempts == 1 and not fixture.blocked_attempts
        nid = checked(client.post("/api/experimental/projects", json={"title": "M4 owned synthetic self-check"}), 201)["id"]
        base = f"/api/projects/{nid}/studio"
        try:
            capabilities = checked(client.get(base + "/graphs/model-capabilities", headers=headers))
            route = next(row for row in capabilities["routes"] if row["provider_id"] == "mock" and row["model_id"] == "mock-writer")
            assert route["available"] and route["synthetic"] and capabilities["api_provider"]["execution_available"] is False
            graph = checked(client.post(base + "/graphs", headers=headers, json={"request_id": "m4_fixture_graph", "expected_version": 0,
                "definition": {"schema_version": 2, "title": "M4 synthetic only", "nodes": [
                    {"id": "Input", "definition_id": "text_input", "parameters": {"text": "Synthetic author source"}},
                    {"id": "Generate", "definition_id": "text_generate", "parameters": {"instruction": "Propose a draft", "max_output_tokens": 128}},
                    {"id": "Review", "definition_id": "human_review", "parameters": {}}], "edges": [
                    {"id": "Source", "source_node_id": "Input", "source_port": "text", "target_node_id": "Generate", "target_port": "text"},
                    {"id": "Check", "source_node_id": "Generate", "source_port": "draft", "target_node_id": "Review", "target_port": "draft"}]}}), 201)
            graph_path = base + "/graphs/" + graph["id"]
            preflight = checked(client.post(graph_path + "/preflight", headers=headers, json={"expected_version": graph["version"]}))
            run = checked(client.post(graph_path + "/runs", headers=headers, json={"expected_graph_version": graph["version"], "reviewed_preflight_digest": preflight["preflight_digest"], "request_id": "m4_fixture_run"}), 201)
            path = base + "/graph-runs/" + run["id"]
            run = checked(client.post(path + "/execute", headers=headers, json={"expected_version": run["version"]}))
            denied = checked(client.post(path + "/model/preview", headers=headers, json={"expected_version": run["version"], "route_id": route["route_id"], "allow_synthetic": False}))
            assert not denied["model_runtime"]["preview"]["execution_available"]
            run = checked(client.post(path + "/model/preview", headers=headers, json={"expected_version": denied["version"], "route_id": route["route_id"], "allow_synthetic": True}))
            assert run["model_runtime"]["preview"]["execution_available"] and fixture.mock_calls == 0
            payload = {"expected_version": run["version"], "reviewed_preview_digest": run["model_runtime"]["preview"]["preview_digest"]}
            run = checked(client.post(path + "/model/dispatch", headers=headers, json=payload))
            duplicate = checked(client.post(path + "/model/dispatch", headers=headers, json=payload))
            assert duplicate["id"] == run["id"] and duplicate["version"] == run["version"]
            assert duplicate["model_runtime"]["execution"]["job_id"] == run["model_runtime"]["execution"]["job_id"]
            deadline = time.monotonic() + 10
            while not run.get("review") and time.monotonic() < deadline:
                run = checked(client.post(path + "/model/refresh", headers=headers, json={"expected_version": run["version"]}))
                if not run.get("review"):
                    time.sleep(.01)
            assert run["review"]["draft"]["origin"] == "MODEL_PROPOSAL", run
            assert fixture.mock_calls == 1 and not fixture.blocked_attempts
            assert run["model_runtime"]["execution"]["synthetic"] and run["model_called"] and not run["applied"]
            for _ in range(2):
                assert checked(client.get(path, headers=headers)) == run
            review = run["review"]
            run = checked(client.post(path + "/approve", headers=headers, json={"expected_version": run["version"], "node_id": review["node_id"], "reviewed_output_digest": review["output_digest"]}))
            assert run["status"] == "SUCCEEDED" and run["reviewed"] and not run["applied"]
            assert checked(client.get(f"/api/novels/{nid}/chapters")) == []
            # A second admitted run is cancelled without model preview/dispatch.
            cancelled = checked(client.post(graph_path + "/runs", headers=headers, json={"expected_graph_version": graph["version"], "reviewed_preflight_digest": preflight["preflight_digest"], "request_id": "m4_fixture_cancelled"}), 201)
            cancelled = checked(client.post(base + "/graph-runs/" + cancelled["id"] + "/cancel", headers=headers, json={"expected_version": cancelled["version"]}))
            assert cancelled["status"] == "CANCELLED" and fixture.mock_calls == 1
            result = checked(client.get(receipt_path, headers=headers))
            assert client.get(receipt_path, headers=headers).headers["cache-control"] == "no-store"
            revoke = receipt_path + "/revoke-current-host"
            for invalid in ({}, [], {"confirmed": 1}, {"confirmed": True, "token": "other"}):
                assert client.post(revoke, headers=headers, json=invalid).status_code == 422
            assert client.post(revoke, headers=headers, json={"confirmed": True}).status_code == 204
            assert client.get(path, headers=headers).status_code == 401
            assert client.get(receipt_path, headers=headers).status_code == 401
            result.update(mounted_lifecycle="PASS", duplicate_dispatch="SAME_ORIGINAL_JOB", read_replay=False, cancelled_without_call=True, host_revoke="PASS", browser="NOT_RUN")
            print(json.dumps(result, sort_keys=True))
        finally:
            assert client.delete(f"/api/novels/{nid}").status_code == 204


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8030)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    application_instance, fixture = application(Path(os.environ["V2_AI_EXECUTION_FIXTURE_ROOT"]))
    if args.self_check:
        self_check(application_instance, fixture)
    else:
        import uvicorn
        uvicorn.run(application_instance, host="127.0.0.1", port=args.port, log_level="warning", proxy_headers=False)
