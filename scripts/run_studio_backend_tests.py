"""Run File/Mock backend checks with isolated settings and no external network.

Loopback is retained for Windows asyncio's socketpair and actual local HTTP
acceptance. This runner never selects a real model or database provider.
"""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import socket
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    run = Path(os.environ.get("STUDIO_TEST_RUN_ROOT", root / ".runtime/studio-backend-tests")).resolve()
    for folder in ("home", "xdg/config", "xdg/cache", "xdg/data", "data", "tmp", "appdata", "localappdata"):
        (run / folder).mkdir(parents=True, exist_ok=True)
    for key in tuple(os.environ):
        if key.endswith("_API_KEY") or key in {
            "DATABASE_URL", "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL"
        }:
            os.environ.pop(key, None)
    os.environ.update(
        PROJECT_ROOT=str(root), PYTHONPATH=str(root), HOME=str(run / "home"),
        USERPROFILE=str(run / "home"), APPDATA=str(run / "appdata"),
        LOCALAPPDATA=str(run / "localappdata"), XDG_CONFIG_HOME=str(run / "xdg/config"),
        XDG_CACHE_HOME=str(run / "xdg/cache"), XDG_DATA_HOME=str(run / "xdg/data"),
        NOVEL_DATA_PATH=str(run / "data"), TMPDIR=str(run / "tmp"),
        TMP=str(run / "tmp"), TEMP=str(run / "tmp"), STORAGE_BACKEND="file",
        CREDENTIAL_VAULT_BACKEND="memory", MOCK_PROVIDER="true",
        ENABLE_PACKAGED_RUNTIME="false", ENABLE_CLOUD="false", CREATION_PROFILE="LOCAL_ONLY",
    )
    os.chdir(root)
    sys.path[:0] = [str(root), str(root / "tests")]

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def require_loopback(host):
        if host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise RuntimeError("external network blocked by isolated File/Mock test runner")

    def connect(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address[0])
        return original_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        if host is not None:
            require_loopback(host)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    from app.config import settings
    assert settings.mock_provider and not settings.enable_cloud and not settings.enable_packaged_runtime
    print("STUDIO_BACKEND_TEST_MODE File/Mock; external network blocked; local loopback allowed", flush=True)
    import pytest
    return pytest.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
