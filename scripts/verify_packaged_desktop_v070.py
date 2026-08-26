from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from verify_packaged_runtime_v070 import _listener_evidence


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) not in {3, 4} or (len(sys.argv) == 4 and sys.argv[3] != "--standard-localapp"):
        raise SystemExit("usage: verify_packaged_desktop_v070.py <application-root> <test-root> [--standard-localapp]")
    application = Path(sys.argv[1]).resolve()
    test_root = Path(sys.argv[2]).resolve()
    local_app_data = test_root / ("Local App Data" if len(sys.argv) == 4 else "Local App 数据")
    python = application / "Runtime" / "Python" / "python.exe"
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    # DesktopHost validates its disposable WebView2 profile against the
    # process LOCALAPPDATA/USERPROFILE roots. Keep those roots aligned with
    # the isolated test fixture passed to the packaged launcher.
    environment["LOCALAPPDATA"] = str(local_app_data)
    environment["USERPROFILE"] = str(test_root / "User Name")
    process = subprocess.Popen(
        [str(python), "-I", "-m", "app.packaging.packaged_desktop_launcher",
         "--application-root", str(application),
         "--local-app-data", str(local_app_data),
         "--user-profile", str(test_root / "User Name")],
        cwd=application / "Backend", env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    line = ""
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and process.poll() is None:
        line = process.stdout.readline().strip()
        if line.startswith("APPLICATION_READY "):
            break
    if not line.startswith("APPLICATION_READY "):
        error = process.stderr.read() if process.poll() is not None else "readiness timeout"
        process.terminate()
        print(json.dumps({"application_ready": False, "error": error[-3000:]}, ensure_ascii=False))
        return 1
    metadata = json.loads(line.removeprefix("APPLICATION_READY "))
    origin = metadata["frontend_origin"]
    with urllib.request.urlopen(origin + "/", timeout=3) as response:
        frontend = response.status == 200 and b'id="root"' in response.read()
    public, addresses = _listener_evidence({metadata["database_port"], metadata["backend_port"]})
    process.send_signal(getattr(subprocess, "CTRL_BREAK_EVENT", 1))
    try:
        exit_code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.terminate()
        exit_code = process.wait(timeout=10)
    error = process.stderr.read()
    result = {
        "application_ready": True,
        "backend_port": metadata["backend_port"],
        "database_port": metadata["database_port"],
        "desktop_host_started": bool(metadata["desktop_host_pid"]),
        "exit_code": exit_code,
        "frontend": frontend,
        "frontend_origin": origin,
        "listener_addresses": addresses,
        "public_listeners": public,
        "version": metadata["application_version"],
    }
    if exit_code != 0:
        result["shutdown_error"] = error[-3000:]
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    forbidden = ("bootstrap_secret", "session_token", "ownership_nonce", "DEEPSEEK_KEY_SENTINEL")
    result["secret_exposure"] = sum(serialized.count(value) for value in forbidden)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if exit_code == 0 and frontend and public == 0 and result["secret_exposure"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
