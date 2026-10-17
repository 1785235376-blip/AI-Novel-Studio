"""Original save/reopen/export contracts for shifted cues, separate from mocked UI.

No offset API or alternate save owner exists. Synthetic measured PCM16 only.
"""
import copy
from fractions import Fraction

import pytest

from app.experimental.store import ExperimentalStore
from app.experimental.subtitle_timeline import SubtitleTimelineService, read_captions
from app.services.asset_library_service import AssetLibraryService
from test_caption_import_preview_additive import track
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.mark.parametrize("timebase,offset", [
    ({"numerator": 1000, "denominator": 1}, 100),
    ({"numerator": 24000, "denominator": 1001}, 1),
    ({"numerator": 30000, "denominator": 1001}, -1),
])
def test_shifted_original_save_fresh_reopen_and_both_exports(mounted, timebase, offset):
    e = mounted
    row, _ = track(e, timebase)
    path = e.base + f'/subtitle-timeline/records/{row["id"]}'
    cues = [{"id": "first", "start_tick": 3, "end_tick": 12, "text": "字幕🌙", "segment_id": None, "overlap_reason": ""},
            {"id": "second", "start_tick": 15, "end_tick": 20, "text": "Second", "segment_id": None, "overlap_reason": ""}]
    saved = checked(e.client.put(path, json={"expected_version": 1, "cues": cues}))
    # This is an original-owner persistence contract, not an assertion that Python
    # executed the TypeScript helper or that a browser completed the journey.
    shifted = [{**cue, "start_tick": cue["start_tick"] + offset, "end_tick": cue["end_tick"] + offset} for cue in cues]
    changed = checked(e.client.put(path, json={"expected_version": 2, "cues": shifted}))
    assert changed["version"] == 3 and changed["cues"] == shifted
    for key in ("asset_id", "asset_snapshot", "timebase", "plan_id", "media"):
        assert changed.get(key) == saved.get(key)
    assert len(changed["history"]) == 2 and changed["history"][-1]["cues"] == cues
    fresh = SubtitleTimelineService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters,
                                    e.experimental.audiobook_service, AssetLibraryService(e.root))
    reopened = fresh._current(e.nid, e.scope, "local-author", row["id"])
    assert reopened["cues"] == shifted and reopened["version"] == 3
    factor = Fraction(timebase["denominator"] * 1000, timebase["numerator"])
    expected = [{"start_ms": int(cue["start_tick"] * factor), "end_ms": int(cue["end_tick"] * factor), "text": cue["text"]} for cue in shifted]
    for format in ("srt", "vtt"):
        actual = fresh.download(e.nid, e.scope, "local-author", row["id"], 3, format)
        assert read_captions(actual.decode("utf-8"), format) == expected
        exported = e.client.get(path + f'/file.{format}?expected_version=3')
        assert exported.status_code == 200 and exported.content == actual
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    stale = e.client.put(path, json={"expected_version": 2, "cues": cues})
    assert stale.status_code == 409 and e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize("cues,error", [
    ([{"id": "a", "start_tick": -1, "end_tick": 2, "text": "a"}], "greater_than_equal"),
    ([{"id": "a", "start_tick": 1, "end_tick": 5000, "text": "a"}], "CAPTION_OUT_OF_MEDIA_RANGE"),
    ([{"id": "a", "start_tick": 200, "end_tick": 300, "text": "a"}, {"id": "b", "start_tick": 100, "end_tick": 200, "text": "b", "overlap_reason": "intentional"}], "CAPTION_ORDER_INVALID"),
    ([{"id": "a", "start_tick": 100, "end_tick": 300, "text": "a"}, {"id": "b", "start_tick": 200, "end_tick": 400, "text": "b"}], "CAPTION_OVERLAP_REQUIRES_REASON"),
])
def test_original_save_rejects_invalid_offset_result_atomically(mounted, cues, error):
    e = mounted
    row, _ = track(e)
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    response = e.client.put(e.base + f'/subtitle-timeline/records/{row["id"]}', json={"expected_version": 1, "cues": cues})
    assert response.status_code == 422 and error in response.text
    assert e.store.read(e.nid, e.scope) == before
