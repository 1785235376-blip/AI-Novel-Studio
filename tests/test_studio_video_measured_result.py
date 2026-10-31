"""The video generation owner records facts from decoded candidate bytes."""
import base64
import copy
import hashlib
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from app.media_files import MediaValidationError, inspect_media
from app.services.studio_video_execution import StudioVideoExecution


class Owner:
    def __init__(self, root, row):
        self.root = root
        self.row = copy.deepcopy(row)
        self.assets = SimpleNamespace(MAX_BYTES=16 * 1024 * 1024)

    def _studio_read(self, nid, branch, actor, jid, *, context):
        return copy.deepcopy(self.row)

    def _studio_mutate(self, nid, branch, actor, jid, version, change, *, context):
        assert self.row['version'] == version
        change(self.row)
        self.row['version'] += 1
        return copy.deepcopy(self.row)


@pytest.fixture
def execution(tmp_path):
    context = {'actor': 'a', 'scope_key': 's', 'incarnation': 'i', 'request_digest': 'd',
               'operation_id': 'm7.video.t2v', 'sources': []}
    row = {'id': 'job', 'contract': 'studio-video-execution/1', 'version': 1, 'status': 'SEND_RESERVED', 'attempt': 1,
           'request_digest': 'd', 'context': context, 'execution_token': 'token',
           'body': {'provider_id': 'p', 'model_id': 'm'}}
    owner = Owner(tmp_path, row)
    return StudioVideoExecution(owner), owner, context


def test_synthetic_video_is_decoded_and_existing_receipt_shape_preserved(execution, tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg and ffprobe are required for actual media verification')
    path = tmp_path / 'source.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=96x64:r=10:d=1',
                    '-c:v', 'mpeg4', '-y', str(path)], check=True, timeout=30)
    data = path.read_bytes()
    independently_measured = inspect_media(data, 'video', include_video_dimensions=True)
    assert (independently_measured['width'], independently_measured['height']) == (96, 64)
    service, owner, context = execution
    observed = []

    def publish(payload, kind, filename, measured, jid, current):
        current()
        observed.append((payload, copy.deepcopy(measured)))
        return {'id': 'candidate', 'version': 1, 'kind': kind, 'sha256': hashlib.sha256(payload).hexdigest(),
                'size': len(payload), 'media_type': measured['media_type'], '_owner_actor_id': 'a',
                'source_job_id': jid, '_required_features': ['narrative_production_v2'],
                '_project_binding': {'novel_id': 'n', 'branch_id': None, 'scope_key': 's', 'incarnation': 'i'},
                '_studio_result_origin': {'contract': 'studio-production-result/1', 'job_id': jid,
                    **{key: context[key] for key in ('actor', 'scope_key', 'incarnation', 'request_digest', 'operation_id', 'sources')},
                    'provider_id': 'p', 'model_id': 'm', 'license_note': ''}}

    uri = 'data:video/mp4;base64,' + base64.b64encode(data).decode('ascii')
    result = service._complete('n', None, 'a', owner.row, context, uri, None,
                               lambda: None, lambda _: None, publish, None, lambda: None)
    assert result['status'] == 'AWAITING_REVIEW'
    assert observed[0][0] == data
    assert result['measured']['validation'] == 'DECODED'
    assert set(result['measured']) == {'media_type', 'extension', 'duration_ms', 'validation', 'codec'}
    assert result['measured']['media_type'] == 'video/mp4'
    assert result['measured']['duration_ms'] == 1000
    assert result['measured']['codec'] == 'mpeg4'
    assert result['output_candidate']['digest'] == hashlib.sha256(data).hexdigest()


def test_invalid_video_never_becomes_candidate(execution):
    service, owner, context = execution
    published = []
    uri = 'data:video/mp4;base64,' + base64.b64encode(b'not a video').decode('ascii')
    with pytest.raises(MediaValidationError):
        service._complete('n', None, 'a', owner.row, context, uri, None, lambda: None,
                          lambda _: None, lambda *args: published.append(args), None, lambda: None)
    assert published == []
    assert owner.row['status'] == 'SEND_RESERVED'
