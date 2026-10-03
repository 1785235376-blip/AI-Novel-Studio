from app.services.user_preference_service import UserPreferenceService

def test_preferences_are_explicit_and_separate(tmp_path):
    service=UserPreferenceService(tmp_path)
    assert service.list()=={"enabled":True,"share_enabled":False,"harness_enabled":False,"items":[]}
    saved=service.upsert("chapter_length","约 3000 字")
    assert saved["source"]=="explicit" and saved["confidence"]==1
    assert UserPreferenceService(tmp_path).list()["items"][0]["content"]=="约 3000 字"

def test_preferences_can_be_disabled_and_deleted(tmp_path):
    service=UserPreferenceService(tmp_path);service.upsert("tone","克制")
    assert service.set_enabled(False) is False
    assert service.list()["enabled"] is False
    service.delete("tone")
    assert service.list()["items"]==[]


def test_preference_permissions_are_independent_and_persistent(tmp_path):
    service = UserPreferenceService(tmp_path)
    service.upsert("tone", "克制")
    service.set_enabled(False)
    service.set_share_enabled(True)
    state = UserPreferenceService(tmp_path).list()
    assert state["enabled"] is False
    assert state["share_enabled"] is True
    assert state["harness_enabled"] is False

    service.set_harness_enabled(True)
    enabled_state = UserPreferenceService(tmp_path).list()
    assert enabled_state == {**state, "harness_enabled": True}

    service.set_harness_enabled(False)
    assert UserPreferenceService(tmp_path).list() == state


def test_legacy_preferences_do_not_implicitly_authorize_harness(tmp_path):
    service = UserPreferenceService(tmp_path)
    service.path.write_text('{"enabled": true, "share_enabled": true, "items": {}}', encoding="utf-8")
    assert service.list() == {
        "enabled": True,
        "share_enabled": True,
        "harness_enabled": False,
        "items": [],
    }
