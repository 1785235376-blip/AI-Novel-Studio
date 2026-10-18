"""Unmounted contract/real decoder checks, never real model execution proof."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from test_v2_independent_workspace import rig, import_asset, stored_asset
from app.creative.director_image_source import DirectorImageSources, decode_image, MAX_IMAGE_BYTES
from app.creative.director_image_preview import preview_image
from app.director_vision_wire import OllamaDirectorVisionCodec as Codec
from app.model_runtime import ProviderRegistry, ModelRegistry, ProviderDescriptor, ModelDescriptor, Modality
from app.stable_identity import StableIdentityStore


class NoCalls:
    def __getattr__(self, name):
        raise AssertionError('No provider methods may be called: ' + name)


@pytest.fixture
def registry(tmp_path):
    identities = StableIdentityStore(tmp_path / 'image-identities.json')
    identities.get_or_create('execution_node', 'local')
    providers, models = ProviderRegistry(identities), ModelRegistry(identities)
    providers.register(ProviderDescriptor('vision-local', 'Fixture only', 'local',
        frozenset({Modality.VISION}), True, True), NoCalls())
    models.register(ModelDescriptor('vision-test', 'vision-local', 'Fixture only',
        Modality.VISION, frozenset({'IMAGE_UNDERSTANDING'})))
    return SimpleNamespace(providers=providers, models=models)


def selection(asset):
    return {'asset_id': asset['id'], 'version': asset['version'], 'sha256': asset['sha256']}


def preview(rig, registry, **changes):
    asset = import_asset(rig)
    value = dict(asset=selection(asset), provider_id='vision-local', model_id='vision-test')
    value.update(changes)
    return asset, preview_image(rig.service, registry, rig.nid, rig.scope, rig.actor, value, guard=lambda: None)


def test_source_and_preview_use_original_asset_without_persistence_or_calls(rig, registry):
    asset = import_asset(rig)
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    meta = stored_asset(rig, asset['id'])
    result = preview_image(rig.service, registry, rig.nid, rig.scope, rig.actor,
        dict(asset=selection(asset), provider_id='vision-local', model_id='vision-test'), guard=lambda: None)
    assert result['source']['asset'] == selection(asset)
    assert result['source']['width'] == result['source']['height'] == 2
    assert result['source']['source_kind'] == 'IMAGE'
    assert result['model_called'] is False
    assert result['execution_available'] is result['adoption_available'] is False
    assert result['registry_observation']['admission'] == 'UNKNOWN'
    assert result['registry_observation']['capability_status'] == 'DECLARED_ONLY'
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    assert stored_asset(rig, asset['id']) == meta
    encoded = json.dumps(result)
    assert 'content_base64' not in encoded and 'data:image' not in encoded
    assert 'http://' not in encoded


def test_exact_pin_reopen_and_stale_version_digest_actor_scope(rig):
    asset = import_asset(rig)
    sources = DirectorImageSources(rig.service)
    pin = sources.capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)
    with sources.read(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None, expected=pin) as (again, content):
        assert again.model_dump() == pin and sha256(content).hexdigest() == asset['sha256']
    for field, changed in [('version', 2), ('sha256', 'a' * 64)]:
        with pytest.raises(ValueError):
            sources.capture(rig.nid, rig.scope, rig.actor, {**selection(asset), field: changed}, guard=lambda: None)
    with pytest.raises(ValueError, match='AUTHORITY_MISMATCH'):
        with sources.read(rig.nid, rig.scope, 'other', selection(asset), guard=lambda: None, expected=pin):
            pytest.fail('cross actor')
    with pytest.raises(ValueError, match='AUTHORITY_MISMATCH'):
        sources.capture(rig.nid, {'mode': 'local', 'novel_id': 'other'}, rig.actor, selection(asset), guard=lambda: None)


def test_missing_owner_never_provisions_marker(rig):
    asset = import_asset(rig)
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    if rig.backend == 'file':
        marker.unlink()
    else:
        # PostgreSQL's original owner identity is the novels UUID, not a File marker.
        with rig.raw_store._connect() as connection:
            owner = connection.execute(
                'DELETE FROM novels WHERE slug = %s RETURNING id', (rig.nid,)).fetchone()
            assert owner is not None
        assert not marker.exists()
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(FileNotFoundError):
        DirectorImageSources(rig.service).capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)
    assert not marker.exists()
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    if rig.backend == 'postgres':
        with rig.raw_store._connect() as connection:
            assert connection.execute(
                'SELECT id FROM novels WHERE slug = %s OR id = %s',
                (rig.nid, owner[0])).fetchone() is None


def test_permissions_and_flags_fail_before_content(rig, monkeypatch):
    asset = import_asset(rig)
    def denied(): raise PermissionError('revoked')
    monkeypatch.setattr(rig.assets, 'content', lambda *_a, **_k: pytest.fail('content read'))
    with pytest.raises(PermissionError):
        DirectorImageSources(rig.service).capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=denied)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        DirectorImageSources(rig.service).capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)


@pytest.mark.parametrize('capabilities', [{'OCR'}, {'TEXT_GENERATION'}, {'IMAGE_GENERATION'}, set()])
def test_nonvision_capability_cannot_masquerade_as_visual_analysis(rig, registry, capabilities):
    model = registry.models.descriptors()[0]
    registry.models.register(replace(model, capabilities=frozenset(capabilities)), replace=True)
    with pytest.raises(ValueError, match='UNSUPPORTED'):
        preview(rig, registry)


def test_remote_and_changed_registry_fail_closed(rig, registry):
    descriptor = registry.providers.descriptors()[0]
    registry.providers.register(replace(descriptor, provider_type='cloud'), NoCalls(), replace=True)
    with pytest.raises(ValueError, match='UNSUPPORTED'):
        preview(rig, registry)


def test_provider_replacement_during_source_decode_invalidates_preview(rig, registry):
    asset = import_asset(rig)
    original = registry.providers.resolve('vision-local')
    calls = 0
    def guard():
        nonlocal calls
        calls += 1
        if calls == 7:
            registry.providers.register(registry.providers.descriptors()[0], NoCalls(), replace=True)
    with pytest.raises(ValueError, match='REGISTRY_CHANGED'):
        preview_image(rig.service, registry, rig.nid, rig.scope, rig.actor,
            dict(asset=selection(asset), provider_id='vision-local', model_id='vision-test'), guard=guard)
    assert registry.providers.resolve('vision-local') is not original


def image_bytes(fmt='PNG', size=(2, 2), **kwargs):
    stream = BytesIO()
    Image.new('RGB', size, 'red').save(stream, format=fmt, **kwargs)
    return stream.getvalue()


@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg')])
def test_real_decoders_and_exact_transient_wire(rig, fmt, mime):
    raw = image_bytes(fmt)
    asset = import_asset(rig, data=raw, filename='example.' + fmt.lower())
    sources = DirectorImageSources(rig.service)
    with sources.read(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None) as (source, content):
        assert decode_image(content, mime, guard=lambda: None) == (2, 2)
        wire = Codec.encode(model_id='vision-test', source=source, content=content,
            prompt='Give uncertain visual observations.', parameters={}, guard=lambda: None)
        import base64
        assert base64.b64decode(wire['messages'][0]['images'][0]) == raw
        assert wire['stream'] is False and wire['format'] == 'json'
        assert wire['options'] == {'temperature': 0.0, 'num_predict': 512}
        assert Codec.execution_available is False
        with pytest.raises(ValueError):
            Codec.encode(model_id='vision-test', source=source, content=image_bytes('PNG', (3, 3)),
                prompt='Observe', parameters={}, guard=lambda: None)


@pytest.mark.parametrize('raw,mime', [(b'fake', 'image/png'), (b'x' * (MAX_IMAGE_BYTES + 1), 'image/png'),
    (image_bytes(), 'image/jpeg'), (image_bytes()[:40], 'image/png'),
    (image_bytes(size=(4097, 1)), 'image/png'), (image_bytes(size=(2049, 2048)), 'image/png')])
def test_invalid_bounded_media_has_no_header_only_success(raw, mime):
    with pytest.raises(ValueError): decode_image(raw, mime, guard=lambda: None)


def test_orientation_and_animation_rejected():
    exif = Image.Exif(); exif[274] = 6
    with pytest.raises(ValueError): decode_image(image_bytes('JPEG', exif=exif), 'image/jpeg', guard=lambda: None)
    out = BytesIO()
    Image.new('RGB', (2, 2), 'red').save(out, format='PNG', save_all=True,
        append_images=[Image.new('RGB', (2, 2), 'blue')])
    with pytest.raises(ValueError): decode_image(out.getvalue(), 'image/png', guard=lambda: None)


def response(**changes):
    value = {'model': 'vision-test', 'done': True, 'done_reason': 'stop',
        'message': {'role': 'assistant', 'content': '{"observations": []}'}}
    value.update(changes)
    return json.dumps(value).encode()


def test_wire_decoder_does_not_claim_model_call_or_understanding():
    assert Codec.decode(response(), model_id='vision-test') == '{"observations": []}'


@pytest.mark.parametrize('raw', [response(model='other'), response(done=False), response(done_reason='length'),
    response(error='bad'), response(message={'role': 'assistant', 'content': 'text', 'tool_calls': [{}]}),
    b'{"done":true,"done":false}', b'NaN', b'x'*128001])
def test_wire_response_mismatch_malformed_truncation_and_tools_rejected(raw):
    with pytest.raises(ValueError): Codec.decode(raw, model_id='vision-test')


def test_private_asset_never_read_even_by_owning_actor(rig, monkeypatch):
    asset = import_asset(rig)
    path = rig.assets._meta_path(asset['id'])
    row = stored_asset(rig, asset['id']); row['_owner_actor_id'] = rig.actor
    path.write_text(json.dumps(row))
    monkeypatch.setattr(rig.assets, '_verified_bounded_content', lambda *_a, **_k: pytest.fail('private bytes read'))
    with pytest.raises(FileNotFoundError):
        DirectorImageSources(rig.service).capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)


def test_incarnation_change_and_source_deletion_invalidate_pin(rig):
    from uuid import uuid4
    asset = import_asset(rig)
    sources = DirectorImageSources(rig.service)
    pin = sources.capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)
    changed = dict(pin, project_incarnation='file:' + str(uuid4()))
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        with sources.read(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None, expected=changed):
            pytest.fail('wrong incarnation')
    path = rig.assets._meta_path(asset['id'])
    row = stored_asset(rig, asset['id']); row['deleted_at'] = '2026-10-18T00:00:00+00:00'
    path.write_text(json.dumps(row))
    with pytest.raises(FileNotFoundError):
        sources.capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)


def test_source_bytes_mutation_during_consumer_rejected(rig):
    asset = import_asset(rig)
    with pytest.raises(ValueError):
        with DirectorImageSources(rig.service).read(rig.nid, rig.scope, rig.actor,
                selection(asset), guard=lambda: None):
            rig.assets._bin_path(asset['id']).write_bytes(b'changed')


def test_existing_raw_transaction_rejected_without_inverted_asset_lock(rig, monkeypatch):
    asset = import_asset(rig)
    monkeypatch.setattr(rig.service, '_asset_scope', lambda *_: pytest.fail('inverted lock'))
    with rig.raw_store.transaction(rig.nid, rig.scope):
        with pytest.raises(ValueError, match='PHASE_ORDER_INVALID'):
            DirectorImageSources(rig.service).capture(rig.nid, rig.scope, rig.actor, selection(asset), guard=lambda: None)


def test_unknown_extra_fields_cannot_inject_execution_authority(rig, registry):
    with pytest.raises(ValueError): preview(rig, registry, execute=True)


def test_decoder_unsafe_truncation_mode_fails_closed(monkeypatch):
    from PIL import ImageFile
    monkeypatch.setattr(ImageFile, 'LOAD_TRUNCATED_IMAGES', True)
    with pytest.raises(ValueError, match='POLICY_UNSAFE'):
        decode_image(image_bytes(), 'image/png', guard=lambda: None)


def test_v3_source_cannot_reuse_text_director_binding_or_terminal_contract(rig):
    from app.creative.director_binding import _passive_source_binding
    from app.creative.director_transport_contract import PreviewReceipt, ScreenplayPreviewReceipt
    asset = import_asset(rig)
    pin = DirectorImageSources(rig.service).capture(rig.nid, rig.scope, rig.actor,
        selection(asset), guard=lambda: None)
    with pytest.raises(ValueError): _passive_source_binding(pin)
    assert PreviewReceipt.model_fields['source_mode'].default == 'STORYBOARD'
    assert ScreenplayPreviewReceipt.model_fields['source_mode'].default == 'SCREENPLAY'


def test_unregistered_identity_fails_without_source_bytes(rig, registry, monkeypatch):
    registry.models.identity_store = None
    monkeypatch.setattr(rig.service, 'pinned_content', lambda *_a, **_k: pytest.fail('bytes read'))
    with pytest.raises(ValueError, match='REGISTERED_IDENTITY_REQUIRED'):
        preview(rig, registry)
