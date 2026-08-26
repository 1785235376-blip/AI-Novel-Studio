from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from .desktop_bridge import DesktopHostLaunch
from .runtime_identity import RuntimeIdentity, RuntimeRole, validate_process_ownership
from .host_uplink import parse_host_ping


class PackagedDesktopHost:
    def __init__(self, *, application: Path, runtime: RuntimeIdentity, inspector, job):
        self.executable = (application / "DesktopHost" / "AI-Novel-Studio.DesktopHost.exe").resolve()
        if not self.executable.is_file():
            raise RuntimeError("应用窗口组件不完整，请重新安装 AI-Novel-Studio。")
        self.runtime = runtime
        self.inspector = inspector
        self.job = job
        self.process: subprocess.Popen[str] | None = None
        self.identity = None
        self._output: queue.Queue[str] = queue.Queue()
        self.failure_code: str | None = None
        self.status_file: Path | None = None

    def start(self, launch: DesktopHostLaunch) -> None:
        self.status_file = Path(launch.webview_profile_directory) / "host.status"
        self.status_file.unlink(missing_ok=True)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["PACKAGED_HOST_STATUS_FILE"] = str(self.status_file)
        # The packaged launcher may run with an isolated LOCALAPPDATA during
        # acceptance checks.  Pass the already-owned WebView2 root explicitly
        # so the native host does not have to infer it from Win32 special-folder
        # APIs (which can ignore an overridden LOCALAPPDATA value).
        environment["PACKAGED_HOST_WEBVIEW_ROOT"] = str(
            Path(launch.webview_profile_directory).resolve().parent
        )
        self.process = subprocess.Popen(
            [str(self.executable)], cwd=self.executable.parent,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        self.inspector.register(self.process.pid, RuntimeRole.DESKTOP_HOST, self.runtime)
        self.identity = self.inspector.inspect(self.process.pid)
        validate_process_ownership(self.identity, self.identity, self.runtime)
        self.job.assign_pid(self.process.pid)
        envelope = {
            "frontend_origin": launch.frontend_origin,
            "backend_origin": launch.backend_origin,
            "runtime_instance_id": launch.runtime_instance_id,
            "bootstrap_secret": launch.bootstrap_secret,
            "webview_profile_directory": launch.webview_profile_directory,
        }
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            self._output.put(line.strip())

    def wait_session_ready(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while self.is_running() and time.monotonic() < deadline:
            if self.status_file is not None and self.status_file.is_file():
                status = self.status_file.read_text(encoding="ascii", errors="replace").strip()
                if status == "DESKTOP_SESSION_READY":
                    return True
                if status.startswith("DESKTOP_"):
                    self.failure_code = status
                    return False
            try:
                output = self._output.get(timeout=min(0.25, deadline - time.monotonic()))
                if output == "DESKTOP_SESSION_READY":
                    return True
                if output.startswith("DESKTOP_"):
                    self.failure_code = output
                    return False
            except queue.Empty:
                pass
        return False


    def block_actions(self) -> None:
        """Host protocol has no BLOCK frame; fail closed by withholding actions.

        The native host is only sent the documented CLOSE frame.  Until a
        versioned BLOCK command exists, the Python side performs no privileged
        action and does not invent an unsupported stdin message.
        """
        return None

    def close(self) -> None:
        if not self.is_running():
            return
        assert self.process is not None and self.process.stdin is not None
        self.process.stdin.write("CLOSE\n")
        self.process.stdin.flush()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            actual = self.inspector.inspect(self.process.pid)
            validate_process_ownership(self.identity, actual, self.runtime)
            self.process.terminate()
            self.process.wait(timeout=5)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def drain_valid_control_pings(self) -> int:
        count = 0
        while True:
            try:
                line = self._output.get_nowait()
            except queue.Empty:
                return count
            if parse_host_ping(line, self.runtime.runtime_instance_id):
                count += 1

    def drain_valid_control_messages(self) -> tuple[int, list[str]]:
        """Drain host output once, preserving credential frames for the launcher."""
        pings = 0
        credentials: list[str] = []
        while True:
            try:
                line = self._output.get_nowait()
            except queue.Empty:
                return pings, credentials
            if parse_host_ping(line, self.runtime.runtime_instance_id):
                pings += 1
            elif line.startswith("AI_NOVEL_HOST_CREDENTIAL_V1\t"):
                credentials.append(line)
