"""Opt-in, owned CPU acceptance through the original mounted Studio APIs.

No downloads, credentials, external-service startup or mock provider. Supply
already verified local llama.cpp/GGUF paths and an unused output directory.
This is operational acceptance, not an automatic CI/pytest model dependency.
All generated data is retained; only the child runtime we own is stopped.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
FLAGS = "ai_execution_v2,narrative_production_v2,model_broker_v2,author_context_inspector_v2"
ALIAS = "studio-owned-cpu-text-check"
ACTOR = "owned-cpu-acceptance-host"
TOKEN = "owned-isolated-acceptance-session-not-a-user-credential"
INHERITED_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT")
OWNED_ENV_FOLDERS = ("home", "data", "cache", "config", "local", "tmp")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validated_inputs(server, model, expected_sha, port):
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise ValueError("EXPLICIT_MODEL_SHA256_REQUIRED")
    for path in (server, model):
        if not path.is_absolute() or not path.is_file() or path.is_symlink():
            raise ValueError("VERIFIED_ABSOLUTE_INPUT_FILE_REQUIRED")
        if any(parent.is_symlink() for parent in path.parents):
            raise ValueError("LINKED_INPUT_PATH_REJECTED")
    if not os.access(server, os.X_OK):
        raise ValueError("VERIFIED_EXECUTABLE_REQUIRED")
    if not 1024 <= port <= 65535:
        raise ValueError("UNPRIVILEGED_LOOPBACK_PORT_REQUIRED")
    if sha256_file(model) != expected_sha:
        raise ValueError("MODEL_SHA256_MISMATCH")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError("OWNED_PORT_ALREADY_IN_USE")


def required_child_environment(root):
    return {"HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
        "XDG_DATA_HOME": str(root / "data"), "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_CONFIG_HOME": str(root / "config"), "APPDATA": str(root / "local"),
        "LOCALAPPDATA": str(root / "local"), "TMPDIR": str(root / "tmp"),
        "PROJECT_ROOT": str(REPO), "NOVEL_DATA_PATH": str(root / "novel-data"),
        "STORAGE_BACKEND": "file", "ENABLE_COLLABORATION_RUNTIME": "false",
        "ENABLE_PACKAGED_RUNTIME": "false", "MOCK_PROVIDER": "false",
        "ENABLE_CLOUD": "false", "ENABLE_PROVIDER_FALLBACK": "false",
        "CREDENTIAL_VAULT_BACKEND": "memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true",
        "COLLABORATION_DEV_SESSIONS_JSON": "", "V1_ACCEPTANCE_MODE": "false",
        "EXPERIMENTAL_FEATURES": FLAGS, "CREATION_PROFILE": "LOCAL_ONLY",
        "FRONTEND_ORIGIN": "http://127.0.0.1:5190", "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "PYTHONUNBUFFERED": "1",
        "V2_REAL_TEXT_CHECK_ROOT": str(root)}


def isolated_environment(root):
    # Allowlist, never copy the caller's credentials, proxies or provider config.
    env = {key: os.environ[key] for key in INHERITED_ENV_KEYS if key in os.environ}
    for folder in OWNED_ENV_FOLDERS:
        (root / folder).mkdir()
    env.update(required_child_environment(root))
    return env


def validate_isolated_environment(root):
    # Ownership metadata is an isolation guard, not user authentication.
    required = required_child_environment(root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("OWNED_CHILD_WORKSPACE_REQUIRED")
    if any(os.environ.get(key) != value for key, value in required.items()):
        raise ValueError("ISOLATED_CHILD_ENVIRONMENT_REQUIRED")
    if set(os.environ) - set(required) - set(INHERITED_ENV_KEYS):
        raise ValueError("UNEXPECTED_CHILD_ENVIRONMENT")
    if any(not (root / folder).is_dir() or (root / folder).is_symlink() for folder in OWNED_ENV_FOLDERS):
        raise ValueError("OWNED_CHILD_DIRECTORIES_REQUIRED")


def runtime_argv(server, model, port):
    return [str(server), "-m", str(model), "--alias", ALIAS, "--host", "127.0.0.1",
        "--port", str(port), "--device", "none", "--n-gpu-layers", "0", "--ctx-size", "2048",
        "--parallel", "1", "--threads", "2", "--threads-batch", "2", "--batch-size", "128",
        "--ubatch-size", "128", "--cache-ram", "0", "--offline", "--no-ui", "--no-agent",
        "--no-ui-mcp-proxy", "--cors-origins", f"http://127.0.0.1:{port}", "--no-cors-credentials"]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def source_identity():
    from scripts.run_v2_checks import source_snapshot
    files = source_snapshot(REPO)
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
            "input_files": files, "sha256": digest}


def native_json(endpoint, path):
    # No proxy environment is present in the isolated child, and never redirect.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open(endpoint + path, timeout=2) as response:
        data = response.read(256_001)
    if len(data) > 256_000:
        raise ValueError("NATIVE_METADATA_TOO_LARGE")
    return json.loads(data)


def mounted_acceptance(root, server, model, port, outcome):
    sys.path.insert(0, str(REPO))
    from fastapi.testclient import TestClient
    from app import main
    from app.actor_context import SessionContext
    from app.dependencies import asset_library_service
    from app.experimental.api import independent_workspace_service
    from app.jobs import jobs
    assert not main.settings.mock_provider and not main.settings.enable_cloud and not main.settings.enable_fallback
    assert main.settings.storage_backend == "file" and main.settings.data_path() == root / "novel-data"
    # Original injected host-session seam, only in this disposable test process.
    # It is test authority, not a real user's sign-in or a model mock.
    main.trusted_session_resolver.register(TOKEN, SessionContext("owned-cpu-acceptance-session", "owned-cpu-acceptance", ACTOR, "owned-cpu-workspace"))
    headers = {"X-Session-Token": TOKEN}
    evidence = []
    with TestClient(main.app) as client:
        def api(method, path, payload=None, status=200):
            started = time.monotonic()
            response = client.request(method, path, headers=headers, **({"json": payload} if payload is not None else {}))
            value = response.json() if response.content else None
            evidence.append({"method": method, "path": path, "request": payload, "status": response.status_code,
                "elapsed_seconds": round(time.monotonic() - started, 6), "response": value})
            write_json(root / "api-transcript.json", evidence)
            assert response.status_code == status, (path, response.status_code, value)
            return value

        discovery = "/api/model-center/local-ai"
        assert client.get(discovery).status_code == 401
        assert api("GET", "/api/local-session")["actor_id"] == ACTOR
        api("PUT", discovery + "/settings", {"scan_roots": [], "include_common_model_dirs": False})
        configured = api("POST", discovery + "/runtimes", {"name": "Owned CPU acceptance", "type": "LLAMA_CPP",
            "endpoint": f"http://127.0.0.1:{port}", "model_id": ALIAS, "modality": "TEXT", "health_endpoint": "/v1/models",
            "credential_required": False, "management": "EXTERNAL", "executable": str(server), "model_path": str(model),
            "context_size": 2048, "gpu_layers": 0, "threads": 2, "batch_size": 128})
        scope = api("GET", discovery + "/onboarding/scan-scope?include_common_model_dirs=false")
        scan = api("POST", discovery + "/onboarding/scan", {"scope_digest": scope["scope_digest"], "confirmed": True}, 202)
        deadline = time.monotonic() + 50
        while scan["status"] == "RUNNING" and time.monotonic() < deadline:
            time.sleep(.2)
            scan = api("GET", discovery + "/scan/" + scan["id"])
        # Other optional local runtimes can be absent. Their explicit PARTIAL
        # report remains intact; this acceptance requires our exact runtime.
        assert scan["status"] in {"COMPLETED", "PARTIAL"}, scan
        assert any(row["id"] == configured["id"] and row["status"] == "RUNNING" for row in scan["runtimes"])
        assert not any(error.get("runtime_id") == configured["id"] for error in scan["errors"])
        candidate = next(item for item in scan["candidates"] if item["runtime_id"] == configured["id"] and item["local_path"] == str(model))
        cid = candidate["id"]
        api("POST", discovery + f"/candidates/{cid}/validate")
        api("POST", discovery + f"/candidates/{cid}/register")
        api("PUT", discovery + f"/registrations/{cid}", {"workflow_adapter_id": "", "license_confirmed": True})
        registration = api("POST", discovery + f"/registrations/{cid}/enable", {"confirmed": True})
        assert registration["enabled"] and registration["local"] is True

        nid = api("POST", "/api/experimental/projects", {"title": "Owned real CPU TextNode acceptance"}, 201)["id"]
        base = f"/api/projects/{nid}/studio"
        broker_path = f"/api/novels/{nid}/experimental/model-broker"
        broker = api("GET", broker_path + "/status")
        priced_route = next(row for row in broker["candidates"] if row["provider_id"] == registration["provider_id"])
        assert priced_route["available"] and not priced_route["cloud"] and not priced_route["synthetic"]
        stamp = datetime.now(timezone.utc)
        # Explicit original price receipt, scoped to this owned invocation.
        # This states provider invoicing only, not free electricity/hardware.
        api("PUT", broker_path + "/price", {"route_id": priced_route["route_id"],
            "route_fingerprint": priced_route["fingerprint"], "currency": "USD", "reserve_microusd": 0,
            "input_per_million_microusd": 0, "output_per_million_microusd": 0,
            "source": "Owned offline CPU acceptance: no provider invoice; excludes electricity and hardware",
            "as_of": stamp.isoformat(), "expires_at": (stamp + timedelta(minutes=30)).isoformat(),
            "applicability": "per_request", "expected_version": 0})
        capabilities = api("GET", base + "/graphs/model-capabilities")
        routes = [route for route in capabilities["routes"] if route["available"] and not route["synthetic"]]
        assert len(routes) == 1, capabilities
        route = routes[0]
        match = api("POST", base + "/graphs/model-match", {"task_type": "TEXT_GENERATION", "preferred_route": route["route_id"],
            "local_only": True, "allow_synthetic": False})
        assert any(row["route_id"] == route["route_id"] and row["eligible"] for row in match["matches"]), match
        graph = api("POST", base + "/graphs", {"request_id": "owned_real_cpu_graph", "expected_version": 0,
            "definition": {"schema_version": 2, "title": "Real CPU draft, explicit human review", "nodes": [
                {"id": "Input", "definition_id": "text_input", "parameters": {"text": "A paper boat floats on a quiet pond."}},
                {"id": "Generate", "definition_id": "text_generate", "parameters": {"instruction": "Write one short English sentence about the paper boat. No explanation.", "max_output_tokens": 128}},
                {"id": "Review", "definition_id": "human_review", "parameters": {}}], "edges": [
                {"id": "Source", "source_node_id": "Input", "source_port": "text", "target_node_id": "Generate", "target_port": "text"},
                {"id": "Check", "source_node_id": "Generate", "source_port": "draft", "target_node_id": "Review", "target_port": "draft"}]}}, 201)
        graph_path = base + "/graphs/" + graph["id"]
        preflight = api("POST", graph_path + "/preflight", {"expected_version": graph["version"]})
        run = api("POST", graph_path + "/runs", {"expected_graph_version": graph["version"],
            "reviewed_preflight_digest": preflight["preflight_digest"], "request_id": "owned_real_cpu_run"}, 201)
        path = base + "/graph-runs/" + run["id"]
        run = api("POST", path + "/execute", {"expected_version": run["version"]})
        run = api("POST", path + "/model/preview", {"expected_version": run["version"], "route_id": route["route_id"], "allow_synthetic": False})
        assert run["model_runtime"]["preview"]["execution_available"], run
        payload = {"expected_version": run["version"], "reviewed_preview_digest": run["model_runtime"]["preview"]["preview_digest"], "archive_result": True}
        started = time.monotonic()
        outcome["real_inference"] = "DISPATCH_ATTEMPTED_OUTCOME_UNCONFIRMED"
        run = api("POST", path + "/model/dispatch", payload)
        duplicate = api("POST", path + "/model/dispatch", payload)
        job_id = run["model_runtime"]["execution"]["job_id"]
        assert duplicate["model_runtime"]["execution"]["job_id"] == job_id
        deadline = started + 180  # Existing product deadline, never extended.
        while not run.get("review") and time.monotonic() < deadline:
            time.sleep(.2)
            run = api("GET", path)
            if run.get("model_runtime", {}).get("execution", {}).get("status") in {"FAILED", "CANCELLED"}:
                raise AssertionError(run)
        assert run.get("review"), run
        elapsed = time.monotonic() - started
        assert elapsed < 180
        job = jobs.get(job_id)
        write_json(root / "original-job.json", job.public())
        assert job.execution_mode == "real" and job.status == "COMPLETED" and job.output.strip()
        outcome["real_inference"] = "PASS"
        assert job.terminal_hook_status == "COMPLETED" and len(jobs.jobs) == 1
        assert run["model_runtime"]["execution"]["synthetic"] is False and not run["applied"]
        draft = run["asset_output"]
        assert draft["state"] == "DRAFT" and draft["version"] == 1
        receipt = draft["execution_receipt"]
        assert receipt["execution_mode"] == "real" and receipt["quality_verification"] == "NOT_RUN"
        assert receipt["prompt_sha256"] == hashlib.sha256(receipt["prompt"].encode()).hexdigest()
        # The File project owner is the original local-author context, distinct
        # from the injected host session. Generic asset routes correctly hide
        # private proposals. Inspect bytes through the original owner's scope.
        assert client.get(base + "/assets/" + draft["asset_id"], headers=headers).status_code == 404
        with independent_workspace_service._asset_scope(nid, job.scope):
            asset = asset_library_service.get(draft["asset_id"], actor_id=job.actor_id)
            assert "_text_execution_receipt" not in asset_library_service.public(asset)
            content = asset_library_service.content(draft["asset_id"], actor_id=job.actor_id)
        assert content == job.output.encode()
        (root / "actual-model-output.txt").write_bytes(content)
        write_json(root / "draft-asset.json", draft)
        for _ in range(2):
            repeated = api("GET", path)
            assert repeated["asset_output"] == draft
        review = run["review"]
        run = api("POST", path + "/approve", {"expected_version": run["version"], "node_id": review["node_id"], "reviewed_output_digest": review["output_digest"]})
        approved = run["asset_output"]
        assert approved["asset_id"] == draft["asset_id"] and approved["version"] == 2 and approved["state"] == "APPROVED"
        assert approved["execution_receipt"] == receipt and run["status"] == "SUCCEEDED" and not run["applied"]
        assert api("GET", f"/api/novels/{nid}/chapters") == []
        with independent_workspace_service._asset_scope(nid, job.scope):
            assert len(asset_library_service.list(nid, actor_id=job.actor_id)) == 1
        assert len(jobs.jobs) == 1
        write_json(root / "approved-asset.json", approved)
        main.trusted_session_resolver.revoke(TOKEN)
        assert client.get(path, headers=headers).status_code == 401
        return {"project_id": nid, "graph_id": graph["id"], "run_id": run["id"], "job_id": job_id,
            "asset_id": draft["asset_id"], "asset_versions": [1, 2], "dispatch_to_draft_seconds": elapsed,
            "execution_mode": "real", "route": route, "duplicate_dispatch": "SAME_ORIGINAL_JOB",
            "read_replay": False, "host_revoke": "PASS", "manuscript_changed": False, "quality_verification": "NOT_RUN",
            "browser": "NOT_RUN", "authority": "ORIGINAL_INJECTED_TEST_HOST_SESSION", "project_actor": job.actor_id,
            "asset_bytes_verification": "ORIGINAL_ASSET_OWNER_SCOPE", "project_data_retained": True}


def execute(root, server, model, expected_sha, port):
    validated_inputs(server, model, expected_sha, port)
    before = source_identity()
    write_json(root / "source-before.json", before)
    receipt = {"status": "STARTING", "started_utc": datetime.now(timezone.utc).isoformat(), "model_sha256": expected_sha,
        "server_sha256": sha256_file(server), "argv": runtime_argv(server, model, port), "real_inference": "NOT_RUN",
        "paid_api": False, "gpu": False, "private_credentials_used": False, "automatic_model_download": False}
    endpoint = f"http://127.0.0.1:{port}"
    process = None
    started = time.monotonic()
    def terminate_owned_check(_signal, _frame):
        raise TimeoutError("OWNED_ACCEPTANCE_CANCELLED")
    signal.signal(signal.SIGTERM, terminate_owned_check)
    try:
        version = subprocess.run([str(server), "--version"], capture_output=True, text=True, timeout=10, check=True)
        receipt["runtime_version_output"] = version.stdout + version.stderr
        with (root / "native-runtime.log").open("wb") as log:
            process = subprocess.Popen(receipt["argv"], stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("OWNED_RUNTIME_EXITED_BEFORE_READINESS")
                try:
                    if native_json(endpoint, "/health").get("status") == "ok":
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(.2)
            else:
                raise TimeoutError("OWNED_RUNTIME_READINESS_TIMEOUT")
            receipt["ready_seconds"] = time.monotonic() - started
            for path, name in (("/props", "props"), ("/v1/models", "models")):
                write_json(root / ("native-" + name + ".json"), native_json(endpoint, path))
            receipt["mounted_acceptance"] = mounted_acceptance(root, server, model, port, receipt)
            if receipt["real_inference"] != "PASS":
                raise RuntimeError("REAL_INFERENCE_RECEIPT_UNCONFIRMED")
            receipt["status"] = "PASS"
    except BaseException as error:
        receipt.update(status="FAIL", error_type=type(error).__name__, error=str(error)[:2000])
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
                receipt["forced_stop"] = True
            receipt.update(runtime_returncode=process.returncode, owned_runtime_stopped=process.poll() is not None)
            if receipt["status"] == "PASS" and (process.returncode != 0 or receipt.get("forced_stop")
                                                or not receipt["owned_runtime_stopped"]):
                receipt["status"] = "FAIL_RUNTIME_SHUTDOWN"
        after = source_identity()
        write_json(root / "source-after.json", after)
        receipt["source_stable"] = before == after
        if not receipt["source_stable"] and receipt["status"] == "PASS":
            receipt["status"] = "INCONCLUSIVE_SOURCE_DRIFT"
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(root / "acceptance.json", receipt)
        print(json.dumps({key: value for key, value in receipt.items() if key != "argv"}), flush=True)
        if receipt["status"] == "INCONCLUSIVE_SOURCE_DRIFT":
            raise SystemExit(2)
        if receipt["status"] == "FAIL_RUNTIME_SHUTDOWN":
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--confirm-owned-cpu-runtime", action="store_true", required=True)
    parser.add_argument("--isolated-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.isolated_child:
        validate_isolated_environment(root)
        execute(root, args.server, args.model, args.model_sha256, args.port)
    else:
        validated_inputs(args.server, args.model, args.model_sha256, args.port)
        root.mkdir(parents=True, exist_ok=False)
        env = isolated_environment(root)
        # Whole harness bound covers startup/scan + unchanged 180-second node.
        with (root / "application.log").open("wb") as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--isolated-child"],
                cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                child.wait(timeout=360)
            finally:
                group_killed = False
                if child.poll() is None:
                    child.terminate()  # Child's finally stops its exact native process.
                    try:
                        child.wait(timeout=25)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(child.pid, signal.SIGKILL)  # Only this new owned process group.
                        except ProcessLookupError:
                            pass
                        group_killed = True
                        child.wait(timeout=5)
                if child.returncode and not group_killed:
                    # A crash or SIGKILL can skip the child's native-runtime finally.
                    # Reaping the child alone does not stop its remaining descendants.
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        print((root / "acceptance.json").read_text() if (root / "acceptance.json").exists() else "NO_FINAL_RECEIPT", flush=True)
        raise SystemExit(child.returncode)


if __name__ == "__main__":
    main()
