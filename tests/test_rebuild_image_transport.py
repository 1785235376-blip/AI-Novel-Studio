"""Synthetic wire contracts for the original configured/discovery image owners.

No socket or model is used: even proxy selection is captured by MockTransport.
"""
import base64
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib

import httpx
import pytest

from app.asset_providers import AssetGenerationRequest, ComfyUIImageProvider
from app.model_center.discovery_bridge import _LocalImageTransport
from scripts.run_v2_checks import isolated_environment
from test_v2_independent_workspace import rig


class Wire(httpx.SyncByteStream):
    def __init__(self, parts):
        self.parts = parts
        self.count = 0
        self.closed = False

    def __iter__(self):
        for part in self.parts:
            self.count += len(part)
            yield part

    def close(self):
        self.closed = True


def mock_wire(monkeypatch, parts, *, headers=None, status=200):
    wire, calls, clients = Wire(parts), [], []
    original = httpx.Client

    def dispatch(request):
        calls.append(request)
        return httpx.Response(status, headers=headers, stream=wire)

    def client(**kwargs):
        clients.append(kwargs.copy())
        return original(**kwargs, transport=httpx.MockTransport(dispatch))

    monkeypatch.setattr(httpx, 'Client', client)
    return wire, calls, clients


CONFIGURED_SCRIPT = r'''
import json, os
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from app import asset_provider_config
from app.asset_providers import AssetGenerationRequest
from app.config import settings

style, registration, endpoint = json.loads(os.environ['IMAGE_TEST_CASE'])
if registration == 'refresh':
    from app import dependencies
asset_provider_config.save('image_transport_fixture', endpoint, 'fixture',
    api_style=style, local=True, requires_credential=False)
if registration == 'startup':
    from app import dependencies
else:
    assert dependencies.refresh_asset_provider('image_transport_fixture')
from app.creative.production_execution import ProductionExecutionService
from app.creative.production_execution_models import MediaCommand
provider = dependencies.asset_provider_registry.get('image_transport_fixture')
owner = ProductionExecutionService.__new__(ProductionExecutionService)
owner.image_registry = dependencies.asset_provider_registry
owner.workspace = SimpleNamespace(novels=SimpleNamespace(get_context_sources=lambda _: {}),
    project=lambda *_: {'project': {'entry_kind': 'NEUTRAL_STUDIO'}})
owner.store = SimpleNamespace(key=lambda *_: 'synthetic-scope', incarnation=lambda *_: 'synthetic-incarnation')
command = MediaCommand(operation_id='m5.image.t2i', request_id='synthetic', provider_id='image_transport_fixture',
    model_id='fixture', prompt='SYNTHETIC_PRIVATE_PROMPT')
binding = owner._binding(command)
events = []
def response(*, payload=None, content=None):
    wire = json.dumps(payload).encode() if payload is not None else content
    return httpx.Response(200, stream=httpx.ByteStream(wire))
def dispatch(route):
    def reply(request):
        events.append({'route': route, 'url': str(request.url),
            'prompt': b'SYNTHETIC_PRIVATE_PROMPT' in request.content})
        if request.url.path.endswith('/prompt'):
            return response(payload={'prompt_id': 'synthetic-job'})
        if '/history/' in request.url.path:
            return response(payload={'synthetic-job': {'outputs': {'9': {'images': [{'filename': 'fixture.png'}]}}}})
        if request.url.path.endswith('/view'):
            return response(content=b'SYNTHETIC_BINARY')
        return response(payload={'images': ['QUJD']})
    return httpx.MockTransport(reply)
env = {key: '' for key in ('http_proxy','https_proxy','all_proxy','no_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY')}
for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    env[key] = 'http://proxy.invalid:8888'
with patch.dict(os.environ, env), patch.object(httpx.Client, '_init_transport', lambda *a, **k: dispatch('DIRECT')), patch.object(httpx.Client, '_init_proxy_transport', lambda *a, **k: dispatch('PROXY')):
    os.environ.pop('NO_PROXY', None)
    os.environ.pop('no_proxy', None)
    blocked = None
    if not binding['local']:
        try:
            owner.preview('synthetic', {}, 'synthetic-actor', command, lambda: None)
        except ValueError as exc:
            blocked = str(exc)
        assert not events
        # Explicitly model the existing authorized cloud gate without weakening it.
        object.__setattr__(settings, 'enable_cloud', True)
        try:
            owner.preview('synthetic', {}, 'synthetic-actor', command, lambda: None)
        except ValueError as exc:
            assert str(exc) == 'STUDIO_CLOUD_EXPLICIT_CONSENT_REQUIRED'
        else:
            raise AssertionError('missing explicit cloud consent gate')
        assert not events
        command = command.model_copy(update={'allow_cloud': True, 'source_snapshots': []})
        cloud_sources = owner._cloud_sources
        def source_gate(*args):
            events.append({'source_gate': True})
            return cloud_sources(*args)
        owner._cloud_sources = source_gate
        preview, _, command = owner.preview('synthetic', {}, 'synthetic-actor', command, lambda: None)
        assert preview['provider']['local'] is False
    result = provider.generate(AssetGenerationRequest('image_transport_fixture', 'fixture', 'SYNTHETIC_PRIVATE_PROMPT', 'synthetic-task'))
print(json.dumps({'local': binding['local'], 'events': events, 'blocked': blocked, 'uri': result.asset_uri}))
'''


@pytest.mark.parametrize('registration', ['startup', 'refresh'])
@pytest.mark.parametrize('style', ['automatic1111', 'comfyui'])
@pytest.mark.parametrize('endpoint,local', [
    ('http://127.0.0.1:7860', True),
    ('http://localhost:7860', True),
    ('http://[::1]:7860', True),
    ('http://192.168.1.4:7860', True),
    ('https://api.example.test:443', False),
])
def test_original_registration_preserves_local_proxy_isolation_and_remote_gates(tmp_path, registration, style, endpoint, local):
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for key in list(env):
        if key.endswith(('_API_KEY', '_TOKEN', '_SECRET')) or key in {
            'DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL',
            'ASSET_OPENAI_ENDPOINT', 'COLLABORATION_DEV_SESSIONS_JSON', 'PACKAGED_CONTROL_PIPE',
        }:
            env.pop(key, None)
    env.update(isolated_environment(root, tmp_path / 'profile'))
    env['ASSET_PROVIDER_CONFIG_PATH'] = str(tmp_path / 'providers.json')
    env['IMAGE_TEST_CASE'] = json.dumps([style, registration, endpoint])
    result = subprocess.run([sys.executable, '-c', CONFIGURED_SCRIPT], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    result = json.loads(result.stdout)
    assert result['local'] is local
    requests = [event for event in result['events'] if 'route' in event]
    assert requests and all(event['route'] == ('DIRECT' if local else 'PROXY') for event in requests)
    assert sum(event['prompt'] for event in requests) == 1
    assert result['uri'].startswith('data:image/png;base64,')
    if not local:
        assert result['blocked'] == 'STUDIO_CLOUD_DISABLED'
        assert result['events'][0] == {'source_gate': True}


@pytest.mark.parametrize('payload', [b'{"images":["QUJD"]}', b'\x89PNG\r\n\x1a\n\x00\xffSYNTHETIC'])
@pytest.mark.parametrize('encoding', ['identity', 'gzip', 'deflate', 'raw-deflate'])
def test_json_and_binary_decode_once(monkeypatch, payload, encoding):
    encoded = encode(payload, encoding)
    wire, calls, clients = mock_wire(monkeypatch, [encoded[:1], encoded[1:3], encoded[3:]], headers={
        'Content-Encoding': encoding.removeprefix('raw-'), 'Content-Length': str(len(encoded)),
        'Content-Type': 'application/json' if payload.startswith(b'{') else 'image/png',
    })
    response = _LocalImageTransport('http://127.0.0.1:7860').get('http://127.0.0.1:7860/view', params={'filename': 'fixture.png'})
    assert response.content == payload
    if payload.startswith(b'{'):
        assert response.json() == {'images': ['QUJD']}
    assert response.request == calls[0] and response.status_code == 200
    assert response.headers.get('content-encoding') is None
    assert response.headers['content-length'] == str(len(payload))
    assert clients[0]['trust_env'] is False and clients[0]['follow_redirects'] is False
    assert wire.closed


def encode(payload, encoding):
    if encoding == 'gzip':
        return gzip.compress(payload)
    if encoding == 'deflate':
        return zlib.compress(payload)
    if encoding == 'raw-deflate':
        return zlib.compress(payload)[2:-4]
    return payload


@pytest.mark.parametrize('endpoint', ['http://192.168.1.4:7860', 'https://example.test:443',
    'http://0.0.0.0:7860', 'http://169.254.1.1:7860', 'http://user:password@127.0.0.1:7860',
    'http://127.0.0.1:7860/?query=1', 'http://127.0.0.1:7860/#fragment'])
def test_discovery_rejects_non_loopback_or_ambiguous_origin(monkeypatch, endpoint):
    _, calls, _ = mock_wire(monkeypatch, [])
    with pytest.raises(ValueError, match='LOCAL_AI_LOOPBACK_ENDPOINT_REQUIRED'):
        _LocalImageTransport(endpoint)
    assert not calls


@pytest.mark.parametrize('url', ['http://127.0.0.2:7860/view', 'http://127.0.0.1:8188/view',
    'https://127.0.0.1:7860/view', 'https://external.invalid/view',
    'http://user:password@127.0.0.1:7860/view'])
def test_discovery_request_remains_origin_pinned(monkeypatch, url):
    _, calls, _ = mock_wire(monkeypatch, [])
    with pytest.raises(ValueError, match='LOCAL_AI_DESTINATION_REJECTED'):
        _LocalImageTransport('http://127.0.0.1:7860').get(url)
    assert not calls


@pytest.mark.parametrize('status', [301, 302, 303, 307, 308])
@pytest.mark.parametrize('configured', [False, True])
def test_redirects_reject_without_reading_or_following(monkeypatch, status, configured):
    wire, calls, _ = mock_wire(monkeypatch, [b'ignored'], status=status,
                               headers={'Location': 'https://external.invalid/private'})
    with pytest.raises(ValueError, match='LOCAL_AI_REDIRECT_REJECTED'):
        _LocalImageTransport('http://127.0.0.1:7860', configured=configured).post(
            'http://127.0.0.1:7860/prompt', json={}, follow_redirects=True)
    assert len(calls) == 1 and wire.count == 0 and wire.closed


@pytest.mark.parametrize('headers', [{}, {'Transfer-Encoding': 'chunked'}, {'Content-Length': '1'}])
def test_wire_limit_is_independent_of_declared_length(monkeypatch, headers):
    transport = _LocalImageTransport('http://127.0.0.1:7860')
    transport.max_wire_bytes, transport.max_response_bytes = 8, 64
    wire, _, _ = mock_wire(monkeypatch, [b'12345678', b'9', b'never-read'], headers=headers)
    with pytest.raises(ValueError, match='LOCAL_AI_RESPONSE_TOO_LARGE'):
        transport.get(transport.endpoint + '/view')
    assert wire.count == 9 and wire.closed


@pytest.mark.parametrize('headers', [{}, {'Content-Length': '1'}, {'Transfer-Encoding': 'chunked'}])
@pytest.mark.parametrize('encoding', ['gzip', 'deflate', 'raw-deflate'])
def test_compressed_expansion_is_bounded_before_decoded_allocation(monkeypatch, headers, encoding):
    import zlib
    real = zlib.decompressobj
    limits = []

    class Decoder:
        def __init__(self, *args, **kwargs):
            self.delegate = real(*args, **kwargs)

        def decompress(self, data, max_length=0):
            limits.append(max_length)
            assert 0 < max_length <= 33
            return self.delegate.decompress(data, max_length)

        def __getattr__(self, name):
            return getattr(self.delegate, name)

    monkeypatch.setattr(zlib, 'decompressobj', Decoder)
    transport = _LocalImageTransport('http://127.0.0.1:7860')
    transport.max_wire_bytes, transport.max_response_bytes = 1024, 32
    wire, _, _ = mock_wire(monkeypatch, [encode(b'x' * 100000, encoding)],
                            headers={**headers, 'Content-Encoding': encoding.removeprefix('raw-')})
    with pytest.raises(ValueError, match='LOCAL_AI_RESPONSE_TOO_LARGE'):
        transport.get(transport.endpoint + '/view')
    assert limits and wire.closed


@pytest.mark.parametrize('parts', [
    [gzip.compress(b'{}') + b'extra'],
    [gzip.compress(b'{}'), b'extra', b'never-read'],
    [gzip.compress(b'{}')[:-1]],
    [b'not gzip'],
])
def test_gzip_trailing_truncated_or_malformed_data_fail_closed(monkeypatch, parts):
    wire, _, _ = mock_wire(monkeypatch, parts, headers={'Content-Encoding': 'gzip'})
    with pytest.raises(ValueError, match='LOCAL_AI_'):
        _LocalImageTransport('http://127.0.0.1:7860').get('http://127.0.0.1:7860/view')
    assert wire.closed and wire.count <= sum(map(len, parts[:2]))


@pytest.mark.parametrize('encoding', ['identity', 'gzip', 'deflate', 'raw-deflate'])
@pytest.mark.parametrize('overflow', [False, True])
def test_decoded_limit_exact_boundary_and_one_byte_over(monkeypatch, encoding, overflow):
    payload = b'x' * (32 + int(overflow))
    encoded = encode(payload, encoding)
    wire, _, _ = mock_wire(monkeypatch, [encoded[index:index + 1] for index in range(len(encoded))],
                            headers={'Content-Encoding': encoding.removeprefix('raw-'), 'Content-Length': '1'})
    transport = _LocalImageTransport('http://127.0.0.1:7860')
    transport.max_wire_bytes, transport.max_response_bytes = 1024, 32
    if overflow:
        with pytest.raises(ValueError, match='LOCAL_AI_RESPONSE_TOO_LARGE'):
            transport.get(transport.endpoint + '/view')
    else:
        assert transport.get(transport.endpoint + '/view').content == payload
    assert wire.closed


@pytest.mark.parametrize('encoding', ['gzip', 'deflate', 'raw-deflate'])
def test_compressed_wire_limit_independent_of_small_decoded_body(monkeypatch, encoding):
    encoded = encode(b'{}', encoding)
    wire, _, _ = mock_wire(monkeypatch, [encoded[:-1], encoded[-1:]],
                            headers={'Content-Encoding': encoding.removeprefix('raw-'), 'Content-Length': '1'})
    transport = _LocalImageTransport('http://127.0.0.1:7860')
    transport.max_wire_bytes, transport.max_response_bytes = len(encoded) - 1, 64
    with pytest.raises(ValueError, match='LOCAL_AI_RESPONSE_TOO_LARGE'):
        transport.get(transport.endpoint + '/view')
    assert wire.closed


@pytest.mark.parametrize('encoding', ['br', 'zstd', 'unknown', 'gzip, deflate', ''])
def test_unsupported_encoding_rejected_without_reading(monkeypatch, encoding):
    wire, _, _ = mock_wire(monkeypatch, [b'opaque'], headers={'Content-Encoding': encoding})
    with pytest.raises(ValueError, match='LOCAL_AI_CONTENT_ENCODING_UNSUPPORTED'):
        _LocalImageTransport('http://127.0.0.1:7860').get('http://127.0.0.1:7860/view')
    assert wire.count == 0 and wire.closed


@pytest.mark.parametrize('encoding', ['gzip', 'deflate', 'raw-deflate'])
@pytest.mark.parametrize('corruption', ['trailing', 'concatenated', 'truncated', 'malformed'])
def test_compressed_eof_and_trailing_data_are_not_silently_ignored(monkeypatch, encoding, corruption):
    encoded = encode(b'{}', encoding)
    parts = {'trailing': [encoded, b'extra', b'never-read'],
             'concatenated': [encoded + encoded], 'truncated': [encoded[:-1]],
             'malformed': [b'bad compressed stream']}[corruption]
    wire, _, _ = mock_wire(monkeypatch, parts, headers={'Content-Encoding': encoding.removeprefix('raw-')})
    with pytest.raises(ValueError, match='LOCAL_AI_INVALID_RESPONSE_ENCODING'):
        _LocalImageTransport('http://127.0.0.1:7860').get('http://127.0.0.1:7860/view')
    assert wire.closed and wire.count <= sum(map(len, parts[:2]))


def test_empty_identity_and_http_error_preserve_response_contract(monkeypatch):
    wire, calls, _ = mock_wire(monkeypatch, [], status=503, headers={'Content-Type': 'text/plain'})
    response = _LocalImageTransport('http://127.0.0.1:7860').get('http://127.0.0.1:7860/view')
    assert response.content == b'' and response.headers['content-length'] == '0'
    assert response.headers['content-type'] == 'text/plain' and response.request == calls[0]
    with pytest.raises(httpx.HTTPStatusError):
        response.raise_for_status()
    assert wire.closed


def test_discovery_canonicalizes_localhost_and_preserves_numeric_origin(monkeypatch):
    wire, calls, _ = mock_wire(monkeypatch, [b'{}'])
    transport = _LocalImageTransport('http://localhost:7860')
    assert transport.endpoint == 'http://127.0.0.1:7860'
    transport.get(transport.endpoint + '/view')
    assert calls[0].url.host == '127.0.0.1' and wire.closed


@pytest.mark.parametrize('chunk_size', [1, 2, 3, 7, 166])
def test_raw_deflate_with_zlib_looking_prefix_is_supported(monkeypatch, chunk_size):
    encoded = b'\x78\x9c\x00\x63\xff' + b'A' * 156 + b'\x01\x00\x00\xff\xff'
    assert zlib.decompress(encoded, -zlib.MAX_WBITS) == b'A' * 156
    wire, _, _ = mock_wire(monkeypatch, [encoded[index:index + chunk_size] for index in range(0, len(encoded), chunk_size)],
                            headers={'Content-Encoding': 'deflate'})
    transport = _LocalImageTransport('http://127.0.0.1:7860')
    transport.max_response_bytes = 156
    assert transport.get(transport.endpoint + '/view').content == b'A' * 156
    assert wire.closed


@pytest.mark.parametrize('style', ['automatic1111', 'comfyui'])
def test_persisted_production_preview_keeps_public_local_declaration_cloud_gated(rig, monkeypatch, style):
    from app import asset_provider_config, dependencies
    from app.asset_providers import AssetProviderRegistry
    from app.config import settings
    from app.creative.production_execution import ProductionExecutionService
    monkeypatch.setenv('ASSET_PROVIDER_CONFIG_PATH', str(rig.root / 'image-providers.json'))
    asset_provider_config.save('synthetic-public-image', 'https://example.invalid', 'fixture',
                               api_style=style, local=True, requires_credential=False)
    registry = AssetProviderRegistry()
    monkeypatch.setattr(dependencies, 'asset_provider_registry', registry)
    assert dependencies.refresh_asset_provider('synthetic-public-image')
    assert registry.get('synthetic-public-image').transport.trust_env is True
    rig.service.activate(rig.nid, rig.scope, rig.actor)
    owner = ProductionExecutionService.__new__(ProductionExecutionService)
    owner.workspace, owner.store, owner.image_registry = rig.service, rig.store, registry
    _, calls, _ = mock_wire(monkeypatch, [b'never-dispatched'])
    command = {'operation_id': 'm5.image.t2i', 'request_id': 'synthetic-public-preview',
               'provider_id': 'synthetic-public-image', 'model_id': 'fixture', 'prompt': 'SYNTHETIC_PRIVATE_PROMPT'}
    object.__setattr__(settings, 'enable_cloud', False)
    with pytest.raises(ValueError, match='STUDIO_CLOUD_DISABLED'):
        owner.preview(rig.nid, rig.scope, rig.actor, command, lambda: None)
    object.__setattr__(settings, 'enable_cloud', True)
    with pytest.raises(ValueError, match='STUDIO_CLOUD_EXPLICIT_CONSENT_REQUIRED'):
        owner.preview(rig.nid, rig.scope, rig.actor, command, lambda: None)
    preview, _, _ = owner.preview(rig.nid, rig.scope, rig.actor, {**command, 'allow_cloud': True}, lambda: None)
    assert preview['provider']['local'] is False and preview['automatic_dispatch'] is False
    assert not calls


def test_comfy_guarded_download_keeps_original_media_owner(monkeypatch):
    import app.media_files as media
    calls = []

    class Transport:
        def get(self, url, **kwargs):
            assert '/history/' in url
            return httpx.Response(200, json={'job': {'outputs': {'9': {'images': [{'filename': 'synthetic.png'}]}}}},
                                  request=httpx.Request('GET', url))

    monkeypatch.setattr(media, 'fetch_media_bytes', lambda url, limit, **kwargs:
                        calls.append((url, limit, kwargs)) or b'SYNTHETIC_BINARY')
    monkeypatch.setattr(media, 'inspect_image', lambda data: {'media_type': 'image/png'})
    adapter = ComfyUIImageProvider(Transport(), 'http://127.0.0.1:8188')
    guards = []
    request = AssetGenerationRequest('synthetic', 'fixture', 'prompt', 'task', dispatch_guard=lambda: guards.append(True))
    result = adapter._result(request, 'job')
    assert len(calls) == 1 and calls[0][1:] == (25 * 1024 * 1024, {'configured_provider_endpoint': adapter.endpoint})
    assert len(guards) == 3
    assert result.asset_uri == 'data:image/png;base64,' + base64.b64encode(b'SYNTHETIC_BINARY').decode()
