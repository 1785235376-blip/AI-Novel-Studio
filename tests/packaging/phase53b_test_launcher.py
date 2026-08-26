import sys
import os
import msvcrt
import argparse
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.packaging.host_uplink import encode_host_ping, parse_host_ping
from app.packaging.packaged_processes import PackagedProcessFactory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-handle", type=int)
    args = parser.parse_args()
    if args.observer_handle is not None:
        os.write(msvcrt.open_osfhandle(args.observer_handle, 0), b"AI_NOVEL_TEST_OBSERVER_V1\tLAUNCHER_OBSERVER_TEST\n")
    runtime_id = "test-composition-runtime"
    if not parse_host_ping(encode_host_ping(runtime_id), runtime_id):
        return 1
    if args.observer_handle is not None:
        factory = PackagedProcessFactory.__new__(PackagedProcessFactory)
        factory._runtime_instance_id = runtime_id
        factory.backend_control_writer = io.BytesIO()
        def observed(stage: str) -> None:
            if stage != "A1_PING_FORWARDED_FROM_WEBVIEW": raise RuntimeError()
            os.write(msvcrt.open_osfhandle(args.observer_handle, 0), b"AI_NOVEL_TEST_ATTRIBUTION_V1\tA1_PING_FORWARDED_FROM_WEBVIEW\n")
        if not factory.forward_backend_ping(runtime_id, observer=observed):
            return 1
    print("TEST_LAUNCHER_START=PASS")
    print("TEST_LAUNCHER_EXIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
