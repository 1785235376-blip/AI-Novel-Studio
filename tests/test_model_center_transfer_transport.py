"""Transport contracts exercise DNS, socket and TLS fakes only; no listeners."""
from __future__ import annotations

import socket
import ssl
import threading

import pytest

from app.model_center import transfer_transport as transport
from app.model_center.transfer_transport import HttpsTransferTransport, TransferTransportError


URL = "https://models.example/artifact.gguf"
PUBLIC = "93.184.216.34"


def record(address=PUBLIC, port=443):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
    return family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr


def wire(status=200, headers=None, body=b"model"):
    headers = [("Content-Length", str(len(body))), ("ETag", '"v1"')] if headers is None else headers
    return (f"HTTP/1.1 {status} response\r\n" + "".join(f"{key}: {value}\r\n" for key, value in headers)
            + "\r\n").encode("latin-1") + body


class FakeSocket:
    def __init__(self, network, family, kind, protocol):
        self.network = network
        self.family = family
        self.kind = kind
        self.protocol = protocol
        self.chunks = list(network.chunks)
        self.requests = bytearray()
        self.closed = False
        self.address = None
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, address):
        self.address = address
        self.network.event("connect")

    def send(self, value):
        self.network.event("send")
        self.requests.extend(value)
        return len(value)

    def recv_into(self, buffer):
        self.network.event("receive")
        if not self.chunks:
            return 0
        part = self.chunks.pop(0)
        size = min(len(buffer), len(part))
        buffer[:size] = part[:size]
        if len(part) > size:
            self.chunks.insert(0, part[size:])
        return size

    def close(self):
        self.closed = True
        self.network.events.append("close")


class FakeTLS:
    check_hostname = True
    verify_mode = ssl.CERT_REQUIRED

    def __init__(self, network):
        self.network = network

    def wrap_socket(self, sock, *, server_hostname):
        self.network.server_names.append(server_hostname)
        self.network.event("tls")
        return sock


class FakeNetwork:
    def __init__(self):
        self.records = [record()]
        self.chunks = [wire()]
        self.sockets = []
        self.resolutions = []
        self.server_names = []
        self.events = []
        self.failures = {}
        self.on_event = lambda _event: None
        self.context = FakeTLS(self)

    def event(self, name):
        self.events.append(name)
        self.on_event(name)
        if name in self.failures:
            raise self.failures[name]

    def getaddrinfo(self, host, port, **kwargs):
        self.event("dns")
        self.resolutions.append((host, port, kwargs))
        return self.records

    def socket(self, family, kind, protocol):
        self.event("socket")
        sock = FakeSocket(self, family, kind, protocol)
        self.sockets.append(sock)
        return sock

    def open(self, *, url=URL, size=5, offset=0, validator=None, guard=lambda: None):
        return HttpsTransferTransport().open(url, expected_size=size, offset=offset,
                                             validator=validator, guard=guard)


@pytest.fixture
def network(monkeypatch):
    fake = FakeNetwork()
    monkeypatch.setattr(transport.socket, "getaddrinfo", fake.getaddrinfo)
    monkeypatch.setattr(transport.socket, "socket", fake.socket)
    monkeypatch.setattr(transport.ssl, "create_default_context", lambda: fake.context)
    return fake


def test_initial_stream_is_pinned_and_uses_original_tls_hostname(network, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9998")
    with network.open() as stream:
        assert stream.etag == '"v1"'
        assert stream.read_chunk(2) == b"mo"
        assert stream.read_chunk(100) == b"del"
        assert stream.read_chunk(1) == b""
        assert not network.sockets[0].closed
    assert network.sockets[0].closed
    assert network.sockets[0].address == (PUBLIC, 443)
    assert network.server_names == ["models.example"]
    assert len(network.resolutions) == 1
    request = bytes(network.sockets[0].requests)
    assert request.startswith(b"GET /artifact.gguf HTTP/1.1\r\n")
    assert b"Host: models.example\r\n" in request
    assert b"Accept-Encoding: identity\r\n" in request
    for header in (b"Authorization:", b"Proxy-Authorization:", b"Cookie:", b"Range:", b"If-Range:"):
        assert header not in request
    assert all(0 < timeout <= 30 for timeout in network.sockets[0].timeouts)


def test_initial_etag_is_optional_and_cookies_are_ignored(network):
    network.chunks = [wire(headers=[("Content-Length", "5"), ("Set-Cookie", "private=value")])]
    with network.open() as stream:
        assert stream.etag is None
        assert stream.read_chunk(100) == b"model"
    with network.open() as stream:
        assert stream.read_chunk(100) == b"model"
    assert b"Cookie:" not in network.sockets[1].requests


def test_resume_requires_exact_range_length_total_and_strong_etag(network):
    network.chunks = [wire(206, [("Content-Length", "3"), ("Content-Range", "bytes 2-4/5"), ("ETag", '"v1"')], b"del")]
    with network.open(offset=2, validator='"v1"') as stream:
        assert stream.etag == '"v1"'
        assert stream.read_chunk(100) == b"del"
        assert stream.read_chunk(100) == b""
    request = bytes(network.sockets[0].requests)
    assert b"Range: bytes=2-\r\n" in request
    assert b'If-Range: "v1"\r\n' in request


@pytest.mark.parametrize("url", [
    "http://models.example/a", "ftp://models.example/a", "HTTPS://models.example/a",
    "//models.example/a", "https:///a", "https://user@models.example/a", "https://user:secret@models.example/a",
    "https://models.example/a?secret=value", "https://models.example/a?", "https://models.example/a#fragment",
    "https://models.example/a#", "https://models.example/a\\b", "https://models.example/a\r\nCookie:x",
    "https://models.example/a\t", " https://models.example/a", "https://models.example/a b",
    "https://models.example/%0d%0a", "https://models.example/%00", "https://models.example/%7f",
    "https://models.example/%252f", "https://models.example/%2f", "https://models.example/%5c",
    "https://models.example/%3f", "https://models.example/%23", "https://models.example/%zz",
    "https://models.example/%", "https://models.example/a/../b", "https://models.example/%2e%2e/b",
    "https://models.example/./b", "https://models.example//b", "https://models.example/a|b",
    "https://models.example:0/a", "https://models.example:65536/a", "https://models.example:/a",
    "https://models.example:abc/a", "https://models.example./a", "https://models..example/a",
    "https://-models.example/a", "https://models_.example/a", "https://mödels.example/a",
    "https://models%2eexample/a", "https://[2606:4700:4700::1111]extra/a", "https://[::1/a",
    "https://[2606:4700:4700::1111%25scope]/a", "https://models.example/" + "a" * 8192,
])
def test_unsafe_urls_rejected_before_dns_or_socket(network, url):
    with pytest.raises(TransferTransportError) as error:
        with network.open(url=url):
            pytest.fail("must not open")
    assert error.value.code == "TRANSFER_INVALID_URL"
    assert network.resolutions == [] and network.sockets == []
    assert str(error.value) == error.value.code
    assert error.value.__cause__ is None


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254", "0.0.0.0",
    "224.0.0.1", "240.0.0.1", "100.64.0.1", "198.18.0.1", "192.0.2.1", "198.51.100.1",
    "203.0.113.1", "::1", "::", "fc00::1", "fe80::1", "ff02::1", "2001:db8::1",
    "::ffff:127.0.0.1", "::ffff:10.1.1.1", "::ffff:169.254.169.254", "::ffff:224.0.0.1",
    "64:ff9b::7f00:1", "64:ff9b:1::1", "2002:7f00:1::", "2001:0000:4136:e378:8000:63bf:3fff:fdd2",
])
def test_resolve_all_rejects_mixed_public_and_restricted_answers(network, address):
    network.records = [record(), record(address)]
    with pytest.raises(TransferTransportError, match="TRANSFER_DESTINATION_RESTRICTED"):
        with network.open():
            pytest.fail("must not open")
    assert network.sockets == []


@pytest.mark.parametrize("url", ["https://127.0.0.1/a", "https://[::1]/a", "https://[::ffff:127.0.0.1]/a"])
def test_restricted_literal_cannot_be_disguised_by_resolver(network, url):
    with pytest.raises(TransferTransportError, match="TRANSFER_DESTINATION_RESTRICTED"):
        with network.open(url=url):
            pass
    assert network.resolutions == []


@pytest.mark.parametrize("address", ["2606:4700:4700::1111", "::ffff:93.184.216.34"])
def test_public_ipv6_and_mapped_ipv4_are_pinned(network, address):
    network.records = [record(address)]
    with network.open() as stream:
        assert stream.read_chunk(5) == b"model"
    assert network.sockets[0].family == socket.AF_INET6
    assert network.sockets[0].address[1:] == (443, 0, 0)
    assert network.server_names == ["models.example"]


@pytest.mark.parametrize("records", [[], None, [()], [record()] * 129,
    [(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_TCP, "", (PUBLIC, 443))],
    [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC, 80))],
    [(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("2606:4700:4700::1111", 443, 0, 1))],
    [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("2606:4700:4700::1111", 443))],
])
def test_malformed_dns_fails_closed(network, records):
    network.records = records
    with pytest.raises(TransferTransportError):
        with network.open():
            pass
    assert network.sockets == []


@pytest.mark.parametrize("size,offset,validator,code", [
    (0, 0, None, "INVALID_REQUEST"), (-1, 0, None, "INVALID_REQUEST"), (True, 0, None, "INVALID_REQUEST"),
    (5, True, None, "INVALID_REQUEST"), (5, -1, None, "INVALID_REQUEST"), (5, 5, None, "INVALID_REQUEST"),
    (1024 ** 4 + 1, 0, None, "INVALID_REQUEST"), (5, 1, None, "VALIDATOR_REQUIRED"),
    (5, 1, 'W/"v1"', "INVALID_ETAG"), (5, 1, "v1", "INVALID_ETAG"),
    (5, 1, '"v1"\r\nCookie: value', "INVALID_ETAG"), (5, 1, 1, "INVALID_ETAG"),
])
def test_invalid_request_never_resolves(network, size, offset, validator, code):
    with pytest.raises(TransferTransportError, match="TRANSFER_" + code):
        with network.open(size=size, offset=offset, validator=validator):
            pass
    assert network.resolutions == [] and network.sockets == []


@pytest.mark.parametrize("status,headers,code", [
    (301, [("Location", "https://127.0.0.1/private")], "REDIRECT_REJECTED"),
    (302, [("Location", "https://other.example/artifact")], "REDIRECT_REJECTED"),
    (307, [], "REDIRECT_REJECTED"), (401, [("WWW-Authenticate", "Basic")], "HTTP_STATUS"),
    (404, [], "HTTP_STATUS"), (204, [], "HTTP_STATUS"), (206, [("Content-Length", "5")], "HTTP_STATUS"),
    (200, [], "SIZE_MISMATCH"), (200, [("Content-Length", "4")], "SIZE_MISMATCH"),
    (200, [("Content-Length", "6")], "SIZE_MISMATCH"), (200, [("Content-Length", "-5")], "SIZE_MISMATCH"),
    (200, [("Content-Length", "+5")], "SIZE_MISMATCH"), (200, [("Content-Length", "5, 5")], "SIZE_MISMATCH"),
    (200, [("Content-Length", "5"), ("Content-Length", "5")], "INVALID_RESPONSE"),
    (200, [("Content-Length", "5"), ("Transfer-Encoding", "chunked")], "INVALID_RESPONSE"),
    (200, [("Content-Length", "5"), ("Content-Encoding", "gzip")], "ENCODING_REJECTED"),
    (200, [("Content-Length", "5"), ("Content-Encoding", "")], "ENCODING_REJECTED"),
    (200, [("Content-Length", "5"), ("Content-Encoding", "identity"), ("Content-Encoding", "identity")], "INVALID_RESPONSE"),
    (200, [("Content-Length", "5"), ("Content-Range", "bytes 0-4/5")], "RANGE_MISMATCH"),
    (200, [("Content-Length", "5"), ("ETag", 'W/"v1"')], "INVALID_ETAG"),
    (200, [("Content-Length", "5"), ("ETag", "unquoted")], "INVALID_ETAG"),
    (200, [("Content-Length", "5"), ("ETag", '"v1", "v2"')], "INVALID_ETAG"),
    (200, [("Content-Length", "5"), ("ETag", '"v1"'), ("ETag", '"v1"')], "INVALID_RESPONSE"),
    (200, [("Content-Length", "5"), ("ETag", '"' + "a" * 1024 + '"')], "INVALID_ETAG"),
    (200, [("Content-Length", "5"), ("ETag", '"a\tvalue"')], "INVALID_ETAG"),
    (200, [("Content-Length", "5"), ("X-Large", "a" * 16385)], "INVALID_RESPONSE"),
    (200, [("Content-Length", "5"), ("ETag", '"a\r\n b"')], "INVALID_RESPONSE"),
])
def test_response_metadata_rejected_without_following_or_retrying(network, status, headers, code):
    network.chunks = [wire(status, headers)]
    with pytest.raises(TransferTransportError, match="TRANSFER_" + code):
        with network.open():
            pass
    assert len(network.resolutions) == len(network.sockets) == 1
    assert network.sockets[0].closed


@pytest.mark.parametrize("content_range,etag,length,code", [
    ("bytes 0-4/5", '"v1"', "3", "RANGE_MISMATCH"),
    ("bytes 2-3/5", '"v1"', "3", "RANGE_MISMATCH"),
    ("bytes 2-4/6", '"v1"', "3", "RANGE_MISMATCH"),
    ("bytes 2-4/*", '"v1"', "3", "RANGE_MISMATCH"),
    ("bytes 2-4/5, 6-8/9", '"v1"', "3", "RANGE_MISMATCH"),
    (None, '"v1"', "3", "RANGE_MISMATCH"),
    ("bytes 2-4/5", None, "3", "VALIDATOR_MISMATCH"),
    ("bytes 2-4/5", '"changed"', "3", "VALIDATOR_MISMATCH"),
    ("bytes 2-4/5", 'W/"v1"', "3", "INVALID_ETAG"),
    ("bytes 2-4/5", '"v1"', "5", "SIZE_MISMATCH"),
])
def test_resume_cannot_accept_wrong_suffix_or_validator(network, content_range, etag, length, code):
    headers = [("Content-Length", length)]
    if content_range is not None:
        headers.append(("Content-Range", content_range))
    if etag is not None:
        headers.append(("ETag", etag))
    network.chunks = [wire(206, headers, b"del")]
    with pytest.raises(TransferTransportError, match="TRANSFER_" + code):
        with network.open(offset=2, validator='"v1"'):
            pass
    assert len(network.sockets) == 1 and network.sockets[0].closed


def test_resume_200_never_silently_restarts(network):
    with pytest.raises(TransferTransportError, match="TRANSFER_HTTP_STATUS"):
        with network.open(offset=2, validator='"v1"'):
            pass
    assert len(network.sockets) == 1


@pytest.mark.parametrize("phase,exception,code", [
    ("dns", OSError("private hostname secret"), "DNS_FAILED"),
    ("connect", OSError("private URL secret"), "CONNECT_FAILED"),
    ("connect", TimeoutError("private URL secret"), "TIMEOUT"),
    ("tls", ssl.SSLError("private URL secret"), "TLS_FAILED"),
    ("send", OSError("private URL secret"), "NETWORK_FAILED"),
    ("receive", TimeoutError("private URL secret"), "TIMEOUT"),
])
def test_network_failures_are_safe_and_never_fallback(network, phase, exception, code):
    network.records = [record(), record("1.1.1.1")]
    network.failures[phase] = exception
    with pytest.raises(TransferTransportError, match="TRANSFER_" + code) as error:
        with network.open():
            pass
    assert "secret" not in str(error.value) and error.value.__cause__ is None
    assert len(network.sockets) <= 1
    assert all(sock.closed for sock in network.sockets)


@pytest.mark.parametrize("phase", ["dns", "socket", "connect", "tls", "send", "receive"])
@pytest.mark.parametrize("error_type", [ValueError, OSError])
def test_authority_guard_survives_network_error_normalization(network, phase, error_type):
    revoked = False
    failure = error_type("authority revoked")
    def event(name):
        nonlocal revoked
        revoked = revoked or name == phase
    network.on_event = event
    def guard():
        network.events.append("guard")
        if revoked:
            raise failure
    with pytest.raises(error_type) as error:
        with network.open(guard=guard):
            pass
    assert error.value is failure
    assert all(sock.closed for sock in network.sockets)
    assert network.events.index("guard") < network.events.index(phase)


def test_guard_checked_before_and_after_body_read_and_closed_on_cancellation(network):
    network.chunks = [wire(body=b"").replace(b"Content-Length: 0", b"Content-Length: 5"), b"model"]
    cancelled = False
    def guard():
        if cancelled:
            raise ValueError("cancelled")
    with pytest.raises(ValueError, match="cancelled"):
        with network.open(guard=guard) as stream:
            def revoke(name):
                nonlocal cancelled
                if name == "receive":
                    cancelled = True
            network.on_event = revoke
            stream.read_chunk(5)
    assert network.sockets[0].closed


def test_truncated_body_fails_with_bounded_reads(network):
    network.chunks = [wire(headers=[("Content-Length", "5")], body=b"mo")]
    with network.open() as stream:
        assert stream.read_chunk(4) == b"mo"
        with pytest.raises(TransferTransportError, match="TRANSFER_TRUNCATED"):
            stream.read_chunk(4)
    assert network.sockets[0].closed


@pytest.mark.parametrize("amount", [0, -1, True, "5", 1024 ** 2 + 1])
def test_chunk_limits_are_strict(network, amount):
    with network.open() as stream:
        with pytest.raises(TransferTransportError, match="TRANSFER_INVALID_CHUNK_SIZE"):
            stream.read_chunk(amount)


def test_close_is_idempotent_and_prevents_later_reads(network):
    with network.open() as stream:
        stream.close()
        stream.close()
        assert network.sockets[0].closed
        with pytest.raises(TransferTransportError, match="TRANSFER_CLOSED"):
            stream.read_chunk(5)


def test_disabled_hostname_or_certificate_verification_is_rejected(network):
    network.context.check_hostname = False
    with pytest.raises(TransferTransportError, match="TRANSFER_TLS_FAILED"):
        with network.open():
            pass
    assert network.sockets == []


def test_dns_timeout_does_not_create_socket_after_late_resolution(network, monkeypatch):
    pending = threading.Event()
    finished = threading.Event()
    def resolver(*_args, **_kwargs):
        pending.wait(2)
        finished.set()
        return [record()]
    monkeypatch.setattr(transport.socket, "getaddrinfo", resolver)
    monkeypatch.setattr(transport, "_DNS_TIMEOUT", 0.01)
    try:
        with pytest.raises(TransferTransportError, match="TRANSFER_TIMEOUT"):
            with network.open():
                pass
        assert network.sockets == []
    finally:
        pending.set()
        assert finished.wait(1)
    assert network.sockets == []


def test_malformed_http_is_safe_and_closed(network):
    network.chunks = [b"not an HTTP response\r\n\r\n"]
    with pytest.raises(TransferTransportError, match="TRANSFER_INVALID_RESPONSE"):
        with network.open():
            pass
    assert network.sockets[0].closed


@pytest.mark.parametrize("phase,delay", [("connect", 16), ("tls", 16), ("send", 31), ("receive", 31)])
def test_single_blocking_operation_has_wall_clock_deadline(network, monkeypatch, phase, delay):
    now = [1000.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    def advance(name):
        if name == phase:
            now[0] += delay
    network.on_event = advance
    with pytest.raises(TransferTransportError, match="TRANSFER_TIMEOUT"):
        with network.open():
            pass
    assert all(sock.closed for sock in network.sockets)


def test_slow_drip_headers_do_not_reset_phase_deadline(network, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    network.chunks = [bytes([byte]) for byte in wire()]
    def advance(name):
        if name == "receive":
            now[0] += 2
    network.on_event = advance
    with pytest.raises(TransferTransportError, match="TRANSFER_TIMEOUT"):
        with network.open():
            pass
    assert network.events.count("receive") <= 16
    assert network.sockets[0].closed


def test_total_deadline_cannot_be_extended_by_reading_small_chunks(network, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    with network.open() as stream:
        assert stream.read_chunk(1) == b"m"
        now[0] += transport._TOTAL_TIMEOUT + 1
        with pytest.raises(TransferTransportError, match="TRANSFER_TIMEOUT"):
            stream.read_chunk(1)
    assert network.sockets[0].closed


def test_connection_close_response_keeps_body_socket_until_stream_close(network):
    network.chunks = [wire(headers=[("Content-Length", "5"), ("Connection", "close")], body=b""), b"model"]
    with network.open() as stream:
        assert not network.sockets[0].closed
        assert stream.read_chunk(100) == b"model"
    assert network.sockets[0].closed


def test_empty_strong_etag_is_valid_and_identity_encoding_is_case_insensitive(network):
    network.chunks = [wire(headers=[("Content-Length", "5"), ("Content-Encoding", "Identity"), ("ETag", '""')])]
    with network.open() as stream:
        assert stream.etag == '""'
        assert stream.read_chunk(5) == b"model"


def test_public_literal_and_nondefault_https_port_preserve_authority(network):
    network.records = [record(PUBLIC, 8443)]
    with network.open(url=f"https://{PUBLIC}:8443/artifact.gguf") as stream:
        assert stream.read_chunk(5) == b"model"
    assert network.sockets[0].address == (PUBLIC, 8443)
    assert network.server_names == [PUBLIC]
    assert b"Host: 93.184.216.34:8443\r\n" in network.sockets[0].requests


def test_error_constructor_cannot_reflect_arbitrary_messages():
    assert TransferTransportError("https://secret.example/token").code == "TRANSFER_FAILED"
    assert TransferTransportError(None).code == "TRANSFER_FAILED"


def test_failed_body_read_closes_immediately_and_cannot_be_retried(network):
    network.chunks = [wire(headers=[("Content-Length", "5")], body=b"")]
    with network.open() as stream:
        network.failures["receive"] = TimeoutError("private error")
        with pytest.raises(TransferTransportError, match="TRANSFER_TIMEOUT"):
            stream.read_chunk(5)
        assert network.sockets[0].closed
        receive_count = network.events.count("receive")
        with pytest.raises(TransferTransportError, match="TRANSFER_CLOSED"):
            stream.read_chunk(5)
        assert network.events.count("receive") == receive_count


def test_excess_framed_bytes_are_never_returned_or_used_for_another_request(network):
    network.chunks = [wire(headers=[("Content-Length", "5")], body=b"modelEXCESS")]
    with network.open() as stream:
        assert stream.read_chunk(1024) == b"model"
        assert stream.read_chunk(1024) == b""
    assert network.sockets[0].closed
    assert bytes(network.sockets[0].requests).count(b"GET ") == 1
