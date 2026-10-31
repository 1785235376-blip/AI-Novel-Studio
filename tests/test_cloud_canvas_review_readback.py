"""Original File/API observations for an explicitly synthetic approved candidate.

Approval is fixture setup, never a claimed review transition. Only existing GET
routes are exercised; no accept, execution, provider, fetch or media inspection.
"""
import base64
from copy import deepcopy
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import api as api_module, dependencies
from app.asset_providers import AssetProviderRegistry
from app.identity import IdentityStatus
from app.repository import now
from app.services import image_job_service as image_job_module
from app.services.image_job_service import ImageJobService
from test_cloud_canvas_candidate_protocol import SYNTHETIC_PNG_B64
from test_cloud_canvas_image_queue import queue_command
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def review_readback(rig, monkeypatch):
    owner = ImageJobService(rig.root / "synthetic-review-jobs")
    registry = AssetProviderRegistry()
    forbidden = []
    for target, name in ((registry, "get"), (ImageJobService, "execute"), (ImageJobService, "accept"),
                         (image_job_module, "inspect_image"), (image_job_module, "fetch_media_bytes")):
        sentinel = Mock(side_effect=AssertionError("Readback must not invoke " + name))
        monkeypatch.setattr(target, name, sentinel)
        forbidden.append(sentinel)
    monkeypatch.setattr(api_module, "image_job_service", owner)
    monkeypatch.setattr(api_module, "asset_library_service", rig.assets)
    monkeypatch.setattr(dependencies, "asset_provider_registry", registry)
    e = SimpleNamespace(rig=rig, owner=owner, client=rig.client, nid=rig.nid, assets=rig.assets)
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def seed_approved(e, *, actor=None, branch=None, request_id="synthetic-reviewed-source"):
    """Persist known fixture state without dispatching or accepting anything."""
    owner = e.owner.for_actor(actor) if actor else e.owner
    job = owner.create(e.nid, branch, queue_command(e.nid), request_id)
    asset = e.assets.create(e.nid, "synthetic-reviewed-source.png", SYNTHETIC_PNG_B64,
                            "image/png", "image", branch_id=branch)
    stamp = now()
    asset = e.assets.update_metadata(asset["id"], {
        "source_job_id": job["id"], "provider_id": job["provider_id"], "model_id": job["model_id"],
        "parameters": deepcopy(job["parameters"]), "approved_at": stamp,
    }, branch_id=branch)

    def persist(rows):
        current = owner._find(rows, job["id"])
        current.update(status="SUCCEEDED", attempt=1, approval_status="APPROVED", asset_id=asset["id"],
                       approved_at=stamp, updated_at=stamp, asset_uri="https://unused.invalid/synthetic-result")
        return current

    return owner._mutate(e.nid, branch, persist), asset


def paths(e, asset):
    return (f"/api/novels/{e.nid}/image-jobs",
            f"/api/assets/{asset['id']}?novel_id={e.nid}",
            f"/api/assets/{asset['id']}/download?novel_id={e.nid}")


def test_real_asset_version_digest_and_source_are_read_without_changing_original_files(review_readback):
    e = review_readback
    job, asset = seed_approved(e)
    jobs_path, metadata_path, download_path = paths(e, asset)
    tracked = [e.owner._path(e.nid), e.assets._meta_path(asset["id"]), e.assets._bin_path(asset["id"])]
    before = {str(path): path.read_bytes() for path in tracked}
    response = e.client.get(jobs_path)
    assert response.status_code == 200 and set(response.json()) == {"items"}
    observed = response.json()["items"][0]
    assert observed["id"] == job["id"] and observed["asset_id"] == asset["id"]
    assert observed["branch_id"] is None and observed["owner_actor_id"] is None
    assert observed["status"] == "SUCCEEDED" and observed["approval_status"] == "APPROVED"
    assert "version" not in observed and "output_digest" not in observed
    metadata = e.client.get(metadata_path)
    assert metadata.status_code == 200
    value = metadata.json()
    original = base64.b64decode(SYNTHETIC_PNG_B64, validate=True)
    assert value["version"] == asset["version"] == 2
    assert value["sha256"] == hashlib.sha256(original).hexdigest()
    assert value["source_job_id"] == job["id"] and value["branch_id"] is None
    assert value["provider_id"] == job["provider_id"] and value["model_id"] == job["model_id"]
    download = e.client.get(download_path)
    assert download.status_code == 200 and download.content == original
    assert download.headers["x-asset-sha256"] == value["sha256"]
    assert {str(path): path.read_bytes() for path in tracked} == before


@pytest.mark.parametrize("changed", [
    {"source_job_id": "another-source-job"}, {"provider_id": "another-provider"},
    {"model_id": "another-model"}, {"parameters": {"steps": 12}},
])
def test_asset_provenance_changes_while_original_candidate_observation_can_remain_unchanged(review_readback, changed):
    e = review_readback
    _, asset = seed_approved(e)
    jobs_path, metadata_path, download_path = paths(e, asset)
    before_job = e.client.get(jobs_path).json()
    before_asset = e.client.get(metadata_path).json()
    e.assets.update_metadata(asset["id"], changed, expected_version=before_asset["version"])
    after_asset = e.client.get(metadata_path)
    assert after_asset.status_code == 200
    assert after_asset.json()["version"] == before_asset["version"] + 1
    assert after_asset.json()["sha256"] == before_asset["sha256"]
    assert all(after_asset.json()[key] == value for key, value in changed.items())
    assert e.client.get(jobs_path).json() == before_job
    assert e.client.get(download_path).status_code == 200


def test_deleted_asset_refuses_both_original_reads_even_when_job_remains_marked_approved(review_readback):
    e = review_readback
    _, asset = seed_approved(e)
    jobs_path, metadata_path, download_path = paths(e, asset)
    before_job = e.client.get(jobs_path).json()
    e.assets.delete(asset["id"])
    assert e.client.get(jobs_path).json() == before_job
    for path in (metadata_path, download_path):
        response = e.client.get(path)
        assert response.status_code == 404 and response.json()["detail"] == "asset not found"
        assert asset["id"] not in response.text


def test_legal_restore_changes_asset_version_without_rewriting_candidate_or_original_content(review_readback):
    e = review_readback
    _, asset = seed_approved(e)
    jobs_path, metadata_path, download_path = paths(e, asset)
    before_job = e.client.get(jobs_path).json()
    before_content = e.client.get(download_path).content
    e.assets.delete(asset["id"])
    e.assets.restore(asset["id"])
    metadata = e.client.get(metadata_path)
    assert metadata.status_code == 200
    assert metadata.json()["version"] == asset["version"] + 2
    assert metadata.json()["sha256"] == asset["sha256"]
    assert e.client.get(download_path).content == before_content
    assert e.client.get(jobs_path).json() == before_job


def test_different_legal_asset_content_has_a_new_identity_and_invalidates_candidate_reference(review_readback):
    e = review_readback
    job, asset = seed_approved(e)
    jobs_path, _, _ = paths(e, asset)
    before_job = e.client.get(jobs_path).json()["items"][0]
    # The generic Asset owner supports opaque upload bytes, not replacing an
    # existing ID's binary. This is fixture content, never a media-validity claim.
    payload = b"distinct synthetic file content; not generated or reviewed media"
    replacement = e.assets.create(e.nid, "synthetic-replacement.bin", base64.b64encode(payload).decode(),
                                   "application/octet-stream", "image")
    replacement = e.assets.update_metadata(replacement["id"], {"source_job_id": job["id"]})

    def replace_fixture_reference(rows):
        current = e.owner._find(rows, job["id"])
        current.update(asset_id=replacement["id"], updated_at=now())
        return current

    e.owner._mutate(e.nid, None, replace_fixture_reference)
    after_job = e.client.get(jobs_path).json()["items"][0]
    assert after_job["asset_id"] != before_job["asset_id"]
    assert replacement["sha256"] != asset["sha256"]
    _, metadata_path, download_path = paths(e, replacement)
    assert e.client.get(metadata_path).json()["sha256"] == hashlib.sha256(payload).hexdigest()
    assert e.client.get(download_path).content == payload


def test_metadata_and_content_require_exact_project_and_metadata_requires_project_query(review_readback):
    e = review_readback
    _, asset = seed_approved(e)
    other = e.rig.project()
    for suffix in ("", "/download"):
        path = f"/api/assets/{asset['id']}{suffix}"
        assert e.client.get(path).status_code == 422
        response = e.client.get(path, params={"novel_id": other})
        assert response.status_code == 404 and response.json()["detail"] == "asset not found"


@pytest.mark.parametrize("case,status", [("missing_session", 401), ("invalid_session", 401),
    ("no_grant", 403), ("missing_branch", 400), ("revoked_membership", 403)])
def test_original_authority_is_checked_for_job_metadata_and_content_on_each_read(review_readback, case, status):
    e = review_readback
    scope, headers = shared_scope(e.rig)
    _, asset = seed_approved(e, actor="reader", branch=scope["branch_id"])
    routes = paths(e, asset)
    for path in routes:
        assert e.client.get(path, headers=headers).status_code == 200
    if case == "missing_session":
        headers = {"X-Branch-Id": scope["branch_id"]}
    elif case == "invalid_session":
        headers = {**headers, "X-Session-Token": "unknown-session"}
    elif case == "no_grant":
        headers = {**headers, "X-Session-Token": "token-no-grants"}
    elif case == "missing_branch":
        headers = {"X-Session-Token": "token-reader"}
    else:
        e.rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    for path in routes:
        response = e.client.get(path, headers=headers)
        assert response.status_code == status, response.text
        assert asset["id"] not in response.text and "sha256" not in response.text


def test_actor_private_job_and_shared_asset_branch_are_separate_original_contracts(review_readback):
    e = review_readback
    scope, headers = shared_scope(e.rig)
    visible, asset = seed_approved(e, actor="reader", branch=scope["branch_id"])
    hidden, _ = seed_approved(e, actor="another-actor", branch=scope["branch_id"], request_id="different-actor")
    jobs_path, metadata_path, download_path = paths(e, asset)
    rows = e.client.get(jobs_path, headers=headers).json()["items"]
    assert [row["id"] for row in rows] == [visible["id"]]
    assert rows[0]["owner_actor_id"] == "reader" and rows[0]["branch_id"] == scope["branch_id"]
    assert hidden["id"] not in str(rows)
    other_branch = {**headers, "X-Branch-Id": "query-branch-b"}
    assert e.client.get(jobs_path, headers=other_branch).json() == {"items": []}
    for path in (metadata_path, download_path):
        assert e.client.get(path, headers=other_branch).status_code == 404
    # A read-only grant is enough to GET; the response is not a write/review capability.
    assert e.client.get(metadata_path, headers=headers).status_code == 200
