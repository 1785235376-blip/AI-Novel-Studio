"""Injected HTTP/metadata only: no service call, real inference or quality proof."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from threading import Event, RLock
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
from PIL import Image
import pytest

from app.runtime import Runtime
from app.model_runtime import Modality
from app.stable_identity import StableIdentityStore
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_probes import ollama_locality_evidence
from app.local_ollama_vision import (LocalOllamaVisionProvider, GuardedOllamaVisionHTTP,
    admission, sync_vision_registration, vision_provider_id)
from app.vision_analysis_runtime import VisionAnalysisRequest
from app.creative.director_image_source import DirectorImageSource
from app.director_vision_wire import VisionWireParameters
from app.experimental.model_broker import ModelBrokerService


class Chunks(httpx.AsyncByteStream):
    def __init__(self, values, callback=lambda: None): self.values, self.callback = values, callback
    async def __aiter__(self):
        for value in self.values:
            self.callback()
            yield value


def response(**changes):
    value = {'model': 'fixture-vision:exact', 'done': True, 'done_reason': 'stop',
             'message': {'role': 'assistant', 'content': '{"observation":"test fixture only"}'}}
    value.update(changes)
    return json.dumps(value).encode()


def image():
    out = BytesIO(); Image.new('RGB', (2, 2), 'blue').save(out, format='PNG')
    return out.getvalue()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from app.experimental.flags import runtime_dependencies
    flags = {'ai_execution_v2', 'narrative_production_v2', 'model_broker_v2', 'author_context_inspector_v2', 'asset_lineage_v2'}
    dependencies = runtime_dependencies()
    while True:
        expanded = flags | {item for flag in flags for item in dependencies[flag]}
        if expanded == flags: break
        flags = expanded
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(flags)))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    import socket
    monkeypatch.setattr(socket, 'create_connection', lambda *_a, **_k: pytest.fail('real network forbidden'))
    runtime = Runtime(StableIdentityStore(tmp_path / 'vision-identities.json'))
    checked = ollama_locality_evidence(
        {'digest': 'a'*64, 'size': 100, 'details': {'format': 'gguf'}},
        {'capabilities': ['vision', 'completion'], 'details': {'format': 'gguf'},
         'model_info': {'general.architecture': 'fixture'}})
    candidate = {'id': 'original-model-id', 'provider_id': 'original-provider-id',
        'display_name': 'Fixture only', 'model_name': 'fixture-vision:exact',
        'enabled': True, 'enable_eligible': True, 'runtime_type': 'OLLAMA',
        'runtime_config': {'type': 'OLLAMA', 'management': 'EXTERNAL', 'endpoint': 'http://127.0.0.1:11434'},
        'verified_capabilities': ['TEXT', 'VISION'], 'local': True, 'source_locality': 'LOCAL_VERIFIED',
        'evidence': checked, 'license_confirmed': True, 'validated_at': '2026-10-18T00:00:00Z',
        'enabled_at': '2026-10-18T00:00:01Z', 'model_evidence_fingerprint': 'b'*64,
        'runtime_fingerprint': 'c'*64}
    service = SimpleNamespace(lock=RLock(), registrations={candidate['id']: candidate}, configured_runtime_sources=[])
    events = {'metadata': 0, 'post': 0, 'payload': None}
    def verify(value, **kwargs):
        events['metadata'] += 1
        assert value['id'] == candidate['id']
        return deepcopy(candidate['evidence'])
    service.check_ollama_dispatch = verify
    assets = SimpleNamespace(_providers={}, unregister=lambda _: None)
    bridge = LocalDiscoveryBridge(service, runtime, assets)
    bridge(deepcopy(candidate))
    provider_id = vision_provider_id(candidate)
    provider = runtime.provider_registry.resolve(provider_id)
    def handler(request):
        events['post'] += 1
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        assert 'authorization' not in request.headers
        events['payload'] = json.loads(request.read())
        return httpx.Response(200, stream=Chunks([response()]))
    provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    return SimpleNamespace(runtime=runtime, node=runtime.generation_runtime.vision_analysis_node,
        candidate=candidate, bridge=bridge, provider=provider, provider_id=provider_id, events=events,
        handler=handler)


def request(s, *, guard=lambda: None, cancellation=None, **changes):
    raw = image()
    source = DirectorImageSource(project_id='project', project_incarnation='file:'+str(uuid4()),
        actor_id='actor', scope={'mode': 'local', 'novel_id': 'project'},
        asset={'asset_id': 'asset', 'version': 1, 'sha256': sha256(raw).hexdigest()},
        media_type='image/png', byte_count=len(raw), width=2, height=2)
    value = dict(provider_id=s.provider_id, model_id=s.candidate['id'], job_id=str(uuid4()),
        route_digest=s.node.binding(s.provider_id, s.candidate['id'])['route_digest'],
        source=source, content=raw, prompt='Describe visible observations with uncertainty.',
        parameters=VisionWireParameters(), deadline=time.monotonic()+30,
        dispatch_guard=guard, cancellation=cancellation or Event())
    value.update(changes)
    return VisionAnalysisRequest(**value)


def test_explicit_bridge_preserves_text_and_reads_never_probe(setup):
    s = setup
    text = s.runtime.provider_registry.resolve(s.candidate['provider_id'])
    text_model = s.runtime.model_registry.resolve(s.candidate['provider_id'], s.candidate['id'], Modality.TEXT)
    sync_vision_registration(s.bridge, deepcopy(s.candidate))
    assert s.runtime.provider_registry.resolve(s.candidate['provider_id']) is text
    assert s.runtime.model_registry.resolve(s.candidate['provider_id'], s.candidate['id'], Modality.TEXT) == text_model
    binding = s.node.binding(s.provider_id, s.candidate['id'])
    assert binding['route']['model_sha256'] == 'a'*64
    assert s.events['metadata'] == s.events['post'] == 0


def test_actual_adapter_uses_exact_bytes_and_bounded_injected_post(setup):
    s = setup; req = request(s)
    result = s.node.execute(req)
    import base64
    assert base64.b64decode(s.events['payload']['messages'][0]['images'][0]) == req.content
    assert s.events['payload']['options']['num_predict'] == 512
    assert s.events['metadata'] == 2 and s.events['post'] == 1
    assert result.source_digest == req.source.asset.sha256
    assert result.route_digest == req.route_digest
    assert result.quality_verification == 'NOT_RUN'
    assert result.output_digest == sha256(result.text.encode()).hexdigest()


@pytest.mark.parametrize('field,value', [('license_confirmed', False), ('enabled', False),
    ('enable_eligible', False), ('local', False), ('source_locality', 'UNKNOWN'),
    ('verified_capabilities', ['TEXT']), ('runtime_fingerprint', None), ('model_evidence_fingerprint', '')])
def test_missing_current_trusted_evidence_never_available(setup, field, value):
    s = setup; s.candidate[field] = value
    with pytest.raises((ValueError, RuntimeError)): s.node.binding(s.provider_id, s.candidate['id'])
    assert s.events['post'] == s.events['metadata'] == 0


@pytest.mark.parametrize('field,value', [('reported_capabilities', ['completion']), ('digest', 'bad'),
    ('size', 0), ('source_locality', 'REMOTE'), ('remote_host', 'private-cloud'), ('locality_fingerprint', None)])
def test_changed_weight_vision_and_locality_metadata_fails_closed(setup, field, value):
    s = setup; s.candidate['evidence'][field] = value
    with pytest.raises((ValueError, RuntimeError)): s.node.binding(s.provider_id, s.candidate['id'])
    assert s.events['post'] == 0


@pytest.mark.parametrize('endpoint', ['http://example.com:11434', 'http://192.168.1.2:11434',
    'http://user:pass@127.0.0.1:11434', 'http://127.0.0.1:11434?token=secret'])
def test_nonloopback_credentials_and_queries_rejected(setup, endpoint):
    s = setup; s.candidate['runtime_config']['endpoint'] = endpoint
    with pytest.raises(ValueError): admission(s.candidate)
    assert s.events['post'] == 0


def test_disable_only_vision_helper_keeps_text_identity(setup):
    s = setup; text = s.runtime.provider_registry.resolve(s.candidate['provider_id'])
    sync_vision_registration(s.bridge, {**s.candidate, 'enabled': False})
    with pytest.raises(RuntimeError): s.runtime.provider_registry.resolve(s.provider_id)
    assert s.runtime.provider_registry.resolve(s.candidate['provider_id']) is text
    sync_vision_registration(s.bridge, {**s.candidate, 'enabled': False})
    assert s.runtime.provider_registry.resolve(s.candidate['provider_id']) is text


def test_private_broker_inventory_remains_job_blocked_and_no_probe(setup):
    s = setup
    broker = object.__new__(ModelBrokerService); broker.runtime = s.runtime
    rows = broker.candidates(local_vision_only=True)
    assert len(rows) == 1 and rows[0]['runtime_available'] is True
    assert rows[0]['available'] is rows[0]['execution_available'] is False
    assert rows[0]['reasons'] == ['DIRECTOR_IMAGE_JOB_NOT_INTEGRATED']
    assert 'http://' not in json.dumps(rows) and 'endpoint' not in json.dumps(rows)
    assert 'price' not in rows[0] and 'latency_ms' not in rows[0]
    assert s.events['metadata'] == s.events['post'] == 0
    with pytest.raises(ValueError): broker.candidates(local_vision_only=True, local_text_only=True)
    with pytest.raises(ValueError): broker.candidates(local_vision_only=True, local_ocr_only=True)


def test_cancel_and_revocation_before_post_send_nothing(setup):
    s = setup; req = request(s); req.cancellation.set()
    with pytest.raises(ValueError, match='CANCELLED'): s.node.execute(req)
    assert s.events['post'] == 0
    active = True
    def guard():
        if not active: raise PermissionError('revoked')
    req = request(s, guard=guard); active = False
    with pytest.raises(PermissionError): s.node.execute(req)
    assert s.events['post'] == 0


def test_cancellation_during_response_discards_and_never_retries(setup):
    s = setup; req = request(s)
    def handler(request):
        s.events['post'] += 1
        return httpx.Response(200, stream=Chunks([b'x'*16384, response()], req.cancellation.set))
    s.provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match='CANCELLED'): s.node.execute(req)
    assert s.events['post'] == 1


def test_source_revocation_during_response_discards_output(setup):
    s = setup; active = True
    def guard():
        if not active: raise PermissionError('source deleted')
    req = request(s, guard=guard)
    def handler(request):
        nonlocal active
        active = False
        return httpx.Response(200, stream=Chunks([response()]))
    s.provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    with pytest.raises(PermissionError): s.node.execute(req)


def test_weights_changed_after_response_discard_result(setup):
    s = setup; checks = 0
    def verify(value, **kwargs):
        nonlocal checks
        checks += 1
        return {**s.candidate['evidence'], 'digest': ('d'*64 if checks == 2 else 'a'*64)}
    s.bridge.service.check_ollama_dispatch = verify
    with pytest.raises(ValueError, match='MODEL_CHANGED'): s.node.execute(request(s))
    assert s.events['post'] == 1 and checks == 2


@pytest.mark.parametrize('status,headers,body', [(302, {'location': 'http://example.com'}, response()),
    (500, {}, response()), (200, {'content-encoding': 'gzip'}, b'garbage'),
    (200, {'content-length': '128001'}, b''), (200, {}, b'x'*128001),
    (200, {'content-length': '999'}, response()), (200, {}, response(model='other'))])
def test_http_errors_bounds_and_response_binding_do_not_retry(setup, status, headers, body):
    s = setup
    def handler(request):
        s.events['post'] += 1
        return httpx.Response(status, headers=headers, stream=Chunks([body]))
    s.provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError): s.node.execute(request(s))
    assert s.events['post'] == 1


def test_deadline_and_changed_route_before_dispatch_send_nothing(setup):
    s = setup; req = request(s, deadline=time.monotonic()+0.01); time.sleep(0.02)
    with pytest.raises(ValueError, match='TIMEOUT'): s.node.execute(req)
    req = request(s); s.candidate['enabled_at'] = 'changed'
    with pytest.raises(ValueError): s.node.execute(req)
    assert s.events['post'] == 0


def test_original_flags_block_runtime_before_inference(setup, monkeypatch):
    s = setup; req = request(s); monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    from fastapi import HTTPException
    with pytest.raises(HTTPException): s.node.execute(req)
    assert s.events['post'] == 0


def test_runtime_provider_replaced_mid_response_discards_output(setup):
    s = setup; req = request(s)
    def handler(request):
        s.events['post'] += 1
        sync_vision_registration(s.bridge, deepcopy(s.candidate))
        return httpx.Response(200, stream=Chunks([response()]))
    s.provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match='ROUTE_CHANGED'): s.node.execute(req)
    assert s.events['post'] == 1


def test_upload_chunks_reauthorize_before_each_send(setup):
    s = setup; checks = 0
    def guard():
        nonlocal checks
        checks += 1
        if checks >= 3: raise PermissionError('upload revoked')
    with pytest.raises(PermissionError):
        s.provider.transport.post('http://127.0.0.1:11434', {'image': 'x'*200000},
            guard=guard, deadline=time.monotonic()+30)
    assert checks >= 3 and s.events['post'] == 0


def test_final_authorization_revocation_never_returns_text(setup):
    s = setup; active = True; checks = 0
    def guard():
        if not active: raise PermissionError('revoked before publication')
    req = request(s, guard=guard)
    def verify(value, **kwargs):
        nonlocal active, checks
        checks += 1
        if checks == 2: active = False
        return deepcopy(s.candidate['evidence'])
    s.bridge.service.check_ollama_dispatch = verify
    with pytest.raises(PermissionError): s.node.execute(req)
    assert s.events['post'] == 1


def test_no_registration_from_constructing_runtime_or_unsupported_candidate(tmp_path):
    runtime = Runtime(StableIdentityStore(tmp_path/'empty-identities.json'))
    assert not any('IMAGE_UNDERSTANDING' in row.capabilities for row in runtime.model_registry.descriptors())
    assert runtime.generation_runtime.vision_analysis_node.providers is runtime.provider_registry


def test_model_center_disable_and_reenable_vision_keeps_stable_identity(setup):
    s = setup
    original = s.node.binding(s.provider_id, s.candidate['id'])
    sync_vision_registration(s.bridge, {**s.candidate, 'enabled': False})
    sync_vision_registration(s.bridge, deepcopy(s.candidate))
    current = s.node.binding(s.provider_id, s.candidate['id'])
    assert original['provider_uuid'] == current['provider_uuid']
    assert original['model_uuid'] == current['model_uuid']


def test_director_request_cannot_claim_wrong_bytes_or_route(setup):
    s = setup
    with pytest.raises(ValueError): request(s, content=b'wrong')
    req = request(s, route_digest='d'*64)
    with pytest.raises(ValueError, match='ROUTE_CHANGED'): s.node.execute(req)
    assert s.events['post'] == 0


def test_original_model_center_validate_enable_disable_pipeline(setup, tmp_path):
    from test_local_ai_discovery import service, scan, ollama, approve_license
    from app.asset_providers import AssetProviderRegistry
    s = setup; original = service(tmp_path/'original-center')
    ollama(original.client, name='vision-fixture:exact', capabilities=('completion', 'vision'))
    bridge = LocalDiscoveryBridge(original, s.runtime, AssetProviderRegistry())
    original.route_bridge = bridge
    candidate = scan(original)['candidates'][0]
    original.validate(candidate['id']); original.register(candidate['id'])
    approve_license(original, candidate['id'])
    enabled = original.enable(candidate['id'])
    key = vision_provider_id(enabled)
    count = len(original.client.calls)
    binding = s.node.binding(key, enabled['id'])
    assert binding['route']['model_sha256'] == 'a'*64
    assert len(original.client.calls) == count  # observations do not probe
    assert s.runtime.model_registry.resolve(enabled['provider_id'], enabled['id'], Modality.TEXT)
    assert s.runtime.model_registry.resolve(key, enabled['id'], Modality.VISION)
    original.disable(enabled['id'])
    with pytest.raises(RuntimeError): s.node.binding(key, enabled['id'])
    assert len(original.client.calls) == count


from test_v2_independent_workspace import rig, import_asset


def test_original_asset_exact_source_to_runtime_without_job_publication(rig, setup):
    from app.creative.director_image_source import DirectorImageSources
    s = setup; asset = import_asset(rig)
    selected = {'asset_id': asset['id'], 'version': asset['version'], 'sha256': asset['sha256']}
    sources = DirectorImageSources(rig.service)
    with sources.read(rig.nid, rig.scope, rig.actor, selected, guard=lambda: None) as (source, data):
        pin = source.model_dump()
    # Source/Asset/project locks are released before any simulated HTTP I/O.
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    def current_source():
        with sources.read(rig.nid, rig.scope, rig.actor, selected,
                guard=lambda: None, expected=pin):
            pass
    req = request(s, source=source, content=data, guard=current_source)
    result = s.node.execute(req)
    assert result.source_digest == asset['sha256']
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    assert rig.chapters.list(rig.nid) == []
    assert s.events['post'] == 1


def test_direct_adapter_flags_cannot_bypass_original_execution_policy(setup, monkeypatch):
    s = setup; req = request(s); monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    from fastapi import HTTPException
    with pytest.raises(HTTPException): s.provider.analyze_image(req)
    assert s.events['post'] == s.events['metadata'] == 0


@pytest.mark.parametrize('stage', ['headers', 'body'])
@pytest.mark.parametrize('stop', ['deadline', 'cancel', 'revoke'])
def test_async_io_absolute_deadline_and_cancellation_close_inflight(stage, stop):
    import asyncio
    state = {'stopped': False, 'closed': False, 'calls': 0, 'chunks': 0}
    def guard():
        if state['stopped']:
            if stop == 'revoke': raise PermissionError('revoked')
            raise ValueError('CANCELLED')
    async def delay():
        await asyncio.sleep(.01)
        if stop != 'deadline': state['stopped'] = True
    class Drip(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await delay()
                state['chunks'] += 1
                yield b'x'
        async def aclose(self): state['closed'] = True
    async def handler(req):
        state['calls'] += 1
        if stage == 'headers':
            try:
                while True: await delay()
            finally: state['closed'] = True
        return httpx.Response(200, stream=Drip())
    transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    started = time.monotonic()
    with pytest.raises((ValueError, PermissionError), match='TIMEOUT|CANCELLED|revoked'):
        transport.post('http://127.0.0.1:11434', {}, guard=guard,
                       deadline=started + (.08 if stop == 'deadline' else 5))
    assert time.monotonic() - started < 1
    assert state['closed'] and state['calls'] == 1
    if stage == 'body': assert state['chunks'] < 20


@pytest.mark.parametrize('error', [httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError])
def test_transport_errors_never_leak_endpoint_or_raw_message(error):
    async def handler(req): raise error('secret endpoint http://127.0.0.1:1234/private')
    transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError) as raised:
        transport.post('http://127.0.0.1:11434', {}, guard=lambda: None, deadline=time.monotonic()+1)
    assert str(raised.value) == 'VISION_HTTP_TRANSPORT_FAILED'
    assert raised.value.__suppress_context__


@pytest.mark.parametrize('path', ['/api/tags', '/api/show'])
@pytest.mark.parametrize('stage', ['headers', 'body'])
@pytest.mark.parametrize('stop', ['cancel', 'deadline'])
def test_original_metadata_checker_cancellation_closes_request(setup, path, stage, stop):
    import asyncio
    from app.model_center.discovery import LocalDiscoveryService
    s = setup
    # Use the real original validator with bounded injected metadata I/O.
    service = s.bridge.service
    service.check_ollama_dispatch = lambda candidate, **kw: LocalDiscoveryService.check_ollama_dispatch(service, candidate, **kw)
    state = {'closed': False, 'paths': []}
    req = request(s, deadline=time.monotonic()+(.08 if stop == 'deadline' else 5))
    class MetadataDrip(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(.01)
                if stop == 'cancel': req.cancellation.set()
                yield b' '
        async def aclose(self): state['closed'] = True
    async def handler(http_request):
        state['paths'].append(http_request.url.path)
        if http_request.url.path == path:
            if stage == 'body': return httpx.Response(200, stream=MetadataDrip())
            try:
                if stop == 'cancel': req.cancellation.set()
                await asyncio.sleep(5)
            finally: state['closed'] = True
        tag = {'name': s.candidate['model_name'], 'digest': 'a'*64, 'size': 100, 'details': {'format': 'gguf'}}
        return httpx.Response(200, stream=Chunks([json.dumps({'models': [tag]}).encode()]))
    s.provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    started = time.monotonic()
    with pytest.raises(ValueError, match='CANCELLED|TIMEOUT'): s.node.execute(req)
    assert time.monotonic() - started < 1
    assert state['closed'] and '/api/chat' not in state['paths']
    assert state['paths'] == (['/api/tags'] if path == '/api/tags' else ['/api/tags', '/api/show'])


@pytest.mark.parametrize('raw', [
    b'{"remote_host":"cloud.example","remote_host":""}',
    b'{"capabilities":["vision"],"capabilities":["completion"]}',
    b'{"digest":"a","digest":"b"}', b'{"size":NaN}', b'{"size":Infinity}',
    b'null', b'1', b'"text"'])
def test_metadata_json_rejects_ambiguous_nonfinite_scalar_and_recursive_values(raw):
    async def handler(req): return httpx.Response(200, stream=Chunks([raw]))
    client = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler)).metadata_client(
        guard=lambda: None, deadline=time.monotonic()+1)
    with pytest.raises(ValueError, match='^VISION_METADATA_RESPONSE_INVALID$'):
        client.json('http://127.0.0.1:11434', '/api/show', body={'model': 'fixture'})


def test_metadata_parser_recursion_failure_is_sanitized(monkeypatch):
    async def handler(req): return httpx.Response(200, stream=Chunks([b'{}']))
    client = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler)).metadata_client(
        guard=lambda: None, deadline=time.monotonic()+1)
    def recursive(*args, **kwargs): raise RecursionError('private parser detail')
    monkeypatch.setattr('app.local_ollama_vision.json.loads', recursive)
    with pytest.raises(ValueError, match='^VISION_METADATA_RESPONSE_INVALID$'):
        client.json('http://127.0.0.1:11434', '/api/tags')


def test_oversized_decimal_content_length_is_sanitized():
    async def handler(req):
        return httpx.Response(200, headers={'content-length': '9' * 5000}, stream=Chunks([]))
    transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match='^VISION_RESPONSE_BYTE_LIMIT$'):
        transport.post('http://127.0.0.1:11434', {}, guard=lambda: None, deadline=time.monotonic()+1)
