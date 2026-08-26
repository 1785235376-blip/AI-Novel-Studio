from __future__ import annotations

import http.server
import msvcrt
import os
import secrets
import subprocess
import tempfile
import threading
from pathlib import Path


class Server(http.server.ThreadingHTTPServer):
    def __init__(self, address, handler, expected: str, wrong_origin: str = ""):
        super().__init__(address, handler)
        self.expected = expected
        self.wrong_origin = wrong_origin
        self.match = False
        self.leak = False


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        token = self.headers.get("X-Session-Token")
        self.server.match |= token == self.server.expected
        self.server.leak |= token is not None and token == self.server.expected
        if self.path == "/" and self.server.wrong_origin:
            body = f'<html><body><img src="{self.server.wrong_origin}/probe"></body></html>'.encode()
            content_type = "text/html"
        else:
            body = b"ok"
            content_type = "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    exe = root / "tests/desktop_host_webview2_t4_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe"
    token = secrets.token_urlsafe(64)
    wrong = Server(("127.0.0.1", 0), Handler, token)
    wrong_origin = f"http://127.0.0.1:{wrong.server_port}"
    main_server = Server(("127.0.0.1", 0), Handler, token, wrong_origin)
    origin = f"http://127.0.0.1:{main_server.server_port}"
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (main_server, wrong)]
    for thread in threads:
        thread.start()

    observer_r, observer_w = os.pipe()
    session_r, session_w = os.pipe()
    os.set_inheritable(observer_w, True)
    os.set_inheritable(session_r, True)
    observer_handle = msvcrt.get_osfhandle(observer_w)
    session_handle = msvcrt.get_osfhandle(session_r)
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": [observer_handle, session_handle]}
    with tempfile.TemporaryDirectory(prefix="ai-novel-h1-profile-", ignore_cleanup_errors=True) as profile:
        child = subprocess.Popen(
            [str(exe), "--frontend-root", str(root / "frontend/dist"),
             "--observer-handle", str(observer_handle), "--session-handle", str(session_handle),
             "--real-origin", origin, "--profile-root", profile, "--scenario", "REAL_PACKAGED"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            close_fds=True, startupinfo=startup,
        )
        os.close(observer_w)
        os.close(session_r)
        encoded = token.encode()
        os.write(session_w, len(encoded).to_bytes(4, "little") + encoded)
        os.close(session_w)
        stdout, stderr = child.communicate(timeout=30)
    os.close(observer_r)
    for server in (main_server, wrong):
        server.shutdown()
        server.server_close()
    ok = child.returncode == 0 and main_server.match and not wrong.leak and token not in stdout + stderr
    print("EXTERNAL_TEST_ORIGIN=" + ("YES" if main_server.match else "NO"))
    print("MATCHING_ORIGIN_SESSION_HEADER_MATCH=" + ("YES" if main_server.match else "NO"))
    print("WRONG_ORIGIN_SESSION_HEADER=" + ("ABSENT" if not wrong.leak else "PRESENT"))
    print("SESSION_SENTINEL_OUTPUT=" + ("0" if token not in stdout + stderr else "1"))
    print("H1_RUNTIME=" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
