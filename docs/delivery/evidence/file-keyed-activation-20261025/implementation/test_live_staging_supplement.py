"""New live capability does not widen staged-variant mutation eligibility."""
import pytest
from fastapi import HTTPException
from test_file_keyed_activation import keyed, memory_settings, queued, finish


def test_live_bound_candidate_cannot_stage_reviewed_variants(keyed):
    f=keyed
    _,job=queued(f)
    before=f.bundle.generations._job_path(job.id).read_bytes()
    states=dict(job.public())
    with pytest.raises(HTTPException) as exc:
        f.manager.stage_reviewed_variants([job])
    assert exc.value.status_code==409
    assert exc.value.detail['code']=='GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'
    assert f.bundle.generations._job_path(job.id).read_bytes()==before
    assert job.public()==states and job.reviewed_variant_receipt_state is None
    assert f.counts['provider']==0
    finish(f,job)
