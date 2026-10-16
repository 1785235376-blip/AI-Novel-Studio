"""Original File timeline save/reopen for an exact, manually accepted asset reference.

No render, model, provider discovery, candidate review, or authorization changes.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.asset_providers import AssetProviderRegistry
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_discovered_image_production import owner
from test_v2_independent_workspace import rig, import_asset, reopened


def test_exact_asset_draft_save_reopen_and_cas(rig, monkeypatch):
    production = owner(AssetProviderRegistry(), monkeypatch, rig)
    asset = import_asset(rig)
    reference = {"id": asset["id"], "kind": "ASSET", "asset_kind": "image", "version": asset["version"], "digest": asset["sha256"]}
    current = rig.service.asset(rig.nid, rig.scope, asset["id"])
    assert (current["version"], current["sha256"]) == (reference["version"], reference["digest"])
    timeline = {"schema_version": 2, "duration_ms": 5000, "width": 640, "height": 360, "fps": 24,
        "tracks": [{"id": "visual", "kind": "VIDEO", "order": 0, "muted": False, "gain_db": 0, "role": "PRIMARY",
            "clips": [{"id": "accepted-reference", "source_snapshot": reference, "start_ms": 0, "in_ms": 0, "out_ms": 1000,
                "x": 0, "y": 0, "width": 640, "height": 360, "speed_num": 1, "speed_den": 1, "muted": False,
                "gain_db": 0, "fade_in_ms": 0, "fade_out_ms": 0, "opacity": 1, "include_audio": False}]}], "captions": []}
    body = {"expected_version": 0, "title": "SYNTHETIC accepted asset reference", "timeline": timeline}
    saved = production.timeline_save(rig.nid, rig.scope, rig.actor, None, body, lambda: None)
    fresh_environment = SimpleNamespace(**{**vars(rig), "service": reopened(rig)})
    fresh = owner(AssetProviderRegistry(), monkeypatch, fresh_environment)
    assert fresh.timeline_get(rig.nid, rig.scope, rig.actor, saved["id"], lambda: None) == saved
    assert saved["timeline"]["tracks"][0]["clips"][0]["source_snapshot"] == reference
    update = {**deepcopy(body), "expected_version": 1, "title": "SYNTHETIC explicit title edit"}
    changed = fresh.timeline_save(rig.nid, rig.scope, rig.actor, saved["id"], update, lambda: None)
    assert changed["version"] == 2
    with pytest.raises(CapabilityVersionConflict) as conflict:
        production.timeline_save(rig.nid, rig.scope, rig.actor, saved["id"], update, lambda: None)
    assert conflict.value.current["version"] == 2
    assert fresh.timeline_get(rig.nid, rig.scope, rig.actor, saved["id"], lambda: None) == changed
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 1
