"""Explicit-enable Ollama vision adapter; no discovery/probe on observation.

Original Model Center registration owns admission. A separate provider key keeps
TEXT registries unchanged. No credentials, process starts or automatic fallback.
The original Director Job path remains blocked even when this adapter is ready.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
import threading
import time

from .creative.director_image_preview import digest
from .director_vision_wire import OllamaDirectorVisionCodec, MAX_RESPONSE_BYTES
from .model_center.discovery_types import local_endpoint
from .model_runtime import ModelDescriptor, ProviderDescriptor, Modality

MAX_WIRE_REQUEST_BYTES = 6 * 1024 * 1024


def vision_provider_id(candidate):
    return 'local-vision-v3-' + digest(['original-model-center', candidate['provider_id'], candidate['id']])[:40]


def admission(candidate):
    """Validate trusted original host data only, never an HTTP admission body."""
    evidence = candidate.get('evidence') or {}
    config = candidate.get('runtime_config') or {}
    if (candidate.get('enabled') is not True or candidate.get('enable_eligible') is not True
            or candidate.get('runtime_type') != 'OLLAMA' or config.get('type') != 'OLLAMA'
            or config.get('management', 'EXTERNAL') != 'EXTERNAL'
            or candidate.get('local') is not True or candidate.get('source_locality') != 'LOCAL_VERIFIED'
            or evidence.get('source_locality') != 'LOCAL_VERIFIED'
            or not {'VISION', 'TEXT'}.issubset(candidate.get('verified_capabilities', []))
            or not {'vision', 'completion'}.issubset(evidence.get('reported_capabilities', []))
            or candidate.get('license_confirmed') is not True
            or not candidate.get('validated_at') or not candidate.get('enabled_at')
            or any(evidence.get(key) not in (None, '') for key in ('remote_model', 'remote_host', 'show_remote_model', 'show_remote_host'))):
        raise ValueError('VISION_LOCAL_ADMISSION_REQUIRED')
    endpoint = local_endpoint(config.get('endpoint'))
    if endpoint != config['endpoint']:
        raise ValueError('VISION_CANONICAL_LOOPBACK_REQUIRED')
    model_hash = evidence.get('digest', '').removeprefix('sha256:').lower()
    for value in (model_hash, evidence.get('locality_fingerprint'), candidate.get('model_evidence_fingerprint'),
                  candidate.get('runtime_fingerprint')):
        if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
            raise ValueError('VISION_LOCAL_EVIDENCE_REQUIRED')
    if type(evidence.get('size')) is not int or evidence['size'] <= 0:
        raise ValueError('VISION_LOCAL_EVIDENCE_REQUIRED')
    for key in ('id', 'provider_id', 'model_name'):
        value = candidate.get(key)
        if (type(value) is not str or not value.strip() or len(value) > 240
                or any(ord(c) < 32 for c in value)):
            raise ValueError('VISION_LOCAL_IDENTITY_REQUIRED')
    value = {'contract': 'LOCAL_OLLAMA_VISION_ADMISSION_V3', 'provider_id': vision_provider_id(candidate),
        'model_id': candidate['id'], 'host_provider_id': candidate['provider_id'],
        'model_name': candidate['model_name'], 'endpoint': endpoint,
        'model_sha256': model_hash, 'locality_fingerprint': evidence['locality_fingerprint'],
        'model_evidence_fingerprint': candidate['model_evidence_fingerprint'],
        'runtime_fingerprint': candidate['runtime_fingerprint'], 'enabled_at': candidate['enabled_at'],
        'validated_at': candidate['validated_at'], 'license_confirmed': True,
        'source_locality': 'LOCAL_VERIFIED', 'operation': 'IMAGE_UNDERSTANDING'}
    value['admission_digest'] = digest(value)
    return value


class GuardedOllamaVisionHTTP:
    """Bounded streaming HTTP I/O despite buffered (stream:false) model output."""
    def __init__(self, *, transport=None):
        # Transport injection is for host tests; never deserialized from requests.
        self.transport = transport

    def post(self, endpoint, payload, *, guard, deadline):
        return self.request(endpoint, '/api/chat', payload, guard=guard, deadline=deadline,
                            limit=MAX_RESPONSE_BYTES)

    def metadata_client(self, *, guard, deadline):
        transport = self
        class MetadataClient:
            def json(self, endpoint, path, *, body=None):
                if path not in {'/api/tags', '/api/show'}:
                    raise ValueError('VISION_METADATA_PATH_REJECTED')
                raw = transport.request(endpoint, path, body, guard=guard, deadline=deadline,
                                        limit=4 * 1024 * 1024)
                def reject_constant(_value): raise ValueError('invalid metadata constant')
                def unique_pairs(pairs):
                    value = {}
                    for key, item in pairs:
                        if key in value: raise ValueError('duplicate metadata key')
                        value[key] = item
                    return value
                try:
                    result = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_pairs)
                    if not isinstance(result, (dict, list)): raise ValueError('invalid metadata shape')
                except (ValueError, UnicodeError, RecursionError):
                    raise ValueError('VISION_METADATA_RESPONSE_INVALID') from None
                guard()
                if time.monotonic() >= deadline: raise ValueError('VISION_HTTP_TIMEOUT')
                return result
        return MetadataClient()

    def request(self, endpoint, path, payload, *, guard, deadline, limit):
        import asyncio
        import httpx
        endpoint = local_endpoint(endpoint)
        wire = (json.dumps(payload, ensure_ascii=False, allow_nan=False,
                           separators=(',', ':')).encode() if payload is not None else b'')
        if len(wire) > MAX_WIRE_REQUEST_BYTES: raise ValueError('VISION_REQUEST_BYTE_LIMIT')
        def current():
            guard()
            if time.monotonic() >= deadline: raise ValueError('VISION_HTTP_TIMEOUT')
        current()
        if not 0 < deadline - time.monotonic() <= 180: raise ValueError('VISION_HTTP_TIMEOUT')
        # No nested loop or worker thread: the original synchronous Job worker owns this call.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise ValueError('VISION_SYNC_WORKER_REQUIRED')

        async def transfer():
            async def chunks():
                for offset in range(0, len(wire), 65536):
                    current()
                    yield wire[offset:offset + 65536]
                current()
            transport = self.transport if self.transport is not None else httpx.AsyncHTTPTransport(
                retries=0, trust_env=False)
            async with httpx.AsyncClient(transport=transport, trust_env=False,
                    follow_redirects=False, timeout=httpx.Timeout(10)) as client:
                async with client.stream('POST' if payload is not None else 'GET', endpoint + path,
                        content=chunks(), headers={'Content-Type': 'application/json',
                            'Accept': 'application/json', 'Accept-Encoding': 'identity'}) as response:
                    current()
                    if response.status_code != 200: raise ValueError('VISION_HTTP_STATUS_REJECTED')
                    if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                        raise ValueError('VISION_HTTP_ENCODING_REJECTED')
                    length = response.headers.get('content-length')
                    if length is not None and (len(length) > 10 or not length.isascii() or not length.isdecimal() or int(length) > limit):
                        raise ValueError('VISION_RESPONSE_BYTE_LIMIT')
                    data = bytearray()
                    async for block in response.aiter_raw():
                        current()
                        if len(data) + len(block) > limit: raise ValueError('VISION_RESPONSE_BYTE_LIMIT')
                        data.extend(block)
                    current()
                    if length is not None and len(data) != int(length): raise ValueError('VISION_RESPONSE_TRUNCATED')
                    return bytes(data)

        async def bounded():
            task = asyncio.create_task(transfer())
            try:
                while True:
                    current()
                    remaining = deadline - time.monotonic()
                    done, _ = await asyncio.wait({task}, timeout=min(.05, max(0, remaining)))
                    current()
                    if done: return task.result()
            finally:
                if not task.done(): task.cancel()
                # Await cancellation so the HTTP context closes before returning.
                await asyncio.gather(task, return_exceptions=True)
        try:
            return asyncio.run(bounded())
        except httpx.HTTPError:
            raise ValueError('VISION_HTTP_TRANSPORT_FAILED') from None


class LocalOllamaVisionProvider:
    supports_dispatch_guard = True

    def __init__(self, bridge, candidate, *, transport=None):
        self.bridge = bridge
        self.candidate_id = candidate['id']
        self._admitted = admission(deepcopy(candidate))
        self.provider_id, self.model_id = self._admitted['provider_id'], self._admitted['model_id']
        self.transport = GuardedOllamaVisionHTTP(transport=transport)
        self._lock = threading.Lock()

    def route_snapshot(self):
        # guard only reads original registration; never health/model probes.
        current = admission(deepcopy(self.bridge.guard(self.candidate_id)))
        if current != self._admitted: raise ValueError('VISION_LOCAL_ADMISSION_CHANGED')
        return current

    def analyze_image(self, request):
        from .vision_analysis_runtime import VisionAnalysisRequest, VisionAnalysisResponse
        if type(request) is not VisionAnalysisRequest or (request.provider_id, request.model_id) != (self.provider_id, self.model_id):
            raise ValueError('VISION_LOCAL_REQUEST_REQUIRED')
        if not self._lock.acquire(blocking=False): raise ValueError('VISION_LOCAL_BUSY')
        try:
            route = self.route_snapshot()
            def current():
                from .creative.ai_execution import require_execution
                require_execution()
                request.current()
                if self.route_snapshot() != route: raise ValueError('VISION_LOCAL_ADMISSION_CHANGED')
            current()
            # Only explicit inference performs a metadata recheck. Observation
            # calls never probe. Original owner invalidates stale registrations.
            def check_weights():
                current()
                checked = self.bridge.service.check_ollama_dispatch(
                    deepcopy(self.bridge.guard(self.candidate_id)),
                    metadata_client=self.transport.metadata_client(guard=current, deadline=request.deadline),
                    guard=current)
                current()
                if (checked.get('source_locality') != 'LOCAL_VERIFIED'
                        or checked.get('locality_fingerprint') != route['locality_fingerprint']
                        or checked.get('digest', '').removeprefix('sha256:').lower() != route['model_sha256']
                        or not {'vision', 'completion'}.issubset(checked.get('reported_capabilities', []))
                        or any(checked.get(key) not in (None, '') for key in
                               ('remote_model', 'remote_host', 'show_remote_model', 'show_remote_host'))):
                    raise ValueError('VISION_LOCAL_MODEL_CHANGED')
            check_weights()
            payload = OllamaDirectorVisionCodec.encode(model_id=route['model_name'], source=request.source,
                content=request.content, prompt=request.prompt, parameters=request.parameters, guard=current)
            current()
            raw = self.transport.post(route['endpoint'], payload, guard=current, deadline=request.deadline)
            current()
            text = OllamaDirectorVisionCodec.decode(raw, model_id=route['model_name'])
            check_weights()
            current()
            return VisionAnalysisResponse(self.provider_id, self.model_id, request.source.asset.sha256,
                request.route_digest, text, sha256(text.encode()).hexdigest())
        finally:
            self._lock.release()


def sync_vision_registration(bridge, candidate):
    """Explicit original enable/disable hook; no replacement of TEXT entries."""
    key = vision_provider_id(candidate)
    runtime = bridge.runtime
    was_registered = runtime.provider_registry.contains(key)
    try:
        provider = LocalOllamaVisionProvider(bridge, candidate)
    except (ValueError, TypeError, KeyError, AttributeError):
        if was_registered:
            old = next(row for row in runtime.provider_registry.descriptors() if row.provider_id == key)
            if not old.configured or not old.available: return
            old_provider = runtime.provider_registry.resolve(key)
            from dataclasses import replace
            runtime.provider_registry.register(replace(old, configured=False, available=False, health_status='disabled'),
                old_provider, replace=True)
            model = next(row for row in runtime.model_registry.descriptors() if row.provider_id == key and row.model_id == candidate['id'])
            runtime.model_registry.register(replace(model, enabled=False), replace=True)
        return
    runtime.provider_registry.register(ProviderDescriptor(key, 'Local image understanding', 'local',
        frozenset({Modality.VISION}), True, True, 'admitted_metadata_inference_not_run'), provider, replace=True)
    runtime.model_registry.register(ModelDescriptor(candidate['id'], key, 'Local image understanding',
        Modality.VISION, frozenset({'IMAGE_UNDERSTANDING'}), enabled=True), replace=True)
