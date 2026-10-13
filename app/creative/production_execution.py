"""Explicit media execution adapters on existing job, source and asset owners.

This module owns no queue, credential store, scheduler or binary directory.
Only editable timeline documents live in the original incarnation-bound scope.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import ipaddress
from contextlib import contextmanager, nullcontext
from urllib.parse import urlsplit

from ..experimental.common import StaleSourceError, new_row, change_row
from ..experimental.store import canonical
from ..media_files import inspect_image, inspect_media
from ..services.v1_capability_service import CapabilityVersionConflict
from .production_execution_models import (MediaCommand, MediaCreate, ProviderSelection, TimelineSave, TimelineRender,
    TimelineEdit, TimelineRestore, TimelineExportPreview, TimelineExport)
from .project_store import BINDING
from .workspace import FLAG

TIMELINES = "creative_production_timelines_v2"


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def endpoint_local(endpoint, declared):
    if not declared:
        return False
    try:
        host = urlsplit(endpoint).hostname or ""
        if host == "localhost": return True
        address = ipaddress.ip_address(host)
        address = getattr(address, "ipv4_mapped", None) or address
        return (address.is_private or address.is_loopback) and not address.is_link_local and not address.is_unspecified and not address.is_multicast and (not address.is_reserved or address.is_loopback)
    except ValueError:
        return False


class ProductionExecutionService:
    def __init__(self, workspace, image_jobs, image_registry, video_owner, video_providers,
                 video_configs, audio_store, vault, transport):
        self.workspace, self.store = workspace, workspace.store
        self.image_jobs, self.image_registry = image_jobs, image_registry
        self.video_owner, self.video_providers, self.video_configs = video_owner, video_providers, video_configs
        self.audio_store, self.vault, self.transport = audio_store, vault, transport
        from ..services.studio_video_execution import StudioVideoExecution
        self.video = StudioVideoExecution(video_owner)
        from .graph_asset_inputs import GraphAssetInputs
        self.timeline_inputs = GraphAssetInputs(self)
        from .graph_timeline_execution import GraphTimelineExecution
        self.graph_timeline = GraphTimelineExecution(self)
        from .timeline_transfer import TimelineTransfer
        self.timeline_transfer = TimelineTransfer(self)
        from .timeline_playback import TimelinePlayback
        self.timeline_playback = TimelinePlayback(self)

    def timeline_playback_preview(self, nid, scope, actor, tid, value, guard):
        return self.timeline_playback.preview(nid, scope, actor, tid, value, guard)

    def timeline_playback_build(self, nid, scope, actor, tid, value, guard):
        return self.timeline_playback.build(nid, scope, actor, tid, value, guard)

    def timeline_playback_attest(self, nid, scope, actor, tid, value, guard):
        return self.timeline_playback.attest(nid, scope, actor, tid, value, guard)

    def timeline_transfer_preview(self, nid, scope, actor, tid, value, guard):
        return self.timeline_transfer.preview(nid, scope, actor, tid, value, guard)

    def timeline_transfer_import(self, nid, scope, actor, tid, value, guard):
        return self.timeline_transfer.apply(nid, scope, actor, tid, value, guard)

    def timeline_transfer_attachment(self, nid, scope, actor, tid, value, guard):
        return self.timeline_transfer.attachment(nid, scope, actor, tid, value, guard)

    def graph_timeline_preflight(self, nid, scope, actor, parameters, guard, *, document, source_kinds):
        return self.graph_timeline.preflight(nid, scope, actor, parameters, guard,
            document=document, source_kinds=source_kinds)

    def graph_timeline_queue(self, nid, scope, actor, preview, graph_binding, incarnation, guard):
        context = self.graph_timeline.context(nid, scope, actor, preview, graph_binding, incarnation)
        with self.timeline_inputs.phase(nid, scope, actor, guard) as document:
            self.graph_timeline.current(nid, scope, actor, context, document, guard, assets=True)
        row = self.video_owner.queue_studio(nid, scope.get("branch_id"), actor,
            context["execution_recipe"]["timeline"], context=context, guard=guard,
            export_profile=context["export_profile"])
        return self.view(row, "timeline")

    @staticmethod
    def _capacity(state):
        timelines = state["collections"].get(TIMELINES, {})
        if len(timelines) > 25 or len(canonical(timelines).encode("utf-8")) > 4 * 1024 * 1024:
            raise ValueError("STUDIO_TIMELINE_STORAGE_LIMIT")
        if any(len(row.get("history", [])) > 100 for row in timelines.values()):
            raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")

    def _base(self, nid, scope, actor, guard):
        guard()
        if self.workspace.project(nid, scope)["project"]["entry_kind"] != "NEUTRAL_STUDIO":
            raise ValueError("STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED")
        return {"actor": actor, "scope_key": self.store.key(nid, scope), "incarnation": self.store.incarnation(nid)}

    def _image(self, actor):
        return self.image_jobs.for_actor(actor)

    def _audio(self, scope, actor):
        from ..services.audiobook_service import AudiobookService
        from ..services.studio_audio_execution import StudioAudioExecution
        store = self.audio_store.for_branch(scope.get("branch_id")).for_actor(actor)
        return StudioAudioExecution(AudiobookService(store, self.workspace.assets, branch_id=scope.get("branch_id")))

    def source(self, nid, scope, snapshot, guard, *, inspection_guard=None):
        guard()
        if snapshot["kind"] == "CREATIVE_DOCUMENT":
            row = self.workspace.creative.get(nid, scope, snapshot["id"])
            if (row["version"], self.workspace.creative.document_digest(row)) != (snapshot["version"], snapshot["digest"]):
                raise StaleSourceError("STUDIO_DOCUMENT_SOURCE_CHANGED")
            guard()
            return {"snapshot": copy.deepcopy(snapshot), "row": row}
        if snapshot["kind"] != "ASSET":
            raise ValueError("STUDIO_SOURCE_OWNER_UNSUPPORTED")
        with self.workspace._asset_scope(nid, scope):
            row = self.workspace._row(nid, scope, snapshot["id"])
            if (row["version"], row["sha256"], row["kind"]) != (snapshot["version"], snapshot["digest"], snapshot["asset_kind"]):
                raise StaleSourceError("STUDIO_ASSET_SOURCE_CHANGED")
            data = self.workspace.assets.content(row["id"], branch_id=scope.get("branch_id"))
            guard()
        def inspect_current():
            guard()
            # Job/Graph stores must never be acquired under the asset lease.
            # The inspection-only fence also must not call source() recursively.
            if inspection_guard is not None:
                inspection_guard()
        measured = inspect_image(data) if row["kind"] == "image" else inspect_media(data, row["kind"], guard=inspect_current)
        guard()
        return {"data": data, "measured": measured, "snapshot": copy.deepcopy(snapshot), "row": row}

    def _source_guard(self, nid, scope, guard):
        return lambda snapshot, *, inspection_guard=None: self.source(
            nid, scope, snapshot, guard, inspection_guard=inspection_guard)

    @staticmethod
    def _cutout_guard(guard):
        def current():
            from ..experimental.flags import require_flag
            guard(); require_flag("asset_lineage_v2")
        return current

    @contextmanager
    def _cutout_queue_phase(self, nid, scope, context, guard):
        with self.store.source_lease(nid, scope):
            with self.workspace._asset_scope(nid, scope):
                self._cutout_inputs(nid, scope, context, guard, under_asset_lease=True)
                yield

    def _cutout_inputs(self, nid, scope, context, guard, *, under_asset_lease=False):
        """Original formal assets only; never probe media or resolve a provider.

        May run under the original asset lease. It must not acquire a queue or
        source-document lease, keeping source -> asset -> project order intact.
        """
        from ..experimental.flags import require_flag
        from ..services.studio_image_mask_authoring import SOURCE_MAX_BYTES, verify_mask, validate_source_png
        guard(); require_flag("asset_lineage_v2")
        inpaint = context["operation_id"] == "m5.image.inpaint"
        sources = [s for s in context["sources"] if s.get("kind") == "ASSET"] if inpaint else context["sources"]
        if (len(sources) != 2 or any(s.get("kind") != "ASSET" or s.get("asset_kind") != "image" for s in sources)
                or sources[0]["id"] == sources[1]["id"] or (not inpaint and context.get("graph_binding") is not None)):
            raise ValueError("STUDIO_IMAGE_CUTOUT_INPUT_REQUIRED")
        with (nullcontext() if under_asset_lease else self.workspace._asset_scope(nid, scope)):
            if self.store.incarnation(nid) != context["incarnation"]:
                raise StaleSourceError("STUDIO_OWNER_CHANGED")
            evidence = []
            for snapshot in sources:
                row = self.workspace._row(nid, scope, snapshot["id"])
                if (row.get("_owner_actor_id") or row.get("media_type") != "image/png"
                        or (row["version"], row["sha256"], row["kind"]) != (snapshot["version"], snapshot["digest"], "image")):
                    raise StaleSourceError("STUDIO_IMAGE_CUTOUT_SOURCE_CHANGED")
                if not 0 < row["size"] <= SOURCE_MAX_BYTES:
                    raise ValueError("STUDIO_IMAGE_CUTOUT_SOURCE_LIMIT")
                view = self.workspace._view(nid, scope, row)
                if view["provenance"]["integrity"] != "VERIFIED" or view["provenance"]["stale"]:
                    raise StaleSourceError("STUDIO_IMAGE_CUTOUT_SOURCE_CHANGED")
                data = self.workspace.assets.content(row["id"], branch_id=scope.get("branch_id"))
                evidence.append({"row": row, "data": data, "snapshot": copy.deepcopy(snapshot)})
            source, mask = evidence
            origin = self.workspace.assets._manual_record(mask["row"])
            if (origin["source"] != {"id": sources[0]["id"], "version": sources[0]["version"], "sha256": sources[0]["digest"]}
                    or origin["scope_key"] != context["scope_key"] or origin["incarnation"] != context["incarnation"]):
                raise StaleSourceError("STUDIO_IMAGE_CUTOUT_MASK_PAIR_CHANGED")
            # Sample authority at bounded intervals; no owner/database check per pixel.
            calls = 0
            def checkpoint():
                nonlocal calls
                calls += 1
                if calls % 64 == 0:
                    guard(); require_flag("asset_lineage_v2")
            proof = verify_mask(mask["data"], checkpoint=checkpoint)
            if any(origin[key] != value for key, value in proof.items()):
                raise ValueError("STUDIO_IMAGE_CUTOUT_MASK_PROOF_CHANGED")
            mask["mask_proof"] = proof
            validate_source_png(source["data"], proof["width"], proof["height"], checkpoint=checkpoint)
            for item in evidence:
                item["measured"] = {"media_type": "image/png", "extension": "png",
                    "width": proof["width"], "height": proof["height"], "validation": "DECODED"}
            guard(); require_flag("asset_lineage_v2")
            return evidence

    @staticmethod
    def _cutout_result_proof(row, inputs):
        proof = row.get("processing_proof")
        mask_proof = inputs[1]["mask_proof"]
        if not isinstance(proof, dict) or any(proof.get(key) != mask_proof[key]
                for key in ("width", "height", "keep_pixels", "remove_pixels", "mask_sha256")):
            raise ValueError("STUDIO_IMAGE_CUTOUT_PROOF_CHANGED")

    def _sources_current(self, nid, scope, context, guard):
        if context["operation_id"] in {"m5.image.cutout", "m5.image.inpaint"}:
            images = self._cutout_inputs(nid, scope, context, guard)
            by_id = {item["snapshot"]["id"]: item for item in images}
            return [by_id[source["id"]] if source["kind"] == "ASSET" else self.source(nid, scope, source, guard)
                    for source in context["sources"]]
        return [self.source(nid, scope, snapshot, guard) for snapshot in context["sources"]]

    @staticmethod
    def _image_configuration(provider):
        getter = getattr(provider, "image_configuration", None)
        return getter() if callable(getter) else None

    @staticmethod
    def _image_runtime(command):
        return isinstance(command, MediaCommand) and (command.image_source is not None
            or bool(command.image_references) or command.mask_source is not None
            or command.parameters.denoising_strength is not None
            or command.operation_id in {"m5.image.reference", "m5.image.inpaint"})

    def _binding(self, command):
        if command.operation_id in {"m8.audio.trim", "m5.image.cutout"}: return None
        pid, mid, operation = command.provider_id, command.model_id, command.operation_id
        if operation.startswith("m5."):
            from ..asset_provider_config import load
            from ..asset_providers import IMAGE_PROVIDER_CATALOG
            config = {**IMAGE_PROVIDER_CATALOG.get(pid, {}), **load().get(pid, {})}
            provider = self.image_registry.get(pid)
            from ..model_center.discovery_bridge import LocalImageAdapter
            if type(provider) is LocalImageAdapter:
                config = provider.studio_configuration()
            image_config = self._image_configuration(provider)
            image_operation = operation.rsplit(".", 1)[-1]
            capability = "TEXT_TO_IMAGE" if image_operation == "t2i" else "IMAGE_EDIT"
            if image_operation in {"reference", "inpaint"} or self._image_runtime(command):
                if (not image_config or image_operation not in image_config["operations"]
                        or not callable(getattr(provider, "generate_image", None))):
                    raise ValueError("STUDIO_IMAGE_RUNTIME_PROVIDER_UNSUPPORTED")
            elif image_config and image_operation != "t2i" and isinstance(command, MediaCommand):
                # Rich recipes have explicit source roles; never run FLUX/Qwen
                # through the historic SD checkpoint img2img template.
                raise ValueError("STUDIO_IMAGE_RUNTIME_BASE_REQUIRED")
            if capability == "IMAGE_EDIT" and not image_config and not callable(getattr(provider, "edit", None)):
                raise ValueError("STUDIO_IMAGE_EDIT_PROVIDER_UNSUPPORTED")
            model = getattr(provider, "default_model", "") or config.get("default_model", "")
        elif operation.startswith("m7."):
            provider = self.video_providers.get(pid)
            if provider is None: raise ValueError("STUDIO_VIDEO_PROVIDER_NOT_CONFIGURED")
            config = self.video_configs.get(pid, {})
            capability = {"m7.video.t2v": "text_to_video", "m7.video.i2v": "image_to_video", "m7.video.v2v": "video_to_video"}[operation]
            if not provider.capabilities().get(capability): raise ValueError("STUDIO_VIDEO_CAPABILITY_UNSUPPORTED")
            model = getattr(provider, "default_model", "")
        else:
            from ..audio_providers import provider_catalog
            config = next((row for row in provider_catalog() if row["provider_id"] == pid), None)
            capability = {"m8.audio.speech": "TTS", "m8.audio.music": "MUSIC", "m8.audio.effects": "SFX"}[operation]
            if config is None or capability not in config.get("capabilities", []):
                raise ValueError("STUDIO_AUDIO_PROVIDER_CAPABILITY_NOT_CONFIGURED")
            provider = None
            model = config.get("default_model", "")
        endpoint = getattr(provider, "endpoint", config.get("endpoint", ""))
        if not endpoint or config.get("enabled") is False or not model or mid != model:
            raise ValueError("STUDIO_PROVIDER_MODEL_BINDING_REQUIRED")
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("STUDIO_PROVIDER_ENDPOINT_INVALID")
        if provider is not None and not getattr(provider, "supports_dispatch_guard", False):
            raise ValueError("STUDIO_PROVIDER_LAST_MILE_AUTHORITY_REQUIRED")
        binding = {"provider_id": pid, "model_id": mid, "endpoint": endpoint,
            "local": endpoint_local(endpoint, bool(config.get("local"))), "capability": capability}
        if operation.startswith("m5.") and type(provider) is LocalImageAdapter:
            binding["registration_digest"] = config["registration_digest"]
        if operation.startswith("m8."):
            # Match the original audio resolver without resolving credentials or
            # probing health while listing/previewing configuration.
            binding["endpoint"] = endpoint.rstrip("/")
            try: ipaddress.ip_address(urlsplit(endpoint).hostname or "")
            except ValueError: binding["local"] = False
        route_config = {k: config.get(k) for k in
            ("enabled", "local", "requires_credential", "default_model", "model_id", "api_style", "capabilities", "video_to_video")}
        if operation.startswith("m5.") and image_config:
            route_config["image_recipe"] = image_config
        binding["route_digest"] = digest({**binding, "config": route_config})
        return binding

    def _egress(self, nid, scope, command, binding, guard):
        guard()
        if binding is None or binding["local"]: return
        from ..config import settings
        if not settings.enable_cloud: raise ValueError("STUDIO_CLOUD_DISABLED")
        if not command.allow_cloud: raise ValueError("STUDIO_CLOUD_EXPLICIT_CONSENT_REQUIRED")
        from ..source_privacy import assert_project_source_policies
        assert_project_source_policies(getattr(self.workspace.novels, "novels", self.workspace.novels), nid)
        self._cloud_sources(nid, scope, command.source_snapshots, guard)
        guard()

    def _cloud_sources(self, nid, scope, snapshots, guard):
        """Carry original privacy through the existing immutable asset DAG.

        This runs outside asset/job leases before dispatch, never grants cloud
        permission from an author license declaration, and never rewrites old
        chapter provenance into a CreativeDocument permission.
        """
        from .production_contracts import ProductionSourceSnapshot
        visited, active, measured_bytes = {}, set(), 0

        def visit(value, depth):
            nonlocal measured_bytes
            snapshot = ProductionSourceSnapshot.model_validate(value).model_dump(exclude_none=True, exclude={"reference_only"})
            if snapshot["kind"] not in {"ASSET", "CREATIVE_DOCUMENT"}:
                raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_UNVERIFIED")
            key, binding = (snapshot["kind"], snapshot["id"]), (snapshot["version"], snapshot["digest"])
            if key in active: raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_CYCLE")
            if key in visited:
                if visited[key] != binding: raise StaleSourceError("STUDIO_SOURCE_CLOUD_PROVENANCE_CHANGED")
                return
            if depth > 16 or len(visited) >= 64:
                raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_LIMIT")
            guard()
            result = self.source(nid, scope, snapshot, guard)
            row = result["row"]
            if snapshot["kind"] == "CREATIVE_DOCUMENT":
                if row.get("privacy_level") != "CLOUD_ALLOWED":
                    raise ValueError("STUDIO_SOURCE_CLOUD_POLICY_REQUIRED")
                visited[key] = binding
                return
            measured_bytes += row["size"]
            if measured_bytes > 200 * 1024 * 1024:
                raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_LIMIT")
            # Do not retain source bytes while descending through provenance.
            del result
            parents = row.get("source_asset_ids", [])
            if not isinstance(parents, list) or any(not isinstance(pid, str) for pid in parents):
                raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_UNVERIFIED")
            parameters = row.get("parameters", {})
            evidence = parameters.get("asset_lineage_v2", {}) if isinstance(parameters, dict) else {}
            if not isinstance(evidence, dict) or evidence.get("sources"):
                # Existing chapter snapshots require their original cloud
                # authority; this new media surface does not mint that grant.
                raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_UNVERIFIED")
            origin = row.get("_studio_result_origin")
            children = []
            if origin is not None:
                original_parents = self.workspace._production_asset_ids(origin)
                if set(parents) - set(original_parents):
                    raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_UNVERIFIED")
                children = origin["sources"]
            elif parents:
                bindings = evidence.get("parents")
                if not isinstance(bindings, dict) or set(bindings) != set(parents):
                    raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_UNVERIFIED")
                for pid in parents:
                    expected = bindings[pid]
                    if not isinstance(expected, dict) or set(expected) != {"version", "digest"}:
                        raise ValueError("STUDIO_SOURCE_CLOUD_PROVENANCE_UNVERIFIED")
                    with self.workspace._asset_scope(nid, scope):
                        parent = self.workspace._row(nid, scope, pid)
                    children.append({"id": pid, "kind": "ASSET", **expected, "asset_kind": parent["kind"]})
            visited[key] = binding
            active.add(key)
            try:
                for child in children: visit(child, depth + 1)
            finally: active.remove(key)
            guard()

        for snapshot in snapshots:
            visit(snapshot.model_dump(exclude_none=True), 0)

    def _parameters(self, command):
        if command.operation_id == "m5.image.cutout": return []
        if command.operation_id.startswith("m5."):
            provider = self.image_registry.get(command.provider_id)
            config = self._image_configuration(provider)
            operation = command.operation_id.rsplit(".", 1)[-1]
            if config:
                names = provider.image_parameters(operation)
            else:
                names = getattr(provider, "supported_parameters", None)
                if command.operation_id == "m5.image.i2i": names = getattr(provider, "edit_supported_parameters", names)
            if names is None: raise ValueError("STUDIO_PROVIDER_PARAMETER_CONTRACT_REQUIRED")
            if isinstance(command, MediaCommand):
                from ..asset_providers import validate_image_parameters
                validate_image_parameters(command.parameters.model_dump(exclude_none=True), names)
                count = (1 if command.image_source is not None else 0) + len(command.image_references or [])
                if config and operation != "t2i" and count > config["reference_limit"]:
                    raise ValueError("STUDIO_PROVIDER_IMAGE_REFERENCE_LIMIT")
                if not config and command.operation_id == "m5.image.i2i" and sum(s.kind == "ASSET" for s in command.source_snapshots) > getattr(provider, "edit_reference_limit", 0):
                    raise ValueError("STUDIO_PROVIDER_IMAGE_REFERENCE_LIMIT")
            return list(names)
        return {"m7.video.t2v": ["width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"],
            "m7.video.i2v": ["width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"],
            "m7.video.v2v": ["width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"],
            "m8.audio.speech": ["voice_id", "speech_rate"], "m8.audio.music": ["duration_seconds", "seed"],
            "m8.audio.effects": ["duration_seconds", "seed"], "m8.audio.trim": ["in_ms", "out_ms", "gain_db", "sample_rate", "channels"]}[command.operation_id]

    def preview(self, nid, scope, actor, value, guard, *, graph_binding=None):
        command = MediaCommand.model_validate(value)
        if (graph_binding is not None and command.operation_id == "m8.audio.trim"
                and any(getattr(command.parameters, key) is not None for key in ("gain_db", "sample_rate", "channels"))):
            raise ValueError("STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY")
        if command.operation_id in {"m5.image.cutout", "m5.image.inpaint"}: guard = self._cutout_guard(guard)
        context = self._base(nid, scope, actor, guard)
        if graph_binding is not None:
            from .graph_media_binding import validate_graph_binding
            context["graph_binding"] = validate_graph_binding(graph_binding, context)
        sources = [s.model_dump(exclude={"reference_only"}, exclude_none=True) for s in command.source_snapshots]
        if command.operation_id == "m5.image.cutout" and graph_binding is not None:
            raise ValueError("STUDIO_IMAGE_CUTOUT_STANDALONE_ONLY")
        evidence = [{"snapshot": source["snapshot"], "measured": source.get("measured")}
            for source in self._sources_current(nid, scope, {**context, "sources": sources, "operation_id": command.operation_id}, guard)]
        binding = self._binding(command)
        names = self._parameters(command)
        # Resolve supported random seeds once from the captured request ID.
        # Re-reading/queueing the same preview therefore retains its recipe.
        if "seed" in names and command.parameters.seed is None:
            command = command.model_copy(update={"parameters": command.parameters.model_copy(update={
                "seed": int(digest([command.request_id, command.operation_id])[:8], 16) % 2147483648})})
        if command.operation_id == "m8.audio.speech" and command.parameters.speech_rate is None:
            command = command.model_copy(update={"parameters": command.parameters.model_copy(update={"speech_rate": 1.0})})
        self._egress(nid, scope, command, binding, guard)
        body = command.model_dump()
        if command.operation_id == "m5.image.cutout": body["parameters"] = {}
        recipe = self._recipe(command)
        context.update(request_id=command.request_id, operation_id=command.operation_id, sources=sources,
            provider_binding=binding, license_note=command.license_note, rights={"license_note": command.license_note}, execution_recipe=recipe)
        context["request_digest"] = digest({"context": context, "command": body})
        preview = {"contract": "studio-production-preview/1", "novel_id": nid, "branch_id": scope.get("branch_id"),
            "operation_id": command.operation_id, "request_id": command.request_id,
            "request_digest": context["request_digest"], "provider": {k: binding[k] for k in ("provider_id", "model_id", "local", "route_digest")} if binding else None, "sources": evidence,
            "execution_recipe": recipe,
            "command": body, "product_acceptance": "LOCAL_REQUIRED", "execution_available": True,
            "automatic_dispatch": False, "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW"}
        preview["preview_digest"] = digest(preview)
        guard()
        return preview, context, command

    def _recipe(self, command):
        parameters = command.parameters.model_dump(exclude_none=True)
        recipe = {"contract": "studio-execution-recipe/1", "operation_id": command.operation_id,
            "adapter": "ORIGINAL_HTTP_PROVIDER", "parameters": parameters, "automatic_fallback": False}
        if command.operation_id == "m5.image.cutout":
            recipe.update(adapter="LOCAL_CPU_MASK", output_profile="PNG_RGBA8_STORED_DEFLATE",
                mask_policy="WHITE_KEEP_BLACK_TRANSPARENT_ZERO")
        elif command.operation_id.startswith("m5."):
            from ..asset_providers import AssetGenerationRequest, ComfyUIImageProvider, Automatic1111ImageProvider
            provider = self.image_registry.get(command.provider_id)
            image_config = self._image_configuration(provider)
            if image_config:
                operation = command.operation_id.rsplit(".", 1)[-1]
                weights = [reference.weight for reference in command.image_references or []]
                if command.image_source is not None: weights.insert(0, 1.0)
                result = provider.image_recipe(AssetGenerationRequest(command.provider_id, command.model_id,
                    command.prompt, command.request_id, parameters), operation=operation,
                    reference_weights=weights, mask=command.mask_source is not None)
                recipe.update(adapter="COMFYUI_BUILTIN_IMAGE" if image_config["recipe_id"].startswith("comfy-") else "AUTOMATIC1111_IMAGE",
                    image_recipe_id=image_config["recipe_id"], reference_weights=weights,
                    reference_semantics=image_config["reference_semantics"],
                    mask_semantics=image_config["mask_semantics"] if command.mask_source is not None else None)
                if image_config["recipe_id"].startswith("comfy-"): recipe["workflow"] = result
                else:
                    recipe["defaults"] = {"width": 1024, "height": 1024, "steps": 28} if operation == "t2i" else {"steps": 28}
                    if operation != "t2i": recipe["denoising_strength"] = parameters.get("denoising_strength", 0.6)
                recipe["recipe_digest"] = digest(recipe)
                return recipe
            from ..model_center.discovery_bridge import LocalImageAdapter
            model_id = command.model_id
            if type(provider) is LocalImageAdapter:
                config = provider.studio_configuration()
                model_id = config["runtime_model_id"]
                provider = provider.delegate
            if isinstance(provider, ComfyUIImageProvider):
                recipe["adapter"] = "COMFYUI_BUILTIN_IMAGE"
                workflow = provider._workflow(AssetGenerationRequest(command.provider_id, model_id,
                    command.prompt, command.request_id, parameters))
                if command.operation_id == "m5.image.i2i":
                    # The transport upload receipt supplies the input basename
                    # later; this symbolic owner reference is never dispatched.
                    workflow["10"] = {"class_type": "LoadImage", "inputs": {"image": "VERIFIED_SOURCE_UPLOAD_RECEIPT"}}
                    workflow["5"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["4", 2]}}
                    workflow["3"]["inputs"]["denoise"] = 0.6
                recipe["workflow"] = workflow
            elif isinstance(provider, Automatic1111ImageProvider):
                recipe["adapter"] = "AUTOMATIC1111_IMAGE"
                recipe["defaults"] = {"width": 1024, "height": 1024, "steps": 28}
                if command.operation_id == "m5.image.i2i": recipe["denoising_strength"] = 0.6
        elif command.operation_id == "m8.audio.trim":
            from ..services.studio_audio_execution import trim_output_profile
            recipe.update(adapter="LOCAL_FFMPEG", output_profile=trim_output_profile(parameters))
        recipe["recipe_digest"] = digest(recipe)
        return recipe

    @staticmethod
    def view(row, owner):
        context = row.get("context", {})
        binding = context.get("provider_binding")
        command = copy.deepcopy(context.get("command"))
        if command is not None:
            command["parameters"] = {k: v for k, v in command["parameters"].items() if v is not None}
            command["source_snapshots"] = [{k: v for k, v in s.items() if v is not None} for s in command["source_snapshots"]]
        candidate = row.get("output_candidate")
        if candidate is None and row.get("output_asset_id"):
            candidate = {"id": row["output_asset_id"], "version": row.get("candidate_asset_version", row.get("output_asset_version")), "digest": row.get("output_digest"),
                "kind": "image" if owner == "image" else "audio"}
        return {"contract": "studio-production-job/1", "owner": owner,
            **({"processing_proof": copy.deepcopy(row.get("processing_proof"))} if context.get("operation_id") == "m5.image.cutout" else {}),
            **{key: copy.deepcopy(row.get(key)) for key in ("id", "novel_id", "branch_id", "version", "status", "request_digest", "receipt_digest", "attempt", "created_at", "updated_at", "error_code", "review_state", "cancellation_mode", "needs_reconciliation", "execution_state")},
            "operation_id": row.get("context", {}).get("operation_id"), "output_candidate": candidate,
            "timeline_snapshot": copy.deepcopy(row.get("context", {}).get("timeline_snapshot")),
            "sources": copy.deepcopy(row.get("context", {}).get("sources", [])),
            "command": command,
            "provider": {k: binding[k] for k in ("provider_id", "model_id", "local", "route_digest")} if binding else None,
            "execution_recipe": copy.deepcopy(context.get("execution_recipe")),
            "media_measurement": {key: copy.deepcopy(row["measured"][key]) for key in
                ("duration_ms", "byte_count", "width", "height", "fps", "video_codec", "audio_codec", "sample_rate", "channels",
                 "container", "profile_validation", "render_profile", "export_profile") if key in row.get("measured", {})}
                if owner == "timeline" and isinstance(row.get("measured"), dict) else
                copy.deepcopy(row.get("measured")) if owner == "audio" and context.get("operation_id") == "m8.audio.trim"
                and context.get("graph_binding") is None else None,
            "approved_asset_version": row.get("approved_asset_version", row.get("output_asset_version") if row.get("status") == "APPROVED" else None),
            "request_id": row.get("context", {}).get("request_id"), "product_acceptance": "LOCAL_REQUIRED",
            "automatic_replay": False, "remote_compute_may_continue": owner != "timeline" and row.get("cancellation_mode") == "LOCAL_RESULT_DISCARD"}

    def create(self, nid, scope, actor, value, guard, *, graph_binding=None):
        body = MediaCreate.model_validate(value)
        preview, context, command = self.preview(nid, scope, actor, body.command, guard, graph_binding=graph_binding)
        if preview["preview_digest"] != body.reviewed_preview_digest:
            raise StaleSourceError("STUDIO_PRODUCTION_PREVIEW_CHANGED")
        payload = command.model_dump(exclude={"source_snapshots", "allow_cloud", "license_note", "request_id"})
        payload["parameters"] = command.parameters.model_dump(exclude_none=True)
        # Keep the exact reviewed command for later egress and route rechecks.
        context["command"] = copy.deepcopy(preview["command"]) if command.operation_id == "m5.image.cutout" else command.model_dump()
        branch = scope.get("branch_id")
        if command.operation_id.startswith("m5."):
            if command.operation_id in {"m5.image.cutout", "m5.image.inpaint"}:
                guard = self._cutout_guard(guard)
                row = self._image(actor).create_studio(nid, branch, actor, payload, context, guard,
                    source_phase=lambda: self._cutout_queue_phase(nid, scope, context, guard))
            else:
                row = self._image(actor).create_studio(nid, branch, actor, payload, context, guard)
            owner = "image"
        elif command.operation_id.startswith("m7."):
            row = self.video.create(nid, branch, actor, payload, context=context, guard=guard)
            owner = "video"
        else:
            row = self._audio(scope, actor).queue(nid, {**payload, "source_snapshots": copy.deepcopy(context["sources"])},
                context, guard, self._source_guard(nid, scope, guard))
            owner = "audio"
        guard()
        return self.view(row, owner)

    def _row(self, nid, scope, actor, owner, jid, guard, *, graph_binding=None):
        context = self._base(nid, scope, actor, guard)
        branch = scope.get("branch_id")
        if owner == "image": row = self._image(actor).get_studio(nid, branch, actor, jid, guard)
        elif owner == "audio": row = self._audio(scope, actor).get(nid, jid, context, guard)
        elif owner == "video": row = self.video.get(nid, branch, actor, jid, context=context, guard=guard)
        elif owner == "timeline":
            row = self.video_owner.get_studio(nid, branch, actor, jid, context=context, guard=guard)
            if row.get("kind") != "STUDIO_TIMELINE": raise FileNotFoundError(jid)
        else: raise ValueError("STUDIO_EXECUTION_OWNER_INVALID")
        captured = row.get("context", {})
        self._graph_admission(captured, graph_binding, jid)
        if any(captured.get(k) != context[k] for k in ("actor", "scope_key", "incarnation")):
            raise FileNotFoundError(jid)
        return row, captured

    @staticmethod
    def _graph_admission(context, graph_binding, jid):
        # Public standalone commands cannot submit the server-only binding.
        # A bound original job is owned by the matching Graph runtime surface.
        from .graph_media_binding import validate_graph_binding
        expected = validate_graph_binding(graph_binding, context)
        captured = context.get("graph_binding")
        if captured != expected or ("graph_binding" in context and captured is None):
            raise FileNotFoundError(jid)
        if captured is not None:
            validate_graph_binding(captured, context)

    def get(self, nid, scope, actor, owner, jid, guard, *, graph_binding=None):
        row, _ = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        return self.view(row, owner)

    def list(self, nid, scope, actor, guard, *, graph_binding=None):
        context = self._base(nid, scope, actor, guard)
        rows = []
        def admitted(row):
            try: self._graph_admission(row.get("context", {}), graph_binding, row["id"])
            except FileNotFoundError: return False
            return True
        for row in self._image(actor).list_studio(nid, scope.get("branch_id"), actor, context, guard):
            if not admitted(row): continue
            rows.append(self.view(row, "image"))
        for row in self._audio(scope, actor).list(nid, context, guard):
            if not admitted(row): continue
            rows.append(self.view(row, "audio"))
        for row in self.video_owner.list_studio(nid, scope.get("branch_id"), actor, context=context, guard=guard):
            if not admitted(row): continue
            rows.append(self.view(row, "timeline" if row.get("kind") == "STUDIO_TIMELINE" else "video"))
        guard()
        return {"items": sorted(rows, key=lambda row: (row.get("created_at") or "", row["id"]), reverse=True), "product_acceptance": "LOCAL_REQUIRED"}

    def candidate(self, nid, scope, actor, owner, jid, guard, *, graph_binding=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        candidate = self.view(row, owner)["output_candidate"]
        if candidate is None: raise FileNotFoundError(jid)
        if owner == "timeline":
            # Read the original queue first, then fence the saved timeline,
            # exact formal sources and candidate under the same publication
            # scope -> asset -> project order. A later queue read only checks
            # the captured receipt; it never holds a queue lock across a scope
            # callback and cannot recreate a candidate or adopt stale output.
            with self.timeline_inputs.phase(nid, scope, actor, guard) as document:
                current = self._timeline_context_current(nid, scope, actor, context, document)
                self._timeline_sources_current(nid, scope, current["timeline"], guard)
                meta = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                expected_version = row.get("approved_asset_version") if row["status"] == "APPROVED" else candidate["version"]
                origin = self._timeline_result_origin(context, jid)
                reviewed_origin = {"contract": "studio-production-review/1", "job_id": jid,
                    "request_digest": row["request_digest"], "output_digest": candidate["digest"],
                    "candidate_version": candidate["version"], "review_actor": actor}
                if (meta.get("version") != expected_version or meta.get("sha256") != candidate["digest"]
                        or meta.get("kind") != "video" or meta.get("deleted_at")
                        or meta.get("novel_id") != nid or meta.get("branch_id") != scope.get("branch_id")
                        or meta.get("_required_features") != [FLAG]
                        or meta.get("_studio_result_origin") != origin or meta.get("source_job_id") != jid
                        or meta.get("_project_binding") != {"novel_id": nid, "branch_id": scope.get("branch_id"),
                            "scope_key": context["scope_key"], "incarnation": context["incarnation"]}
                        or (row["status"] == "APPROVED" and (meta.get("_owner_actor_id") is not None
                            or meta.get("_origin_provenance") != reviewed_origin))
                        or (row["status"] != "APPROVED" and meta.get("_owner_actor_id") != actor)):
                    raise StaleSourceError("STUDIO_CANDIDATE_RECEIPT_MISMATCH")
                data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                if hashlib.sha256(data).hexdigest() != candidate["digest"]:
                    raise StaleSourceError("STUDIO_CANDIDATE_BYTES_CHANGED")
                result = self.workspace.assets.public(meta)
                guard()
            latest, latest_context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
            if (latest["version"] != row["version"] or latest["request_digest"] != row["request_digest"]
                    or latest["status"] != row["status"] or latest.get("output_candidate") != row.get("output_candidate")
                    or latest.get("receipt_digest") != row.get("receipt_digest") or latest_context != context):
                raise StaleSourceError("STUDIO_CANDIDATE_JOB_CHANGED")
            guard()
            return result, data
        # Inspection of a cancelled private result remains available, but its
        # exact recorded bytes/identity are never replaced by current metadata.
        # Queue reads stay outside the source/asset phase (V1 queue -> asset).
        with self.store.source_lease(nid, scope):
            with self.workspace._asset_scope(nid, scope):
                if row["status"] == "APPROVED":
                    meta = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                    approved = self.view(row, owner)["approved_asset_version"]
                    provenance = self._approved_media_provenance(row, owner, actor)
                    if (approved != candidate["version"] + 1 or meta.get("version") != approved
                            or meta.get("_owner_actor_id") is not None or meta.get("deleted_at")
                            or meta.get("kind") != candidate["kind"] or meta.get("sha256") != candidate["digest"]
                            or meta.get("novel_id") != nid or meta.get("branch_id") != scope.get("branch_id")
                            or meta.get("source_job_id") != jid or meta.get("_required_features") != [FLAG]
                            or meta.get("_origin_provenance") != provenance
                            or meta.get("_studio_result_origin") != self._media_result_origin(context, jid)
                            or meta.get("_project_binding") != {"novel_id": nid, "branch_id": scope.get("branch_id"),
                                "scope_key": context["scope_key"], "incarnation": context["incarnation"]}):
                        raise StaleSourceError("STUDIO_CANDIDATE_RECEIPT_MISMATCH")
                    data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                    if hashlib.sha256(data).hexdigest() != candidate["digest"] or len(data) != meta["size"]:
                        raise StaleSourceError("STUDIO_CANDIDATE_BYTES_CHANGED")
                else:
                    meta = self._private_media_candidate(nid, scope, actor, context, jid, candidate)
                    data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                result = self.workspace.assets.public(meta)
                guard()
        latest, latest_context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if (latest["version"] != row["version"] or latest["status"] != row["status"] or latest_context != context
                or latest["request_digest"] != row["request_digest"] or latest.get("receipt_digest") != row.get("receipt_digest")
                or self.view(latest, owner)["output_candidate"] != candidate):
            raise StaleSourceError("STUDIO_CANDIDATE_JOB_CHANGED")
        guard()
        return result, data

    @staticmethod
    def _approved_media_provenance(row, owner, actor):
        # These are the original owners' immutable approval receipts; this
        # projection neither changes them nor performs an approval.
        if owner == "image":
            from ..services.studio_image_execution import _receipt
            return {**_receipt(row), "receipt_digest": row["receipt_digest"], "human_review": "EXPLICIT_APPROVAL", "review_actor": actor}
        context = row["context"]
        if owner == "audio":
            from ..services.studio_audio_execution import STUDIO_ORIGIN
            return {"contract": "studio-production-review/1", "studio_origin": STUDIO_ORIGIN, "source_job_id": row["id"],
                "request_digest": context["request_digest"], "actor": actor, "scope_key": context["scope_key"],
                "incarnation": context["incarnation"], "source_snapshots": copy.deepcopy(context["sources"]),
                "output_digest": row["output_digest"], "candidate_version": row["candidate_asset_version"],
                "provider_binding": copy.deepcopy(context["provider_binding"]), "rights": copy.deepcopy(context["rights"]), "review_actor": actor}
        candidate = row["output_candidate"]
        return {"contract": "studio-production-review/1", "job_id": row["id"], "request_digest": row["request_digest"],
            "output_digest": candidate["digest"], "candidate_version": candidate["version"], "review_actor": actor}

    def cancel(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if (row["version"], row["request_digest"]) != (action.expected_version, action.expected_request_digest):
            raise CapabilityVersionConflict(self.view(row, owner))
        if owner == "video":
            row = self.video.cancel(nid, scope.get("branch_id"), actor, jid, action, context=context, guard=guard)
        elif owner == "audio": row = self._audio(scope, actor).cancel(nid, jid, action.expected_version, context, guard)
        elif owner == "image":
            row = self._image(actor).cancel_studio(nid, scope.get("branch_id"), actor, jid,
                expected_version=action.expected_version, expected_request_digest=action.expected_request_digest, guard=guard)
        else:
            # Fence publication under its original scope -> asset -> project
            # leases before the original queue CAS. Do not wait on the executor
            # lease or require stale input assets to become current to cancel.
            with self.timeline_inputs.phase(nid, scope, actor, guard):
                row = self.video_owner.cancel_studio(nid, scope.get("branch_id"), actor, jid,
                    action.expected_version, action.expected_request_digest, context=context, guard=guard)
        guard()
        return self.view(row, owner)

    def reconcile(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None, graph_guard=None, graph_source_guard=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if (row["version"], row["request_digest"]) != (action.expected_version, action.expected_request_digest):
            raise CapabilityVersionConflict(self.view(row, owner))
        if context["operation_id"] in {"m5.image.cutout", "m5.image.inpaint"}: guard = self._cutout_guard(guard)
        branch = scope.get("branch_id")
        recover = lambda captured: self._recover_media_candidate(nid, scope, actor, captured, context, guard,
            graph_source_guard=graph_source_guard)
        recover_review = self._review_compensation(nid, scope, actor, context, jid)
        if owner == "image":
            row = self._image(actor).reconcile_studio(nid, branch, actor, jid,
                expected_version=action.expected_version, expected_request_digest=action.expected_request_digest, guard=guard,
                recover_candidate=recover, recover_review=recover_review)
        elif owner == "audio":
            row = self._audio(scope, actor).reconcile(nid, jid, action.expected_version, context, guard,
                expected_request_digest=action.expected_request_digest, recover_candidate=recover, recover_review=recover_review)
        elif owner == "video":
            row = self.video.reconcile(nid, branch, actor, jid, action, context=context, guard=guard,
                recover_candidate=recover, recover_review=recover_review)
        else:
            if context.get("graph_binding") is not None and row["status"] != "REVIEWING":
                if graph_guard is None or graph_source_guard is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_SOURCE_GUARD_REQUIRED")
                graph_guard()
            row = self.video_owner.reconcile_studio(nid, branch, actor, jid, action.expected_version,
                action.expected_request_digest, context=context, guard=guard,
                recover_candidate=lambda captured: self._recover_timeline_candidate(nid, scope, actor, captured, context, guard,
                    graph_source_guard=graph_source_guard), recover_review=recover_review)
        guard()
        return self.view(row, owner)

    @staticmethod
    def _media_result_origin(context, jid):
        binding = context.get("provider_binding") or {}
        origin = {"contract": "studio-production-result/1", "job_id": jid,
            **{key: copy.deepcopy(context[key]) for key in ("scope_key", "incarnation", "actor", "request_digest", "operation_id", "sources")},
            "provider_id": binding.get("provider_id"), "model_id": binding.get("model_id"), "license_note": context.get("license_note", "")}
        if context.get("graph_binding") is not None:
            origin["graph_binding"] = copy.deepcopy(context["graph_binding"])
        return origin

    def _private_media_candidate(self, nid, scope, actor, context, jid, candidate):
        """Exact proof only; caller already holds the source -> asset phase."""
        if not isinstance(candidate, dict) or self.store.incarnation(nid) != context["incarnation"]:
            raise StaleSourceError("STUDIO_CANDIDATE_OWNER_CHANGED")
        meta = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
        if (meta.get("novel_id") != nid or meta.get("branch_id") != scope.get("branch_id")
                or meta.get("_owner_actor_id") != actor or meta.get("version") != candidate["version"]
                or meta.get("kind") != candidate["kind"] or meta.get("sha256") != candidate["digest"] or meta.get("deleted_at")
                or meta.get("source_job_id") != jid or meta.get("_required_features") != [FLAG] or meta.get("_origin_provenance") is not None
                or meta.get("_studio_result_origin") != self._media_result_origin(context, jid)
                or meta.get("_project_binding") != {"novel_id": nid, "branch_id": scope.get("branch_id"),
                    "scope_key": context["scope_key"], "incarnation": context["incarnation"]}):
            raise StaleSourceError("STUDIO_PRIVATE_CANDIDATE_PROOF_CHANGED")
        data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
        if hashlib.sha256(data).hexdigest() != candidate["digest"] or len(data) != meta["size"]:
            raise StaleSourceError("STUDIO_CANDIDATE_BYTES_CHANGED")
        return copy.deepcopy(meta)

    def _review_compensation(self, nid, scope, actor, context, jid):
        def recover(candidate, compensate):
            # Internal compensation grants no new authority. A revoked Host or
            # stale source must not strand this proven unpromoted reservation.
            # The owner pre-acquires its original queue fence and supplies its
            # exact CAS write; it runs before the private asset lease ends.
            try:
                with self.store.source_lease(nid, scope):
                    with self.workspace._asset_scope(nid, scope):
                        self._private_media_candidate(nid, scope, actor, context, jid, candidate)
                        compensate()
                return True
            except Exception:
                return False
        return recover

    def _recover_media_candidate(self, nid, scope, actor, captured, context, guard, *, graph_source_guard=None):
        ready = captured.get("publication_ready")
        if not isinstance(ready, dict) or set(ready) != {"kind", "output_digest", "output_bytes", "media_type"}:
            return None
        if (ready["kind"] not in {"image", "video", "audio"} or type(ready["output_bytes"]) is not int
                or not 0 < ready["output_bytes"] <= self.workspace.assets.MAX_BYTES):
            raise ValueError("STUDIO_PUBLICATION_READY_RECEIPT_INVALID")
        with self.store.source_lease(nid, scope) as document:
            guard()
            graph_asset_guard = None
            if context.get("graph_binding") is not None:
                if graph_source_guard is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_SOURCE_GUARD_REQUIRED")
                graph_asset_guard = graph_source_guard(document)
                if not callable(graph_asset_guard):
                    raise ValueError("CREATIVE_GRAPH_MEDIA_ASSET_GUARD_REQUIRED")
            for source in context["sources"]:
                if source["kind"] != "ASSET": self.source(nid, scope, source, guard)
            with self.workspace._asset_scope(nid, scope):
                if graph_asset_guard is not None: graph_asset_guard()
                if self.store.incarnation(nid) != context["incarnation"]:
                    raise StaleSourceError("STUDIO_OWNER_CHANGED")
                if context["operation_id"] == "m5.image.cutout":
                    inputs = self._cutout_inputs(nid, scope, context, guard, under_asset_lease=True)
                    self._cutout_result_proof(captured, inputs)
                elif context["operation_id"] == "m5.image.inpaint":
                    self._cutout_inputs(nid, scope, context, guard, under_asset_lease=True)
                for source in context["sources"]:
                    if source["kind"] == "ASSET":
                        asset = self.workspace._row(nid, scope, source["id"])
                        if (asset.get("_owner_actor_id") or (asset["version"], asset["sha256"], asset["kind"]) !=
                                (source["version"], source["digest"], source["asset_kind"])):
                            raise StaleSourceError("STUDIO_SOURCE_CHANGED")
                        self.workspace.assets.content(asset["id"], branch_id=scope.get("branch_id"))
                key = "studio-production:" + digest([context["scope_key"], context["incarnation"], actor, captured["id"]])
                matches = [asset for asset in self.workspace.assets.list(nid, branch_id=scope.get("branch_id"),
                    include_deleted=True, actor_id=actor) if asset.get("idempotency_key") == key]
                if not matches: return None
                if len(matches) != 1: raise ValueError("STUDIO_RECOVERY_CANDIDATE_AMBIGUOUS")
                meta = matches[0]
                # The original publication creates version 1. No candidate
                # version was durably captured yet, so a later metadata edit
                # cannot supply its own expected version as recovery proof.
                if type(meta.get("version")) is not int or meta["version"] != 1:
                    raise StaleSourceError("STUDIO_RECOVERY_ORIGINAL_PUBLICATION_CHANGED")
                candidate = {"id": meta["id"], "version": 1, "digest": ready["output_digest"], "kind": ready["kind"]}
                asset = self._private_media_candidate(nid, scope, actor, context, captured["id"], candidate)
                if asset["size"] != ready["output_bytes"] or asset["media_type"] != ready["media_type"]:
                    raise ValueError("STUDIO_RECOVERY_CANDIDATE_MEASUREMENT_CHANGED")
                guard()
                return asset

    def _recover_timeline_candidate(self, nid, scope, actor, captured, context, guard, *, graph_source_guard=None):
        """Recover only an already-published original private candidate.

        Runs under the original stopped-executor lease; no rendering, source
        rewriting, promotion or replacement job is permitted. The original
        queue owner does the final version/status CAS after this short phase.
        """
        if captured.get("phase") not in {"PUBLICATION_READY", "CANDIDATE_RECORDED", "INTERRUPTED_EXECUTION_RECONCILED"} or not captured.get("output_digest"):
            return None
        with self.store.source_lease(nid, scope) as document:
            graph_asset_guard = None
            if context.get("graph_binding") is not None:
                if graph_source_guard is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_SOURCE_GUARD_REQUIRED")
                graph_asset_guard = graph_source_guard(document)
                if not callable(graph_asset_guard):
                    raise ValueError("CREATIVE_GRAPH_MEDIA_ASSET_GUARD_REQUIRED")
            current = self._timeline_context_current(nid, scope, actor, context, document)
            with self.workspace._asset_scope(nid, scope):
                if graph_asset_guard is not None: graph_asset_guard()
                if self.store.incarnation(nid) != context["incarnation"]:
                    raise StaleSourceError("STUDIO_OWNER_CHANGED")
                self._timeline_sources_current(nid, scope, current["timeline"], guard)
                key = "studio-production:" + digest([context["scope_key"], context["incarnation"], actor, captured["id"]])
                matches = [asset for asset in self.workspace.assets.list(nid, branch_id=scope.get("branch_id"),
                    include_deleted=True, actor_id=actor) if asset.get("idempotency_key") == key]
                if not matches: return None
                if len(matches) != 1: raise ValueError("STUDIO_TIMELINE_RECOVERY_CANDIDATE_AMBIGUOUS")
                asset = matches[0]
                origin = self._timeline_result_origin(context, captured["id"])
                if (asset.get("kind") != "video" or asset.get("novel_id") != nid or asset.get("branch_id") != scope.get("branch_id")
                        or asset.get("_owner_actor_id") != actor or asset.get("deleted_at") or asset.get("_required_features") != [FLAG]
                        or type(asset.get("version")) is not int or asset["version"] != 1 or asset.get("_origin_provenance") is not None
                        or asset.get("sha256") != captured["output_digest"] or asset.get("source_job_id") != captured["id"]
                        or asset.get("_studio_result_origin") != origin or asset.get("_project_binding") !=
                            {"novel_id": nid, "branch_id": scope.get("branch_id"), "scope_key": context["scope_key"], "incarnation": context["incarnation"]}):
                    raise ValueError("STUDIO_TIMELINE_RECOVERY_CANDIDATE_INVALID")
                data = self.workspace.assets.content(asset["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                if hashlib.sha256(data).hexdigest() != captured["output_digest"]:
                    raise ValueError("STUDIO_TIMELINE_RECOVERY_BYTES_CHANGED")
                guard()
                return copy.deepcopy(asset)

    def review(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None, graph_source_guard=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if row["request_digest"] != action.expected_request_digest:
            raise CapabilityVersionConflict(self.view(row, owner))
        if owner == "timeline":
            with self.video_owner.studio_review_phase(jid):
                return self._review_timeline(nid, scope, actor, jid, row, context, action, guard,
                    graph_source_guard=graph_source_guard)
        if context["operation_id"] in {"m5.image.cutout", "m5.image.inpaint"}:
            guard = self._cutout_guard(guard)
        if context["operation_id"] == "m5.image.cutout":
            self._cutout_result_proof(row, self._cutout_inputs(nid, scope, context, guard))
        _, promote = self._callbacks(nid, scope, actor, context, guard, graph_source_guard=graph_source_guard)
        sources = self._source_guard(nid, scope, guard)
        if owner == "image":
            row = self._image(actor).accept_studio(nid, scope.get("branch_id"), actor, jid,
                expected_version=action.expected_version, expected_request_digest=action.expected_request_digest,
                expected_output_digest=action.reviewed_output_digest, guard=guard,
                source_guard=lambda: self._sources_current(nid, scope, context, guard), promote=promote,
                recover_review=self._review_compensation(nid, scope, actor, context, jid))
        elif owner == "audio":
            row = self._audio(scope, actor).review(nid, jid, action.expected_version, context, guard, sources, action.reviewed_output_digest, promote,
                recover_review=self._review_compensation(nid, scope, actor, context, jid))
        else:
            return self._review_video(nid, scope, actor, jid, row, context, action, guard, sources, promote)
        guard()
        return self.view(row, owner)

    def _review_video(self, nid, scope, actor, jid, captured, context, action, guard, sources, promote):
        with self.video.review_phase(jid):
            row = self.video.get(nid, scope.get("branch_id"), actor, jid, context=context, guard=guard)
            if row["version"] != captured["version"] or row["request_digest"] != action.expected_request_digest:
                raise CapabilityVersionConflict(self.view(row, "video"))
            candidate = row.get("output_candidate")
            if candidate is None or candidate["digest"] != action.reviewed_output_digest:
                raise StaleSourceError("STUDIO_REVIEW_OUTPUT_CHANGED")
            if row["version"] != action.expected_version:
                raise CapabilityVersionConflict(self.view(row, "video"))
            if row["status"] not in {"AWAITING_REVIEW", "SUCCEEDED", "REVIEWING", "APPROVED"}:
                raise ValueError("STUDIO_PRODUCTION_JOB_NOT_REVIEWABLE")
            for source in context["sources"]: sources(source)
            provenance = {"contract": "studio-production-review/1", "job_id": jid,
                "request_digest": row["request_digest"], "output_digest": candidate["digest"], "candidate_version": candidate["version"]}
            if row["status"] == "APPROVED":
                with self.store.source_lease(nid, scope):
                    with self.workspace._asset_scope(nid, scope):
                        meta = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                        if (meta.get("_owner_actor_id") is not None or meta.get("version") != candidate["version"] + 1
                                or meta.get("sha256") != candidate["digest"] or meta.get("deleted_at")
                                or meta.get("kind") != "video" or meta.get("novel_id") != nid or meta.get("branch_id") != scope.get("branch_id")
                                or meta.get("source_job_id") != jid or meta.get("_required_features") != [FLAG]
                                or meta.get("_project_binding") != {"novel_id": nid, "branch_id": scope.get("branch_id"),
                                    "scope_key": context["scope_key"], "incarnation": context["incarnation"]}
                                or meta.get("_origin_provenance") != {**provenance, "review_actor": actor}
                                or meta.get("_studio_result_origin") != self._media_result_origin(context, jid)
                                or row.get("approved_asset_version") != meta.get("version")):
                            raise StaleSourceError("STUDIO_CANDIDATE_APPROVAL_CHANGED")
                        data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                        if hashlib.sha256(data).hexdigest() != candidate["digest"] or len(data) != meta["size"]:
                            raise StaleSourceError("STUDIO_CANDIDATE_BYTES_CHANGED")
                guard()
                return self.view(row, "video")
            if row["status"] != "REVIEWING":
                row = self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, row["version"],
                    lambda current: current.update(status="REVIEWING"), context=context)
            reviewed_version = row["version"]
            def job_current():
                current = self.video_owner._studio_read(nid, scope.get("branch_id"), actor, jid, context=context)
                if (current["version"] != reviewed_version or current["status"] != "REVIEWING"
                        or current["request_digest"] != action.expected_request_digest or current.get("output_candidate") != candidate):
                    raise ValueError("STUDIO_REVIEW_ATTEMPT_CHANGED")
            try:
                asset = promote(candidate["id"], candidate["version"], provenance, job_current)
            except Exception:
                # Only the exact unpromoted reservation becomes cancellable/reviewable again;
                # durable promotion or ambiguous evidence remains REVIEWING.
                recover = self._review_compensation(nid, scope, actor, context, jid)
                def compensate():
                    def restore(current):
                        if (current["status"] != "REVIEWING" or current["request_digest"] != action.expected_request_digest
                                or current.get("output_candidate") != candidate):
                            raise ValueError("STUDIO_REVIEW_ATTEMPT_CHANGED")
                        current.update(status="AWAITING_REVIEW", review_state="HUMAN_REVIEW_REQUIRED")
                    self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, reviewed_version, restore, context=context)
                recover(candidate, compensate)
                raise
            job_current()
            row = self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, reviewed_version,
                lambda current: current.update(status="APPROVED", review_state="ORIGINAL_OWNER_REVIEWED", approved_asset_version=asset["version"]), context=context)
            guard()
            return self.view(row, "video")

    def _review_timeline(self, nid, scope, actor, jid, captured, context, action, guard, *, graph_source_guard=None):
        """Reserve and promote against one fixed original source/asset phase.

        A stale timeline is rejected before REVIEWING is reserved. Source edits,
        cancellation and another review cannot cross the short promotion window.
        Restart recovery accepts only this exact original promotion receipt.
        """
        _, promote = self._callbacks(nid, scope, actor, context, guard, graph_source_guard=graph_source_guard)
        with self.timeline_inputs.phase(nid, scope, actor, guard) as document:
            if context.get("graph_binding") is not None:
                if graph_source_guard is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_SOURCE_GUARD_REQUIRED")
                graph_asset_guard = graph_source_guard(document)
                if not callable(graph_asset_guard):
                    raise ValueError("CREATIVE_GRAPH_MEDIA_ASSET_GUARD_REQUIRED")
                graph_asset_guard()
            timeline = self._timeline_context_current(nid, scope, actor, context, document)
            self._timeline_sources_current(nid, scope, timeline["timeline"], guard)
            row = self.video_owner.get_studio(nid, scope.get("branch_id"), actor, jid, context=context, guard=guard)
            if row["version"] != action.expected_version or row["request_digest"] != action.expected_request_digest:
                raise CapabilityVersionConflict(self.view(row, "timeline"))
            if row["version"] != captured["version"] or row.get("output_candidate") != captured.get("output_candidate"):
                raise StaleSourceError("STUDIO_CANDIDATE_JOB_CHANGED")
            candidate = row.get("output_candidate")
            if candidate is None or candidate["digest"] != action.reviewed_output_digest:
                raise StaleSourceError("STUDIO_REVIEW_OUTPUT_CHANGED")
            if row["status"] not in {"AWAITING_REVIEW", "SUCCEEDED", "REVIEWING", "APPROVED"}:
                raise ValueError("STUDIO_PRODUCTION_JOB_NOT_REVIEWABLE")
            provenance = {"contract": "studio-production-review/1", "job_id": jid,
                "request_digest": row["request_digest"], "output_digest": candidate["digest"], "candidate_version": candidate["version"]}
            meta = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
            already_promoted = (meta.get("_owner_actor_id") is None
                and meta.get("_origin_provenance") == {**provenance, "review_actor": actor}
                and meta.get("version") == candidate["version"] + 1)
            private_current = meta.get("_owner_actor_id") == actor and meta.get("version") == candidate["version"]
            if (meta.get("sha256") != candidate["digest"] or meta.get("kind") != "video" or meta.get("deleted_at")
                    or meta.get("_studio_result_origin") != self._timeline_result_origin(context, jid)
                    or meta.get("novel_id") != nid or meta.get("branch_id") != scope.get("branch_id")
                    or meta.get("source_job_id") != jid or meta.get("_required_features") != [FLAG]
                    or meta.get("_project_binding") != {"novel_id": nid, "branch_id": scope.get("branch_id"),
                        "scope_key": context["scope_key"], "incarnation": context["incarnation"]}
                    or not (private_current or already_promoted and row["status"] in {"REVIEWING", "APPROVED"})):
                raise StaleSourceError("STUDIO_CANDIDATE_RECEIPT_MISMATCH")
            data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
            if hashlib.sha256(data).hexdigest() != candidate["digest"]:
                raise StaleSourceError("STUDIO_CANDIDATE_BYTES_CHANGED")
            if row["status"] == "APPROVED":
                if not already_promoted or row.get("approved_asset_version") != meta["version"]:
                    raise StaleSourceError("STUDIO_CANDIDATE_APPROVAL_CHANGED")
                guard()
                return self.view(row, "timeline")
            previous_status = row["status"]
            if previous_status != "REVIEWING":
                guard()
                row = self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, row["version"],
                    lambda current: current.update(status="REVIEWING"), context=context)
            reviewed_version = row["version"]
            def queue_current():
                current = self.video_owner._studio_read(nid, scope.get("branch_id"), actor, jid, context=context)
                if (current["version"] != reviewed_version or current["status"] != "REVIEWING"
                        or current["request_digest"] != action.expected_request_digest
                        or current.get("output_candidate") != candidate):
                    raise ValueError("STUDIO_REVIEW_ATTEMPT_CHANGED")
            def job_current():
                guard()
                queue_current()
            try:
                asset = promote(candidate["id"], candidate["version"], provenance, job_current)
            except Exception:
                # Roll back only a known unpromoted private candidate. A failed
                # write with a durable promotion remains REVIEWING for exact
                # original-receipt recovery; it must never become discardable.
                actual = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
                if (actual.get("_owner_actor_id") == actor and actual.get("version") == candidate["version"]
                        and actual.get("sha256") == candidate["digest"]):
                    # Internal compensation of this exact reservation grants
                    # no authority and performs no promotion or external call.
                    # A revoked Host still receives its original auth error;
                    # it cannot strand a proven unpromoted job in REVIEWING.
                    queue_current()
                    self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, reviewed_version,
                        lambda current: current.update(status=previous_status if previous_status != "REVIEWING" else "SUCCEEDED",
                            review_state="HUMAN_REVIEW_REQUIRED"), context=context)
                raise
            job_current()
            row = self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, reviewed_version,
                lambda current: current.update(status="APPROVED", review_state="ORIGINAL_OWNER_REVIEWED", approved_asset_version=asset["version"]), context=context)
            guard()
            return self.view(row, "timeline")

    def timeline_list(self, nid, scope, actor, guard):
        self._base(nid, scope, actor, guard)
        rows = [self._timeline_view(row, scope) for row in self.store.read(nid, scope)["collections"].get(TIMELINES, {}).values() if row.get("created_by") == actor]
        guard()
        return {"items": sorted(rows, key=lambda row: (row["updated_at"], row["id"]), reverse=True)}

    @staticmethod
    def _timeline_view(row, scope):
        result = {**{k: copy.deepcopy(row[k]) for k in ("id", "novel_id", "title", "version", "timeline_digest", "timeline", "created_at", "updated_at")},
            "branch_id": scope.get("branch_id")}
        transfer = row.get("last_edit") or {}
        if transfer.get("operation") == "TRANSFER_IMPORT":
            if (row["version"] != transfer.get("input_version", -1) + 1 or row["timeline_digest"] != transfer.get("output_digest")):
                raise ValueError("STUDIO_TRANSFER_RECEIPT_CORRUPT")
            result["transfer_receipt"] = {key: copy.deepcopy(transfer[key]) for key in (
                "operation", "request_id", "input_version", "input_digest", "output_digest", "preview_digest", "format",
                "transfer_input_digest", "acknowledge_losses")}
        return result

    def _callbacks(self, nid, scope, actor, context, guard, *, graph_source_guard=None):
        def timeline_current(document):
            asset_guard = None
            if context.get("graph_binding") is not None:
                if graph_source_guard is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_SOURCE_GUARD_REQUIRED")
                asset_guard = graph_source_guard(document)
                if not callable(asset_guard):
                    raise ValueError("CREATIVE_GRAPH_MEDIA_ASSET_GUARD_REQUIRED")
            snapshot = context.get("timeline_snapshot")
            if snapshot:
                self._timeline_context_current(nid, scope, actor, context, document)
            return asset_guard
        def publish(data, kind, filename, measured, jid, job_guard=lambda: None):
            # The source document is leased before assets -> project. Never
            # query the scope/job store while holding the asset/project lease.
            with self.store.source_lease(nid, scope) as document:
                graph_asset_guard = timeline_current(document)
                for source in context["sources"]:
                    if source["kind"] != "ASSET": self.source(nid, scope, source, guard)
                with self.workspace._asset_scope(nid, scope):
                    if self.store.incarnation(nid) != context["incarnation"]: raise StaleSourceError("STUDIO_OWNER_CHANGED")
                    if graph_asset_guard is not None: graph_asset_guard()
                    if context["operation_id"] in {"m5.image.cutout", "m5.image.inpaint"}: self._cutout_inputs(nid, scope, context, guard, under_asset_lease=True)
                    for source in context["sources"]:
                        if source["kind"] == "ASSET":
                            row = self.workspace._row(nid, scope, source["id"])
                            if (row["version"], row["sha256"]) != (source["version"], source["digest"]): raise StaleSourceError("STUDIO_SOURCE_CHANGED")
                            self.workspace.assets.content(row["id"], branch_id=scope.get("branch_id"))
                    guard()
                    usage = self.workspace.assets.project_usage(nid, branch_id=scope.get("branch_id"))
                    key = "studio-production:" + digest([context["scope_key"], context["incarnation"], actor, jid])
                    prior = next((r for r in self.workspace.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=True, actor_id=actor) if r.get("idempotency_key") == key), None)
                    if prior is None:
                        if usage["count"] >= self.workspace.MAX_ASSETS or usage["bytes"] + len(data) > self.workspace.MAX_PROJECT_BYTES:
                            raise ValueError("CREATIVE_PROJECT_ASSET_QUOTA")
                        self.workspace.storage_admission.require(len(data))
                    binding = context.get("provider_binding") or {}
                    origin = {"contract": "studio-production-result/1", **{k: context[k] for k in ("scope_key", "incarnation", "actor", "request_digest", "operation_id", "sources")},
                        "job_id": jid, "provider_id": binding.get("provider_id"), "model_id": binding.get("model_id"), "license_note": context.get("license_note", "")}
                    if context.get("graph_binding") is not None:
                        origin["graph_binding"] = copy.deepcopy(context["graph_binding"])
                    def commit():
                        guard(); job_guard()
                        if prior is None: self.workspace.storage_admission.require(1)
                    return self.workspace.assets.create(nid, filename, base64.b64encode(data).decode("ascii"), measured["media_type"], kind,
                        key, branch_id=scope.get("branch_id"), required_features=(FLAG,), owner_actor_id=actor, guard=commit,
                        _initial_studio_result=origin)
        def promote(aid, expected_version, provenance, job_guard=lambda: None):
            shared_phase = bool(context.get("timeline_snapshot")) and self.timeline_inputs.in_phase(nid, scope, actor)
            phase = nullcontext(self.store.read(nid, scope)) if shared_phase else self.store.source_lease(nid, scope)
            with phase as document:
                graph_asset_guard = timeline_current(document)
                for source in context["sources"]:
                    if source["kind"] != "ASSET": self.source(nid, scope, source, guard)
                asset_phase = nullcontext() if shared_phase else self.workspace._asset_scope(nid, scope)
                with asset_phase:
                    if self.store.incarnation(nid) != context["incarnation"]: raise StaleSourceError("STUDIO_OWNER_CHANGED")
                    if graph_asset_guard is not None: graph_asset_guard()
                    if context["operation_id"] in {"m5.image.cutout", "m5.image.inpaint"}: self._cutout_inputs(nid, scope, context, guard, under_asset_lease=True)
                    for source in context["sources"]:
                        if source["kind"] == "ASSET":
                            row = self.workspace._row(nid, scope, source["id"])
                            if (row["version"], row["sha256"]) != (source["version"], source["digest"]): raise StaleSourceError("STUDIO_SOURCE_CHANGED")
                            self.workspace.assets.content(row["id"], branch_id=scope.get("branch_id"))
                    candidate = self.workspace.assets.get(aid, branch_id=scope.get("branch_id"), actor_id=actor)
                    origin = candidate.get("_studio_result_origin", {})
                    if origin.get("graph_binding") != context.get("graph_binding") or any(origin.get(k) != context.get(k) for k in ("scope_key", "incarnation", "actor", "request_digest")):
                        raise ValueError("STUDIO_CANDIDATE_OWNER_MISMATCH")
                    def commit(): guard(); job_guard()
                    return self.workspace.assets.promote_owned(aid, actor_id=actor, branch_id=scope.get("branch_id"),
                        expected_version=expected_version, provenance=provenance, guard=commit)
        return publish, promote

    def providers(self, nid, scope, actor, guard):
        """Configuration references only. No health probe or credential read."""
        self._base(nid, scope, actor, guard)
        from ..asset_provider_config import load
        from ..audio_providers import provider_catalog
        candidates = []
        for pid, config in load().items():
            model = config.get("default_model", "")
            if model:
                try: image_config = self._image_configuration(self.image_registry.get(pid))
                except ValueError: image_config = None
                operations = ["m5.image." + op for op in image_config["operations"]] if image_config else ["m5.image.t2i", "m5.image.i2i"]
                for operation in operations: candidates.append((pid, model, operation))
        from ..model_center.discovery_bridge import LocalImageAdapter
        for pid, provider in self.image_registry._providers.copy().items():
            if type(provider) is not LocalImageAdapter:
                continue
            try:
                config = provider.studio_configuration()
            except ValueError:
                continue
            for operation in config.get("image_operations", ["t2i"]):
                candidate = (pid, config["default_model"], "m5.image." + operation)
                if candidate not in candidates:
                    candidates.append(candidate)
        for pid, config in self.video_configs.items():
            model = config.get("model_id", "")
            if model:
                for operation in ("m7.video.t2v", "m7.video.i2v", "m7.video.v2v"): candidates.append((pid, model, operation))
        for config in provider_catalog():
            for capability, operation in (("TTS", "m8.audio.speech"), ("MUSIC", "m8.audio.music"), ("SFX", "m8.audio.effects")):
                if capability in config.get("capabilities", []) and config.get("default_model"):
                    candidates.append((config["provider_id"], config["default_model"], operation))
        rows = []
        for pid, model, operation in candidates:
            command = ProviderSelection(operation_id=operation, provider_id=pid, model_id=model)
            try:
                binding = self._binding(command)
                parameters = self._parameters(command)
            except ValueError: continue
            row = {"operation_id": operation, "provider_id": pid, "model_id": model,
                "local": binding["local"], "route_digest": binding["route_digest"], "capability": binding["capability"],
                "supported_parameters": parameters,
                "readiness": "CONFIGURED_NOT_VERIFIED", "product_acceptance": "LOCAL_REQUIRED"}
            if operation.startswith("m5."):
                image_config = self._image_configuration(self.image_registry.get(pid))
                if image_config:
                    from ..services.studio_image_provider_recipes import public_capabilities
                    row["image_capabilities"] = public_capabilities(image_config)
            rows.append(row)
        guard()
        return {"items": rows, "automatic_runtime_start": False, "health_probed": False, "credentials_read": False}

    def execute(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None, graph_guard=None, graph_source_guard=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if (row["version"], row["request_digest"]) != (action.expected_version, action.expected_request_digest):
            raise CapabilityVersionConflict(self.view(row, owner))
        if owner == "timeline":
            if context.get("graph_binding") is None:
                raise ValueError("STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY")
            if graph_guard is None or graph_source_guard is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_SOURCE_GUARD_REQUIRED")
            def timeline_guard():
                guard()
                graph_guard()
            publish, _ = self._callbacks(nid, scope, actor, context, guard, graph_source_guard=graph_source_guard)
            rendered = self.video_owner.execute_studio(nid, scope.get("branch_id"), actor, jid,
                action.expected_version, action.expected_request_digest, context=context, guard=timeline_guard,
                # source() already holds its asset lease during its final guard;
                # only Host authority is safe there. Original executor guards
                # fence Graph before/after reads; publication takes raw first.
                source_guard=self._source_guard(nid, scope, guard), publish=publish,
                inspect_source=self._source_guard(nid, scope, guard))
            return self.view(rendered, owner)
        command = MediaCommand.model_validate(context["command"])
        host_guard = guard
        def guard():
            host_guard()
            if command.operation_id in {"m5.image.cutout", "m5.image.inpaint"}:
                from ..experimental.flags import require_flag
                require_flag("asset_lineage_v2")
            if command.operation_id not in {"m5.image.cutout", "m8.audio.trim"}:
                from .ai_execution import require_execution
                require_execution()
                binding = context.get("provider_binding")
                if binding and not binding["local"]:
                    from ..config import settings
                    if not settings.enable_cloud or not command.allow_cloud: raise ValueError("STUDIO_CLOUD_DISABLED")
        guard()
        def before_send(*args):
            if context.get("graph_binding") is not None:
                if graph_guard is None: raise ValueError("CREATIVE_GRAPH_MEDIA_DISPATCH_GUARD_REQUIRED")
                graph_guard()
            binding = self._binding(command)
            self._parameters(command)
            if binding != context["provider_binding"]: raise StaleSourceError("STUDIO_PROVIDER_ROUTE_CHANGED")
            if self._recipe(command) != context.get("execution_recipe"):
                raise StaleSourceError("STUDIO_EXECUTION_RECIPE_CHANGED")
            if owner == "video" and args and self.video_providers.get(binding["provider_id"]) is not args[-1]:
                raise StaleSourceError("STUDIO_PROVIDER_INSTANCE_CHANGED")
            self._egress(nid, scope, command, binding, guard)
        source_guard = self._source_guard(nid, scope, guard)
        publish, _ = self._callbacks(nid, scope, actor, context, guard, graph_source_guard=graph_source_guard)
        branch = scope.get("branch_id")
        if owner == "image":
            row = self._image(actor).execute_studio(nid, branch, actor, jid, self.image_registry,
                expected_version=action.expected_version, expected_request_digest=action.expected_request_digest,
                guard=guard, source_guard=lambda: self._sources_current(nid, scope, context, guard), dispatch_guard=before_send,
                read_images=lambda: ([item["data"] for item in self._cutout_inputs(nid, scope, context, guard)]
                    if command.operation_id in {"m5.image.cutout", "m5.image.inpaint"} else [source_guard(s)["data"] for s in context["sources"] if s["kind"] == "ASSET" and s["asset_kind"] == "image"]), publish=publish)
        elif owner == "video":
            def resolve(binding):
                if self._binding(command) != binding: raise StaleSourceError("STUDIO_PROVIDER_ROUTE_CHANGED")
                return self.video_providers[binding["provider_id"]]
            row = self.video.execute(nid, branch, actor, jid, action, context=context, guard=guard, source_guard=source_guard,
                resolve=resolve, before_send=before_send, publish=publish)
        else:
            from ..audio_providers import resolve_provider
            def resolve(pid, capability):
                before_send()
                return resolve_provider(pid, capability, self.vault, self.transport)
            execution_guard = guard
            if command.operation_id == "m8.audio.trim" and context.get("graph_binding") is not None:
                if graph_guard is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_DISPATCH_GUARD_REQUIRED")
                def execution_guard():
                    guard(); graph_guard()
            row = self._audio(scope, actor).execute(nid, jid, action.expected_version, context, execution_guard, source_guard, resolve, publish, before_send,
                inspect_source=source_guard)
        guard()
        return self.view(row, owner)

    def refresh_video(self, nid, scope, actor, jid, action, guard, *, graph_binding=None, graph_guard=None, graph_source_guard=None):
        row, context = self._row(nid, scope, actor, "video", jid, guard, graph_binding=graph_binding)
        command = MediaCommand.model_validate(context["command"])
        def resolve(binding):
            if context.get("graph_binding") is not None:
                if graph_guard is None: raise ValueError("CREATIVE_GRAPH_MEDIA_DISPATCH_GUARD_REQUIRED")
                graph_guard()
            if self._binding(command) != binding: raise StaleSourceError("STUDIO_PROVIDER_ROUTE_CHANGED")
            if self._recipe(command) != context.get("execution_recipe"): raise StaleSourceError("STUDIO_EXECUTION_RECIPE_CHANGED")
            self._egress(nid, scope, command, binding, guard)
            return self.video_providers[binding["provider_id"]]
        publish, _ = self._callbacks(nid, scope, actor, context, guard, graph_source_guard=graph_source_guard)
        row = self.video.refresh(nid, scope.get("branch_id"), actor, jid, action, context=context, guard=guard,
            source_guard=self._source_guard(nid, scope, guard), resolve=resolve, publish=publish)
        return self.view(row, "video")

    def timeline_get(self, nid, scope, actor, tid, guard):
        context = self._base(nid, scope, actor, guard)
        row = self._owned_timeline(nid, scope, actor, tid, context, self.store.read(nid, scope))
        guard()
        return self._timeline_view(row, scope)

    def _owned_timeline(self, nid, scope, actor, tid, context, document):
        from ..services.studio_timeline_render import normalize_studio_timeline
        row = document["collections"].get(TIMELINES, {}).get(tid)
        if (not isinstance(row, dict) or row.get("created_by") != actor or row.get("novel_id") != nid
                or row.get("scope") != scope or row.get(BINDING) != context["incarnation"]):
            raise FileNotFoundError(tid)
        normalized = normalize_studio_timeline(row.get("timeline"))
        if (normalized != row["timeline"] or digest(normalized) != row.get("timeline_digest")
                or type(row.get("version")) is not int or row["version"] < 1 or not isinstance(row.get("history"), list)):
            raise ValueError("STUDIO_TIMELINE_RECORD_CORRUPT")
        return row

    def _timeline_context_current(self, nid, scope, actor, context, document):
        from ..services.studio_timeline_render import studio_sources
        snapshot = context.get("timeline_snapshot")
        if not isinstance(snapshot, dict):
            raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        row = self._owned_timeline(nid, scope, actor, snapshot.get("id"), context, document)
        if ((row["version"], row["timeline_digest"]) != (snapshot.get("version"), snapshot.get("digest"))
                or studio_sources(row["timeline"]) != context.get("sources")):
            raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        return row

    @staticmethod
    def _timeline_result_origin(context, jid):
        origin = {"contract": "studio-production-result/1", "job_id": jid,
            **{field: copy.deepcopy(context[field]) for field in ("scope_key", "incarnation", "actor", "request_digest", "operation_id", "sources")},
            "provider_id": None, "model_id": None, "license_note": context.get("license_note", "")}
        if context.get("graph_binding") is not None:
            origin["graph_binding"] = copy.deepcopy(context["graph_binding"])
        return origin

    def _timeline_sources_current(self, nid, scope, timeline, guard):
        """Only inside the existing raw scope -> asset -> project phase."""
        from ..services.studio_timeline_render import studio_sources
        for source in studio_sources(timeline):
            row = self.workspace._row(nid, scope, source["id"])
            if (row.get("_owner_actor_id") or (row["version"], row["sha256"], row["kind"]) !=
                    (source["version"], source["digest"], source["asset_kind"])):
                raise StaleSourceError("STUDIO_TIMELINE_SOURCE_CHANGED")
            self.workspace.assets.content(row["id"], branch_id=scope.get("branch_id"))
        guard()

    def timeline_save(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_render import normalize_studio_timeline, studio_sources
        from ..services.studio_timeline_edit import require_timeline_lock_preservation
        body = TimelineSave.model_validate(value)
        context = self._base(nid, scope, actor, guard)
        timeline = normalize_studio_timeline(body.timeline)
        with self.timeline_inputs.transaction(nid, scope, actor, guard) as document:
            self._timeline_sources_current(nid, scope, timeline, guard)
            collection = document["collections"].setdefault(TIMELINES, {})
            if tid is None:
                if body.expected_version != 0 or len(collection) >= 25: raise ValueError("STUDIO_TIMELINE_CREATE_LIMIT_OR_VERSION")
                row = new_row(nid, scope, actor, {"title": body.title, "timeline": timeline, "timeline_digest": digest(timeline), BINDING: context["incarnation"]})
                collection[row["id"]] = row
            else:
                row = self._owned_timeline(nid, scope, actor, tid, context, document)
                timeline = require_timeline_lock_preservation(row["timeline"], timeline)
                if len(row["history"]) >= 100: raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
                change_row(row, actor, body.expected_version, lambda current: current.update(title=body.title, timeline=timeline,
                    timeline_digest=digest(timeline), last_edit=None))
            if len(canonical(collection).encode()) > 4 * 1024 * 1024: raise ValueError("STUDIO_TIMELINE_STORAGE_LIMIT")
            guard()
        return self.timeline_get(nid, scope, actor, row["id"], guard)

    def timeline_edit(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_edit import apply_timeline_edits
        body = TimelineEdit.model_validate(value)
        context = self._base(nid, scope, actor, guard)
        request_digest = digest(body.model_dump())
        with self.timeline_inputs.transaction(nid, scope, actor, guard) as document:
            row = self._owned_timeline(nid, scope, actor, tid, context, document)
            prior = row.get("last_edit") or {}
            if (prior.get("request_id") == body.request_id and prior.get("request_digest") == request_digest
                    and prior.get("input_version") == body.expected_version and row["version"] == body.expected_version + 1
                    and prior.get("output_digest") == row["timeline_digest"]):
                self._timeline_sources_current(nid, scope, row["timeline"], guard)
            else:
                if row["version"] != body.expected_version or row["timeline_digest"] != body.reviewed_timeline_digest:
                    raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
                if prior.get("request_id") == body.request_id:
                    raise ValueError("STUDIO_TIMELINE_EDIT_IDEMPOTENCY_CONFLICT")
                if any((entry.get("last_edit") or {}).get("request_id") == body.request_id for entry in row["history"]):
                    raise ValueError("STUDIO_TIMELINE_EDIT_IDEMPOTENCY_CONFLICT")
                if len(row["history"]) >= 100: raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
                timeline = apply_timeline_edits(row["timeline"], body.operations)
                self._timeline_sources_current(nid, scope, timeline, guard)
                receipt = {"request_id": body.request_id, "request_digest": request_digest,
                    "input_version": row["version"], "input_digest": row["timeline_digest"], "output_digest": digest(timeline)}
                change_row(row, actor, body.expected_version, lambda current: current.update(timeline=timeline,
                    timeline_digest=receipt["output_digest"], last_edit=receipt))
            result = self._timeline_view(row, scope)
            guard()
        return result

    def timeline_history(self, nid, scope, actor, tid, guard):
        context = self._base(nid, scope, actor, guard)
        row = self._owned_timeline(nid, scope, actor, tid, context, self.store.read(nid, scope))
        result = {"timeline_id": tid, "current_version": row["version"],
            "items": [self._timeline_view(version, scope) for version in reversed(row["history"])]}
        guard()
        return result

    def timeline_restore(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_render import normalize_studio_timeline
        from ..services.studio_timeline_edit import require_timeline_lock_preservation
        body = TimelineRestore.model_validate(value)
        context = self._base(nid, scope, actor, guard)
        with self.timeline_inputs.transaction(nid, scope, actor, guard) as document:
            row = self._owned_timeline(nid, scope, actor, tid, context, document)
            if row["version"] != body.expected_version or row["timeline_digest"] != body.reviewed_timeline_digest:
                raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
            versions = [entry for entry in row["history"] if entry.get("version") == body.restore_version]
            if len(versions) != 1 or versions[0].get("timeline_digest") != body.restore_digest:
                raise ValueError("STUDIO_TIMELINE_HISTORY_VERSION_INVALID")
            original = versions[0]
            timeline = normalize_studio_timeline(original["timeline"])
            if digest(timeline) != body.restore_digest: raise ValueError("STUDIO_TIMELINE_HISTORY_CORRUPT")
            timeline = require_timeline_lock_preservation(row["timeline"], timeline)
            self._timeline_sources_current(nid, scope, timeline, guard)
            if len(row["history"]) >= 100: raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
            change_row(row, actor, body.expected_version, lambda current: current.update(title=original["title"], timeline=timeline,
                timeline_digest=body.restore_digest, last_edit=None))
            result = self._timeline_view(row, scope)
            guard()
        return result

    def timeline_export_preview(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_render import studio_sources, RENDER_TIMEOUT_SECONDS
        from ..services.studio_timeline_export import normalize_export_profile, validate_export_admission
        body = TimelineExportPreview.model_validate(value)
        context = self._base(nid, scope, actor, guard)
        profile = normalize_export_profile(body.export_profile)
        with self.timeline_inputs.phase(nid, scope, actor, guard) as document:
            row = self._owned_timeline(nid, scope, actor, tid, context, document)
            if row["version"] != body.expected_version or row["timeline_digest"] != body.reviewed_timeline_digest:
                raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
            self._timeline_sources_current(nid, scope, row["timeline"], guard)
            validate_export_admission(row["timeline"], profile, self.workspace.assets.MAX_BYTES)
            recipe = {"contract": "studio-execution-recipe/1", "operation_id": "m9.timeline.multitrack", "adapter": "LOCAL_FFMPEG",
                "output_profile": profile["preset"], "timeline": copy.deepcopy(row["timeline"]),
                "export_profile": profile, "automatic_fallback": False}
            recipe["recipe_digest"] = digest(recipe)
            result = {"contract": "studio-timeline-export-preview/1", "timeline_snapshot": {"id": tid, "version": row["version"], "digest": row["timeline_digest"]},
                "export_profile": profile, "sources": studio_sources(row["timeline"]), "execution_recipe": recipe,
                "limits": {"max_output_bytes": self.workspace.assets.MAX_BYTES, "render_timeout_seconds": RENDER_TIMEOUT_SECONDS},
                "model_called": False, "automatic_replay": False, "product_acceptance": "LOCAL_REQUIRED"}
            result["preview_digest"] = digest([context, result])
            guard()
        return result

    def timeline_export(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_export import export_profile_digest
        body = TimelineExport.model_validate(value)
        preview = self.timeline_export_preview(nid, scope, actor, tid, body.model_dump(exclude={"request_id", "reviewed_export_digest"}), guard)
        if preview["preview_digest"] != body.reviewed_export_digest:
            raise StaleSourceError("STUDIO_TIMELINE_EXPORT_PREVIEW_CHANGED")
        context = self._base(nid, scope, actor, guard)
        context.update(request_id=body.request_id, operation_id="m9.timeline.multitrack", sources=copy.deepcopy(preview["sources"]),
            timeline_snapshot=copy.deepcopy(preview["timeline_snapshot"]), provider_binding=None, license_note="", rights={"license_note": ""},
            execution_recipe=copy.deepcopy(preview["execution_recipe"]), export_profile=copy.deepcopy(preview["export_profile"]),
            export_profile_digest=export_profile_digest(preview["export_profile"]),
            reviewed_export_digest=preview["preview_digest"])
        context["request_digest"] = digest(context)
        def current():
            # timeline_get checks live authority before any read and again
            # afterwards; avoid an adjacent duplicate PostgreSQL connection.
            actual = self.timeline_get(nid, scope, actor, tid, guard)
            if (actual["version"], actual["timeline_digest"]) != (body.expected_version, body.reviewed_timeline_digest):
                raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        publish, _ = self._callbacks(nid, scope, actor, context, guard)
        rendered = self.video_owner.create_studio(nid, scope.get("branch_id"), actor, preview["execution_recipe"]["timeline"],
            context=context, guard=current, source_guard=self._source_guard(nid, scope, guard), publish=publish,
            export_profile=preview["export_profile"], inspect_source=self._source_guard(nid, scope, guard))
        return self.view(rendered, "timeline")

    def timeline_render(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_render import studio_sources
        body = TimelineRender.model_validate(value)
        row = self.timeline_get(nid, scope, actor, tid, guard)
        if row["version"] != body.expected_version or row["timeline_digest"] != body.reviewed_timeline_digest:
            raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        context = self._base(nid, scope, actor, guard)
        context.update(request_id=body.request_id, operation_id="m9.timeline.multitrack", sources=studio_sources(row["timeline"]),
            timeline_snapshot={"id": tid, "version": row["version"], "digest": row["timeline_digest"]}, provider_binding=None, license_note="", rights={"license_note": ""})
        recipe = {"contract": "studio-execution-recipe/1", "operation_id": "m9.timeline.multitrack", "adapter": "LOCAL_FFMPEG",
            "output_profile": "STUDIO_MULTITRACK_LOCAL_FFMPEG", "timeline": copy.deepcopy(row["timeline"]), "automatic_fallback": False}
        recipe["recipe_digest"] = digest(recipe)
        context["execution_recipe"] = recipe
        context["request_digest"] = digest(context)
        def current():
            # Keep the original live checks at both sides of timeline_get.
            actual = self.timeline_get(nid, scope, actor, tid, guard)
            if (actual["version"], actual["timeline_digest"]) != (row["version"], row["timeline_digest"]): raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        publish, _ = self._callbacks(nid, scope, actor, context, guard)
        rendered = self.video_owner.create_studio(nid, scope.get("branch_id"), actor, row["timeline"], context=context,
            guard=current, source_guard=self._source_guard(nid, scope, guard), publish=publish,
            inspect_source=self._source_guard(nid, scope, guard))
        return self.view(rendered, "timeline")
