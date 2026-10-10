"""Current mounted aliases share automatic archival and original review authority."""
from copy import deepcopy
from hashlib import sha256

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_creative_graph_api import graph_client
from test_v2_ai_execution_api import ai_client, ready, body
from test_v2_ai_execution_runtime import spy_transport, wait_job, owned_jobs


def test_existing_dispatch_read_review_ui_contract_archives_without_extra_action(ai_client, monkeypatch):
    e = ai_client; spy_transport(e, monkeypatch)
    before_chapter = deepcopy(e.chapters.get(e.chapter["id"]))
    before_canon = deepcopy(e.canon.list(e.nid))
    capabilities = checked(e.client.get(e.graph_base + "/model-capabilities", headers=e.headers))
    assert capabilities["result_storage"] == {"contract": "creative-graph-text-asset/1", "available": True,
        "owner": "AssetLibraryService", "actor_private": True, "automatic_model_retry": False}
    row, path = ready(e)
    dispatched = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json={**body(row), "archive_result": True}))
    assert dispatched["asset_output"]["state"] == "PENDING"
    job = e.manager.get(dispatched["model_runtime"]["execution"]["job_id"])
    wait_job(e, job); e.calls[-1]["worker"].join(8)
    assert not e.calls[-1]["worker"].is_alive()
    response = e.client.get(path, headers=e.headers)
    assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"
    waiting = checked(response)
    assert waiting["asset_output"]["state"] == "DRAFT" and waiting["asset_output"]["version"] == 1
    assert waiting["review"]["draft"]["origin"] == "MODEL_PROPOSAL" and not waiting["applied"]
    assert checked(e.client.get(e.studio_base + "/assets", headers=e.headers))["items"] == []
    done = checked(e.client.post(path + "/approve", headers=e.headers, json={"expected_version": waiting["version"],
        "node_id": waiting["review"]["node_id"], "reviewed_output_digest": waiting["review"]["output_digest"]}))
    assert done["asset_output"]["state"] == "APPROVED" and done["asset_output"]["version"] == 2
    assert not done["applied"] and done["reviewed"]
    assert checked(e.client.get(path, headers=e.headers))["asset_output"] == done["asset_output"]
    assert e.chapters.get(e.chapter["id"]) == before_chapter and e.canon.list(e.nid) == before_canon
    assert len(e.calls) == len(owned_jobs(e)) == 1
    e.sessions.revoke(e.host)
    denied = e.client.get(path, headers=e.headers)
    assert denied.status_code == 401
    assert done["asset_output"]["asset_id"] not in denied.text and job.output not in denied.text


@pytest.mark.parametrize("value", ["true", 1, None, {}, []])
def test_archival_consent_requires_an_actual_boolean(ai_client, value):
    e = ai_client
    row, path = ready(e)
    response = e.client.post(path + "/model/dispatch", headers=e.headers, json={**body(row), "archive_result": value})
    assert response.status_code == 422 and not owned_jobs(e)


def test_archive_failure_response_masks_data_then_original_refresh_recovers(ai_client, monkeypatch):
    e = ai_client; spy_transport(e, monkeypatch)
    row, path = ready(e)
    dispatched = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json={**body(row), "archive_result": True}))
    job = e.manager.get(dispatched["model_runtime"]["execution"]["job_id"])
    wait_job(e, job); e.calls[-1]["worker"].join(8)
    assert not e.calls[-1]["worker"].is_alive()
    original = e.assets.create_text_result
    def unavailable(*args, **kwargs):
        raise OSError("synthetic private storage detail")
    monkeypatch.setattr(e.assets, "create_text_result", unavailable)
    response = e.client.get(path, headers=e.headers)
    failed = checked(response)
    assert failed["asset_output"]["state"] == "INCOMPLETE" and failed["stale"] and failed["review"] is None
    assert job.output not in response.text and "synthetic private storage detail" not in response.text
    monkeypatch.setattr(e.assets, "create_text_result", original)
    recovered = checked(e.client.post(path + "/model/refresh", headers=e.headers, json={"expected_version": failed["version"]}))
    assert recovered["asset_output"]["state"] == "DRAFT" and len(e.calls) == 1


def test_existing_manual_refresh_stays_current_across_completion_then_returns_one_asset(ai_client, monkeypatch):
    e = ai_client; entered, release = spy_transport(e, monkeypatch, blocked=True)
    before_chapter, before_canon = deepcopy(e.chapters.get(e.chapter["id"])), deepcopy(e.canon.list(e.nid))
    row, path = ready(e)
    sent = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json={**body(row), "archive_result": True}))
    job = e.manager.get(sent["model_runtime"]["execution"]["job_id"])
    def refresh(value):
        response = e.client.post(path + "/model/refresh", headers=e.headers, json={"expected_version": value["version"]})
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        return checked(response)
    try:
        assert entered.wait(3)
        pending = refresh(sent)
        assert pending["asset_output"]["state"] == "PENDING" and not pending["stale"]
        original = e.models._refresh
        def completed_after_precheck(*args, **kwargs):
            assert job.status == "GENERATING"
            release.set(); e.calls[0]["worker"].join(8)
            assert not e.calls[0]["worker"].is_alive()
            assert job.status == job.terminal_hook_status == "COMPLETED"
            return original(*args, **kwargs)
        with monkeypatch.context() as boundary:
            boundary.setattr(e.models, "_refresh", completed_after_precheck)
            pending = refresh(pending)
        assert pending["status"] == "RUNNING" and not pending["stale"]
        assert pending["review"] is None and pending["node_states"]["Generate"]["output"] is None
        assert pending["asset_output"] == sent["asset_output"]
    finally:
        release.set(); e.calls[0]["worker"].join(8)
        assert not e.calls[0]["worker"].is_alive()
    waiting = refresh(pending)
    assert waiting["status"] == "WAITING_APPROVAL" and not waiting["stale"]
    assert waiting["review"]["draft"] == {"text": job.output, "origin": "MODEL_PROPOSAL"}
    receipt = waiting["asset_output"]
    assert receipt["state"] == "DRAFT" and receipt["version"] == 1 and receipt["asset_id"]
    assert receipt["source"]["run_id"] == sent["id"] and receipt["source"]["job_id"] == job.id
    assert receipt["size"] == len(job.output.encode()) and receipt["sha256"] == sha256(job.output.encode()).hexdigest()
    assert refresh(waiting) == waiting
    assert len(e.calls) == len(owned_jobs(e)) == 1
    assert e.chapters.get(e.chapter["id"]) == before_chapter and e.canon.list(e.nid) == before_canon
