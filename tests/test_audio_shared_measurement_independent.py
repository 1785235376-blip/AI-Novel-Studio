"""Independent byte-counter tests for the isolated pure measurement candidate."""
import base64
import copy
import hashlib
import json
import io
import wave

import pytest

from app.experimental.audio_shared_document_measurement import measure_file_scope_document
from app.experimental.store import ExperimentalStore, canonical
from test_studio_asset_query import rig

NID = "synthetic-novel"
SCOPE = {"mode": "local", "novel_id": NID}
COLLECTION = "audio_v2_mix_proposals"


def row(data=b"pcm", title="雪☃"):
    return {"id": "candidate", "novel_id": NID, "scope": copy.deepcopy(SCOPE),
            "version": 1, "created_by": "synthetic-author", "updated_by": "synthetic-author",
            "created_at": "2026-10-28T00:00:00Z", "updated_at": "2026-10-28T00:00:00Z",
            "privacy_level": "LOCAL_ONLY", "plan_id": "synthetic-plan", "plan_version": 1,
            "sources": {}, "source_asset_ids": [], "mixer_id": title,
            "verification": "MOCK_ONLY", "asset_id": None,
            "content_base64": base64.b64encode(data).decode("ascii"),
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "media": {"media_type": "audio/wav", "extension": "wav", "duration_ms": 100,
                      "sample_rate": 8000, "channels": 1, "sample_width": 2, "validation": "PCM_DECODED"},
            "status": "PENDING_REVIEW", "history": []}


def raw(collections):
    document = ExperimentalStore.empty(NID, SCOPE)
    document["collections"] = collections
    return canonical(document).encode("utf-8")


def expected_collection_field(rows, siblings):
    # Independent byte expression: entire real collection's serialized field
    # plus exactly one comma when there are other fields in collections.
    field = ('"' + COLLECTION + '":').encode() + canonical(rows).encode("utf-8")
    return len(field) + int(bool(siblings))


@pytest.mark.parametrize("siblings", [False, True])
@pytest.mark.parametrize("count", [0, 1, 3])
def test_exact_field_empty_and_multiple_candidates_with_unicode(count, siblings):
    entries = {f"candidate-{i}": row(("声音-" + str(i)).encode("utf-8"), "音声" * (i + 1))
               for i in range(count)}
    for key, value in entries.items():
        value["id"] = key
    collections = {COLLECTION: entries}
    if siblings:
        collections.update({"audio_v2_plans": {"p": {"noncandidate": "故事"}},
                            "private_images": {"i": {"not_audio": "🖼"}}})
    data = raw(collections)
    measured = measure_file_scope_document(data, NID, SCOPE)
    assert measured["mix_collection_bytes"] == expected_collection_field(entries, siblings)
    assert measured["full_document_bytes"] == measured["atomic_temporary_bytes"] == len(data)
    assert measured["other_document_bytes"] + measured["mix_collection_bytes"] == len(data)


def test_unrelated_unicode_or_base64_growth_changes_only_non_audio_and_peak():
    candidate = row(b"\x00\x01\x02")
    base = {COLLECTION: {"candidate": candidate}, "unrelated": {"payload": "old"}}
    previous = measure_file_scope_document(raw(base), NID, SCOPE)
    changed = copy.deepcopy(base)
    changed["unrelated"]["payload"] = "同音内容" * 4000 + candidate["content_base64"] * 20
    after = measure_file_scope_document(raw(changed), NID, SCOPE)
    assert previous["mix_collection_bytes"] == after["mix_collection_bytes"]
    assert after["other_document_bytes"] > previous["other_document_bytes"]
    assert after["atomic_temporary_bytes"] > previous["atomic_temporary_bytes"]


def test_repeated_history_bytes_are_physically_counted_once_per_serialized_copy():
    original = row(b"identical audio bytes")
    one = {COLLECTION: {"candidate": copy.deepcopy(original)}, "unrelated": {}}
    one_measure = measure_file_scope_document(raw(one), NID, SCOPE)
    snapshot = copy.deepcopy(original)
    snapshot.pop("history")
    two = copy.deepcopy(one)
    two[COLLECTION]["candidate"]["history"] = [snapshot]
    two_measure = measure_file_scope_document(raw(two), NID, SCOPE)
    # Replacing [] with [<snapshot>] increases storage by exactly the snapshot
    # JSON bytes, independent of the source digest being equal.
    assert two_measure["mix_collection_bytes"] - one_measure["mix_collection_bytes"] == len(canonical(snapshot).encode("utf-8"))


@pytest.mark.parametrize("fault", ["invalid_utf8", "duplicate_key", "not_canonical", "missing_digest",
                                   "bad_snapshot", "bad_collection", "nonfinite"])
def test_unreliable_legacy_or_corrupt_content_fails_closed(fault):
    value = row()
    collections = {COLLECTION: {"candidate": value}}
    if fault == "missing_digest":
        value.pop("content_sha256")
    elif fault == "bad_snapshot":
        value["history"] = [dict(value, content_sha256="0" * 64)]
    elif fault == "bad_collection":
        collections[COLLECTION] = []
    elif fault == "nonfinite":
        value["media"]["duration"] = float("nan")
    if fault == "nonfinite":
        document = ExperimentalStore.empty(NID, SCOPE)
        document["collections"] = collections
        data = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=True).encode()
    else:
        data = raw(collections)
    if fault == "invalid_utf8":
        data += b"\xff"
    elif fault == "duplicate_key":
        data = data.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1', 1)
    elif fault == "not_canonical":
        data = json.dumps(json.loads(data)).encode("utf-8")
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        measure_file_scope_document(data, NID, SCOPE)


def test_absent_collection_counts_zero_without_changing_other():
    collections = {"unrelated": {"note": "☃"}}
    data = raw(collections)
    measured = measure_file_scope_document(data, NID, SCOPE)
    assert measured["mix_collection_bytes"] == 0
    assert measured["other_document_bytes"] == len(data)


def test_unknown_row_field_is_not_silently_classified_as_audio_metadata():
    candidate = row()
    candidate["unknown_unrelated_payload"] = "unrelated synthetic content" * 100
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        measure_file_scope_document(raw({COLLECTION: {"candidate": candidate}}), NID, SCOPE)


def test_mismatched_row_key_is_not_treated_as_attributable():
    candidate = row()
    candidate["id"] = "other-candidate"
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        measure_file_scope_document(raw({COLLECTION: {"candidate": candidate}}), NID, SCOPE)


@pytest.mark.parametrize("status", ["PENDING_REVIEW", "REJECTED", "APPROVING", "APPROVED"])
def test_original_review_statuses_and_source_media_timeline_are_measured(status):
    candidate = row()
    candidate["status"] = status
    candidate["sources"] = {"chapter-one": {"version": 1, "digest": "a" * 64, "scope": SCOPE}}
    candidate["timeline"] = [{"id": "segment", "audio_asset_id": "source-one", "start_ms": 0,
        "end_ms": 100, "pause_after_ms": 0, "frame_timing": {"frames": 800, "sample_rate": 8000}}]
    candidate["voice_direction"] = True
    if status in {"APPROVING", "APPROVED"}:
        candidate.update(promotion_token="synthetic-token", promotion_started_at="2026-10-28T00:00:00Z",
                         promotion_actor="synthetic-author")
    if status == "APPROVED":
        candidate.update(asset_id="synthetic-asset", approved_at="2026-10-28T00:00:00Z", approved_by="synthetic-author")
    snapshot = copy.deepcopy(candidate)
    snapshot.pop("history")
    candidate["history"] = [snapshot]
    data = raw({COLLECTION: {"candidate": candidate}, "unrelated": {"body": "原文"}})
    result = measure_file_scope_document(data, NID, SCOPE)
    assert result["mix_collection_bytes"] == expected_collection_field({"candidate": candidate}, True)


@pytest.mark.parametrize("nested", ["media", "source", "source_scope", "timeline", "frames", "snapshot"])
def test_unknown_nested_audio_metadata_is_refused(nested):
    candidate = row()
    candidate["sources"] = {"chapter-one": {"version": 1, "digest": "a" * 64, "scope": SCOPE}}
    candidate["timeline"] = [{"id": "segment", "frame_timing": {"frames": 800, "sample_rate": 8000}}]
    if nested == "media": candidate["media"]["unrelated"] = "x"
    elif nested == "source": candidate["sources"]["chapter-one"]["unrelated"] = "x"
    elif nested == "source_scope": candidate["sources"]["chapter-one"]["scope"] = {"mode": "local", "novel_id": "other"}
    elif nested == "timeline": candidate["timeline"][0]["unrelated"] = "x"
    elif nested == "frames": candidate["timeline"][0]["frame_timing"]["unrelated"] = "x"
    else:
        snapshot = copy.deepcopy(candidate)
        snapshot.pop("history")
        snapshot["unrelated"] = "x"
        candidate["history"] = [snapshot]
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        measure_file_scope_document(raw({COLLECTION: {"candidate": candidate}}), NID, SCOPE)


def test_noninteger_schema_version_is_not_accepted_as_one():
    document = ExperimentalStore.empty(NID, SCOPE)
    document["schema_version"] = True  # bool == 1 in Python, but not a schema integer
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        measure_file_scope_document(canonical(document).encode("utf-8"), NID, SCOPE)


@pytest.mark.parametrize("mutation", ["boolean_version", "unknown_status", "invalid_media_type"])
def test_corrupt_known_candidate_values_are_not_recognized(mutation):
    candidate = row()
    if mutation == "boolean_version": candidate["version"] = True
    elif mutation == "unknown_status": candidate["status"] = "SYNTHETIC_UNKNOWN"
    else: candidate["media"]["channels"] = {"unrelated": "bytes"}
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        measure_file_scope_document(raw({COLLECTION: {"candidate": candidate}}), NID, SCOPE)


def test_actual_audiobook_owner_produces_and_reviews_synthetic_wav_candidates(rig):
    from app.experimental.audiobook import AudiobookV2Service, LocalPcmMixer
    chapter = rig.workspace.creative.chapters.create(rig.nid, {"title": "Synthetic", "content": "纯合成旁白"})
    source = io.BytesIO()
    with wave.open(source, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 800)
    audio = source.getvalue()
    asset = rig.assets.create(rig.nid, "fixture.wav", base64.b64encode(audio).decode("ascii"), "audio/wav", "audio")
    service = AudiobookV2Service(rig.workspace.store.store, rig.novels, rig.workspace.creative.chapters,
                                 rig.assets, mixer=LocalPcmMixer())
    profile = service.create_profile(rig.nid, rig.scope, "author", {"display_name": "Synthetic voice",
        "provider_id": "none", "model_id": "none", "voice_id": "none", "license_note": "synthetic only"})
    plan = service.create_plan(rig.nid, rig.scope, "author", {"chapter_id": chapter["id"]})
    segment = plan["segments"][0]
    plan = service.update_segment(rig.nid, rig.scope, "author", plan["id"], segment["id"],
                                  {"expected_version": plan["version"], "profile_id": profile["id"]})
    plan = service.bind_audio(rig.nid, rig.scope, "author", plan["id"], segment["id"],
                              {"expected_version": plan["version"], "asset_id": asset["id"]})
    plan = service.review(rig.nid, rig.scope, "author", plan["id"], "approve", plan["version"])
    candidate = service.mix(rig.nid, rig.scope, "author", plan["id"], plan["version"])
    path = service.store.path(rig.nid, rig.scope)
    before = path.read_bytes()
    pending = measure_file_scope_document(before, rig.nid, rig.scope)
    assert pending["mix_collection_bytes"] > len(audio)
    rejected = service.review(rig.nid, rig.scope, "author", candidate["id"], "reject", candidate["version"])
    after = path.read_bytes()
    assert rejected["status"] == "REJECTED"
    measured = measure_file_scope_document(after, rig.nid, rig.scope)
    assert measured["mix_collection_bytes"] > pending["mix_collection_bytes"]
    approved_candidate = service.mix(rig.nid, rig.scope, "author", plan["id"], plan["version"])
    approved = service.review(rig.nid, rig.scope, "author", approved_candidate["id"], "approve", approved_candidate["version"])
    assert approved["status"] == "APPROVED"
    final = measure_file_scope_document(path.read_bytes(), rig.nid, rig.scope)
    assert final["mix_collection_bytes"] > measured["mix_collection_bytes"]
