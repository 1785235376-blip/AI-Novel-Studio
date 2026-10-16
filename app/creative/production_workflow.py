"""Unified production workflow projection over the original Studio owners.

This module introduces no project, asset, job, model, queue or timeline owner.
It reads the existing owners and returns one bounded projection so the Studio can
present Director, Storyboard, Image, Video, Audio, Timeline and Asset work as one
workflow. The projection is advisory: it grants no execution authority and can
never promote a milestone to acceptance.

Exactly one mutation exists here, and it is delegated to the original
scope-atomic preference row: the neutral studio's own saved intent set
(``WorkspacePreferences.intents``/``preset``/``custom_intent``) with its existing
version CAS and retained history. No second intent store is created.
"""
from __future__ import annotations

from typing import get_args

from fastapi import HTTPException

from ..experimental.common import now
from ..services.v1_capability_service import CapabilityVersionConflict
from .models import CreativeMode
from .production_workflow_models import ProductionIntentUpdate
from .workspace import IndependentWorkspaceService
from .workspace_models import CreativeIntent, WorkspacePreset, WorkspacePreferencesUpdate

CONTRACT = "studio-production-workflow/1"
SCHEMA_VERSION = 1

# Display labels mirror the existing frontend catalog
# (frontend/src/creative/studioWorkspacePreferences.ts). The identifier
# vocabulary itself is derived from the backend literals below, so the two can
# never drift out of the owner's declared value set.
INTENT_LABELS = {
    "novel_writing": "小说创作", "novel_adaptation": "小说改编", "ai_short_film": "短片",
    "commercial_cg": "商业 CG", "advertisement": "广告", "music_video": "MV",
    "game_previs": "游戏预演", "image_design": "图片设计", "podcast_voice": "播客 / 配音",
    "blank": "空白创作", "custom": "自定义",
}

# (module id, label, creative document mode, asset kind, authoritative owner)
MODULE_SPECS = (
    ("director", "导演", "DIRECTOR", None, "DirectorService"),
    ("storyboard", "分镜", "STORYBOARD", None, "StoryboardWorkspace"),
    ("image", "图像", None, "image", "ImageJobService"),
    ("video", "视频", None, "video", "StudioVideoExecution"),
    ("audio", "音频", None, "audio", "StudioAudioExecution"),
    ("timeline", "时间线", "PRODUCTION", None, "VideoAssemblyService"),
    ("asset", "资产", None, "asset", "AssetLibraryService"),
)

KIND_BUCKETS = ("image", "audio", "video", "text")
NEXT_ACTIONS = {
    "NOT_STARTED": "尚未开始",
    "PLANNED": "已规划，等待素材执行",
    "IN_PRODUCTION": "素材进行中",
    "REVIEW_PENDING": "有待人工复核的私有候选",
    "REVIEWED": "素材已复核",
}


def intent_catalog() -> tuple[str, ...]:
    """The owner's own intent vocabulary, as lowercase stable identifiers."""
    return tuple(value.lower() for value in get_args(CreativeIntent))


def preset_catalog() -> tuple[str, ...]:
    return tuple(value.lower() for value in get_args(WorkspacePreset))


def document_modes() -> tuple[str, ...]:
    """Every declared creative document mode; an unknown mode is never guessed."""
    return get_args(CreativeMode)


class ProductionWorkflowService:
    """Read the original owners and project them as one workflow.

    Every number below is measured from an existing owner's own rows. Nothing is
    inferred, scheduled or reserved, and no owner is asked to execute anything.
    """

    def __init__(self, workspace, creative):
        self.workspace, self.creative = workspace, creative

    # ---------------------------------------------------------------- reads --
    def projection(self, nid, scope):
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        document = self.workspace.store.read(nid, scope)
        preferences = IndependentWorkspaceService._preferences(document)
        incarnation = self.workspace.store.incarnation(nid)
        documents = self.creative.list(nid, scope)
        assets = self.workspace.asset_index(nid, scope)
        modules = self._modules(documents, assets)
        overview = self._asset_overview(assets)
        return {
            "schema_version": SCHEMA_VERSION,
            "contract": CONTRACT,
            "project_id": nid,
            "scope": self._scope_view(nid, scope),
            "advisory_only": True,
            "execution_authority": False,
            "generated_at": now(),
            "project_start": {
                "state": self._start_state(preferences),
                "entry_kind": "NEUTRAL_STUDIO",
                "incarnation": incarnation,
                "has_creative_documents": bool(documents),
                "start_action": {"method": "POST", "path": "/api/experimental/projects",
                                 "requires_original_host_session": True},
            },
            "creative_intent": self._intent_view(
                IndependentWorkspaceService._preference_view(preferences)),
            "modules": modules,
            "asset_overview": overview,
            "dashboard": self._dashboard(modules, overview),
        }

    @staticmethod
    def _scope_view(nid, scope):
        view = {"mode": scope.get("mode", "local"), "novel_id": nid}
        for key in ("workspace_id", "project_id", "storyline_id", "branch_id"):
            if key in scope:
                view[key] = scope[key]
        return view

    @staticmethod
    def _start_state(preferences):
        if preferences is None:
            return "NOT_STARTED"
        return "STARTED" if preferences.get("entry_kind") == "NEUTRAL_STUDIO" else "READY"

    @staticmethod
    def _intent_view(view):
        saved = [value for value in view.get("intents", []) if isinstance(value, str)]
        custom = view.get("custom_intent") if isinstance(view.get("custom_intent"), str) else ""
        values = []
        for identifier in intent_catalog():
            literal = identifier.upper()
            label = INTENT_LABELS.get(identifier, literal)
            # The author's own custom text is the custom entry's label, so the
            # editor never has to re-derive it from a second field.
            if identifier == "custom" and literal in saved and custom:
                label = custom
            values.append({"intent_id": identifier, "label": label,
                           "selected": literal in saved, "custom": identifier == "custom"})
        return {"version": view["version"], "preset": view["preset"], "values": values,
                "editable": True, "history_retained": True}

    def _modules(self, documents, assets):
        modes = {}
        for row in documents:
            mode = row.get("mode")
            modes[mode] = modes.get(mode, 0) + 1
        modules = []
        for identifier, label, mode, kind, owner in MODULE_SPECS:
            selected = [row for row in assets if kind == "asset" or row["kind"] == kind]
            documents_here = modes.get(mode, 0) if mode else 0
            pending = sum(1 for row in selected if row["review_status"] == "DRAFT")
            approved = sum(1 for row in selected if row["review_status"] == "APPROVED")
            jobs = len({row["source_job_id"] for row in selected if row["source_job_id"]})
            status = self._status(documents_here, len(selected), pending, approved)
            modules.append({
                "id": identifier, "label": label, "status": status,
                "document_count": documents_here, "asset_count": len(selected), "job_count": jobs,
                "blocked_reasons": ["PRIVATE_CANDIDATES_AWAITING_REVIEW"] if pending else [],
                "owner": owner, "next_action": NEXT_ACTIONS[status],
            })
        return modules

    @staticmethod
    def _status(documents, assets, pending, approved):
        if not documents and not assets:
            return "NOT_STARTED"
        if pending:
            return "REVIEW_PENDING"
        if not assets:
            return "PLANNED"
        return "REVIEWED" if approved else "IN_PRODUCTION"

    @staticmethod
    def _asset_overview(assets):
        by_kind = {bucket: 0 for bucket in KIND_BUCKETS + ("other",)}
        for row in assets:
            kind = row["kind"]
            by_kind[kind if kind in KIND_BUCKETS else "other"] += 1
        return {"total": len(assets), "by_kind": by_kind,
                "private_pending_review": sum(1 for row in assets if row["review_status"] == "DRAFT"),
                "reviewed": sum(1 for row in assets if row["review_status"] == "APPROVED")}

    @staticmethod
    def _dashboard(modules, overview):
        return {"stages_total": len(MODULE_SPECS),
                "stages_started": sum(1 for row in modules if row["status"] != "NOT_STARTED"),
                "stages_reviewed": sum(1 for row in modules if row["status"] == "REVIEWED"),
                "open_reviews": overview["private_pending_review"],
                "blocked_stages": [row["id"] for row in modules if row["blocked_reasons"]]}

    # ------------------------------------------------------------- mutation --
    def update_intent(self, nid, scope, actor, value, guard=lambda: None):
        """Replace the saved neutral intent through the original preference row.

        The write reuses the established scope-atomic transaction, version CAS and
        retained history of ``WorkspacePreferences``. No intent store, revision
        counter or history list is introduced here.
        """
        body = ProductionIntentUpdate.model_validate(value)
        sentinels = intent_catalog()
        selected, custom = [], ""
        for entry in body.values:
            if entry.intent_id not in sentinels:
                raise self._invalid(f"UNKNOWN_INTENT:{entry.intent_id}")
            if not entry.selected:
                continue
            if entry.intent_id.upper() in selected:
                raise self._invalid(f"DUPLICATE_INTENT:{entry.intent_id}")
            selected.append(entry.intent_id.upper())
            if entry.intent_id == "custom":
                custom = entry.label
        preset = body.preset.lower() if body.preset else None
        if preset is not None and preset not in preset_catalog():
            raise self._invalid(f"UNKNOWN_PRESET:{body.preset}")
        current = self._current_intent(nid, scope)
        # ``None`` declares "nothing saved yet" and must fail closed instead of
        # silently adopting whatever the row currently holds.
        expected = body.expected_version if body.expected_version is not None else 0
        payload = WorkspacePreferencesUpdate.model_validate({
            "expected_version": expected, "intents": selected, "custom_intent": custom,
            # The owner stores the declared uppercase literals; the wire form is
            # the lower-case catalog value.
            "preset": (preset.upper() if preset else None) or (current or {}).get("preset") or "BLANK",
        })
        try:
            view = self.workspace.preferences(nid, scope, actor, payload, guard)
        except CapabilityVersionConflict as exc:
            raise HTTPException(409, {"code": "PRODUCTION_WORKFLOW_INTENT_CONFLICT",
                                      "current": exc.current}) from None
        except ValueError as exc:
            raise self._invalid(str(exc)) from None
        return self._intent_view(view)

    @staticmethod
    def _invalid(message):
        return HTTPException(422, {"code": "PRODUCTION_WORKFLOW_INTENT_INVALID", "message": message})

    def _current_intent(self, nid, scope):
        document = self.workspace.store.read(nid, scope)
        row = IndependentWorkspaceService._preferences(document)
        if row is None:
            return None
        view = IndependentWorkspaceService._preference_view(row)
        return {"version": view["version"], "preset": view["preset"], "intents": list(view["intents"]),
                "custom_intent": view["custom_intent"]}
