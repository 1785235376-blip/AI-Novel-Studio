from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg

from prepare_acceptance import seed
from verify_packaged_runtime_v070 import _listener_evidence


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: seed_packaged_acceptance_v070.py "
            "<application-root> <test-root> <evidence-json>"
        )
    application = Path(sys.argv[1]).resolve()
    test_root = Path(sys.argv[2]).resolve()
    evidence_path = Path(sys.argv[3]).resolve()
    if evidence_path.exists():
        raise SystemExit(f"evidence file must be fresh: {evidence_path}")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    local_app_data = test_root / "Local App Data"
    packaged_python = application / "Runtime" / "Python" / "python.exe"
    environment = os.environ.copy()
    environment.update({
        "PYTHONUTF8": "1",
        "LOCALAPPDATA": str(local_app_data),
        "USERPROFILE": str(test_root / "User Name"),
    })
    process = subprocess.Popen(
        [str(packaged_python), "-I", "-m", "app.packaging.packaged_launcher",
         "--application-root", str(application), "--local-app-data", str(local_app_data),
         "--user-profile", str(test_root / "User Name")],
        cwd=application / "Backend", env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    result: dict[str, object] = {}
    try:
        line = ""
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and process.poll() is None:
            line = process.stdout.readline().strip()
            if line.startswith("PACKAGED_BACKEND_READY "):
                break
        if not line.startswith("PACKAGED_BACKEND_READY "):
            error = process.stderr.read() if process.poll() is not None else "readiness timeout"
            raise RuntimeError(error[-2000:])
        metadata = json.loads(line.removeprefix("PACKAGED_BACKEND_READY "))
        database_port = int(metadata["database_port"])
        database_url = f"postgresql://novel_studio@127.0.0.1:{database_port}/ai_novel_studio"
        seed(database_url)
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "INSERT INTO users(id,display_name,status,created_at,updated_at,metadata) "
                "VALUES ('local-author','Local Author','ACTIVE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,"
                "'{\"acceptance_seed\":true}'::jsonb) ON CONFLICT(id) DO NOTHING"
            )
            for workspace_id in ("acceptance-alpha", "acceptance-beta"):
                connection.execute(
                    "INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) "
                    "VALUES (%s,'local-author',%s,'ACTIVE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,"
                    "'{\"acceptance_seed\":true}'::jsonb) ON CONFLICT DO NOTHING",
                    (f"acceptance-membership:{workspace_id}:local-author", workspace_id),
                )
                role = {
                    "id": f"acceptance-local-author:{workspace_id}",
                    "principal_id": "local-author",
                    "role": "ADMIN",
                    "domain": "NOVEL",
                    "scope": {
                        "kind": "WORKSPACE", "workspace_id": workspace_id,
                        "project_id": None, "storyline_id": None, "branch_id": None,
                    },
                    "created_by": "acceptance-seed",
                    "created_at": "2026-08-26T00:00:00+00:00",
                }
                connection.execute(
                    "INSERT INTO domain_role_assignments(id,payload) VALUES (%s,%s::jsonb) "
                    "ON CONFLICT(id) DO NOTHING",
                    (role["id"], json.dumps(role)),
                )
            connection.commit()
            counts = {
                "workspaces": connection.execute(
                    "SELECT count(*) FROM workspaces WHERE payload->>'acceptance_seed'='true'"
                ).fetchone()[0],
                "novels": connection.execute(
                    "SELECT count(*) FROM novels WHERE metadata->>'acceptance_seed'='true'"
                ).fetchone()[0],
                "chapters": connection.execute(
                    "SELECT count(*) FROM chapters c JOIN novels n ON n.id=c.novel_id "
                    "WHERE n.metadata->>'acceptance_seed'='true'"
                ).fetchone()[0],
                "local_author_workspaces": connection.execute(
                    "SELECT count(*) FROM workspace_memberships "
                    "WHERE user_id='local-author' AND workspace_id LIKE 'acceptance-%' AND status='ACTIVE'"
                ).fetchone()[0],
            }
        public, addresses = _listener_evidence({database_port, int(metadata["backend_port"])})
        result = {
            "seeded": counts == {
                "workspaces": 3, "novels": 2, "chapters": 2, "local_author_workspaces": 2,
            },
            "counts": counts,
            "version": metadata["application_version"],
            "packaged": metadata["packaged_windows_mode"],
            "listener_addresses": addresses,
            "public_listeners": public,
        }
    finally:
        if process.poll() is None:
            process.send_signal(getattr(subprocess, "CTRL_BREAK_EVENT", 1))
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
        result["exit_code"] = process.returncode
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        forbidden = ("bootstrap_secret", "session_token", "ownership_nonce", "DEEPSEEK_KEY_SENTINEL")
        result["secret_exposure"] = sum(serialized.count(value) for value in forbidden)
        evidence_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if (
        result.get("seeded") and result.get("packaged") and result.get("public_listeners") == 0
        and result.get("secret_exposure") == 0 and result.get("exit_code") == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
