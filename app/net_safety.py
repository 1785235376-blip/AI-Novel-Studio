from __future__ import annotations
import ipaddress
import re
import socket
from urllib.parse import urlparse, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

class OutboundURLRejected(ValueError): pass


class ProviderEndpointRejected(ValueError):
    """A caller-supplied provider endpoint names a transport target that a
    local-first service must never dial on a caller's behalf."""


_PROVIDER_LEGACY_NUMERIC_HOST = re.compile(r"(?:[0-9]+|0[xX][0-9A-Fa-f]+)(?:\.[0-9]+|0[xX][0-9A-Fa-f]+)*\Z")


def validate_provider_endpoint(url: str) -> str:
    """Offline-safe admission for an operator-supplied provider endpoint.

    The packaged, single-user product intentionally talks to operator-configured
    local (loopback/private) and public providers, so those ranges stay accepted.
    Link-local (cloud metadata), multicast, unspecified and reserved transports
    are never a legitimate provider and are refused. This check uses literal host
    parsing only: it never performs DNS, so saving a configuration keeps the
    existing offline behaviour. A hostname that later resolves to a restricted
    address is outside this bounded check and is recorded as NOT_VERIFIED.
    """
    parsed = urlsplit(str(url).strip())
    if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment):
        raise ProviderEndpointRejected("invalid provider endpoint")
    host = parsed.hostname.strip()
    # A fully-qualified trailing dot is the same host to a resolver.
    normalized = host.rstrip(".")
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        # Legacy numeric spellings (decimal/hex/partial IPv4) are resolved by the
        # operating system and could silently denote a restricted address.
        if _PROVIDER_LEGACY_NUMERIC_HOST.fullmatch(normalized):
            raise ProviderEndpointRejected("provider endpoint address is not allowed") from None
        return str(url).strip()
    effective = getattr(address, "ipv4_mapped", None) or address
    if (effective.is_link_local or effective.is_multicast or effective.is_unspecified
            or (effective.is_reserved and not effective.is_loopback)):
        raise ProviderEndpointRejected("provider endpoint address is not allowed")
    return str(url).strip()

def _allowed_loopback_hosts() -> set[str]:
    from .config import settings
    return {item.strip().lower().rstrip('.') for item in settings.outbound_loopback_allowlist.split(',') if item.strip()}

def _is_restricted(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved or ip.is_multicast

def validate_outbound_url(url: str) -> str:
    parsed=urlparse(str(url).strip())
    if parsed.scheme.lower() not in {'http','https'} or not parsed.hostname:
        raise OutboundURLRejected('outbound URL must use http or https')
    host=parsed.hostname.lower().rstrip('.')
    allow_local=host in _allowed_loopback_hosts()
    if (host=='localhost' or host.endswith('.localhost')) and not allow_local:
        raise OutboundURLRejected('outbound URL host is not allowed')
    try: ip=ipaddress.ip_address(host)
    except ValueError: ip=None
    if ip and _is_restricted(ip) and not allow_local:
        raise OutboundURLRejected('outbound URL host is not allowed')
    if ip is None:
        try:
            resolved={ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme.lower()=='https' else 80), type=socket.SOCK_STREAM)}
        except (socket.gaierror, ValueError, OSError) as exc:
            raise OutboundURLRejected('outbound URL host could not be resolved') from exc
        if not resolved or (any(_is_restricted(address) for address in resolved) and not allow_local):
            raise OutboundURLRejected('outbound URL host is not allowed')
    return parsed.geturl()

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

def fetch_outbound_bytes(url: str, max_bytes: int, timeout: int = 30) -> bytes:
    safe=validate_outbound_url(url)
    request=Request(safe, headers={'User-Agent':'AI-Novel-Studio/0.7'})
    opener=build_opener(_NoRedirect)
    with opener.open(request, timeout=timeout) as response:
        length=response.headers.get('Content-Length')
        if length and int(length)>max_bytes: raise OutboundURLRejected('response exceeds asset size limit')
        data=response.read(max_bytes+1)
    if len(data)>max_bytes: raise OutboundURLRejected('response exceeds asset size limit')
    return data
