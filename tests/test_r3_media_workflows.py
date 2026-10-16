import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.media import (MediaService, MediaAdapterRegistry, MockImageWorkflowAdapter, OPERATIONS,
                                    AdapterDefinition, ImageWorkflowResult)
from app.experimental.media_api import create_media_router
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, branch_scope


def service(rig, registry=None):
    return MediaService(rig.store, rig.novels, rig.chapters, assets=rig.assets, screenplays=rig.screenplays, registry=registry)


def prepare(rig, instance=None):
    instance = instance or service(rig)
    brief = instance.create_cover(rig.nid, rig.scope, rig.actor, {"title": "Cover", "character_ids": ["alice"],
                                                                "chapter_ids": [rig.chapter["id"]]})
    task = instance.queue(rig.nid, rig.scope, rig.actor, {"brief_id": brief["id"], "expected_brief_version": brief["version"],
                                                       "adapter_id": "mock-image-v1", "candidate_count": 2})
    return instance, brief, task


def test_family_registry_does_not_infer_runnable_from_discovery():
    registry = MediaAdapterRegistry()
    definitions = registry.definitions()
    families = [r for r in definitions["items"] if r["state"] == "ADAPTER_REQUIRED"]
    assert len(families) == 8
    assert all(not r["runnable"] for r in families)
    assert {"start_end_frame", "chapter_audiobook", "cover_generation"} <= set(sum((list(v) for v in OPERATIONS.values()), []))
    assert next(r for r in definitions["items"] if r["adapter_id"] == "mock-image-v1")["state"] == "MOCK_ONLY"
    with pytest.raises(ValueError, match="ADAPTER_REQUIRED"):
        registry.resolve("qwen-image", "cover_generation")
    with pytest.raises(ValueError, match="OPERATION_UNSUPPORTED"):
        registry.resolve("mock-image-v1", "chapter_audiobook")


def test_cover_execution_compare_review_lineage_and_restart(rig):
    instance, brief, task = prepare(rig)
    body_before = rig.chapters.get(rig.chapter["id"])
    complete = instance.execute(rig.nid, rig.scope, rig.actor, task["id"], task["version"])
    assert complete["status"] == "SUCCEEDED"
    assert rig.assets.list(rig.nid) == []
    proposals = instance.proposals(rig.nid, rig.scope)
    assert len(proposals) == 2 and all(p["verification"] == "MOCK_ONLY" for p in proposals)
    assert all("content_base64" not in p for p in proposals)
    compared = instance.compare(rig.nid, rig.scope, [p["id"] for p in proposals])
    assert compared["inference_performed"] is False
    assert proposals[0]["content_sha256"] != proposals[1]["content_sha256"]
    reopened = MediaService(ExperimentalStore(rig.root, rig.backend, rig.store.database_url), rig.novels, rig.chapters,
                            rig.assets, rig.screenplays)
    approved = reopened.review(rig.nid, rig.scope, rig.actor, proposals[0]["id"], "approve", 1)
    assert approved["status"] == "APPROVED"
    asset = rig.assets.get(approved["asset_id"])
    assert asset["parameters"]["experimental_media_lineage"]["brief_id"] == brief["id"]
    assert asset["parameters"]["experimental_media_lineage"]["verification"] == "MOCK_ONLY"
    assert rig.assets.content(asset["id"]).startswith(b"\x89PNG")
    assert len(rig.assets.list(rig.nid)) == 1
    assert rig.chapters.get(rig.chapter["id"]) == body_before
    with pytest.raises(CapabilityVersionConflict):
        reopened.review(rig.nid, rig.scope, rig.actor, proposals[0]["id"], "approve", 1)
    rejected = reopened.review(rig.nid, rig.scope, rig.actor, proposals[1]["id"], "reject", 1)
    reopened.review(rig.nid, rig.scope, rig.actor, rejected["id"], "reopen", rejected["version"])


def test_media_stale_source_cannot_be_approved_or_run(rig):
    instance, _, task = prepare(rig)
    instance.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
    proposal = instance.proposals(rig.nid, rig.scope)[0]
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "Changed source"})
    assert instance.proposals(rig.nid, rig.scope)[0]["stale"] is True
    with pytest.raises(StaleSourceError):
        instance.review(rig.nid, rig.scope, rig.actor, proposal["id"], "approve", 1)
    assert rig.assets.list(rig.nid) == []


def test_media_branch_and_version_fences(rig):
    instance, brief, task = prepare(rig)
    with pytest.raises(FileNotFoundError):
        instance.get(rig.nid, branch_scope(rig), instance.TASKS, task["id"])
    with pytest.raises(StaleSourceError, match="BRANCH_SOURCE_ADAPTER_REQUIRED"):
        instance.create_cover(rig.nid, branch_scope(rig), rig.actor, {"title": "Branch", "chapter_ids": [rig.chapter["id"]]})
    instance.update_cover(rig.nid, rig.scope, rig.actor, brief["id"], 1, {"title": "Edited cover"})
    with pytest.raises(StaleSourceError, match="BRIEF_SOURCE_CHANGED"):
        instance.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)


def test_storyboard_binds_exact_shot_and_fences_changes(rig):
    instance = service(rig)
    screenplay = rig.screenplays.create(rig.nid)
    screenplay = rig.screenplays.approve(rig.nid, screenplay["id"], screenplay["edit_version"])
    screenplay = rig.screenplays.plan_shots(rig.nid, screenplay["id"], screenplay["edit_version"])
    shot = screenplay["shots"][0]
    brief = instance.create_storyboard(rig.nid, rig.scope, rig.actor, {"screenplay_id": screenplay["id"], "shot_id": shot["id"],
        "expected_screenplay_version": screenplay["edit_version"]})
    assert brief["shot_snapshot"] == shot
    task = instance.queue(rig.nid, rig.scope, rig.actor, {"brief_id": brief["id"], "expected_brief_version": 1, "adapter_id": "mock-image-v1"})
    instance.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
    proposal = instance.proposals(rig.nid, rig.scope)[0]
    approved = instance.review(rig.nid, rig.scope, rig.actor, proposal["id"], "approve", 1)
    assert approved["lineage"]["shot_id"] == shot["id"]
    assert approved["lineage"]["screenplay_id"] == screenplay["id"]
    with pytest.raises(FileNotFoundError):
        instance.create_storyboard(rig.nid, branch_scope(rig), rig.actor, {"screenplay_id": screenplay["id"], "shot_id": shot["id"],
            "expected_screenplay_version": screenplay["edit_version"]})


def test_media_cancel_late_callback_and_restart_recovery(rig):
    entered, release = Event(), Event()
    class Slow(MockImageWorkflowAdapter):
        def generate(self, request):
            entered.set()
            assert release.wait(10)
            return super().generate(request)
    registry = MediaAdapterRegistry(include_mock=False); registry.register(Slow())
    instance, _, task = prepare(rig, service(rig, registry))
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(instance.execute, rig.nid, rig.scope, rig.actor, task["id"], 1)
        assert entered.wait(10)
        running = instance.get(rig.nid, rig.scope, instance.TASKS, task["id"])
        cancelled = instance.transition(rig.nid, rig.scope, rig.actor, task["id"], "cancel", running["version"])
        release.set()
        assert pending.result(timeout=20)["status"] == "CANCELLED"
    assert instance.proposals(rig.nid, rig.scope) == []
    retried = instance.transition(rig.nid, rig.scope, rig.actor, task["id"], "retry", cancelled["version"])
    with rig.store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"][instance.TASKS][task["id"]].update(status="RUNNING", execution_token="old-process-token")
    assert instance.tasks(rig.nid, rig.scope)[0]["recoverable"] is True
    recovered = instance.transition(rig.nid, rig.scope, rig.actor, task["id"], "retry", retried["version"])
    assert recovered["status"] == "QUEUED"


def test_media_remote_guard_does_not_dispatch(rig):
    called = []
    class Remote(MockImageWorkflowAdapter):
        definition = MockImageWorkflowAdapter.definition.model_copy(update={"adapter_id": "remote-fixture", "local": False})
        def generate(self, request):
            called.append(request)
            return super().generate(request)
    registry = MediaAdapterRegistry(include_mock=False); registry.register(Remote())
    instance = service(rig, registry)
    brief = instance.create_cover(rig.nid, rig.scope, rig.actor, {"title": "Private"})
    task = instance.queue(rig.nid, rig.scope, rig.actor, {"brief_id": brief["id"], "expected_brief_version": 1, "adapter_id": "remote-fixture"})
    with pytest.raises(ValueError, match="EGRESS_AUTHORITY_REQUIRED"):
        instance.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
    assert not called
    assert instance.tasks(rig.nid, rig.scope)[0]["status"] == "FAILED"


def test_media_api_flag_authorization_review_and_contract(rig):
    instance = service(rig)
    flags = {"media_adapter_registry", "cover_storyboard_generation"}
    permissions = []
    def authorize(nid, token, branch, permission):
        if token != "valid":
            raise HTTPException(403, "denied")
        permissions.append(permission)
        return rig.actor, rig.scope if branch is None else branch_scope(rig, branch)
    def enabled(flag):
        if flag not in flags:
            raise HTTPException(404, "disabled")
    app = FastAPI(); app.include_router(create_media_router(instance, authorize, enabled))
    client = TestClient(app); base = f"/novels/{rig.nid}/experimental/media"
    assert client.get(base + "/adapters").status_code == 403
    headers = {"X-Session-Token": "valid"}
    assert client.get(base + "/adapters", headers=headers).status_code == 200
    brief = client.post(base + "/cover-briefs", headers=headers, json={"title": "API"}).json()
    task = client.post(base + "/tasks", headers=headers, json={"brief_id": brief["id"], "expected_brief_version": 1, "adapter_id": "mock-image-v1"}).json()
    assert client.post(base + f"/tasks/{task['id']}/execute", headers=headers, json={"expected_version": 1}).status_code == 200
    proposal = client.get(base + "/proposals", headers=headers).json()["items"][0]
    assert client.get(base + f"/proposals/{proposal['id']}/preview", headers=headers).headers["content-type"] == "image/png"
    assert client.post(base + f"/proposals/{proposal['id']}/reject", headers=headers, json={"expected_version": 1}).status_code == 200
    assert permissions[-1] == "domain.review"
    assert client.post(base + f"/proposals/{proposal['id']}/reopen", headers=headers, json={"expected_version": 1}).status_code == 409
    flags.remove("cover_storyboard_generation")
    assert client.get(base + "/proposals", headers=headers).status_code == 404


def test_media_promotion_checkpoint_blocks_reject_and_recovers(rig, monkeypatch):
    instance, _, task = prepare(rig)
    instance.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
    proposal = instance.proposals(rig.nid, rig.scope)[0]
    assert instance.list_review_items(rig.nid, rig.scope)[0]["allowed_actions"] == ["approve", "reject"]
    original = rig.assets.update_metadata
    def crash_after_commit(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated crash after asset commit")
    monkeypatch.setattr(rig.assets, "update_metadata", crash_after_commit)
    with pytest.raises(RuntimeError, match="simulated crash"):
        instance.review(rig.nid, rig.scope, rig.actor, proposal["id"], "approve", 1)
    pending = instance.get(rig.nid, rig.scope, instance.PROPOSALS, proposal["id"])
    assert pending["status"] == "APPROVING"
    with pytest.raises(ValueError, match="TRANSITION_INVALID"):
        instance.review(rig.nid, rig.scope, rig.actor, pending["id"], "reject", pending["version"])
    entry = next(r for r in instance.list_review_items(rig.nid, rig.scope) if r["id"] == pending["id"])
    assert entry["recovery_required"] is True and entry["allowed_actions"] == ["approve"]
    monkeypatch.setattr(rig.assets, "update_metadata", original)
    reopened = MediaService(ExperimentalStore(rig.root, rig.backend, rig.store.database_url), rig.novels, rig.chapters, rig.assets, rig.screenplays)
    approved = reopened.review(rig.nid, rig.scope, rig.actor, pending["id"], "approve", pending["version"])
    assert approved["status"] == "APPROVED" and len(rig.assets.list(rig.nid)) == 1


def test_storyboard_old_scene_cannot_launder_new_chapter_lineage(rig):
    instance = service(rig)
    screenplay = rig.screenplays.create(rig.nid)
    screenplay = rig.screenplays.approve(rig.nid, screenplay["id"], screenplay["edit_version"])
    screenplay = rig.screenplays.plan_shots(rig.nid, screenplay["id"], screenplay["edit_version"])
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "Completely new chapter"})
    with pytest.raises(StaleSourceError, match="SCENE_SOURCE_VERSION_CHANGED"):
        instance.create_storyboard(rig.nid, rig.scope, rig.actor, {"screenplay_id": screenplay["id"],
            "shot_id": screenplay["shots"][0]["id"], "expected_screenplay_version": screenplay["edit_version"]})


def test_media_operation_contract_validates_specific_inputs():
    from app.experimental.media import MediaOperationInput
    from pydantic import ValidationError
    valid = [
        {"operation": "text_to_image", "prompt": "Cover"},
        {"operation": "image_edit", "prompt": "Edit", "reference_asset_ids": ["image"]},
        {"operation": "multi_reference_image", "prompt": "Compose", "reference_asset_ids": ["a", "b"]},
        {"operation": "character_reference_image", "character_id": "character", "reference_asset_ids": ["a"]},
        {"operation": "scene_reference_image", "scene_id": "scene", "reference_asset_ids": ["a"]},
        {"operation": "cover_generation", "brief_id": "cover"},
        {"operation": "storyboard_card_generation", "brief_id": "card", "shot_ids": ["shot"]},
        {"operation": "text_to_video", "prompt": "Video"},
        {"operation": "image_to_video", "reference_asset_ids": ["a"]},
        {"operation": "start_end_frame", "start_frame_asset_id": "a", "end_frame_asset_id": "b"},
        {"operation": "continuation", "previous_clip_asset_id": "clip"},
        {"operation": "storyboard_to_clip", "shot_ids": ["shot"]},
        {"operation": "tts", "prompt": "Hello", "profile_id": "voice"},
        {"operation": "character_voice", "prompt": "Hello", "profile_id": "voice", "character_id": "character"},
        {"operation": "emotion_tts", "prompt": "Hello", "profile_id": "voice", "emotion": "joy"},
        {"operation": "dialogue_sequence", "segment_ids": ["segment"]},
        {"operation": "chapter_audiobook", "chapter_id": "chapter", "segment_ids": ["segment"]},
    ]
    assert len(valid) == sum(len(v) for v in OPERATIONS.values())
    for value in valid:
        assert MediaOperationInput.model_validate(value).operation == value["operation"]
        with pytest.raises(ValidationError):
            MediaOperationInput.model_validate({"operation": value["operation"]})


def test_cover_character_source_changes_require_new_review(rig):
    instance, _, task = prepare(rig)
    instance.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
    proposal = instance.proposals(rig.nid, rig.scope)[0]
    rig.novels.upsert_character(rig.nid, "alice", {"name": "Alice", "personality": "Changed"})
    with pytest.raises(StaleSourceError, match="CHARACTER_SOURCE_CHANGED"):
        instance.review(rig.nid, rig.scope, rig.actor, proposal["id"], "approve", 1)
    assert rig.assets.list(rig.nid) == []
