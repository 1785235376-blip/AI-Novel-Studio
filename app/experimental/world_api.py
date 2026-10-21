"""Feature-gated world candidates, reviewed Canon and deterministic queries."""
import hashlib
from contextlib import contextmanager
from fastapi import APIRouter, Header, Query
from pydantic import Field

from .common import api_call
from .planning import StrictModel
from .world import (CHARACTER_REFERENCE_GROUP_KIND, CharacterReferenceGroupData,
    CharacterReferenceView, WorldRecordIn, WorldRecordEditIn)


class WorldActionIn(StrictModel):
    expected_version: int = Field(ge=1)


class CharacterReferenceGroupIn(StrictModel):
    character_id: str = Field(min_length=1, max_length=160)
    visual_record_id: str = Field(min_length=1, max_length=160)
    visual_record_version: int = Field(ge=1)
    visual_record_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    title: str = Field(min_length=1, max_length=240)
    views: list[CharacterReferenceView] = Field(min_length=3, max_length=3)
    consistency_confirmed: bool = True


def _verify_reference_group_owner(service, nid, scope, actor, data):
    """Server-derived group verification against the original owners.

    Client data is parsed only for shape. Every trusted fact is read back from
    the current World visual pin, existing Asset/Workspace owner and original
    Image production jobs. A client-supplied verification marker is ignored and
    replaced by the server result. Any missing, changed, cross-project or
    unproven request/asset relationship is rejected before a World row is written.
    """
    group = CharacterReferenceGroupData.model_validate(data)
    pin = service.character_visual_pin(nid, scope, group.visual_record_id)
    if (pin.get("character_id") != group.character_id
            or pin.get("version") != group.visual_record_version
            or pin.get("digest") != group.visual_record_digest):
        raise ValueError("CHARACTER_REFERENCE_GROUP_VISUAL_PIN_CHANGED")
    try:
        from . import api as experimental_api
        workspace = experimental_api.independent_workspace_service
        production = experimental_api.studio_production_service
    except (ImportError, AttributeError) as exc:
        raise ValueError("CHARACTER_REFERENCE_GROUP_VERIFICATION_UNAVAILABLE") from exc
    try:
        listed = production.list(nid, scope, actor, lambda: None)
    except Exception as exc:
        raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_UNAVAILABLE") from exc
    jobs = listed.get("items") if isinstance(listed, dict) else None
    if not isinstance(jobs, list):
        raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_UNAVAILABLE")
    used_jobs, used_assets, used_requests = set(), set(), set()
    for view in group.views:
        if view.request_id in used_requests or view.asset_id in used_assets:
            raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_REUSED")
        used_requests.add(view.request_id); used_assets.add(view.asset_id)
        try:
            public, content = workspace.download(nid, scope, view.asset_id)
        except (FileNotFoundError, PermissionError, ValueError) as exc:
            raise ValueError("CHARACTER_REFERENCE_GROUP_ASSET_UNAVAILABLE") from exc
        if (public.get("novel_id") != nid
                or (public.get("branch_id") or None) != (scope.get("branch_id") or None)
                or public.get("kind") != "image" or public.get("deleted_at")
                or public.get("version") != view.asset_version
                or public.get("sha256") != view.asset_sha256
                or hashlib.sha256(content).hexdigest() != view.asset_sha256):
            raise ValueError("CHARACTER_REFERENCE_GROUP_ASSET_CHANGED")
        matches = [row for row in jobs if row.get("owner") == "image" and row.get("request_id") == view.request_id]
        if len(matches) != 1:
            raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_UNPROVEN")
        job = matches[0]
        job_id = job.get("id")
        if not isinstance(job_id, str) or not job_id or job_id in used_jobs:
            raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_REUSED")
        used_jobs.add(job_id)
        command = job.get("command")
        candidate = job.get("output_candidate")
        provider = job.get("provider") or {}
        if (job.get("status") != "APPROVED" or job.get("approved_asset_version") != view.asset_version
                or not isinstance(command, dict) or not isinstance(candidate, dict)
                or not isinstance(command.get("operation_id"), str)
                or not command["operation_id"].startswith("m5.image.")
                or candidate.get("id") != view.asset_id or candidate.get("digest") != view.asset_sha256
                or candidate.get("kind") != "image"):
            raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_UNPROVEN")
        if (command.get("prompt") != view.prompt
                or command.get("parameters") != view.parameters
                or command.get("provider_id") != view.provider_id
                or command.get("model_id") != view.model_id
                or provider.get("provider_id") != view.provider_id
                or provider.get("model_id") != view.model_id):
            raise ValueError("CHARACTER_REFERENCE_GROUP_REQUEST_BINDING_CHANGED")
        source_ids = [source.get("id") for source in job.get("sources", []) if source.get("kind") == "ASSET"]
        if source_ids != view.reference_asset_ids:
            raise ValueError("CHARACTER_REFERENCE_GROUP_REFERENCE_BINDING_CHANGED")
        try:
            formal, formal_content = production.candidate(nid, scope, actor, "image", job_id, lambda: None)
        except Exception as exc:
            raise ValueError("CHARACTER_REFERENCE_GROUP_ASSET_ORIGIN_UNPROVEN") from exc
        if (formal.get("id") != view.asset_id or formal.get("version") != view.asset_version
                or formal.get("sha256") != view.asset_sha256 or formal.get("kind") != "image"
                or formal.get("novel_id") != nid
                or (formal.get("branch_id") or None) != (scope.get("branch_id") or None)
                or hashlib.sha256(formal_content).hexdigest() != view.asset_sha256):
            raise ValueError("CHARACTER_REFERENCE_GROUP_ASSET_ORIGIN_UNPROVEN")
    result = group.model_dump(mode="json")
    result["asset_verification"] = "SERVER_VERIFIED_FORMAL_ASSET_SNAPSHOTS"
    return result


@contextmanager
def _reference_group_commit_guard(service, nid, scope, actor, data):
    """Hold the original asset/job lease through the World/Canon durable write.

    The World store's final_guard runs this context manager immediately before
    its own atomic write/UPDATE, while the World scope lock is already held.
    Entering the existing Workspace/Asset project scope here takes the original
    asset -> project-owner lease. The asset version/content and the original
    approved Image job/review identity are re-read under that lease, and the
    lease remains held until the World commit finishes. Therefore a change that
    happened after the earlier verifier but before this commit is rejected and
    cannot leave a Canon row referencing the old snapshot.
    """
    group = CharacterReferenceGroupData.model_validate(data)
    pin = service.character_visual_pin(nid, scope, group.visual_record_id)
    if (pin.get("character_id") != group.character_id
            or pin.get("version") != group.visual_record_version
            or pin.get("digest") != group.visual_record_digest):
        raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_VISUAL_PIN_CHANGED")
    try:
        from . import api as experimental_api
        workspace = experimental_api.independent_workspace_service
        production = experimental_api.studio_production_service
    except (ImportError, AttributeError) as exc:
        raise ValueError("CHARACTER_REFERENCE_GROUP_VERIFICATION_UNAVAILABLE") from exc
    with workspace._asset_scope(nid, scope):
        binding = getattr(workspace.assets._scope, "binding", None)
        try:
            listed = production.list(nid, scope, actor, lambda: None)
        except Exception as exc:
            raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_UNAVAILABLE") from exc
        jobs = listed.get("items") if isinstance(listed, dict) else None
        if not isinstance(jobs, list):
            raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_UNAVAILABLE")
        used_jobs, used_assets, used_requests = set(), set(), set()
        for view in group.views:
            if view.request_id in used_requests or view.asset_id in used_assets:
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_REUSED")
            used_requests.add(view.request_id); used_assets.add(view.asset_id)
            try:
                meta = workspace.assets.get(view.asset_id, branch_id=scope.get("branch_id"))
                content = workspace.assets.content(view.asset_id, branch_id=scope.get("branch_id"))
            except (FileNotFoundError, PermissionError, ValueError) as exc:
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_ASSET_UNAVAILABLE") from exc
            if (meta.get("novel_id") != nid
                    or (meta.get("branch_id") or None) != (scope.get("branch_id") or None)
                    or meta.get("kind") != "image" or meta.get("deleted_at")
                    or meta.get("version") != view.asset_version
                    or meta.get("sha256") != view.asset_sha256
                    or meta.get("_project_binding") != binding
                    or hashlib.sha256(content).hexdigest() != view.asset_sha256):
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_ASSET_CHANGED")
            matches = [row for row in jobs if row.get("owner") == "image" and row.get("request_id") == view.request_id]
            if len(matches) != 1:
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_UNPROVEN")
            job = matches[0]
            job_id = job.get("id")
            if not isinstance(job_id, str) or not job_id or job_id in used_jobs:
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_REUSED")
            used_jobs.add(job_id)
            command = job.get("command")
            candidate = job.get("output_candidate")
            provider = job.get("provider") or {}
            if (job.get("status") != "APPROVED" or job.get("approved_asset_version") != view.asset_version
                    or not isinstance(command, dict) or not isinstance(candidate, dict)
                    or not isinstance(command.get("operation_id"), str)
                    or not command["operation_id"].startswith("m5.image.")
                    or candidate.get("id") != view.asset_id or candidate.get("digest") != view.asset_sha256
                    or candidate.get("kind") != "image"
                    or meta.get("source_job_id") != job_id
                    or not isinstance(meta.get("_studio_result_origin"), dict)
                    or meta["_studio_result_origin"].get("job_id") != job_id):
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_UNPROVEN")
            if (command.get("prompt") != view.prompt
                    or command.get("parameters") != view.parameters
                    or command.get("provider_id") != view.provider_id
                    or command.get("model_id") != view.model_id
                    or provider.get("provider_id") != view.provider_id
                    or provider.get("model_id") != view.model_id):
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REQUEST_BINDING_CHANGED")
            source_ids = [source.get("id") for source in job.get("sources", []) if source.get("kind") == "ASSET"]
            if source_ids != view.reference_asset_ids:
                raise ValueError("CHARACTER_REFERENCE_GROUP_COMMIT_REFERENCE_BINDING_CHANGED")
        yield


def create_world_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/world", tags=["experimental-world"])
    if hasattr(service, "reference_group_verifier"):
        service.reference_group_verifier = lambda nid, scope, actor, data: _verify_reference_group_owner(
            service, nid, scope, actor, data)
    if hasattr(service, "reference_group_commit_guard"):
        service.reference_group_commit_guard = lambda nid, scope, actor, data: _reference_group_commit_guard(
            service, nid, scope, actor, data)

    def access(nid, token, branch, permission="domain.read"):
        require_flag("world_character_engines_v2")
        return authorize(nid, token, branch, permission)

    @router.get("/schema")
    def schema(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        from .world import DATA_MODELS
        return {"record": WorldRecordIn.model_json_schema(), "kinds": {kind: model.model_json_schema() for kind, model in DATA_MODELS.items()}, "verification": "DETERMINISTIC_RULES"}

    @router.get("/records")
    def records(nid: str, kind: str | None = None, status: str | None = None, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        rows = api_call(service.records, nid, scope)
        items = []
        for row in rows:
            if (not kind or row["kind"] == kind) and (not status or row["status"] == status):
                if row["kind"] == "CHARACTER_VISUAL":
                    row = {**row, "record_digest": api_call(service.record_digest, nid, scope, row["id"])}
                items.append(row)
        return {"items": items}

    @router.post("/records", status_code=201)
    def create_record(nid: str, body: WorldRecordIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_record, nid, scope, actor, body)

    @router.get("/records/{rid}")
    def record(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.record, nid, scope, rid)

    @router.put("/records/{rid}")
    def edit_record(nid: str, rid: str, body: WorldRecordEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.edit_record, nid, scope, actor, rid, body)

    @router.get("/records/{rid}/history")
    def history(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.history, nid, scope, rid)}

    @router.get("/records/{rid}/pin")
    def character_visual_pin(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.character_visual_pin, nid, scope, rid)

    @router.post("/character-reference-groups", status_code=201)
    def create_character_reference_group(nid: str, body: CharacterReferenceGroupIn,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")

        def verified_create():
            # The dedicated route fills the current pin digest, then the same
            # service-level verifier used by generic create/edit/approve reads
            # the original owners again. No incoming marker is trusted.
            pin = service.character_visual_pin(nid, scope, body.visual_record_id)
            if (pin["character_id"] != body.character_id
                    or pin["version"] != body.visual_record_version
                    or body.visual_record_digest is not None and body.visual_record_digest != pin["digest"]):
                raise ValueError("CHARACTER_REFERENCE_GROUP_VISUAL_PIN_CHANGED")
            data = CharacterReferenceGroupData.model_validate({
                "character_id": body.character_id, "visual_record_id": body.visual_record_id,
                "visual_record_version": body.visual_record_version, "visual_record_digest": pin["digest"],
                "views": [view.model_dump(mode="json") for view in body.views],
                "consistency_confirmed": body.consistency_confirmed,
                "asset_verification": "UNVERIFIED",
            })
            record = WorldRecordIn(kind=CHARACTER_REFERENCE_GROUP_KIND, title=body.title,
                data=data.model_dump(mode="json"))
            return service.create_record(nid, scope, actor, record)

        return api_call(verified_create)

    @router.post("/records/{rid}/{action}")
    def review(nid: str, rid: str, action: str, body: WorldActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        permission = "domain.review" if action in {"approve", "reject", "reopen", "archive"} else "domain.write"
        actor, scope = access(nid, x_session_token, x_branch_id, permission)
        return api_call(service.review, nid, scope, actor, rid, action, body.expected_version)

    @router.get("/canon")
    def canon(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.canon, nid, scope)}

    @router.get("/continuity")
    def continuity(nid: str, include_candidates: bool = Query(False), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.continuity, nid, scope, include_candidates)

    @router.get("/character-state")
    def character_state(nid: str, character_id: str, chapter_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.character_state, nid, scope, character_id, chapter_id)

    return router
