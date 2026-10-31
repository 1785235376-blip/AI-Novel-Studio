"""Real synthetic FLAC in the original shared audio owner, not quota admission."""
import base64
import hashlib
import io
import json
import shutil
import struct
import subprocess
import wave

import pytest

from app.experimental.audio_shared_document_measurement import (
    measure_file_scope_document,
    plan_file_scope_replacement,
)
from app.experimental.audiobook import AudiobookV2Service, MixerResult
from app.experimental.store import ExperimentalStore
from test_studio_asset_query import rig


def _run(*argv):
    return subprocess.run(argv, check=True, capture_output=True, timeout=30).stdout


def test_original_audio_owner_flac_candidate_and_history_measurement(rig, tmp_path):
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        pytest.skip('installed ffmpeg and ffprobe are required')

    # Both the source and the mixed result are synthetic PCM, not model output.
    pcm = b''.join(struct.pack('<h', ((i % 101) - 50) * 300) for i in range(8000))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(pcm)
    wav = buffer.getvalue()
    source = tmp_path / 'synthetic-source.wav'
    flac_path = tmp_path / 'synthetic-result.flac'
    source.write_bytes(wav)
    _run(ffmpeg, '-nostdin', '-v', 'error', '-y', '-i', str(source), '-c:a', 'flac', str(flac_path))
    flac = flac_path.read_bytes()
    digest = hashlib.sha256(flac).hexdigest()
    probe = json.loads(_run(ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                            'stream=codec_name,sample_rate,channels,duration:format=duration',
                            '-of', 'json', str(flac_path)))
    stream = probe['streams'][0]
    assert (stream['codec_name'], int(stream['sample_rate']), stream['channels']) == ('flac', 8000, 1)
    assert abs(float(stream.get('duration') or probe['format']['duration']) - 1.0) < 0.001
    assert _run(ffmpeg, '-nostdin', '-v', 'error', '-i', str(flac_path), '-f', 's16le',
                '-acodec', 'pcm_s16le', '-') == pcm

    class SyntheticFlacMixer:
        adapter_id, local = 'synthetic-flac-fixture', True

        def mix(self, request):
            assert request.speech and request.speech[0]['content'] == wav
            return MixerResult(flac, 'audio/flac', 'CONTRACT_VERIFIED')

    chapter = rig.workspace.creative.chapters.create(rig.nid, {'title': '合成章节', 'content': '合成旁白'})
    asset = rig.assets.create(rig.nid, 'synthetic-source.wav', base64.b64encode(wav).decode('ascii'),
                              'audio/wav', 'audio')
    store = rig.workspace.store.store
    service = AudiobookV2Service(store, rig.novels, rig.workspace.creative.chapters,
                                 rig.assets, mixer=SyntheticFlacMixer())
    profile = service.create_profile(rig.nid, rig.scope, 'author', {
        'display_name': '合成声线', 'provider_id': 'none', 'model_id': 'none',
        'voice_id': 'none', 'license_note': 'synthetic only'})
    plan = service.create_plan(rig.nid, rig.scope, 'author', {'chapter_id': chapter['id']})
    segment = plan['segments'][0]
    plan = service.update_segment(rig.nid, rig.scope, 'author', plan['id'], segment['id'],
                                  {'expected_version': plan['version'], 'profile_id': profile['id']})
    plan = service.bind_audio(rig.nid, rig.scope, 'author', plan['id'], segment['id'],
                              {'expected_version': plan['version'], 'asset_id': asset['id']})
    plan = service.review(rig.nid, rig.scope, 'author', plan['id'], 'approve', plan['version'])

    first = service.mix(rig.nid, rig.scope, 'author', plan['id'], plan['version'])
    path = store.path(rig.nid, rig.scope)
    pending_bytes = path.read_bytes()
    pending = measure_file_scope_document(pending_bytes, rig.nid, rig.scope)
    rejected = service.review(rig.nid, rig.scope, 'author', first['id'], 'reject', first['version'])
    assert rejected['status'] == 'REJECTED'
    rejected_bytes = path.read_bytes()
    rejected_measure = measure_file_scope_document(rejected_bytes, rig.nid, rig.scope)
    plan_result = plan_file_scope_replacement(pending_bytes, rejected_bytes, rig.nid, rig.scope)
    assert plan_result['previous_sha256'] == hashlib.sha256(pending_bytes).hexdigest()
    assert plan_result['replacement_sha256'] == hashlib.sha256(rejected_bytes).hexdigest()
    assert plan_result['persistent_candidate_delta'] == (
        rejected_measure['mix_collection_bytes'] - pending['mix_collection_bytes'])
    assert plan_result['temporary_reservation_bytes'] == len(rejected_bytes)

    # Reopening the original File owner must preserve the exact encoded bytes
    # and count both physically serialized copies (current row and snapshot).
    reopened = ExperimentalStore(rig.root, 'file', '')
    row = reopened.read(rig.nid, rig.scope)['collections'][service.MIXES][first['id']]
    assert row['content_sha256'] == digest
    assert base64.b64decode(row['content_base64'], validate=True) == flac
    assert len(row['history']) == 1
    assert base64.b64decode(row['history'][0]['content_base64'], validate=True) == flac
    assert row['media']['media_type'] == 'audio/flac'
    assert row['media']['validation'] == 'DECODED'
    assert rejected_bytes.count(base64.b64encode(flac)) == 2
    assert rejected_measure['mix_collection_bytes'] > 2 * len(base64.b64encode(flac))

    second = service.mix(rig.nid, rig.scope, 'author', plan['id'], plan['version'])
    approved = service.review(rig.nid, rig.scope, 'author', second['id'], 'approve', second['version'])
    assert approved['status'] == 'APPROVED'
    metadata = rig.assets.get(approved['asset_id'])
    assert (metadata['media_type'], metadata['size'], metadata['sha256']) == ('audio/flac', len(flac), digest)
    assert rig.assets.content(metadata['id']) == flac
    reopened_final = ExperimentalStore(rig.root, 'file', '')
    saved = reopened_final.read(rig.nid, rig.scope)['collections'][service.MIXES][second['id']]
    assert saved['status'] == 'APPROVED' and saved['asset_id'] == metadata['id']
    final_measure = measure_file_scope_document(path.read_bytes(), rig.nid, rig.scope)
    assert final_measure['mix_collection_bytes'] > rejected_measure['mix_collection_bytes']
    print(json.dumps({'format': 'flac', 'bytes': len(flac), 'sha256': digest,
                      'sample_rate': 8000, 'channels': 1, 'duration_seconds': 1,
                      'pcm_sha256': hashlib.sha256(pcm).hexdigest()}, sort_keys=True))
