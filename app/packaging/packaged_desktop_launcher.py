from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

from .desktop_bridge import DesktopHostLaunch
from .packaged_desktop_host import PackagedDesktopHost
from .packaged_launcher import _install_stop_handlers, create_packaged_backend_runtime
from .paths import WindowsPackagingPaths
from .runtime_identity import RuntimeRole


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-root", type=Path)
    parser.add_argument("--local-app-data", type=Path)
    parser.add_argument("--user-profile", type=Path)
    args = parser.parse_args()
    paths = None
    if args.local_app_data is not None or args.user_profile is not None:
        if args.local_app_data is None or args.user_profile is None:
            parser.error("both packaged path roots are required")
        paths = WindowsPackagingPaths.resolve(
            local_app_data=args.local_app_data, user_profile=args.user_profile,
        )
    runtime, factory = create_packaged_backend_runtime(application=args.application_root, paths=paths)
    stopping = False
    host = None

    def request_stop(*_args) -> None:
        nonlocal stopping
        stopping = True

    _install_stop_handlers(request_stop)
    try:
        identity = runtime.startup()
        assert runtime.reservations is not None
        port = runtime.reservations.ports[RuntimeRole.BACKEND]
        origin = f"http://127.0.0.1:{port}"
        host = PackagedDesktopHost(
            application=factory.config.layout.application, runtime=identity,
            inspector=runtime.inspector, job=runtime.job,
        )
        host.start(DesktopHostLaunch(
            frontend_origin=origin, backend_origin=origin,
            runtime_instance_id=identity.runtime_instance_id,
            bootstrap_secret=factory.take_bootstrap_secret(),
            webview_profile_directory=str(
                factory.config.paths.cache / "WebView2" / identity.runtime_instance_id
            ),
        ))
        if not host.wait_session_ready(90):
            if host.failure_code:
                print(host.failure_code, file=sys.stderr, flush=True)
            raise RuntimeError("本地安全会话初始化失败，请关闭程序后重新打开。")
        metadata = factory.config.public_runtime_metadata(
            database_port=runtime.reservations.ports[RuntimeRole.POSTGRESQL], backend_port=port,
        )
        metadata.update({"frontend_origin": origin, "desktop_host_pid": host.process.pid})
        print("APPLICATION_READY " + json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        sys.stdout.flush()
        while not stopping and host.is_running():
            pings, credentials = host.drain_valid_control_messages()
            for _ in range(pings):
                factory.forward_backend_ping(identity.runtime_instance_id)
            for frame in credentials:
                factory.forward_backend_credential(frame)
            if runtime.check_for_child_crash() is not None:
                return 2
            time.sleep(0.25)
        return 0 if stopping else 2
    finally:
        if host is not None:
            host.block_actions()
            host.close()
        runtime.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
