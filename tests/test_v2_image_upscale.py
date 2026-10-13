"""Closed upscale recipe and original File/PG owner; synthetic HTTP, real PNG.

No downloaded models, runtime launch, GPU, or real inference acceptance.
"""
from copy import deepcopy
import base64
from io import BytesIO

from PIL import Image
import pytest

from app.asset_providers import AssetGenerationRequest, ComfyUIImageProvider, validate_image_parameters
from app.creative.production_execution_models import MediaCommand, MediaReview
from app.experimental.common import StaleSourceError
from app.services.studio_image_provider_recipes import build_workflow, project_comfy_image_recipe, validate_workflow
from app.services.studio_image_control_contract import ImageControlInput, reservation
from test_v2_image_provider_recipes import object_info, Transport, Response, inline
from test_v2_image_discovery_capabilities import enabled
from test_v2_image_runtime_owner import snapshot, queued, action, runtime
from test_v2_discovered_image_production import owner, command
from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_owner import mask


def upscale_info(model="RealESRGAN_x4plus.pth"):
    info = object_info()
    info.update({
        "UpscaleModelLoader": {"input": {"required": {"model_name": [[model]]}}, "output": ["UPSCALE_MODEL"]},
        "ImageUpscaleWithModel": {"input": {"required": {"upscale_model": ["UPSCALE_MODEL"], "image": ["IMAGE"]}}, "output": ["IMAGE"]},
        "ImageScale": {"input": {"required": {"image": ["IMAGE"], "upscale_method": [["lanczos"]],
            "width": ["INT", {"min": 1, "max": 16384}], "height": ["INT", {"min": 1, "max": 16384}],
            "crop": [["disabled"]]}}, "output": ["IMAGE"]},
    })
    return info


def png_size(width, height):
    out = BytesIO()
    Image.new("RGB", (width, height), (41, 99, 137)).save(out, format="PNG")
    return out.getvalue()


class UpscaleTransport(Transport):
    def __init__(self, model="RealESRGAN_x4plus.pth", scale=2):
        super().__init__()
        self.info = upscale_info(model)
        self.output = png_size(64 * scale, 64 * scale)

    def get(self, url, **kwargs):
        if url.endswith("/view"):
            self.calls.append((url, kwargs))
            return Response(content=self.output)
        return super().get(url, **kwargs)


def configured(e, tmp_path, monkeypatch, scale=2, model="RealESRGAN_x4plus.pth"):
    original, registry, adapter, _ = enabled(tmp_path, model, info=upscale_info(model))
    production = owner(registry, monkeypatch, e)
    wire = UpscaleTransport(model, scale)
    adapter.delegate.transport = wire
    source = snapshot(e.source)
    value = command(adapter, "image-upscale-" + str(scale))
    value.update(operation_id="m5.image.upscale", prompt="", parameters={"scale": scale},
        image_source=source, source_snapshots=[source])
    return original, adapter, production, wire, value


@pytest.mark.parametrize("model", ["RealESRGAN_x4plus.pth", "SwinIR_4x.pth", "compatible-upscaler.pth"])
def test_exact_loader_schema_supports_compatible_models_without_inference_claim(tmp_path, model):
    original, _, adapter, result = enabled(tmp_path, model, info=upscale_info(model))
    assert result["family"] == "IMAGE_UPSCALE" and result["verified_capabilities"] == ["IMAGE"]
    config = adapter.studio_configuration()
    assert config["image_operations"] == ["upscale"]
    assert config["image_capabilities"]["upscaling"]["scales"] == [2, 4]
    assert config["image_capabilities"]["structural_only"] is True
    assert config["image_capabilities"]["inference_verified"] is False
    assert original.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("bad", ["wrong_type", "missing_resize", "extra_command", "wrong_enum", "missing_model"])
def test_metadata_name_alone_never_authorizes_upscale(bad):
    info = upscale_info()
    if bad == "wrong_type": info["UpscaleModelLoader"]["output"] = ["MODEL"]
    elif bad == "missing_resize": del info["ImageScale"]
    elif bad == "extra_command": info["ImageUpscaleWithModel"]["input"]["required"]["command"] = ["STRING"]
    elif bad == "wrong_enum": info["ImageScale"]["input"]["required"]["crop"] = [["center"]]
    else: info["UpscaleModelLoader"]["input"]["required"]["model_name"] = [[]]
    assert project_comfy_image_recipe(info, "RealESRGAN_x4plus.pth", "IMAGE_UPSCALE") is None


@pytest.mark.parametrize("scale", [2, 4])
def test_upscale_fixed_graph_matches_source_dimensions_and_dispatch_guard(scale):
    wire = UpscaleTransport(scale=scale)
    adapter = ComfyUIImageProvider(wire, "http://127.0.0.1:8188")
    adapter.image_recipe_descriptor = project_comfy_image_recipe(wire.info, "RealESRGAN_x4plus.pth", "IMAGE_UPSCALE")
    checks = []
    request = AssetGenerationRequest("comfyui", "RealESRGAN_x4plus.pth", "", "upscale-unit", {"scale": scale},
        dispatch_guard=lambda: checks.append("checked"))
    result = adapter.generate_image(request, operation="upscale", images=[inline()], reference_weights=[1])
    graph = next(kwargs["json"]["prompt"] for url, kwargs in wire.calls if url.endswith("/prompt"))
    validate_workflow(wire.info, graph)
    assert set(graph) == {"20", "4", "8", "28", "9"}
    assert graph["4"]["inputs"]["model_name"] == "RealESRGAN_x4plus.pth"
    assert graph["28"]["inputs"] == {"image": ["8", 0], "upscale_method": "lanczos",
        "width": 64 * scale, "height": 64 * scale, "crop": "disabled"}
    assert result.asset_uri.startswith("data:image/png;base64,") and len(checks) > 5


@pytest.mark.parametrize("width,height,scale", [(2048, 2048, 4), (2049, 64, 2), (0, 64, 2), (64, 64, 3)])
def test_upscale_bounded_before_upload(width, height, scale):
    recipe = project_comfy_image_recipe(upscale_info(), "RealESRGAN_x4plus.pth", "IMAGE_UPSCALE")
    with pytest.raises(ValueError):
        build_workflow(recipe, "", {"scale": scale}, operation="upscale", uploads=["source.png"], weights=[1],
            source_dimensions={"width": width, "height": height})


def test_legacy_parameter_validator_does_not_accept_scale_without_explicit_contract():
    with pytest.raises(ValueError): validate_image_parameters({"scale": 2})
    assert validate_image_parameters({"scale": 2}, ("scale",)) == {"scale": 2}


@pytest.mark.parametrize("scale", [2, 4])
def test_upscale_original_private_job_proof_review_and_reopen(mask, tmp_path, monkeypatch, scale):
    e = mask
    original, _, production, wire, value = configured(e, tmp_path, monkeypatch, scale)
    before = e.service.asset(e.nid, e.scope, e.source["id"])
    preview, job = queued(e, production, value)
    assert preview["execution_recipe"]["source_dimensions"] == {"width": 64, "height": 64}
    assert preview["execution_recipe"]["target_dimensions"] == {"width": 64 * scale, "height": 64 * scale}
    assert wire.calls == []
    ready = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    assert ready["status"] == "AWAITING_REVIEW" and ready["approved_asset_version"] is None
    proof = ready["processing_proof"]
    assert proof["source_sha256"] == e.source["sha256"] and proof["scale"] == scale
    assert (proof["output_width"], proof["output_height"]) == (64 * scale, 64 * scale)
    candidate = ready["output_candidate"]
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate["id"])
    restored = owner(production.image_registry, monkeypatch, type("Env", (), {
        "service": reopened(e), "nid": e.nid, "scope": e.scope, "actor": e.actor, "root": e.root})())
    public = restored.get(e.nid, e.scope, e.actor, "image", job["id"], lambda: None)
    assert public["processing_proof"] == proof
    approved = restored.review(e.nid, e.scope, e.actor, "image", job["id"], MediaReview(
        expected_version=ready["version"], expected_request_digest=ready["request_digest"],
        reviewed_output_digest=candidate["digest"]), lambda: None)
    assert approved["status"] == "APPROVED" and approved["approved_asset_version"] == 2
    assert e.service.asset(e.nid, e.scope, e.source["id"]) == before
    assert original.center.lifecycle.start.call_count == 0


def test_wrong_output_dimensions_never_publish_candidate(mask, tmp_path, monkeypatch):
    e = mask
    _, _, production, wire, value = configured(e, tmp_path, monkeypatch)
    wire.output = png_size(64, 64)
    _, job = queued(e, production, value)
    failed = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    assert failed["status"] == "UNKNOWN" and failed["output_candidate"] is None
    assert failed["processing_proof"] is None


def test_upscale_disable_after_source_upload_never_dispatches_or_publishes(mask, tmp_path, monkeypatch):
    e = mask
    original, adapter, production, wire, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    wire.after_upload = lambda: original.disable(adapter.candidate["id"])
    failed = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    assert failed["status"] == "UNKNOWN" and failed["output_candidate"] is None
    assert not any(url.endswith("/prompt") for url, _ in wire.calls)


def test_reference_roles_change_reviewed_identity_but_default_does_not(mask, tmp_path, monkeypatch):
    e = mask
    _, _, production, _, value = runtime(e, tmp_path, monkeypatch)
    old = MediaCommand.model_validate(value).model_dump()
    assert set(old["image_references"][0]) == {"source", "weight"}
    initial, _, _ = production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    altered = deepcopy(value)
    altered["image_references"][0].update(purpose="character", source_note="Character design board")
    preview, _, _ = production.preview(e.nid, e.scope, e.actor, altered, lambda: None)
    assert preview["request_digest"] != initial["request_digest"]
    returned = preview["command"]["image_references"][0]["source"]
    assert {key: returned[key] for key in value["image_references"][0]["source"]} == value["image_references"][0]["source"]
    with pytest.raises(StaleSourceError):
        production.create(e.nid, e.scope, e.actor, {"command": altered,
            "reviewed_preview_digest": initial["preview_digest"]}, lambda: None)


@pytest.mark.parametrize("kind", ["DEPTH", "POSE", "EDGE", "MASK", "LAYOUT"])
def test_control_reservation_is_typed_and_never_executable(kind):
    source = {"kind": "ASSET", "asset_kind": "image", "id": "source", "version": 1, "digest": "a" * 64}
    value = ImageControlInput(kind=kind, source=source, weight=.5)
    assert value.source.model_dump(exclude_none=True, exclude={"reference_only"}) == source
    assert reservation()["execution_available"] is False
    with pytest.raises(ValueError): ImageControlInput(kind=kind, source=source, weight=.5, command="arbitrary")


def test_upscale_source_edit_before_atomic_queue_creates_no_job(mask, tmp_path, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = mask
    _, _, production, wire, value = configured(e, tmp_path, monkeypatch)
    preview, _, _ = production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    original = ImageJobService.create_studio
    def changed(service, *args, **kwargs):
        with e.service._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(e.source["id"], {"scene_id": "edited-before-upscale-queue"}, expected_version=1)
        return original(service, *args, **kwargs)
    monkeypatch.setattr(ImageJobService, "create_studio", changed)
    with pytest.raises(StaleSourceError):
        production.create(e.nid, e.scope, e.actor, {"command": value,
            "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    rows = production._image(e.actor).list_studio(e.nid, e.scope.get("branch_id"), e.actor,
        production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None)
    assert rows == [] and wire.calls == []


@pytest.mark.parametrize("phase", ["execute", "review"])
def test_upscale_source_version_change_never_silently_refreshes(mask, tmp_path, monkeypatch, phase):
    e = mask
    _, _, production, wire, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    if phase == "review":
        job = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    with e.service._asset_scope(e.nid, e.scope):
        e.assets.update_metadata(e.source["id"], {"scene_id": "source-changed"}, expected_version=1)
    before = len(wire.calls)
    with pytest.raises(StaleSourceError):
        if phase == "execute": production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
        else: production.review(e.nid, e.scope, e.actor, "image", job["id"], MediaReview(
            expected_version=job["version"], expected_request_digest=job["request_digest"],
            reviewed_output_digest=job["output_candidate"]["digest"]), lambda: None)
    assert len(wire.calls) == before


def test_upscale_requires_source_phase_even_through_lower_original_owner(mask, tmp_path, monkeypatch):
    e = mask
    _, _, production, wire, value = configured(e, tmp_path, monkeypatch)
    preview, context, body = production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    context["command"] = body.model_dump()
    payload = body.model_dump(exclude={"source_snapshots", "allow_cloud", "license_note", "request_id"})
    payload["parameters"] = body.parameters.model_dump(exclude_none=True)
    with pytest.raises(ValueError, match="STUDIO_IMAGE_UPSCALE_SOURCE_PHASE_REQUIRED"):
        production._image(e.actor).create_studio(e.nid, e.scope.get("branch_id"), e.actor, payload, context, lambda: None)
    assert wire.calls == []


def test_persisted_upscale_proof_tampering_cannot_promote_private_result(mask, tmp_path, monkeypatch):
    e = mask
    _, _, production, _, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    ready = production.execute(e.nid, e.scope, e.actor, "image", job["id"], action(job), lambda: None)
    image_jobs = production._image(e.actor)
    def corrupt(rows):
        row = image_jobs._find(rows, job["id"])
        row["processing_proof"]["output_width"] += 1
        return row
    image_jobs._mutate(e.nid, e.scope.get("branch_id"), corrupt)
    with pytest.raises(ValueError, match="STUDIO_IMAGE_UPSCALE_PROOF_INVALID"):
        production.review(e.nid, e.scope, e.actor, "image", ready["id"], MediaReview(
            expected_version=ready["version"], expected_request_digest=ready["request_digest"],
            reviewed_output_digest=ready["output_candidate"]["digest"]), lambda: None)
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, ready["output_candidate"]["id"])


@pytest.mark.parametrize("scale", [True, 2.0, 3, "2", None])
def test_upscale_requires_exact_explicit_scale_type(scale):
    source = {"kind": "ASSET", "asset_kind": "image", "id": "source", "version": 1, "digest": "a" * 64}
    with pytest.raises(ValueError):
        MediaCommand(operation_id="m5.image.upscale", provider_id="configured", model_id="selected",
            request_id="upscale-contract", prompt="", parameters={"scale": scale},
            image_source=source, source_snapshots=[source])
