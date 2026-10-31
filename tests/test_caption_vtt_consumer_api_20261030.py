"""Actual mounted caption consumer: own WebVTT download remains literal on import."""
import base64
from copy import deepcopy
import io
import wave
from types import SimpleNamespace

import pytest

from app.experimental import api as experimental_api
from app.experimental.subtitle_timeline import SubtitleTimelineService
from app.experimental.voice_direction import DirectedAudiobookService
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


@pytest.fixture
def captions(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',
        'narrative_production_v2,asset_lineage_v2,audiobook_v2,voice_direction_v2,subtitle_timeline_v2')
    creative = rig.workspace.creative
    voice = DirectedAudiobookService(creative.store, creative.novels, creative.chapters, assets=rig.assets)
    service = SubtitleTimelineService(creative.store, creative.novels, creative.chapters, voice, rig.assets)
    # Mounted router captures this instance; preserve actual route/authorization.
    for name, value in service.__dict__.items():
        monkeypatch.setattr(experimental_api.subtitle_timeline_service, name, value, raising=False)
    binary = io.BytesIO()
    with wave.open(binary, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b'\0\0' * 16000)
    asset = rig.assets.create(rig.nid, 'synthetic-caption.wav',
        base64.b64encode(binary.getvalue()).decode(), 'audio/wav', 'audio')
    return SimpleNamespace(rig=rig, service=service, asset=asset)


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_caption_own_vtt_export_import_preview_preserves_literal_and_is_read_only(captions, prefix):
    e = captions
    base = f'{prefix}/novels/{e.rig.nid}/experimental/subtitle-timeline/records'
    text = 'Literal &#65; &copy; &amp; &nbsp; &eacute;'
    row = checked(e.rig.client.post(base, json={'asset_id': e.asset['id'],
        'cues': [{'id': 'literal', 'start_tick': 0, 'end_tick': 1500, 'text': text}]}), 201)
    before = deepcopy(e.service.store.read(e.rig.nid, e.rig.scope))
    exported = e.rig.client.get(f'{base}/{row["id"]}/file.vtt', params={'expected_version': row['version']})
    assert exported.status_code == 200, exported.text
    assert exported.headers['cache-control'] == 'no-store'
    preview = checked(e.rig.client.post(f'{base}/{row["id"]}/import-preview', json={
        'expected_version': row['version'], 'format': 'vtt',
        'content_base64': base64.b64encode(exported.content).decode()}))
    assert preview['cues'][0]['text'] == text
    assert preview['expected_version'] == row['version']
    assert e.service.store.read(e.rig.nid, e.rig.scope) == before

    # External text references decode once; authored literal entities must not.
    external = 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.500\ncaf&eacute; &#65; &copy;\n'
    decoded = checked(e.rig.client.post(f'{base}/{row["id"]}/import-preview', json={
        'expected_version': row['version'], 'format': 'vtt',
        'content_base64': base64.b64encode(external.encode()).decode()}))
    assert decoded['cues'][0]['text'] == 'café A ©'
    assert e.service.store.read(e.rig.nid, e.rig.scope) == before

    for unsafe in ('<b>text</b>', '&#60;b&#62;text&#60;/b&#62;'):
        content = 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.500\n' + unsafe + '\n'
        response = e.rig.client.post(f'{base}/{row["id"]}/import-preview', json={
            'expected_version': row['version'], 'format': 'vtt',
            'content_base64': base64.b64encode(content.encode()).decode()})
        assert response.status_code == 422, response.text
        assert 'CAPTION_PLAIN_NONEMPTY_TEXT_REQUIRED' in response.text
        assert e.service.store.read(e.rig.nid, e.rig.scope) == before
