"""Run only an explicit MOCK_ONLY local fixture. No app startup/import side effect."""
from __future__ import annotations
import argparse
import socket
import uvicorn
from app.local_interop.synthetic_tutor import create_synthetic_tutor_app


def main():
    parser = argparse.ArgumentParser(description="MOCK_ONLY local synthetic Tutor")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("invalid loopback port")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", args.port))
    sock.listen(16)
    print(f"MOCK_ONLY_ENDPOINT=http://127.0.0.1:{sock.getsockname()[1]}", flush=True)
    config = uvicorn.Config(create_synthetic_tutor_app(), host="127.0.0.1", access_log=False,
                            log_level="error", proxy_headers=False)
    try:
        uvicorn.Server(config).run(sockets=[sock])
    finally:
        sock.close()


if __name__ == "__main__":
    main()
