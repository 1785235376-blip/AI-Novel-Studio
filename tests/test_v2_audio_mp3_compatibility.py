"""Versioned admission and exact readback of real pre-versioned File/CPU receipts."""
from copy import deepcopy
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.audio_production_store import AudioProductionStore
from app.config import Settings
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand, MediaJobAction, MediaReview
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.audiobook_service import AudiobookError
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from app.services.studio_audio_execution import _body, _digest
from support_reconciliation_test_v2_independent_workspace import services

pytestmark = pytest.mark.file_backend_only
PROFILE = 'studio-audio-mp3/1'
FIXTURE = Path(__file__).with_name('fixtures') / 'studio_audio_mp3_legacy_v1.json.gz'


class NoControl:
    def __getattr__(self, name):
        raise AssertionError('local MP3 must not use a provider or external control: ' + name)


def restored(tmp_path, monkeypatch, stage='ready'):
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ['PROJECT_ROOT']).resolve() == root
    assert tmp_path.resolve().is_relative_to(root / '.runtime')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    captured = json.loads(gzip.decompress(FIXTURE.read_bytes()))
    assert captured['capture_exit'] == 0 and captured['source_commit'] == '72e636f87c7299a62cb3357bcb6a6e44a9388883'
    fixture = captured['stages'][stage]
    for name, entry in fixture['files'].items():
        path = tmp_path / name
        assert path.resolve().is_relative_to(tmp_path.resolve())
        data = base64.b64decode(entry['base64'])
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    bundle = create_repository_bundle(Settings(storage_backend='file', database_url='', novel_data=tmp_path,
        enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    workspace = services(tmp_path, 'file', '', novels, chapters)
    production = ProductionExecutionService(workspace, ImageJobService(tmp_path), NoControl(), VideoAssemblyService(tmp_path, workspace.assets), {}, {},
        AudioProductionStore(tmp_path / 'audio-production'), NoControl(), NoControl())
    view = fixture['view']; nid = view['novel_id']; actor = 'local-studio-author'
    return SimpleNamespace(root=tmp_path, production=production, nid=nid, actor=actor,
        scope={'mode': 'local', 'novel_id': nid}, view=view, fixture=fixture, captured=captured)


def read(e):
    return e.production.get(e.nid, e.scope, e.actor, 'audio', e.view['id'], lambda: None)


def raw(e):
    owner = e.production._audio(e.scope, e.actor)
    return owner.get(e.nid, e.view['id'], e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None)


def action(row):
    return MediaJobAction(expected_version=row['version'], expected_request_digest=row['request_digest'])


def immutable(row):
    return {key: deepcopy(row[key]) for key in ('id', '_studio_body', 'context', 'request_digest', 'request_sha256', 'source_sha256')}


@pytest.mark.parametrize('stage', ['queued', 'ready', 'approved'])
def test_real_unmarked_rows_read_without_migration_replay_or_native_execution(tmp_path, monkeypatch, stage):
    e = restored(tmp_path, monkeypatch, stage)
    import app.services.studio_timeline_export as native
    from app.services.studio_audio_execution import StudioAudioExecution
    def prohibited(*args, **kwargs):
        pytest.fail('reading a saved MP3 must not create, replay, reconcile, encode, or decode')
    monkeypatch.setattr(native, 'run_guarded_process', prohibited)
    for method in ('queue', 'execute', 'reconcile'):
        monkeypatch.setattr(StudioAudioExecution, method, prohibited)
    assert read(e) == e.view
    assert e.production.list(e.nid, e.scope, e.actor, lambda: None)['items'] == [e.view]
    stored = raw(e)
    assert stored['request_sha256'] == _digest({'body': stored['_studio_body'], 'context': stored['context']})
    for value in (stored['_studio_body'], stored['context']['command'], stored['context']['execution_recipe']):
        assert 'audio_profile' not in value
    if stage != 'queued':
        meta, data = e.production.candidate(e.nid, e.scope, e.actor, 'audio', e.view['id'], lambda: None)
        assert meta['media_type'] == 'audio/mpeg'
        assert hashlib.sha256(data).hexdigest() == e.view['output_candidate']['digest']
        assert len(data) == e.view['media_measurement']['byte_count']
    for name, entry in e.fixture['files'].items():
        assert hashlib.sha256((e.root / name).read_bytes()).hexdigest() == entry['sha256'], name


def test_original_explicit_execution_keeps_legacy_request_and_real_output(tmp_path, monkeypatch):
    e = restored(tmp_path, monkeypatch, 'queued'); before = immutable(raw(e))
    result = e.production.execute(e.nid, e.scope, e.actor, 'audio', e.view['id'], action(e.view), lambda: None)
    assert result['status'] == 'AWAITING_REVIEW'
    assert immutable(raw(e)) == before
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'audio', e.view['id'], lambda: None)
    assert hashlib.sha256(data).hexdigest() == e.captured['stages']['ready']['view']['output_candidate']['digest']
    assert len(e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']) == 1


def test_original_explicit_review_preserves_unmarked_output_and_hashes(tmp_path, monkeypatch):
    e = restored(tmp_path, monkeypatch); before = immutable(raw(e))
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('review must not encode'))
    review = MediaReview(**action(e.view).model_dump(), reviewed_output_digest=e.view['output_candidate']['digest'])
    approved = e.production.review(e.nid, e.scope, e.actor, 'audio', e.view['id'], review, lambda: None)
    assert approved['status'] == 'APPROVED' and approved['media_measurement'] == e.view['media_measurement']
    assert approved['output_candidate'] == e.view['output_candidate']
    assert immutable(raw(e)) == before and read(e) == approved


def test_original_explicit_reconcile_recovers_legacy_publication_without_encoding(tmp_path, monkeypatch):
    e = restored(tmp_path, monkeypatch, 'queued'); before = immutable(raw(e)); callbacks = e.production._callbacks
    def interrupted(*args, **kwargs):
        publish, promote = callbacks(*args, **kwargs)
        def lost(*args, **kwargs):
            publish(*args, **kwargs)
            raise OSError('synthetic loss after the original durable private publication')
        return lost, promote
    monkeypatch.setattr(e.production, '_callbacks', interrupted)
    uncertain = e.production.execute(e.nid, e.scope, e.actor, 'audio', e.view['id'], action(e.view), lambda: None)
    assert uncertain['status'] == 'UNKNOWN' and uncertain['media_measurement']
    monkeypatch.setattr(e.production, '_callbacks', callbacks)
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('reconcile must not replay'))
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, 'audio', e.view['id'], action(uncertain), lambda: None)
    assert recovered['status'] == 'AWAITING_REVIEW'
    assert recovered['media_measurement'] == uncertain['media_measurement']
    assert immutable(raw(e)) == before
    assert len(e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']) == 1


@pytest.mark.parametrize('marker', ['ABSENT', None, '', False, 1, 'studio-audio-mp3/2'])
def test_fresh_unmarked_and_invalid_markers_fail_model_preview_create_and_owner_queue(tmp_path, monkeypatch, marker):
    e = restored(tmp_path, monkeypatch, 'queued'); stored = raw(e); value = deepcopy(e.view['command'])
    if marker != 'ABSENT': value['audio_profile'] = marker
    with pytest.raises(ValueError): MediaCommand.model_validate(value)
    with pytest.raises(ValueError): e.production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    with pytest.raises(ValueError): e.production.create(e.nid, e.scope, e.actor,
        {'command': value, 'reviewed_preview_digest': 'a' * 64}, lambda: None)
    body = {key: item for key, item in value.items() if key not in {'request_id', 'allow_cloud', 'license_note'}}
    with pytest.raises(AudiobookError): _body(body)
    with pytest.raises(AudiobookError): e.production._audio(e.scope, e.actor).queue(e.nid, body,
        stored['context'], lambda: None, lambda source: pytest.fail('invalid admission must precede source read'))
    assert read(e) == e.view


def test_marked_request_binds_every_digest_and_cannot_upgrade_same_old_request_id(tmp_path, monkeypatch):
    e = restored(tmp_path, monkeypatch, 'queued'); value = {**e.view['command'], 'audio_profile': PROFILE}
    preview, context, command = e.production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    assert command.model_dump()['audio_profile'] == preview['command']['audio_profile'] == PROFILE
    assert preview['execution_recipe']['audio_profile'] == PROFILE
    assert preview['request_digest'] != e.view['request_digest']
    assert preview['execution_recipe']['recipe_digest'] != e.view['execution_recipe']['recipe_digest']
    with pytest.raises(AudiobookError, match='原请求标识'):
        e.production.create(e.nid, e.scope, e.actor,
            {'command': value, 'reviewed_preview_digest': preview['preview_digest']}, lambda: None)
    value['request_id'] = 'marked-new-request'
    preview = e.production.preview(e.nid, e.scope, e.actor, value, lambda: None)[0]
    queued = e.production.create(e.nid, e.scope, e.actor,
        {'command': value, 'reviewed_preview_digest': preview['preview_digest']}, lambda: None)
    stored = e.production._audio(e.scope, e.actor).get(e.nid, queued['id'], context, lambda: None)
    assert all(v['audio_profile'] == PROFILE for v in (stored['_studio_body'], stored['context']['command'], stored['context']['execution_recipe']))
    assert stored['request_sha256'] == _digest({'body': stored['_studio_body'], 'context': stored['context']})
    assert stored['request_sha256'] != raw(e)['request_sha256']
    assert _digest(stored['_studio_body']) != _digest(raw(e)['_studio_body'])
    assert _digest(stored['context']['command']) != _digest(raw(e)['context']['command'])
    assert read(e) == e.view and queued['id'] != e.view['id']


@pytest.mark.parametrize('field', ['_studio_body', 'command', 'execution_recipe', 'request_sha256', 'receipt_digest', 'measured'])
def test_tampered_legacy_rows_fail_existing_integrity_checks(tmp_path, monkeypatch, field):
    e = restored(tmp_path, monkeypatch); owner = e.production._audio(e.scope, e.actor)
    state = owner.store.load(e.nid, include_studio=True); row = state['jobs'][0]
    if field == '_studio_body': row[field]['audio_profile'] = PROFILE
    elif field in {'command', 'execution_recipe'}: row['context'][field]['audio_profile'] = PROFILE
    elif field == 'measured': row[field]['output_sha256'] = 'a' * 64
    else: row[field] = 'a' * 64
    owner.store.save(e.nid, state, include_studio=True)
    with pytest.raises(AudiobookError): read(e)


def test_legacy_wav_flac_serialization_has_no_new_key_and_original_digests():
    fixture = json.loads(gzip.decompress(FIXTURE.read_bytes()))
    raw_file = next(v for k, v in fixture['stages']['queued']['files'].items() if k.startswith('audio-production/') and k.endswith('.json'))
    legacy = json.loads(base64.b64decode(raw_file['base64']))['jobs'][0]['context']['command']
    service = object.__new__(ProductionExecutionService)
    for output in (None, 'FLAC'):
        expected = deepcopy(legacy)
        if output is None: expected['parameters'].pop('output_format')
        else: expected['parameters']['output_format'] = output
        model = MediaCommand.model_validate(expected)
        assert model.model_dump() == expected
        assert model.model_dump_json() == json.dumps(expected, ensure_ascii=False, separators=(',', ':'))
        parameters = {k: v for k, v in expected['parameters'].items() if v is not None}
        recipe = {'contract': 'studio-execution-recipe/1', 'operation_id': 'm8.audio.trim', 'adapter': 'LOCAL_FFMPEG',
            'parameters': parameters, 'automatic_fallback': False,
            'output_profile': 'PCM_S16LE_WAV_22050_MONO' if output is None else 'FLAC_S16_22050_MONO_COMPRESSION5'}
        recipe['recipe_digest'] = digest(recipe)
        assert service._recipe(model) == recipe
        assert 'audio_profile' not in model.model_dump() and 'audio_profile' not in recipe


@pytest.mark.parametrize('target', ['body', 'command', 'recipe'])
def test_rehashed_cross_layer_marker_mismatch_cannot_queue(tmp_path, monkeypatch, target):
    e = restored(tmp_path, monkeypatch, 'queued')
    value = {**e.view['command'], 'request_id': 'forged-marker', 'audio_profile': PROFILE}
    _, context, command = e.production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    context['command'] = command.model_dump()
    body = command.model_dump(exclude={'request_id', 'allow_cloud', 'license_note'})
    body['parameters'] = command.parameters.model_dump(exclude_none=True)
    body['source_snapshots'] = deepcopy(context['sources'])
    target_value = body if target == 'body' else context['command'] if target == 'command' else context['execution_recipe']
    target_value.pop('audio_profile')
    context['execution_recipe']['recipe_digest'] = digest({k: v for k, v in context['execution_recipe'].items() if k != 'recipe_digest'})
    context['request_digest'] = digest({'context': {k: v for k, v in context.items() if k not in {'request_digest', 'command'}}, 'command': context['command']})
    with pytest.raises(AudiobookError):
        e.production._audio(e.scope, e.actor).queue(e.nid, body, context, lambda: None,
            lambda source: pytest.fail('forged marker must fail before source reads'))
    assert read(e) == e.view


@pytest.mark.parametrize('output', [None, 'FLAC', 'WAV'])
def test_versioned_mp3_profile_cannot_widen_other_legacy_formats(output):
    captured = json.loads(gzip.decompress(FIXTURE.read_bytes()))['stages']['queued']['view']['command']
    value = {**captured, 'parameters': {**captured['parameters']}, 'audio_profile': PROFILE}
    if output is None: value['parameters'].pop('output_format')
    else: value['parameters']['output_format'] = output
    with pytest.raises(ValueError): MediaCommand.model_validate(value)
    with pytest.raises(AudiobookError): _body({k: v for k, v in value.items() if k not in {'request_id', 'allow_cloud', 'license_note'}})
