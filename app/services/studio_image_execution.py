"""Guarded Studio adapter for the original ImageJobService and AssetLibrary.

No scheduler, provider registry, credential owner or asset store is introduced.
Publication/review callbacks retain original source -> asset -> project locking.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from contextlib import contextmanager

from ..asset_providers import AssetGenerationRequest, validate_image_parameters
from ..media_files import fetch_media_bytes, inspect_image
from ..repositories.file.mutation_coordinator import workspace_mutation
from ..repository import now

CONTRACT = "studio-image-execution/1"
MAX_BYTES = 25 * 1024 * 1024
MAX_VERSION = 2**53 - 1
STATES = {"QUEUED", "RUNNING", "FAILED", "UNKNOWN", "AWAITING_REVIEW", "REVIEWING", "APPROVED", "CANCELLED"}
OPERATIONS = {"m5.image.t2i", "m5.image.i2i", "m5.image.cutout", "m5.image.composite", "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"}
IMAGE_RUNTIME_FIELDS = {"image_source", "image_references", "mask_source", "image_layers"}
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_digest(value):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError("STUDIO_IMAGE_DIGEST_INVALID")


def _require_version(value):
    if type(value) is not int or not 1 <= value <= MAX_VERSION:
        raise ValueError("STUDIO_IMAGE_VERSION_INVALID")


def _text(value, limit=240):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("STUDIO_IMAGE_IDENTITY_INVALID")


def _no_secrets(value):
    forbidden = {"api_key", "secret", "password", "credentials", "credential", "authorization",
                 "session_token", "access_token", "host_token"}
    if isinstance(value, dict):
        if any(not isinstance(key, str) or key.lower() in forbidden for key in value):
            raise ValueError("STUDIO_IMAGE_CONTEXT_NOT_PUBLIC")
        for child in value.values():
            _no_secrets(child)
    elif isinstance(value, list):
        for child in value:
            _no_secrets(child)


def _payload(body):
    if hasattr(body, "model_dump"):
        body = body.model_dump()
    required = {"operation_id", "provider_id", "model_id", "prompt", "parameters"}
    if (not isinstance(body, dict) or not required.issubset(body)
            or set(body) - required - IMAGE_RUNTIME_FIELDS or body["operation_id"] not in OPERATIONS):
        raise ValueError("STUDIO_IMAGE_REQUEST_INVALID")
    for key in IMAGE_RUNTIME_FIELDS.intersection(body):
        if key == 'image_layers':
            from .studio_image_composite import layers
            layers(body[key]); continue
        item = body[key]
        if (key == "image_references" and (not isinstance(item, list) or not 1 <= len(item) <= 5)
                or key != "image_references" and not isinstance(item, dict)):
            raise ValueError("STUDIO_IMAGE_RUNTIME_INPUT_INVALID")
    if body['operation_id'] == 'm5.image.composite':
        if body.get('provider_id') is not None or body.get('model_id') is not None or body.get('prompt') != '' or body.get('parameters') != {} or 'image_layers' not in body:
            raise ValueError('STUDIO_IMAGE_COMPOSITE_LOCAL_INPUT_REQUIRED')
        return copy.deepcopy(body)
    if body["operation_id"] == "m5.image.cutout":
        from .studio_image_cutout_webp import parameters_valid
        if body["provider_id"] is not None or body["model_id"] is not None or body["prompt"] != "" or (body["parameters"] != {} and not parameters_valid(body["parameters"])):
            raise ValueError("STUDIO_IMAGE_CUTOUT_LOCAL_ONLY")
        return copy.deepcopy(body)
    _text(body["provider_id"]); _text(body["model_id"])
    if body["operation_id"] == "m5.image.upscale":
        if (body["prompt"] != "" or not isinstance(body["parameters"], dict) or set(body["parameters"]) != {"scale"}
                or "image_source" not in body or set(body) & {"image_references", "mask_source"}
                or type(body["parameters"].get("scale")) is not int or body["parameters"]["scale"] not in (2, 4)):
            raise ValueError("STUDIO_IMAGE_UPSCALE_INPUT_INVALID")
        return copy.deepcopy(body)
    if not isinstance(body["prompt"], str) or not body["prompt"].strip() or len(body["prompt"]) > 16_000:
        raise ValueError("STUDIO_IMAGE_PROMPT_INVALID")
    parameters = body["parameters"]
    if not isinstance(parameters, dict):
        raise ValueError("STUDIO_IMAGE_PARAMETERS_INVALID")
    # Only the explicit new image path admits denoise; the old parameter
    # validator and old body identity remain unchanged for legacy requests.
    legacy_parameters = {key: value for key, value in parameters.items() if key != "denoising_strength"}
    validate_image_parameters(legacy_parameters)
    if "denoising_strength" in parameters:
        value = parameters["denoising_strength"]
        if (type(value) not in (float, int) or not 0 < value <= 1
                or body["operation_id"] not in {"m5.image.i2i", "m5.image.reference", "m5.image.inpaint"}):
            raise ValueError("STUDIO_IMAGE_DENOISE_INVALID")
    if (parameters.get("width") is None) != (parameters.get("height") is None):
        raise ValueError("STUDIO_IMAGE_DIMENSIONS_PAIR_REQUIRED")
    return copy.deepcopy(body)


def _context(value, body, actor):
    fields = {"scope_key", "incarnation", "actor", "request_id", "operation_id", "request_digest",
              "sources", "provider_binding", "rights"}
    if not isinstance(value, dict) or not fields.issubset(value) or set(value) - fields - {"license_note", "command", "execution_recipe", "graph_binding", "batch_binding"}:
        raise ValueError("STUDIO_IMAGE_CONTEXT_INVALID")
    _require_digest(value["scope_key"]); _require_digest(value["request_digest"])
    if 'batch_binding' in value:
        from ..experimental.safe_batch_studio_image import validate_binding
        if value['batch_binding'] is None:
            raise ValueError('BATCH_STUDIO_IMAGE_BINDING_INVALID')
        validate_binding(value['batch_binding'], value)
    if "graph_binding" in value:
        from ..creative.graph_media_binding import validate_graph_binding
        if value["graph_binding"] is None:
            raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
        validate_graph_binding(value["graph_binding"], value)
    if (value["actor"] != actor or value["operation_id"] != body["operation_id"]
            or not isinstance(value["incarnation"], str)
            or not re.fullmatch(r"(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", value["incarnation"])):
        raise ValueError("STUDIO_IMAGE_CONTEXT_OWNER_CHANGED")
    if not isinstance(value["request_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value["request_id"]):
        raise ValueError("STUDIO_IMAGE_REQUEST_ID_INVALID")
    sources = value["sources"]
    if not isinstance(sources, list) or len(sources) > 32:
        raise ValueError("STUDIO_IMAGE_SOURCES_INVALID")
    seen = set()
    for source in sources:
        if (not isinstance(source, dict) or set(source) - {"id", "kind", "version", "digest", "asset_kind", "comic_panel"}
                or not {"id", "kind", "version", "digest"}.issubset(source)):
            raise ValueError("STUDIO_IMAGE_SOURCE_INVALID")
        _text(source["id"]); _require_version(source["version"]); _require_digest(source["digest"])
        if source["kind"] not in {"ASSET", "CREATIVE_DOCUMENT", "COMIC_PANEL"}:
            raise ValueError("STUDIO_IMAGE_SOURCE_KIND_INVALID")
        if source["kind"] == "ASSET":
            if source.get("asset_kind") not in {"image", "video", "audio"}:
                raise ValueError("STUDIO_IMAGE_SOURCE_ASSET_KIND_INVALID")
        elif source.get("asset_kind") is not None:
            raise ValueError("STUDIO_IMAGE_SOURCE_KIND_INVALID")
        if source["kind"] == "COMIC_PANEL" or "comic_panel" in source:
            from ..creative.production_contracts import ProductionSourceSnapshot
            ProductionSourceSnapshot.model_validate(source)
            if (body["operation_id"] != "m5.image.t2i" or len(sources) != 1
                    or any(source["comic_panel"][key] != value[key] for key in ("actor", "scope_key", "incarnation"))):
                raise ValueError("STUDIO_COMIC_SOURCE_CONTEXT_CHANGED")
        identity = (source["kind"], source["id"])
        if identity in seen:
            raise ValueError("STUDIO_IMAGE_SOURCE_DUPLICATE")
        seen.add(identity)
    if any(source["kind"] == "COMIC_PANEL" for source in sources):
        from ..creative.production_execution_models import MediaCommand
        from ..creative.production_execution import digest
        command = MediaCommand.model_validate(value.get("command"))
        if (command.allow_cloud or digest(body["prompt"]) != sources[0]["comic_panel"]["brief_digest"]
                or value.get("graph_binding") is not None):
            raise ValueError("STUDIO_COMIC_SOURCE_CONTEXT_CHANGED")
    images = [source for source in sources if source.get("asset_kind") == "image"]
    if body["operation_id"] == "m5.image.i2i" and not 1 <= len(images) <= 5:
        raise ValueError("STUDIO_IMAGE_REFERENCE_COUNT_INVALID")
    if body["operation_id"] in {"m5.image.cutout", "m5.image.composite"}:
        if (value["provider_binding"] is not None or "graph_binding" in value or len(sources) != 2 or len(images) != 2):
            raise ValueError("STUDIO_IMAGE_CUTOUT_INPUT_REQUIRED")
        if not isinstance(value.get("command"), dict) or value["command"].get("allow_cloud") is not False:
            raise ValueError("STUDIO_IMAGE_CUTOUT_LOCAL_ONLY")
    elif not isinstance(value["provider_binding"], dict) or not value["provider_binding"]:
        raise ValueError("STUDIO_IMAGE_PROVIDER_BINDING_REQUIRED")
    if not isinstance(value["rights"], (dict, str)):
        raise ValueError("STUDIO_IMAGE_RIGHTS_INVALID")
    if "license_note" in value and (not isinstance(value["license_note"], str) or len(value["license_note"]) > 2000):
        raise ValueError("STUDIO_IMAGE_RIGHTS_INVALID")
    if "command" in value:
        command = value["command"]
        if not isinstance(command, dict) or type(command.get("allow_cloud")) is not bool:
            raise ValueError("STUDIO_IMAGE_REVIEWED_COMMAND_INVALID")
        parameters = command.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError("STUDIO_IMAGE_REVIEWED_COMMAND_INVALID")
        command_body = {key: command.get(key) for key in ("operation_id", "provider_id", "model_id", "prompt")}
        command_body["parameters"] = {key: item for key, item in parameters.items() if item is not None}
        for key in IMAGE_RUNTIME_FIELDS:
            if key in body:
                command_body[key] = copy.deepcopy(command.get(key))
        if command_body != body or command.get("request_id") != value["request_id"]:
            raise ValueError("STUDIO_IMAGE_REVIEWED_COMMAND_CHANGED")
        references = command.get("source_snapshots")
        if not isinstance(references, list) or any(not isinstance(source, dict) for source in references):
            raise ValueError("STUDIO_IMAGE_REVIEWED_COMMAND_INVALID")
        references = [{key: item for key, item in source.items() if key != "reference_only" and item is not None}
                      for source in references]
        if references != sources:
            raise ValueError("STUDIO_IMAGE_REVIEWED_SOURCE_CHANGED")
        if (IMAGE_RUNTIME_FIELDS.intersection(body) or IMAGE_RUNTIME_FIELDS.intersection(command)
                or body["operation_id"] in {"m5.image.reference", "m5.image.inpaint", "m5.image.upscale"}
                or "denoising_strength" in body["parameters"]):
            from ..creative.production_execution_models import MediaCommand
            checked = MediaCommand.model_validate(command)
            checked_body = checked.model_dump(exclude={"source_snapshots", "allow_cloud", "license_note", "request_id", "canvas_return"})
            checked_body["parameters"] = checked.parameters.model_dump(exclude_none=True)
            if checked.operation_id not in OPERATIONS or checked_body != body:
                raise ValueError("STUDIO_IMAGE_RUNTIME_CONTEXT_INVALID")
            if checked.canvas_return is not None and (checked.canvas_return.incarnation != value['incarnation']
                    or value.get('graph_binding') is not None or value.get('batch_binding') is not None):
                raise ValueError('STUDIO_CANVAS_RETURN_CONTEXT_CHANGED')
    elif (IMAGE_RUNTIME_FIELDS.intersection(body) or body["operation_id"] in {"m5.image.reference", "m5.image.inpaint", "m5.image.upscale"}
            or "denoising_strength" in body["parameters"]):
        raise ValueError("STUDIO_IMAGE_RUNTIME_CONTEXT_REQUIRED")
    if body["operation_id"] == "m5.image.cutout":
        from .studio_image_cutout_webp import PARAMETER, validate_context
        if PARAMETER in body["parameters"] or any(isinstance(captured, dict) and isinstance(captured.get("parameters"), dict) and PARAMETER in captured["parameters"]
                for captured in (value.get("command"), value.get("execution_recipe"))):
            validate_context(body, value)
    if body['operation_id'] == 'm5.image.composite':
        from .studio_image_composite import validate_context
        validate_context(body, value)
    _no_secrets(value)
    if len(_canonical(value).encode("utf-8")) > 128 * 1024:
        raise ValueError("STUDIO_IMAGE_CONTEXT_LIMIT")
    return copy.deepcopy(value)


def _cutout_proof(row):
    proof = row.get("processing_proof")
    ready = row.get("publication_ready")
    if proof is None:
        if ready is not None or row.get("output_asset_id"):
            raise ValueError("STUDIO_IMAGE_CUTOUT_PROOF_REQUIRED")
        return
    from .studio_image_cutout_webp import parameters_valid, validate_proof
    if parameters_valid(row["body"]["parameters"]):
        return validate_proof(row)
    from .studio_image_cutout import CONTRACT as CUTOUT_CONTRACT, MAX_OUTPUT_BYTES
    from .studio_image_mask_authoring import dimensions
    fields = {"contract", "width", "height", "source_sha256", "mask_sha256", "output_sha256",
        "output_bytes", "keep_pixels", "remove_pixels"}
    if not isinstance(proof, dict) or set(proof) != fields or proof["contract"] != CUTOUT_CONTRACT:
        raise ValueError("STUDIO_IMAGE_CUTOUT_PROOF_INVALID")
    dimensions(proof["width"], proof["height"])
    for key in ("source_sha256", "mask_sha256", "output_sha256"): _require_digest(proof[key])
    if (any(type(proof[key]) is not int or proof[key] <= 0 for key in ("keep_pixels", "remove_pixels", "output_bytes"))
            or proof["keep_pixels"] + proof["remove_pixels"] != proof["width"] * proof["height"]
            or proof["output_bytes"] > MAX_OUTPUT_BYTES
            or proof["output_bytes"] != ((proof["width"] * 4 + 1) * proof["height"]
                + 5 * (((proof["width"] * 4 + 1) * proof["height"] + 65534) // 65535) + 63)
            or [proof["source_sha256"], proof["mask_sha256"]] != [source["digest"] for source in row["context"]["sources"]]
            or ready != {"kind": "image", "output_digest": proof["output_sha256"], "output_bytes": proof["output_bytes"], "media_type": "image/png"}
            or (row.get("output_digest") is not None and row["output_digest"] != proof["output_sha256"])):
        raise ValueError("STUDIO_IMAGE_CUTOUT_PROOF_INVALID")


def _binding(row):
    return _digest({key: row[key] for key in ("id", "novel_id", "branch_id", "owner_actor_id", "body", "context", "request_digest")})


def _upscale_proof(row):
    proof, ready = row.get("processing_proof"), row.get("publication_ready")
    if proof is None:
        if ready is not None or row.get("output_asset_id"):
            raise ValueError("STUDIO_IMAGE_UPSCALE_PROOF_REQUIRED")
        return
    from .studio_image_provider_recipes import upscale_dimensions
    fields = {"contract", "source_sha256", "source_width", "source_height", "scale",
        "output_width", "output_height", "output_sha256", "output_bytes"}
    if not isinstance(proof, dict) or set(proof) != fields or proof["contract"] != "studio-image-upscale-proof/1":
        raise ValueError("STUDIO_IMAGE_UPSCALE_PROOF_INVALID")
    source = {"width": proof["source_width"], "height": proof["source_height"]}
    target = upscale_dimensions(source, proof["scale"])
    _require_digest(proof["source_sha256"]); _require_digest(proof["output_sha256"])
    recipe = row["context"].get("execution_recipe", {})
    if (type(proof["output_width"]) is not int or type(proof["output_height"]) is not int
            or target != {"width": proof["output_width"], "height": proof["output_height"]}
            or recipe.get("source_dimensions") != source or recipe.get("target_dimensions") != target
            or proof["scale"] != row["body"]["parameters"]["scale"]
            or len(row["context"]["sources"]) != 1 or row["context"]["sources"][0]["digest"] != proof["source_sha256"]
            or type(proof["output_bytes"]) is not int or not 0 < proof["output_bytes"] <= MAX_BYTES
            or ready != {"kind": "image", "output_digest": proof["output_sha256"], "output_bytes": proof["output_bytes"], "media_type": "image/png"}
            or row.get("output_digest") is not None and row["output_digest"] != proof["output_sha256"]):
        raise ValueError("STUDIO_IMAGE_UPSCALE_PROOF_INVALID")


def _owned(service, row, nid, branch, actor):
    if (row.get("contract") != CONTRACT or service.owner_actor_id != actor or not actor
            or row.get("owner_actor_id") != actor or row.get("novel_id") != nid or row.get("branch_id") != branch):
        raise FileNotFoundError(row.get("id", "studio image"))
    _require_version(row.get("version")); _require_digest(row.get("request_digest"))
    body = _payload(row.get("body"))
    context = _context(row.get("context"), body, actor)
    origin = context.get('command', {}).get('canvas_return')
    if origin is not None and (origin.get('project_id') != nid or origin.get('scope', {}).get('branch_id') != branch):
        raise ValueError('STUDIO_CANVAS_RETURN_CONTEXT_CHANGED')
    if row["request_digest"] != context["request_digest"]:
        raise ValueError("STUDIO_IMAGE_REQUEST_BINDING_CHANGED")
    if body["operation_id"] == "m5.image.cutout": _cutout_proof(row)
    if body['operation_id'] == 'm5.image.composite':
        from .studio_image_composite import validate_proof
        validate_proof(row)
    if body["operation_id"] == "m5.image.upscale": _upscale_proof(row)
    if row.get("status") not in STATES or row.get("binding_digest") != _binding(row):
        raise ValueError("STUDIO_IMAGE_JOB_BINDING_CHANGED")
    return row


def _snapshot(service, nid, branch, actor, job_id):
    """Whole atomic row read for a callback already holding an asset lease.

    Callers own the per-job execution lease. Avoid taking the legacy queue
    mutex inside an asset lease; owner writes still finish under exact CAS.
    """
    return copy.deepcopy(_owned(service, service._find(service._load(nid, branch), job_id), nid, branch, actor))


def _read(service, nid, branch, actor, job_id):
    with service._lock, workspace_mutation(service.root, "image-jobs"):
        return _snapshot(service, nid, branch, actor, job_id)


def _cas(row, version, request_digest):
    _require_version(version); _require_digest(request_digest)
    if row["version"] != version or row["request_digest"] != request_digest:
        raise ValueError("STUDIO_IMAGE_JOB_VERSION_CONFLICT")


def _advance(row, **fields):
    if row["version"] >= MAX_VERSION:
        raise ValueError("STUDIO_IMAGE_VERSION_LIMIT")
    row.update(fields, version=row["version"] + 1, updated_at=now())
    return row


@contextmanager
def _execution_lease(service, job_id):
    if not isinstance(job_id, str) or not IDENTITY.fullmatch(job_id):
        raise ValueError("STUDIO_IMAGE_JOB_ID_INVALID")
    # Original cross-process coordinator; no secondary queue or restart resend.
    with workspace_mutation(service.root, "studio-image-execution:" + job_id):
        yield


def create(service, nid, branch, actor, body, context, guard, *, source_phase=None):
    if not callable(guard) or service.owner_actor_id != actor or not actor:
        raise ValueError("STUDIO_IMAGE_AUTHORITY_REQUIRED")
    body = _payload(body); context = _context(context, body, actor)
    guard()
    def add(rows):
        if 'canvas_image_node' in context.get('command', {}):
            matches = [row for row in rows if row.get('contract') == CONTRACT
                and row.get('context', {}).get('scope_key') == context['scope_key']
                and row.get('context', {}).get('incarnation') == context['incarnation']
                and row.get('context', {}).get('request_id') == context['request_id']]
            if len(matches) > 1:
                from ..experimental.common import StaleSourceError
                raise StaleSourceError('STUDIO_IMAGE_CREATE_AMBIGUOUS')
        for row in rows:
            if (row.get("contract") == CONTRACT and row.get("context", {}).get("scope_key") == context["scope_key"]
                    and row.get("context", {}).get("incarnation") == context["incarnation"]
                    and row.get("context", {}).get("request_id") == context["request_id"]):
                _owned(service, row, nid, branch, actor)
                if row["body"] != body or row["context"] != context:
                    raise ValueError("STUDIO_IMAGE_IDEMPOTENCY_CONFLICT")
                return copy.deepcopy(row)
        if sum(row.get("contract") == CONTRACT for row in rows) >= 200:
            raise ValueError("STUDIO_IMAGE_JOB_CAPACITY")
        from uuid import uuid4
        row = {"contract": CONTRACT, "id": str(uuid4()), "novel_id": nid, "branch_id": branch,
            "owner_actor_id": actor, "body": body, "context": context, "version": 1,
            "request_digest": context["request_digest"], "status": "QUEUED", "attempt": 0,
            "receipt_digest": None, "output_asset_id": None, "output_asset_version": None,
            "output_digest": None, "candidate_asset_version": None, "error_code": None,
            "product_acceptance": "LOCAL_REQUIRED", "created_at": now(), "updated_at": now()}
        row["binding_digest"] = _binding(row)
        rows.append(row)
        return copy.deepcopy(row)
    if (body["operation_id"] in {"m5.image.cutout", "m5.image.inpaint", "m5.image.upscale", "m5.image.composite"}
            or any(source["kind"] == "COMIC_PANEL" for source in context["sources"])):
        if not callable(source_phase):
            raise ValueError("STUDIO_IMAGE_UPSCALE_SOURCE_PHASE_REQUIRED" if body["operation_id"] == "m5.image.upscale"
                else "STUDIO_IMAGE_CUTOUT_SOURCE_PHASE_REQUIRED")
        # Original queue -> source -> asset -> project order; hold the input
        # lease through atomic queue persistence, including idempotent retries.
        with service._lock, workspace_mutation(service.root, "image-jobs"), source_phase():
            guard()
            def checked_add(rows):
                result = add(rows)
                guard()
                return result
            value = service._mutate(nid, branch, checked_add)
            guard()
    else:
        value = service._mutate(nid, branch, add)
    guard()
    return value


def get(service, nid, branch, actor, job_id, guard):
    guard()
    row = _read(service, nid, branch, actor, job_id)
    guard()
    return row


def list_jobs(service, nid, branch, actor, context, guard):
    """Server-only current-incarnation list; callers project public receipt fields."""
    if (not isinstance(context, dict) or set(context) != {"actor", "scope_key", "incarnation"}
            or context.get("actor") != actor or service.owner_actor_id != actor):
        raise ValueError("STUDIO_IMAGE_LIST_CONTEXT_INVALID")
    guard()
    with service._lock, workspace_mutation(service.root, "image-jobs"):
        rows = []
        for row in reversed(service._load(nid, branch)):
            captured = row.get("context", {})
            if (row.get("contract") != CONTRACT or not isinstance(captured, dict)
                    or any(captured.get(key) != context[key] for key in context)):
                continue
            rows.append(copy.deepcopy(_owned(service, row, nid, branch, actor)))
    guard()
    return rows


def resolve_create(service, nid, branch, actor, context, request_id, guard):
    """One bounded original-owner snapshot, with no queue mutation or replay.

    Absence is an observation, not evidence that an in-flight create rolled
    back. Do not substitute list ordering, another actor or another incarnation.
    """
    if (not callable(guard) or not isinstance(context, dict)
            or set(context) != {'actor', 'scope_key', 'incarnation'}
            or context.get('actor') != actor or service.owner_actor_id != actor or not actor):
        raise ValueError('STUDIO_IMAGE_RESOLVE_CONTEXT_INVALID')
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', request_id):
        raise ValueError('STUDIO_IMAGE_REQUEST_ID_INVALID')
    guard()
    path = service._path(nid, branch)
    if not path.exists():
        guard()
        raise FileNotFoundError(request_id)
    # New observation budget only; existing queue reads and writes keep their
    # previous contract. Normal formal storage is already capped at 200 jobs.
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('STUDIO_IMAGE_RESOLVE_CAPACITY')
    with service._lock, workspace_mutation(service.root, 'image-jobs'):
        guard()
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('STUDIO_IMAGE_RESOLVE_CAPACITY')
        stored = service._load(nid, branch)
        if not isinstance(stored, list):
            raise ValueError('STUDIO_IMAGE_RESOLVE_INVALID')
        formal = [row for row in stored if isinstance(row, dict) and row.get('contract') == CONTRACT]
        if len(formal) > 200:
            raise ValueError('STUDIO_IMAGE_RESOLVE_CAPACITY')
        matches = []
        for row in formal:
            captured = row.get('context')
            if (row.get('owner_actor_id') != actor or row.get('novel_id') != nid or row.get('branch_id') != branch
                    or not isinstance(captured, dict)
                    or any(captured.get(key) != context[key] for key in context)
                    or captured.get('request_id') != request_id):
                continue
            matches.append(row)
        if not matches:
            guard()
            raise FileNotFoundError(request_id)
        if len(matches) != 1:
            raise ValueError('STUDIO_IMAGE_CREATE_AMBIGUOUS')
        result = copy.deepcopy(_owned(service, matches[0], nid, branch, actor))
        if (not isinstance(result.get('id'), str) or not IDENTITY.fullmatch(result['id'])
                or type(result.get('attempt')) is not int or not 0 <= result['attempt'] <= MAX_VERSION
                or result.get('product_acceptance') != 'LOCAL_REQUIRED'):
            raise ValueError('STUDIO_IMAGE_RESOLVE_INVALID')
        _text(result.get('created_at')); _text(result.get('updated_at'))
        same_ids = [row for row in formal if row.get('id') == result['id']
            and row.get('owner_actor_id') == actor and row.get('novel_id') == nid and row.get('branch_id') == branch
            and isinstance(row.get('context'), dict)
            and all(row['context'].get(key) == context[key] for key in context)]
        if len(same_ids) != 1:
            raise ValueError('STUDIO_IMAGE_CREATE_AMBIGUOUS')
        guard()
    guard()
    return result


def cancel(service, nid, branch, actor, job_id, *, expected_version, expected_request_digest, guard):
    """Cancel only local ownership; preserve all source/candidate evidence.

    Only the bounded checkpointed CPU operation can cancel RUNNING here.
    Provider RUNNING jobs may already own remote work and remain unchanged.
    UNKNOWN cancellation discards local adoption, not remote execution.
    """
    if not callable(guard):
        raise ValueError("STUDIO_IMAGE_AUTHORITY_REQUIRED")
    guard()
    def change(rows):
        row = _owned(service, service._find(rows, job_id), nid, branch, actor)
        _cas(row, expected_version, expected_request_digest)
        if row["status"] == "CANCELLED":
            return copy.deepcopy(row)
        cpu = row["body"]["operation_id"] in {"m5.image.cutout", "m5.image.composite"}
        if row["status"] not in ({"QUEUED", "RUNNING", "AWAITING_REVIEW", "UNKNOWN"} if cpu else {"QUEUED", "AWAITING_REVIEW", "UNKNOWN"}):
            raise ValueError("STUDIO_IMAGE_NOT_CANCELLABLE")
        return copy.deepcopy(_advance(row, status="CANCELLED", local_result_discarded=True,
            cancellation_mode="COOPERATIVE_LOCAL_CANCEL" if cpu else "LOCAL_RESULT_DISCARD",
            remote_cancel_confirmed=False, cancelled_at=now(), error_code=None))
    value = service._mutate(nid, branch, change)
    guard()
    return value


def reconcile(service, nid, branch, actor, job_id, *, expected_version, expected_request_digest, guard, recover_candidate=None, recover_review=None):
    """Explicit interruption receipt after the original executor lease ends.

    This never contacts a provider or returns a job to QUEUED.
    """
    with _execution_lease(service, job_id):
        guard()
        captured = _read(service, nid, branch, actor, job_id)
        _cas(captured, expected_version, expected_request_digest)
        if captured["status"] == "REVIEWING":
            value = _reconcile_review(service, nid, branch, actor, job_id, captured, recover_review)
            guard()
            return value
        cancelled_cpu = (captured["status"] == "CANCELLED" and captured["body"]["operation_id"] in {"m5.image.cutout", "m5.image.composite"}
            and isinstance(captured.get("publication_ready"), dict) and not captured.get("output_asset_id"))
        if captured["status"] not in {"RUNNING", "UNKNOWN"} and not cancelled_cpu:
            raise ValueError("STUDIO_IMAGE_NOT_RECONCILABLE")
        candidate = None
        ready = captured.get("publication_ready")
        if callable(recover_candidate) and isinstance(ready, dict):
            try:
                _require_digest(ready.get("output_digest"))
                if (set(ready) != {"kind", "output_digest", "output_bytes", "media_type"} or ready["kind"] != "image"
                        or type(ready["output_bytes"]) is not int or not 0 < ready["output_bytes"] <= MAX_BYTES
                        or not isinstance(ready["media_type"], str)):
                    raise ValueError("STUDIO_IMAGE_PUBLICATION_READY_INVALID")
                asset = recover_candidate(copy.deepcopy(captured))
                if asset is not None:
                    candidate = _candidate_identity(asset, captured, ready["output_digest"], ready["output_bytes"], ready["media_type"])
                guard()
            except Exception:
                # A stale/ambiguous source or missing candidate never causes
                # re-admission, generation, publication or adoption.
                guard()
                candidate = None
        def change(rows):
            row = _owned(service, service._find(rows, job_id), nid, branch, actor)
            _cas(row, expected_version, expected_request_digest)
            if (row["status"] != captured["status"] or row.get("execution_token") != captured.get("execution_token")
                    or row.get("publication_ready") != ready or row["context"] != captured["context"]):
                raise ValueError("STUDIO_IMAGE_RECONCILE_RECEIPT_CHANGED")
            if candidate is not None:
                _advance(row, status="CANCELLED" if cancelled_cpu else "AWAITING_REVIEW", execution_token=None, output_asset_id=candidate["id"],
                    output_asset_version=candidate["version"], candidate_asset_version=candidate["version"],
                    output_digest=candidate["sha256"], review_state="VERIFIED_PRIVATE_CANDIDATE", error_code=None)
                row["receipt_digest"] = _digest(_receipt(row))
                return copy.deepcopy(row)
            if cancelled_cpu: return copy.deepcopy(row)
            return copy.deepcopy(_advance(row, status="UNKNOWN", execution_token=None,
                error_code="STUDIO_IMAGE_INTERRUPTED_DISPATCH"))
        value = service._mutate(nid, branch, change)
        guard()
        return value


def _reconcile_review(service, nid, branch, actor, job_id, captured, recover_review):
    """Only release a stopped review proven to own its original private bytes.

    The caller holds the original execution lease and has already checked Host,
    actor, version and request. No current source authority is needed for this
    internal reservation bookkeeping; no provider or promotion is invoked.
    """
    if not callable(recover_review):
        return captured
    recovered = None
    try:
        _text(captured.get("output_asset_id")); _require_version(captured.get("candidate_asset_version"))
        _require_digest(captured.get("output_digest")); _require_digest(captured.get("receipt_digest"))
        _text(captured.get("review_token")); _require_version(captured.get("review_from_version"))
        if (captured["receipt_digest"] != _digest(_receipt(captured))
                or captured.get("output_asset_version") != captured["candidate_asset_version"]
                or captured["review_from_version"] >= captured["version"]):
            raise ValueError("STUDIO_IMAGE_RECONCILE_REVIEW_RECEIPT_CHANGED")
        candidate = {"id": captured["output_asset_id"], "version": captured["candidate_asset_version"],
            "digest": captured["output_digest"], "kind": "image"}
        def compensate():
            nonlocal recovered
            def change(rows):
                row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                _cas(row, captured["version"], captured["request_digest"])
                fields = ("context", "review_token", "review_from_version", "execution_token", "receipt_digest",
                    "output_asset_id", "candidate_asset_version", "output_asset_version", "output_digest")
                if (row["status"] != "REVIEWING" or any(row.get(key) != captured.get(key) for key in fields)
                        or row["receipt_digest"] != _digest(_receipt(row))):
                    raise ValueError("STUDIO_IMAGE_RECONCILE_REVIEW_RECEIPT_CHANGED")
                return copy.deepcopy(_advance(row, status="AWAITING_REVIEW", review_token=None, review_from_version=None,
                    review_state="VERIFIED_PRIVATE_CANDIDATE", error_code="STUDIO_IMAGE_REVIEW_RECOVERED_NOT_PROMOTED",
                    recovery_state="EXACT_PRIVATE_REVIEW_RELEASED_NO_REPLAY", review_reconciled_at=now()))
            recovered = service._mutate(nid, branch, change)
            return recovered
        # Retain V1's queue -> asset order. The callback holds the original
        # source/asset leases while invoking this reentrant exact CAS write.
        with service._lock, workspace_mutation(service.root, "image-jobs"):
            recover_review(candidate, compensate)
    except Exception:
        # Already promoted, deleted, changed or unprovable reviews remain as
        # recorded. A successful exact bookkeeping write is never undone.
        pass
    return recovered if recovered is not None else captured


def _decode(uri, provider):
    if not isinstance(uri, str) or not uri:
        raise ValueError("STUDIO_IMAGE_OUTPUT_INVALID")
    if uri.startswith("data:image/"):
        if len(uri) > 4 * ((MAX_BYTES + 2) // 3) + 100:
            raise ValueError("STUDIO_IMAGE_OUTPUT_LIMIT")
        match = re.fullmatch(r"data:image/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)", uri)
        if not match:
            raise ValueError("STUDIO_IMAGE_OUTPUT_INVALID")
        data = base64.b64decode(match[1], validate=True)
    else:
        if len(uri) > 4096:
            raise ValueError("STUDIO_IMAGE_OUTPUT_LIMIT")
        data = fetch_media_bytes(uri, MAX_BYTES, configured_provider_endpoint=getattr(provider, "endpoint", None))
    if not data or len(data) > MAX_BYTES:
        raise ValueError("STUDIO_IMAGE_OUTPUT_LIMIT")
    return data, inspect_image(data)


def _runtime_images(job, values):
    """Bind actual bounded pixels to the reviewed original Asset snapshots."""
    from ..creative.production_execution_models import MediaCommand
    command = MediaCommand.model_validate(job["context"]["command"])
    references = [source for source in job["context"]["sources"] if source["kind"] == "ASSET"]
    if (not isinstance(values, list) or len(values) != len(references)
            or not 1 <= len(values) <= 5):
        raise ValueError("STUDIO_IMAGE_REFERENCES_CHANGED")
    images, total = [], 0
    for data, reference in zip(values, references):
        if not isinstance(data, bytes) or not data:
            raise ValueError("STUDIO_IMAGE_REFERENCE_INVALID")
        total += len(data)
        if total > MAX_BYTES:
            raise ValueError("STUDIO_IMAGE_REFERENCES_LIMIT")
        if hashlib.sha256(data).hexdigest() != reference["digest"]:
            raise ValueError("STUDIO_IMAGE_REFERENCE_DIGEST_CHANGED")
        measured = inspect_image(data)
        images.append("data:" + measured["media_type"] + ";base64," + base64.b64encode(data).decode("ascii"))
    weights = [reference.weight for reference in command.image_references or []]
    if command.image_source is not None:
        weights.insert(0, 1.0)
    mask = images.pop() if command.mask_source is not None else None
    if len(images) != len(weights):
        raise ValueError("STUDIO_IMAGE_RUNTIME_SNAPSHOT_MISMATCH")
    return images, weights, mask


def _candidate(asset, job, data, measured):
    return _candidate_identity(asset, job, hashlib.sha256(data).hexdigest(), len(data), measured["media_type"])


def _candidate_identity(asset, job, output_digest, output_bytes, media_type):
    expected = {"novel_id": job["novel_id"], "branch_id": job["branch_id"], "kind": "image",
        "sha256": output_digest, "size": output_bytes, "media_type": media_type,
        "source_job_id": job["id"], "provider_id": job["body"]["provider_id"], "model_id": job["body"]["model_id"]}
    expected_binding = {"novel_id": job["novel_id"], "branch_id": job["branch_id"],
        "incarnation": job["context"]["incarnation"], "scope_key": job["context"]["scope_key"]}
    expected_origin = {"contract": "studio-production-result/1", "job_id": job["id"],
        **{key: job["context"][key] for key in ("scope_key", "incarnation", "actor", "request_digest", "operation_id", "sources")},
        "provider_id": job["body"]["provider_id"], "model_id": job["body"]["model_id"],
        "license_note": job["context"].get("license_note", "")}
    if "graph_binding" in job["context"]:
        from ..creative.graph_media_binding import validate_graph_binding
        binding = validate_graph_binding(job["context"]["graph_binding"], job["context"])
        if binding is None:
            raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
        expected_origin["graph_binding"] = copy.deepcopy(binding)
    if 'batch_binding' in job['context']:
        from ..experimental.safe_batch_studio_image import validate_binding
        binding = validate_binding(job['context']['batch_binding'], job['context'])
        if binding is None:
            raise ValueError('BATCH_STUDIO_IMAGE_BINDING_INVALID')
        expected_origin['batch_binding'] = binding
    if (not isinstance(asset, dict) or any(asset.get(key) != value for key, value in expected.items())
            or asset.get("_owner_actor_id") != job["owner_actor_id"] or asset.get("deleted_at")
            or asset.get("_project_binding") != expected_binding
            or asset.get("_studio_result_origin") != expected_origin
            or "narrative_production_v2" not in asset.get("_required_features", [])):
        raise ValueError("STUDIO_IMAGE_PRIVATE_CANDIDATE_INVALID")
    _text(asset.get("id")); _require_version(asset.get("version"))
    return asset


def _receipt(job):
    return {"contract": CONTRACT, "job_id": job["id"], "request_digest": job["request_digest"],
        "binding_digest": job["binding_digest"], "attempt": job["attempt"],
        "provider_id": job["body"]["provider_id"], "model_id": job["body"]["model_id"],
        "source_snapshots": copy.deepcopy(job["context"]["sources"]),
        "candidate_asset_id": job["output_asset_id"], "candidate_asset_version": job["candidate_asset_version"],
        "output_digest": job["output_digest"], "product_acceptance": "LOCAL_REQUIRED",
        **({"processing_proof": copy.deepcopy(job.get("processing_proof"))}
           if job["body"]["operation_id"] in {"m5.image.cutout", "m5.image.upscale", "m5.image.composite"} else {})}


def execute(service, nid, branch, actor, job_id, registry, *, expected_version, expected_request_digest,
            guard, source_guard, dispatch_guard, read_images, publish):
    if not all(callable(value) for value in (guard, source_guard, dispatch_guard, read_images, publish)):
        raise ValueError("STUDIO_IMAGE_EXECUTION_GUARDS_REQUIRED")
    with _execution_lease(service, job_id):
        guard(); source_guard()
        def claim(rows):
            row = _owned(service, service._find(rows, job_id), nid, branch, actor)
            _cas(row, expected_version, expected_request_digest)
            if row["status"] == "RUNNING":
                return copy.deepcopy(_advance(row, status="UNKNOWN", error_code="STUDIO_IMAGE_INTERRUPTED_DISPATCH"))
            if row["status"] != "QUEUED":
                raise ValueError("STUDIO_IMAGE_NOT_QUEUED")
            from uuid import uuid4
            _advance(row, status="RUNNING", execution_token=str(uuid4()), attempt=row["attempt"] + 1,
                dispatch_started=False, error_code=None)
            return copy.deepcopy(row)
        job = service._mutate(nid, branch, claim)
        if job["status"] == "UNKNOWN":
            guard()
            return job
        sent = invoked = False
        candidate = None
        def current(*, under_asset_lease=False):
            actual = (_snapshot if under_asset_lease else _read)(service, nid, branch, actor, job_id)
            if (actual["status"] != "RUNNING" or actual["version"] != job["version"]
                    or actual.get("execution_token") != job["execution_token"] or actual["binding_digest"] != job["binding_digest"]):
                raise ValueError("STUDIO_IMAGE_ATTEMPT_CHANGED")
        def last_mile():
            nonlocal sent, job
            guard(); source_guard()
            if registry.get(job["body"]["provider_id"]) is not provider:
                raise ValueError("STUDIO_IMAGE_PROVIDER_CHANGED")
            dispatch_guard(job, provider)
            current()
            if not sent:
                def intent(rows):
                    row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                    _cas(row, job["version"], job["request_digest"])
                    if row["status"] != "RUNNING" or row.get("execution_token") != job["execution_token"]:
                        raise ValueError("STUDIO_IMAGE_ATTEMPT_CHANGED")
                    return copy.deepcopy(_advance(row, dispatch_started=True, dispatch_intent_at=now()))
                job = service._mutate(nid, branch, intent)
                sent = True
        try:
            cpu = job["body"]["operation_id"] in {"m5.image.cutout", "m5.image.composite"}
            proof = None
            if cpu:
                from .studio_image_cutout import render_cutout
                guard(); source_guard(); dispatch_guard(); current()
                values = read_images()
                if (not isinstance(values, list) or len(values) != 2
                        or any(not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != source["digest"]
                               for data, source in zip(values, job["context"]["sources"]))):
                    raise ValueError("STUDIO_IMAGE_CUTOUT_SOURCE_CHANGED")
                checkpoints = 0
                def checkpoint():
                    nonlocal checkpoints
                    checkpoints += 1
                    # Each call covers at most one bounded scanline/chunk. Poll
                    # cancellation frequently without re-reading source pixels.
                    if checkpoints % 16 == 0:
                        guard(); current()
                checkpoint(); guard(); current()
                if job['body']['operation_id'] == 'm5.image.composite':
                    from .studio_image_composite import render
                    data, proof = render(values, job['body']['image_layers'], checkpoint)
                else:
                    data, proof = render_cutout(*values, checkpoint=checkpoint)
                from .studio_image_cutout_webp import parameters_valid, encode
                webp = parameters_valid(job["body"]["parameters"])
                if webp:
                    data, proof = encode(data, proof, checkpoint)
                measured = {"kind": "image", "media_type": "image/webp" if webp else "image/png", "extension": "webp" if webp else "png",
                    "width": proof["width"], "height": proof["height"], "byte_count": len(data)}
                guard(); source_guard(); dispatch_guard(); current()
            else:
                provider = registry.get(job["body"]["provider_id"])
                if getattr(provider, "supports_dispatch_guard", False) is not True:
                    raise ValueError("STUDIO_IMAGE_PROVIDER_GUARD_UNSUPPORTED")
                guard(); source_guard(); dispatch_guard(job, provider); current()
                images = []
                advanced = (bool(IMAGE_RUNTIME_FIELDS.intersection(job["body"]))
                    or job["body"]["operation_id"] in {"m5.image.reference", "m5.image.inpaint"}
                    or "denoising_strength" in job["body"]["parameters"])
                if advanced:
                    images, weights, mask_image = _runtime_images(job, read_images())
                    if not callable(getattr(provider, "generate_image", None)):
                        raise ValueError("STUDIO_IMAGE_RUNTIME_PROVIDER_UNSUPPORTED")
                elif job["body"]["operation_id"] == "m5.image.i2i":
                    values = read_images()
                    expected_count = sum(source.get("asset_kind") == "image" for source in job["context"]["sources"])
                    if not isinstance(values, list) or len(values) != expected_count or not 1 <= len(values) <= 5:
                        raise ValueError("STUDIO_IMAGE_REFERENCES_CHANGED")
                    total = 0
                    references = [source for source in job["context"]["sources"] if source.get("asset_kind") == "image"]
                    for data, reference in zip(values, references):
                        if not isinstance(data, bytes) or not data:
                            raise ValueError("STUDIO_IMAGE_REFERENCE_INVALID")
                        total += len(data)
                        if total > MAX_BYTES:
                            raise ValueError("STUDIO_IMAGE_REFERENCES_LIMIT")
                        if hashlib.sha256(data).hexdigest() != reference["digest"]:
                            raise ValueError("STUDIO_IMAGE_REFERENCE_DIGEST_CHANGED")
                        measured = inspect_image(data)
                        images.append("data:" + measured["media_type"] + ";base64," + base64.b64encode(data).decode("ascii"))
                    if not callable(getattr(provider, "edit", None)):
                        raise ValueError("STUDIO_IMAGE_EDIT_UNSUPPORTED")
                request = AssetGenerationRequest(job["body"]["provider_id"], job["body"]["model_id"],
                    job["body"]["prompt"], job["id"], copy.deepcopy(job["body"]["parameters"]), dispatch_guard=last_mile)
                invoked = True
                result = (provider.generate_image(request, operation=job["body"]["operation_id"].rsplit(".", 1)[-1],
                    images=images, reference_weights=weights, mask=mask_image) if advanced else
                    provider.edit(request, images) if images else provider.generate(request))
                if not sent:
                    raise ValueError("STUDIO_IMAGE_GUARDED_DISPATCH_NOT_OBSERVED")
                if result.provider_id != request.provider_id or result.model_id != request.model_id:
                    raise ValueError("STUDIO_IMAGE_PROVIDER_RESULT_CHANGED")
                guard(); source_guard(); dispatch_guard(job, provider); current()
                if registry.get(job["body"]["provider_id"]) is not provider:
                    raise ValueError("STUDIO_IMAGE_PROVIDER_CHANGED")
                data, measured = _decode(result.asset_uri, provider)
                if job["body"]["operation_id"] == "m5.image.upscale":
                    recipe = job["context"]["execution_recipe"]
                    source = recipe["source_dimensions"]
                    target = recipe["target_dimensions"]
                    if (measured["media_type"] != "image/png"
                            or {key: measured.get(key) for key in ("width", "height")} != target):
                        raise ValueError("STUDIO_IMAGE_UPSCALE_OUTPUT_CHANGED")
                    proof = {"contract": "studio-image-upscale-proof/1",
                        "source_sha256": job["context"]["sources"][0]["digest"],
                        "source_width": source["width"], "source_height": source["height"],
                        "scale": job["body"]["parameters"]["scale"],
                        "output_width": target["width"], "output_height": target["height"],
                        "output_sha256": hashlib.sha256(data).hexdigest(), "output_bytes": len(data)}
                guard(); source_guard(); dispatch_guard(job, provider); current()
            def publication_ready(rows):
                row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                _cas(row, job["version"], job["request_digest"])
                if row["status"] != "RUNNING" or row.get("execution_token") != job["execution_token"]:
                    raise ValueError("STUDIO_IMAGE_ATTEMPT_CHANGED")
                fields = {"publication_ready": {"kind": "image", "output_digest": hashlib.sha256(data).hexdigest(),
                    "output_bytes": len(data), "media_type": measured["media_type"]}, **({"processing_proof": proof} if proof is not None else {})}
                if cpu:
                    if job['body']['operation_id'] == 'm5.image.composite':
                        from .studio_image_composite import validate_proof
                        validate_proof({**row, **fields})
                    else:
                        _cutout_proof({**row, **fields})
                if row["body"]["operation_id"] == "m5.image.upscale": _upscale_proof({**row, **fields})
                return copy.deepcopy(_advance(row, **fields))
            job = service._mutate(nid, branch, publication_ready)
            # No image-job mutex is held while entering source -> asset -> project.
            if cpu: invoked = True
            candidate = _candidate(publish(data, "image", "studio-image-" + job_id + "." + measured["extension"], measured, job_id,
                lambda: current(under_asset_lease=True)), job, data, measured)
            guard(); source_guard(); current()
            def finish(rows):
                row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                _cas(row, job["version"], job["request_digest"])
                if row["status"] != "RUNNING" or row.get("execution_token") != job["execution_token"]:
                    raise ValueError("STUDIO_IMAGE_ATTEMPT_CHANGED")
                _advance(row, status="AWAITING_REVIEW", output_asset_id=candidate["id"], output_asset_version=candidate["version"],
                    candidate_asset_version=candidate["version"], output_digest=candidate["sha256"], error_code=None)
                row["receipt_digest"] = _digest(_receipt(row))
                return copy.deepcopy(row)
            return service._mutate(nid, branch, finish)
        except Exception as exc:
            code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"(?:STUDIO_IMAGE_|IMAGE_MASK_|IMAGE_CUTOUT_)[A-Z0-9_]{1,100}", str(exc)) else ("STUDIO_IMAGE_CUTOUT_FAILED" if job["body"]["operation_id"] in {"m5.image.cutout", "m5.image.composite"} else "STUDIO_IMAGE_PROVIDER_REQUEST_FAILED")
            def fail(rows):
                row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                if row["status"] == "RUNNING" and row.get("execution_token") == job["execution_token"]:
                    fields = {}
                    if candidate is not None:
                        # Preserve a verified private candidate if the later
                        # authority/source check failed. UNKNOWN stays outside
                        # the human approval transition; no regeneration follows.
                        fields = {"output_asset_id": candidate["id"], "output_asset_version": candidate["version"],
                            "candidate_asset_version": candidate["version"], "output_digest": candidate["sha256"]}
                    _advance(row, status="UNKNOWN" if sent or invoked else "FAILED", error_code=code, **fields)
                    if candidate is not None:
                        row["receipt_digest"] = _digest(_receipt(row))
                elif (row["status"] == "CANCELLED" and row["body"]["operation_id"] in {"m5.image.cutout", "m5.image.composite"}
                        and row.get("execution_token") == job["execution_token"] and candidate is not None
                        and row.get("output_asset_id") is None):
                    # The cancellation remains terminal. Retain an already
                    # committed private result for inspection, never adoption.
                    _advance(row, output_asset_id=candidate["id"], output_asset_version=candidate["version"],
                        candidate_asset_version=candidate["version"], output_digest=candidate["sha256"])
                    row["receipt_digest"] = _digest(_receipt(row))
                return copy.deepcopy(row)
            return service._mutate(nid, branch, fail)


def accept(service, nid, branch, actor, job_id, *, expected_version, expected_request_digest,
           expected_output_digest, guard, source_guard, promote, recover_review=None):
    if not all(callable(value) for value in (guard, source_guard, promote)):
        raise ValueError("STUDIO_IMAGE_REVIEW_GUARDS_REQUIRED")
    _require_digest(expected_output_digest)
    with _execution_lease(service, job_id):
        guard(); source_guard()
        def review_intent(rows):
            row = _owned(service, service._find(rows, job_id), nid, branch, actor)
            _require_version(expected_version); _require_digest(expected_request_digest)
            if row["request_digest"] != expected_request_digest or row["output_digest"] != expected_output_digest:
                raise ValueError("STUDIO_IMAGE_REVIEW_DIGEST_CHANGED")
            if row["receipt_digest"] != _digest(_receipt(row)):
                raise ValueError("STUDIO_IMAGE_RECEIPT_CHANGED")
            if row["status"] in {"REVIEWING", "APPROVED"}:
                if expected_version not in {row["version"], row.get("review_from_version")}:
                    raise ValueError("STUDIO_IMAGE_JOB_VERSION_CONFLICT")
                return copy.deepcopy(row)
            _cas(row, expected_version, expected_request_digest)
            if row["status"] != "AWAITING_REVIEW":
                raise ValueError("STUDIO_IMAGE_NOT_REVIEWABLE")
            from uuid import uuid4
            _advance(row, status="REVIEWING", review_token=str(uuid4()), review_from_version=expected_version,
                error_code=None)
            return copy.deepcopy(row)
        job = service._mutate(nid, branch, review_intent)
        if job["status"] == "APPROVED":
            guard(); source_guard()
            return job
        def job_guard():
            # Called under the original asset lease. Legacy accept() acquires
            # its queue lock before an asset lease; waiting for that queue here
            # would reverse its lock order. atomic_write gives a whole snapshot.
            # This review owns the per-job execution lease, and REVIEWING rows
            # cannot be cancelled or handled by legacy methods. Final commit
            # still compares the exact version/token/receipt under the queue.
            row = _snapshot(service, nid, branch, actor, job_id)
            if (row["version"] != job["version"] or row["status"] != "REVIEWING"
                    or row.get("review_token") != job["review_token"] or row["receipt_digest"] != job["receipt_digest"]
                    or _digest(_receipt(row)) != job["receipt_digest"]):
                raise ValueError("STUDIO_IMAGE_REVIEW_CHANGED")
        provenance = {**_receipt(job), "receipt_digest": job["receipt_digest"], "human_review": "EXPLICIT_APPROVAL"}
        # Private candidate promotion is owned by original AssetLibrary.promote_owned.
        # Stable provenance permits recovery if promotion committed before job write.
        try:
            promoted = promote(job["output_asset_id"], job["candidate_asset_version"], provenance, job_guard)
            if (not isinstance(promoted, dict) or promoted.get("id") != job["output_asset_id"]
                    or promoted.get("sha256") != job["output_digest"]
                    or promoted.get("version") != job["candidate_asset_version"] + 1):
                raise ValueError("STUDIO_IMAGE_PROMOTED_ASSET_CHANGED")
            guard(); source_guard()
            def finish(rows):
                row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                _cas(row, job["version"], job["request_digest"])
                if (row["status"] != "REVIEWING" or row.get("review_token") != job["review_token"]
                        or row["receipt_digest"] != job["receipt_digest"] or _digest(_receipt(row)) != job["receipt_digest"]):
                    raise ValueError("STUDIO_IMAGE_REVIEW_CHANGED")
                return copy.deepcopy(_advance(row, status="APPROVED", output_asset_version=promoted["version"], error_code=None))
            return service._mutate(nid, branch, finish)
        except Exception:
            if callable(recover_review):
                def compensate():
                    def change(rows):
                        row = _owned(service, service._find(rows, job_id), nid, branch, actor)
                        _cas(row, job["version"], job["request_digest"])
                        if (row["status"] != "REVIEWING" or row.get("review_token") != job["review_token"]
                                or row["context"] != job["context"] or row["receipt_digest"] != job["receipt_digest"]
                                or _digest(_receipt(row)) != job["receipt_digest"]):
                            raise ValueError("STUDIO_IMAGE_REVIEW_CHANGED")
                        return copy.deepcopy(_advance(row, status="AWAITING_REVIEW", review_token=None,
                            review_from_version=None, review_state="VERIFIED_PRIVATE_CANDIDATE",
                            error_code="STUDIO_IMAGE_REVIEW_NOT_PROMOTED"))
                    return service._mutate(nid, branch, change)
                try:
                    # Keep the original queue -> asset order, including the
                    # private-proof callback. The callback invokes this exact
                    # reentrant CAS write while its source/asset leases remain
                    # held. No source/Host authority or provider action occurs.
                    with service._lock, workspace_mutation(service.root, "image-jobs"):
                        recover_review({"id": job["output_asset_id"], "version": job["candidate_asset_version"],
                            "digest": job["output_digest"], "kind": "image"}, compensate)
                except Exception:
                    # Promoted, deleted, changed or unprovable candidates stay
                    # REVIEWING for explicit recovery; preserve the first error.
                    pass
            raise
