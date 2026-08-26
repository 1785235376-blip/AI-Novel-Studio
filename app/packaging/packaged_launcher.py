from __future__ import annotations

import json
import argparse
import signal
import sys
import time
from pathlib import Path

from .packaged_processes import PackagedProcessConfig, PackagedProcessFactory
from .paths import WindowsPackagingPaths
from .runtime_identity import RuntimeRole
from .runtime_lifecycle import DefaultPortAllocator, RuntimeLifecycle
from .windows_primitives import (
    WindowsJobObject,
    WindowsNamedMutex,
    WindowsProcessInspector,
    product_mutex_name,
)


def packaged_application_root() -> Path:
    # <ApplicationRoot>/Backend/app/packaging/packaged_launcher.py
    return Path(__file__).resolve().parents[3]


def create_packaged_backend_runtime(
    *, application: Path | None = None, paths: WindowsPackagingPaths | None = None,
    mutex=None, job=None, inspector=None, port_allocator=None,
) -> tuple[RuntimeLifecycle, PackagedProcessFactory]:
    resolved_paths = paths or WindowsPackagingPaths.resolve()
    config = PackagedProcessConfig.create(application or packaged_application_root(), resolved_paths)
    process_inspector = inspector or WindowsProcessInspector()
    factory = PackagedProcessFactory(config, process_inspector)
    lifecycle = RuntimeLifecycle(
        paths=resolved_paths,
        mutex=mutex or WindowsNamedMutex(product_mutex_name()),
        job=job or WindowsJobObject(),
        port_allocator=port_allocator or DefaultPortAllocator(),
        process_factory=factory,
        inspector=process_inspector,
        startup_order=(RuntimeRole.POSTGRESQL, RuntimeRole.BACKEND),
    )
    return lifecycle, factory


def _install_stop_handlers(handler) -> None:
    handled_signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        handled_signals.append(signal.SIGBREAK)
    for handled_signal in handled_signals:
        signal.signal(handled_signal, handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-root", type=Path)
    parser.add_argument("--local-app-data", type=Path)
    parser.add_argument("--user-profile", type=Path)
    args = parser.parse_args()
    custom_paths = None
    if args.local_app_data is not None or args.user_profile is not None:
        if args.local_app_data is None or args.user_profile is None:
            parser.error("both packaged path roots are required")
        custom_paths = WindowsPackagingPaths.resolve(
            local_app_data=args.local_app_data, user_profile=args.user_profile,
        )
    lifecycle, factory = create_packaged_backend_runtime(
        application=args.application_root, paths=custom_paths,
    )
    stopping = False

    def request_stop(*_args) -> None:
        nonlocal stopping
        stopping = True

    _install_stop_handlers(request_stop)
    try:
        identity = lifecycle.startup()
        assert lifecycle.reservations is not None
        metadata = factory.config.public_runtime_metadata(
            database_port=lifecycle.reservations.ports[RuntimeRole.POSTGRESQL],
            backend_port=lifecycle.reservations.ports[RuntimeRole.BACKEND],
        )
        metadata["runtime_instance_id"] = identity.runtime_instance_id
        print("PACKAGED_BACKEND_READY " + json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        sys.stdout.flush()
        while not stopping:
            if lifecycle.check_for_child_crash() is not None:
                return 2
            time.sleep(0.25)
        return 0
    finally:
        lifecycle.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
