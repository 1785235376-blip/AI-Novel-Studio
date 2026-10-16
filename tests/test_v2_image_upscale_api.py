"""Upscale through original Host/API, File/PG stores and human review.

HTTP is synthetic; returned CPU-generated PNG is really decoded. Model
inference, Windows installation and GPU acceptance remain LOCAL_REQUIRED.
"""
import base64
from copy import deepcopy

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action, assert_success_private_headers
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import command
from test_v2_image_runtime_owner import snapshot
from test_v2_image_upscale import upscale_info, UpscaleTransport, png_size


def setup(e, monkeypatch, scale=2):
    original, registry, adapter, _ = enabled(e.root, "SwinIR_4x.pth", info=upscale_info("SwinIR_4x.pth"))
    monkeypatch.setattr(e.production, "image_registry", registry)
    wire = UpscaleTransport("SwinIR_4x.pth", scale)
    adapter.delegate.transport = wire
    asset = checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json={
        "filename": "upscale-source.png", "kind": "image", "idempotency_key": "upscale-source",
        "content_base64": base64.b64encode(png_size(64, 64)).decode()}), 201)
    value = command(adapter, "mounted-upscale")
    value.update(operation_id="m5.image.upscale", prompt="", parameters={"scale": scale},
        image_source=snapshot(asset), source_snapshots=[snapshot(asset)])
    return original, wire, value, asset


@pytest.mark.parametrize("scale", [2, 4])
def test_original_api_upscale_private_candidate_review_and_source_preservation(image_client, monkeypatch, scale):
    e = image_client
    original, wire, value, source = setup(e, monkeypatch, scale)
    response = e.client.post(e.base + "/preview", headers=e.headers, json=value)
    preview = checked(response); assert_success_private_headers(response)
    assert preview["execution_recipe"]["target_dimensions"] == {"width": 64 * scale, "height": 64 * scale}
    assert wire.calls == []
    job = checked(e.client.post(e.base + "/jobs", headers=e.headers,
        json={"command": value, "reviewed_preview_digest": preview["preview_digest"]}), 201)
    path = e.base + "/jobs/image/" + job["id"]
    ready = checked(e.client.post(path + "/execute", headers=e.headers, json=action(job)))
    assert ready["status"] == "AWAITING_REVIEW" and ready["processing_proof"]["scale"] == scale
    before = checked(e.client.get(e.studio_base + "/assets", headers=e.headers))["items"]
    assert {row["id"] for row in before} == {source["id"]}
    rejected = e.client.post(path + "/review", headers=e.headers,
        json={**action(ready), "reviewed_output_digest": "0" * 64})
    assert rejected.status_code == 422
    approved = checked(e.client.post(path + "/review", headers=e.headers,
        json={**action(ready), "reviewed_output_digest": ready["output_candidate"]["digest"]}))
    assert approved["status"] == "APPROVED" and approved["approved_asset_version"] == 2
    after = checked(e.client.get(e.studio_base + "/assets", headers=e.headers))["items"]
    assert len(after) == 2
    assert next(row for row in after if row["id"] == source["id"])["version"] == source["version"]
    assert original.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("change", ["untrusted", "stale", "prompt", "scale", "workflow", "cloud", "no-source"])
def test_upscale_rejects_invalid_authority_or_nonclosed_inputs(image_client, monkeypatch, change):
    e = image_client
    _, wire, value, _ = setup(e, monkeypatch)
    value = deepcopy(value); headers = e.headers
    if change == "untrusted": headers = {"X-Session-Token": "untrusted"}
    elif change == "stale": value["image_source"]["version"] += 1
    elif change == "prompt": value["prompt"] = "must not be ignored"
    elif change == "scale": value["parameters"]["scale"] = 3
    elif change == "workflow": value["parameters"]["workflow"] = {"command": "arbitrary"}
    elif change == "cloud": value["allow_cloud"] = True
    else: value.pop("image_source")
    result = e.client.post(e.base + "/preview", headers=headers, json=value)
    assert result.status_code == (401 if change == "untrusted" else 422), result.text
    assert wire.calls == []
