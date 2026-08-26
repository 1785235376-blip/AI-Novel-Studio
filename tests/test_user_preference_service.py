from app.services.user_preference_service import UserPreferenceService

def test_preferences_are_explicit_and_separate(tmp_path):
    service=UserPreferenceService(tmp_path)
    assert service.list()=={"enabled":True,"share_enabled":False,"items":[]}
    saved=service.upsert("chapter_length","约 3000 字")
    assert saved["source"]=="explicit" and saved["confidence"]==1
    assert UserPreferenceService(tmp_path).list()["items"][0]["content"]=="约 3000 字"

def test_preferences_can_be_disabled_and_deleted(tmp_path):
    service=UserPreferenceService(tmp_path);service.upsert("tone","克制")
    assert service.set_enabled(False) is False
    assert service.list()["enabled"] is False
    service.delete("tone")
    assert service.list()["items"]==[]
