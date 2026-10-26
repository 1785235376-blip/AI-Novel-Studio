"""Native Windows metadata signatures under the original File/HTTP owners."""
import os

import pytest

from test_studio_asset_query import rig
from app.services import asset_query_index as index_module
from app.services.asset_query_index import FileAssetQueryIndex, AssetQueryChanged

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != "nt", reason="Native Windows ChangeTime")]


def replace_preserving_stat(path, before=b'"before.png"', after=b'"afters.png"'):
    previous = path.stat()
    data = path.read_bytes()
    changed = data.replace(before, after)
    assert changed != data and len(changed) == len(data)
    path.write_bytes(changed)
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    current = path.stat()
    assert (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) == (
        previous.st_dev, previous.st_ino, previous.st_size, previous.st_mtime_ns)


def test_same_length_restored_mtime_edit_is_visible_in_filtered_http(rig):
    saved = rig.seed("before.png")
    url = f"/api/projects/{rig.nid}/studio/assets"
    initial = rig.client.get(url, params={"q": "before", "limit": 10})
    assert initial.status_code == 200 and initial.json()["total"] == 1
    path = rig.assets.root / (saved["id"] + ".json")
    replace_preserving_stat(path)
    result = rig.client.get(url, params={"q": "afters", "limit": 10})
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1 and result.json()["items"][0]["id"] == saved["id"]
    assert rig.client.get(url, params={"q": "before", "limit": 10}).json()["total"] == 0


def test_native_change_invalidates_snapshot_and_cold_index_revision(rig):
    saved = rig.seed("before.png")
    index = FileAssetQueryIndex(rig.assets.root)
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        original = index.snapshot(rig.assets._load)
        path = rig.assets.root / (saved["id"] + ".json")
        replace_preserving_stat(path)
        with pytest.raises(AssetQueryChanged):
            index.verify(original)
        reopened = FileAssetQueryIndex(rig.assets.root)
        current = reopened.snapshot(rig.assets._load)
        assert current.revision != original.revision
        reopened.verify(current)


def test_missing_native_capability_cannot_silently_reuse_warm_cache(rig, monkeypatch):
    rig.seed("before.png")
    url = f"/api/projects/{rig.nid}/studio/assets"
    assert rig.client.get(url, params={"limit": 10}).status_code == 200
    path = rig.assets.root / ".asset-query-index" / "index.sqlite3"
    previous = path.read_bytes()
    def unavailable():
        raise OSError("private-native-diagnostic")
    monkeypatch.setattr(index_module, "_windows_signature_api", unavailable)
    result = rig.client.get(url, params={"limit": 10})
    assert result.status_code == 503, result.text
    assert "ASSET_QUERY_INDEX_UNAVAILABLE" in result.text and "private-native-diagnostic" not in result.text
    assert path.read_bytes() == previous


def test_empty_corrupt_metadata_keeps_original_owner_exclusion(rig):
    saved = rig.seed("before.png")
    (rig.assets.root / "empty-metadata.json").write_bytes(b"")
    result = rig.client.get(f"/api/projects/{rig.nid}/studio/assets", params={"limit": 10})
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1 and result.json()["items"][0]["id"] == saved["id"]
