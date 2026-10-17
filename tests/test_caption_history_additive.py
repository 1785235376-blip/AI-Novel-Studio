"""B04 history recovery through real File PCM16 and mounted route aliases."""
import base64
import copy

import pytest
from fastapi import HTTPException

from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.subtitle_timeline import SubtitleTimelineService, read_captions
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import wav_bytes
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_r5_voice_subtitles_mounted import prepare


def cue(text="Original 中文🌙", segment_id=None):
    return {"id": "original", "start_tick": 0, "end_tick": 1500, "text": text,
            "segment_id": segment_id, "overlap_reason": ""}


def create(e, plan=None, empty=False, headers=None):
    asset = e.assets.create(e.nid, "history.wav", base64.b64encode(wav_bytes(4000)).decode(),
                            "audio/wav", "audio", branch_id=e.scope.get("branch_id"))
    payload = {"asset_id": asset["id"], "cues": [] if empty else [cue(segment_id=plan["segments"][0]["id"] if plan else None)]}
    if plan:
        payload.update(plan_id=plan["id"], expected_plan_version=plan["version"])
    row = checked(e.client.post(e.base + "/subtitle-timeline/records", json=payload, headers=headers), 201)
    return row, asset


def endpoint(e, row):
    return e.base + f'/subtitle-timeline/records/{row["id"]}'


def save(e, row, cues, restore=None, headers=None):
    payload = {"expected_version": row["version"], "cues": cues}
    if restore is not None:
        payload["restore_history_version"] = restore
    return e.client.put(endpoint(e, row), json=payload, headers=headers)


def preview(e, row, version=1, headers=None):
    return e.client.post(endpoint(e, row) + "/history-preview", headers=headers,
                         json={"expected_version": row["version"], "history_version": version})


def persisted(e):
    return e.store.path(e.nid, e.scope).read_bytes()


def mutate_history(e, row, change):
    with e.store.transaction(e.nid, e.scope) as doc:
        change(doc["collections"]["subtitle_timeline_v2"][row["id"]]["history"])


def test_preview_restore_preserves_history_reopens_and_original_exports(mounted):
    e = mounted
    first, _ = create(e)
    second = checked(save(e, first, [cue("Replacement")]))
    before = persisted(e)
    listing = e.client.get(endpoint(e, second) + "/history", params={"expected_version": 2})
    page = checked(listing)
    assert listing.headers["cache-control"] == "no-store"
    assert page["items"] == [{"version": 1, "updated_at": first["updated_at"], "status": "DRAFT", "timing_origin": "MANUAL", "cue_count": 1}]
    assert page["has_more"] is False and page["next_before_version"] is None
    result = preview(e, second)
    old = checked(result)
    assert result.headers["cache-control"] == "no-store"
    assert old["cues"] == first["cues"] and len(old["source_binding_digest"]) == 64
    assert persisted(e) == before
    restored = checked(save(e, second, old["cues"], restore=1))
    assert restored["version"] == 3 and restored["cues"] == first["cues"]
    assert restored["history"][:1] == second["history"] and restored["history"][1]["cues"] == second["cues"]
    assert restored["status"] == "DRAFT" and restored["timing_origin"] == "MANUAL"
    assert restored["alignment_model"] is None and restored["processing_task_id"] is None
    fresh = SubtitleTimelineService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters,
                                    e.experimental.audiobook_service, AssetLibraryService(e.root))
    assert fresh._current(e.nid, e.scope, "local-author", first["id"])["history"] == restored["history"]
    for format in ("srt", "vtt"):
        output = fresh.download(e.nid, e.scope, "local-author", first["id"], 3, format)
        response = e.client.get(endpoint(e, first) + f"/file.{format}?expected_version=3")
        assert response.content == output and response.headers["cache-control"] == "no-store"
        assert read_captions(output.decode(), format)[0]["text"] == "Original 中文🌙"
    stale = save(e, second, old["cues"], restore=1)
    assert stale.status_code == 409 and set(stale.json()["detail"]["current"]) == {"version", "status"}


def test_history_paging_is_head_anchored_and_metadata_only(mounted):
    e = mounted; row, _ = create(e)
    for index in range(4):
        row = checked(save(e, row, [cue(str(index))]))
    before = persisted(e)
    path = endpoint(e, row) + "/history"
    first = checked(e.client.get(path, params={"expected_version": 5, "limit": 2}))
    assert [item["version"] for item in first["items"]] == [4, 3]
    assert first["has_more"] and first["next_before_version"] == 3
    second = checked(e.client.get(path, params={"expected_version": 5, "limit": 2, "before_version": 3}))
    assert [item["version"] for item in second["items"]] == [2, 1]
    assert not second["has_more"] and second["next_before_version"] is None
    for item in first["items"] + second["items"]:
        assert set(item) == {"version", "updated_at", "status", "timing_origin", "cue_count"}
    assert persisted(e) == before
    checked(save(e, row, []))
    assert e.client.get(path, params={"expected_version": 5, "before_version": 3}).status_code == 409


@pytest.mark.parametrize("params", [
    {"expected_version": "true"}, {"expected_version": "1.0"}, {"expected_version": "0"},
    {"expected_version": "01"}, {"limit": "0"}, {"limit": "51"}, {"limit": "-1"},
    {"limit": "2.0"}, {"before_version": "0"}, {"before_version": "3"}, {"before_version": "false"},
])
def test_paging_strict_bounds(mounted, params):
    e = mounted; row, _ = create(e); row = checked(save(e, row, [])); before = persisted(e)
    response = e.client.get(endpoint(e, row) + "/history", params={"expected_version": 2, **params})
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert persisted(e) == before


@pytest.mark.parametrize("field,value", [("expected_version", True), ("expected_version", "2"),
    ("expected_version", 2.0), ("history_version", False), ("history_version", "1"), ("history_version", 0)])
def test_preview_strict_integer_inputs(mounted, field, value):
    e = mounted; row, _ = create(e); row = checked(save(e, row, [])); before = persisted(e)
    response = e.client.post(endpoint(e, row) + "/history-preview", json={"expected_version": 2, "history_version": 1, field: value})
    assert response.status_code == 422 and persisted(e) == before


@pytest.mark.parametrize("corruption", ["identity", "scope", "novel", "id", "duplicate", "version_bool", "asset", "plan", "timebase", "media",
    "cue_text_loss", "cue_tick_loss", "cue_extra", "cue_missing", "cue_limit", "duration", "sources_missing"])
def test_malformed_history_never_restores_or_mutates(mounted, corruption):
    e = mounted; row, _ = create(e); row = checked(save(e, row, []))
    def corrupt(history):
        old = history[0]
        if corruption == "identity": old["created_by"] = "other"
        elif corruption == "scope": old["scope"] = {**old["scope"], "branch_id": "other"}
        elif corruption == "novel": old["novel_id"] = "other"
        elif corruption == "id": old["id"] = "other"
        elif corruption == "duplicate": history.append(copy.deepcopy(old))
        elif corruption == "version_bool": old["version"] = True
        elif corruption == "asset": old["asset_snapshot"]["version"] += 1
        elif corruption == "plan": old["plan_id"] = "other-plan"
        elif corruption == "timebase": old["timebase"]["numerator"] = 24
        elif corruption == "media": old["media"]["duration_seconds"] = {"numerator": 999, "denominator": 1}
        elif corruption == "cue_text_loss": old["cues"][0]["text"] = " padded "
        elif corruption == "cue_tick_loss": old["cues"][0]["start_tick"] = False
        elif corruption == "cue_extra": old["cues"][0]["approval"] = True
        elif corruption == "cue_missing": old["cues"][0].pop("overlap_reason")
        elif corruption == "cue_limit": old["cues"] = [cue()] * 2001
        elif corruption == "duration": old["cues"][0]["end_tick"] = 5000
        elif corruption == "sources_missing": old.pop("sources")
    mutate_history(e, row, corrupt); before = persisted(e)
    assert preview(e, row).status_code == 422
    assert save(e, row, [], restore=1).status_code == 422
    assert persisted(e) == before


def test_empty_history_cues_restore_and_current_head_not_history(mounted):
    e = mounted; original, _ = create(e, empty=True); row = checked(save(e, original, [cue()]))
    old = checked(preview(e, row)); assert old["cues"] == []
    assert preview(e, row, row["version"]).status_code == 404
    assert preview(e, row, 999).status_code == 404
    restored = checked(save(e, row, [], restore=1)); assert restored["cues"] == []


def test_removed_current_cues_historical_own_pins_survive_manual_edits(mounted):
    e = mounted; plan = prepare(e); first, _ = create(e, plan); row = checked(save(e, first, []))
    old = checked(preview(e, row))
    edited = [{**old["cues"][0], "text": "Manually edited"}]
    restored = checked(save(e, row, edited, restore=1))
    assert restored["cues"] == edited and restored["speakers"] == first["speakers"]


def test_historical_only_speaker_change_between_preview_save_rejected(mounted):
    e = mounted; plan = prepare(e); first, _ = create(e, plan); row = checked(save(e, first, []))
    old = checked(preview(e, row))
    service = e.experimental.subtitle_timeline_service
    segment = plan["segments"][0]
    checked(e.client.put(e.base + f'/voice-direction/plans/{plan["id"]}/segments/{segment["id"]}', json={
        "expected_version": plan["version"], "kind": "NARRATION", "profile_id": segment["profile_id"],
        "reviewed_text": segment["text"], "text_reviewed": True, "attribution_reviewed": True,
        "voice_authorized": True, "emotion": "calm"}))
    # Current cues no longer reference this speaker: current itself is still valid.
    service._current(e.nid, e.scope, "local-author", row["id"])
    before = persisted(e)
    assert preview(e, row).status_code == 409
    for cues in (old["cues"], [{**old["cues"][0], "text": "edited"}], []):
        result = save(e, row, cues, restore=1)
        assert result.status_code == 409 and "CAPTION_HISTORY_SOURCE_CHANGED" in result.text
    assert persisted(e) == before


def test_history_recheck_head_authority_and_snapshot(mounted):
    e = mounted; first, _ = create(e); row = checked(save(e, first, [])); service = e.experimental.subtitle_timeline_service
    before = persisted(e)
    def denied(): raise HTTPException(403, "denied")
    for fn in (lambda: service.history(e.nid, e.scope, "local-author", row["id"], 2, reauthorize=denied),
               lambda: service.history_preview(e.nid, e.scope, "local-author", row["id"], {"expected_version": 2, "history_version": 1}, denied)):
        with pytest.raises(HTTPException): fn()
    assert persisted(e) == before
    def modify():
        mutate_history(e, row, lambda history: history[0]["cues"][0].update(text="changed in read"))
    with pytest.raises(StaleSourceError, match="CAPTION_HISTORY_CHANGED"):
        service.history_preview(e.nid, e.scope, "local-author", row["id"], {"expected_version": 2, "history_version": 1}, modify)
    def next_head(): checked(save(e, row, [cue("new head")]))
    with pytest.raises(CapabilityVersionConflict):
        service.history(e.nid, e.scope, "local-author", row["id"], 2, reauthorize=next_head)


def test_history_owner_scope_and_real_permission_revocation(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); first, _ = create(e, headers=e.headers)
    row = checked(save(e, first, [], headers=e.headers)); before = persisted(e)
    path = endpoint(e, row)
    assert preview(e, row, headers=e.headers).status_code == 200
    assert preview(e, row, headers=e.viewer_headers).status_code == 403
    assert e.client.get(path + "/history?expected_version=2", headers=e.viewer_headers).status_code == 404
    assert preview(e, row).status_code in (400, 401, 403)
    e.authorization.revoke_role(e.role, e.lead)
    assert preview(e, row, headers=e.headers).status_code == 403
    assert e.client.get(path + "/history?expected_version=2", headers=e.headers).status_code == 403
    assert persisted(e) == before


@pytest.mark.parametrize("missing", ["subtitle_timeline_v2", "voice_direction_v2", "audiobook_v2", "v1"])
def test_all_existing_gates_and_v1_override(mounted, monkeypatch, missing):
    from app.experimental.flags import FLAGS
    e = mounted; first, _ = create(e); row = checked(save(e, first, [])); before = persisted(e)
    if missing == "v1": monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    else: monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(flag for flag in FLAGS if flag != missing))
    for response in (preview(e, row), e.client.get(endpoint(e, row) + "/history?expected_version=2"), save(e, row, [], restore=1)):
        assert response.status_code == 404
    assert persisted(e) == before
