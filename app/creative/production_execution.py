"""Explicit media execution adapters on existing job, source and asset owners.

This module owns no queue, credential store, scheduler or binary directory.
Only editable timeline documents live in the original incarnation-bound scope.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import ipaddress
from urllib.parse import urlsplit

from ..experimental.common import StaleSourceError, new_row, change_row
from ..experimental.store import canonical
from ..media_files import inspect_image, inspect_media
from ..services.v1_capability_service import CapabilityVersionConflict
from .production_execution_models import MediaCommand, MediaCreate, ProviderSelection, TimelineSave, TimelineRender
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

    def source(self, nid, scope, snapshot, guard):
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
        measured = inspect_image(data) if row["kind"] == "image" else inspect_media(data, row["kind"])
        guard()
        return {"data": data, "measured": measured, "snapshot": copy.deepcopy(snapshot), "row": row}

    def _source_guard(self, nid, scope, guard):
        return lambda snapshot: self.source(nid, scope, snapshot, guard)

    def _binding(self, command):
        if command.operation_id == "m8.audio.trim": return None
        pid, mid, operation = command.provider_id, command.model_id, command.operation_id
        if operation.startswith("m5."):
            from ..asset_provider_config import load
            from ..asset_providers import IMAGE_PROVIDER_CATALOG
            config = {**IMAGE_PROVIDER_CATALOG.get(pid, {}), **load().get(pid, {})}
            provider = self.image_registry.get(pid)
            capability = "IMAGE_EDIT" if operation.endswith("i2i") else "TEXT_TO_IMAGE"
            if capability == "IMAGE_EDIT" and not callable(getattr(provider, "edit", None)):
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
        if operation.startswith("m8."):
            # Match the original audio resolver without resolving credentials or
            # probing health while listing/previewing configuration.
            binding["endpoint"] = endpoint.rstrip("/")
            try: ipaddress.ip_address(urlsplit(endpoint).hostname or "")
            except ValueError: binding["local"] = False
        binding["route_digest"] = digest({**binding, "config": {k: config.get(k) for k in
            ("enabled", "local", "requires_credential", "default_model", "model_id", "api_style", "capabilities", "video_to_video")}})
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
        if command.operation_id.startswith("m5."):
            provider = self.image_registry.get(command.provider_id)
            names = getattr(provider, "supported_parameters", None)
            if command.operation_id == "m5.image.i2i": names = getattr(provider, "edit_supported_parameters", names)
            if names is None: raise ValueError("STUDIO_PROVIDER_PARAMETER_CONTRACT_REQUIRED")
            if isinstance(command, MediaCommand):
                from ..asset_providers import validate_image_parameters
                validate_image_parameters(command.parameters.model_dump(exclude_none=True), names)
                if command.operation_id == "m5.image.i2i" and sum(s.kind == "ASSET" for s in command.source_snapshots) > getattr(provider, "edit_reference_limit", 0):
                    raise ValueError("STUDIO_PROVIDER_IMAGE_REFERENCE_LIMIT")
            return list(names)
        return {"m7.video.t2v": ["width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"],
            "m7.video.i2v": ["width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"],
            "m7.video.v2v": ["width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"],
            "m8.audio.speech": ["voice_id", "speech_rate"], "m8.audio.music": ["duration_seconds", "seed"],
            "m8.audio.effects": ["duration_seconds", "seed"], "m8.audio.trim": ["in_ms", "out_ms"]}[command.operation_id]

    def preview(self, nid, scope, actor, value, guard, *, graph_binding=None):
        command = MediaCommand.model_validate(value)
        context = self._base(nid, scope, actor, guard)
        if graph_binding is not None:
            from .graph_media_binding import validate_graph_binding
            context["graph_binding"] = validate_graph_binding(graph_binding, context)
        sources = [s.model_dump(exclude={"reference_only"}, exclude_none=True) for s in command.source_snapshots]
        evidence = []
        for snapshot in sources:
            source = self.source(nid, scope, snapshot, guard)
            evidence.append({"snapshot": snapshot, "measured": source.get("measured")})
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
        if command.operation_id.startswith("m5."):
            from ..asset_providers import AssetGenerationRequest, ComfyUIImageProvider, Automatic1111ImageProvider
            provider = self.image_registry.get(command.provider_id)
            if isinstance(provider, ComfyUIImageProvider):
                recipe["adapter"] = "COMFYUI_BUILTIN_IMAGE"
                workflow = provider._workflow(AssetGenerationRequest(command.provider_id, command.model_id,
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
            recipe.update(adapter="LOCAL_FFMPEG", output_profile="PCM_S16LE_WAV_48000_STEREO")
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
            **{key: copy.deepcopy(row.get(key)) for key in ("id", "novel_id", "branch_id", "version", "status", "request_digest", "receipt_digest", "attempt", "created_at", "updated_at", "error_code", "review_state", "cancellation_mode", "needs_reconciliation", "execution_state")},
            "operation_id": row.get("context", {}).get("operation_id"), "output_candidate": candidate,
            "timeline_snapshot": copy.deepcopy(row.get("context", {}).get("timeline_snapshot")),
            "sources": copy.deepcopy(row.get("context", {}).get("sources", [])),
            "command": command,
            "provider": {k: binding[k] for k in ("provider_id", "model_id", "local", "route_digest")} if binding else None,
            "execution_recipe": copy.deepcopy(context.get("execution_recipe")),
            "approved_asset_version": row.get("approved_asset_version", row.get("output_asset_version") if row.get("status") == "APPROVED" else None),
            "request_id": row.get("context", {}).get("request_id"), "product_acceptance": "LOCAL_REQUIRED",
            "automatic_replay": False, "remote_compute_may_continue": row.get("cancellation_mode") == "LOCAL_RESULT_DISCARD"}

    def create(self, nid, scope, actor, value, guard, *, graph_binding=None):
        body = MediaCreate.model_validate(value)
        preview, context, command = self.preview(nid, scope, actor, body.command, guard, graph_binding=graph_binding)
        if preview["preview_digest"] != body.reviewed_preview_digest:
            raise StaleSourceError("STUDIO_PRODUCTION_PREVIEW_CHANGED")
        payload = command.model_dump(exclude={"source_snapshots", "allow_cloud", "license_note", "request_id"})
        payload["parameters"] = command.parameters.model_dump(exclude_none=True)
        # Keep the exact reviewed command for later egress and route rechecks.
        context["command"] = command.model_dump()
        branch = scope.get("branch_id")
        if command.operation_id.startswith("m5."):
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
        with self.workspace._asset_scope(nid, scope):
            meta = self.workspace.assets.get(candidate["id"], branch_id=scope.get("branch_id"), actor_id=actor)
            origin = meta.get("_studio_result_origin", {})
            if (meta["sha256"] != candidate["digest"] or origin.get("job_id") != jid
                    or origin.get("graph_binding") != context.get("graph_binding")
                    or any(origin.get(k) != context[k] for k in ("actor", "scope_key", "incarnation", "request_digest"))):
                raise ValueError("STUDIO_CANDIDATE_RECEIPT_MISMATCH")
            data = self.workspace.assets.content(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
            guard()
        return self.workspace.assets.public(meta), data

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
        else: raise ValueError("STUDIO_RENDER_CANCEL_REQUIRES_EXECUTOR_OWNER")
        guard()
        return self.view(row, owner)

    def reconcile(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if (row["version"], row["request_digest"]) != (action.expected_version, action.expected_request_digest):
            raise CapabilityVersionConflict(self.view(row, owner))
        branch = scope.get("branch_id")
        if owner == "image":
            row = self._image(actor).reconcile_studio(nid, branch, actor, jid,
                expected_version=action.expected_version, expected_request_digest=action.expected_request_digest, guard=guard)
        elif owner == "audio":
            row = self._audio(scope, actor).reconcile(nid, jid, action.expected_version, context, guard,
                expected_request_digest=action.expected_request_digest)
        elif owner == "video":
            row = self.video.reconcile(nid, branch, actor, jid, action, context=context, guard=guard)
        else:
            row = self.video_owner.reconcile_studio(nid, branch, actor, jid, action.expected_version,
                action.expected_request_digest, context=context, guard=guard)
        guard()
        return self.view(row, owner)

    def review(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None, graph_source_guard=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if row["request_digest"] != action.expected_request_digest:
            raise CapabilityVersionConflict(self.view(row, owner))
        _, promote = self._callbacks(nid, scope, actor, context, guard, graph_source_guard=graph_source_guard)
        sources = self._source_guard(nid, scope, guard)
        if owner == "image":
            row = self._image(actor).accept_studio(nid, scope.get("branch_id"), actor, jid,
                expected_version=action.expected_version, expected_request_digest=action.expected_request_digest,
                expected_output_digest=action.reviewed_output_digest, guard=guard,
                source_guard=lambda: [sources(s) for s in context["sources"]], promote=promote)
        elif owner == "audio":
            row = self._audio(scope, actor).review(nid, jid, action.expected_version, context, guard, sources, action.reviewed_output_digest, promote)
        else:
            candidate = row.get("output_candidate")
            if candidate is None or candidate["digest"] != action.reviewed_output_digest:
                raise StaleSourceError("STUDIO_REVIEW_OUTPUT_CHANGED")
            if row["version"] != action.expected_version:
                raise CapabilityVersionConflict(self.view(row, owner))
            if row["status"] not in {"AWAITING_REVIEW", "SUCCEEDED", "REVIEWING", "APPROVED"}:
                raise ValueError("STUDIO_PRODUCTION_JOB_NOT_REVIEWABLE")
            for source in context["sources"]: sources(source)
            if row["status"] == "APPROVED": return self.view(row, owner)
            if row["status"] != "REVIEWING":
                row = self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, row["version"],
                    lambda current: current.update(status="REVIEWING"), context=context)
            reviewed_version = row["version"]
            provenance = {"contract": "studio-production-review/1", "job_id": jid,
                "request_digest": row["request_digest"], "output_digest": candidate["digest"], "candidate_version": candidate["version"]}
            def job_current():
                current = self.video_owner._studio_read(nid, scope.get("branch_id"), actor, jid, context=context)
                if current["version"] != reviewed_version or current["status"] != "REVIEWING":
                    raise ValueError("STUDIO_REVIEW_ATTEMPT_CHANGED")
            asset = promote(candidate["id"], candidate["version"], provenance, job_current)
            row = self.video_owner._studio_mutate(nid, scope.get("branch_id"), actor, jid, reviewed_version,
                lambda current: current.update(status="APPROVED", review_state="ORIGINAL_OWNER_REVIEWED", approved_asset_version=asset["version"]), context=context)
        guard()
        return self.view(row, owner)

    def timeline_list(self, nid, scope, actor, guard):
        self._base(nid, scope, actor, guard)
        rows = [self._timeline_view(row, scope) for row in self.store.read(nid, scope)["collections"].get(TIMELINES, {}).values() if row.get("created_by") == actor]
        guard()
        return {"items": sorted(rows, key=lambda row: (row["updated_at"], row["id"]), reverse=True)}

    @staticmethod
    def _timeline_view(row, scope):
        return {**{k: copy.deepcopy(row[k]) for k in ("id", "novel_id", "title", "version", "timeline_digest", "timeline", "created_at", "updated_at")},
            "branch_id": scope.get("branch_id")}

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
                row = document["collections"].get(TIMELINES, {}).get(snapshot["id"])
                if row is None or row.get("created_by") != actor or (row["version"], row["timeline_digest"]) != (snapshot["version"], snapshot["digest"]):
                    raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
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
            with self.store.source_lease(nid, scope) as document:
                graph_asset_guard = timeline_current(document)
                for source in context["sources"]:
                    if source["kind"] != "ASSET": self.source(nid, scope, source, guard)
                with self.workspace._asset_scope(nid, scope):
                    if self.store.incarnation(nid) != context["incarnation"]: raise StaleSourceError("STUDIO_OWNER_CHANGED")
                    if graph_asset_guard is not None: graph_asset_guard()
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
                for operation in ("m5.image.t2i", "m5.image.i2i"): candidates.append((pid, model, operation))
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
            rows.append({"operation_id": operation, "provider_id": pid, "model_id": model,
                "local": binding["local"], "route_digest": binding["route_digest"], "capability": binding["capability"],
                "supported_parameters": parameters,
                "readiness": "CONFIGURED_NOT_VERIFIED", "product_acceptance": "LOCAL_REQUIRED"})
        guard()
        return {"items": rows, "automatic_runtime_start": False, "health_probed": False, "credentials_read": False}

    def execute(self, nid, scope, actor, owner, jid, action, guard, *, graph_binding=None, graph_guard=None, graph_source_guard=None):
        row, context = self._row(nid, scope, actor, owner, jid, guard, graph_binding=graph_binding)
        if (row["version"], row["request_digest"]) != (action.expected_version, action.expected_request_digest):
            raise CapabilityVersionConflict(self.view(row, owner))
        if owner == "timeline": raise ValueError("STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY")
        command = MediaCommand.model_validate(context["command"])
        host_guard = guard
        def guard():
            host_guard()
            if command.operation_id != "m8.audio.trim":
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
                guard=guard, source_guard=lambda: [source_guard(s) for s in context["sources"]], dispatch_guard=before_send,
                read_images=lambda: [source_guard(s)["data"] for s in context["sources"] if s["kind"] == "ASSET" and s["asset_kind"] == "image"], publish=publish)
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
            row = self._audio(scope, actor).execute(nid, jid, action.expected_version, context, guard, source_guard, resolve, publish, before_send)
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
        self._base(nid, scope, actor, guard)
        row = self.store.read(nid, scope)["collections"].get(TIMELINES, {}).get(tid)
        if row is None or row.get("created_by") != actor: raise FileNotFoundError(tid)
        guard()
        return self._timeline_view(row, scope)

    def timeline_save(self, nid, scope, actor, tid, value, guard):
        from ..services.studio_timeline_render import normalize_studio_timeline, studio_sources
        body = TimelineSave.model_validate(value)
        context = self._base(nid, scope, actor, guard)
        timeline = normalize_studio_timeline(body.timeline)
        for source in studio_sources(timeline): self.source(nid, scope, source, guard)
        with self.store.transaction(nid, scope) as document:
            collection = document["collections"].setdefault(TIMELINES, {})
            if tid is None:
                if body.expected_version != 0 or len(collection) >= 25: raise ValueError("STUDIO_TIMELINE_CREATE_LIMIT_OR_VERSION")
                row = new_row(nid, scope, actor, {"title": body.title, "timeline": timeline, "timeline_digest": digest(timeline), BINDING: context["incarnation"]})
                collection[row["id"]] = row
            else:
                row = collection.get(tid)
                if row is None or row.get("created_by") != actor: raise FileNotFoundError(tid)
                if len(row["history"]) >= 100: raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
                change_row(row, actor, body.expected_version, lambda current: current.update(title=body.title, timeline=timeline, timeline_digest=digest(timeline)))
            if len(canonical(collection).encode()) > 4 * 1024 * 1024: raise ValueError("STUDIO_TIMELINE_STORAGE_LIMIT")
            guard()
        return self.timeline_get(nid, scope, actor, row["id"], guard)

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
            guard()
            actual = self.timeline_get(nid, scope, actor, tid, guard)
            if (actual["version"], actual["timeline_digest"]) != (row["version"], row["timeline_digest"]): raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        publish, _ = self._callbacks(nid, scope, actor, context, guard)
        rendered = self.video_owner.create_studio(nid, scope.get("branch_id"), actor, row["timeline"], context=context,
            guard=current, source_guard=self._source_guard(nid, scope, guard), publish=publish)
        return self.view(rendered, "timeline")
