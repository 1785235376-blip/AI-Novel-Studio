"""Experimental media workflow contracts and explicitly reviewed image artifacts.

Discovery never registers executable code. Family definitions describe missing
adapters; only host-installed implementations can be registered. No adapter in
this module performs network IO or infers approval from successful generation.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import inspect
import json
import platform
import struct
import threading
import zlib
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..media_files import inspect_image
from ..source_privacy import content_digest
from .common import DomainService, StaleSourceError, check_version, new_row, now, snapshot


OPERATIONS = {
    "IMAGE": ("text_to_image", "image_edit", "multi_reference_image", "character_reference_image",
              "scene_reference_image", "cover_generation", "storyboard_card_generation"),
    "VIDEO": ("text_to_video", "image_to_video", "start_end_frame", "continuation", "storyboard_to_clip"),
    "AUDIO": ("tts", "character_voice", "emotion_tts", "dialogue_sequence", "chapter_audiobook"),
}
FAMILIES = {
    "qwen-image": ("Qwen-Image", "IMAGE", OPERATIONS["IMAGE"]),
    "flux": ("FLUX / FLUX.2", "IMAGE", OPERATIONS["IMAGE"]),
    "z-image": ("Z-Image", "IMAGE", OPERATIONS["IMAGE"]),
    "minimax-h3": ("MiniMax H3 Video", "VIDEO", OPERATIONS["VIDEO"]),
    "wan": ("Wan", "VIDEO", OPERATIONS["VIDEO"]),
    "ltx": ("LTX", "VIDEO", OPERATIONS["VIDEO"]),
    # These are processing families, not fabricated text/video generators.
    "seedvr2": ("SeedVR2", "VIDEO", ("upscale",)),
    "rife": ("RIFE", "VIDEO", ("frame_interpolation",)),
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def scene_sources(nid, scope, scene, chapters):
    """Capture chapter provenance from the scene's original source version."""
    cid, version = scene.get("source_chapter_id"), scene.get("source_version")
    if scene.get("source_independent") is True and cid is None and version is None:
        return {}
    if not cid or not isinstance(version, int) or isinstance(version, bool):
        raise StaleSourceError("MEDIA_SCENE_SOURCE_EVIDENCE_REQUIRED")
    chapter = chapters.get(cid)
    if chapter.get("novel_id") != nid or chapter.get("branch_id") != scope.get("branch_id"):
        raise StaleSourceError("BRANCH_SOURCE_ADAPTER_REQUIRED")
    if chapter.get("version") != version:
        raise StaleSourceError("MEDIA_SCENE_SOURCE_VERSION_CHANGED")
    return {cid: {"version": version, "digest": content_digest(chapter)}}


def checkpoint_promotion_asset(service, nid, scope, actor, collection, current, asset):
    """Durable cross-store checkpoint; never claims a distributed transaction."""
    with service.store.transaction(nid, scope) as doc:
        row = doc["collections"][collection][current["id"]]
        if row.get("promotion_token") != current["promotion_token"] or row["status"] not in {"APPROVING", "APPROVED"}:
            raise ValueError("MEDIA_PROMOTION_CHANGED")
        if row.get("promotion_asset_id"):
            if row["promotion_asset_id"] != asset["id"]:
                raise ValueError("MEDIA_PROMOTION_ASSET_CHANGED")
            return copy.deepcopy(row)
        row.setdefault("history", []).append(snapshot(row))
        row.update(promotion_asset_id=asset["id"], promotion_asset_digest=asset["sha256"],
                   promotion_state="ASSET_CREATED", version=row["version"] + 1, updated_by=actor, updated_at=now())
        return copy.deepcopy(row)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MediaOperationInput(StrictModel):
    """Shared input contract for the complete IMAGE/VIDEO/AUDIO operation set."""
    operation: Literal["text_to_image", "image_edit", "multi_reference_image", "character_reference_image",
        "scene_reference_image", "cover_generation", "storyboard_card_generation", "text_to_video", "image_to_video",
        "start_end_frame", "continuation", "storyboard_to_clip", "tts", "character_voice", "emotion_tts",
        "dialogue_sequence", "chapter_audiobook"]
    prompt: str = Field(default="", max_length=20000)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    character_id: str | None = Field(default=None, max_length=240)
    scene_id: str | None = Field(default=None, max_length=240)
    shot_ids: list[str] = Field(default_factory=list, max_length=200)
    brief_id: str | None = Field(default=None, max_length=240)
    start_frame_asset_id: str | None = Field(default=None, max_length=240)
    end_frame_asset_id: str | None = Field(default=None, max_length=240)
    previous_clip_asset_id: str | None = Field(default=None, max_length=240)
    profile_id: str | None = Field(default=None, max_length=240)
    emotion: str | None = Field(default=None, max_length=80)
    segment_ids: list[str] = Field(default_factory=list, max_length=2000)
    chapter_id: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def operation_requirements(self):
        required = {
            "text_to_image": [self.prompt], "image_edit": [self.prompt, self.reference_asset_ids],
            "multi_reference_image": [self.prompt, len(self.reference_asset_ids) >= 2],
            "character_reference_image": [self.character_id, self.reference_asset_ids],
            "scene_reference_image": [self.scene_id, self.reference_asset_ids],
            "cover_generation": [self.brief_id], "storyboard_card_generation": [self.brief_id, self.shot_ids],
            "text_to_video": [self.prompt], "image_to_video": [self.reference_asset_ids],
            "start_end_frame": [self.start_frame_asset_id, self.end_frame_asset_id],
            "continuation": [self.previous_clip_asset_id], "storyboard_to_clip": [self.shot_ids],
            "tts": [self.prompt, self.profile_id], "character_voice": [self.prompt, self.character_id, self.profile_id],
            "emotion_tts": [self.prompt, self.profile_id, self.emotion],
            "dialogue_sequence": [self.segment_ids], "chapter_audiobook": [self.chapter_id, self.segment_ids],
        }
        if not all(required[self.operation]):
            raise ValueError("MEDIA_OPERATION_REQUIRED_INPUT_MISSING")
        return self


class SafeArea(StrictModel):
    left: float = Field(default=.08, ge=0, lt=.5)
    right: float = Field(default=.08, ge=0, lt=.5)
    top: float = Field(default=.08, ge=0, lt=.5)
    bottom: float = Field(default=.08, ge=0, lt=.5)
    units: Literal["FRACTION"] = "FRACTION"


class CoverBriefIn(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    subtitle: str = Field(default="", max_length=500)
    genre: str = Field(default="", max_length=160)
    character_ids: list[str] = Field(default_factory=list, max_length=50)
    palette: list[str] = Field(default_factory=list, max_length=20)
    composition: str = Field(default="", max_length=4000)
    safe_area: SafeArea = Field(default_factory=SafeArea)
    prompt: str = Field(default="", max_length=12000)
    chapter_ids: list[str] = Field(default_factory=list, max_length=500)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    privacy_level: Literal["LOCAL_ONLY", "CLOUD_ALLOWED"] = "LOCAL_ONLY"


class StoryboardBriefIn(StrictModel):
    screenplay_id: str = Field(min_length=1, max_length=240)
    shot_id: str = Field(min_length=1, max_length=240)
    expected_screenplay_version: int = Field(ge=1)
    prompt: str = Field(default="", max_length=12000)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    privacy_level: Literal["LOCAL_ONLY", "CLOUD_ALLOWED"] = "LOCAL_ONLY"


class MediaTaskIn(StrictModel):
    brief_id: str = Field(min_length=1, max_length=240)
    expected_brief_version: int = Field(ge=1)
    adapter_id: str = Field(min_length=1, max_length=240)
    candidate_count: int = Field(default=2, ge=1, le=8)


class AdapterDefinition(StrictModel):
    adapter_id: str
    family: str
    modality: Literal["IMAGE", "VIDEO", "AUDIO"]
    operations: list[str]
    state: Literal["ADAPTER_REQUIRED", "MOCK_ONLY", "CONTRACT_VERIFIED"]
    local: bool = True
    model_id: str | None = None
    adapter_version: str = "1"
    runnable: bool = False
    limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class MediaWorkflowRequest:
    request_id: str
    operation: str
    model_id: str
    brief: dict
    candidate_count: int
    scope: dict
    source_digest: str


@dataclass(frozen=True)
class ImageWorkflowResult:
    content: bytes
    media_type: str
    metadata: dict


class MediaWorkflowAdapter(Protocol):
    definition: AdapterDefinition

    def generate(self, request: MediaWorkflowRequest) -> list[ImageWorkflowResult]: ...


class MockImageWorkflowAdapter:
    """Deterministic colored PNG fixtures. No claim of image-model quality."""
    definition = AdapterDefinition(adapter_id="mock-image-v1", family="Deterministic test fixture", modality="IMAGE",
        operations=list(OPERATIONS["IMAGE"]), state="MOCK_ONLY", local=True, model_id="mock-png-v1", runnable=True,
        limitations=["Synthetic PNG test fixture; no real image model was called."])

    def generate(self, request):
        output = []
        for candidate in range(request.candidate_count):
            rgb = hashlib.sha256(f"{request.source_digest}:{candidate}".encode()).digest()[:3]
            def chunk(kind, data):
                return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xffffffff)
            content = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", 16, 16, 8, 2, 0, 0, 0))
                       + chunk(b"IDAT", zlib.compress((b"\0" + rgb * 16) * 16)) + chunk(b"IEND", b""))
            output.append(ImageWorkflowResult(content, "image/png", {"verification": "MOCK_ONLY", "candidate_index": candidate}))
        return output


class MediaAdapterRegistry:
    def __init__(self, include_mock=True):
        self._adapters = {}
        if include_mock:
            self.register(MockImageWorkflowAdapter())

    def register(self, adapter: MediaWorkflowAdapter):
        definition = AdapterDefinition.model_validate(adapter.definition)
        if not definition.runnable or definition.state == "ADAPTER_REQUIRED" or not callable(getattr(adapter, "generate", None)):
            raise ValueError("MEDIA_ADAPTER_IMPLEMENTATION_REQUIRED")
        if definition.adapter_id in self._adapters:
            raise ValueError("MEDIA_ADAPTER_ID_CONFLICT")
        # This is a trusted host extension point, deliberately absent from HTTP.
        self._adapters[definition.adapter_id] = adapter

    def definitions(self):
        rows = [AdapterDefinition(adapter_id=key, family=label, modality=modality, operations=list(operations),
                    state="ADAPTER_REQUIRED", limitations=["Family contract only. Model discovery does not install a workflow."]).model_dump()
                for key, (label, modality, operations) in FAMILIES.items()]
        rows.extend(AdapterDefinition.model_validate(adapter.definition).model_dump() for adapter in self._adapters.values())
        return {"items": rows, "operations": OPERATIONS, "request_schema": MediaOperationInput.model_json_schema(), "verification": "CONTRACT_VERIFIED"}

    def resolve(self, adapter_id, operation):
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise ValueError("MEDIA_ADAPTER_REQUIRED")
        if operation not in adapter.definition.operations:
            raise ValueError("MEDIA_OPERATION_UNSUPPORTED")
        return adapter


def production_environment(adapter):
    """Observed host implementation identity, never paths, secrets or hardware.

    A model name is not a weight hash. Only the built-in synthetic fixture has
    a complete deterministic implementation here; other adapters say unknown.
    """
    from .. import __version__
    def source_hash(value):
        try:
            return hashlib.sha256(inspect.getsource(value).encode()).hexdigest()
        except (OSError, TypeError):
            return None
    synthetic = type(adapter) is MockImageWorkflowAdapter
    return {"schema": "media-production-environment-v1", "app_version": __version__,
            "runtime": {"implementation": platform.python_implementation(), "python": platform.python_version(),
                        "zlib": zlib.ZLIB_RUNTIME_VERSION},
            "adapter_version": adapter.definition.adapter_version, "adapter_digest": source_hash(type(adapter)),
            "workflow_version": "r3-media-request-v1", "workflow_digest": source_hash(MediaService.execute),
            "model_id": adapter.definition.model_id, "model_digest": source_hash(type(adapter)) if synthetic else None,
            "deterministic": synthetic, "verification": "SYNTHETIC_PROTOCOL_ONLY" if synthetic else "MODEL_IDENTITY_INCOMPLETE"}


_ACTIVE = set()
_ACTIVE_LOCK = threading.RLock()


class MediaService(DomainService):
    BRIEFS, TASKS, PROPOSALS, LINKS = "media_briefs", "media_tasks", "media_proposals", "media_asset_links"

    def __init__(self, store, novels, chapters, assets=None, screenplays=None, registry=None, production_capture_enabled=None):
        super().__init__(store, novels, chapters)
        self.assets, self.screenplays = assets, screenplays
        self.registry = registry or MediaAdapterRegistry()
        if production_capture_enabled is None:
            from .flags import enabled_flags
            production_capture_enabled = lambda: "production_manifest_v2" in enabled_flags()
        self.production_capture_enabled = production_capture_enabled

    def _change_impact_visible(self, nid, scope, collection, row):
        """Opt-in derivative ownership survives every generic media route.

        Existing ordinary media/A13 records have no marker and are unchanged.
        A malformed marker or missing owner is denied rather than stripped.
        """
        if "change_impact_refresh_id" not in row:
            return True
        from .flags import enabled_flags
        if "change_impact_v2" not in enabled_flags():
            return False
        owner_id = row["change_impact_refresh_id"]
        if not isinstance(owner_id, str) or not owner_id:
            return False
        state = self.store.read(nid, scope)["collections"]
        owner = state.get("change_impact_refreshes_v2", {}).get(owner_id)
        if not isinstance(owner, dict) or owner.get("novel_id") != nid or owner.get("scope") != scope:
            return False
        task = state.get(self.TASKS, {}).get(owner.get("task_id"))
        if (not isinstance(task, dict) or task.get("novel_id") != nid or task.get("scope") != scope
                or task.get("change_impact_refresh_id") != owner_id):
            return False
        brief = state.get(self.BRIEFS, {}).get(task.get("brief_id"))
        if not isinstance(brief, dict) or brief.get("change_impact_refresh_id") != owner_id:
            return False
        try:
            self._scoped_sources(nid, scope, list(brief.get("sources", {})))
            self._character_snapshots(nid, scope, brief.get("character_ids", []))
            self._references(nid, scope, brief)
        except (FileNotFoundError, ValueError):
            return False
        if collection == self.TASKS:
            return owner["task_id"] == row["id"]
        if collection == self.BRIEFS:
            return task.get("brief_id") == row["id"]
        if collection == self.PROPOSALS:
            return row.get("task_id") == task["id"] and row.get("brief_id") == task.get("brief_id")
        return False

    def get(self, nid, scope, collection, rid):
        row = super().get(nid, scope, collection, rid)
        if not self._change_impact_visible(nid, scope, collection, row):
            raise FileNotFoundError("media record unavailable")
        return row

    def list(self, nid, scope, collection):
        return [row for row in super().list(nid, scope, collection)
                if self._change_impact_visible(nid, scope, collection, row)]

    def mutate(self, nid, scope, actor, collection, rid, expected_version, callback):
        # Perform the feature fence before CAS so an error cannot return a
        # disabled derivative's raw current snapshot or its history.
        def checked(row):
            if not self._change_impact_visible(nid, scope, collection, row):
                raise FileNotFoundError("media record unavailable")
            callback(row)
            if not self._change_impact_visible(nid, scope, collection, row):
                raise FileNotFoundError("media record unavailable")
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            row = doc["collections"].get(collection, {}).get(rid)
            if row is None or row.get("novel_id") != nid or row.get("scope") != scope:
                raise FileNotFoundError("media record unavailable")
            if not self._change_impact_visible(nid, scope, collection, row):
                raise FileNotFoundError("media record unavailable")
            from .common import change_row
            change_row(row, actor, expected_version, checked)
            return copy.deepcopy(row)

    def _scoped_sources(self, nid, scope, chapter_ids):
        for cid in chapter_ids:
            chapter = self.chapters.get(cid)
            if chapter.get("branch_id") != scope.get("branch_id"):
                raise StaleSourceError("BRANCH_SOURCE_ADAPTER_REQUIRED")
        return self.sources(nid, chapter_ids)

    def _character_snapshots(self, nid, scope, character_ids):
        rows = {r["id"]: r for r in self.novels.data_set(nid, "characters") if r.get("branch_id") == scope.get("branch_id")}
        if set(character_ids) - set(rows):
            raise ValueError("MEDIA_CHARACTER_REFERENCE_INVALID")
        return {cid: copy.deepcopy(rows[cid]) for cid in character_ids}

    def _references(self, nid, scope, payload):
        characters = {row["id"] for row in self.novels.data_set(nid, "characters") if row.get("branch_id") == scope.get("branch_id")}
        if set(payload.get("character_ids", [])) - characters:
            raise ValueError("MEDIA_CHARACTER_REFERENCE_INVALID")
        references = {}
        for aid in payload.get("reference_asset_ids", []):
            if self.assets is None:
                raise ValueError("MEDIA_ASSET_SERVICE_NOT_CONFIGURED")
            asset = self.assets.get(aid, branch_id=scope.get("branch_id"))
            if asset["novel_id"] != nid or asset.get("branch_id") != scope.get("branch_id"):
                raise FileNotFoundError(aid)
            references[aid] = {"version": asset["version"], "digest": asset["sha256"]}
        return references

    def _shot(self, nid, scope, screenplay_id, shot_id):
        if self.screenplays is None:
            raise ValueError("MEDIA_SCREENPLAY_SERVICE_NOT_CONFIGURED")
        screenplay = next((row for row in self.screenplays.list(nid, branch_id=scope.get("branch_id"))
                          if row["id"] == screenplay_id and row.get("branch_id") == scope.get("branch_id")), None)
        if screenplay is None:
            raise FileNotFoundError(screenplay_id)
        shot = next((row for row in screenplay.get("shots", []) if row["id"] == shot_id), None)
        if shot is None:
            raise FileNotFoundError(shot_id)
        scene = next((row for row in screenplay.get("scenes", []) if row["id"] == shot.get("scene_id")), None)
        if scene is None or shot.get("source_chapter_id") != scene.get("source_chapter_id"):
            raise StaleSourceError("MEDIA_SHOT_SCENE_SOURCE_MISMATCH")
        scene_sources(nid, scope, scene, self.chapters)
        return screenplay, shot

    def prepare_cover(self, nid, scope, actor, body):
        """Build a current-source brief for an atomic caller-owned checkpoint."""
        data = CoverBriefIn.model_validate(body).model_dump()
        data["character_snapshots"] = self._character_snapshots(nid, scope, data["character_ids"])
        data["character_sources"] = {cid: digest(row) for cid, row in data["character_snapshots"].items()}
        data.update(kind="COVER", sources=self._scoped_sources(nid, scope, data["chapter_ids"]),
                    asset_sources=self._references(nid, scope, data), status="DRAFT")
        return new_row(nid, scope, actor, data)

    def create_cover(self, nid, scope, actor, body):
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            row = self.prepare_cover(nid, scope, actor, body)
            doc["collections"].setdefault(self.BRIEFS, {})[row["id"]] = row
            return copy.deepcopy(row)

    def update_cover(self, nid, scope, actor, rid, expected_version, body):
        current = self.get(nid, scope, self.BRIEFS, rid)
        if "change_impact_refresh_id" in current:
            raise ValueError("CHANGE_IMPACT_OWNED_BRIEF_REQUIRES_FRESH_PREFLIGHT")
        data = CoverBriefIn.model_validate(body).model_dump()
        data["character_snapshots"] = self._character_snapshots(nid, scope, data["character_ids"])
        data["character_sources"] = {cid: digest(row) for cid, row in data["character_snapshots"].items()}
        data.update(sources=self._scoped_sources(nid, scope, data["chapter_ids"]), asset_sources=self._references(nid, scope, data))
        def change(row):
            if row["kind"] != "COVER":
                raise ValueError("MEDIA_BRIEF_KIND_INVALID")
            row.update(data)
        return self.mutate(nid, scope, actor, self.BRIEFS, rid, expected_version, change)

    def create_storyboard(self, nid, scope, actor, body):
        data = StoryboardBriefIn.model_validate(body).model_dump()
        screenplay, shot = self._shot(nid, scope, data["screenplay_id"], data["shot_id"])
        if screenplay.get("edit_version", 0) != data.pop("expected_screenplay_version"):
            raise StaleSourceError("MEDIA_SCREENPLAY_VERSION_CHANGED")
        scene = next(row for row in screenplay["scenes"] if row["id"] == shot["scene_id"])
        sources = scene_sources(nid, scope, scene, self.chapters)
        data.update(kind="STORYBOARD", title=f"Shot {shot.get('number', shot['id'])}", shot_snapshot=copy.deepcopy(shot), scene_snapshot=copy.deepcopy(scene),
                    screenplay_source={"id": screenplay["id"], "version": screenplay.get("edit_version", 0), "shot_digest": digest(shot)},
                    sources=sources, asset_sources=self._references(nid, scope, data), status="DRAFT")
        self.assert_sources(nid, sources)
        return self.create(nid, scope, actor, self.BRIEFS, data)

    def _assert_brief(self, nid, scope, brief):
        self._scoped_sources(nid, scope, list(brief.get("sources", {})))
        self._references(nid, scope, brief)
        characters = self._character_snapshots(nid, scope, brief.get("character_ids", []))
        if {cid: digest(row) for cid, row in characters.items()} != brief.get("character_sources", {}):
            raise StaleSourceError("MEDIA_CHARACTER_SOURCE_CHANGED")
        self.assert_sources(nid, brief.get("sources", {}))
        for aid, original in brief.get("asset_sources", {}).items():
            asset = self.assets.get(aid, branch_id=scope.get("branch_id"))
            if asset.get("novel_id") != nid or asset.get("branch_id") != scope.get("branch_id"):
                raise StaleSourceError("MEDIA_ASSET_SCOPE_CHANGED")
            if {"version": asset["version"], "digest": asset["sha256"]} != original:
                raise StaleSourceError("MEDIA_ASSET_SOURCE_CHANGED")
        if brief.get("kind") == "STORYBOARD":
            screenplay, shot = self._shot(nid, scope, brief["screenplay_id"], brief["shot_id"])
            old = brief["screenplay_source"]
            if screenplay.get("edit_version", 0) != old["version"] or digest(shot) != old["shot_digest"]:
                raise StaleSourceError("MEDIA_SHOT_SOURCE_CHANGED")

    def prepare_task(self, nid, scope, actor, body):
        """Build the existing-domain task for a caller-owned atomic checkpoint.

        This does not persist or execute. Replay uses it to commit its pointer
        and the media task in one ExperimentalStore transaction.
        """
        data = MediaTaskIn.model_validate(body).model_dump()
        brief = self.get(nid, scope, self.BRIEFS, data["brief_id"])
        if "change_impact_refresh_id" in brief:
            raise ValueError("CHANGE_IMPACT_OWNED_BRIEF_REQUIRES_FRESH_PREFLIGHT")
        check_version(brief, data.pop("expected_brief_version"))
        self._assert_brief(nid, scope, brief)
        operation = "cover_generation" if brief["kind"] == "COVER" else "storyboard_card_generation"
        adapter = self.registry.resolve(data["adapter_id"], operation)
        inputs = MediaOperationInput(operation=operation, brief_id=brief["id"],
            shot_ids=[brief["shot_id"]] if brief["kind"] == "STORYBOARD" else []).model_dump()
        data.update(request_inputs=inputs, status="QUEUED", brief_version=brief["version"], brief_snapshot=snapshot(brief),
                    source_digest=digest(snapshot(brief)), sources=brief["sources"], operation=operation,
                    adapter_definition=adapter.definition.model_dump(), attempt=0, execution_token=None, proposal_ids=[])
        if self.production_capture_enabled():
            data["queued_environment"] = production_environment(adapter)
        return new_row(nid, scope, actor, data)

    def queue(self, nid, scope, actor, body):
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            row = self.prepare_task(nid, scope, actor, body)
            doc["collections"].setdefault(self.TASKS, {})[row["id"]] = row
            return copy.deepcopy(row)

    def tasks(self, nid, scope):
        rows = self.list(nid, scope, self.TASKS)
        with _ACTIVE_LOCK:
            for row in rows:
                row["recoverable"] = row["status"] == "RUNNING" and row.get("execution_token") not in _ACTIVE
        return [self.public_task(row) for row in rows]

    def public_task(self, row):
        if not self._change_impact_visible(row["novel_id"], row["scope"], self.TASKS, row):
            raise FileNotFoundError("media record unavailable")
        result = copy.deepcopy(row)
        if not self.production_capture_enabled():
            def redact(item):
                for field in ("queued_environment", "observed_environment", "production_replay_id", "production_manifest_id"):
                    item.pop(field, None)
                for previous in item.get("history", []):
                    if isinstance(previous, dict): redact(previous)
            redact(result)
        return result

    def transition(self, nid, scope, actor, rid, action, expected_version):
        def change(row):
            if action == "cancel" and row["status"] in {"QUEUED", "RUNNING"}:
                row.update(status="CANCELLED", execution_token=None, cancellation_mode="LOCAL_RESULT_DISCARD")
            elif action == "retry" and (row["status"] in {"FAILED", "CANCELLED"} or
                    (row["status"] == "RUNNING" and row.get("execution_token") not in _ACTIVE)):
                if row.get("change_impact_refresh_id"):
                    raise ValueError("CHANGE_IMPACT_REQUIRES_NEW_PREFLIGHT_AND_TASK")
                if row.get("production_replay_id"):
                    raise ValueError("PRODUCTION_REPLAY_REQUIRES_NEW_PREFLIGHT_AND_TASK")
                row.update(status="QUEUED", execution_token=None, error_code=None)
            else:
                raise ValueError("MEDIA_TASK_TRANSITION_INVALID")
        return self.public_task(self.mutate(nid, scope, actor, self.TASKS, rid, expected_version, change))

    def _current_brief(self, nid, scope, task):
        brief = self.get(nid, scope, self.BRIEFS, task["brief_id"])
        if brief["version"] != task["brief_version"] or digest(snapshot(brief)) != task["source_digest"]:
            raise StaleSourceError("MEDIA_BRIEF_SOURCE_CHANGED")
        self._assert_brief(nid, scope, brief)
        return brief

    def execute(self, nid, scope, actor, rid, expected_version, check_authority=None, check_egress=None,
                production_guard=None, change_impact_guard=None):
        token = str(uuid4())
        def claim(row):
            if row["status"] != "QUEUED":
                raise ValueError("MEDIA_TASK_NOT_QUEUED")
            if row.get("change_impact_refresh_id") and change_impact_guard is None:
                raise ValueError("CHANGE_IMPACT_DISPATCH_AUTHORITY_REQUIRED")
            if row.get("production_replay_id") and production_guard is None:
                raise ValueError("PRODUCTION_REPLAY_DISPATCH_AUTHORITY_REQUIRED")
            self._current_brief(nid, scope, row)
            row.update(status="RUNNING", attempt=row["attempt"] + 1, execution_token=token, error_code=None)
        with _ACTIVE_LOCK:
            _ACTIVE.add(token)
        try:
            task = self.mutate(nid, scope, actor, self.TASKS, rid, expected_version, claim)
            try:
                adapter = self.registry.resolve(task["adapter_id"], task["operation"])
                if adapter.definition.model_dump() != task["adapter_definition"]:
                    raise ValueError("MEDIA_ADAPTER_CHANGED")
                if task.get("queued_environment") and not self.production_capture_enabled():
                    raise ValueError("MEDIA_PRODUCTION_CAPTURE_DISABLED")
                environment = production_environment(adapter) if task.get("queued_environment") else None
                if task.get("queued_environment") and task["queued_environment"] != environment:
                    raise ValueError("MEDIA_PRODUCTION_ENVIRONMENT_CHANGED")
                if check_authority is None and scope.get("mode") == "collaboration":
                    raise ValueError("MEDIA_AUTHORITY_REQUIRED")
                if check_authority:
                    check_authority()
                if not adapter.definition.local:
                    if check_egress is None:
                        raise ValueError("MEDIA_EGRESS_AUTHORITY_REQUIRED")
                    check_egress(task, adapter)
                if check_authority:
                    check_authority()
                self._current_brief(nid, scope, task)
                current = self.get(nid, scope, self.TASKS, rid)
                if current["status"] != "RUNNING" or current.get("execution_token") != token or current["version"] != task["version"]:
                    return self.public_task(current)
                MediaOperationInput.model_validate(task["request_inputs"])
                request = MediaWorkflowRequest(token, task["operation"], adapter.definition.model_id or "", task["brief_snapshot"],
                                               task["candidate_count"], copy.deepcopy(scope), task["source_digest"])
                if production_guard:
                    production_guard(task, adapter)
                if change_impact_guard:
                    change_impact_guard(task, adapter)
                results = adapter.generate(request)
                if len(results) != task["candidate_count"]:
                    raise ValueError("MEDIA_RESULT_COUNT_INVALID")
                proposals = []
                for index, result in enumerate(results):
                    if not isinstance(result, ImageWorkflowResult) or len(result.content) > 25 * 1024 * 1024:
                        raise ValueError("MEDIA_RESULT_INVALID")
                    measured = inspect_image(result.content)
                    if measured["media_type"] != result.media_type:
                        raise ValueError("MEDIA_RESULT_TYPE_MISMATCH")
                    proposals.append({**({"change_impact_refresh_id": task["change_impact_refresh_id"]} if "change_impact_refresh_id" in task else {}),
                        "id": str(uuid4()), "task_id": rid, "brief_id": task["brief_id"],
                        "kind": task["brief_snapshot"]["kind"], "candidate_index": index, "status": "PENDING_REVIEW",
                        "sources": task["sources"], "source_digest": task["source_digest"], "brief_version": task["brief_version"],
                        "content_base64": base64.b64encode(result.content).decode(), "content_sha256": hashlib.sha256(result.content).hexdigest(),
                        "media": measured, "adapter_id": task["adapter_id"], "model_id": adapter.definition.model_id,
                        "verification": adapter.definition.state, "asset_id": None, "version": 1,
                        "novel_id": nid, "scope": copy.deepcopy(scope), "created_by": actor, "updated_by": actor,
                        "created_at": now(), "updated_at": now(), "history": []})
                if check_authority:
                    check_authority()
                if environment and not self.production_capture_enabled():
                    raise ValueError("MEDIA_PRODUCTION_CAPTURE_DISABLED")
                if environment and (production_environment(adapter) != environment
                                    or adapter.definition.model_dump() != task["adapter_definition"]):
                    raise ValueError("MEDIA_PRODUCTION_ENVIRONMENT_CHANGED")
                with self.store.transaction(nid, scope) as doc:
                    row = doc["collections"][self.TASKS][rid]
                    if row["status"] != "RUNNING" or row.get("execution_token") != token or row["version"] != task["version"]:
                        return self.public_task(row)
                    if "change_impact_refresh_id" in task and check_authority:
                        check_authority()
                    self._current_brief(nid, scope, task)
                    collection = doc["collections"].setdefault(self.PROPOSALS, {})
                    for proposal in proposals:
                        collection[proposal["id"]] = proposal
                    row.setdefault("history", []).append(snapshot(row))
                    if environment:
                        row["observed_environment"] = environment
                    row.update(status="SUCCEEDED", proposal_ids=[p["id"] for p in proposals], version=row["version"] + 1,
                               updated_at=now(), updated_by=actor)
                    return self.public_task(row)
            except Exception as exc:
                def fail(row):
                    if row.get("execution_token") != token or row["status"] != "RUNNING":
                        return
                    row.update(status="FAILED", error_code="MEDIA_SOURCE_STALE" if isinstance(exc, StaleSourceError) else "MEDIA_EXECUTION_FAILED")
                current = self.get(nid, scope, self.TASKS, rid)
                if current.get("execution_token") == token and current["status"] == "RUNNING":
                    self.mutate(nid, scope, actor, self.TASKS, rid, current["version"], fail)
                raise
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(token)

    def proposals(self, nid, scope):
        rows = self.list(nid, scope, self.PROPOSALS)
        for row in rows:
            row.pop("content_base64", None)
            row["stale"] = self._stale(nid, scope, row)
        return rows

    def _stale(self, nid, scope, proposal):
        try:
            self._current_brief(nid, scope, self.get(nid, scope, self.TASKS, proposal["task_id"]))
            return False
        except (StaleSourceError, FileNotFoundError):
            return True

    def preview(self, nid, scope, rid):
        row = self.get(nid, scope, self.PROPOSALS, rid)
        content = base64.b64decode(row["content_base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != row["content_sha256"]:
            raise ValueError("MEDIA_PROPOSAL_INTEGRITY_FAILED")
        return content, row["media"]["media_type"]

    def compare(self, nid, scope, ids):
        if len(ids) < 2 or len(ids) > 8 or len(set(ids)) != len(ids):
            raise ValueError("MEDIA_COMPARE_REQUIRES_DISTINCT_CANDIDATES")
        rows = [self.get(nid, scope, self.PROPOSALS, rid) for rid in ids]
        if len({row["brief_id"] for row in rows}) != 1:
            raise ValueError("MEDIA_COMPARE_BRIEF_MISMATCH")
        return {"items": [{k: v for k, v in row.items() if k != "content_base64"} for row in rows],
                "inference_performed": False, "comparison_fields": ["adapter_id", "model_id", "media", "content_sha256", "verification"]}

    def review(self, nid, scope, actor, item_id, action, expected_version):
        if action != "approve":
            def decide(row):
                if action == "reopen" and row["status"] == "REJECTED":
                    row.update(status="PENDING_REVIEW")
                elif action == "reject" and row["status"] == "PENDING_REVIEW":
                    row.update(status="REJECTED")
                else:
                    raise ValueError("MEDIA_REVIEW_TRANSITION_INVALID")
            result = self.mutate(nid, scope, actor, self.PROPOSALS, item_id, expected_version, decide)
            result.pop("content_base64", None)
            return result
        # Persist the user's promotion intent before writing to another store.
        # If the host crashes, reject is blocked and approve resumes idempotently.
        current = self.get(nid, scope, self.PROPOSALS, item_id)
        check_version(current, expected_version)
        if current["status"] == "PENDING_REVIEW":
            def claim(row):
                task = self.get(nid, scope, self.TASKS, row["task_id"])
                self._current_brief(nid, scope, task)
                if self.assets is None:
                    raise ValueError("MEDIA_ASSET_SERVICE_NOT_CONFIGURED")
                row.update(status="APPROVING", promotion_token=str(uuid4()), promotion_started_at=now(), promotion_actor=actor)
            current = self.mutate(nid, scope, actor, self.PROPOSALS, item_id, expected_version, claim)
        elif current["status"] != "APPROVING":
            raise ValueError("MEDIA_REVIEW_TRANSITION_INVALID")
        task = self.get(nid, scope, self.TASKS, current["task_id"])
        brief = self._current_brief(nid, scope, task)
        content, _ = self.preview(nid, scope, item_id)
        measured = inspect_image(content)
        asset = self.assets.create(nid, f"r3-{current['id']}.{measured['extension']}", current["content_base64"],
            measured["media_type"], "image", "r3-media:" + item_id, branch_id=scope.get("branch_id"))
        current = checkpoint_promotion_asset(self, nid, scope, actor, self.PROPOSALS, current, asset)
        lineage = {"brief_id": brief["id"], "brief_version": brief["version"], "proposal_id": item_id,
            "source_digest": current["source_digest"], "sources": current["sources"], "verification": current["verification"],
            "screenplay_id": brief.get("screenplay_id"), "shot_id": brief.get("shot_id"), "screenplay_source": brief.get("screenplay_source")}
        self.assets.update_metadata(asset["id"], {"source_job_id": task["id"], "provider_id": current["adapter_id"],
            "model_id": current["model_id"], "parameters": {"experimental_media_lineage": lineage},
            "approved_at": current["promotion_started_at"], "source_asset_ids": brief.get("reference_asset_ids", [])},
            branch_id=scope.get("branch_id"))
        with self.store.transaction(nid, scope) as doc:
            row = doc["collections"][self.PROPOSALS][item_id]
            if row.get("promotion_token") != current["promotion_token"]:
                raise ValueError("MEDIA_PROMOTION_CHANGED")
            if row["status"] == "APPROVED":
                return {k: copy.deepcopy(v) for k, v in row.items() if k != "content_base64"}
            check_version(row, current["version"])
            if row["status"] != "APPROVING":
                raise ValueError("MEDIA_PROMOTION_CHANGED")
            self._current_brief(nid, scope, task)
            row.setdefault("history", []).append(snapshot(row))
            row.update(status="APPROVED", asset_id=asset["id"], lineage=lineage,
                approved_at=current["promotion_started_at"], approved_by=current["promotion_actor"],
                version=row["version"] + 1, updated_at=now(), updated_by=actor)
            return {k: copy.deepcopy(v) for k, v in row.items() if k != "content_base64"}

    def list_review_items(self, nid, scope):
        return [{**row, "domain": "media", "source": row["task_id"], "target": {"brief_id": row["brief_id"], "asset_id": row.get("asset_id")},
                 "preview": f"{row['kind']} candidate {row['candidate_index'] + 1}", "risk": "GENERATED_MEDIA_REQUIRES_REVIEW",
                 "privacy_state": "LOCAL_ONLY", "batch_allowed": False,
                 "allowed_actions": ["approve", "reject"] if row["status"] == "PENDING_REVIEW" else ["approve"] if row["status"] == "APPROVING" else ["reopen"] if row["status"] == "REJECTED" else [],
                 "recovery_required": row["status"] == "APPROVING",
                 "recovery_state": "SOURCE_CHANGED_RECONCILIATION_REQUIRED" if row["status"] == "APPROVING" and row["stale"] else "RESUME_APPROVAL" if row["status"] == "APPROVING" else None,
                 "promotion_asset_id": row.get("promotion_asset_id")} for row in self.proposals(nid, scope)]
