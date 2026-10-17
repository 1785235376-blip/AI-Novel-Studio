"""Closed Creative branch of original PreparedTextInvocation; no provider calls.

Supported-caller and persistence boundaries are tested, not protection from
arbitrary Python reflection. The real coordinator alone creates the capability.
"""
from dataclasses import replace
from threading import Event

import pytest

from app.jobs import JobManager, check_generation_bounds, generation_content_available
from app.model_execution import PreparedTextInvocation, _CreativeDirectorCapability
from creative_director_execution_fixture import lifecycle, preview, dispatch

pytestmark = pytest.mark.file_backend_only


def prepared_only(e, monkeypatch):
    captured = []
    def hold(job, capability):
        assert job.creative_execution_authority is capability
        captured.append(job)
        return job
    monkeypatch.setattr(e.manager, "_start_creative_director_job", hold)
    row = preview(e)
    dispatch(e, row)
    assert len(captured) == 1 and not e.requests and not e.manager.jobs
    return captured[0]


def test_only_original_coordinator_issues_bound_transient_invocation(lifecycle, monkeypatch):
    e = lifecycle; job = prepared_only(e, monkeypatch)
    invocation = job.prepared_text_invocation
    assert type(invocation) is PreparedTextInvocation
    assert type(job.creative_execution_authority) is _CreativeDirectorCapability
    invocation._validate_creative(job, manager=e.manager)
    assert invocation.request.job_id == job.id
    assert invocation.request.cancellation is job.cancelled
    assert invocation.adapter.runtime is e.runtime
    assert invocation.adapter._provider is e.adapter
    assert invocation.binding_digest == job.expected_request_digest
    assert not generation_content_available(job)
    assert "creative_execution_authority" not in job.public()
    with pytest.raises(ValueError, match="GRAPH_PREPARED_DOMAIN_INVALID"):
        invocation.validate_job(job)
    with pytest.raises(ValueError, match="GRAPH_PREPARED_DOMAIN_INVALID"):
        PreparedTextInvocation.bind(job, invocation.request, invocation.adapter, False)
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE"):
        e.manager.start_prepared(job)
    with pytest.raises(ValueError): invocation._validate_creative(job, manager=object())
    with pytest.raises(ValueError): invocation._validate_creative(job, started=True)
    assert not e.requests


@pytest.mark.parametrize("mutation", ["job_copy", "cancel", "request_copy", "invocation_copy", "adapter",
    "scope", "binding", "digest", "route_fingerprint", "parameters", "metadata", "context", "callback",
    "before_dispatch", "on_terminal", "removed_markers"])
def test_exact_object_and_payload_contract_cannot_be_substituted(lifecycle, monkeypatch, mutation):
    e = lifecycle; job = prepared_only(e, monkeypatch)
    invocation = job.prepared_text_invocation
    if mutation == "job_copy": job = replace(job)
    elif mutation == "cancel": job.cancelled = Event()
    elif mutation == "request_copy": invocation = replace(invocation, request=replace(invocation.request))
    elif mutation == "invocation_copy": invocation = replace(invocation)
    elif mutation == "adapter": invocation = replace(invocation, adapter=object())
    elif mutation == "scope": job.scope["novel_id"] = "other"
    elif mutation == "binding": job.creative_director_binding["source_digest"] = "f" * 64
    elif mutation == "digest": job.expected_request_digest = "f" * 64
    elif mutation == "route_fingerprint": job.creative_execution_authority.route_fingerprint = "f" * 64
    elif mutation == "parameters": invocation = replace(invocation, request=replace(invocation.request,
        parameters=replace(invocation.request.parameters, temperature=1.0)))
    elif mutation == "metadata": invocation.request.metadata["purpose"] = "other"
    elif mutation == "context": invocation.request.context["unreviewed"] = "text"
    elif mutation == "callback": invocation = replace(invocation, request=replace(invocation.request, dispatch_guard=lambda: None))
    elif mutation == "before_dispatch": job.before_dispatch = lambda: None
    elif mutation == "on_terminal": job.on_terminal = lambda: None
    else:
        job.creative_director_binding = None; job.experimental_origin = None; job.operation = "brainstorm"
    with pytest.raises(ValueError):
        invocation._validate_creative(job)
        check_generation_bounds(job)
    assert not generation_content_available(job)
    assert not e.requests


def test_passive_record_and_unsealed_capability_cannot_prepare(lifecycle):
    e = lifecycle
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_LIVE_AUTHORITY_REQUIRED"):
        _CreativeDirectorCapability(object(), e.manager, e.authority, lambda: None, lambda: None, "f" * 64)
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE"):
        e.manager._prepare_creative_director_job(None, request_binding={}, provider_id="mock", model_id="mock-writer",
            prompt="untrusted", max_output_bytes=256, deadline="invalid", synthetic_allowed=True)
    assert not e.requests and not e.manager.jobs


def test_capability_is_single_bind_and_broker_hook_pair_is_sealed(lifecycle, monkeypatch):
    e = lifecycle; job = prepared_only(e, monkeypatch)
    capability, invocation = job.creative_execution_authority, job.prepared_text_invocation
    with pytest.raises(ValueError): capability._attach(job)
    with pytest.raises(ValueError): capability._bind_hooks(job, lambda: None, lambda: None)
    with pytest.raises(ValueError):
        PreparedTextInvocation._bind_creative(job, invocation.request, invocation.adapter, False, capability)
    invocation._validate_creative(job)
    assert not e.requests


def test_shared_start_tail_rejects_inert_creative_before_all_side_effects(monkeypatch):
    from uuid import uuid4
    import app.jobs as jobs_module
    from app.jobs import Job
    from creative_director_execution_fixture import ForbiddenOwner
    forbidden = ForbiddenOwner()
    manager = object.__new__(JobManager)
    manager.persistence = forbidden
    job = Job(str(uuid4()), "creative_director_text", "inert", None, "", "LOCAL_ONLY", status="PREPARED")
    job.request_authorization = job.before_dispatch = job.on_terminal = forbidden
    monkeypatch.setattr(jobs_module.threading, "Thread", forbidden)
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE"):
        manager._start_prepared_validated(job)
    assert job.status == "PREPARED" and job.terminal_hook_status is None
