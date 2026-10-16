"""Isolated M4-B browser host using the unchanged M4 File/HTTP/Mock owner.

The only injected fault is one failed asset-review metadata operation. Provider
outputs, jobs, archival bytes, graph transitions and authorization stay real.
This test module is never imported by the application.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from v2_ai_execution_browser_server import (
    ACTOR, PRIVATE, TOKEN, application as original_application,
    validate_environment as original_validate_environment,
)

LABEL = "M4B_ORIGINAL_FILE_HTTP_UI_MODEL_CONTRACTS_TEXT_ASSET_WITH_BUILTIN_MOCK_ONLY"
FIXTURE_PATH = "/api/__tests__/v2-model-assets-fixture"
FAULT_BODY = {"confirmed": True, "stage": "review_metadata"}


def validate_environment(root):
    root = original_validate_environment(root)
    if Path(os.environ.get("V2_MODEL_ASSETS_FIXTURE_ROOT", "")).resolve() != root:
        raise AssertionError("M4B_FIXTURE_ROOT_REQUIRED")
    for key, folder in (("USERPROFILE", "home"), ("APPDATA", "local"), ("TEMP", "tmp"), ("TMP", "tmp")):
        if Path(os.environ.get(key, "")).resolve() != root / folder:
            raise AssertionError("M4B_FIXTURE_ENVIRONMENT_ISOLATION_REQUIRED")
    if any(os.environ.get(key) != value for key, value in {
        "FRONTEND_ORIGIN": "http://127.0.0.1:5191", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    }.items()):
        raise AssertionError("M4B_FIXTURE_OWNED_OFFLINE_HOST_REQUIRED")
    return root


class ModelAssetsFixture:
    def __init__(self, original):
        self.original = original
        self.lock = threading.RLock()
        self.asset_ids = set()
        self.asset_actors = {}
        self.create_calls = 0
        self.review_metadata_attempts = 0
        self.review_metadata_faults = 0
        self.fault_armed = False
        self.fault_requested = False
        self.fault_asset_id = None
        self.fault_observed_asset_version = None
        self.fault_observed_asset_state = None

    def arm(self, body):
        if body != FAULT_BODY or type(body.get("confirmed")) is not bool:
            raise HTTPException(422)
        with self.lock:
            if self.fault_requested:
                raise HTTPException(409, "M4B_FIXTURE_FAULT_ALREADY_REQUESTED")
            if len(self.asset_ids) != 1:
                raise HTTPException(409, "M4B_FIXTURE_EXACT_EXISTING_ASSET_REQUIRED")
            self.fault_requested = self.fault_armed = True
            self.fault_asset_id = next(iter(self.asset_ids))

    def install(self, assets):
        original_create, original_review = assets.create_text_result, assets.review_text_result

        def create(*args, **kwargs):
            # Count only real owner success. Do not synthesize or edit its result.
            result = original_create(*args, **kwargs)
            with self.lock:
                self.create_calls += 1
                self.asset_ids.add(result["id"])
                self.asset_actors[result["id"]] = kwargs["owner_actor_id"]
            return result

        def review(asset_id, **kwargs):
            with self.lock:
                self.review_metadata_attempts += 1
                if self.fault_armed and asset_id == self.fault_asset_id and kwargs.get("actor_id") == self.asset_actors.get(asset_id):
                    kwargs["guard"]()
                    saved = assets.get(asset_id, actor_id=kwargs["actor_id"], branch_id=kwargs["branch_id"])
                    self.fault_observed_asset_version = saved["version"]
                    self.fault_observed_asset_state = saved["_text_result_review"]["status"]
                    assert self.fault_observed_asset_version == 1 and self.fault_observed_asset_state == "DRAFT"
                    self.fault_armed = False
                    self.review_metadata_faults += 1
                    # Original WorkflowRun decision has committed; no asset
                    # bytes, provider output or review metadata is fabricated.
                    raise OSError("M4B_TEST_ONLY_REVIEW_METADATA_UNAVAILABLE")
            return original_review(asset_id, **kwargs)

        assets.create_text_result, assets.review_text_result = create, review

    def receipt(self):
        with self.lock:
            return {**self.original.receipt(), "fixture": LABEL,
                "original_fixture": self.original.receipt()["fixture"],
                "create_calls": self.create_calls, "created_asset_ids": sorted(self.asset_ids),
                "review_metadata_attempts": self.review_metadata_attempts,
                "review_metadata_faults": self.review_metadata_faults,
                "fault_armed": self.fault_armed, "fault_asset_id": self.fault_asset_id,
                "fault_observed_asset_version": self.fault_observed_asset_version,
                "fault_observed_asset_state": self.fault_observed_asset_state}


def application(root):
    root = validate_environment(root)
    app, original = original_application(root)
    from app import main
    from app.dependencies import asset_library_service
    fixture = ModelAssetsFixture(original)
    fixture.install(asset_library_service)
    with (root / "owned-synthetic-model-assets-fixture.json").open("x", encoding="utf-8") as handle:
        json.dump({"fixture": LABEL, "process": os.getpid()}, handle)

    def authority(request):
        token = request.headers.get("X-Session-Token")
        if token != TOKEN:
            raise HTTPException(401)
        authority = main._local_discovery_host_authority(request, token)
        authority.guard()
        return authority

    @app.get(FIXTURE_PATH)
    def receipt(request: Request):
        guard = authority(request)
        result = fixture.receipt()
        guard.guard()
        return JSONResponse(result, headers=PRIVATE)

    @app.post(FIXTURE_PATH + "/fail-next-review-metadata")
    async def fail_next_review_metadata(request: Request):
        guard = authority(request)
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422)
        guard.guard()
        fixture.arm(body)
        guard.guard()
        return JSONResponse(fixture.receipt(), headers=PRIVATE)

    return app, fixture


def self_check(app, fixture, wire_receipt=None):
    """Actual mounted File/API/JobManager lifecycle, never a browser claim."""
    from fastapi.testclient import TestClient
    headers = {"X-Session-Token": TOKEN}
    wire = {}
    with TestClient(app, raise_server_exceptions=False) as client:
        def checked(response, status=200):
            assert response.status_code == status, response.text
            return response.json()
        for target in (FIXTURE_PATH, "/api/__tests__/v2-ai-execution-fixture"):
            assert client.get(target).status_code == 401
            assert client.get(target, headers={"X-Session-Token": "other-host"}).status_code == 401
            assert client.get(target, headers={**headers, "Origin": "https://untrusted.invalid"}).status_code == 403
        assert checked(client.get(FIXTURE_PATH, headers=headers))["mock_calls"] == 0
        assert checked(client.get("/api/local-session", headers=headers))["actor_id"] == ACTOR
        nid = checked(client.post("/api/experimental/projects", json={"title": "M4-B isolated archival self-check"}), 201)["id"]
        base = f"/api/projects/{nid}/studio"
        try:
            wire["capabilities"] = capabilities = checked(client.get(base + "/graphs/model-capabilities", headers=headers))
            assert capabilities["result_storage"]["available"]
            route = next(row for row in capabilities["routes"] if row["provider_id"] == "mock" and row["model_id"] == "mock-writer")
            wire["catalog"] = catalog = checked(client.get(base + "/graphs/provider-contracts", headers=headers))
            assert catalog["advisory_only"] and not catalog["dispatch_authorized"] and not catalog["automatic_fallback"]
            assert [row["family"] for row in catalog["providers"]] == ["LOCAL_OLLAMA", "LM_STUDIO", "COMFYUI", "LLAMA_CPP", "API"]
            wire["matches"] = []
            for task in ("TEXT_GENERATION", "IMAGE_GENERATION", "VIDEO_GENERATION"):
                matched = checked(client.post(base + "/graphs/model-match", headers=headers, json={
                    "task_type": task, "preferred_route": route["route_id"], "allow_synthetic": True}))
                wire["matches"].append(matched)
                selected = next(row for row in matched["matches"] if row["route_id"] == route["route_id"])
                assert selected["eligible"] is (task == "TEXT_GENERATION")
                assert not selected["execution_authority"] and not matched["dispatch_authorized"]
                if task != "TEXT_GENERATION":
                    assert "GRAPH_" + task.split("_")[0] + "_EXECUTION_NOT_ENABLED" in selected["reasons"]
            assert fixture.original.mock_calls == 0 and not fixture.original.blocked_attempts
            graph = checked(client.post(base + "/graphs", headers=headers, json={"request_id": "m4b_fixture_graph", "expected_version": 0,
                "definition": {"schema_version": 2, "title": "M4-B synthetic archival", "nodes": [
                    {"id": "Input", "definition_id": "text_input", "parameters": {"text": "M4-B synthetic author source"}},
                    {"id": "Generate", "definition_id": "text_generate", "parameters": {"instruction": "Propose an unapproved draft", "max_output_tokens": 128}},
                    {"id": "Review", "definition_id": "human_review", "parameters": {}}], "edges": [
                    {"id": "Source", "source_node_id": "Input", "source_port": "text", "target_node_id": "Generate", "target_port": "text"},
                    {"id": "Check", "source_node_id": "Generate", "source_port": "draft", "target_node_id": "Review", "target_port": "draft"}]}}), 201)
            graph_path = base + "/graphs/" + graph["id"]
            preflight = checked(client.post(graph_path + "/preflight", headers=headers, json={"expected_version": graph["version"]}))
            run = checked(client.post(graph_path + "/runs", headers=headers, json={"expected_graph_version": graph["version"],
                "reviewed_preflight_digest": preflight["preflight_digest"], "request_id": "m4b_fixture_run"}), 201)
            path = base + "/graph-runs/" + run["id"]
            run = checked(client.post(path + "/execute", headers=headers, json={"expected_version": run["version"]}))
            run = checked(client.post(path + "/model/preview", headers=headers, json={"expected_version": run["version"],
                "route_id": route["route_id"], "allow_synthetic": True}))
            assert fixture.original.mock_calls == 0
            payload = {"expected_version": run["version"], "reviewed_preview_digest": run["model_runtime"]["preview"]["preview_digest"], "archive_result": True}
            wire["dispatch_input"] = payload
            wire["dispatched"] = dispatched = checked(client.post(path + "/model/dispatch", headers=headers, json=payload))
            assert dispatched["asset_output"]["state"] == "PENDING"
            deadline = time.monotonic() + 10
            run = dispatched
            while not run.get("review") and time.monotonic() < deadline:
                run = checked(client.get(path, headers=headers))
                if not run.get("review"):
                    time.sleep(.01)
            wire["draft"] = deepcopy(run)
            assert run["asset_output"]["state"] == "DRAFT" and run["asset_output"]["version"] == 1
            assert run["review"]["draft"]["origin"] == "MODEL_PROPOSAL" and not run["applied"]
            assert fixture.original.mock_calls == 1 and fixture.create_calls == 1
            for _ in range(3):
                assert checked(client.get(path, headers=headers)) == run
            assert checked(client.post(path + "/model/refresh", headers=headers, json={"expected_version": run["version"]})) == run
            assert checked(client.get(base + "/assets", headers=headers))["items"] == []
            fault_path = FIXTURE_PATH + "/fail-next-review-metadata"
            for invalid in ({}, [], {"confirmed": 1, "stage": "review_metadata"}, {**FAULT_BODY, "output": "fake"}):
                assert client.post(fault_path, headers=headers, json=invalid).status_code == 422
            assert client.post(fault_path, json=FAULT_BODY).status_code == 401
            assert client.post(fault_path, headers={**headers, "Origin": "https://untrusted.invalid"}, json=FAULT_BODY).status_code == 403
            checked(client.post(fault_path, headers=headers, json=FAULT_BODY))
            assert client.post(fault_path, headers=headers, json=FAULT_BODY).status_code == 409
            review = run["review"]
            failed = client.post(path + "/approve", headers=headers, json={"expected_version": run["version"],
                "node_id": review["node_id"], "reviewed_output_digest": review["output_digest"]})
            assert failed.status_code == 500 and "M4B_TEST_ONLY" not in failed.text, (failed.status_code, failed.text)
            wire["fault_http_status"] = failed.status_code
            wire["recovered"] = recovered = checked(client.get(path, headers=headers))
            assert recovered["status"] == "SUCCEEDED" and recovered["reviewed"] and not recovered["applied"]
            assert recovered["asset_output"]["asset_id"] == run["asset_output"]["asset_id"]
            assert recovered["asset_output"]["state"] == "APPROVED" and recovered["asset_output"]["version"] == 2
            for _ in range(3):
                assert checked(client.get(path, headers=headers)) == recovered
            assert checked(client.get(f"/api/novels/{nid}/chapters")) == []
            final = checked(client.get(FIXTURE_PATH, headers=headers))
            assert final["mock_calls"] == final["create_calls"] == final["review_metadata_faults"] == 1
            assert final["created_asset_ids"] == [run["asset_output"]["asset_id"]] and not final["fault_armed"]
            assert final["blocked_attempts"] == [] and final["real_inference"] == "NOT_RUN"
            assert final["fault_observed_asset_version"] == 1 and final["fault_observed_asset_state"] == "DRAFT"
            assert client.get(FIXTURE_PATH, headers=headers).headers["cache-control"] == "no-store"
            wire["fixture"] = final
            revoke = "/api/__tests__/v2-ai-execution-fixture/revoke-current-host"
            assert client.post(revoke, headers=headers, json={"confirmed": True}).status_code == 204
            assert client.get(path, headers=headers).status_code == 401
            assert client.get(FIXTURE_PATH, headers=headers).status_code == 401
            assert client.post(fault_path, headers=headers, json=FAULT_BODY).status_code == 401
            result = {**final, "mounted_lifecycle": "PASS", "advisory_no_model_call": True,
                "draft_asset_version": 1, "approved_asset_version": 2, "same_asset_recovered": True,
                "identical_read_no_duplicate": True, "review_metadata_recovery": "ORIGINAL_GET",
                "no_chapters": True, "host_revoke": "PASS", "browser": "NOT_RUN"}
            if wire_receipt:
                Path(wire_receipt).write_text(json.dumps(wire, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, sort_keys=True))
        finally:
            assert client.delete(f"/api/novels/{nid}").status_code == 204


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8031)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--wire-receipt", type=Path)
    args = parser.parse_args()
    app, fixture = application(Path(os.environ["V2_MODEL_ASSETS_FIXTURE_ROOT"]))
    if args.self_check:
        self_check(app, fixture, args.wire_receipt)
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", proxy_headers=False)
