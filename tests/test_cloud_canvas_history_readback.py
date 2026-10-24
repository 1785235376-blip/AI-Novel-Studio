"""Read-only original-owner evidence for two synthetic approved source records.

These File/API cases do not restore a browser binding or perform a review.
Approval markers are explicit fixture state. No accept, provider or media
inspection is called; the reused fixture enforces those boundaries.
"""
import hashlib

import pytest

from app import api as api_module
from app.identity import IdentityStatus
from app.services.asset_library_service import AssetLibraryService
from app.services.image_job_service import ImageJobService
from test_cloud_canvas_review_readback import paths, review_readback, seed_approved
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only


def seed_two_sources(e, *, actor=None, branch=None):
    previous = seed_approved(e, actor=actor, branch=branch, request_id="synthetic-history-previous")
    current = seed_approved(e, actor=actor, branch=branch, request_id="synthetic-history-current")
    assert previous[0]["id"] != current[0]["id"]
    assert previous[1]["id"] != current[1]["id"]
    return previous, current


def read_jobs(e, headers=None):
    response = e.client.get(f"/api/novels/{e.nid}/image-jobs", headers=headers)
    assert response.status_code == 200, response.text
    return {row["id"]: row for row in response.json()["items"]}


def read_asset(e, asset, headers=None):
    _, metadata_path, download_path = paths(e, asset)
    metadata = e.client.get(metadata_path, headers=headers)
    assert metadata.status_code == 200, metadata.text
    download = e.client.get(download_path, headers=headers)
    assert download.status_code == 200, download.text
    value = metadata.json()
    assert download.headers["x-asset-sha256"] == value["sha256"]
    assert hashlib.sha256(download.content).hexdigest() == value["sha256"]
    return value, download.content


def test_previous_exact_asset_pin_remains_readable_after_two_sources_and_owner_reopen(review_readback, monkeypatch):
    e = review_readback
    (old_job, old_asset), (current_job, current_asset) = seed_two_sources(e)
    before_jobs = read_jobs(e)
    old_metadata, old_bytes = read_asset(e, old_asset)
    current_metadata, current_bytes = read_asset(e, current_asset)
    # Identical known fixture bytes deliberately prove that a digest alone
    # cannot distinguish the historical asset or its source job.
    assert old_metadata["sha256"] == current_metadata["sha256"]
    assert old_metadata["id"] != current_metadata["id"]
    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.rig.root / "synthetic-review-jobs"))
    monkeypatch.setattr(api_module, "asset_library_service", AssetLibraryService(e.rig.root))
    assert read_jobs(e) == before_jobs
    for job, asset, pinned, content in ((old_job, old_asset, old_metadata, old_bytes),
                                         (current_job, current_asset, current_metadata, current_bytes)):
        fresh, fresh_content = read_asset(e, asset)
        assert (fresh["id"], fresh["version"], fresh["sha256"]) == (pinned["id"], pinned["version"], pinned["sha256"])
        assert fresh["source_job_id"] == job["id"]
        assert before_jobs[job["id"]]["asset_id"] == fresh["id"]
        assert fresh_content == content


def test_historical_asset_metadata_change_invalidates_its_old_pin_without_changing_current_source(review_readback):
    e = review_readback
    (old_job, old_asset), (current_job, current_asset) = seed_two_sources(e)
    before_jobs = read_jobs(e)
    old_metadata, old_bytes = read_asset(e, old_asset)
    current_before = read_asset(e, current_asset)
    e.assets.update_metadata(old_asset["id"], {"source_job_id": current_job["id"]}, expected_version=old_metadata["version"])
    changed, changed_bytes = read_asset(e, old_asset)
    assert changed["id"] == old_metadata["id"] and changed["sha256"] == old_metadata["sha256"]
    assert changed["version"] == old_metadata["version"] + 1
    assert changed["source_job_id"] != old_job["id"]
    assert changed_bytes == old_bytes
    assert read_jobs(e) == before_jobs
    assert read_asset(e, current_asset) == current_before


def test_historical_asset_delete_and_legal_restore_cannot_reuse_old_version_pin(review_readback):
    e = review_readback
    (old_job, old_asset), (_, current_asset) = seed_two_sources(e)
    before_jobs = read_jobs(e)
    old_metadata, old_bytes = read_asset(e, old_asset)
    current_before = read_asset(e, current_asset)
    _, metadata_path, download_path = paths(e, old_asset)
    e.assets.delete(old_asset["id"])
    for path in (metadata_path, download_path):
        assert e.client.get(path).status_code == 404
    assert read_jobs(e) == before_jobs
    assert read_asset(e, current_asset) == current_before
    e.assets.restore(old_asset["id"])
    restored, restored_bytes = read_asset(e, old_asset)
    assert restored["id"] == old_metadata["id"] and restored["sha256"] == old_metadata["sha256"]
    assert restored["source_job_id"] == old_job["id"]
    assert restored["version"] == old_metadata["version"] + 2
    assert restored_bytes == old_bytes
    assert read_jobs(e) == before_jobs
    assert read_asset(e, current_asset) == current_before


@pytest.mark.parametrize("retirement", ["membership", "read_permission"])
def test_history_source_reads_recheck_original_authority_after_successful_read(review_readback, retirement):
    e = review_readback
    scope, headers = shared_scope(e.rig)
    (old_job, old_asset), (current_job, current_asset) = seed_two_sources(e, actor="reader", branch=scope["branch_id"])
    before_jobs = read_jobs(e, headers)
    assert set(before_jobs) == {old_job["id"], current_job["id"]}
    for asset in (old_asset, current_asset):
        read_asset(e, asset, headers)
    if retirement == "membership":
        e.rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    else:
        e.rig.grants.revoke_permission("query-read", "fixture")
    jobs_path = paths(e, old_asset)[0]
    routes = [jobs_path]
    for asset in (old_asset, current_asset):
        routes.extend(paths(e, asset)[1:])
    # Each old/current request is fresh. Previously read IDs/bytes cannot
    # stand in for the current resolver, membership or permission decision.
    for route in routes:
        response = e.client.get(route, headers=headers)
        assert response.status_code == 403, response.text
        assert all(value["id"] not in response.text for value in (old_job, current_job, old_asset, current_asset))
        assert "sha256" not in response.text and "items" not in response.json()
