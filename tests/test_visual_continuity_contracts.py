import copy
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.screenplay_service import (
    _visual_continuity_shots,
    validate_visual_continuity,
)

TIME_JUMP = "TIME_JUMP_CUT"
TIME_MESSAGE = "时间发生变化，当前使用直接剪切。"


def _time_jump(from_id, to_id):
    return {
        "code": TIME_JUMP,
        "severity": "INFO",
        "from_shot_id": from_id,
        "to_shot_id": to_id,
        "message": TIME_MESSAGE,
    }


def _pair(transition="__missing__", prev_time="夜", curr_time="晨", **curr_extra):
    previous = {"id": "s1", "time": prev_time}
    current = {"id": "s2", "time": curr_time, **curr_extra}
    if transition != "__missing__":
        current["transition"] = transition
    return [previous, current]


def _codes(findings):
    return [item["code"] for item in findings]


def test_missing_none_and_blank_transition_mean_default_cut():
    for transition in ("__missing__", None, "", "  ", "None", "none", " NONE "):
        findings = validate_visual_continuity(_pair(transition))
        assert findings == [_time_jump("s1", "s2")], transition


def test_explicit_cut_reports_time_jump_including_case_and_padding():
    for transition in ("CUT", "cut", "Cut", "  cut  "):
        findings = validate_visual_continuity(_pair(transition))
        assert findings == [_time_jump("s1", "s2")], transition


def test_non_cut_transitions_suppress_time_jump():
    for transition in ("FADE", "DISSOLVE", "MATCH", "WIPE", "fade", " Dissolve "):
        assert validate_visual_continuity(_pair(transition)) == [], transition


def test_same_time_does_not_report_time_jump():
    assert validate_visual_continuity(_pair("CUT", prev_time="夜", curr_time="夜")) == []
    assert validate_visual_continuity(_pair("__missing__", prev_time="晨", curr_time="晨")) == []


def test_missing_time_on_either_side_does_not_report_time_jump():
    assert validate_visual_continuity(_pair("CUT", prev_time="", curr_time="晨")) == []
    assert validate_visual_continuity(_pair("CUT", prev_time="夜", curr_time="")) == []
    shots = [{"id": "s1"}, {"id": "s2", "time": "晨", "transition": "CUT"}]
    assert validate_visual_continuity(shots) == []
    shots = [{"id": "s1", "time": "夜"}, {"id": "s2", "transition": "CUT"}]
    assert validate_visual_continuity(shots) == []


def test_unknown_non_empty_transition_is_not_treated_as_cut():
    assert validate_visual_continuity(_pair("CUSTOM")) == []


def test_adjacent_pairs_emit_stable_ordered_findings():
    shots = [
        {"id": "a", "location": "港口", "time": "夜", "emotion": "紧张", "action": "追"},
        {"id": "b", "location": "宫殿", "time": "晨", "emotion": "平静", "action": ""},
        {"id": "c", "location": "宫殿", "time": "午", "emotion": "平静", "action": "停"},
    ]
    findings = validate_visual_continuity(shots)
    assert _codes(findings) == [
        "LOCATION_JUMP",
        TIME_JUMP,
        "EMOTION_DISCONTINUITY",
        TIME_JUMP,
    ]
    assert [(item["from_shot_id"], item["to_shot_id"]) for item in findings] == [
        ("a", "b"),
        ("a", "b"),
        ("a", "b"),
        ("b", "c"),
    ]
    assert findings[1] == _time_jump("a", "b")
    assert findings[3] == _time_jump("b", "c")


def test_validate_visual_continuity_does_not_mutate_inputs():
    shots = [
        {"id": "s1", "location": "港口", "time": "夜", "emotion": "紧张", "action": "追逐", "nested": ["x"]},
        {"id": "s2", "location": "宫殿", "time": "晨", "emotion": "平静", "action": ""},
    ]
    original = copy.deepcopy(shots)
    findings = validate_visual_continuity(shots)
    assert TIME_JUMP in _codes(findings)
    assert shots == original


def test_check_view_fills_scene_metadata_without_writing_back():
    screenplay = {
        "scenes": [
            {"id": "sc1", "time": "夜", "location": "港口", "emotion": "紧张"},
            {"id": "sc2", "time": "晨", "location": "宫殿", "emotion": "平静"},
        ],
        "shots": [
            {"id": "s1", "scene_id": "sc1", "action": "追逐"},
            {"id": "s2", "scene_id": "sc2", "action": ""},
        ],
        "transitions": [],
    }
    original = copy.deepcopy(screenplay)
    view = _visual_continuity_shots(screenplay)
    assert view[0]["time"] == "夜" and view[1]["time"] == "晨"
    assert view[0]["location"] == "港口" and view[1]["location"] == "宫殿"
    findings = validate_visual_continuity(view)
    assert {item["code"] for item in findings} == {"LOCATION_JUMP", TIME_JUMP, "EMOTION_DISCONTINUITY"}
    assert screenplay == original
    assert "time" not in screenplay["shots"][0]
    assert "transition" not in screenplay["shots"][1]


def test_shot_level_fields_win_over_scene_and_planned_cut_is_attached():
    screenplay = {
        "scenes": [{"id": "sc1", "time": "夜"}, {"id": "sc2", "time": "午"}],
        "shots": [
            {"id": "s1", "scene_id": "sc1", "time": "黄昏"},
            {"id": "s2", "scene_id": "sc2"},
        ],
        "transitions": [{"id": "t1", "from_shot_id": "s1", "to_shot_id": "s2", "type": "CUT"}],
    }
    view = _visual_continuity_shots(screenplay)
    assert view[0]["time"] == "黄昏"
    assert view[1]["time"] == "午"
    assert view[1]["transition"] == "CUT"
    assert "transition" not in screenplay["shots"][1]
    assert validate_visual_continuity(view) == [_time_jump("s1", "s2")]


def _two_scene_screenplay(client):
    novel = client.post("/api/novels", json={"title": f"视觉连续-{uuid4()}"}).json()
    nid = novel["id"]
    client.post(f"/api/novels/{nid}/chapters", json={"title": "一", "content": "港口夜"})
    client.post(f"/api/novels/{nid}/chapters", json={"title": "二", "content": "宫殿晨"})
    created = client.post(f"/api/novels/{nid}/screenplays", json={}).json()
    base = f"/api/novels/{nid}/screenplays/{created['id']}"
    first, second = created["scenes"]
    edited = client.put(
        f"{base}/scenes/{first['id']}",
        json={"heading": "港口", "time": "夜", "location": "港口", "characters": ["甲"], "action": "追逐", "dialogue": [], "emotion": "紧张"},
    ).json()
    client.put(
        f"{base}/scenes/{second['id']}",
        json={"heading": "宫殿", "time": "晨", "location": "宫殿", "characters": ["乙"], "action": "", "dialogue": [], "emotion": "平静"},
    )
    assert edited["revision"] == 2
    assert client.post(f"{base}/approve").status_code == 200
    assert client.post(f"{base}/shots").status_code == 201
    return nid, created["id"], base


def _snapshot(client, nid, screenplay_id):
    rows = client.get(f"/api/novels/{nid}/screenplays").json()
    return copy.deepcopy(next(row for row in rows if row["id"] == screenplay_id))


def test_service_api_default_cut_then_planned_cut_then_fade():
    client = TestClient(app)
    nid, screenplay_id, base = _two_scene_screenplay(client)
    before = _snapshot(client, nid, screenplay_id)
    assert not before.get("transitions")
    unplanned = client.get(f"{base}/visual-continuity")
    assert unplanned.status_code == 200
    payload = unplanned.json()
    assert payload["screenplay_id"] == screenplay_id
    codes = {item["code"] for item in payload["findings"]}
    assert TIME_JUMP in codes
    assert "LOCATION_JUMP" in codes
    assert "EMOTION_DISCONTINUITY" in codes
    assert [item for item in payload["findings"] if item["code"] == TIME_JUMP] == [
        _time_jump(before["shots"][0]["id"], before["shots"][1]["id"])
    ]
    after_unplanned = _snapshot(client, nid, screenplay_id)
    assert after_unplanned == before

    assert client.post(f"{base}/shots/approve").status_code == 200
    planned = client.post(f"{base}/transitions").json()
    assert planned["transitions"][0]["type"] == "CUT"
    planned_revision = planned.get("transition_revision")
    planned_findings = client.get(f"{base}/visual-continuity").json()["findings"]
    assert TIME_JUMP in {item["code"] for item in planned_findings}
    after_planned = _snapshot(client, nid, screenplay_id)
    assert after_planned.get("transition_revision") == planned_revision
    assert after_planned["transitions"][0]["type"] == "CUT"

    tid = planned["transitions"][0]["id"]
    faded = client.put(
        f"{base}/transitions/{tid}",
        json={"type": "FADE", "duration_seconds": 2, "note": "时间跨度", "prompt": "fade"},
    ).json()
    assert faded["transitions"][0]["type"] == "FADE"
    fade_revision = faded.get("transition_revision")
    fade_findings = client.get(f"{base}/visual-continuity").json()["findings"]
    assert TIME_JUMP not in {item["code"] for item in fade_findings}
    assert "EMOTION_DISCONTINUITY" in {item["code"] for item in fade_findings}
    after_fade = _snapshot(client, nid, screenplay_id)
    assert after_fade.get("transition_revision") == fade_revision
    assert after_fade["transitions"][0]["type"] == "FADE"
    assert after_fade["scenes"][0]["time"] == "夜"
    assert "time" not in after_fade["shots"][0]
    assert client.get(f"{base}/visual-continuity").json()["findings"] == fade_findings
    assert _snapshot(client, nid, screenplay_id) == after_fade
