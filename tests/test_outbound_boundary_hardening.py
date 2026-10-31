"""Independent regression coverage for the outbound boundaries hardened on
2026-10-30.

Two production paths are covered here, deliberately without claiming to replace
any packaged/real-network acceptance:

1. Operator-supplied provider endpoints (asset/audio/video configuration) must
   never name link-local, multicast, unspecified or reserved transports. Cloud
   metadata (``169.254.169.254``) and its legacy numeric spellings are the
   concrete external-request risk this admission check removes.
2. The *returned-media* boundary in ``app.media_files`` is exercised directly.
   The older P0 regression test only calls ``app.net_safety.validate_outbound_url``
   (no production caller); these tests bind the same rejection matrix to the
   function that actually fetches bytes.
"""
from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

from app.net_safety import ProviderEndpointRejected, validate_provider_endpoint


# ---------------------------------------------------------------------------
# 1. Provider endpoint admission
# ---------------------------------------------------------------------------

RESTRICTED_PROVIDER_ENDPOINTS = (
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.0.1/v1",
    "http://[fe80::1]/v1",
    "http://0.0.0.0/v1",
    "http://[::]/v1",
    "http://224.0.0.1/v1",
    "http://[ff02::1]/v1",
    "http://240.0.0.1/v1",
    # Legacy numeric spellings resolved by the OS to a restricted address.
    "http://2852039166/v1",
    "http://0xA9FEA9FE/v1",
    "http://169.254.169.254./v1",
)

ALLOWED_PROVIDER_ENDPOINTS = (
    "http://127.0.0.1:8188",
    "http://[::1]:8188/v1",
    "http://localhost:11434/v1",
    "http://192.168.1.20:7860/v1",
    "http://10.0.0.5:8001/v1",
    "https://api.openai.com/v1",
    "https://custom.example.test/v1",
    "http://[::ffff:127.0.0.1]:8188/v1",
)


@pytest.mark.parametrize("endpoint", RESTRICTED_PROVIDER_ENDPOINTS)
def test_provider_endpoint_rejects_restricted_transports(endpoint):
    with pytest.raises(ProviderEndpointRejected):
        validate_provider_endpoint(endpoint)


@pytest.mark.parametrize("endpoint", ALLOWED_PROVIDER_ENDPOINTS)
def test_provider_endpoint_keeps_local_and_public_services(endpoint):
    assert validate_provider_endpoint(endpoint) == endpoint


# ``socket.getaddrinfo`` applies the idna codec before resolution, so these
# lookalike spellings reach the same link-local metadata address as the ASCII
# literal. Admission must mirror the resolver instead of only inspecting the
# literal characters supplied by the caller.
IDNA_RESTRICTED_PROVIDER_ENDPOINTS = (
    "http://１69.254.169.254/v1",
    "http://１６９.２５４.１６９.２５４/v1",
    "http://１６９.２５４.１６９.２５４/v1",
    "http://169\uff0e254\uff0e169\uff0e254/v1",
)


def test_provider_endpoint_rejects_lookalike_trailing_separator():
    # IDNA maps the fullwidth full stop, so the normalized host still names the
    # restricted literal even though this spelling is not resolvable verbatim.
    with pytest.raises(ProviderEndpointRejected):
        validate_provider_endpoint("http://169.254.169.254\uff0e/v1")


@pytest.mark.parametrize("endpoint", IDNA_RESTRICTED_PROVIDER_ENDPOINTS)
def test_provider_endpoint_rejects_idna_normalized_restricted_address(endpoint):
    host = urlsplit(endpoint).hostname
    resolved = {item[4][0] for item in socket.getaddrinfo(host, 80, type=socket.SOCK_STREAM)}
    # The operating-system resolver really maps the lookalike host to metadata.
    assert resolved == {"169.254.169.254"}
    with pytest.raises(ProviderEndpointRejected):
        validate_provider_endpoint(endpoint)


def test_provider_endpoint_keeps_public_idn_host():
    endpoint = "https://例子.测试/v1"
    assert validate_provider_endpoint(endpoint) == endpoint


@pytest.mark.parametrize("endpoint", [
    "file:///tmp/provider", "ftp://example.test/v1", "http://user:pass@127.0.0.1/v1",
    "http://127.0.0.1/v1#fragment", "http://", "",
])
def test_provider_endpoint_rejects_invalid_url_shapes(endpoint):
    with pytest.raises(ProviderEndpointRejected):
        validate_provider_endpoint(endpoint)


def test_asset_provider_config_rejects_metadata_endpoint_without_writing(tmp_path, monkeypatch):
    from app import asset_provider_config

    path = tmp_path / "asset-providers.json"
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))
    with pytest.raises(ValueError):
        asset_provider_config.save("custom", "http://169.254.169.254/v1", "m")
    assert not path.exists()

    saved = asset_provider_config.save("local-comfy", "http://127.0.0.1:8188", "")
    assert saved["endpoint"] == "http://127.0.0.1:8188"
    assert json.loads(path.read_text(encoding="utf-8"))["local-comfy"]["endpoint"] == "http://127.0.0.1:8188"


def test_audio_provider_config_rejects_metadata_endpoint_without_writing(tmp_path, monkeypatch):
    from app import audio_provider_config

    path = tmp_path / "audio-providers.json"
    monkeypatch.setenv("AUDIO_PROVIDER_CONFIG_PATH", str(path))
    with pytest.raises(ValueError):
        audio_provider_config.save("probe-voice", endpoint="http://[fe80::1]/v1", default_model="m",
                                   display_name="d", local=True, enabled=True,
                                   requires_credential=False, capabilities=["TTS"])
    assert not path.exists()


def test_video_provider_config_model_rejects_restricted_endpoint():
    from app.api import VideoProviderConfigIn

    with pytest.raises(ValueError):
        VideoProviderConfigIn(endpoint="http://169.254.169.254/v1", model_id="video")
    accepted = VideoProviderConfigIn(endpoint="http://127.0.0.1:8189", model_id="video")
    assert accepted.endpoint == "http://127.0.0.1:8189"


def test_asset_provider_http_route_refuses_metadata_endpoint(tmp_path, monkeypatch):
    """The mounted route maps the same refusal to its existing 400 contract."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app import api

    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "asset-providers.json"))
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    client = TestClient(application)
    response = client.put("/api/asset-providers/custom", json={
        "endpoint": "http://169.254.169.254/v1", "default_model": "m", "api_style": "openai",
        "local": False, "enabled": True, "requires_credential": False, "display_name": "probe",
    })
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PROVIDER_CONFIG"
    assert not (tmp_path / "asset-providers.json").exists()


def test_asset_provider_http_route_refuses_idna_metadata_endpoint(tmp_path, monkeypatch):
    """The HTTP contract rejects a resolver-equivalent lookalike endpoint too."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app import api

    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "asset-providers.json"))
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    client = TestClient(application)
    response = client.put("/api/asset-providers/custom", json={
        "endpoint": "http://１69.254.169.254/v1", "default_model": "m", "api_style": "openai",
        "local": False, "enabled": True, "requires_credential": False, "display_name": "probe",
    })
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PROVIDER_CONFIG"
    assert not (tmp_path / "asset-providers.json").exists()


def test_hand_edited_asset_config_cannot_register_restricted_endpoint(tmp_path, monkeypatch):
    from app import dependencies

    path = tmp_path / "asset-providers.json"
    path.write_text(json.dumps({"custom": {
        "endpoint": "http://169.254.169.254/v1", "default_model": "m", "api_style": "openai",
        "local": False, "enabled": True, "requires_credential": False, "display_name": "hand-edited",
    }}), encoding="utf-8")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))
    monkeypatch.setattr(dependencies, "credential_vault", _AllowAllVault())
    assert dependencies.refresh_asset_provider("custom") is False


class _AllowAllVault:
    def has(self, provider):
        return True

    def resolve(self, provider):
        return "synthetic"


def test_hand_edited_audio_config_is_skipped_before_adapter_construction(monkeypatch):
    from app import audio_providers

    monkeypatch.setattr(audio_providers, "provider_catalog", lambda: [{
        "provider_id": "probe-voice", "endpoint": "http://169.254.169.254/v1",
        "default_model": "m", "capabilities": ["TTS"], "requires_credential": False,
        "local": True, "priority": 1,
    }])
    with pytest.raises(ValueError):
        audio_providers.resolve_provider("probe-voice", "TTS", _AllowAllVault(), _RejectTransport())


class _RejectTransport:
    def get(self, *args, **kwargs):
        raise AssertionError("restricted provider endpoint must not be dialed")

    post = get


# ---------------------------------------------------------------------------
# 2. Returned-media (production fetch) boundary
# ---------------------------------------------------------------------------

class _MediaHandler(BaseHTTPRequestHandler):
    response_status = 200
    response_headers: dict[str, str] = {}
    response_body = b"synthetic"

    def do_GET(self):
        self.send_response(self.response_status)
        for key, value in self.response_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(self.response_body)))
        self.end_headers()
        self.wfile.write(self.response_body)

    def log_message(self, *_args):
        return


@pytest.fixture
def media_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MediaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _resolver(address):
    def getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, int(port or 80)))]

    return getaddrinfo


RESTRICTED_MEDIA_URLS = (
    ("http://127.0.0.1/x", "127.0.0.1"),
    ("http://169.254.169.254/latest", "169.254.169.254"),
    ("http://10.0.0.1/x", "10.0.0.1"),
    ("http://192.168.1.1/x", "192.168.1.1"),
    ("http://0.0.0.0/x", "0.0.0.0"),
    ("http://224.0.0.1/x", "224.0.0.1"),
    ("http://[::1]/x", "::1"),
    ("http://[fe80::1]/x", "fe80::1"),
)


@pytest.mark.parametrize(("url", "address"), RESTRICTED_MEDIA_URLS)
def test_media_destination_rejects_restricted_addresses_without_configured_origin(monkeypatch, url, address):
    from app import media_files

    monkeypatch.setattr(media_files.socket, "getaddrinfo", _resolver(address))
    with pytest.raises(media_files.OutboundURLRejected):
        media_files.media_destination(url)


def test_media_destination_accepts_public_address(monkeypatch):
    from app import media_files

    monkeypatch.setattr(media_files.socket, "getaddrinfo", _resolver("93.184.216.34"))
    parsed, origin, address = media_files.media_destination("https://example.test/image.png")
    assert address == "93.184.216.34"
    assert origin[0] == "https"


def test_media_destination_limits_local_provider_to_exact_origin(media_server, monkeypatch):
    from app import media_files

    monkeypatch.setattr(media_files.socket, "getaddrinfo", _resolver("127.0.0.1"))
    media_files.media_destination(media_server + "/view?filename=a.png", configured_provider_endpoint=media_server)
    with pytest.raises(media_files.OutboundURLRejected):
        # A different loopback port is not the configured provider origin.
        media_files.media_destination("http://127.0.0.1:1/view", configured_provider_endpoint=media_server)
    with pytest.raises(media_files.OutboundURLRejected):
        # A hostname alias for the same address is a different origin.
        media_files.media_destination("http://localhost:1/view", configured_provider_endpoint=media_server)


def test_media_destination_rejects_embedded_credentials_and_fragments():
    from app import media_files

    for url in ("http://user:pass@93.184.216.34/x", "http://93.184.216.34/x#frag", "ftp://93.184.216.34/x"):
        with pytest.raises(media_files.OutboundURLRejected):
            media_files.media_destination(url)


def test_fetch_media_bytes_rejects_redirect_responses(media_server, monkeypatch):
    from app import media_files

    monkeypatch.setattr(media_files.socket, "getaddrinfo", _resolver("127.0.0.1"))
    _MediaHandler.response_status = 302
    _MediaHandler.response_headers = {"Location": "http://169.254.169.254/latest"}
    _MediaHandler.response_body = b""
    try:
        with pytest.raises(media_files.OutboundURLRejected):
            media_files.fetch_media_bytes(media_server + "/redirect", 1024, timeout=5,
                                          configured_provider_endpoint=media_server)
    finally:
        _MediaHandler.response_status = 200
        _MediaHandler.response_headers = {}
        _MediaHandler.response_body = b"synthetic"


def test_fetch_media_bytes_rejects_compressed_and_serve_identity_body(media_server, monkeypatch):
    from app import media_files

    monkeypatch.setattr(media_files.socket, "getaddrinfo", _resolver("127.0.0.1"))
    _MediaHandler.response_headers = {"Content-Encoding": "gzip"}
    try:
        with pytest.raises(media_files.OutboundURLRejected):
            media_files.fetch_media_bytes(media_server + "/gzip", 1024, timeout=5,
                                          configured_provider_endpoint=media_server)
    finally:
        _MediaHandler.response_headers = {}
    assert media_files.fetch_media_bytes(media_server + "/ok", 1024, timeout=5,
                                         configured_provider_endpoint=media_server) == b"synthetic"


def test_image_job_reference_url_is_fenced_before_job_creation(monkeypatch):
    """The mounted image-job route must reject restricted reference URLs before
    it creates a durable job or reaches any provider adapter."""
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import api, dependencies

    created_jobs = []

    class NovelOwner:
        def get(self, nid):
            return {"id": nid}

    class JobOwner:
        def create(self, *args, **kwargs):
            created_jobs.append((args, kwargs))
            raise AssertionError("restricted reference URL must be refused before job creation")

    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=False))
    monkeypatch.setattr(dependencies, "repositories", SimpleNamespace(novels=NovelOwner()))
    monkeypatch.setattr(api.image_job_service, "create", JobOwner().create, raising=False)
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    client = TestClient(application)
    for reference in ("http://169.254.169.254/latest", "http://127.0.0.1:1/x",
                      "http://[fe80::1]/x"):
        response = client.post("/api/novels/synthetic-project/image-jobs", json={
            "provider_id": "automatic1111", "model_id": "m", "prompt": "synthetic",
            "images": [reference],
        })
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == "IMAGE_JOB_INVALID"
        # The refusal must not echo the restricted target back to the caller.
        assert "169.254" not in response.text and "127.0.0.1" not in response.text
    assert created_jobs == []
