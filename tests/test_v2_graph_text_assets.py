"""M4-B real-owner text archival; provider output is built-in synthetic only."""
from copy import deepcopy
from hashlib import sha256

import pytest

from app.jobs import JobManager
from app.creative.text_assets import CONTRACT
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig
from test_v2_ai_execution_runtime import (model_rig, admit, preview, action, raw, current,
    wait_job, spy_transport, owned_jobs, ForbiddenOwner, generation_delta)


def dispatch_asset(e):
    row = preview(e, admit(e))
    sent = e.models.dispatch(e.nid, e.scope, e.actor, row["id"], {"expected_version": row["version"],
        "reviewed_preview_digest": row["model_runtime"]["preview"]["preview_digest"], "archive_result": True}, e.guard)
    job = e.manager.get(sent["model_runtime"]["execution"]["job_id"])
    wait_job(e, job)
    # A restart fixture must stop the actual worker, not race its final emit
    # after terminal_hook_status first becomes COMPLETED.
    if e.calls:
        e.calls[-1]["worker"].join(8)
        assert not e.calls[-1]["worker"].is_alive(), "original worker did not stop"
    return sent, job


def assets(e):
    with e.service._asset_scope(e.nid, e.scope):
        return e.assets.list(e.nid, branch_id=e.scope.get("branch_id"), actor_id=e.actor, include_deleted=True)


def approve(e, row):
    return action(e, row, "approve", node_id=row["review"]["node_id"],
        reviewed_output_digest=row["review"]["output_digest"])


def test_existing_read_archives_one_draft_then_original_review_updates_version(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    assert sent["asset_output"]["state"] == "PENDING"
    assert not assets(e)
    before = deepcopy(e.chapters.list(e.nid))
    waiting = current(e, sent)
    assert waiting["status"] == "WAITING_APPROVAL" and waiting["review"] and not waiting["stale"]
    receipt = waiting["asset_output"]
    assert receipt["contract"] == CONTRACT and receipt["state"] == "DRAFT" and receipt["version"] == 1
    assert receipt["source"]["job_id"] == job.id and receipt["sha256"] == sha256(job.output.encode()).hexdigest()
    assert receipt["source"]["output_digest"] != waiting["review"]["output_digest"]
    saved = assets(e)
    assert len(saved) == 1 and saved[0]["_owner_actor_id"] == e.actor
    assert saved[0]["source_job_id"] == job.id
    done = approve(e, waiting)
    assert done["status"] == "SUCCEEDED" and done["reviewed"] and not done["applied"]
    assert done["asset_output"]["asset_id"] == receipt["asset_id"]
    assert done["asset_output"]["state"] == "APPROVED" and done["asset_output"]["version"] == 2
    stable = current(e, done)
    assert stable == current(e, done)
    assert stable["asset_output"]["version"] == 2
    assert len(e.calls) == len(owned_jobs(e)) == len(generation_delta(e)) == len(assets(e)) == 1
    assert e.chapters.list(e.nid) == before
    assert assets(e)[0]["_owner_actor_id"] == e.actor


def test_completed_restart_reconciles_without_rebuilding_execution_authority(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    owner = ForbiddenOwner()
    reopened = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner,
        snapshot_required=True, collaboration_updates=owner)
    loaded = reopened.get(job.id)
    assert loaded.prepared_text_invocation is None and loaded.request_authorization is None
    def forbidden(*args, **kwargs):
        raise AssertionError("recovery attempted model dispatch")
    monkeypatch.setattr(reopened, "start_prepared", forbidden)
    monkeypatch.setattr(e.models, "manager", reopened)
    recovered = current(e, sent)
    assert not recovered["stale"] and recovered["asset_output"]["state"] == "DRAFT", recovered
    assert recovered["review"]["draft"]["text"] == job.output
    done = approve(e, recovered)
    assert done["asset_output"]["state"] == "APPROVED"
    assert loaded.request_authorization is None and loaded.prepared_text_invocation is None
    assert len(e.calls) == len(assets(e)) == 1


@pytest.mark.parametrize("after_commit", [False, True])
def test_archive_io_fault_retains_result_and_existing_refresh_recovers_once(model_rig, monkeypatch, after_commit):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    original = e.assets._write_meta
    writes = []
    def crash(meta):
        writes.append(meta["id"])
        if len(writes) == 1:
            if after_commit:
                original(meta)
            raise OSError("synthetic archive failure")
        return original(meta)
    monkeypatch.setattr(e.assets, "_write_meta", crash)
    failed = current(e, sent)
    assert failed["asset_output"]["state"] == "INCOMPLETE" and failed["stale"] and failed["review"] is None
    assert all(state["output"] is None for state in failed["node_states"].values())
    assert job.status == "COMPLETED" and job.output and e.persistence.get(job.id)["output"] == job.output
    assert current(e, sent)["asset_output"]["state"] == "INCOMPLETE"
    assert len(writes) == 1, "read cooldown must not retry the failed write"
    live = raw(e, sent)
    recovered = e.models.refresh(e.nid, e.scope, e.actor, sent["id"], {"expected_version": live["version"]}, e.guard)
    assert recovered["asset_output"]["state"] == "DRAFT" and not recovered["stale"]
    assert len(assets(e)) == len(e.calls) == 1
    if after_commit:
        assert recovered["asset_output"]["asset_id"] == writes[0] and len(writes) == 1
    else:
        assert len(writes) == 2


def test_archive_to_workflow_gap_reopens_without_duplicate_asset_or_model(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    original = e.models._refresh
    def crash(*args, **kwargs):
        raise OSError("synthetic crash after asset before workflow")
    monkeypatch.setattr(e.models, "_refresh", crash)
    first = current(e, sent)
    assert first["stale"] and first["asset_output"]["state"] == "INCOMPLETE"
    archived = assets(e)[0]
    assert raw(e, sent)["status"] == "RUNNING" and archived["version"] == 1
    monkeypatch.setattr(e.models, "_refresh", original)
    owner = ForbiddenOwner()
    reopened = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner,
        snapshot_required=True, collaboration_updates=owner)
    # New runtime adapter models a process reopen, including an empty retry
    # throttle. Original durable owners and their identity remain unchanged.
    e.graphs.configure_models(e.broker, reopened)
    e.models = e.graphs.model_runtime
    recovered = current(e, sent)
    assert not recovered["stale"] and recovered["asset_output"]["asset_id"] == archived["id"]
    assert recovered["asset_output"]["version"] == 1 and recovered["review"]
    assert reopened.get(job.id).request_authorization is None
    assert len(e.calls) == len(assets(e)) == 1


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_original_review_commit_to_asset_gap_converges_on_existing_read(model_rig, monkeypatch, decision):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    original = e.assets.review_text_result
    def crash(*args, **kwargs):
        raise OSError("synthetic review projection failure")
    monkeypatch.setattr(e.assets, "review_text_result", crash)
    with pytest.raises(OSError):
        action(e, waiting, decision, node_id=waiting["review"]["node_id"],
            reviewed_output_digest=waiting["review"]["output_digest"])
    assert raw(e, sent)["status"] == ("SUCCEEDED" if decision == "approve" else "REJECTED")
    assert assets(e)[0]["_text_result_review"]["status"] == "DRAFT"
    monkeypatch.setattr(e.assets, "review_text_result", original)
    recovered = current(e, sent)
    assert recovered["asset_output"]["state"] == ("APPROVED" if decision == "approve" else "REJECTED")
    assert recovered["asset_output"]["version"] == 2
    assert current(e, sent)["asset_output"] == recovered["asset_output"]
    if decision == "reject":
        assert recovered["review"] is None and all(s["output"] is None for s in recovered["node_states"].values())
    assert len(e.calls) == len(assets(e)) == 1


def test_archive_corruption_masks_result_and_cannot_be_approved(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    saved = assets(e)[0]
    e.assets._bin_path(saved["id"]).write_bytes(b"corrupted")
    denied = current(e, sent)
    assert denied["stale"] and denied["review"] is None and denied["asset_output"]["state"] == "INCOMPLETE"
    with pytest.raises((ValueError, StaleSourceError)):
        approve(e, waiting)
    assert raw(e, sent)["status"] == "WAITING_APPROVAL"
    assert assets(e)[0]["version"] == 1 and len(e.calls) == 1


def test_stale_review_cas_cannot_advance_asset_projection(model_rig, monkeypatch):
    from app.services.v1_capability_service import CapabilityVersionConflict
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    with pytest.raises(CapabilityVersionConflict):
        approve(e, {**waiting, "version": waiting["version"] - 1})
    assert assets(e)[0]["version"] == 1
    assert approve(e, waiting)["asset_output"]["version"] == 2


def test_revocation_at_archive_commit_stops_without_publishing_or_replay(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    original = e.assets.create_text_result
    def revoke(*args, **kwargs):
        e.active = False
        return original(*args, **kwargs)
    monkeypatch.setattr(e.assets, "create_text_result", revoke)
    with pytest.raises(PermissionError):
        current(e, sent)
    assert not assets(e) and len(e.calls) == 1
    assert e.persistence.get(job.id)["output"] == job.output


def test_private_text_assets_never_appear_in_unscoped_or_manual_media_views(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    aid = waiting["asset_output"]["asset_id"]
    assert e.assets.list(e.nid) == []
    assert e.service.list_assets(e.nid, e.scope) == {"items": []}
    with pytest.raises(FileNotFoundError):
        e.assets.get(aid)
    with e.service._asset_scope(e.nid, e.scope):
        with pytest.raises(FileNotFoundError):
            e.assets.get(aid, actor_id="another-actor")
    with pytest.raises(FileNotFoundError):
        e.graphs.get_run(e.nid, e.scope, "another-actor", sent["id"], e.guard)


def test_uncertain_terminal_accounting_is_not_a_successful_text_asset(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    job.terminal_hook_status = "MISSING_RECONCILIATION_REQUIRED"
    e.manager._persist(job)
    result = current(e, sent)
    assert result["asset_output"]["state"] == "INCOMPLETE" and result["review"] is None
    assert raw(e, sent)["status"] == "RUNNING"
    again = e.models.refresh(e.nid, e.scope, e.actor, sent["id"], {"expected_version": result["version"]}, e.guard)
    assert again["asset_output"]["state"] == "INCOMPLETE" and raw(e, sent)["status"] == "RUNNING"
    assert not assets(e) and len(e.calls) == 1


def test_provider_change_after_asset_validation_cannot_commit_review(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    original = e.models.text_assets.ensure
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        e.runtime.providers['mock'].delay_ms = 1
        return result
    monkeypatch.setattr(e.models.text_assets, 'ensure', changed)
    with pytest.raises(ValueError):
        approve(e, waiting)
    assert raw(e, sent)['status'] == 'WAITING_APPROVAL'
    assert assets(e)[0]['version'] == 1 and len(e.calls) == 1


def test_changed_graph_source_retains_job_but_cannot_archive_or_review(model_rig, monkeypatch):
    from test_v2_ai_execution_runtime import definition
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    graph = e.graphs.get(e.nid, e.scope, e.actor, sent['graph_id'])
    e.graphs.save(e.nid, e.scope, e.actor, graph['id'], {
        'expected_version': graph['version'], 'definition': definition(text='New author source')}, e.guard)
    failed = current(e, sent)
    assert failed['asset_output']['state'] == 'INCOMPLETE' and failed['review'] is None
    assert not assets(e) and len(e.calls) == 1
    assert e.persistence.get(job.id)['output'] == job.output


def test_cancel_after_draft_retains_private_asset_without_approval(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    cancelled = action(e, waiting, 'cancel')
    assert cancelled['status'] == 'CANCELLED'
    assert cancelled['asset_output']['state'] == 'NO_ACCEPTED_RESULT'
    assert cancelled['review'] is None and all(s['output'] is None for s in cancelled['node_states'].values())
    assert current(e, sent)['asset_output']['state'] == 'NO_ACCEPTED_RESULT'
    saved = assets(e)
    assert len(saved) == len(e.calls) == 1 and saved[0]['version'] == 1
    assert saved[0]['_text_result_review']['status'] == 'DRAFT'


def test_late_output_after_archival_run_cancel_creates_no_asset(model_rig, monkeypatch):
    from test_v2_ai_execution_runtime import dispatch
    e = model_rig; entered, release = spy_transport(e, monkeypatch, blocked=True)
    sent = dispatch(e, preview(e, admit(e)), archive_result=True)
    job = e.manager.get(sent['model_runtime']['execution']['job_id'])
    try:
        assert entered.wait(3)
        cancelled = action(e, current(e, sent), 'cancel')
        assert cancelled['asset_output']['state'] == 'NO_ACCEPTED_RESULT'
    finally:
        release.set()
    wait_job(e, job)
    e.calls[0]['worker'].join(8)
    assert not e.calls[0]['worker'].is_alive()
    assert job.status == 'CANCELLED' and job.output == ''
    assert current(e, sent)['asset_output']['state'] == 'NO_ACCEPTED_RESULT'
    assert not assets(e) and len(e.calls) == 1


def test_concurrent_read_reconciliation_creates_one_asset_and_never_replays(model_rig, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: current(e, sent), range(2)))
    assert any(row['asset_output']['state'] == 'DRAFT' for row in results)
    assert all(row['asset_output']['state'] in {'DRAFT', 'INCOMPLETE'} for row in results)
    saved = assets(e)
    assert len(saved) == len(e.calls) == len(owned_jobs(e)) == 1
    assert saved[0]['version'] == 1 and raw(e, sent)['status'] == 'WAITING_APPROVAL'


def test_review_asset_commit_rechecks_current_registration_and_preserves_draft(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    original = e.assets.review_text_result
    def changed(*args, **kwargs):
        e.runtime.providers['mock'].delay_ms = 1
        return original(*args, **kwargs)
    monkeypatch.setattr(e.assets, 'review_text_result', changed)
    with pytest.raises(ValueError):
        approve(e, waiting)
    # Original review is already durable; its projection cannot claim success.
    assert raw(e, sent)['status'] == 'SUCCEEDED'
    assert assets(e)[0]['version'] == 1 and assets(e)[0]['_text_result_review']['status'] == 'DRAFT'
    failed = current(e, sent)
    assert failed['asset_output']['state'] == 'INCOMPLETE' and failed['review'] is None
    assert len(e.calls) == 1


@pytest.mark.parametrize('reviewed', [False, True])
def test_original_terminal_notification_does_not_change_archived_origin(model_rig, monkeypatch, reviewed):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    first = current(e, sent)
    if reviewed:
        first = approve(e, first)
    ledger = e.broker.get(e.nid, e.scope, e.broker.LEDGER, raw(e, sent)['model_execution']['reservation_id'])
    assert first['asset_output']['source']['produced_at'] == ledger['updated_at']
    assert ledger['status'] == 'SETTLED' and ledger['job_status'] == 'COMPLETED'
    old = job.updated_at
    # This is the original owner's real notification/persistence method, which
    # follows completed terminal accounting in _run. No clock or output is faked.
    e.manager._emit(job)
    assert job.updated_at != old and e.persistence.get(job.id)['updated_at'] == job.updated_at
    again = current(e, sent)
    assert again['asset_output'] == first['asset_output'] and not again['stale']
    assert len(e.calls) == len(assets(e)) == 1
    assert again['asset_output']['version'] == (2 if reviewed else 1)


def test_settled_ledger_must_confirm_completed_job_before_archival(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    reservation = raw(e, sent)['model_execution']['reservation_id']
    with e.broker.store.transaction(e.nid, e.scope) as state:
        state['collections'][e.broker.LEDGER][reservation]['job_status'] = 'FAILED'
    result = current(e, sent)
    assert result['asset_output']['state'] == 'INCOMPLETE' and result['review'] is None
    assert not assets(e) and len(e.calls) == 1
