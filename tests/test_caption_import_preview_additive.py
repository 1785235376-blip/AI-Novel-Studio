"""Additive caption import contracts. Synthetic PCM16/File, in-process HTTP only."""
import base64
import copy
import hashlib

import pytest

from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.subtitle_timeline import SubtitleTimelineService, read_captions
from app.services.asset_library_service import AssetLibraryService
from app.services.studio_timeline_subtitles import parse_subtitle_cues
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import wav_bytes
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


def body(content, format="srt", version=1):
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return {"expected_version": version, "format": format, "content_base64": base64.b64encode(raw).decode("ascii")}


def srt(text="中文🌙", start="00:00:00,000", end="00:00:01,000"):
    return f"1\n{start} --> {end}\n{text}\n"


def track(e, timebase=None, headers=None):
    asset = checked(e.client.post(e.prefix + f"/novels/{e.nid}/assets", headers=headers, json={
        "novel_id": e.nid, "filename": "caption-import.wav", "kind": "audio", "media_type": "audio/wav",
        "content_base64": base64.b64encode(wav_bytes(4000)).decode("ascii")}))
    payload = {"asset_id": asset["id"]}
    if timebase: payload["timebase"] = timebase
    row = checked(e.client.post(e.base + "/subtitle-timeline/records", headers=headers, json=payload), 201)
    return row, asset


def endpoint(e, row):
    return e.base + f'/subtitle-timeline/records/{row["id"]}/import-preview'


@pytest.mark.parametrize("format", ["srt", "vtt"])
def test_exact_bytes_preview_original_save_fresh_file_reopen_export(mounted, format):
    e = mounted
    row, asset = track(e)
    source = srt("[旁白] 中文🌙\n第二行")
    if format == "vtt": source = "WEBVTT\n\n" + source.replace(",", ".")
    raw = ("\ufeff" + source.replace("\n", "\r\n")).encode("utf-8")
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    response = e.client.post(endpoint(e, row), json=body(raw, format))
    preview = checked(response)
    assert response.headers["cache-control"] == "no-store"
    assert preview["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert preview["byte_length"] == len(raw)
    assert preview["record_id"] == row["id"] and preview["expected_version"] == 1
    assert preview["asset_snapshot"] == row["asset_snapshot"] and preview["timebase"] == row["timebase"]
    assert preview["cues"][0]["segment_id"] is None and preview["cues"][0]["overlap_reason"] == ""
    assert preview["cues"][0]["text"] == "[旁白] 中文🌙\n第二行"
    assert e.store.read(e.nid, e.scope) == before
    assert checked(e.client.post(endpoint(e, row), json=body(raw, format))) == preview
    saved = checked(e.client.put(e.base + f'/subtitle-timeline/records/{row["id"]}', json={
        "expected_version": 1, "cues": preview["cues"]}))
    assert saved["version"] == 2 and saved["status"] == "DRAFT" and len(saved["history"]) == 1
    fresh = SubtitleTimelineService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters,
                                    e.experimental.audiobook_service, AssetLibraryService(e.root))
    reopened = fresh._current(e.nid, e.scope, "local-author", row["id"])
    assert reopened["cues"] == preview["cues"]
    actual = fresh.download(e.nid, e.scope, "local-author", row["id"], 2, format)
    assert read_captions(actual.decode("utf-8"), format) == [{"start_ms": 0, "end_ms": 1000, "text": "[旁白] 中文🌙\n第二行"}]
    exported = e.client.get(e.base + f'/subtitle-timeline/records/{row["id"]}/file.{format}?expected_version=2')
    assert exported.status_code == 200 and exported.content == actual
    conflict = e.client.post(endpoint(e, row), json=body(raw, format))
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "EXPERIMENTAL_VERSION_CONFLICT"
    assert set(conflict.json()["detail"]["current"]) == {"version", "status"}
    e.assets.update_metadata(asset["id"], {"model_id": "changed-media"})
    stale = e.client.post(endpoint(e, row), json=body(raw, format, 2))
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "EXPERIMENTAL_SOURCE_STALE"


@pytest.mark.parametrize("content,format,error", [
    (srt("<b>markup</b>"), "srt", "CAPTION_PLAIN_NONEMPTY_TEXT_REQUIRED"),
    (srt("x\x00"), "srt", "CAPTION_PLAIN_NONEMPTY_TEXT_REQUIRED"),
    (srt("trailing "), "srt", "CAPTION_ROUND_TRIP_FAILED"),
    (srt(" leading"), "srt", "CAPTION_ROUND_TRIP_FAILED"),
    (srt("a\u0085b"), "srt", "CAPTION_ROUND_TRIP_FAILED"),
    (srt("a\u2028b"), "srt", "CAPTION_ROUND_TRIP_FAILED"),
    (srt("a\u2029b"), "srt", "CAPTION_ROUND_TRIP_FAILED"),
    (srt(end="00:00:00,000"), "srt", "greater_than_equal"),
    (srt(start="00:00:01,000", end="00:00:01,000"), "srt", "CAPTION_REVERSED_TIME"),
    (srt(end="00:00:05,000"), "srt", "CAPTION_OUT_OF_MEDIA_RANGE"),
    (srt() + "\n2\n00:00:00,500 --> 00:00:01,500\noverlap\n", "srt", "CAPTION_OVERLAP_REQUIRES_REASON"),
    (srt(start="00:00:01,000", end="00:00:02,000") + "\n2\n00:00:00,000 --> 00:00:00,500\nbackward\n", "srt", "CAPTION_ORDER_INVALID"),
    ("WEBVTT metadata\n\n" + srt().replace(",", "."), "vtt", "STUDIO_SUBTITLE_VTT_PLAIN_HEADER_REQUIRED"),
    ("WEBVTT\n\nNOTE metadata\nignored", "vtt", "STUDIO_SUBTITLE_NUMBERED_CUES_REQUIRED"),
    ("WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000 align:start\nx", "vtt", "STUDIO_SUBTITLE_PLAIN_TIMING_REQUIRED"),
    (srt().replace("00:00:01,000", "00:60:01,000"), "srt", "STUDIO_SUBTITLE_PLAIN_TIMING_REQUIRED"),
    (srt().replace("\n", "\r"), "srt", "STUDIO_SUBTITLE_LINE_ENDINGS_INVALID"),
    (b"\xff", "srt", "CAPTION_IMPORT_UTF8_REQUIRED"),
    ("", "srt", "string_too_short"),
])
def test_preview_rejects_unsupported_or_invalid_without_mutation(mounted, content, format, error):
    e = mounted; row, _ = track(e)
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    response = e.client.post(endpoint(e, row), json=body(content, format))
    assert response.status_code == 422 and error in response.text
    assert e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize("base,start,end,expected", [
    ({"numerator": 48000, "denominator": 1}, "00:00:00,001", "00:00:01,001", (48, 48048)),
    ({"numerator": 30000, "denominator": 1001}, "00:00:00,000", "00:00:01,001", (0, 30)),
    ({"numerator": 30000, "denominator": 1001}, "00:00:00,001", "00:00:01,001", None),
    ({"numerator": 24, "denominator": 1}, "00:00:00,000", "00:00:00,001", None),
])
def test_exact_rational_ticks_never_round(mounted, base, start, end, expected):
    e = mounted; row, _ = track(e, base)
    response = e.client.post(endpoint(e, row), json=body(srt(start=start, end=end)))
    if expected is None:
        assert response.status_code == 422 and "CAPTION_IMPORT_TIME_UNREPRESENTABLE" in response.text
    else:
        cue = checked(response)["cues"][0]
        assert (cue["start_tick"], cue["end_tick"]) == expected


def test_base64_schema_limits_and_unknown_fields(mounted):
    e = mounted; row, _ = track(e)
    for payload, error in [
        ({**body(srt()), "content_base64": "!"}, "CAPTION_IMPORT_BASE64_INVALID"),
        ({**body(srt()), "content_base64": "A" * 256004}, "string_too_long"),
        ({**body(srt()), "format": "ass"}, "literal_error"),
        ({**body(srt()), "overlap_reason": "invented"}, "extra_forbidden"),
    ]:
        response = e.client.post(endpoint(e, row), json=payload)
        assert response.status_code == 422 and error in response.text


def test_lexical_parser_existing_bounds_optional_vtt_and_unicode():
    assert parse_subtitle_cues("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n中文🌙\n", "VTT")[0]["text"] == "中文🌙"
    exact = srt("x")
    exact += "x" * (192000 - len(exact.encode()))
    assert len(exact.encode()) == 192000
    assert len(parse_subtitle_cues(exact, "SRT")) == 1
    with pytest.raises(ValueError, match="STUDIO_SUBTITLE_BYTE_LIMIT"):
        parse_subtitle_cues(exact + "x", "SRT")
    cues = "\n\n".join(f"{i}\n00:00:00,000 --> 00:00:01,000\nx" for i in range(1, 501))
    assert len(parse_subtitle_cues(cues, "SRT")) == 500
    with pytest.raises(ValueError, match="STUDIO_SUBTITLE_CUE_LIMIT"):
        parse_subtitle_cues(cues + "\n\n501\n00:00:00,000 --> 00:00:01,000\nx", "SRT")
    with pytest.raises(ValueError, match="STUDIO_SUBTITLE_UTF8_REQUIRED"):
        parse_subtitle_cues(srt("\ud800"), "SRT")


def test_owner_scope_and_recheck_at_preview_completion(mounted):
    e = mounted; row, asset = track(e)
    service = e.experimental.subtitle_timeline_service
    with pytest.raises(FileNotFoundError):
        service.import_preview(e.nid, e.scope, "other-actor", row["id"], body(srt()))
    with pytest.raises(FileNotFoundError):
        service.import_preview(e.nid, {**e.scope, "branch_id": "other"}, "local-author", row["id"], body(srt()))
    def change_version():
        service.update(e.nid, e.scope, "local-author", row["id"], {"expected_version": 1, "cues": []})
    with pytest.raises(CapabilityVersionConflict):
        service.import_preview(e.nid, e.scope, "local-author", row["id"], body(srt()), change_version)
    def change_media():
        e.assets.update_metadata(asset["id"], {"model_id": "changed-during-preview"})
    with pytest.raises(StaleSourceError, match="CAPTION_MEDIA_CHANGED"):
        service.import_preview(e.nid, e.scope, "local-author", row["id"], body(srt(), version=2), change_media)


def test_mounted_scope_permission_revocation_and_disabled(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    # The legacy asset upload route is project-scoped. Seed an actual File
    # branch asset through its original service, then use real caption routes.
    asset = e.assets.create(e.nid, "branch-caption.wav", base64.b64encode(wav_bytes(4000)).decode(),
                            "audio/wav", "audio", branch_id=e.branch)
    row = checked(e.client.post(e.base + "/subtitle-timeline/records", headers=e.headers,
                                json={"asset_id": asset["id"]}), 201)
    assert e.client.post(endpoint(e, row), headers=e.headers, json=body(srt())).status_code == 200
    assert e.client.post(endpoint(e, row), headers=e.viewer_headers, json=body(srt())).status_code == 403
    assert e.client.post(endpoint(e, row), json=body(srt())).status_code in (400, 401, 403)
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(endpoint(e, row), headers=e.headers, json=body(srt())).status_code == 403
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    disabled = e.client.post(endpoint(e, row), headers=e.headers, json=body(srt()))
    assert disabled.status_code == 501
    assert disabled.json()["detail"]["code"] == "COLLABORATION_ROUTE_NOT_ENABLED"


@pytest.mark.parametrize("override", [False, True])
def test_local_disabled_feature_and_v1_override(mounted, monkeypatch, override):
    e = mounted; row, _ = track(e)
    if override:
        monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    else:
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    disabled = e.client.post(endpoint(e, row), json=body(srt()))
    assert disabled.status_code == 404
    assert disabled.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"


def test_plan_source_staleness_and_preview_authority_guard(mounted):
    from fastapi import HTTPException
    from test_r5_voice_subtitles_mounted import prepare
    e = mounted; plan = prepare(e)
    _, asset = track(e)
    row = checked(e.client.post(e.base + "/subtitle-timeline/records", json={
        "asset_id": asset["id"], "plan_id": plan["id"], "expected_plan_version": plan["version"]}), 201)
    service = e.experimental.subtitle_timeline_service
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    def denied():
        raise HTTPException(403, {"code": "CAPTION_AUTHORITY_CHANGED"})
    with pytest.raises(HTTPException) as caught:
        service.import_preview(e.nid, e.scope, "local-author", row["id"], body(srt()), denied)
    assert caught.value.status_code == 403
    assert e.store.read(e.nid, e.scope) == before
    current = e.chapters.get(e.chapter["id"])
    e.chapters.save(current["id"], {"version": current["version"], "content": "Edited source text"})
    response = e.client.post(endpoint(e, row), json=body(srt()))
    assert response.status_code == 409 and response.json()["detail"]["code"] == "EXPERIMENTAL_SOURCE_STALE"
