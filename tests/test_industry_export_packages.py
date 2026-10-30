"""Industry export packaging: screenplay / shot-list / storyboard ZIPs.

Synthetic snapshots only; no models, providers, credentials or user manuscripts.
Covers declared package layout, manifest and missing-resource inventory,
resource digest/ownership verification, deterministic bytes, CSV safety and the
absence of environment/secrets in artifacts (issue #17 evidence for the
already-integrated exporters).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from zipfile import ZipFile

import pytest

from app.industry_export_formats import (
    IndustryExportResourceError,
    IndustryExportValidationError,
    screenplay_to_fountain,
    screenplay_to_package,
    shot_list_to_csv,
    shot_list_to_package,
    storyboard_to_package,
    storyboard_to_html,
)

NOVEL_ID = "synthetic-novel"


def screenplay(asset_id="asset-001"):
    return {
        "id": "screenplay-1",
        "title": "Synthetic 剧本",
        "revision": 3,
        "shot_revision": 4,
        "storyboard_revision": 5,
        "scenes": [{
            "id": "scene-1",
            "heading": "INT. ROOM - DAY",
            "location": "ROOM", "time": "DAY",
            "action": "角色进入房间。",
            "characters": ["角色"],
            "dialogue": [{"character": "角色", "text": "你好。"}],
            "asset_ids": [asset_id],
        }],
        "shots": [{
            "id": "shot-1", "number": 1, "scene_id": "scene-1",
            "shot_size": "WIDE", "camera_angle": "EYE_LEVEL", "camera_motion": "STATIC",
            "action": "角色进入画面。", "duration_seconds": 3.5,
            "sound_effect": "AMBIENCE", "asset_ids": [asset_id],
        }],
        "storyboard": [{
            "id": "card-1", "number": 1, "shot_id": "shot-1", "scene_id": "scene-1",
            "frame_prompt": "角色站在房间中央。", "composition": "CENTER",
            "color": "WARM", "asset_ids": [asset_id],
        }],
    }


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Loader:
    def __init__(self, rows):
        self.rows = rows

    def get(self, asset_id):
        return self.rows[asset_id]["metadata"]

    def content(self, asset_id):
        return self.rows[asset_id]["content"]


def manifest_for(asset_id, content, *, size=None, digest=None):
    return {"referenced": [asset_id], "available": [{
        "id": asset_id, "filename": "frame.png", "media_type": "image/png",
        "sha256": digest or sha(content), "size": len(content) if size is None else size,
        "status": "AVAILABLE"}], "missing": []}


def loader_for(asset_id, content, *, novel_id=NOVEL_ID, digest=None):
    return Loader({asset_id: {"metadata": {
        "id": asset_id, "novel_id": novel_id, "filename": "frame.png",
        "media_type": "image/png", "sha256": digest or sha(content), "size": len(content)},
        "content": content}})


def package_entries(data: bytes):
    with ZipFile(io.BytesIO(data)) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


def test_screenplay_package_layout_manifest_and_determinism():
    first = screenplay_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                                  snapshot_id="snap-1", source_versions={"chapters": []})
    second = screenplay_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                                   snapshot_id="snap-1", source_versions={"chapters": []})
    assert first == second  # deterministic archive bytes/timestamps
    entries = package_entries(first)
    assert {"screenplay.fountain", "screenplay.docx", "manifest.json"} <= set(entries)
    manifest = json.loads(entries["manifest.json"])
    assert manifest["package_type"] == "screenplay"
    assert manifest["schema_version"] == 1 and manifest["format_version"] == "1.0"
    assert manifest["project"] == {"novel_id": NOVEL_ID, "title": "Synthetic 剧本"}
    assert manifest["source"]["snapshot_id"] == "snap-1"
    assert manifest["source"]["screenplay_revision"] == 3
    assert manifest["source"]["shot_revision"] == 4
    assert manifest["source"]["storyboard_revision"] == 5
    assert manifest["files"] == sorted(entries)
    assert manifest["resources"]["referenced"] == ["asset-001"]
    assert manifest["resources"]["available"] == [] and manifest["resources"]["missing_count"] == 1
    assert manifest["resources"]["missing"][0]["reason"] == "asset not listed in snapshot"
    with ZipFile(io.BytesIO(first)) as archive:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())


def test_screenplay_fountain_is_textual_and_contains_heading():
    value = screenplay_to_fountain(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID)
    assert isinstance(value, str) and "INT. ROOM - DAY" in value
    assert value == screenplay_to_fountain(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID)


def test_shot_list_package_and_csv_safety():
    data = shot_list_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID)
    entries = package_entries(data)
    assert {"shot-list.csv", "manifest.json"} <= set(entries)
    manifest = json.loads(entries["manifest.json"])
    assert manifest["package_type"] == "shot-list"
    csv_text = entries["shot-list.csv"].decode("utf-8-sig")
    assert csv_text.startswith("镜号") and "WIDE" in csv_text and "asset-001" in csv_text
    injected = screenplay()
    injected["shots"][0]["action"] = "=HYPERLINK(\"http://evil\")"
    csv_text = shot_list_to_csv(injected, title="Synthetic 剧本", novel_id=NOVEL_ID).decode("utf-8-sig")
    # Formula-leading cells are neutralised with an apostrophe prefix.
    assert '"\'=HYPERLINK' in csv_text
    assert csv_text.startswith("镜号")


def test_storyboard_package_embeds_verified_resource_and_manifest():
    content = b"\x89PNG\r\n\x1a\nsynthetic"
    data = storyboard_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                                 snapshot_id="snap-2",
                                 resource_manifest=manifest_for("asset-001", content),
                                 resource_loader=loader_for("asset-001", content))
    entries = package_entries(data)
    manifest = json.loads(entries["manifest.json"])
    assert manifest["package_type"] == "storyboard"
    assert {"storyboard.html", "shots.csv", "screenplay.fountain", "manifest.json"} <= set(entries)
    resource_keys = [name for name in entries if name.startswith("resources/")]
    assert len(resource_keys) == 1 and entries[resource_keys[0]] == content
    available = manifest["resources"]["available"]
    assert len(available) == 1 and available[0]["id"] == "asset-001"
    assert available[0]["packaged"] is True and available[0]["sha256"] == sha(content)
    html = entries["storyboard.html"].decode("utf-8")
    assert "<!doctype html>" in html and "resources/001-frame.png" in html and "frame.png" in html


def test_missing_resource_policy_inventory_and_fatal_mode():
    data = storyboard_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                                 resource_manifest=manifest_for("asset-001", b"x"),
                                 resource_loader=None,
                                 resource_policy="allow_missing")
    manifest = json.loads(package_entries(data)["manifest.json"])
    assert manifest["resources"]["missing_count"] == 1
    reason = manifest["resources"]["missing"][0]["reason"]
    assert "binary loader not configured" in reason
    with pytest.raises(IndustryExportResourceError) as refused:
        storyboard_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                              resource_manifest=manifest_for("asset-001", b"x"),
                              resource_loader=None, resource_policy="require_all")
    assert refused.value.code == "EXPORT_RESOURCES_MISSING"
    assert refused.value.details["missing_count"] == 1


def test_resource_digest_and_ownership_mismatch_are_not_packaged():
    expected = b"expected-bytes"
    manifest = manifest_for("asset-001", expected)
    # Different bytes: captured digest is authoritative and current metadata
    # cannot bless replaced content.
    data = storyboard_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                                 resource_manifest=manifest,
                                 resource_loader=loader_for("asset-001", b"replaced-bytes"))
    manifest_json = json.loads(package_entries(data)["manifest.json"])
    assert manifest_json["resources"]["missing_count"] == 1
    assert "checksum mismatch" in manifest_json["resources"]["missing"][0]["reason"]
    # Wrong project ownership is rejected even with matching bytes.
    data = storyboard_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID,
                                 resource_manifest=manifest_for("asset-001", expected),
                                 resource_loader=loader_for("asset-001", expected, novel_id="other"))
    assert json.loads(package_entries(data)["manifest.json"])["resources"]["missing_count"] == 1


def test_packages_do_not_contain_environment_secrets(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-synthetic-must-not-leak")
    monkeypatch.setenv("AI_NOVEL_STUDIO_PDF_FONT", "C:/private/font.ttf")
    data = storyboard_to_package(screenplay(), title="Synthetic 剧本", novel_id=NOVEL_ID)
    blob = data
    for entry in package_entries(data).values():
        blob += entry
    assert b"sk-synthetic-must-not-leak" not in blob
    assert b"C:/private/font.ttf" not in blob
    assert b"NOVEL_DATA" not in blob and b"DATABASE_URL" not in blob


def test_packages_reject_screenplay_without_scenes():
    with pytest.raises(IndustryExportValidationError) as invalid:
        screenplay_to_package({"scenes": []}, title="empty", novel_id=NOVEL_ID)
    assert invalid.value.code == "EXPORT_SCHEMA_INVALID"



