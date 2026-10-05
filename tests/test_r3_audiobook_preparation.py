import base64
import io
import wave
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.audiobook import AudiobookV2Service, RuleDialogueAttribution, LocalPcmMixer, MixerRequest
from app.experimental.audiobook_api import create_audiobook_router
from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, audio_asset, wav_bytes, branch_scope


def service(rig, mixer=None):
    return AudiobookV2Service(rig.store, rig.novels, rig.chapters, assets=rig.assets, mixer=mixer)


def profile(rig, instance):
    return instance.create_profile(rig.nid, rig.scope, rig.actor, {"display_name": "Test voice", "provider_id": "mock",
        "model_id": "mock-tts", "voice_id": "fixture", "license_note": "Synthetic contract fixture, no synthesis"})


def mapped_plan(rig, instance):
    voice = profile(rig, instance)
    for cid in ["alice", "__narrator__"]:
        instance.map_voice(rig.nid, rig.scope, rig.actor, {"character_id": cid, "profile_id": voice["id"]})
    return voice, instance.create_plan(rig.nid, rig.scope, rig.actor, {"chapter_id": rig.chapter["id"]})


def reviewed_plan(rig, instance, bind=False):
    voice, plan = mapped_plan(rig, instance)
    for segment in plan["segments"]:
        if segment["attribution_status"] == "NEEDS_REVIEW":
            plan = instance.update_segment(rig.nid, rig.scope, rig.actor, plan["id"], segment["id"], {
                "expected_version": plan["version"], "character_id": "alice", "profile_id": voice["id"],
                "emotion": "curious", "speaking_style": "quiet", "attribution_reviewed": True})
    if bind:
        asset = audio_asset(rig)
        for segment in plan["segments"]:
            plan = instance.bind_audio(rig.nid, rig.scope, rig.actor, plan["id"], segment["id"], {
                "expected_version": plan["version"], "asset_id": asset["id"]})
    return instance.review(rig.nid, rig.scope, rig.actor, plan["id"], "approve", plan["version"])


def test_attribution_only_exact_named_unambiguous_prefix():
    rule = RuleDialogueAttribution(); characters = [{"id": "a", "name": "Alice"}, {"id": "b", "name": "Bob"}]
    assert rule.attribute("Alice: ", "Hello", characters).character_id == "a"
    assert rule.attribute("她说：", "Hello", characters).status == "NEEDS_REVIEW"
    assert rule.attribute("They saw Alice. ", "Hello", characters).status == "NEEDS_REVIEW"
    assert rule.attribute("NotAlice: ", "Hello", characters).status == "NEEDS_REVIEW"
    assert rule.attribute("Alice: ", "Hello", characters + [{"id": "c", "name": "Alice"}]).status == "NEEDS_REVIEW"


def test_audio_plan_offsets_attribution_voice_mapping_and_review(rig):
    instance = service(rig); voice, plan = mapped_plan(rig, instance)
    before = rig.chapters.get(rig.chapter["id"])
    dialogue = [s for s in plan["segments"] if s["kind"] == "DIALOGUE"]
    assert dialogue[0]["character_id"] == "alice" and dialogue[0]["attribution_status"] == "RULE_CONFIRMED"
    assert dialogue[1]["character_id"] is None and dialogue[1]["attribution_status"] == "NEEDS_REVIEW"
    assert plan["timing_status"] == "UNMEASURED" and plan["duration_ms"] is None
    for segment in plan["segments"]:
        assert before["content"][segment["source_start"]:segment["source_end"]] == segment["text"]
        assert segment["duration_ms"] is None and segment["end_ms"] is None
    with pytest.raises(ValueError, match="ATTRIBUTION_NEEDS_REVIEW"):
        instance.review(rig.nid, rig.scope, rig.actor, plan["id"], "approve", plan["version"])
    plan = instance.update_segment(rig.nid, rig.scope, rig.actor, plan["id"], dialogue[1]["id"], {
        "expected_version": plan["version"], "character_id": "alice", "profile_id": voice["id"],
        "emotion": "uncertain", "speaking_style": "whisper", "attribution_reviewed": True})
    approved = instance.review(rig.nid, rig.scope, rig.actor, plan["id"], "approve", plan["version"])
    assert approved["status"] == "APPROVED"
    assert rig.chapters.get(rig.chapter["id"]) == before
    assert rig.assets.list(rig.nid) == []
    assert instance.capabilities()["phoneme_alignment"] == "NOT_CONFIGURED"
    assert {"reopen"} == set(instance.list_review_items(rig.nid, rig.scope)[0]["allowed_actions"])


def test_audio_measured_timeline_manifest_subtitles_and_mixer(rig):
    instance = service(rig, LocalPcmMixer())
    approved = reviewed_plan(rig, instance, bind=True)
    manifest = instance.duration_manifest(rig.nid, rig.scope, approved["id"])
    assert manifest["timing_status"] == "MEASURED"
    assert manifest["duration_ms"] == 100 * len(approved["segments"])
    assert [s["start_ms"] for s in manifest["segments"]] == [100 * n for n in range(len(approved["segments"]))]
    captions = instance.subtitles(rig.nid, rig.scope, approved["id"])
    assert captions["precision"] == "SEGMENT_ONLY" and captions["alignment_model"] is None
    count = len(rig.assets.list(rig.nid))
    mixed = instance.mix(rig.nid, rig.scope, rig.actor, approved["id"], approved["version"])
    assert mixed["status"] == "PENDING_REVIEW" and mixed["verification"] == "CONTRACT_VERIFIED"
    assert len(rig.assets.list(rig.nid)) == count
    result = instance.review(rig.nid, rig.scope, rig.actor, mixed["id"], "approve", mixed["version"])
    assert result["status"] == "APPROVED"
    asset = rig.assets.get(result["asset_id"])
    assert asset["source_asset_ids"]
    assert asset["parameters"]["experimental_audio_lineage"]["plan_id"] == approved["id"]
    with wave.open(io.BytesIO(rig.assets.content(asset["id"])), "rb") as audio:
        assert audio.getnframes() / audio.getframerate() * 1000 == manifest["duration_ms"]


def test_audio_partial_durations_do_not_invent_later_starts(rig):
    instance = service(rig); _, plan = mapped_plan(rig, instance)
    with pytest.raises(ValueError, match="MEASURED_TIMING_REQUIRED"):
        instance.subtitles(rig.nid, rig.scope, plan["id"])
    asset = audio_asset(rig)
    plan = instance.bind_audio(rig.nid, rig.scope, rig.actor, plan["id"], plan["segments"][1]["id"], {
        "expected_version": plan["version"], "asset_id": asset["id"]})
    assert plan["timing_status"] == "PARTIAL" and plan["duration_ms"] is None
    assert plan["segments"][1]["duration_ms"] == 100
    assert plan["segments"][1]["start_ms"] is None and plan["segments"][1]["end_ms"] is None
    assert all(s["start_ms"] is None for s in plan["segments"][2:])


def test_audio_stale_mapping_source_conflict_and_scope(rig):
    instance = service(rig); voice, plan = mapped_plan(rig, instance)
    with pytest.raises(FileNotFoundError):
        instance.get(rig.nid, branch_scope(rig), instance.PLANS, plan["id"])
    with pytest.raises(StaleSourceError, match="BRANCH_SOURCE_ADAPTER_REQUIRED"):
        instance.create_plan(rig.nid, branch_scope(rig), rig.actor, {"chapter_id": rig.chapter["id"]})
    with pytest.raises(CapabilityVersionConflict):
        instance.map_voice(rig.nid, rig.scope, rig.actor, {"character_id": "alice", "profile_id": voice["id"]})
    mapping = next(r for r in instance.list(rig.nid, rig.scope, instance.MAPPINGS) if r["character_id"] == "alice")
    instance.map_voice(rig.nid, rig.scope, rig.actor, {"character_id": "alice", "profile_id": voice["id"], "expected_version": mapping["version"]})
    assert instance.plans(rig.nid, rig.scope)[0]["stale"] is True
    with pytest.raises(StaleSourceError, match="MAPPING_CHANGED"):
        instance.duration_manifest(rig.nid, rig.scope, plan["id"])
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "New chapter"})
    with pytest.raises(StaleSourceError):
        instance.update_segment(rig.nid, rig.scope, rig.actor, plan["id"], plan["segments"][0]["id"], {
            "expected_version": plan["version"], "profile_id": voice["id"]})


def test_audio_track_slots_and_not_configured_mixer(rig):
    instance = service(rig); _, plan = mapped_plan(rig, instance)
    plan = instance.add_track(rig.nid, rig.scope, rig.actor, plan["id"], {"expected_version": plan["version"], "kind": "AMBIENCE", "label": "Rain"})
    assert plan["tracks"][0]["status"] == "PLANNED" and plan["tracks"][0]["asset_id"] is None
    assert plan["tracks"][0]["start_ms"] is None
    with pytest.raises(ValueError, match="MIXER_NOT_CONFIGURED"):
        instance.mix(rig.nid, rig.scope, rig.actor, plan["id"], plan["version"])
    plan = instance.remove_track(rig.nid, rig.scope, rig.actor, plan["id"], plan["tracks"][0]["id"], plan["version"])
    assert plan["tracks"] == []
    reopened = AudiobookV2Service(ExperimentalStore(rig.root, rig.backend, rig.store.database_url), rig.novels, rig.chapters, rig.assets)
    assert reopened.get(rig.nid, rig.scope, reopened.PLANS, plan["id"]) == plan


def test_local_mixer_overlaps_audio_and_validates_formats():
    mixer = LocalPcmMixer()
    output = mixer.mix(MixerRequest("test", [{"content": wav_bytes(100, sample=100), "start_ms": 0}],
        [{"content": wav_bytes(100, sample=200), "start_ms": 0, "gain_db": 0}]))
    with wave.open(io.BytesIO(output.content), "rb") as audio:
        assert int.from_bytes(audio.readframes(1), "little", signed=True) == 300
    with pytest.raises(ValueError, match="FORMAT_MISMATCH"):
        mixer.mix(MixerRequest("test", [{"content": wav_bytes(), "start_ms": 0}],
            [{"content": wav_bytes(sample_rate=16000), "start_ms": 0}]))


def test_audio_mix_promotion_failure_checkpoint_blocks_reject_and_resumes(rig, monkeypatch):
    instance = service(rig, LocalPcmMixer()); plan = reviewed_plan(rig, instance, bind=True)
    proposal = instance.mix(rig.nid, rig.scope, rig.actor, plan["id"], plan["version"])
    original = rig.assets.update_metadata
    def crash_after_commit(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated crash after asset commit")
    monkeypatch.setattr(rig.assets, "update_metadata", crash_after_commit)
    with pytest.raises(RuntimeError, match="simulated crash"):
        instance.review(rig.nid, rig.scope, rig.actor, proposal["id"], "approve", 1)
    pending = instance.get(rig.nid, rig.scope, instance.MIXES, proposal["id"])
    assert pending["status"] == "APPROVING"
    with pytest.raises(ValueError, match="TRANSITION_INVALID"):
        instance.review(rig.nid, rig.scope, rig.actor, pending["id"], "reject", pending["version"])
    count = len(rig.assets.list(rig.nid))
    monkeypatch.setattr(rig.assets, "update_metadata", original)
    reopened = AudiobookV2Service(ExperimentalStore(rig.root, rig.backend, rig.store.database_url), rig.novels, rig.chapters, rig.assets)
    approved = reopened.review(rig.nid, rig.scope, rig.actor, pending["id"], "approve", pending["version"])
    assert approved["status"] == "APPROVED" and len(rig.assets.list(rig.nid)) == count


def test_audio_mix_source_changes_during_callback_are_discarded(rig):
    entered, release = Event(), Event()
    class Slow(LocalPcmMixer):
        def mix(self, request):
            entered.set(); assert release.wait(10)
            return super().mix(request)
    instance = service(rig, Slow()); plan = reviewed_plan(rig, instance, bind=True)
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(instance.mix, rig.nid, rig.scope, rig.actor, plan["id"], plan["version"])
        assert entered.wait(10)
        instance.review(rig.nid, rig.scope, rig.actor, plan["id"], "reopen", plan["version"])
        release.set()
        with pytest.raises(StaleSourceError, match="MIX_PLAN_CHANGED"):
            pending.result(timeout=20)
    assert instance.list(rig.nid, rig.scope, instance.MIXES) == []


def test_audio_api_flag_authority_and_contract(rig):
    instance = service(rig); permissions = []; flags = {"audiobook_v2"}
    def authorize(nid, token, branch, permission):
        if token != "valid": raise HTTPException(403, "denied")
        permissions.append(permission); return rig.actor, rig.scope
    def enabled(flag):
        if flag not in flags: raise HTTPException(404, "disabled")
    app = FastAPI(); app.include_router(create_audiobook_router(instance, authorize, enabled)); client = TestClient(app)
    base = f"/novels/{rig.nid}/experimental/audiobook"; headers = {"X-Session-Token": "valid"}
    assert client.get(base + "/capabilities").status_code == 403
    assert client.get(base + "/capabilities", headers=headers).json()["mixer"] == "NOT_CONFIGURED"
    plan = client.post(base + "/plans", headers=headers, json={"chapter_id": rig.chapter["id"]}).json()
    response = client.post(base + f"/plans/{plan['id']}/approve", headers=headers, json={"expected_version": 1})
    assert response.status_code == 422 and "NEEDS_REVIEW" in response.text
    assert permissions[-1] == "domain.review"
    response = client.get(base + f"/plans/{plan['id']}/subtitles", headers=headers)
    assert response.status_code == 422 and "MEASURED_TIMING_REQUIRED" in response.text
    flags.clear()
    assert client.get(base + "/plans", headers=headers).status_code == 404


def test_audio_source_edit_during_attribution_cannot_bind_old_text_to_new_version(rig):
    class ConcurrentEdit(RuleDialogueAttribution):
        changed = False
        def attribute(self, *args):
            if not self.changed:
                self.changed = True
                rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "New manuscript"})
            return super().attribute(*args)
    instance = AudiobookV2Service(rig.store, rig.novels, rig.chapters, rig.assets, attribution=ConcurrentEdit())
    with pytest.raises(StaleSourceError):
        instance.create_plan(rig.nid, rig.scope, rig.actor, {"chapter_id": rig.chapter["id"]})
    assert instance.plans(rig.nid, rig.scope) == []


def test_audio_approval_validates_exact_segment_evidence(rig):
    instance = service(rig); plan = reviewed_plan(rig, instance)
    plan = instance.review(rig.nid, rig.scope, rig.actor, plan["id"], "reopen", plan["version"])
    with rig.store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"][instance.PLANS][plan["id"]]["segments"][0]["text"] = "Corrupted evidence"
    with pytest.raises(StaleSourceError, match="SEGMENT_EVIDENCE_CHANGED"):
        instance.review(rig.nid, rig.scope, rig.actor, plan["id"], "approve", plan["version"])


def test_audio_mixer_change_at_final_authority_guard_cannot_dispatch(rig):
    called = []
    class Remote(LocalPcmMixer):
        local = False
        def mix(self, request):
            called.append(request)
            return super().mix(request)
    instance = service(rig, LocalPcmMixer()); plan = reviewed_plan(rig, instance, bind=True)
    def swap():
        instance.mixer = Remote()
    with pytest.raises(StaleSourceError, match="MIXER_CHANGED"):
        instance.mix(rig.nid, rig.scope, rig.actor, plan["id"], plan["version"], check_authority=swap)
    assert called == []
