"""Existing unified errors preserve explicit transport/privacy headers."""
import asyncio
import json
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.main import unified_http_error


@pytest.mark.parametrize("header_name", ["X-Request-ID", "x-request-id", "X-ReQuEsT-Id"])
def test_unified_error_retains_no_store_nosniff_and_server_request_id(header_name):
    request = Request({'type': 'http', 'method': 'GET', 'path': '/synthetic', 'headers': [], 'state': {'request_id': 'server-receipt'}})
    response = asyncio.run(unified_http_error(request, HTTPException(409, {'code': 'SYNTHETIC_STALE'},
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', header_name: 'untrusted-override'})))
    assert response.status_code == 409
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-request-id'] == 'server-receipt'
    assert json.loads(response.body)['code'] == 'SYNTHETIC_STALE'


def test_existing_auth_retry_headers_and_default_body_are_preserved():
    request = Request({'type': 'http', 'method': 'GET', 'path': '/synthetic', 'headers': [], 'state': {}})
    response = asyncio.run(unified_http_error(request, HTTPException(401, 'Sign in', headers={'WWW-Authenticate': 'Bearer', 'Retry-After': '5'})))
    assert response.headers['www-authenticate'] == 'Bearer'
    assert response.headers['retry-after'] == '5'
    assert json.loads(response.body)['detail'] == 'Sign in'
    plain = asyncio.run(unified_http_error(request, HTTPException(404, 'Missing')))
    assert plain.status_code == 404 and json.loads(plain.body)['code'] == 'HTTP_404'
