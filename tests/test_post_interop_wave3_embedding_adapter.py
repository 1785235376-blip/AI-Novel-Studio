"""Real bounded HTTP and original Model Center lifecycle, synthetic vector server.

The transport is real. Vector semantics, actual Ollama/model inference and GPU
performance are NOT_RUN, not inferred from this contract fixture.
"""
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest
from app.asset_providers import AssetProviderRegistry
from app.experimental.common import StaleSourceError
from app.experimental.embeddings import EmbeddingInput, LocalOllamaEmbeddingProvider, EmbeddingService
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_types import LocalRuntimeInput
from app.model_runtime import ModelRegistry, ProviderRegistry, ModelRuntimeError
from test_local_ai_discovery import service, scan, approve_license
from test_r3_planning import planning_env


@pytest.fixture
def registered(tmp_path, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'visual_embeddings')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    calls, behavior = [], {'dimensions': 3, 'digest': 'a' * 64, 'remote': False}
    class Server(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self): self.reply(None)
        def do_POST(self): self.reply(json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0)))))
        def reply(self, body):
            calls.append((self.path, body))
            if self.path == '/api/tags': value = {'models': [{'name': 'synthetic-embedding:latest', 'size': 1234, 'digest': behavior['digest'], 'details': {'format': 'gguf', 'family': 'bert'}}]}
            elif self.path == '/api/show': value = {'capabilities': ['embedding'], 'details': {'format': 'gguf', 'family': 'bert'}, 'model_info': {'general.architecture': 'bert'}}
            elif self.path == '/api/version': value = {'version': 'synthetic-test-only'}
            elif self.path == '/api/embed': value = {'model': 'synthetic-embedding:latest', 'embeddings': [[1.0] * behavior['dimensions'] for _ in body['input']]}
            else: self.send_error(404); return
            if behavior['remote'] and self.path == '/api/show': value['remote_host'] = 'https://ollama.com'
            raw = json.dumps(value).encode(); self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    http = ThreadingHTTPServer(('127.0.0.1', 0), Server); thread = Thread(target=http.serve_forever, daemon=True); thread.start()
    svc = service(tmp_path)
    from app.model_center.discovery_probes import LocalProbeClient
    svc.client = LocalProbeClient(timeout=.2)
    svc.configure_runtime(LocalRuntimeInput(name='Synthetic contract endpoint', type='OLLAMA', endpoint=f'http://127.0.0.1:{http.server_port}'))
    runtime = SimpleNamespace(provider_registry=ProviderRegistry(), model_registry=ModelRegistry())
    bridge = LocalDiscoveryBridge(svc, runtime, AssetProviderRegistry()); svc.route_bridge = bridge
    row = next(row for row in scan(svc)['candidates'] if row['model_name'] == 'synthetic-embedding:latest')
    checked = svc.validate(row['id']); assert checked['verified_capabilities'] == ['EMBEDDING']
    svc.register(row['id']); approve_license(svc, row['id']); svc.enable(row['id'])
    calls.clear()
    yield SimpleNamespace(service=svc, bridge=bridge, runtime=runtime, row=row, calls=calls, behavior=behavior, root=tmp_path)
    http.shutdown(); http.server_close(); thread.join(timeout=5)


def test_real_local_http_contract_does_not_register_text_or_call_on_read(registered):
    e = registered
    assert not e.runtime.model_registry.contains(e.row['provider_id'], e.row['id'])
    provider = LocalOllamaEmbeddingProvider(e.bridge, e.row['id'], 3)
    assert provider.capability.input_types == ['TEXT']
    assert e.calls == []
    vectors = provider.embed([EmbeddingInput('TEXT', 'Synthetic reference')])
    assert vectors == [[1.0, 1.0, 1.0]]
    assert next(body for path, body in e.calls if path == '/api/embed') == {'model': 'synthetic-embedding:latest', 'input': ['Synthetic reference'], 'truncate': False, 'keep_alive': '0s'}
    assert not any(path in {'/api/generate', '/api/pull'} for path, _ in e.calls)


@pytest.mark.parametrize('change', ['disable', 'remote', 'digest', 'dimension', 'v1'])
def test_original_revocation_remote_identity_dimensions_and_v1_fail_closed(registered, monkeypatch, change):
    e = registered; provider = LocalOllamaEmbeddingProvider(e.bridge, e.row['id'], 3)
    if change == 'disable': e.service.disable(e.row['id'])
    elif change == 'remote': e.behavior['remote'] = True
    elif change == 'digest': e.behavior['digest'] = 'b' * 64
    elif change == 'dimension': e.behavior['dimensions'] = 2
    elif change == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    with pytest.raises((ValueError, ModelRuntimeError)):
        provider.embed([EmbeddingInput('TEXT', 'Synthetic reference')])
    if change != 'dimension': assert not any(path == '/api/embed' for path, _ in e.calls)


def test_metadata_probe_cannot_bypass_final_source_and_permission_guard(registered):
    e = registered; provider = LocalOllamaEmbeddingProvider(e.bridge, e.row['id'], 3)
    def deny(): raise ValueError('source permission revoked')
    with pytest.raises(ValueError, match='permission revoked'):
        provider.embed_guarded([EmbeddingInput('TEXT', 'Synthetic reference')], deny)
    assert not any(path == '/api/embed' for path, _ in e.calls)


def test_selected_original_registration_persists_index_and_requires_reenable_after_restart(registered, planning_env):
    e = planning_env; host = registered
    service = EmbeddingService(e.store, e.novels, e.chapter_service, discovery_bridge=host.bridge)
    row = service.create_index(e.nid, e.scope, 'writer', {'title': 'Registered vector index', 'entities': [{'entity_type': 'CHARACTER', 'entity_id': 'alice'}], 'registration_id': host.row['id'], 'dimensions': 3})
    assert row['status'] == 'DRAFT' and service.status()['status'] == 'NOT_CONFIGURED'
    ready = service.rebuild(e.nid, e.scope, 'writer', row['id'], 1)
    assert ready['status'] == 'ACTIVE' and ready['model']['verification'] == 'CONTRACT_VERIFIED'
    assert service.query(e.nid, e.scope, {'index_id': row['id'], 'text': 'Synthetic'})['metric'] == 'COSINE'
    from app.model_center.discovery import LocalDiscoveryService
    reloaded = LocalDiscoveryService(host.service.center, host.service.path, client=host.service.client)
    service.discovery_bridge = LocalDiscoveryBridge(reloaded, host.runtime, AssetProviderRegistry())
    index = service.indexes(e.nid, e.scope)[0]
    assert index['stale'] is True and index['provider_status'] == 'NOT_CONFIGURED'
    with pytest.raises((ValueError, ModelRuntimeError)):
        service.query(e.nid, e.scope, {'index_id': row['id'], 'text': 'Synthetic'})
