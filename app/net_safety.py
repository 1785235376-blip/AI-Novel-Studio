from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

class OutboundURLRejected(ValueError): pass

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
