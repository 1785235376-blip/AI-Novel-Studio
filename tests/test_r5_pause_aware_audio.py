"""B03 real local PCM assembly; synthetic samples, never voice-quality evidence."""
import base64
import io
import wave

import pytest
from app.experimental.audiobook import LocalPcmMixer, MixerRequest
from app.experimental.common import StaleSourceError
from app.media_files import concatenate_wav, MediaValidationError
from app.services.audiobook_service import AudiobookError
from test_r3_media_support import rig, wav_bytes, audio_asset
from test_r5_voice_subtitles import setup, directed, edit, api_client


def measured_plan(rig, setup, *, rate=8000, duration=100):
    v = setup.voice
    v.mixer = LocalPcmMixer()
    p = setup.plan
    originals = []
    for i, segment in enumerate(p['segments']):
        p = v.edit_direction(rig.nid, rig.scope, rig.actor, p['id'], segment['id'], edit(p, segment, setup.profile, pause_ms=125 + i * 100))
        content = wav_bytes(duration, sample_rate=rate, sample=(i + 1) * 100)
        asset = rig.assets.create(rig.nid, f'part-{i}.wav', base64.b64encode(content).decode(), 'audio/wav', 'audio')
        originals.append(asset['id'])
        p = v.as_actor(rig.actor, v.bind_audio, rig.nid, rig.scope, rig.actor, p['id'], segment['id'], {'expected_version':p['version'], 'asset_id':asset['id']})
    return p, originals


def approve(rig, v, p):
    return v.as_actor(rig.actor, v.review, rig.nid, rig.scope, rig.actor, p['id'], 'approve', p['version'])


def pcm(content):
    with wave.open(io.BytesIO(content), 'rb') as audio:
        return audio.getframerate(), audio.getnframes(), audio.readframes(audio.getnframes())


def test_directed_frame_offsets_pauses_reorder_tracks_and_original_bytes(rig, setup):
    v = setup.voice
    before = rig.chapters.get(rig.chapter['id'])
    p, ids = measured_plan(rig, setup, rate=11025, duration=101)
    p = v.reorder(rig.nid, rig.scope, rig.actor, p['id'], {'expected_version':p['version'], 'segment_ids':[s['id'] for s in reversed(p['segments'])]})
    p = approve(rig, v, p)
    mix = v.as_actor(rig.actor, v.mix, rig.nid, rig.scope, rig.actor, p['id'], p['version'])
    output, mime = v.as_actor(rig.actor, v.mix_audio, rig.nid, rig.scope, rig.actor, mix['id'], mix['version'])
    expected, _ = concatenate_wav([rig.assets.content(aid) for aid in reversed(ids)], pauses_ms=[s['direction']['pause_ms'] for s in p['segments'][:-1]])
    assert output == expected and mime == 'audio/wav'
    assert mix['voice_direction'] and mix['status'] == 'PENDING_REVIEW'
    assert mix['timeline'][-1]['pause_after_ms'] == 0
    assert pcm(output)[1] == round(p['duration_ms'] * 11025 / 1000)
    again = v.as_actor(rig.actor, v.mix, rig.nid, rig.scope, rig.actor, p['id'], p['version'])
    assert again['content_sha256'] == mix['content_sha256']
    assert len(rig.assets.list(rig.nid)) == len(ids)
    assert rig.chapters.get(rig.chapter['id']) == before
    p = v.as_actor(rig.actor, v.review, rig.nid, rig.scope, rig.actor, p['id'], 'reopen', p['version'])
    track = rig.assets.create(rig.nid, 'track.wav', base64.b64encode(wav_bytes(50, 11025, 50)).decode(), 'audio/wav', 'audio')
    p = v.as_actor(rig.actor, v.add_track, rig.nid, rig.scope, rig.actor, p['id'], {'expected_version':p['version'], 'kind':'AMBIENCE', 'label':'Synthetic tone', 'asset_id':track['id'], 'start_ms':0, 'gain_db':0})
    p = approve(rig, v, p)
    mixed = v.as_actor(rig.actor, v.mix, rig.nid, rig.scope, rig.actor, p['id'], p['version'])
    output, _ = v.as_actor(rig.actor, v.mix_audio, rig.nid, rig.scope, rig.actor, mixed['id'], mixed['version'])
    assert int.from_bytes(pcm(output)[2][:2], 'little', signed=True) == len(ids) * 100 + 50
    with pytest.raises(StaleSourceError):
        v.as_actor(rig.actor, v.mix_audio, rig.nid, rig.scope, rig.actor, mix['id'], mix['version'])


def test_partial_pauses_do_not_create_guessed_later_starts(rig, setup):
    v = setup.voice; p = directed(rig, setup)
    asset = audio_asset(rig)
    p = v.as_actor(rig.actor, v.bind_audio, rig.nid, rig.scope, rig.actor, p['id'], p['segments'][1]['id'], {'expected_version':p['version'], 'asset_id':asset['id']})
    assert p['timing_status'] == 'PARTIAL' and p['duration_ms'] is None
    assert all(s['start_ms'] is None for s in p['segments'][1:])


def test_directed_mix_api_current_actor_version_origin_approval_and_flags(rig, setup, monkeypatch):
    p, _ = measured_plan(rig, setup); p = approve(rig, setup.voice, p)
    client, authority, _ = api_client(rig, setup)
    base = f'/novels/{rig.nid}/experimental'
    mix = client.post(f'{base}/voice-direction/plans/{p["id"]}/mix', json={'expected_version':p['version']}).json()
    assert mix['status'] == 'PENDING_REVIEW'
    url = f'{base}/voice-direction/mixes/{mix["id"]}/audio?expected_version={mix["version"]}'
    result = client.get(url)
    assert result.status_code == 200 and result.content.startswith(b'RIFF') and result.headers['cache-control'] == 'no-store'
    assert client.get(url.replace('expected_version=1','expected_version=999')).status_code == 409
    authority['actor'] = 'other'
    assert client.get(url).status_code == 404
    assert client.get(f'{base}/audiobook/mixes').json()['items'] == []
    authority['actor'] = rig.actor
    accepted = client.post(f'{base}/audiobook/mixes/{mix["id"]}/approve', json={'expected_version':mix['version']})
    assert accepted.status_code == 200, accepted.text
    asset_id = accepted.json()['asset_id']
    assert rig.assets.content(asset_id) == result.content
    assert rig.assets.get(asset_id)['parameters']['experimental_audio_lineage']['timeline'] == mix['timeline']
    for name, value in [('EXPERIMENTAL_FEATURES','audiobook_v2'), ('V1_ACCEPTANCE_MODE','true')]:
        monkeypatch.setenv(name,value)
        assert client.get(url).status_code == 404
        with pytest.raises(FileNotFoundError): rig.assets.content(asset_id)


def test_current_source_change_during_mix_does_not_publish_candidate(rig, setup):
    p, _ = measured_plan(rig, setup); p = approve(rig, setup.voice, p)
    class Changed(LocalPcmMixer):
        def mix(self, request):
            result = super().mix(request)
            rig.chapters.save(rig.chapter['id'], {'version':rig.chapter['version'], 'content':'Changed'})
            return result
    setup.voice.mixer = Changed()
    with pytest.raises(StaleSourceError):
        setup.voice.as_actor(rig.actor, setup.voice.mix, rig.nid, rig.scope, rig.actor, p['id'], p['version'])
    assert setup.voice.as_actor(rig.actor, setup.voice.list, rig.nid, rig.scope, setup.voice.MIXES) == []


def test_pcm_concatenation_vectors_scalar_compatibility_and_rejection():
    parts = [wav_bytes(100, sample=100), wav_bytes(100, sample=200), wav_bytes(100, sample=300)]
    assert concatenate_wav(parts, 200) == concatenate_wav(parts, pauses_ms=[200,200])
    output, manifest = concatenate_wav(parts, pauses_ms=[125,350])
    assert [row['start_ms'] for row in manifest] == [0,225,675]
    assert pcm(output)[1] == 6200
    for pauses in ([], [100], [1,2,3], [-1,0], [3001,0], [True,0], [1.5,0]):
        with pytest.raises(MediaValidationError): concatenate_wav(parts, pauses_ms=pauses)
    with pytest.raises(MediaValidationError): concatenate_wav([parts[0], wav_bytes(sample_rate=16000)], pauses_ms=[100])
    with pytest.raises(ValueError): LocalPcmMixer().mix(MixerRequest('bad', [{'content':parts[0][:-4], 'start_ms':0}], []))


def test_original_export_varied_pauses_and_directed_current_authority_guard(rig, setup):
    _, _, factory = api_client(rig, setup); executor = factory(rig.scope, rig.actor)
    jobs = []
    for pause in (125,350,999):
        job = executor.queue(rig.nid, rig.chapter, {'pause_ms':pause}, [])
        asset = audio_asset(rig)
        executor.store.mutate(rig.nid, lambda state, jid=job['id'], aid=asset['id']: executor.find(state,jid).update(status='SUCCEEDED', asset_id=aid, duration_ms=100))
        jobs.append(job['id'])
    output, manifest = executor.export_chapter(rig.nid, rig.chapter['id'], jobs)
    assert [r['start_ms'] for r in manifest['segments']] == [0,225,675]
    assert manifest['duration_ms'] == 775 and pcm(output)[1] == 6200
    executor.store.mutate(rig.nid, lambda state: executor.find(state,jobs[0]).update(experimental_origin='voice_direction_v2'))
    with pytest.raises(AudiobookError, match='声音导演'): executor.export_chapter(rig.nid, rig.chapter['id'], jobs)


def test_rejected_mix_source_asset_change_and_permission_revocation(rig, setup):
    p, ids = measured_plan(rig, setup); p = approve(rig, setup.voice, p)
    client, authority, _ = api_client(rig, setup); base = f'/novels/{rig.nid}/experimental'
    mixed = client.post(f'{base}/voice-direction/plans/{p["id"]}/mix', json={'expected_version':p['version']}).json()
    rejected = client.post(f'{base}/audiobook/mixes/{mixed["id"]}/reject', json={'expected_version':mixed['version']}).json()
    assert client.get(f'{base}/voice-direction/mixes/{mixed["id"]}/audio?expected_version={rejected["version"]}').status_code == 422
    class Revoked(LocalPcmMixer):
        def mix(self, request):
            result = super().mix(request); authority['allowed'] = False
            return result
    setup.voice.mixer = Revoked()
    assert client.post(f'{base}/voice-direction/plans/{p["id"]}/mix', json={'expected_version':p['version']}).status_code == 403
    authority['allowed'] = True; setup.voice.mixer = LocalPcmMixer()
    mixed = client.post(f'{base}/voice-direction/plans/{p["id"]}/mix', json={'expected_version':p['version']}).json()
    rig.assets.update_metadata(ids[0], {'model_id':'new source version'})
    assert client.get(f'{base}/voice-direction/mixes/{mixed["id"]}/audio?expected_version={mixed["version"]}').status_code == 409
    assert client.post(f'{base}/audiobook/mixes/{mixed["id"]}/approve', json={'expected_version':mixed['version']}).status_code == 409


def test_mixer_output_limit_and_non_pcm16_are_explicit():
    with pytest.raises(ValueError, match='OUTPUT_TOO_LARGE'):
        LocalPcmMixer().mix(MixerRequest('bounded', [{'content':wav_bytes(), 'start_ms':2_000_000}], []))
    data=io.BytesIO()
    with wave.open(data, 'wb') as writer:
        writer.setnchannels(1);writer.setsampwidth(1);writer.setframerate(8000);writer.writeframes(b'\x80'*800)
    with pytest.raises(ValueError, match='PCM16_REQUIRED'):
        LocalPcmMixer().mix(MixerRequest('unsupported', [{'content':data.getvalue(), 'start_ms':0}], []))


def test_mix_inherits_batch_asset_origin_before_and_after_review(rig, setup, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,subtitle_timeline_v2,reader_preflight_v2,safe_batches_v2')
    p, _ = measured_plan(rig, setup); v = setup.voice
    asset = rig.assets.create(rig.nid,'accepted-batch.wav',base64.b64encode(wav_bytes()).decode(),'audio/wav','audio',required_features=('voice_direction_v2','safe_batches_v2'))
    p = v.as_actor(rig.actor,v.bind_audio,rig.nid,rig.scope,rig.actor,p['id'],p['segments'][0]['id'],{'expected_version':p['version'],'asset_id':asset['id']})
    p = approve(rig,v,p)
    mixed = v.as_actor(rig.actor,v.mix,rig.nid,rig.scope,rig.actor,p['id'],p['version'])
    assert 'safe_batches_v2' in mixed['required_features']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,subtitle_timeline_v2')
    assert v.as_actor(rig.actor,v.list,rig.nid,rig.scope,v.MIXES) == []
    with pytest.raises(FileNotFoundError): v.as_actor(rig.actor,v.mix_audio,rig.nid,rig.scope,rig.actor,mixed['id'],mixed['version'])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,subtitle_timeline_v2,reader_preflight_v2,safe_batches_v2')
    accepted = v.as_actor(rig.actor,v.review,rig.nid,rig.scope,rig.actor,mixed['id'],'approve',mixed['version'])
    assert 'safe_batches_v2' in rig.assets.get(accepted['asset_id'])['_required_features']
    assert 'content_base64' not in __import__('json').dumps(v.catalog(rig.nid,rig.scope,rig.actor)['mixes'])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,subtitle_timeline_v2')
    with pytest.raises(FileNotFoundError): rig.assets.content(accepted['asset_id'])


def test_marking_old_manual_approval_directed_does_not_skip_voice_review(rig, setup):
    v = setup.voice; v.mixer = LocalPcmMixer(); p = setup.plan
    asset = audio_asset(rig)
    for segment in p['segments']:
        if segment['attribution_status'] == 'NEEDS_REVIEW':
            p = v.update_segment(rig.nid,rig.scope,rig.actor,p['id'],segment['id'],{'expected_version':p['version'],'character_id':'alice','profile_id':setup.profile['id'],'attribution_reviewed':True})
        p = v.bind_audio(rig.nid,rig.scope,rig.actor,p['id'],segment['id'],{'expected_version':p['version'],'asset_id':asset['id']})
    p = approve(rig,v,p)
    p = v.lock(rig.nid, rig.scope, rig.actor, p['id'], p['segments'][0]['id'], {'expected_version':p['version'], 'locked':True})
    with pytest.raises(ValueError, match='TEXT_AND_VOICE_REVIEW_REQUIRED'):
        v.as_actor(rig.actor,v.mix,rig.nid,rig.scope,rig.actor,p['id'],p['version'])


def test_preview_rechecks_current_source_after_reading_approved_bytes(rig, setup, monkeypatch):
    p, _ = measured_plan(rig, setup); v = setup.voice; p = approve(rig,v,p)
    mixed = v.as_actor(rig.actor,v.mix,rig.nid,rig.scope,rig.actor,p['id'],p['version'])
    accepted = v.as_actor(rig.actor,v.review,rig.nid,rig.scope,rig.actor,mixed['id'],'approve',mixed['version'])
    original = rig.assets.content
    def changed(aid, **kwargs):
        result = original(aid, **kwargs)
        if aid == accepted['asset_id']:
            chapter = rig.chapters.get(rig.chapter['id'])
            rig.chapters.save(chapter['id'],{'version':chapter['version'],'content':'Changed during byte read'})
        return result
    monkeypatch.setattr(rig.assets,'content',changed)
    with pytest.raises(StaleSourceError):
        v.as_actor(rig.actor,v.mix_audio,rig.nid,rig.scope,rig.actor,mixed['id'],accepted['version'])
