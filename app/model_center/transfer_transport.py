"""Single-response, public-only HTTPS transport for verified model artifacts.

There is no proxy, credential store, redirect handler, or private-host exception.
DNS is resolved once, every answer is checked, and exactly one numeric address
is connected. TLS still authenticates the URL hostname. Tests replace the
socket/DNS/TLS boundaries; production has no configurable network-policy seam.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import http.client
import io
import ipaddress
import re
import socket
import ssl
import threading
import time
from typing import Callable, Iterator
from urllib.parse import unquote_to_bytes, urlsplit


_MAX_FILE_BYTES = 1024 ** 4
_MAX_CHUNK_BYTES = 1024 ** 2
_MAX_URL_BYTES = 8192
_MAX_HEADER_BYTES = 16384
_DNS_TIMEOUT = 10.0
_CONNECT_TIMEOUT = 15.0
_IO_TIMEOUT = 30.0
_TOTAL_TIMEOUT = 24 * 60 * 60.0
_DNS_SLOTS = threading.BoundedSemaphore(4)
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")
_STRONG_ETAG = re.compile(r'"[\x21\x23-\x7e]*"\Z')
_CONTENT_RANGE = re.compile(r"bytes ([0-9]{1,13})-([0-9]{1,13})/([0-9]{1,13})\Z")


class TransferTransportError(ValueError):
    """A stable, non-sensitive error suitable for persisted job status."""

    def __init__(self, code: str):
        # Even a mistaken caller must not accidentally expose a URL in an error.
        self.code = code if isinstance(code, str) and re.fullmatch(r"TRANSFER_[A-Z_]{1,64}", code) else "TRANSFER_FAILED"
        super().__init__(self.code)


def _fail(code: str) -> None:
    raise TransferTransportError(code) from None


class _Calls:
    def __init__(self, guard: Callable[[], None]):
        self.guard = guard
        self.deadline = time.monotonic() + _TOTAL_TIMEOUT
        self.guard_failure: BaseException | None = None

    def check(self) -> None:
        try:
            self.guard()
        except BaseException as error:
            self.guard_failure = error
            raise
        if time.monotonic() >= self.deadline:
            _fail("TRANSFER_TIMEOUT")

    def run(self, operation, code: str = "TRANSFER_NETWORK_FAILED"):
        self.check()
        try:
            result = operation()
        except BaseException as error:
            if error is self.guard_failure:
                raise
            self.check()
            if isinstance(error, TransferTransportError):
                raise
            if not isinstance(error, Exception):
                raise
            if isinstance(error, (TimeoutError, socket.timeout)):
                code = "TRANSFER_TIMEOUT"
            elif isinstance(error, ssl.SSLError):
                code = "TRANSFER_TLS_FAILED"
            elif isinstance(error, http.client.IncompleteRead):
                code = "TRANSFER_TRUNCATED"
            elif isinstance(error, http.client.HTTPException):
                code = "TRANSFER_INVALID_RESPONSE"
            raise TransferTransportError(code) from None
        self.check()
        return result

    def timeout(self, seconds: float, deadline: float | None = None) -> float:
        remaining = min(seconds, self.deadline - time.monotonic())
        if deadline is not None:
            remaining = min(remaining, deadline - time.monotonic())
        if remaining <= 0:
            _fail("TRANSFER_TIMEOUT")
        return remaining


@dataclass(frozen=True)
class _Destination:
    hostname: str
    port: int
    path: str


def _destination(url: str) -> _Destination:
    if (not isinstance(url, str) or not url or len(url) > _MAX_URL_BYTES
            or any(ord(char) <= 32 or ord(char) >= 127 for char in url)
            or any(char in url for char in "\\?#")):
        _fail("TRANSFER_INVALID_URL")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not url.startswith("https://")
                or not parsed.netloc or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or "@" in parsed.netloc
                or "%" in parsed.netloc or parsed.netloc.endswith(":")):
            _fail("TRANSFER_INVALID_URL")
        hostname = parsed.hostname
        port = parsed.port if parsed.port is not None else 443
        if not 1 <= port <= 65535 or hostname.endswith("."):
            _fail("TRANSFER_INVALID_URL")
        if not re.fullmatch(r"(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(?::[0-9]{1,5})?", parsed.netloc):
            _fail("TRANSFER_INVALID_URL")
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            if len(hostname) > 253 or not all(_HOST_LABEL.fullmatch(label) for label in hostname.split(".")):
                _fail("TRANSFER_INVALID_URL")
        else:
            _public_address(str(literal))
        path = parsed.path or "/"
        if not path.startswith("/") or path.startswith("//") or re.search(r"[^A-Za-z0-9._~!$&'()*+,;=:@%/\-]", path):
            _fail("TRANSFER_INVALID_URL")
        if re.search(r"%(?![0-9A-Fa-f]{2})", path):
            _fail("TRANSFER_INVALID_URL")
        decoded = unquote_to_bytes(path)
        # No escaped separators, controls, double escaping, or dot traversal.
        for match in re.finditer(r"%([0-9A-Fa-f]{2})", path):
            byte = int(match.group(1), 16)
            if byte <= 32 or byte == 127 or chr(byte) in "/\\%?#":
                _fail("TRANSFER_INVALID_URL")
        if any(segment in (b".", b"..") for segment in decoded.split(b"/")):
            _fail("TRANSFER_INVALID_URL")
        return _Destination(hostname, port, path)
    except (ValueError, UnicodeError) as error:
        if isinstance(error, TransferTransportError):
            raise
        raise TransferTransportError("TRANSFER_INVALID_URL") from None


def _public_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        if not isinstance(value, str) or "%" in value:
            _fail("TRANSFER_DESTINATION_RESTRICTED")
        address = ipaddress.ip_address(value)
        effective = getattr(address, "ipv4_mapped", None) or address
        if (not effective.is_global or effective.is_multicast or effective.is_reserved
                or effective.is_loopback or effective.is_link_local or effective.is_unspecified):
            _fail("TRANSFER_DESTINATION_RESTRICTED")
        # Transition routes can reach an embedded address that differs from the
        # apparently global IPv6 address. They are outside this narrow transport.
        if isinstance(address, ipaddress.IPv6Address) and (
                address.sixtofour is not None or address.teredo is not None
                or address in ipaddress.IPv6Network("64:ff9b::/96")
                or address in ipaddress.IPv6Network("64:ff9b:1::/48")):
            _fail("TRANSFER_DESTINATION_RESTRICTED")
        return address
    except ValueError as error:
        if isinstance(error, TransferTransportError):
            raise
        raise TransferTransportError("TRANSFER_DESTINATION_RESTRICTED") from None


def _resolve(destination: _Destination, calls: _Calls) -> tuple[int, tuple]:
    calls.check()
    # getaddrinfo has no portable timeout. A bounded number of daemon workers
    # may finish DNS after cancellation, but they can never connect a socket.
    if not _DNS_SLOTS.acquire(blocking=False):
        _fail("TRANSFER_DNS_BUSY")
    finished = threading.Event()
    result: list = []
    def resolve() -> None:
        try:
            result.append(socket.getaddrinfo(destination.hostname, destination.port,
                                            family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
                                            proto=socket.IPPROTO_TCP))
        except BaseException:
            result.append(None)
        finally:
            _DNS_SLOTS.release()
            finished.set()
    try:
        thread = threading.Thread(target=resolve, name="model-transfer-dns", daemon=True)
        thread.start()
    except Exception:
        _DNS_SLOTS.release()
        raise TransferTransportError("TRANSFER_DNS_FAILED") from None
    deadline = time.monotonic() + _DNS_TIMEOUT
    while not finished.is_set():
        calls.run(lambda: finished.wait(calls.timeout(0.1, deadline)), "TRANSFER_DNS_FAILED")
        if not finished.is_set() and time.monotonic() >= deadline:
            _fail("TRANSFER_TIMEOUT")
    calls.check()
    records = result[0]
    if not isinstance(records, (tuple, list)) or not records or len(records) > 128:
        _fail("TRANSFER_DNS_FAILED")
    addresses = []
    try:
        for family, socktype, protocol, _canonname, sockaddr in records:
            if (family not in (socket.AF_INET, socket.AF_INET6)
                    or socktype != socket.SOCK_STREAM or protocol != socket.IPPROTO_TCP
                    or not isinstance(sockaddr, tuple)
                    or len(sockaddr) != (2 if family == socket.AF_INET else 4)
                    or sockaddr[1] != destination.port
                    or (family == socket.AF_INET6 and sockaddr[2:] != (0, 0))):
                _fail("TRANSFER_DESTINATION_RESTRICTED")
            address = _public_address(sockaddr[0])
            if address.version != (4 if family == socket.AF_INET else 6):
                _fail("TRANSFER_DESTINATION_RESTRICTED")
            # Rebuild the address from its parsed numeric form, never a hostname.
            pinned = (str(address), destination.port)
            if family == socket.AF_INET6:
                pinned += (0, 0)
            addresses.append((family, pinned))
    except (ValueError, TypeError, IndexError) as error:
        if isinstance(error, TransferTransportError):
            raise
        raise TransferTransportError("TRANSFER_DNS_FAILED") from None
    return addresses[0]


class _SocketReader(io.RawIOBase):
    def __init__(self, owner: "_GuardedSocket"):
        super().__init__()
        self.owner = owner

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        if self.closed:
            raise ValueError("closed transfer stream")
        return self.owner.recv_into(buffer)

    def close(self) -> None:
        if not self.closed:
            try:
                self.owner.release_reader()
            finally:
                super().close()


class _GuardedSocket:
    """Guard every network read, including HTTP headers and interim responses.

    A phase deadline prevents slow headers from resetting the timeout one byte
    at a time. File references retain the socket when HTTPConnection relinquishes
    its own reference for a Connection: close response.
    """
    def __init__(self, sock, calls: _Calls):
        self.sock = sock
        self.calls = calls
        self.readers = 0
        self.closed = False
        self.phase_deadline = time.monotonic() + _IO_TIMEOUT

    def begin_phase(self) -> None:
        self.phase_deadline = time.monotonic() + _IO_TIMEOUT

    def _prepare(self) -> None:
        self.sock.settimeout(self.calls.timeout(_IO_TIMEOUT, self.phase_deadline))

    def recv_into(self, buffer) -> int:
        self._prepare()
        result = self.calls.run(lambda: self.sock.recv_into(buffer))
        self.calls.timeout(_IO_TIMEOUT, self.phase_deadline)
        return result

    def sendall(self, data) -> None:
        view = memoryview(data)
        while view:
            self._prepare()
            count = self.calls.run(lambda: self.sock.send(view))
            self.calls.timeout(_IO_TIMEOUT, self.phase_deadline)
            if not isinstance(count, int) or not 0 < count <= len(view):
                _fail("TRANSFER_NETWORK_FAILED")
            view = view[count:]

    def makefile(self, mode: str):
        if mode != "rb" or self.closed:
            _fail("TRANSFER_INVALID_RESPONSE")
        self.readers += 1
        return io.BufferedReader(_SocketReader(self), buffer_size=65536)

    def release_reader(self) -> None:
        self.readers -= 1
        if self.closed and not self.readers:
            self.sock.close()

    def close(self) -> None:
        self.closed = True
        if not self.readers:
            self.sock.close()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, destination: _Destination, address: tuple[int, tuple], calls: _Calls):
        context = calls.run(ssl.create_default_context, "TRANSFER_TLS_FAILED")
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            _fail("TRANSFER_TLS_FAILED")
        super().__init__(destination.hostname, destination.port, timeout=_CONNECT_TIMEOUT, context=context)
        self.address = address
        self.calls = calls
        self.connected_once = False
        self.stream_socket: _GuardedSocket | None = None

    def connect(self) -> None:
        if self.connected_once:
            _fail("TRANSFER_RECONNECT_REJECTED")
        self.connected_once = True
        family, sockaddr = self.address
        raw = None
        try:
            def create_socket():
                nonlocal raw
                raw = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
                self.sock = raw
            self.calls.run(create_socket)
            deadline = time.monotonic() + _CONNECT_TIMEOUT
            self.calls.run(lambda: raw.settimeout(self.calls.timeout(_CONNECT_TIMEOUT, deadline)))
            self.calls.run(lambda: raw.connect(sockaddr), "TRANSFER_CONNECT_FAILED")
            self.calls.timeout(_CONNECT_TIMEOUT, deadline)
            deadline = time.monotonic() + _CONNECT_TIMEOUT
            self.calls.run(lambda: raw.settimeout(self.calls.timeout(_CONNECT_TIMEOUT, deadline)))
            def handshake():
                # Assign before the post-call guard, so cancellation still closes
                # the TLS socket after wrap_socket has detached the raw socket.
                self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
            self.calls.run(handshake, "TRANSFER_TLS_FAILED")
            self.calls.timeout(_CONNECT_TIMEOUT, deadline)
            self.stream_socket = _GuardedSocket(self.sock, self.calls)
            self.sock = self.stream_socket
        except BaseException:
            _quiet_close(self)
            if raw is not None:
                _quiet_close(raw)
            raise


def _quiet_close(value) -> None:
    try:
        value.close()
    except Exception:
        pass


def _header(response: http.client.HTTPResponse, name: str) -> str | None:
    values = [value for key, value in response.getheaders() if key.lower() == name.lower()]
    if len(values) > 1:
        _fail("TRANSFER_INVALID_RESPONSE")
    if not values:
        return None
    value = values[0]
    if not isinstance(value, str) or any(ord(char) < 32 and char != "\t" or ord(char) == 127 for char in value):
        _fail("TRANSFER_INVALID_RESPONSE")
    return value.strip(" \t")


def _etag(value: str | None) -> str | None:
    if value is not None and (len(value) > 1024 or not _STRONG_ETAG.fullmatch(value)):
        _fail("TRANSFER_INVALID_ETAG")
    return value


def _validate_response(response, expected_size: int, offset: int, validator: str | None) -> str | None:
    headers = response.getheaders()
    if sum(len(key) + len(value) for key, value in headers) > _MAX_HEADER_BYTES:
        _fail("TRANSFER_INVALID_RESPONSE")
    if 300 <= response.status < 400:
        _fail("TRANSFER_REDIRECT_REJECTED")
    if response.status != (206 if offset else 200):
        _fail("TRANSFER_HTTP_STATUS")
    if _header(response, "Transfer-Encoding") is not None:
        _fail("TRANSFER_INVALID_RESPONSE")
    encoding = _header(response, "Content-Encoding")
    if encoding is not None and encoding.lower() != "identity":
        _fail("TRANSFER_ENCODING_REJECTED")
    length = _header(response, "Content-Length")
    if length is None or not re.fullmatch(r"[0-9]{1,13}", length) or int(length) != expected_size - offset:
        _fail("TRANSFER_SIZE_MISMATCH")
    content_range = _header(response, "Content-Range")
    if offset:
        match = _CONTENT_RANGE.fullmatch(content_range or "")
        if not match or tuple(map(int, match.groups())) != (offset, expected_size - 1, expected_size):
            _fail("TRANSFER_RANGE_MISMATCH")
    elif content_range is not None:
        _fail("TRANSFER_RANGE_MISMATCH")
    etag = _etag(_header(response, "ETag"))
    if offset and etag != validator:
        _fail("TRANSFER_VALIDATOR_MISMATCH")
    return etag


class _TransferStream:
    def __init__(self, connection: _PinnedHTTPSConnection, response, calls: _Calls,
                 expected_bytes: int, etag: str | None):
        self.connection = connection
        self.response = response
        self.calls = calls
        self.remaining = expected_bytes
        self.etag = etag
        self.closed = False

    def read_chunk(self, max_bytes: int) -> bytes:
        try:
            self.calls.check()
            if self.closed:
                _fail("TRANSFER_CLOSED")
            if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_CHUNK_BYTES:
                _fail("TRANSFER_INVALID_CHUNK_SIZE")
            if not self.remaining:
                return b""
            limit = min(max_bytes, self.remaining)
            self.connection.stream_socket.begin_phase()
            part = self.calls.run(lambda: self.response.read1(limit))
            if not isinstance(part, bytes) or len(part) > limit:
                _fail("TRANSFER_SIZE_MISMATCH")
            if not part:
                _fail("TRANSFER_TRUNCATED")
            self.remaining -= len(part)
            return part
        except BaseException:
            # Cancellation and failed reads invalidate this connection. Retrying
            # the same partially consumed HTTP stream would be ambiguous.
            self.close()
            raise

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            _quiet_close(self.response)
            _quiet_close(self.connection)


class HttpsTransferTransport:
    """Stream one exact artifact or a validator-bound suffix; never retry."""

    @contextmanager
    def open(self, url: str, *, expected_size: int, offset: int,
             validator: str | None, guard: Callable[[], None]) -> Iterator[_TransferStream]:
        if (type(expected_size) is not int or not 1 <= expected_size <= _MAX_FILE_BYTES
                or type(offset) is not int or not 0 <= offset < expected_size
                or not callable(guard)):
            _fail("TRANSFER_INVALID_REQUEST")
        if validator is not None and not isinstance(validator, str):
            _fail("TRANSFER_INVALID_ETAG")
        _etag(validator)
        if offset and validator is None:
            _fail("TRANSFER_VALIDATOR_REQUIRED")
        calls = _Calls(guard)
        calls.check()
        destination = _destination(url)
        address = _resolve(destination, calls)
        connection = _PinnedHTTPSConnection(destination, address, calls)
        response = None
        stream = None
        try:
            connection.connect()
            headers = {"Accept": "application/octet-stream", "Accept-Encoding": "identity",
                       "User-Agent": "AI-Novel-Studio/ModelCenter", "Connection": "close"}
            if offset:
                headers.update({"Range": f"bytes={offset}-", "If-Range": validator})
            connection.stream_socket.begin_phase()
            calls.run(lambda: connection.request("GET", destination.path, headers=headers))
            connection.stream_socket.begin_phase()
            def receive():
                nonlocal response
                response = connection.getresponse()
            calls.run(receive)
            etag = _validate_response(response, expected_size, offset, validator)
            calls.check()
            stream = _TransferStream(connection, response, calls, expected_size - offset, etag)
            yield stream
        finally:
            if stream is not None:
                stream.close()
            else:
                if response is not None:
                    _quiet_close(response)
                _quiet_close(connection)
