from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
OWNERSHIP_MANIFEST = ROOT / ".runtime" / "v061-process-ownership.json"


def main() -> int:
    run_id = os.environ["V061_RUN_ID"]
    port = int(os.environ["V061_API_PORT"])
    launched_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 2,
        "run_id": run_id,
        "fastapi": {
            "run_id": run_id,
            "role": "fastapi_listener",
            "listener_pid": os.getpid(),
            "parent_pid": os.getppid(),
            "selected_port": port,
            "creation_time": launched_at,
            "executable": sys.executable,
            "base_executable": getattr(sys, "_base_executable", sys.executable),
            "argv": ["v061_fastapi_server.py", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            "cwd": str(Path.cwd()),
            "ownership": "SELF_REPORTED_PENDING_OS_VERIFICATION",
        },
    }
    temporary = OWNERSHIP_MANIFEST.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(OWNERSHIP_MANIFEST)
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
