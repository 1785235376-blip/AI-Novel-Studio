from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

from verify_packaged_runtime_v070 import _listener_evidence


USER32 = ctypes.WinDLL("user32", use_last_error=True)
SWP_SHOWWINDOW = 0x0040
WINDOW_SIZES = ((1024, 720), (1440, 900), (1920, 1080))


def _find_window(process_id: int, timeout: float = 30) -> int:
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(window: int, _: int) -> bool:
        owner = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == process_id and USER32.IsWindowVisible(window):
            found.append(window)
            return False
        return True

    callback = callback_type(visit)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found.clear()
        USER32.EnumWindows(callback, 0)
        if found:
            return found[0]
        time.sleep(0.2)
    raise RuntimeError("DesktopHost window was not visible before the evidence timeout")


def _window_rect(window: int) -> tuple[int, int, int, int]:
    rectangle = wintypes.RECT()
    if not USER32.GetWindowRect(window, ctypes.byref(rectangle)):
        raise ctypes.WinError(ctypes.get_last_error())
    return rectangle.left, rectangle.top, rectangle.right, rectangle.bottom


def _capture(window: int, output: Path, width: int, height: int) -> dict[str, object]:
    if not USER32.SetWindowPos(window, 0, 20, 20, width, height, SWP_SHOWWINDOW):
        raise ctypes.WinError(ctypes.get_last_error())
    USER32.SetForegroundWindow(window)
    time.sleep(1.5)
    left, top, right, bottom = _window_rect(window)
    actual_width, actual_height = right - left, bottom - top
    command = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$bitmap = [System.Drawing.Bitmap]::new([int]$env:STUDIO_CAPTURE_WIDTH, [int]$env:STUDIO_CAPTURE_HEIGHT)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
  $graphics.CopyFromScreen([int]$env:STUDIO_CAPTURE_LEFT, [int]$env:STUDIO_CAPTURE_TOP, 0, 0, $bitmap.Size)
  $bitmap.Save($env:STUDIO_CAPTURE_OUTPUT, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
  $graphics.Dispose()
  $bitmap.Dispose()
}
"""
    capture_environment = os.environ.copy()
    capture_environment.update({
        "STUDIO_CAPTURE_LEFT": str(left),
        "STUDIO_CAPTURE_TOP": str(top),
        "STUDIO_CAPTURE_WIDTH": str(actual_width),
        "STUDIO_CAPTURE_HEIGHT": str(actual_height),
        "STUDIO_CAPTURE_OUTPUT": str(output),
    })
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        env=capture_environment,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0 or not output.is_file():
        raise RuntimeError(f"DesktopHost screenshot failed: {completed.stderr[-1000:]}")
    dpi = USER32.GetDpiForWindow(window) if hasattr(USER32, "GetDpiForWindow") else 0
    return {
        "file": output.name,
        "requested_width": width,
        "requested_height": height,
        "actual_width": actual_width,
        "actual_height": actual_height,
        "dpi": dpi,
        "bytes": output.stat().st_size,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: capture_packaged_desktop_evidence_v070.py "
            "<application-root> <test-root> <evidence-root>"
        )
    application = Path(sys.argv[1]).resolve()
    test_root = Path(sys.argv[2]).resolve()
    evidence_root = Path(sys.argv[3]).resolve()
    if evidence_root.exists():
        raise SystemExit(f"evidence root must be fresh: {evidence_root}")
    evidence_root.mkdir(parents=True)
    local_app_data = test_root / "Local App Data"
    python = application / "Runtime" / "Python" / "python.exe"
    environment = os.environ.copy()
    environment.update({
        "PYTHONUTF8": "1",
        "LOCALAPPDATA": str(local_app_data),
        "USERPROFILE": str(test_root / "User Name"),
    })
    process = subprocess.Popen(
        [str(python), "-I", "-m", "app.packaging.packaged_desktop_launcher",
         "--application-root", str(application), "--local-app-data", str(local_app_data),
         "--user-profile", str(test_root / "User Name")],
        cwd=application / "Backend", env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    try:
        line = ""
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and process.poll() is None:
            line = process.stdout.readline().strip()
            if line.startswith("APPLICATION_READY "):
                break
        if not line.startswith("APPLICATION_READY "):
            error = process.stderr.read() if process.poll() is not None else "readiness timeout"
            raise RuntimeError(error[-3000:])
        metadata = json.loads(line.removeprefix("APPLICATION_READY "))
        with urllib.request.urlopen(metadata["frontend_origin"] + "/", timeout=3) as response:
            frontend = response.status == 200 and b'id="root"' in response.read()
        window = _find_window(int(metadata["desktop_host_pid"]))
        captures = [
            _capture(window, evidence_root / f"desktophost-{width}x{height}.png", width, height)
            for width, height in WINDOW_SIZES
        ]
        public, addresses = _listener_evidence({metadata["database_port"], metadata["backend_port"]})
        result = {
            "application_ready": True,
            "desktop_host_started": True,
            "frontend": frontend,
            "version": metadata["application_version"],
            "listener_addresses": addresses,
            "public_listeners": public,
            "captures": captures,
        }
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        forbidden = ("bootstrap_secret", "session_token", "ownership_nonce", "DEEPSEEK_KEY_SENTINEL")
        result["secret_exposure"] = sum(serialized.count(value) for value in forbidden)
        (evidence_root / "desktophost-visual-evidence.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if frontend and public == 0 and result["secret_exposure"] == 0 else 1
    finally:
        if process.poll() is None:
            process.send_signal(getattr(subprocess, "CTRL_BREAK_EVENT", 1))
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
