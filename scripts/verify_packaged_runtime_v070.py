from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def _listener_evidence(ports: set[int]) -> tuple[int, list[str]]:
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    addresses: list[str] = []
    for line in completed.stdout.splitlines():
        columns = line.split()
        if len(columns) < 4 or columns[0].upper() != "TCP" or columns[3].upper() != "LISTENING":
            continue
        local = columns[1]
        try:
            port = int(local.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
        if port in ports:
            addresses.append(local)
    public = sum(
        not (address.startswith("127.0.0.1:") or address.startswith("[::1]:"))
        for address in addresses
    )
    return public, addresses


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) not in {3, 4} or (len(sys.argv) == 4 and sys.argv[3] != "--standard-localapp"):
        raise SystemExit("usage: verify_packaged_runtime_v070.py <application-root> <test-root> [--standard-localapp]")
    application = Path(sys.argv[1]).resolve()
    test_root = Path(sys.argv[2]).resolve()
    local_app_data = test_root / ("Local App Data" if len(sys.argv) == 4 else "Local App 数据")
    python = application / "Runtime" / "Python" / "python.exe"
    arguments = [
        str(python), "-I", "-m", "app.packaging.packaged_launcher",
        "--application-root", str(application),
        "--local-app-data", str(local_app_data),
        "--user-profile", str(test_root / "User Name"),
    ]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        arguments, cwd=application / "Backend", stdin=subprocess.DEVNULL,
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    line = ""
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline and process.poll() is None:
        line = process.stdout.readline().strip()
        if line.startswith("PACKAGED_BACKEND_READY "):
            break
    if not line.startswith("PACKAGED_BACKEND_READY "):
        error = process.stderr.read() if process.poll() is not None else "readiness timeout"
        process.terminate()
        print(json.dumps({"ready": False, "error": error[-2000:]}, ensure_ascii=False))
        return 1
    metadata = json.loads(line.removeprefix("PACKAGED_BACKEND_READY "))
    with urllib.request.urlopen(f"http://127.0.0.1:{metadata['backend_port']}/", timeout=3) as response:
        frontend_ready = response.status == 200 and b'id="root"' in response.read()
    query_environment = os.environ.copy()
    query_environment["PGCLIENTENCODING"] = "UTF8"
    chinese = subprocess.run(
        [str(application / "PostgreSQL" / "bin" / "psql.exe"),
         "-h", "127.0.0.1", "-p", str(metadata["database_port"]),
         "-U", "novel_studio", "-d", "ai_novel_studio", "-tAc",
         "SELECT convert_from(decode('e4b8ade69687e5b08fe8afb4e58685e5aeb9','hex'),'UTF8')"],
        capture_output=True,
        env=query_environment, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    decoded_outputs = []
    for encoding in ("utf-8", "gbk"):
        try:
            decoded_outputs.append(chinese.stdout.decode(encoding).strip())
        except UnicodeDecodeError:
            pass
    chinese_roundtrip = chinese.returncode == 0 and "中文小说内容" in decoded_outputs
    public_listeners, listener_addresses = _listener_evidence({
        int(metadata["database_port"]), int(metadata["backend_port"]),
    })
    database = local_app_data / "AI-Novel-Studio" / "UserData" / "PostgreSQL"
    marker = database / "phase51-preserve.marker"
    marker.write_text("preserve", encoding="ascii")
    process.send_signal(getattr(subprocess, "CTRL_BREAK_EVENT", 1))
    try:
        exit_code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.terminate(); exit_code = process.wait(timeout=10)
    shutdown_error = process.stderr.read()
    result = {
        "ready": True,
        "exit_code": exit_code,
        "version": metadata.get("application_version"),
        "packaged": metadata.get("packaged_windows_mode"),
        "database_port": metadata.get("database_port"),
        "backend_port": metadata.get("backend_port"),
        "cluster_version": (database / "PG_VERSION").read_text(encoding="ascii").strip(),
        "userdata_preserved": marker.exists(),
        "python": str(python),
        "frontend_ready": frontend_ready,
        "chinese_roundtrip": chinese_roundtrip,
        "listener_addresses": listener_addresses,
        "public_listeners": public_listeners,
    }
    if exit_code != 0:
        result["shutdown_error"] = shutdown_error[-2000:]
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    forbidden = ("bootstrap_secret", "session_token", "ownership_nonce", "DEEPSEEK_KEY_SENTINEL")
    result["secret_exposure"] = sum(serialized.count(value) for value in forbidden)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if exit_code == 0 and result["version"] == "0.7.0" and frontend_ready and chinese_roundtrip and public_listeners == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
