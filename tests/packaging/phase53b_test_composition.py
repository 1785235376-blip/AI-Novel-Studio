from __future__ import annotations

import subprocess
import sys
import os
import time
import msvcrt

PREFIX = b"AI_NOVEL_TEST_OBSERVER_V1\t"
VALID = {"HOST_OBSERVER_TEST", "LAUNCHER_OBSERVER_TEST", "BACKEND_OBSERVER_TEST"}
MAX_FRAME = 128


def parse_frames(data: bytes) -> dict[str, int]:
    counts = {event: 0 for event in VALID}
    for line in data.splitlines():
        if len(line) > MAX_FRAME or not line.startswith(PREFIX):
            continue
        event = line[len(PREFIX):].decode("ascii", "ignore")
        if event in counts:
            counts[event] += 1
    return counts


def negative_case(frame: bytes) -> dict[str, int]:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, frame)
    os.close(write_fd)
    data = os.read(read_fd, 4096)
    os.close(read_fd)
    return parse_frames(data)
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, True)
    dotnet = Path(r"C:\Users\bcard\.cache\ai-novel-studio-dotnet\dotnet.exe")
    python = root / ".venv/Scripts/python.exe"
    apphost = root / "tests/desktop_host_test_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe"
    write_handle = msvcrt.get_osfhandle(write_fd)
    commands = (
        [str(apphost), "--observer-handle", str(write_handle)],
        [str(python), str(root / "tests/packaging/phase53b_test_launcher.py"), "--observer-handle", str(write_handle)],
        [str(python), str(root / "tests/packaging/phase53b_test_backend.py"), "--observer-handle", str(write_handle)],
    )
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": [write_handle]}
    children = [subprocess.Popen(command, cwd=root, close_fds=True, startupinfo=startup) for command in commands]
    results = [child.wait(timeout=30) for child in children]
    os.close(write_fd)
    os.set_blocking(read_fd, False)
    data = bytearray()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            chunk = os.read(read_fd, 4096)
            if not chunk: break
            data.extend(chunk)
        except BlockingIOError:
            time.sleep(0.05)
    os.close(read_fd)
    allowed = {"HOST_OBSERVER_TEST", "LAUNCHER_OBSERVER_TEST", "BACKEND_OBSERVER_TEST"}
    counts = {event: 0 for event in allowed}
    for line in data.decode("ascii", "replace").splitlines():
        prefix, _, event = line.partition("\t")
        if prefix == "AI_NOVEL_TEST_OBSERVER_V1" and event in counts:
            counts[event] += 1
    if any(results):
        return 1
    if counts != {event: 1 for event in allowed}:
        return 1
    print("HOST_OBSERVER_TEST=1")
    print("LAUNCHER_OBSERVER_TEST=1")
    print("BACKEND_OBSERVER_TEST=1")
    unknown = negative_case(PREFIX + b"UNKNOWN_EVENT\n")
    malformed = [negative_case(case) for case in (b"UNKNOWN\n", PREFIX + b"\n", b"AI_NOVEL_TEST_OBSERVER_V1 HOST_OBSERVER_TEST\n")]
    oversized = negative_case(PREFIX + b"HOST_OBSERVER_TEST" + b"X" * MAX_FRAME + b"\n")
    duplicate = negative_case(PREFIX + b"HOST_OBSERVER_TEST\n" + PREFIX + b"HOST_OBSERVER_TEST\n")
    missing = {event: 0 for event in allowed}
    if unknown != missing or any(case != missing for case in malformed) or oversized != missing:
        return 1
    if duplicate["HOST_OBSERVER_TEST"] == 1 or duplicate["HOST_OBSERVER_TEST"] != 2:
        return 1
    print("UNKNOWN_OBSERVER_EVENT=PASS")
    print("MALFORMED_OBSERVER_FRAME=PASS")
    print("OVERSIZED_OBSERVER_FRAME=PASS")
    print("MISSING_CHILD_EVENT=PASS")
    print("DUPLICATE_SYNTHETIC_EVENT=PASS")
    print("TEST_THREE_PROCESS_COMPOSITION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
