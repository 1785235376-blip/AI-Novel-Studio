"""Original local image call boundary; injected transport only, no model call."""
from types import SimpleNamespace
import pytest
from app.asset_providers import AssetGenerationRequest, AssetGenerationResult
from app.model_center.discovery_bridge import LocalImageAdapter


def test_local_image_authority_runs_after_metadata_before_original_delegate():
    events = []
    candidate = {'id': 'image', 'provider_id': 'local-image', 'model_name': 'fixture',
                 'runtime_type': 'AUTOMATIC1111', 'runtime_config': {'endpoint': 'http://127.0.0.1:7860'}, 'enabled_at': 'one'}
    bridge = SimpleNamespace(guard=lambda _: candidate, service=SimpleNamespace(check_model_dispatch=lambda _: events.append('metadata')))
    adapter = LocalImageAdapter(bridge, candidate)
    def generate(request):
        events.append('generate')
        assert request.model_id == 'fixture'
        return AssetGenerationResult(request.provider_id, request.model_id, 'fixture')
    adapter.delegate = SimpleNamespace(generate=generate)
    def guard(): events.append('authority')
    result = adapter.generate(AssetGenerationRequest('local-image', 'image', 'fixture', 'job', dispatch_guard=guard))
    assert result.model_id == 'image' and events == ['metadata', 'authority', 'generate']


def test_local_image_changed_authority_during_metadata_never_generates():
    candidate = {'id': 'image', 'provider_id': 'local-image', 'model_name': 'fixture',
                 'runtime_type': 'AUTOMATIC1111', 'runtime_config': {'endpoint': 'http://127.0.0.1:7860'}, 'enabled_at': 'one'}
    calls = []
    bridge = SimpleNamespace(guard=lambda _: candidate, service=SimpleNamespace(check_model_dispatch=lambda _: calls.append('metadata')))
    adapter = LocalImageAdapter(bridge, candidate)
    adapter.delegate = SimpleNamespace(generate=lambda _: calls.append('INFERENCE'))
    def guard(): raise ValueError('current source changed')
    with pytest.raises(ValueError, match='current source changed'):
        adapter.generate(AssetGenerationRequest('local-image', 'image', 'fixture', 'job', dispatch_guard=guard))
    assert calls == ['metadata']
