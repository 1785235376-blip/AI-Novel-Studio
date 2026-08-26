import io
import os
import msvcrt
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.packaging.control_pipe import PackagedControlReader, encode_ping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-handle", type=int)
    args = parser.parse_args()
    if args.observer_handle is not None:
        os.write(msvcrt.open_osfhandle(args.observer_handle, 0), b"AI_NOVEL_TEST_OBSERVER_V1\tBACKEND_OBSERVER_TEST\n")
    runtime_id = "test-composition-runtime"
    def observed(stage: str) -> None:
        if stage != "BACKEND_PING_ACCEPTED_FROM_WEBVIEW": raise RuntimeError()
        if args.observer_handle is not None:
            os.write(msvcrt.open_osfhandle(args.observer_handle, 0), b"AI_NOVEL_TEST_ATTRIBUTION_V1\tBACKEND_PING_ACCEPTED_FROM_WEBVIEW\n")
    reader = PackagedControlReader(runtime_id, io.BytesIO(encode_ping(runtime_id)), observer=observed)
    reader._read()
    if reader.ping_count != 1:
        return 1
    print("TEST_BACKEND_START=PASS")
    print("TEST_BACKEND_EXIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
