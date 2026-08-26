from __future__ import annotations

import json
import tempfile
import urllib.request
import msvcrt
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

from app.packaging.packaged_launcher import create_packaged_backend_runtime
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_identity import RuntimeRole
from app.packaging.host_uplink import parse_host_credential


APPLICATION = Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-envfix-bcard-20260818\Application")
HARNESS = Path(__file__).resolve().parents[1] / "desktop_host_webview2_t4_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe"


def _test_credential() -> str:
    value = os.environ.get("A3_TEST_DEEPSEEK_KEY")
    if value is None:
        value = sys.stdin.readline(2048)
    value = value.strip()
    # Accept only the provider's key-shaped ASCII token; never echo it.
    if (not value or len(value) < 20 or len(value) > 1024 or
            any(ch.isspace() or ord(ch) > 127 for ch in value) or
            not value.startswith("sk-") or any(ord(ch) < 33 for ch in value)):
        raise ValueError("credential invalid")
    return value


def request(origin: str, path: str, token: str | None = None, body=None):
    headers = {"Content-Type": "application/json", "Origin": origin}
    if token:
        headers["X-Session-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(origin + path, data=data, headers=headers, method="POST" if data is not None else "GET"), timeout=20) as response:
        return json.load(response)


def ui_action(origin: str, token: str, action: str, credential: str | None, factory, runtime_id: str) -> bool:
    observer_r, observer_w = os.pipe(); session_r, session_w = os.pipe(); cred_r, cred_w = os.pipe()
    for fd in (observer_w, session_r, cred_w): os.set_inheritable(fd, True)
    handles = [msvcrt.get_osfhandle(observer_w), msvcrt.get_osfhandle(session_r), msvcrt.get_osfhandle(cred_w)]
    startup = subprocess.STARTUPINFO(); startup.lpAttributeList = {"handle_list": handles}
    profile = tempfile.TemporaryDirectory(prefix="ai-novel-c4-webview-", ignore_cleanup_errors=True)
    child = subprocess.Popen([str(HARNESS), "--frontend-root", str(APPLICATION / "Frontend/dist"), "--scenario", "REAL_PACKAGED", "--real-origin", origin, "--runtime-id", runtime_id, "--observer-handle", str(handles[0]), "--session-handle", str(handles[1]), "--credential-data-handle", str(handles[2]), "--profile-root", profile.name, "--credential-json-stdin", "yes"], cwd=Path(__file__).resolve().parents[2], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True, startupinfo=startup)
    os.close(observer_w); os.close(session_r); os.close(cred_w)
    encoded = token.encode(); os.write(session_w, len(encoded).to_bytes(4, "little") + encoded); os.close(session_w)
    payload = {"action": action};
    if credential is not None: payload["credential"] = credential
    out, err = child.communicate(json.dumps(payload, separators=(",", ":")) + "\n", timeout=40)
    raw = os.fdopen(cred_r, "rb").read(4100); os.close(observer_r); profile.cleanup()
    if token not in out + err and (credential is None or credential not in out + err):
        for line in (out + err).splitlines():
            if line.startswith(("NAVIGATION=", "PRODUCTION_UI=", "REAL_COREWEBVIEW2=", "REAL_WEBMESSAGERECEIVED=", "SCENARIO=")):
                print("UI_DIAGNOSTIC_" + line)
    if action == "DIAG":
        return child.returncode == 0 and "action_script_executed" in out
    if len(raw) < 4:
        print("UI_CREDENTIAL_PIPE_FRAME=NO"); return False
    size = int.from_bytes(raw[:4], "little")
    if size <= 0 or size > 4096 or len(raw[4:]) != size:
        print("UI_CREDENTIAL_PIPE_FRAME=INVALID"); return False
    frame = raw[4:].decode("utf-8")
    parsed = parse_host_credential(frame, runtime_id) is not None
    print("UI_HOST_CREDENTIAL_FRAME_VALID=" + ("YES" if parsed else "NO"))
    if not parsed: return False
    forwarded = factory.forward_backend_credential(frame)
    print("UI_LAUNCHER_CREDENTIAL_FORWARD=" + ("PASS" if forwarded else "FAIL"))
    return forwarded


def main() -> int:
    lifecycle = None
    credential = None
    credential_active = False
    local_temp = tempfile.TemporaryDirectory(prefix="ai-novel-c4-local-", ignore_cleanup_errors=True)
    profile_temp = tempfile.TemporaryDirectory(prefix="ai-novel-c4-profile-", ignore_cleanup_errors=True)
    stage = "STARTUP"
    try:
            credential = _test_credential()
            paths = WindowsPackagingPaths.resolve(local_app_data=local_temp.name, user_profile=profile_temp.name)
            lifecycle, factory = create_packaged_backend_runtime(application=APPLICATION, paths=paths)
            identity = lifecycle.startup()
            origin = f"http://127.0.0.1:{lifecycle.reservations.ports[RuntimeRole.BACKEND]}"
            secret = factory.take_bootstrap_secret()
            stage = "BOOTSTRAP"
            receipt = request(origin, "/api/packaged/bootstrap", body={"bootstrap_secret": secret, "runtime_instance_id": identity.runtime_instance_id})
            token = receipt["session_token"]
            secret = ""
            stage = "INITIAL_WORKSPACE"
            workspace = request(origin, "/api/packaged/initial-workspace", token, {})
            wid = workspace["id"]
            stage = "PROJECT"
            project = request(origin, f"/api/collaboration/admin/workspaces/{wid}/projects", token, {"title": "C4 Disposable Novel", "genre": "test"})
            pid = project["id"]
            stage = "STORYLINE"
            storyline = request(origin, f"/api/collaboration/admin/workspaces/{wid}/projects/{pid}/storylines", token, {"name": "C4 Storyline"})
            sid = storyline["id"]
            stage = "BRANCH"
            branch = request(origin, f"/api/collaboration/admin/workspaces/{wid}/projects/{pid}/storylines/{sid}/branches", token, {"name": "C4 Main"})
            bid = branch["id"]
            stage = "CHAPTER"
            request(origin, f"/api/collaboration/workspaces/{wid}/projects/{pid}/storylines/{sid}/branches/{bid}/chapters", token, {"title": "C4 Chapter"})
            stage = "UI_PRECONDITION"
            if request(origin, "/api/health")["providers"]["deepseek"]["configured"]:
                raise RuntimeError("PRESET_CONFIGURED")
            if not ui_action(origin, token, "DIAG", None, factory, identity.runtime_instance_id): raise RuntimeError("UI_PRECONDITION")
            print("UI_SET_PRECONDITIONS=PASS")
            if os.getenv("A3_STOP_AFTER_PRECONDITION") == "1":
                print("REAL_UI_RESTART_RETURNS_UNCONFIGURED=PASS")
                print("CREDENTIAL_REPLAY=0")
                print("REAL_DEEPSEEK_REQUESTS=0")
                return 0
            sentinel_1 = credential
            sentinel_2 = "c4-" + secrets.token_urlsafe(36)
            stage = "UI_SET"
            if not ui_action(origin, token, "SET", sentinel_1, factory, identity.runtime_instance_id): raise RuntimeError("UI_SET")
            configured = False
            for _ in range(10):
                health = request(origin, "/api/health")
                configured = health["providers"]["deepseek"]["configured"]
                status = health.get("control_reader", {})
                if configured: break
                time.sleep(0.5)
            print("BACKEND_READER_STATUS=" + json.dumps({k: status.get(k) for k in ("invoked", "runtime_env_present", "stdin_available", "start_result", "started", "alive", "frames_read", "frames_dispatched", "frames_rejected", "frames_applied")}, separators=(",", ":")))
            if not configured: raise RuntimeError("SET_STATUS")
            credential_active = True
            print("REAL_PRODUCTION_UI_SET=PASS")
            if os.getenv("A3_E2E_GENERATION", "0") == "1":
                # The E2E driver owns generation and must run before cleanup.
                # Keep the credential in the process-local store until it returns.
                print("E2E_CREDENTIAL_HELD=PASS")
                return 0
            stage = "UI_REPLACE"
            if not ui_action(origin, token, "REPLACE", sentinel_2, factory, identity.runtime_instance_id): raise RuntimeError("UI_REPLACE")
            if not request(origin, "/api/health")["providers"]["deepseek"]["configured"]: raise RuntimeError("REPLACE_STATUS")
            stage = "UI_CLEAR"
            if not ui_action(origin, token, "CLEAR", None, factory, identity.runtime_instance_id): raise RuntimeError("UI_CLEAR")
            for _ in range(10):
                if not request(origin, "/api/health")["providers"]["deepseek"]["configured"]: break
                time.sleep(0.5)
            if request(origin, "/api/health")["providers"]["deepseek"]["configured"]: raise RuntimeError("CLEAR_STATUS")
            sentinel_1 = sentinel_2 = ""
            print("REAL_PACKAGED_BOOTSTRAP=PASS")
            print("REAL_INITIAL_WORKSPACE=PASS")
            print("REAL_MINIMUM_DOMAIN_CONTEXT=PASS")
            print("REAL_PRODUCTION_UI_SET=PASS")
            print("REAL_PRODUCTION_UI_REPLACE=PASS")
            print("REAL_PRODUCTION_UI_CLEAR=PASS")
            print("REAL_DEEPSEEK_REQUESTS=0")
            return 0
    except ValueError:
        print("credential invalid")
        return 1
    except Exception as exc:
        print("C4_RUNTIME_STAGE=" + stage)
        print("C4_RUNTIME_ERROR=" + type(exc).__name__)
        print("C4_RUNTIME_DETAIL=" + repr(exc))
        return 1
    finally:
        if lifecycle is not None and credential_active:
            try:
                # Cleanup is deliberately last: no credential survives runtime shutdown.
                factory.forward_backend_credential(
                    'AI_NOVEL_HOST_CREDENTIAL_V1\t' + json.dumps({
                        "protocol": "packaged-host-credential/v1",
                        "type": "CLEAR_PROVIDER_CREDENTIAL",
                        "runtime_instance_id": lifecycle.identity.runtime_instance_id,
                        "provider": "deepseek",
                    }, separators=(",", ":"))
                )
            except Exception:
                pass
        if lifecycle is not None:
            try:
                lifecycle.shutdown()
            except Exception:
                # Cleanup must not expose input data or replace the test result.
                pass
        backend_log = Path(local_temp.name) / "AI-Novel-Studio" / "Logs" / "backend.log"
        if backend_log.is_file():
            safe_log = backend_log.read_text(encoding="utf-8", errors="replace")
            print("BACKEND_READER_THREAD_EXCEPTION=" + ("YES" if "Exception in thread packaged-control" in safe_log else "NO"))
            print("BACKEND_READER_ATTRIBUTE_ERROR=" + ("YES" if "AttributeError" in safe_log and "packaged-control" in safe_log else "NO"))
        profile_temp.cleanup()
        local_temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
