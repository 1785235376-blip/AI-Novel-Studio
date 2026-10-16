"""Trusted original JobManager bounds; no second executor or paid inference."""
from datetime import datetime, timedelta, timezone
import time

import pytest
from fastapi import HTTPException
from app.jobs import Job, check_generation_bounds, validate_generation_bounds, mark_generation_origin, require_whole_generation_acceptance
from app.experimental.author_context_api import AuthorPreviewInput
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_broker_mounted import broker_app, author_body


def bounded_job():
    value = Job('synthetic', 'brainstorm', 'novel', 'chapter', 'instructions', 'LOCAL_ONLY')
    value.generation_max_output_bytes = 256
    value.generation_deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    return value


def test_utf8_bound_discards_output_and_does_not_double_count_completion():
    job = bounded_job(); job.output = '潮' * 80
    check_generation_bounds(job, completion_text=job.output)
    assert job.output == '潮' * 80
    with pytest.raises(ValueError, match='GENERATION_OUTPUT_LIMIT'):
        check_generation_bounds(job, delta='潮' * 6)
    assert not job.output and job.cancelled.is_set()
    assert job.generation_bound_failure == 'GENERATION_OUTPUT_LIMIT'
    completion = bounded_job()
    with pytest.raises(ValueError, match='GENERATION_OUTPUT_LIMIT'):
        check_generation_bounds(completion, completion_text='潮' * 86)


@pytest.mark.parametrize('size,deadline', [(True, '2026-01-01'), (128001, '2026-01-01'), (256, '2026-01-01'), (None, '2026-01-01'), (256, None), (256, 'invalid')])
def test_invalid_trusted_bounds_rejected(size, deadline):
    job = bounded_job(); job.generation_max_output_bytes = size; job.generation_deadline = deadline
    with pytest.raises(ValueError, match='GENERATION_BOUNDS_INVALID'): validate_generation_bounds(job)


def test_deadline_discards_incomplete_output():
    job = bounded_job(); job.output = 'Synthetic partial'; job.generation_deadline = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match='GENERATION_DEADLINE_EXCEEDED'): check_generation_bounds(job)
    assert not job.output and job.cancelled.is_set()


def test_declarative_origin_blocks_legacy_accept_even_after_persisted_reload(broker_app):
    e = broker_app; job = e.manager.prepare_job('brainstorm', {**author_body(e), 'generation_max_output_bytes': 300, 'generation_deadline': 'browser invented'})
    assert job.generation_max_output_bytes is None and job.generation_deadline is None
    mark_generation_origin(job, 'declarative_agent')
    job.generation_max_output_bytes = 256; job.generation_deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    e.manager._persist(job)
    stored = e.manager.persistence.get(job.id)
    assert stored['generation_max_output_bytes'] == 256 and stored['generation_deadline'] == job.generation_deadline
    restored = Job(**{k: v for k, v in stored.items() if k in Job.__dataclass_fields__ and k not in e.manager.transient_fields})
    with pytest.raises(HTTPException) as blocked: require_whole_generation_acceptance(restored)
    assert blocked.value.detail['code'] == 'DECLARATIVE_DRAFT_ONLY'


def test_original_stream_discards_oversized_utf8_and_retains_truthful_terminal_cause(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *args, **kwargs: iter(['潮' * 80, '潮' * 6]))
    author = author_body(e)
    receipt = checked(e.client.post(e.base + '/author-context/preview', headers=e.headers, json=author))
    job = e.experimental.author_preparer.prepare_author(e.nid, AuthorPreviewInput.model_validate({**author, 'preview_digest': receipt['preview_digest']}), 'broker-host')
    mark_generation_origin(job, 'declarative_agent')
    job.generation_max_output_bytes = 256; job.generation_deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    e.manager.start_prepared(job)
    deadline = time.monotonic() + 5
    while job.status not in e.manager.terminal and time.monotonic() < deadline: time.sleep(.01)
    assert job.status == 'FAILED' and job.error_code == 'GENERATION_OUTPUT_LIMIT' and not job.output
    assert job.cancelled.is_set() and job.execution_outcome == 'FAILED'


def test_started_bounds_are_immutable_between_provider_events():
    job = bounded_job(); job._generation_bounds = (job.generation_max_output_bytes, job.generation_deadline)
    job.output = 'Incomplete synthetic'; job.generation_max_output_bytes = 128000
    with pytest.raises(ValueError, match='GENERATION_BOUNDS_CHANGED'): check_generation_bounds(job, delta='new')
    assert job.output == '' and job.cancelled.is_set()
