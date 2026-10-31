"""Independent pure size-plan observations; no reservation or CAS occurs."""
import base64
import copy
import hashlib
import io
import os
from pathlib import Path
import wave

import pytest

from app.experimental.audio_shared_document_measurement import plan_file_scope_replacement
from app.experimental.common import new_row, snapshot
from app.experimental.store import ExperimentalStore, canonical
from test_studio_asset_query import rig

NID = "synthetic-novel"
SCOPE = {"mode": "local", "novel_id": NID}
NAME = "audio_v2_mix_proposals"


def candidate():
    audio = io.BytesIO()
    with wave.open(audio, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 800)
    data = audio.getvalue()
    return new_row(NID, SCOPE, "synthetic-author", {"plan_id": "plan", "plan_version": 1,
        "sources": {}, "source_asset_ids": [], "status": "PENDING_REVIEW", "mixer_id": "local",
        "content_base64": base64.b64encode(data).decode("ascii"), "content_sha256": hashlib.sha256(data).hexdigest(),
        "verification": "CONTRACT_VERIFIED", "media": {"media_type": "audio/wav", "extension": "wav",
        "duration_ms": 100, "sample_rate": 8000, "channels": 1, "sample_width": 2,
        "validation": "PCM_DECODED"}, "asset_id": None})


def encode(document):
    return canonical(document).encode("utf-8")


def docs():
    original = ExperimentalStore.empty(NID, SCOPE)
    original["collections"]["unrelated"] = {"item": {"text": "非音频☃" * 40}}
    replacement = copy.deepcopy(original)
    row = candidate()
    replacement["collections"][NAME] = {row["id"]: row}
    return original, replacement


def test_add_and_remove_are_exact_utf8_and_stage_full_document():
    old, new = docs()
    a, b = encode(old), encode(new)
    plan = plan_file_scope_replacement(a, b, NID, SCOPE)
    field = ('"' + NAME + '":').encode() + encode(new["collections"][NAME]) + b','
    assert plan["previous_sha256"] == hashlib.sha256(a).hexdigest()
    assert plan["replacement_sha256"] == hashlib.sha256(b).hexdigest()
    assert plan["previous_candidate_bytes"] == 0
    assert plan["requires_write"] is True
    assert plan["replacement_candidate_bytes"] == len(field)
    assert plan["persistent_candidate_delta"] == len(field)
    assert plan["temporary_reservation_bytes"] == len(b) > len(field)
    remove = plan_file_scope_replacement(b, a, NID, SCOPE)
    assert remove["persistent_candidate_delta"] == -len(field)
    assert remove["temporary_reservation_bytes"] == len(a)


def test_identical_bytes_need_no_write_or_temporary_reservation():
    _, document = docs()
    data = encode(document)
    plan = plan_file_scope_replacement(data, data, NID, SCOPE)
    assert plan["previous_sha256"] == plan["replacement_sha256"]
    assert plan["persistent_candidate_delta"] == 0
    assert plan["requires_write"] is False
    assert plan["temporary_reservation_bytes"] == 0


def test_duplicate_history_increases_delta_by_real_serialized_copy():
    old, replacement = docs()
    before = encode(replacement)
    item = next(iter(replacement["collections"][NAME].values()))
    old_row = snapshot(item)
    item["history"].append(old_row)
    after = encode(replacement)
    plan = plan_file_scope_replacement(before, after, NID, SCOPE)
    assert plan["persistent_candidate_delta"] == len(encode(old_row))
    assert plan["temporary_reservation_bytes"] == len(after)


def test_nonaudio_growth_changes_hash_and_peak_but_not_candidate_delta():
    old, new = docs()
    first = plan_file_scope_replacement(encode(old), encode(new), NID, SCOPE)
    changed_old = copy.deepcopy(old)
    changed_new = copy.deepcopy(new)
    for value in (changed_old, changed_new):
        value["collections"]["unrelated"]["item"]["text"] += "雪" * 1000
    changed = plan_file_scope_replacement(encode(changed_old), encode(changed_new), NID, SCOPE)
    assert changed["persistent_candidate_delta"] == first["persistent_candidate_delta"]
    assert changed["previous_sha256"] != first["previous_sha256"]
    assert changed["temporary_reservation_bytes"] == first["temporary_reservation_bytes"] + 3000
    # Different old hash tells a caller to redo preflight; the pure function
    # itself never acquires a scope lease, compares current bytes or reserves.


def test_plan_matches_real_scope_owner_staging_but_does_not_reserve(rig, monkeypatch):
    import app.storage as storage
    store = rig.workspace.store.store
    with store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"]["unrelated"] = {"x": {"body": "真实合成正文☃" * 100}}
    path = store.path(rig.nid, rig.scope)
    previous = path.read_bytes()
    new = store.read(rig.nid, rig.scope)
    entry = candidate()
    entry.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope))
    new["collections"][NAME] = {entry["id"]: entry}
    replacement = encode(new)
    plan = plan_file_scope_replacement(previous, replacement, rig.nid, rig.scope)
    captured = []
    original = os.replace
    def observe(source, target):
        if Path(target) == path:
            captured.append(Path(source).read_bytes())
        return original(source, target)
    monkeypatch.setattr(storage.os, "replace", observe)
    with store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"][NAME] = {entry["id"]: entry}
    assert captured == [replacement]
    assert len(captured[0]) == plan["temporary_reservation_bytes"]
    assert path.read_bytes() == replacement


@pytest.mark.parametrize("fault", ["old_absent", "old_corrupt", "new_corrupt", "old_wrong_project", "new_wrong_project"])
def test_unproven_original_or_replacement_rejected(fault):
    old, new = docs()
    a, b = encode(old), encode(new)
    if fault == "old_absent": a = None
    elif fault == "old_corrupt": a += b"\xff"
    elif fault == "new_corrupt": b += b"\xff"
    elif fault == "old_wrong_project": old["novel_id"] = "wrong"; a = encode(old)
    else: new["scope"] = {"mode": "local", "novel_id": "wrong"}; b = encode(new)
    with pytest.raises(ValueError, match="MEASUREMENT_UNAVAILABLE"):
        plan_file_scope_replacement(a, b, NID, SCOPE)
