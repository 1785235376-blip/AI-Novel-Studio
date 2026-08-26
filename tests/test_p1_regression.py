from app.api import normalize_world_rule_payload, summarize_foreshadowing
from app.review import deterministic_review
from app.services.screenplay_service import suggest_transition_type, validate_visual_continuity, require_motion_frames
from app.services.screenplay_service import ScreenplayService
from app.api import MotionResultIn


def test_foreshadowing_summary_tracks_pending_overdue_and_paid_off():
    result = summarize_foreshadowing([
        {"id": "open", "status": "OPEN", "target_chapter": 8},
        {"id": "future", "status": "PLANTED", "target_chapter": 12},
        {"id": "paid", "status": "PAID_OFF", "target_chapter": 4},
    ], chapter=10)
    assert [row["id"] for row in result["pending"]] == ["open", "future"]
    assert [row["id"] for row in result["overdue"]] == ["open"]
    assert [row["id"] for row in result["paid_off"]] == ["paid"]


def test_character_consistency_rules_share_stable_codes():
    findings = deterministic_review(
        "周启走进门，林海已经31岁。",
        {"chapter": 2, "characters": [
            {"name": "周启", "status": "MISSING"},
            {"name": "林海", "age": 29},
        ]},
    )
    assert {item["code"] for item in findings} == {"MISSING_CHARACTER", "CANON_CONFLICT"}


def test_world_rule_normalization_is_compatible_with_continuity_payload():
    payload = normalize_world_rule_payload({"statement": "魔法需要代价", "forbidden_terms": ["无代价", "无代价", ""]})
    assert payload == {"statement": "魔法需要代价", "forbidden_terms": ["无代价"]}

def test_transition_suggestion_prioritizes_location_then_time_then_emotion():
    assert suggest_transition_type({"action":"推开门"},{"action":"推开门后拔剑"})[0] == "MATCH"
    assert suggest_transition_type({"action":"他转身，奔跑。"},{"action":"镜头跟随奔跑！"})[0] == "MATCH"
    assert suggest_transition_type({"location":"港口","time":"夜","emotion":"紧张"},{"location":"宫殿","time":"夜","emotion":"紧张"})[0] == "DISSOLVE"
    assert suggest_transition_type({"location":"港口","time":"夜"},{"location":"港口","time":"晨"})[0] == "FADE"
    assert suggest_transition_type({"location":"港口","emotion":"紧张"},{"location":"港口","emotion":"平静"})[0] == "MATCH"
    assert suggest_transition_type({}, {})[0] == "CUT"

def test_visual_continuity_reports_scene_jumps():
    findings = validate_visual_continuity([
        {"id":"s1","location":"港口","time":"夜","emotion":"紧张","action":"追逐"},
        {"id":"s2","location":"宫殿","time":"晨","emotion":"平静","action":""},
    ])
    assert {item["code"] for item in findings} == {"LOCATION_JUMP", "TIME_JUMP_CUT", "EMOTION_DISCONTINUITY"}
    assert validate_visual_continuity([{ "id":"s1" }, { "id":"s2" }]) == []

def test_motion_result_requires_http_video_url():
    assert MotionResultIn(url='https://cdn.example/video.mp4').media_type == 'video/mp4'
    try:
        MotionResultIn(url='file:///tmp/video.mp4')
        raise AssertionError('expected URL validation failure')
    except ValueError:
        pass

def test_motion_frames_are_required_before_execution():
    try:
        require_motion_frames({'start_frame':'https://a/frame.jpg'})
        raise AssertionError('expected missing end frame failure')
    except ValueError:
        pass
    require_motion_frames({'start_frame':'https://a/start.jpg','end_frame':'https://a/end.jpg'})

def test_motion_callback_payload_model_accepts_progress_and_url():
    from app.api import MotionCallbackIn
    callback=MotionCallbackIn(status='RUNNING',progress=45)
    assert callback.progress == 45
    completed=MotionCallbackIn(status='SUCCEEDED',progress=100,url='https://cdn.example/video.mp4')
    assert completed.url.startswith('https://')

def test_video_provider_config_rejects_non_http_endpoint():
    from app.api import VideoProviderConfigIn, video_callback_security
    try:
        VideoProviderConfigIn(endpoint='file:///tmp/provider', model_id='video')
        raise AssertionError('expected endpoint validation failure')
    except ValueError:
        pass
    assert video_callback_security()['secret_exposed'] is False

def test_http_video_provider_requires_endpoint_and_key():
    from app.asset_providers import HttpVideoProvider
    try:
        HttpVideoProvider(object(), '', '')
        raise AssertionError('expected provider configuration failure')
    except ValueError:
        pass
