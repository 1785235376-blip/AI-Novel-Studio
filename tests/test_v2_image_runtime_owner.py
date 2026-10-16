"""Real original File/PG owners and synthetic HTTP; no model inference claim."""
from copy import deepcopy
import base64

import pytest

from app.creative.production_execution_models import MediaCommand, MediaJobAction, MediaReview
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_owner import mask, save
from test_v2_manual_mask_pixels import source_png
from test_v2_discovered_image_production import owner, command
from test_v2_image_discovery_capabilities import enabled
from test_v2_image_provider_recipes import Transport, Response, png


def snapshot(row):
    return {"kind": "ASSET", "asset_kind": "image", "id": row["id"], "version": row["version"], "digest": row["sha256"]}


def runtime(e, tmp_path, monkeypatch, operation="reference", kind="COMFYUI"):
    model = "sdxl-fixture.safetensors" if kind == "COMFYUI" else "SDXL.safetensors"
    original, registry, adapter, _ = enabled(tmp_path, model, kind)
    production = owner(registry, monkeypatch, e)
    transport = Transport()
    adapter.delegate.transport = transport
    value = command(adapter, "image-runtime-" + operation)
    value.update(operation_id="m5.image." + operation, parameters={"seed": 3, "denoising_strength": .4})
    base = snapshot(e.source)
    if operation == "inpaint":
        authored = save(e)["asset"]
        painted = snapshot(authored)
        value.update(image_source=base, mask_source=painted, source_snapshots=[base, painted])
    else:
        with e.service._asset_scope(e.nid, e.scope):
            other = e.assets.create(e.nid, "reference.png", base64.b64encode(source_png()).decode(),
                "image/png", "image", "reference-image", required_features=("narrative_production_v2",))
        auxiliary = snapshot(other)
        value["source_snapshots"] = [base, auxiliary]
        if operation == "reference":
            value["image_references"] = [{"source": base, "weight": 1.0}, {"source": auxiliary, "weight": .25}]
        else:
            value.update(image_source=base, image_references=[{"source": auxiliary, "weight": .25}])
    return original, adapter, production, transport, value


def queued(e, production, value):
    preview, _, _ = production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    job = production.create(e.nid, e.scope, e.actor,
        {"command": value, "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    return preview, job


def action(job):
    return MediaJobAction(expected_version=job["version"], expected_request_digest=job["request_digest"])


@pytest.mark.parametrize("operation", ["reference", "i2i", "inpaint"])
def test_runtime_original_job_private_review_asset_and_reopen(mask, tmp_path, monkeypatch, operation):
    e = mask
    original, adapter, production, wire, value = runtime(e, tmp_path, monkeypatch, operation)
    initial = e.service.asset(e.nid, e.scope, e.source["id"])
    preview, job = queued(e, production, value)
    assert job["status"] == "QUEUED" and job["output_candidate"] is None
    assert preview["execution_recipe"]["reference_weights"] == ([1.0] if operation == "inpaint" else [1.0, .25])
    assert preview["execution_recipe"]["workflow"]["4"]["inputs"]["ckpt_name"] == "sdxl-fixture.safetensors"
    ready = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    assert ready["status"] == "AWAITING_REVIEW" and ready["approved_asset_version"] is None
    assert ready["command"]["parameters"]["denoising_strength"] == .4
    submitted = next(kwargs["json"]["prompt"] for url, kwargs in wire.calls if url.endswith("/prompt"))
    assert submitted["3"]["inputs"]["denoise"] == .4
    if operation == "inpaint":
        assert submitted["5"]["inputs"]["mask"] == ["27", 0]
        assert submitted["9"]["inputs"]["images"] == ["28", 0]
    else:
        assert submitted["31"]["inputs"]["blend_factor"] == .2
    candidate = ready["output_candidate"]
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate["id"])
    restored = owner(production.image_registry, monkeypatch, type("Env", (), {
        "service": reopened(e), "nid": e.nid, "scope": e.scope, "actor": e.actor, "root": e.root})())
    public = restored.get(e.nid, e.scope, e.actor, "image", job["id"], lambda: None)
    assert public["command"] == ready["command"] and public["execution_recipe"] == ready["execution_recipe"]
    approved = restored.review(e.nid, e.scope, e.actor, "image", job["id"], MediaReview(
        expected_version=ready["version"], expected_request_digest=ready["request_digest"],
        reviewed_output_digest=candidate["digest"]), lambda: None)
    assert approved["status"] == "APPROVED"
    formal = e.service.asset(e.nid, e.scope, candidate["id"])
    assert formal["version"] == candidate["version"] + 1 and formal["sha256"] == candidate["digest"]
    assert e.service.asset(e.nid, e.scope, e.source["id"]) == initial
    assert original.center.lifecycle.start.call_count == 0


def test_weights_and_exact_source_roles_are_in_reviewed_identity(mask, tmp_path, monkeypatch):
    e = mask
    _, _, production, wire, value = runtime(e, tmp_path, monkeypatch)
    preview, job = queued(e, production, value)
    changed = deepcopy(value); changed["image_references"][1]["weight"] = .75
    next_preview, _, _ = production.preview(e.nid, e.scope, e.actor, changed, lambda: None)
    assert next_preview["request_digest"] != preview["request_digest"]
    assert next_preview["execution_recipe"]["workflow"]["31"]["inputs"]["blend_factor"] != .2
    with pytest.raises(StaleSourceError, match="PREVIEW_CHANGED"):
        production.create(e.nid, e.scope, e.actor, {"command": changed,
            "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    assert wire.calls == [] and job["status"] == "QUEUED"


@pytest.mark.parametrize("phase", ["preview", "execute", "review"])
def test_inpaint_never_refreshes_mask_to_new_original_version(mask, tmp_path, monkeypatch, phase):
    e = mask
    _, _, production, wire, value = runtime(e, tmp_path, monkeypatch, "inpaint")
    job = None
    if phase != "preview": _, job = queued(e, production, value)
    if phase == "review": job = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    with e.service._asset_scope(e.nid, e.scope):
        e.assets.update_metadata(e.source["id"], {"scene_id": "source-edited"}, expected_version=1)
    before = len(wire.calls)
    with pytest.raises(StaleSourceError):
        if phase == "preview": production.preview(e.nid, e.scope, e.actor, value, lambda: None)
        elif phase == "execute": production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
        else: production.review(e.nid, e.scope, e.actor, "image", job["id"], MediaReview(
            expected_version=job["version"], expected_request_digest=job["request_digest"],
            reviewed_output_digest=job["output_candidate"]["digest"]), lambda: None)
    assert len(wire.calls) == before
    if phase == "review":
        with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, job["output_candidate"]["id"])


def test_inpaint_rejects_another_formal_image_as_unauthored_mask(mask, tmp_path, monkeypatch):
    e = mask
    _, _, production, wire, value = runtime(e, tmp_path, monkeypatch, "i2i")
    value.update(operation_id="m5.image.inpaint", mask_source=value["source_snapshots"][1])
    value.pop("image_references")
    with pytest.raises(ValueError): production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    assert wire.calls == []


def test_revoke_registration_after_reference_upload_never_promotes_result(mask, tmp_path, monkeypatch):
    e = mask
    original, adapter, production, wire, value = runtime(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    wire.after_upload = lambda: original.disable(adapter.candidate["id"])
    failed = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    assert failed["status"] == "UNKNOWN" and failed["output_candidate"] is None
    assert len([url for url, _ in wire.calls if url.endswith("/upload/image")]) == 1
    assert not any(url.endswith("/prompt") for url, _ in wire.calls)


def test_inpaint_source_change_before_atomic_queue_write_creates_no_job(mask, tmp_path, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = mask
    _, _, production, wire, value = runtime(e, tmp_path, monkeypatch, "inpaint")
    preview, _, _ = production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    original = ImageJobService.create_studio
    def changed(service, *args, **kwargs):
        with e.service._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(e.source["id"], {"scene_id": "changed-before-queue"}, expected_version=1)
        return original(service, *args, **kwargs)
    monkeypatch.setattr(ImageJobService, "create_studio", changed)
    with pytest.raises(StaleSourceError):
        production.create(e.nid, e.scope, e.actor, {"command": value,
            "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    rows = production._image(e.actor).list_studio(e.nid, e.scope.get("branch_id"), e.actor,
        production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None)
    assert rows == [] and wire.calls == []


def test_inpaint_lineage_revocation_at_final_review_commit_keeps_private_asset(mask, tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.services.asset_library_service import AssetLibraryService
    e = mask
    _, _, production, _, value = runtime(e, tmp_path, monkeypatch, "inpaint")
    _, job = queued(e, production, value)
    ready = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    original = AssetLibraryService.promote_owned
    def revoked(assets, *args, **kwargs):
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2")
        return original(assets, *args, **kwargs)
    monkeypatch.setattr(AssetLibraryService, "promote_owned", revoked)
    with pytest.raises(HTTPException) as denied:
        production.review(e.nid, e.scope, e.actor, "image", ready["id"], MediaReview(
            expected_version=ready["version"], expected_request_digest=ready["request_digest"],
            reviewed_output_digest=ready["output_candidate"]["digest"]), lambda: None)
    assert denied.value.status_code == 404 and denied.value.detail == {
        "code": "EXPERIMENTAL_FEATURE_DISABLED", "feature": "asset_lineage_v2"}
    aid = ready["output_candidate"]["id"]
    raw = e.assets._load(aid)
    assert raw["version"] == 1 and raw["_owner_actor_id"] == e.actor
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, aid)


def test_upscale_extension_is_closed_and_non_executable():
    from app.services.studio_image_upscale_contract import ReservedImageUpscaleInput, reservation
    source = {"kind": "ASSET", "asset_kind": "image", "id": "source", "version": 1, "digest": "a" * 64}
    assert ReservedImageUpscaleInput(source=source, scale=2).output_format == "PNG"
    assert reservation()["execution_available"] is False and reservation()["status"] == "NOT_CONFIGURED"
    with pytest.raises(ValueError): ReservedImageUpscaleInput(source=source, scale=2, command="shell")
    with pytest.raises(ValueError): MediaCommand(operation_id="m5.image.upscale", request_id="not-executable")


@pytest.mark.parametrize("kind", ["COMFYUI", "AUTOMATIC1111"])
def test_original_provider_listing_requires_structural_evidence_and_stays_passive(tmp_path, monkeypatch, kind):
    model = "sdxl-fixture.safetensors" if kind == "COMFYUI" else "SDXL.safetensors"
    original, registry, adapter, _ = enabled(tmp_path, model, kind)
    production = owner(registry, monkeypatch)
    before = deepcopy(original.client.calls)
    rows = production.providers("project", {}, "author", lambda: None)["items"]
    assert {row["operation_id"] for row in rows} == ({"m5.image.t2i", "m5.image.i2i", "m5.image.inpaint"}
        | ({"m5.image.reference"} if kind == "COMFYUI" else set()))
    assert all(row["image_capabilities"]["inference_verified"] is False for row in rows)
    assert all(row["product_acceptance"] == "LOCAL_REQUIRED" for row in rows)
    assert original.client.calls == before and original.center.lifecycle.start.call_count == 0


def test_legacy_default_serialization_omits_only_new_unset_fields():
    original = MediaCommand(operation_id="m5.image.t2i", request_id="legacy", provider_id="provider",
        model_id="model", prompt="p")
    body = original.model_dump()
    assert not {"image_source", "image_references", "mask_source"}.intersection(body)
    assert "denoising_strength" not in body["parameters"] and body["parameters"]["width"] is None
    assert MediaCommand.model_validate({**body, "image_references": []}).model_dump() == body


@pytest.mark.parametrize("mutation", ["duplicate", "reordered", "weight-zero", "weight-nan", "missing-base", "unused", "t2i"])
def test_closed_command_never_accepts_ambiguous_reference_roles(mutation):
    first = {"kind": "ASSET", "asset_kind": "image", "id": "base", "version": 1, "digest": "a" * 64}
    second = {**first, "id": "reference"}
    body = {"operation_id": "m5.image.i2i", "request_id": "closed", "provider_id": "provider", "model_id": "model",
        "prompt": "p", "image_source": first, "image_references": [{"source": second, "weight": .5}],
        "source_snapshots": [first, second]}
    if mutation == "duplicate": body["image_references"][0]["source"] = first
    elif mutation == "reordered": body["source_snapshots"].reverse()
    elif mutation == "weight-zero": body["image_references"][0]["weight"] = 0
    elif mutation == "weight-nan": body["image_references"][0]["weight"] = float("nan")
    elif mutation == "missing-base": body.pop("image_source")
    elif mutation == "unused": body["source_snapshots"].append({**first, "id": "unused"})
    else: body["operation_id"] = "m5.image.t2i"
    with pytest.raises(ValueError): MediaCommand.model_validate(body)
