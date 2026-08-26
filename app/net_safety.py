from __future__ import annotations
import ipaddress
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

class OutboundURLRejected(ValueError): pass

def validate_outbound_url(url: str) -> str:
    parsed=urlparse(str(url).strip())
    if parsed.scheme.lower() not in {'http','https'} or not parsed.hostname:
        raise OutboundURLRejected('outbound URL must use http or https')
    host=parsed.hostname.lower().rstrip('.')
    if host=='localhost' or host.endswith('.localhost'):
        raise OutboundURLRejected('outbound URL host is not allowed')
    try: ip=ipaddress.ip_address(host)
    except ValueError: ip=None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved):
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
