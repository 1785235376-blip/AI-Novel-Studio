"""Legacy audio metadata remains readable without exposing internal history fields."""
import base64
import hashlib
import json

from app.services.asset_library_service import AssetLibraryService


def file_snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_legacy_audio_read_is_private_and_does_not_migrate(tmp_path):
    owner = AssetLibraryService(tmp_path)
    data = b"synthetic legacy audio content"
    audio = owner.create("synthetic-project", "synthetic.wav", base64.b64encode(data).decode(),
                         "audio/wav", "audio")
    legacy = owner.create("synthetic-project", "older.wav", base64.b64encode(data).decode(),
                          "audio/wav", "audio")
    path = owner._meta_path(audio["id"])
    stored = json.loads(path.read_text(encoding="utf-8"))
    # Shape emitted by the published history owner, retained as input only.
    stored["_audio_history_head"] = "a" * 64
    stored["_audio_history_restore_origin"] = {"private": "synthetic-origin"}
    path.write_text(json.dumps(stored), encoding="utf-8")
    before = file_snapshot(tmp_path)

    current = owner.get(audio["id"])
    public = owner.public({"items": [current, owner.get(legacy["id"])]})
    assert public["items"][0]["id"] == audio["id"]
    assert public["items"][1]["id"] == legacy["id"]
    assert "_audio_history_head" not in public["items"][0]
    assert "_audio_history_restore_origin" not in public["items"][0]
    assert owner.content(audio["id"]) == owner.content(legacy["id"]) == data
    assert file_snapshot(tmp_path) == before
    assert not (owner.root / ".audio-history").exists()
