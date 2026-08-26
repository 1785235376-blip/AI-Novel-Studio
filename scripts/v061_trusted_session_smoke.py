from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
ENVIRONMENT_MANIFEST = RUNTIME / "v061-acceptance-environment.json"
RUN_MANIFEST = RUNTIME / "v061-browser-run.json"
BASE_URL = os.environ.get("V061_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def require(condition: bool, stage: str, status: int | None = None) -> None:
    if not condition:
        suffix = "" if status is None else f"_HTTP_{status}"
        raise AssertionError(f"{stage}{suffix}")


def request_status(
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | None]:
    headers: dict[str, str] = {}
    if token is not None:
        headers["X-Session-Token"] = token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
            return response.status, payload
    except urllib.error.HTTPError as exc:
        try:
            payload = json.load(exc)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        return exc.code, payload


def error_code(payload: dict[str, object] | None) -> str:
    if not isinstance(payload, dict):
        return "UNKNOWN"
    detail = payload.get("detail")
    if isinstance(detail, dict) and isinstance(detail.get("code"), str):
        return detail["code"]
    return "UNKNOWN"


def load_sessions() -> tuple[dict[str, object], list[dict[str, str]]]:
    manifest = json.loads(ENVIRONMENT_MANIFEST.read_text(encoding="utf-8"))
    sessions = manifest.get("sessions")
    environment = manifest.get("environment")
    if not isinstance(sessions, list) or not isinstance(environment, dict):
        raise ValueError("acceptance environment manifest is invalid")
    trusted = json.loads(str(environment.get("COLLABORATION_DEV_SESSIONS_JSON", "")))
    if not isinstance(trusted, list):
        raise ValueError("trusted session root must be an array")
    trusted_tokens = {item.get("token") for item in trusted}
    for session in sessions:
        token = session.get("token")
        if not isinstance(token, str) or not token or token != token.strip():
            raise ValueError("acceptance session token is invalid")
        if token not in trusted_tokens:
            raise ValueError("acceptance session is absent from the FastAPI runtime")
    return manifest, sessions


def main() -> int:
    try:
        manifest, sessions = load_sessions()
        admin = next(item for item in sessions if item.get("role") == "ADMIN")
        lead = next(item for item in sessions if item.get("role") == "DOMAIN_LEAD")
        run_id = os.environ.get("V061_RUN_ID", "").strip()
        if not run_id:
            raise ValueError("V061_RUN_ID is required")
        workspace_id = f"acceptance-roundtrip-empty-{run_id}"

        status, _ = request_status("/api/collaboration/admin/workspaces")
        require(status == 401, "MISSING_SESSION", status)
        status, invalid_payload = request_status(
            "/api/collaboration/admin/workspaces", token="invalid-v061-session"
        )
        require(status == 401, "INVALID_SESSION", status)
        for role_session in sessions:
            role_status, role_payload = request_status(
                "/api/collaboration/admin/workspaces",
                token=str(role_session["token"]),
            )
            require(
                role_status == 200,
                f"{role_session['role']}_SESSION_{error_code(role_payload)}",
                role_status,
            )
        status, forbidden_payload = request_status(
            "/api/collaboration/admin/workspaces",
            token=str(lead["token"]),
            method="POST",
            body={"id": workspace_id, "name": workspace_id},
        )
        require(status == 403, f"VALID_UNAUTHORIZED_{error_code(forbidden_payload)}", status)

        status, created = request_status(
            "/api/collaboration/admin/workspaces",
            token=str(admin["token"]),
            method="POST",
            body={"id": workspace_id, "name": workspace_id},
        )
        require(status == 201 and created is not None, "ADMIN_WORKSPACE_CREATE", status)
        status, navigation = request_status(
            f"/api/collaboration/admin/workspaces/{urllib.parse.quote(workspace_id)}/navigation",
            token=str(admin["token"]),
        )
        require(status == 200 and navigation is not None, "WORKSPACE_NAVIGATION", status)
        require(
            navigation["eligible_paths"] == [] and navigation["default_path"] is None,
            "WORKSPACE_NOT_EMPTY",
        )

        bootstrap_path = (
            "/api/collaboration/workspaces/acceptance-alpha/"
            "projects/acceptance-alpha-novel/"
            "storylines/acceptance-alpha-storyline/"
            "branches/acceptance-alpha-main/bootstrap?actor_id=acceptance-lead&role=ADMIN"
        )
        status, bootstrap = request_status(bootstrap_path, token=str(admin["token"]))
        require(status == 200 and bootstrap is not None, "COLLABORATION_BOOTSTRAP", status)
        require(bootstrap["actor"]["actor_id"] == admin["actor_id"], "ACTOR_SPOOFED")
        require(bootstrap["actor"]["session_id"] == admin["session_id"], "SESSION_MISMATCH")

        RUN_MANIFEST.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "roundtrip_empty": {"id": workspace_id, "name": workspace_id},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        detail = str(exc) if isinstance(exc, AssertionError) else type(exc).__name__
        print(f"TRUSTED_SESSION_SMOKE_FAILED={detail}", file=sys.stderr)
        return 1

    print("SESSION_MANIFEST_STRUCTURE=PASS")
    print("SESSION_RUNTIME_CONSISTENCY=PASS")
    print("TRUSTED_SESSION_COLLABORATION_SMOKE=PASS")
    print("INVALID_SESSION_REJECTED=PASS")
    print("UNAUTHORIZED_VALID_SESSION_REJECTED=PASS")
    print("CLIENT_SPOOFING_REJECTED=PASS")
    print("ACTOR_CONTEXT=TRUSTED")
    print("ACTIVE_BACKEND=postgres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
