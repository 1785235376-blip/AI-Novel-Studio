"""Local VIDEO timeline render: synthetic MP4 track -> REVIEW_MP4 candidate.

File backend + real FFmpeg; no model/provider call. Not an external NLE run.
"""
from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess

import pytest

from app.creative.production_execution_models import MediaReview
from app.services.studio_timeline_export import probe_media_file
from test_studio_asset_query import rig
from test_studio_backend_integration_v2 import studio

pytestmark = pytest.mark.file_backend_only


def synthetic_video(path):
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "installed CPU FFmpeg is required"
    result = subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", "-threads", "1",
        "-f", "lavfi", "-i", "color=c=red:s=64x64:r=25:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "mpeg4", "-c:a", "aac",
        "-ar", "48000", "-ac", "2", "-threads", "1", "-y", str(path)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return path.read_bytes()


def import_video(e, data):
    with e.workspace._asset_scope(e.nid, e.scope):
        return e.workspace.assets.create(
            e.nid, "synthetic-local.mp4", base64.b64encode(data).decode("ascii"),
            "video/mp4", "video", None,
            required_features=("narrative_production_v2",), _capacity_admitted=True)


def snapshot(asset):
    return {"kind": "ASSET", "asset_kind": asset["kind"], "id": asset["id"],
            "version": asset["version"], "digest": asset["sha256"]}


def test_local_video_timeline_render_to_review_mp4(studio, tmp_path, monkeypatch):
    e = studio
    data = synthetic_video(tmp_path / "synthetic-source.mp4")
    asset = import_video(e, data)
    timeline = {"schema_version": 2, "duration_ms": 1000, "width": 320, "height": 180, "fps": 25,
                "tracks": [{"id": "video-track", "kind": "VIDEO", "order": 0, "clips": [{
                    "id": "video-clip", "source_snapshot": snapshot(asset),
                    "start_ms": 0, "in_ms": 0, "out_ms": 1000, "include_audio": True}]}],
                "captions": []}
    saved = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {"expected_version": 0, "title": "Local synthetic video render", "timeline": timeline}, lambda: None)
    body = {"expected_version": saved["version"], "reviewed_timeline_digest": saved["timeline_digest"],
            "export_profile": {"preset": "REVIEW_MP4"}}
    preview = e.production.timeline_export_preview(e.nid, e.scope, e.actor, saved["id"], body, lambda: None)
    result = e.production.timeline_export(e.nid, e.scope, e.actor, saved["id"],
        {**body, "request_id": "local-video-render", "reviewed_export_digest": preview["preview_digest"]},
        lambda: None)
    assert result["status"] == "SUCCEEDED", result
    assert result["output_candidate"]["kind"] == "video"
    metadata, output = e.production.candidate(e.nid, e.scope, e.actor, "timeline", result["id"], lambda: None)
    assert metadata["sha256"] == hashlib.sha256(output).hexdigest() == result["output_candidate"]["digest"]
    path = tmp_path / "rendered-review.mp4"
    path.write_bytes(output)
    probe = probe_media_file(path, guard=lambda: None)
    streams = {row["codec_type"]: row for row in probe["streams"]}
    assert streams["video"]["codec_name"] == "mpeg4"
    assert streams["video"]["width"] == 320 and streams["video"]["height"] == 180
    assert streams["audio"]["codec_name"] == "aac"
    assert int(streams["audio"]["sample_rate"]) == 48000 and streams["audio"]["channels"] == 2
    duration_ms = round(float(probe["format"]["duration"]) * 1000)
    assert 900 <= duration_ms <= 1100
    review = MediaReview(expected_version=result["version"],
                         expected_request_digest=result["request_digest"],
                         reviewed_output_digest=result["output_candidate"]["digest"])
    approved = e.production.review(e.nid, e.scope, e.actor, "timeline", result["id"], review, lambda: None)
    assert approved["status"] == "APPROVED"
    with e.workspace._asset_scope(e.nid, e.scope):
        formal = e.workspace.assets.content(result["output_candidate"]["id"], branch_id=e.scope.get("branch_id"))
    assert formal == output
