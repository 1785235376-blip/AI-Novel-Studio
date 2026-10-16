"""Original two-process real loopback gate on the frozen native candidate."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

runtime = Path(__file__).resolve().parent
origin = runtime.parents[2]
native_environment = json.loads((runtime / "native-environment.json").read_text())
native = Path(native_environment["native"])
project = native / "project"
receipts = native / "receipts/file"
sandbox = native / "sandbox-sync-tcp"
sandbox.mkdir(exist_ok=True)
environment = dict(os.environ)
environment.update({
    "RUN_B10_TCP_SYNC_TEST": "1", "STORAGE_BACKEND": "file", "MOCK_PROVIDER": "true",
    "MOCK_STREAM_DELAY_MS": "0", "ENABLE_CLOUD": "false", "DATABASE_URL": "", "TEST_POSTGRES_DATABASE_URL": "",
    "CREDENTIAL_VAULT_BACKEND": "memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true",
    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    "PATH": str(native / "venv/bin") + ":" + native_environment["path"],
    "LD_LIBRARY_PATH": native_environment["ld_library_path"], "LC_ALL": "C.UTF-8",
    "NOVEL_DATA_PATH": str(sandbox / "novels"), "BACKUP_PATH": str(sandbox / "backups"),
    "DATABASE_BACKUP_PATH": str(sandbox / "db-backups"), "KNOWLEDGE_SOURCE_PATH": str(sandbox / "novels"),
    "XDG_DATA_HOME": str(sandbox / "xdg"), "APPDATA": str(sandbox / "appdata"),
    "LOCALAPPDATA": str(sandbox / "localappdata"), "TMPDIR": str(sandbox),
})
environment.pop("AI_NOVEL_STUDIO_PDF_FONT", None)
environment.pop("AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT", None)
arguments = [str(native / "venv/bin/python"), "-m", "pytest", "-p", "no:cacheprovider",
             f"--basetemp={sandbox / 'pytest'}", "-q", "-ra", "--tb=short", "tests/test_r5_offline_sync_tcp.py",
             f"--junitxml={receipts / 'sync-tcp.xml'}"]
started = time.monotonic()
with (receipts / "sync-tcp.log").open("wb") as output:
    result = subprocess.run(arguments, cwd=project, env=environment, stdout=output, stderr=subprocess.STDOUT)
record = {"boundary": "Original real two-process uvicorn/loopback TCP gate; synthetic documents; no mocked HTTP transport",
          "project": str(project), "arguments": arguments, "elapsed_seconds": round(time.monotonic() - started, 3),
          "process_exitcode": result.returncode}
(receipts / "sync-tcp-local-run.json").write_text(json.dumps(record, indent=2) + "\n")
destination = origin / "docs/delivery/full-recovery/candidate-linux-receipts/file"
destination.mkdir(parents=True, exist_ok=True)
for name in ("sync-tcp.log", "sync-tcp.xml", "sync-tcp-local-run.json"):
    source = receipts / name
    if source.exists():
        shutil.copyfile(source, destination / name)
print(json.dumps(record))
raise SystemExit(result.returncode)
