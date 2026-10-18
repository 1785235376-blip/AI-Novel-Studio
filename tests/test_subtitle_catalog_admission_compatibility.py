"""Schema-1 catalog compatibility using original registries and File/PG owners.

Routes are synthetic contract fixtures. No ASR model, network or service runs.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from app.audio_processing_runtime import AudioProcessingModelNode
from app.experimental.subtitle_asr import ModelRuntimeSubtitleAdapter
from app.model_runtime import (ModelDescriptor, ModelRegistry, Modality,
    ProviderDescriptor, ProviderRegistry)
from app.stable_identity import StableIdentityStore
from post_interop_media_fixture_support import rig
from test_surface_freeze_media_engine_adapters import action, env, queue

REQUIREMENT = 'ORIGINAL_AUDIO_MODEL_NODE_EXPLICIT_REGISTERED_LOCAL_ROUTE_REQUIRED'
UNCONFIGURED = 'NOT_CONFIGURED_ORIGINAL_MEDIA_RUNTIME_REQUIRED'


class RegisteredAudioFixture:
    supports_dispatch_guard = True

    def __init__(self):
        self.route = {'schema': 'local-audio-admission/1', 'provider_id': 'test.audio',
            'model_id': 'test.asr', 'endpoint': 'http://127.0.0.1:8999',
            'model_sha256': 'a' * 64, 'admission_digest': 'b' * 64,
            'operations': ['ASR'], 'adapter_version': 'synthetic-contract/1'}

    def route_snapshot(self):
        return deepcopy(self.route)

    def process_audio(self, request):
        raise AssertionError('Catalog and queue checks must not invoke a provider')


@pytest.fixture
def registered(env, tmp_path):
    identities = StableIdentityStore(tmp_path / 'audio-identities.json')
    identities.get_or_create('execution_node', 'local')
    providers, models = ProviderRegistry(identities), ModelRegistry(identities)
    provider = RegisteredAudioFixture()
    providers.register(ProviderDescriptor('test.audio', 'Synthetic audio', 'local',
        frozenset({Modality.AUDIO}), True, True), provider)
    models.register(ModelDescriptor('test.asr', 'test.audio', 'Synthetic ASR',
        Modality.AUDIO, frozenset({'TRANSCRIBE'})))
    adapter = ModelRuntimeSubtitleAdapter(AudioProcessingModelNode(providers, models),
        provider_id='test.audio', model_id='test.asr')
    env.service._initialize_processing((adapter,))
    env.adapter = adapter
    return env, provider, providers, models


def assert_catalog(service, admitted, status):
    catalog = service.processing_catalog()
    assert catalog['schema'] == 'ai-novel-subtitle-processing/1'
    assert catalog['model_runtime_admission'] == (REQUIREMENT if admitted else UNCONFIGURED)
    assert catalog['model_runtime_admission_state'] == (
        'EXPLICIT_REGISTERED_LOCAL_ROUTE' if admitted else 'NOT_CONFIGURED')
    assert catalog['model_runtime_admission_requirement'] == REQUIREMENT
    operation = next(row for row in catalog['operations'] if row['operation'] == 'ASR')
    assert operation == {'operation': 'ASR', 'status': status, 'runtime_verification': 'NOT_RUN'}


def test_original_registered_route_has_positive_catalog_and_queue(registered):
    e, _, _, _ = registered
    assert e.adapter.model_runtime_admitted()
    assert_catalog(e.service, True, 'CONTRACT_VERIFIED')
    assert queue(e)['status'] == 'QUEUED'


@pytest.mark.parametrize('revoke', ['admission', 'provider', 'model', 'identity'])
def test_original_route_revocation_restores_legacy_unconfigured_and_gates(registered, revoke):
    e, provider, providers, models = registered
    assert_catalog(e.service, True, 'CONTRACT_VERIFIED')
    if revoke == 'admission':
        provider.route['admission_digest'] = 'c' * 64
    elif revoke == 'provider':
        providers.register(replace(providers.descriptors()[0], available=False), provider, replace=True)
    elif revoke == 'model':
        models.register(replace(models.descriptors()[0], enabled=False), replace=True)
    else:
        models.identity_store = None
    assert not e.adapter.model_runtime_admitted()
    assert_catalog(e.service, False, 'NOT_CONFIGURED')
    task = queue(e)
    assert task['status'] == 'NOT_CONFIGURED'
    with pytest.raises(ValueError):
        action(e, task, 'execute')
    with pytest.raises(ValueError, match='NOT_CONFIGURED'):
        action(e, task, 'resume')


@pytest.mark.parametrize('fixture_kind', ['absent', 'mock', 'unadmitted'])
def test_missing_or_synthetic_routes_keep_legacy_unconfigured(env, fixture_kind):
    if fixture_kind == 'absent':
        env.service._initialize_processing(())
    elif fixture_kind == 'unadmitted':
        env.adapter.definition = replace(env.adapter.definition, verification='CONTRACT_VERIFIED')
    assert_catalog(env.service, False, 'MOCK_ONLY' if fixture_kind == 'mock' else 'NOT_CONFIGURED')
    assert env.adapter.calls == []
