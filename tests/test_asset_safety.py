import base64

import pytest

from app.services.asset_library_service import AssetLibraryService


def test_asset_library_normalizes_download_filename_and_mime(tmp_path):
    service = AssetLibraryService(tmp_path)
    item = service.create(
        "novel-a",
        "..\\cover\r\n.png",
        base64.b64encode(b"fixture").decode(),
        "image/png",
    )
    assert item["filename"] == "cover.png"
    assert item["media_type"] == "image/png"


def test_asset_library_rejects_oversize_and_invalid_mime(tmp_path):
    service = AssetLibraryService(tmp_path)
    with pytest.raises(ValueError, match="25 MiB"):
        service.create("novel-a", "large.bin", base64.b64encode(b"x" * (service.MAX_BYTES + 1)).decode())
    with pytest.raises(ValueError, match="media_type"):
        service.create("novel-a", "cover.png", base64.b64encode(b"x").decode(), "image/png\r\nX-Test: bad")
