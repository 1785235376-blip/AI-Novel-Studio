"""Synthetic, deterministic last-hop dispatch races. No network/model calls."""
import json
from types import SimpleNamespace as S

import pytest

from app.agents import agent_runner
from app.authorization import ModalityDomain
from app.config import settings
from app.identity import IdentityStatus
from app.model_runtime import TextGenerationResponse, TextModelNode, TextModelNodeOutput
from app.repositories.factory import create_repository_bundle
from app.services import ContextService
from app.services.agent_context_service import AgentContextService
from app.services.agent_job_service import AgentJobService
from app.services.audiobook_service import AudiobookError, AudiobookService
from app.services.image_job_service import ImageJobService
from app.source_privacy import content_digest, review_source_privacy
from test_phase6_agent_authorization import actor, authorization_stack
from test_r2_media_lifecycle import FixtureVoice, audio_setup


def reviewed_audio(tmp_path):
    object.__setattr__(settings, "novel_data", tmp_path)
    service, store, assets, chapter, _ = audio_setup(tmp_path)
    review_source_privacy(chapter, None, "author", "CLOUD_ALLOWED", chapter["version"], content_digest(chapter))
    job = service.queue("novel-a", chapter, {"provider_id": "synthetic", "model_id": "fixture"}, [])
    voice = FixtureVoice()
    voice.local = False
    return service, store, assets, chapter, job, voice


@pytest.mark.parametrize("boundary", ["resolve", "project_policy", "final_source"])
@pytest.mark.parametrize("retry", [False, True])
def test_audio_cancellation_at_last_preparation_boundaries_blocks_send(tmp_path, boundary, retry):
    service, store, assets, chapter, job, voice = reviewed_audio(tmp_path)
    source_reads = []

    def cancel():
        service.transition("novel-a", job["id"], "CANCELLED")
        if retry:
            service.transition("novel-a", job["id"], "QUEUED")

    def resolve(_):
        if boundary == "resolve":
            cancel()
        return "synthetic", "fixture", voice

    def policy():
        if boundary == "project_policy":
            cancel()

    def source():
        source_reads.append(True)
        if boundary == "final_source" and len(source_reads) == 2:
            cancel()
        return chapter

    result = service.execute("novel-a", job["id"], chapter, resolve, source, policy)
    assert result["status"] == ("QUEUED" if retry else "CANCELLED")
    assert voice.requests == []
    assert store.load("novel-a")["generations"] == []
    assert assets.list("novel-a") == []


@pytest.mark.parametrize("change", ["privacy", "version", "membership"])
def test_audio_reloads_source_and_authority_after_project_check(tmp_path, change):
    service, store, _, chapter, job, voice = reviewed_audio(tmp_path)
    live = dict(chapter)
    allowed = [True]

    def policy():
        if change == "privacy":
            review_source_privacy(live, None, "author", "LOCAL_ONLY", live["version"], content_digest(live))
        elif change == "version":
            live.update(content="New synthetic private revision", version=8)
        else:
            allowed[0] = False

    def source():
        if not allowed[0]:
            raise AudiobookError("AUDIOBOOK_PERMISSION_REVOKED", "membership revoked", 403)
        return dict(live)

    with pytest.raises(AudiobookError) as error:
        service.execute("novel-a", job["id"], chapter, lambda _: ("synthetic", "fixture", voice), source, policy)
    expected = {"privacy": "AUDIOBOOK_PRIVACY_BLOCKED", "version": "AUDIOBOOK_SOURCE_CHANGED", "membership": "AUDIOBOOK_PERMISSION_REVOKED"}
    assert error.value.code == expected[change]
    assert voice.requests == []
    assert service.find(store.load("novel-a"), job["id"])["status"] == "FAILED"


@pytest.mark.parametrize("field,value", [("owner_actor_id", "another-owner"), ("execution_token", "replacement-attempt"), ("source_text", "changed synthetic text")])
def test_audio_lost_claim_neither_dispatches_nor_overwrites_new_record(tmp_path, field, value):
    service, store, _, chapter, job = audio_setup(tmp_path)
    voice = FixtureVoice()

    def resolve(_):
        def change(state):
            current = service.find(state, job["id"])
            current[field] = value
            return current
        store.mutate("novel-a", change)
        return "synthetic", "fixture", voice

    result = service.execute("novel-a", job["id"], chapter, resolve)
    assert result[field] == value and result["status"] == "RUNNING"
    assert voice.requests == []


def test_owned_audio_requires_authority_even_for_local_provider(tmp_path):
    service, store, assets, chapter, _ = audio_setup(tmp_path)
    service = AudiobookService(store.for_actor("author"), assets)
    job = service.queue("novel-a", chapter, {"provider_id": "synthetic"}, [])
    voice = FixtureVoice()
    with pytest.raises(AudiobookError) as error:
        service.execute("novel-a", job["id"], chapter, lambda _: ("synthetic", "fixture", voice))
    assert error.value.code == "AUDIOBOOK_POLICY_AUTHORITY_MISSING"
    assert voice.requests == []


class RecordingImage:
    local = True

    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return S(asset_uri="data:image/png;base64,AA==")

    def edit(self, request, images, **options):
        return self.generate(request)


@pytest.mark.parametrize("edit", [False, True])
@pytest.mark.parametrize("boundary", ["resolve", "authority"])
@pytest.mark.parametrize("retry", [False, True])
def test_image_cancelled_before_generate_or_edit_is_never_dispatched(tmp_path, edit, boundary, retry):
    service = ImageJobService(tmp_path)
    body = {"provider_id": "synthetic", "model_id": "fixture", "prompt": "Synthetic private image"}
    if edit:
        body["images"] = ["data:image/png;base64,AA=="]
    job = service.create("n", None, body)
    provider = RecordingImage()
    cancelled = []

    def cancel():
        if cancelled:
            return
        cancelled.append(True)
        service.transition("n", None, job["id"], "CANCELLED")
        if retry:
            service.transition("n", None, job["id"], "QUEUED")

    def resolve(_):
        if boundary == "resolve":
            cancel()
        return provider

    def authority():
        if boundary == "authority":
            cancel()

    result = service.execute("n", None, job["id"], S(get=resolve), authority)
    assert result["status"] == ("QUEUED" if retry else "CANCELLED")
    assert provider.requests == []
    assert not service._active


@pytest.mark.parametrize("field,value", [("owner_actor_id", "new-owner"), ("branch_id", "new-branch"), ("execution_token", "new-attempt"), ("prompt", "new prompt")])
def test_image_changed_claim_does_not_dispatch_or_overwrite(tmp_path, field, value):
    service = ImageJobService(tmp_path)
    job = service.create("n", None, {"provider_id": "synthetic", "model_id": "fixture", "prompt": "Synthetic"})
    provider = RecordingImage()

    def resolve(_):
        def change(rows):
            current = service._find(rows, job["id"])
            current[field] = value
            return current
        service._mutate("n", None, change)
        return provider

    result = service.execute("n", None, job["id"], S(get=resolve))
    assert result[field] == value and result["status"] == "RUNNING"
    assert provider.requests == []


@pytest.mark.parametrize("missing", [False, True])
def test_owned_image_requires_current_membership_after_resolution(tmp_path, missing):
    authority, scope = authorization_stack(tmp_path / "auth")
    service = ImageJobService(tmp_path).for_actor("lead")
    job = service.create("p", "b", {"provider_id": "synthetic", "model_id": "fixture", "prompt": "Synthetic"})
    provider = RecordingImage()

    def resolve(_):
        authority.identity_service.set_membership_status("lead", "w", IdentityStatus.INACTIVE)
        return provider

    check = None if missing else lambda: authority.require(actor("lead"), "domain.write", ModalityDomain.NOVEL, scope)
    result = service.execute("p", "b", job["id"], S(get=resolve), check)
    assert result["status"] == "FAILED" and provider.requests == []


@pytest.mark.parametrize("explicit", [False, True])
def test_image_remote_dispatch_requires_an_egress_authority_callback(tmp_path, explicit):
    service = ImageJobService(tmp_path)
    job = service.create("n", None, {"provider_id": "synthetic", "model_id": "fixture", "prompt": "Synthetic", "allow_cloud_prompt": explicit})
    provider = RecordingImage()
    provider.local = False
    result = service.execute("n", None, job["id"], S(get=lambda _: provider))
    assert result["status"] == "FAILED"
    assert result["error_code"] == "IMAGE_EGRESS_AUTHORITY_MISSING"
    assert provider.requests == []


def test_image_egress_callback_sees_hash_bound_consent_and_cannot_race_cancellation(tmp_path):
    service = ImageJobService(tmp_path)
    body = {"provider_id": "synthetic", "model_id": "fixture", "prompt": "Synthetic", "allow_cloud_prompt": True}
    job = service.create("n", None, body, "idempotent")
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        service.create("n", None, {**body, "allow_cloud_prompt": False}, "idempotent")
    provider = RecordingImage()
    provider.local = False
    seen = []

    def check_egress(claimed, resolved):
        seen.append((claimed["allow_cloud_prompt"], resolved))
        service.transition("n", None, job["id"], "CANCELLED")

    result = service.execute("n", None, job["id"], S(get=lambda _: provider), check_egress=check_egress)
    assert seen == [(True, provider)]
    assert result["status"] == "CANCELLED" and provider.requests == []


@pytest.fixture
def agent_rig(tmp_path):
    object.__setattr__(settings, "novel_data", tmp_path)
    bundle = create_repository_bundle(data_root=tmp_path)
    novel = bundle.novels.create({"title": "Synthetic dispatch fixture"})
    bundle.chapters.create(novel["id"], {"title": "Synthetic", "content": "Synthetic chapter."})
    fact = {"name": "PRIVATE_FACT_CANARY", "privacy_level": "CLOUD_ALLOWED"}
    bundle.novels.upsert_character(novel["id"], "fact", fact)
    contexts = AgentContextService(bundle.novels, bundle.chapters, ContextService(bundle.novels, bundle.chapters))
    captured = []

    class Node:
        def execute(self, value):
            request = value.request
            captured.append(request)
            output = {"schema": "story_plan_proposal", "agent_id": "planner", "summary": "Synthetic result", "proposals": [], "findings": [], "context_hash": request.context["context_hash"]}
            response = TextGenerationResponse(json.dumps(output), "completed", "remote", "fixture")
            return TextModelNodeOutput(response.text, response, request.job_id)

    runtime = S(is_remote_text_provider=lambda _: True, prepare_text_route=lambda *_: Node(), providers={})
    service = AgentJobService(bundle.generations, contexts, bundle.novels, runtime, agent_runner)
    job = service.create("planner", novel["id"], 1, provider="remote", model="fixture", execution_mode="model")
    return S(service=service, bundle=bundle, novel=novel, fact=fact, captured=captured, runtime=runtime, job=job, node=Node())


def revoke_fact(rig):
    rig.bundle.novels.upsert_character(rig.novel["id"], "fact", {**rig.fact, "privacy_level": "LOCAL_ONLY"})


@pytest.mark.parametrize("boundary", ["route", "authority", "runtime_resolve"])
def test_agent_fact_revocation_at_each_preparation_boundary_blocks_send(agent_rig, boundary):
    rig = agent_rig
    authority = None
    if boundary == "route":
        def prepare(*_):
            revoke_fact(rig)
            return rig.node
        rig.runtime.prepare_text_route = prepare
    elif boundary == "authority":
        authority = lambda _: revoke_fact(rig)
    else:
        def resolve(_):
            revoke_fact(rig)
            return S(generate_text=lambda request: rig.captured.append(request))
        node = TextModelNode(S(resolve=resolve), S(resolve=lambda *_: S(structured_output=False)))
        rig.runtime.prepare_text_route = lambda *_: node
    result = rig.service.execute(rig.job["id"], authority)
    assert result["status"] == "FAILED" and result["error_code"] == "AGENT_SOURCE_CHANGED"
    assert rig.captured == []


@pytest.mark.parametrize("change", ["cancel", "timeout", "token", "owner", "scope", "queued"])
def test_agent_lost_claim_or_cancellation_during_route_preparation_blocks_send(agent_rig, change):
    rig = agent_rig

    def prepare(*_):
        if change == "cancel":
            rig.service.cancel(rig.job["id"])
        elif change == "timeout":
            rig.service._timeout(rig.job["id"])
        else:
            current = rig.service.get(rig.job["id"])
            updates = {"token": {"execution_token": "replacement"}, "owner": {"owner": {"actor_id": "new-owner"}}, "scope": {"branch_id": "other-branch"}, "queued": {"status": "QUEUED"}}
            rig.bundle.generations.save({**current, **updates[change]})
        return rig.node

    rig.runtime.prepare_text_route = prepare
    result = rig.service.execute(rig.job["id"])
    assert rig.captured == []
    assert result == rig.service.get(rig.job["id"])
    assert result["status"] == {"cancel": "CANCELLED", "timeout": "FAILED", "queued": "QUEUED"}.get(change, "WORKING")


@pytest.mark.parametrize("missing", [False, True])
def test_agent_owned_job_requires_membership_recheck_after_route(agent_rig, tmp_path, missing):
    rig = agent_rig
    authority, scope = authorization_stack(tmp_path / "auth")
    rig.bundle.generations.save({**rig.job, "owner": {"actor_id": "lead", "workspace_id": "w"}, "branch_id": "b"})

    def prepare(*_):
        authority.identity_service.set_membership_status("lead", "w", IdentityStatus.INACTIVE)
        return rig.node

    rig.runtime.prepare_text_route = prepare
    check = None if missing else lambda current: authority.require(actor(current["owner"]["actor_id"]), "domain.write", ModalityDomain.NOVEL, scope)
    result = rig.service.execute(rig.job["id"], check)
    assert result["status"] == "FAILED"
    assert result["error_code"] == ("AGENT_AUTHORITY_MISSING" if missing else "AGENT_PERMISSION_REVOKED")
    assert rig.captured == []


def test_agent_valid_context_and_authority_still_dispatch_once(agent_rig):
    rig = agent_rig
    seen = []
    result = rig.service.execute(rig.job["id"], lambda current: seen.append(current["execution_token"]))
    assert result["status"] == "COMPLETED"
    assert len(rig.captured) == 1 and len(seen) == 2
    assert "PRIVATE_FACT_CANARY" in rig.captured[0].prompt
    assert callable(rig.captured[0].dispatch_guard)


@pytest.mark.parametrize("change", ["cancel", "token"])
def test_agent_late_model_result_never_overwrites_cancelled_or_new_attempt(agent_rig, change):
    rig = agent_rig

    def execute(value):
        result = rig.node.execute(value)
        if change == "cancel":
            rig.service.cancel(rig.job["id"])
        else:
            current = rig.service.get(rig.job["id"])
            rig.bundle.generations.save({**current, "execution_token": "new-attempt"})
        return result

    rig.runtime.prepare_text_route = lambda *_: S(execute=execute)
    result = rig.service.execute(rig.job["id"])
    assert result["status"] == ("CANCELLED" if change == "cancel" else "WORKING")
    assert "result" not in result


def test_image_membership_revoked_during_egress_preparation_blocks_send(tmp_path):
    authority, scope = authorization_stack(tmp_path / "auth")
    service = ImageJobService(tmp_path).for_actor("lead")
    job = service.create("p", "b", {"provider_id": "synthetic", "model_id": "fixture", "prompt": "Synthetic"})
    provider = RecordingImage()
    result = service.execute(
        "p", "b", job["id"], S(get=lambda _: provider),
        lambda: authority.require(actor("lead"), "domain.write", ModalityDomain.NOVEL, scope),
        lambda *_: authority.identity_service.set_membership_status("lead", "w", IdentityStatus.INACTIVE),
    )
    assert result["status"] == "FAILED" and provider.requests == []


def test_agent_membership_revoked_during_context_reload_blocks_send(agent_rig, tmp_path):
    rig = agent_rig
    authority, scope = authorization_stack(tmp_path / "auth")
    rig.bundle.generations.save({**rig.job, "owner": {"actor_id": "lead", "workspace_id": "w"}, "branch_id": "b"})
    build = rig.service.contexts.build
    reads = []

    def read(*args):
        context = build(*args)
        reads.append(True)
        if len(reads) == 2:
            authority.identity_service.set_membership_status("lead", "w", IdentityStatus.INACTIVE)
        return context

    rig.service.contexts.build = read
    result = rig.service.execute(rig.job["id"], lambda _: authority.require(actor("lead"), "domain.write", ModalityDomain.NOVEL, scope))
    assert result["status"] == "FAILED" and result["error_code"] == "AGENT_PERMISSION_REVOKED"
    assert rig.captured == []


@pytest.mark.parametrize("operation", ["execute", "start"])
def test_agent_api_passes_a_fresh_record_authority_check(monkeypatch, operation):
    import app.api as api
    from fastapi import HTTPException

    original = {"id": "synthetic", "owner": {"actor_id": "author"}}
    current = {**original, "owner": {"actor_id": "different-author"}}
    seen = []

    def authorize(token, job, permission):
        seen.append((token, job, permission))
        if job is current:
            raise HTTPException(403, {"code": "SYNTHETIC_REVOKED"})

    def execute(jid, check_authority):
        assert jid == original["id"]
        check_authority(current)
        pytest.fail("revoked execution must not proceed")

    monkeypatch.setattr(api, "_agent_job_actor_for_record", authorize)
    monkeypatch.setattr(api, "agent_job_service", S(get=lambda _: original, execute=execute, start=execute))
    endpoint = api.execute_agent_job if operation == "execute" else api.start_agent_job
    with pytest.raises(HTTPException) as error:
        endpoint(original["id"], "synthetic-token")
    assert error.value.status_code == 403
    assert seen == [("synthetic-token", original, "domain.write"), ("synthetic-token", current, "domain.write")]


def test_image_api_forwards_authority_and_current_egress_checks(monkeypatch):
    import app.api as api

    seen = []
    job = {"id": "synthetic", "novel_id": "n", "allow_cloud_prompt": True}
    provider = RecordingImage()

    def execute(nid, branch_id, jid, registry, check_authority, check_egress):
        check_authority()
        check_egress(job, provider)
        return {**job, "status": "SUCCEEDED"}

    monkeypatch.setattr(api, "_image_jobs", lambda _: S(execute=execute))
    monkeypatch.setattr(api, "_authorize_media_novel", lambda *args: seen.append(("authority", args)))
    monkeypatch.setattr(api, "_assert_manual_media_egress", lambda *args: seen.append(("egress", args)))
    result = api.execute_image_job("n", "synthetic", "synthetic-token", "b")
    assert result["status"] == "SUCCEEDED"
    assert seen == [
        ("authority", ("n", "synthetic-token", "domain.write", "b")),
        ("authority", ("n", "synthetic-token", "domain.write", "b")),
        ("egress", (job, provider, "synthetic-token", "b")),
    ]
