"""New image roles through original mounted Host/API/File/PG owners."""
import base64
from copy import deepcopy

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action, assert_success_private_headers
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import command
from test_v2_image_runtime_owner import snapshot
from test_v2_manual_mask_pixels import source_png, plane
from test_v2_image_provider_recipes import Transport


def setup(e, monkeypatch, operation):
    original, registry, adapter, _ = enabled(e.root, "sdxl-fixture.safetensors")
    monkeypatch.setattr(e.production, "image_registry", registry)
    wire = Transport(); adapter.delegate.transport = wire
    assets = []
    for index in range(2 if operation == "reference" else 1):
        assets.append(checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json={
            "filename": f"runtime-source-{index}.png", "kind": "image", "idempotency_key": f"image-runtime-{index}",
            "content_base64": base64.b64encode(source_png()).decode()}), 201))
    value = command(adapter, "mounted-runtime-" + operation)
    value.update(operation_id="m5.image." + operation, parameters={"seed": 3, "denoising_strength": .4})
    if operation == "reference":
        value["image_references"] = [{"source": snapshot(row), "weight": weight} for row, weight in zip(assets, [1.0, .25])]
    else:
        authored = checked(e.client.post(e.studio_base + "/assets/" + assets[0]["id"] + "/mask",
            headers=e.headers, json={"contract": "manual-binary-mask/1", "source_version": assets[0]["version"],
                "source_sha256": assets[0]["sha256"], "width": 64, "height": 64,
                "bitplane_base64": plane(), "idempotency_key": "mounted-runtime-mask"}), 201)["asset"]
        value.update(image_source=snapshot(assets[0]), mask_source=snapshot(authored))
        assets.append(authored)
    value["source_snapshots"] = [snapshot(row) for row in assets]
    return original, wire, value, assets


@pytest.mark.parametrize("operation", ["reference", "inpaint"])
def test_original_api_accepts_exact_roles_and_requires_explicit_review(image_client, monkeypatch, operation):
    e = image_client
    original, wire, value, inputs = setup(e, monkeypatch, operation)
    response = e.client.post(e.base + "/preview", headers=e.headers, json=value)
    captured = checked(response); assert_success_private_headers(response)
    assert captured["command"]["operation_id"] == value["operation_id"] and captured["automatic_dispatch"] is False
    assert captured["execution_recipe"]["reference_weights"] == ([1.0, .25] if operation == "reference" else [1.0])
    assert wire.calls == []
    queued = checked(e.client.post(e.base + "/jobs", headers=e.headers,
        json={"command": value, "reviewed_preview_digest": captured["preview_digest"]}), 201)
    path = e.base + "/jobs/image/" + queued["id"]
    ready = checked(e.client.post(path + "/execute", headers=e.headers, json=action(queued)))
    assert ready["status"] == "AWAITING_REVIEW" and ready["output_candidate"] is not None
    formal_before = checked(e.client.get(e.studio_base + "/assets", headers=e.headers))["items"]
    assert {row["id"] for row in formal_before} == {row["id"] for row in inputs}
    wrong = e.client.post(path + "/review", headers=e.headers,
        json={**action(ready), "reviewed_output_digest": "0" * 64})
    assert wrong.status_code == 422 and checked(e.client.get(path, headers=e.headers))["status"] == "AWAITING_REVIEW"
    approved = checked(e.client.post(path + "/review", headers=e.headers,
        json={**action(ready), "reviewed_output_digest": ready["output_candidate"]["digest"]}))
    assert approved["status"] == "APPROVED" and approved["approved_asset_version"] == 2
    formal = checked(e.client.get(e.studio_base + "/assets", headers=e.headers))["items"]
    assert len(formal) == len(inputs) + 1
    assert original.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("change", ["untrusted", "reordered", "wrong-version", "extra-workflow"])
def test_new_reference_fields_do_not_expand_authority_or_arbitrary_execution(image_client, monkeypatch, change):
    e = image_client
    _, wire, body, _ = setup(e, monkeypatch, "reference")
    body = deepcopy(body); headers = e.headers
    if change == "untrusted": headers = {"X-Session-Token": "untrusted"}
    elif change == "reordered": body["source_snapshots"].reverse()
    elif change == "wrong-version": body["image_references"][0]["source"]["version"] += 1
    else: body["image_references"][0]["workflow"] = {"command": "arbitrary"}
    result = e.client.post(e.base + "/preview", headers=headers, json=body)
    assert result.status_code == (401 if change == "untrusted" else 422), result.text
    assert wire.calls == []
