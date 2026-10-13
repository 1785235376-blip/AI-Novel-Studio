"""Mounted Storyboard→original Image Job→review→Timeline draft integration.

Original trusted Host/scope/File/PG owners, synthetic HTTP and real tiny PNG
only. Runtime startup, GPU and production model acceptance are not executed.
"""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from test_r3_mounted_contracts import mounted, prefix, checked
from test_v2_independent_workspace_api import client, upload_body
from test_v2_discovered_image_production_api import image_client, action
from test_v2_storyboard_workspace import board_value


@pytest.fixture
def storyboard_client(image_client, monkeypatch):
    from app.creative.graph_asset_inputs import GraphAssetInputs
    e = image_client
    creative = e.experimental.creative_service
    for name, value in (("store", e.studio.store), ("novels", e.novels), ("chapters", e.chapters)):
        monkeypatch.setattr(creative, name, value)
    monkeypatch.setattr(e.studio, "creative", creative)
    monkeypatch.setattr(e.production, "timeline_inputs", GraphAssetInputs(e.production))
    creative.configure_storyboard_production(e.production)
    e.creative = creative
    e.creative_base = e.prefix + f"/novels/{e.nid}/experimental/creative"
    row = checked(e.client.post(e.creative_base + "/documents", headers=e.headers, json=board_value()), 201)
    e.board_path = e.creative_base + "/documents/" + row["id"]
    e.board_id = row["id"]
    return e


def get_storyboard(e):
    return checked(e.client.get(e.board_path + "/storyboard", headers=e.headers))


def capture(e, name, value):
    """Opt-in actual mounted response evidence in a bounded private directory."""
    target = os.getenv("PHASE4_STORYBOARD_CAPTURE")
    if target:
        directory = Path(target).resolve()
        root = Path(__file__).resolve().parents[1]
        assert directory.is_relative_to(root / ".runtime")
        directory.mkdir(parents=True, exist_ok=True)
        filename = e.store.backend + "-" + e.prefix.strip("/").replace("/", "-") + "-" + name + ".json"
        (directory / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def shot_action(receipt, shot_id="shot-1"):
    shot = next(shot for shot in receipt["shots"] if shot["shot_id"] == shot_id)
    return {"expected_version": receipt["document_snapshot"]["version"],
            "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"]}


def approve_board(e, receipt):
    return checked(e.client.post(e.board_path + "/storyboard/approve", headers=e.headers, json={
        "expected_version": receipt["document_snapshot"]["version"], "reviewed_content_digest": receipt["content_digest"]}))


def bind_asset(e, receipt, asset, shot_id="shot-1"):
    return e.client.post(e.board_path + f"/shots/{shot_id}/image-binding", headers=e.headers, json={
        **shot_action(receipt, shot_id), "asset": {"asset_id": asset["id"], "version": asset["version"],
                                                  "digest": asset["sha256"], "kind": "image"}})


def test_mounted_storyboard_image_request_job_review_asset_binding_and_timeline(storyboard_client):
    e = storyboard_client
    board = get_storyboard(e)
    response = e.client.post(e.board_path + "/shots/shot-1/image-request", headers=e.headers, json={
        **shot_action(board), "request_id": "synthetic-storyboard-image", "provider": {key: e.command[key]
            for key in ("operation_id", "provider_id", "model_id")}, "parameters": {"width": 64, "height": 64}})
    requested = checked(response)
    capture(e, "image-request", requested)
    assert requested["automatic_dispatch"] is requested["model_called"] is False
    assert requested["shot_pin"]["document_snapshot"] == board["document_snapshot"]
    assert e.calls == []
    command = requested["command"]
    assert command["source_snapshots"][0]["id"] == e.board_id
    preview = checked(e.client.post(e.base + "/preview", headers=e.headers, json=command))
    job = checked(e.client.post(e.base + "/jobs", headers=e.headers, json={
        "command": command, "reviewed_preview_digest": preview["preview_digest"]}), 201)
    job_path = e.base + "/jobs/image/" + job["id"]
    ready = checked(e.client.post(job_path + "/execute", headers=e.headers, json=action(job)))
    candidate = ready["output_candidate"]
    assert ready["status"] == "AWAITING_REVIEW"
    denied = bind_asset(e, board, {"id": candidate["id"], "version": candidate["version"], "sha256": candidate["digest"]})
    assert denied.status_code in (404, 422), denied.text
    assert get_storyboard(e) == board
    approved = checked(e.client.post(job_path + "/review", headers=e.headers, json={
        **action(ready), "reviewed_output_digest": candidate["digest"]}))
    assert approved["status"] == "APPROVED"
    formal = checked(e.client.get(e.studio_base + "/assets/" + candidate["id"], headers=e.headers))
    attached = checked(bind_asset(e, board, formal))
    attached = checked(bind_asset(e, attached, formal, "shot-2"))
    reviewed = approve_board(e, attached)
    capture(e, "storyboard", reviewed)
    assert reviewed["approved"] and [shot["shot_version"] for shot in reviewed["shots"]] == [1, 1]
    timeline = checked(e.client.post(e.board_path + "/storyboard/timeline-draft", headers=e.headers, json={
        "expected_version": reviewed["document_snapshot"]["version"], "reviewed_content_digest": reviewed["content_digest"],
        "title": "SYNTHETIC storyboard timeline", "shot_ids": ["shot-1", "shot-2"]}), 201)
    capture(e, "timeline-draft", timeline)
    assert timeline["rendered"] is timeline["model_called"] is False
    saved = checked(e.client.get(e.base + "/timelines/" + timeline["timeline"]["id"], headers=e.headers))
    assert saved == timeline["timeline"] and saved["storyboard_origin"] == timeline["storyboard_origin"]
    assert len(checked(e.client.get(e.studio_base + "/assets", headers=e.headers))["items"]) == 1
    assert len(checked(e.client.get(e.base + "/jobs", headers=e.headers))["items"]) == 1
    assert e.discovery.center.lifecycle.start.call_count == 0


def test_mounted_director_camera_visual_rhythm_advice_is_read_only(storyboard_client):
    from test_v2_director_storyboard_production import independent_direction, rich_note
    e = storyboard_client
    authored = independent_direction(director_notes=[rich_note(lighting="Soft key", color_palette="Blue",
        material="Brushed metal", transition="Cut on action")])
    director = checked(e.client.post(e.creative_base + "/documents", headers=e.headers, json=authored), 201)
    path = e.creative_base + "/documents/" + director["id"]
    advice = checked(e.client.get(path + "/director-advice", headers=e.headers))
    capture(e, "director-advice", advice)
    assert advice["advice_only"] and advice["automatic_apply"] is False
    assert advice["notes"][0]["visual_style"]["material"] == "Brushed metal"
    assert advice["notes"][0]["rhythm"]["transition"] == "Cut on action"
    assert checked(e.client.get(path, headers=e.headers)) == director and e.calls == []


@pytest.mark.parametrize("change,status", [("missing", 401), ("forged", 401), ("origin", 403), ("forwarded", 403)])
def test_storyboard_production_endpoints_require_original_trusted_host(storyboard_client, change, status):
    e = storyboard_client
    before = get_storyboard(e)
    headers = {} if change == "missing" else {"X-Session-Token": "forged"} if change == "forged" else (
        {**e.headers, "Origin": "https://untrusted.invalid"} if change == "origin" else {**e.headers, "Forwarded": "for=127.0.0.1"})
    for method, suffix, body in [
        ("GET", "/storyboard", None),
        ("POST", "/storyboard/approve", {"expected_version": 1, "reviewed_content_digest": before["content_digest"]}),
        ("POST", "/shots/shot-1/image-request", {**shot_action(before), "request_id": "forged-image-request",
            "provider": {key: e.command[key] for key in ("operation_id", "provider_id", "model_id")}}),
        ("POST", "/storyboard/timeline-draft", {"expected_version": 1, "reviewed_content_digest": before["content_digest"],
            "title": "Must not save", "shot_ids": ["shot-1"]}),
    ]:
        result = e.client.request(method, e.board_path + suffix, headers=headers, json=body)
        assert result.status_code == status, result.text
    assert get_storyboard(e) == before and e.calls == []


@pytest.mark.parametrize("change", ["privatefields", "wrongkind", "foreign", "stale", "wrongshot", "wrongdigest"])
def test_image_binding_rejects_nonformal_noncurrent_or_unbound_input(storyboard_client, change):
    e = storyboard_client
    board = get_storyboard(e)
    asset = checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json=upload_body()), 201)
    body = {**shot_action(board), "asset": {"asset_id": asset["id"], "version": asset["version"], "digest": asset["sha256"], "kind": "image"}}
    if change == "privatefields": body["asset"]["path"] = "private.png"
    elif change == "wrongkind": body["asset"]["kind"] = "video"
    elif change == "foreign": body["asset"]["asset_id"] = "foreign-project-image"
    elif change == "stale": body["asset"]["version"] += 1
    elif change == "wrongshot": body["shot_version"] += 1
    else: body["shot_digest"] = "0" * 64
    denied = e.client.post(e.board_path + "/shots/shot-1/image-binding", headers=e.headers, json=body)
    assert denied.status_code in (404, 409, 422), denied.text
    assert get_storyboard(e) == board and e.calls == []
