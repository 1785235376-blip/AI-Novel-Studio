"""Independent regression coverage for bounded raster-image inspection cleanup.

The media decoder shares one owned temporary-directory contract: the directory
identity is recorded, release is retried only for the same private empty
directory (Windows child sharing), and a cleanup failure is reported as the
bounded media error rather than a native path/diagnostic. The older image
inspector created a plain ``TemporaryDirectory``; this suite binds the shared
contract to it.

Subprocess tools are replaced with deterministic stand-ins; only synthetic
header bytes are inspected. No real media, project data or native tool is used.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import media_files
from app.media_files import MediaValidationError


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def fake_tools(monkeypatch):
    """Deterministic ffprobe/ffmpeg stand-ins (no native decoder required)."""
    monkeypatch.setattr(media_files.shutil, "which", lambda name: "/synthetic/" + name)
    calls: list[str] = []

    def fake_run(argv, **kwargs):
        calls.append(str(argv[0]))
        if "ffprobe" in str(argv[0]):
            return SimpleNamespace(stdout=b'{"streams": [{"codec_type": "video", "width": 10, "height": 20}]}')
        return SimpleNamespace(stdout=b"", stderr=b"")

    monkeypatch.setattr(media_files.subprocess, "run", fake_run)
    return calls


def test_inspect_image_uses_the_owned_inspection_directory(tmp_path, monkeypatch, fake_tools):
    seen = {}

    @contextmanager
    def recording_directory(prefix="novel-media-"):
        seen["prefix"] = prefix
        yield str(tmp_path)

    monkeypatch.setattr(media_files, "_media_inspection_directory", recording_directory)
    result = media_files.inspect_image(PNG_HEADER)
    assert result == {
        "extension": "png",
        "media_type": "image/png",
        "width": 10,
        "height": 20,
        "validation": "DECODED",
    }
    assert seen["prefix"] == "novel-image-"
    assert fake_tools  # the deterministic decoder path really ran


def test_inspect_image_reports_cleanup_failure_as_bounded_media_error(fake_tools, monkeypatch):
    def failing_cleanup(temporary, identity):
        raise OSError(32, "synthetic sharing violation at C:\\private\\path")

    monkeypatch.setattr(media_files, "_cleanup_media_directory", failing_cleanup)
    with pytest.raises(MediaValidationError) as caught:
        media_files.inspect_image(PNG_HEADER)
    assert str(caught.value) == "image temporary directory cleanup failed"
    # The native diagnostic/path must not leak through the media error.
    assert "private" not in str(caught.value)


def test_owned_empty_media_directory_rejects_replaced_or_nonempty_tree(tmp_path):
    owned = tmp_path / "owned"
    owned.mkdir()
    stat = owned.lstat()
    identity = (stat.st_dev, stat.st_ino)
    assert media_files._owned_empty_media_directory(owned, identity) is True

    replacement = tmp_path / "replacement"
    replacement.mkdir()
    assert media_files._owned_empty_media_directory(replacement, identity) is False

    (owned / "later-content.txt").write_text("synthetic", encoding="utf-8")
    assert media_files._owned_empty_media_directory(owned, identity) is False
    assert media_files._owned_empty_media_directory(owned, None) is False
