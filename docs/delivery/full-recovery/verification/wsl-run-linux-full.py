"""Strict original complete suite, local Linux supplemental evidence only."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--backend", choices=("file", "postgres"), required=True)
parser.add_argument("--shard", type=int, default=0)
parser.add_argument("--tree", required=True)
parser.add_argument("--sha", required=True)
parser.add_argument("--run", default="local-recovery-20261007-linux-final")
args = parser.parse_args()
runtime = Path(__file__).resolve().parent
origin = runtime.parents[2]
native_environment = json.loads((runtime / "native-environment.json").read_text(encoding="utf8"))
native = Path(native_environment["native"])
project = native / "project"
venv_python = native / "venv/bin/python"
count = 1 if args.backend == "file" else 2
assert 0 <= args.shard < count
receipts = native / "receipts" / ("file" if args.backend == "file" else f"postgres-{args.shard}")
receipts.mkdir(parents=True, exist_ok=True)
sandbox = native / f"sandbox-{args.backend}-{args.shard}"
for folder in ("data", "backup", "tmp", "appdata", "localappdata", "config", "cache", "state"):
    (sandbox / folder).mkdir(parents=True, exist_ok=True)
font = origin / ".runtime/full-recovery/fonts/NotoSansSC-Regular.ttf"
manifest = project / ".github/ci/coverage_manifest.json.gz"
assert font.is_file() and manifest.is_file() and venv_python.is_file()
database = "novel_recovery_ci" if args.shard == 0 else "novel_recovery_shard1_ci"
url = f"postgresql://recovery@127.0.0.1:55446/{database}"
environment = dict(os.environ)
environment.update({
    "STORAGE_BACKEND": args.backend, "MOCK_PROVIDER": "true", "ENABLE_CLOUD": "false", "MOCK_STREAM_DELAY_MS": "0",
    "CREDENTIAL_VAULT_BACKEND": "memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
    "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "LC_ALL": "C.UTF-8",
    "PYTHONPATH": os.pathsep.join((str(project / ".github/ci"), str(project))),
    "PATH": str(native/"venv/bin") + ":" + native_environment["path"], "LD_LIBRARY_PATH": native_environment["ld_library_path"],
    "PROJECT_ROOT": str(project), "NOVEL_DATA_PATH": str(sandbox/"data/novels"), "BACKUP_PATH": str(sandbox/"backup"),
    "DATABASE_BACKUP_PATH": str(sandbox/"data/database-backups"), "KNOWLEDGE_SOURCE_PATH": str(sandbox/"data/novels"),
    "APPDATA": str(sandbox/"appdata"), "LOCALAPPDATA": str(sandbox/"localappdata"),
    "XDG_CONFIG_HOME": str(sandbox/"config"), "XDG_CACHE_HOME": str(sandbox/"cache"), "XDG_DATA_HOME": str(sandbox/"data"), "XDG_STATE_HOME": str(sandbox/"state"),
    "TMPDIR": str(sandbox/"tmp"), "TMP": str(sandbox/"tmp"), "TEMP": str(sandbox/"tmp"), "R2_TEST_FONT_FILE": str(font),
    "DATABASE_URL": url if args.backend == "postgres" else "", "TEST_POSTGRES_DATABASE_URL": url if args.backend == "postgres" else "",
    "CI_COVERAGE_SHA":args.sha, "CI_COVERAGE_TREE":args.tree,
    "GITHUB_SHA":args.sha, "GITHUB_RUN_ID":args.run, "GITHUB_RUN_ATTEMPT":"1", "GITHUB_REPOSITORY":"1785235376-blip/AI-Novel-Studio",
})
environment.pop("AI_NOVEL_STUDIO_PDF_FONT", None)
environment.pop("AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT", None)
arguments = [str(venv_python), "-m", "pytest", "-p", "postgres_gate", "-p", "suite_coverage", "-p", "no:cacheprovider",
             f"--basetemp={sandbox/'pytest'}", "-q", "-ra", "--tb=short", "--ci-scope=backend", f"--ci-shard-index={args.shard}", f"--ci-shard-count={count}",
             f"--ci-coverage-manifest={manifest}", f"--ci-coverage-dir={receipts}", f"--junitxml={receipts/'backend.xml'}"]
record = {"boundary":"Local WSL Ubuntu 24.04/Python 3.12.3 supplemental validation; not hosted Actions/Python 3.12.9; strict guards unchanged",
          "start_utc":datetime.now(timezone.utc).isoformat(), "platform":platform.platform(), "python":platform.python_version(),
          "backend":args.backend, "shard":args.shard, "project":str(project), "arguments":arguments,
          "timeout_seconds":1200 if args.backend == "file" else 3300,
          "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(), "source_tree":args.tree, "checked_out_sha":args.sha}
(receipts/"local-run.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf8")
shutil.copyfile(manifest, receipts/"source-manifest.json.gz")
started = time.monotonic()
with (receipts/"backend.log").open("wb") as output:
    process = subprocess.Popen(arguments, cwd=project, env=environment, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    print(f"Linux strict {args.backend}/{args.shard} started pid={process.pid} receipts={receipts}", flush=True)
    try:
        code = process.wait(timeout=record["timeout_seconds"])
        record["timed_out"] = False
    except subprocess.TimeoutExpired:
        record["timed_out"] = True
        import signal
        os.killpg(process.pid, signal.SIGKILL)
        code = process.wait()
record.update({"elapsed_seconds":round(time.monotonic()-started,3), "process_exitcode":code, "end_utc":datetime.now(timezone.utc).isoformat()})
(receipts/"local-run.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf8")
destination = origin / "docs/delivery/full-recovery/candidate-linux-receipts" / receipts.name
shutil.copytree(receipts, destination, dirs_exist_ok=True)
print(json.dumps({key:record[key] for key in ("elapsed_seconds", "process_exitcode", "timed_out")}), flush=True)
sys.exit(code if code else 0)
