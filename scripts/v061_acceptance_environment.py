from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values

try:
    from .prepare_acceptance import acceptance_url
except ImportError:
    from prepare_acceptance import acceptance_url


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / ".runtime" / "v061-acceptance-environment.json"
FRONTEND_ORIGIN = "http://127.0.0.1:4173"
PROVIDER_SECRET_ENVIRONMENT_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
)
PROCESS_ONLY_ENVIRONMENT_KEYS = (*PROVIDER_SECRET_ENVIRONMENT_KEYS, "REAL_PROVIDER_VERIFICATION")


def build_child_environment(
    manifest_environment: dict[str, object],
    parent_environment: dict[str, str] | None = None,
) -> dict[str, str]:
    """Compose a child environment without accepting persisted provider secrets.

    Non-secret acceptance configuration remains manifest-authoritative. Explicitly
    approved process-only values are inherited only from the launching process.
    """
    parent = dict(os.environ if parent_environment is None else parent_environment)
    child = dict(parent)
    child.update(
        {
            key: str(value)
            for key, value in manifest_environment.items()
            if key not in PROCESS_ONLY_ENVIRONMENT_KEYS
        }
    )
    for key in PROCESS_ONLY_ENVIRONMENT_KEYS:
        value = parent.get(key)
        if value:
            child[key] = value
        else:
            child.pop(key, None)
    return child


def safe_environment_diagnostics(environment: dict[str, str]) -> dict[str, object]:
    return {
        "provider_credentials_present": {
            key: bool(environment.get(key)) for key in PROVIDER_SECRET_ENVIRONMENT_KEYS
        },
        "real_provider_verification": environment.get("REAL_PROVIDER_VERIFICATION", "UNSET"),
        "mock_provider": environment.get("MOCK_PROVIDER", "UNSET"),
    }


def build_sessions() -> list[dict[str, str]]:
    run_id = uuid.uuid4().hex
    return [
        {
            "role": role,
            "token": f"accept-{label}-{uuid.uuid4().hex}",
            "actor_id": f"acceptance-{label}",
            "workspace_id": "acceptance-alpha",
            "session_id": f"accept-{uuid.uuid4().hex}",
            "client_id": "acceptance-browser",
        }
        for role, label in (
            ("ADMIN", "admin"),
            ("DOMAIN_LEAD", "lead"),
            ("MEMBER", "member"),
        )
    ]


def build_manifest() -> dict[str, object]:
    base = {
        key: value
        for key, value in dotenv_values(ROOT / ".env").items()
        if value is not None and key not in PROCESS_ONLY_ENVIRONMENT_KEYS
    }
    source_url = base.get("DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    sessions = build_sessions()
    trusted_sessions = [
        {key: value for key, value in session.items() if key != "role"}
        for session in sessions
    ]
    environment = {
        **base,
        "STORAGE_BACKEND": "postgres",
        "DATABASE_URL": acceptance_url(source_url),
        "ENABLE_COLLABORATION_RUNTIME": "true",
        "MOCK_PROVIDER": "false" if os.environ.get("REAL_PROVIDER_VERIFICATION", "").lower() == "true" else "true",
        "MOCK_STREAM_DELAY_MS": "0",
        "FRONTEND_ORIGIN": FRONTEND_ORIGIN,
        "COLLABORATION_DEV_SESSIONS_JSON": json.dumps(
            trusted_sessions, separators=(",", ":")
        ),
    }
    return {
        "schema_version": 1,
        "run_id": os.environ.get("V061_RUN_ID") or uuid.uuid4().hex,
        "environment": environment,
        "sessions": sessions,
    }


def validate(manifest: dict[str, object]) -> None:
    environment = manifest.get("environment")
    if not isinstance(environment, dict):
        raise ValueError("environment must be an object")
    if environment.get("STORAGE_BACKEND") != "postgres":
        raise ValueError("STORAGE_BACKEND must be postgres")
    if not environment.get("DATABASE_URL"):
        raise ValueError("DATABASE_URL is required")
    if environment.get("FRONTEND_ORIGIN") != FRONTEND_ORIGIN:
        raise ValueError("FRONTEND_ORIGIN is invalid")
    if environment.get("MOCK_PROVIDER") not in {"true", "false"}:
        raise ValueError("provider configuration is invalid")
    sessions = json.loads(str(environment.get("COLLABORATION_DEV_SESSIONS_JSON", "")))
    if not isinstance(sessions, list):
        raise ValueError("trusted session root must be an array")
    if not manifest.get("run_id"):
        raise ValueError("run_id is required")


def main() -> int:
    try:
        manifest = build_manifest()
        validate(manifest)
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = MANIFEST_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(MANIFEST_PATH)
    except Exception as exc:
        print(f"Acceptance environment builder failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print("ACCEPTANCE_ENVIRONMENT_MANIFEST_CREATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
