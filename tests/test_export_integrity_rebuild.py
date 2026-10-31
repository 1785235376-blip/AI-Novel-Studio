"""New synthetic tests, not recovered evidence from the previous workspace."""
import base64
import json
import multiprocessing
import os
from pathlib import Path
import time

import pytest

from app.services.export_job_service import ExportJobService, ExportJobResultInvalid


@pytest.fixture
def completed(tmp_path):
    service = ExportJobService(tmp_path, lambda *_: {'content': '原文', 'format': 'txt'})
    job = service.create('synthetic-novel', 'txt')
    for _ in range(300):
        row = service.get(job['id'])
        if row['status'] in {'succeeded', 'failed'}:
            break
        time.sleep(.01)
    assert row['status'] == 'succeeded'
    yield service, row
    service._pool.shutdown(wait=True)


def mutate(service, row, change):
    rows = json.loads(service.path.read_text())
    change(rows[row['id']])
    service.path.write_text(json.dumps(rows))


@pytest.mark.parametrize('change', ['content', 'size', 'hash'])
def test_missing_artifact_still_binds_receipt(completed, change):
    service, row = completed
    (service.artifact_root / row['artifact']['path']).unlink()
    def edit(item):
        if change == 'content': item['result']['content'] = '另文'
        elif change == 'size': item['artifact']['size'] += 1
        else: item['artifact']['sha256'] = '0' * 64
    mutate(service, row, edit)
    with pytest.raises(ExportJobResultInvalid):
        service.download(row['id'])


def test_valid_fallback_is_readonly_and_survives_reopen(completed):
    service, row = completed
    path = service.artifact_root / row['artifact']['path']
    path.unlink()
    before = service.path.read_bytes()
    assert service.download(row['id'])['content'] == '原文'.encode()
    other = ExportJobService(service.path.parent, lambda *_: pytest.fail('must not render'))
    try: assert other.download(row['id'])['content'] == '原文'.encode()
    finally: other._pool.shutdown(wait=True)
    assert not path.exists()
    assert service.path.read_bytes() == before


def test_legacy_no_artifact_remains_supported(completed):
    service, row = completed
    mutate(service, row, lambda item: item.pop('artifact'))
    assert service.download(row['id'])['content'] == '原文'.encode()


def test_regular_file_integrity_still_checked(completed):
    service, row = completed
    (service.artifact_root / row['artifact']['path']).write_bytes(b'wrong')
    with pytest.raises(ExportJobResultInvalid): service.download(row['id'])


@pytest.mark.parametrize('key', ['content', 'content_base64'])
def test_encoded_limit_checked_before_decoder(monkeypatch, key):
    monkeypatch.setattr(ExportJobService, 'MAX_RESULT_BYTES', 3)
    def decoder(*_args, **_kwargs): pytest.fail('oversize reached decoder')
    monkeypatch.setattr(base64, 'b64decode', decoder)
    with pytest.raises(ExportJobResultInvalid, match='limit'):
        ExportJobService._result_bytes({key: 'YWJjYWJj', 'content_encoding': 'base64'})


@pytest.mark.parametrize('key', ['content', 'content_base64'])
@pytest.mark.parametrize('payload', [b'', b'a', b'abc', b'abcd'])
def test_decode_boundary(monkeypatch, key, payload):
    monkeypatch.setattr(ExportJobService, 'MAX_RESULT_BYTES', 3)
    result = {key: base64.b64encode(payload).decode(), 'content_encoding': 'base64'}
    if len(payload) > 3:
        with pytest.raises(ExportJobResultInvalid): ExportJobService._result_bytes(result)
    else: assert ExportJobService._result_bytes(result) == payload


def test_directory_is_stable_result_error(completed):
    service, row = completed
    target = service.artifact_root / row['artifact']['path']
    target.unlink(); target.mkdir()
    with pytest.raises(ExportJobResultInvalid): service.download(row['id'])


def _fifo_child(root, job_id, output):
    service = ExportJobService(Path(root), lambda *_: {})
    try:
        try: service.download(job_id)
        except ExportJobResultInvalid: output.put('rejected')
        else: output.put('unexpected success')
    finally: service._pool.shutdown(wait=True)


@pytest.mark.skipif(os.name != 'posix', reason='POSIX synthetic FIFO')
def test_fifo_download_never_blocks(completed):
    service, row = completed
    target = service.artifact_root / row['artifact']['path']
    target.unlink(); os.mkfifo(target)
    ctx = multiprocessing.get_context('spawn')
    output = ctx.Queue()
    child = ctx.Process(target=_fifo_child, args=(str(service.path.parent), row['id'], output))
    child.start(); child.join(3)
    try:
        assert not child.is_alive(), 'FIFO download exceeded watchdog'
        assert child.exitcode == 0
        assert output.get(timeout=1) == 'rejected'
    finally:
        if child.is_alive(): child.kill(); child.join(3)
        output.close()
