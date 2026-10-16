"""Strict isolated local PostgreSQL full suite; no hosted-CI equivalence claim."""
from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / ".runtime/full-recovery/postgres-ci-final"
RECEIPTS = ROOT / "docs/delivery/full-recovery/candidate-backend-receipts/postgres"
PG_BIN = ROOT.parent / "AI-Novel-Studio-acceptance/Application/PostgreSQL/bin"
DB_URL = "postgresql://recovery@127.0.0.1:55445/novel_recovery_ci"
FONT = ROOT / ".runtime/full-recovery/fonts/NotoSansSC-Regular.ttf"
PROVENANCE = json.loads((ROOT / "docs/delivery/full-recovery/candidate-coverage-manifest-provenance.json").read_text())
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert FONT.is_file() and (PG_BIN / "pg_dump.exe").is_file()
RECEIPTS.mkdir(parents=True, exist_ok=True)
for suffix in ("appdata", "localappdata", "config", "cache", "data", "state", "tmp"):
    (RUNTIME / suffix).mkdir(parents=True, exist_ok=True)
environment = dict(os.environ)
for name in ("AI_NOVEL_STUDIO_PDF_FONT", "AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT"):
    environment.pop(name, None)
environment.update({
    "STORAGE_BACKEND":"postgres", "DATABASE_URL":DB_URL, "TEST_POSTGRES_DATABASE_URL":DB_URL,
    "MOCK_PROVIDER":"true", "ENABLE_CLOUD":"false", "MOCK_STREAM_DELAY_MS":"0",
    "CREDENTIAL_VAULT_BACKEND":"memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK":"true",
    "PYTHONDONTWRITEBYTECODE":"1", "HF_HUB_OFFLINE":"1", "TRANSFORMERS_OFFLINE":"1",
    "PYTHONUTF8":"1",
    "PYTHONPATH":os.pathsep.join((str(ROOT / ".github/ci"),str(ROOT))),
    "PATH":os.pathsep.join((str(PG_BIN),environment.get("PATH",""))),
    "PROJECT_ROOT":str(ROOT), "NOVEL_DATA_PATH":str(RUNTIME / "data/novels"),
    "BACKUP_PATH":str(RUNTIME / "data/backups"), "DATABASE_BACKUP_PATH":str(RUNTIME / "data/database-backups"),
    "KNOWLEDGE_SOURCE_PATH":str(RUNTIME / "data/novels"),
    "APPDATA":str(RUNTIME / "appdata"), "LOCALAPPDATA":str(RUNTIME / "localappdata"),
    "XDG_CONFIG_HOME":str(RUNTIME / "config"), "XDG_CACHE_HOME":str(RUNTIME / "cache"),
    "XDG_DATA_HOME":str(RUNTIME / "data"), "XDG_STATE_HOME":str(RUNTIME / "state"),
    "TMPDIR":str(RUNTIME / "tmp"), "TMP":str(RUNTIME / "tmp"), "TEMP":str(RUNTIME / "tmp"),
    "R2_TEST_FONT_FILE":str(FONT),
    "CI_COVERAGE_SHA":HEAD, "GITHUB_SHA":HEAD,
    "CI_COVERAGE_TREE":"local-working-source-" + PROVENANCE["source_files_fingerprint_sha256"],
    "GITHUB_RUN_ID":"local-recovery-20261007-final", "GITHUB_RUN_ATTEMPT":"1",
    "GITHUB_REPOSITORY":"1785235376-blip/AI-Novel-Studio",
})
arguments = [sys.executable,"-m","pytest","-p","postgres_gate","-p","suite_coverage","-p","no:cacheprovider",
             f"--basetemp={RUNTIME / 'pytest'}","-q","-ra","--tb=short","--ci-scope=backend",
             "--ci-shard-index=0","--ci-shard-count=1",f"--ci-coverage-dir={RECEIPTS}",
             f"--junitxml={RECEIPTS / 'backend.xml'}"]
record = {"evidence_boundary":"Local Windows/Python supplemental reviewed working tree; NOT hosted GitHub Actions",
          "start_utc":datetime.now(timezone.utc).isoformat(), "platform":platform.platform(),
          "python_version":platform.python_version(), "arguments":arguments, "timeout_seconds":3300,
          "identity_environment":{key:environment[key] for key in ("CI_COVERAGE_SHA","CI_COVERAGE_TREE","GITHUB_SHA","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT","GITHUB_REPOSITORY")},
          "database":"Isolated PostgreSQL 16.4 recovery@127.0.0.1:55445/novel_recovery_ci",
          "manifest_sha256":hashlib.sha256((ROOT / '.github/ci/coverage_manifest.json.gz').read_bytes()).hexdigest(),
          "font_sha256":hashlib.sha256(FONT.read_bytes()).hexdigest()}
(RECEIPTS / "local-run.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
started = time.monotonic()
with (RECEIPTS / "backend.log").open("wb") as output:
    process = subprocess.Popen(arguments,cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT)
    print(f"Strict PostgreSQL full runner started pid={process.pid}",flush=True)
    try:
        code = process.wait(timeout=3300)
        record["timed_out"] = False
    except subprocess.TimeoutExpired:
        record["timed_out"] = True
        subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],check=False,stdout=output,stderr=subprocess.STDOUT)
        code = process.wait()
record.update(elapsed_seconds=round(time.monotonic()-started,3),process_exitcode=code,end_utc=datetime.now(timezone.utc).isoformat())
(RECEIPTS / "local-run.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
print(json.dumps({key:record[key] for key in ("elapsed_seconds","process_exitcode","timed_out")}),flush=True)
raise SystemExit(code)
