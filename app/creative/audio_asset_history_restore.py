"""Read-only audio history restore preview.

Candidate admission and a real review route are unavailable. This module does
not issue confirmation authority, create candidates or manufacture receipts.
The original soft-delete restore contract is independent and unchanged.
"""
from __future__ import annotations
from copy import deepcopy
import re
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from ..services.audio_asset_history_store import AudioHistoryIntegrityError

_HEX = re.compile(r"[a-f0-9]{64}\Z")
OperationId = Annotated[StrictStr, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Digest = Annotated[StrictStr, Field(pattern=r"^[a-f0-9]{64}$")]

class AudioHistoryRestorePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: OperationId

class AudioHistoryRestoreConfirm(AudioHistoryRestorePreview):
    observation_token: Annotated[StrictStr, Field(min_length=1, max_length=8192)]
    confirm: Literal[True]

    @field_validator("confirm", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("explicit confirmation required")
        return value

class AudioHistoryRestoreResolve(AudioHistoryRestorePreview):
    operation_digest: Digest

def _snapshot(record, version_id):
    metadata = record.get("metadata", {})
    allowed = ("filename", "kind", "media_type", "size", "sha256", "version", "created_at", "updated_at")
    return {"version_id": version_id, "asset_version": record["asset_version"],
        "metadata_digest": record["metadata_digest"], "sha256": record["sha256"], "size": record["size"],
        "metadata": {key: deepcopy(metadata[key]) for key in allowed if key in metadata}}

class AudioAssetHistoryRestore:
    """Current-authority inspect; candidate writes remain explicitly unavailable."""
    def __init__(self, workspace):
        self.workspace = workspace

    @property
    def assets(self):
        return self.workspace.assets

    def _context(self, nid, scope, actor, aid, authority, guard, authorize_source):
        if not isinstance(authority, str) or not _HEX.fullmatch(authority):
            raise ValueError("AUDIO_HISTORY_AUTHORITY_REQUIRED")
        if not isinstance(actor, str) or not actor:
            raise ValueError("AUDIO_HISTORY_ACTOR_REQUIRED")
        if not callable(authorize_source):
            raise ValueError("AUDIO_HISTORY_SOURCE_AUTHORITY_REQUIRED")
        guard()
        incarnation = self.workspace.store.incarnation(nid)
        from .audio_asset_history import AudioAssetHistoryService
        row = AudioAssetHistoryService(self.workspace).row(nid, scope, actor, aid)
        if row.get("kind") != "audio":
            raise FileNotFoundError(aid)
        authorize_source(row)
        guard()
        return incarnation

    def _detail(self, aid, version_id, scope, actor, guard, authorize_source):
        return self.assets.audio_history_detail(aid, version_id, branch_id=scope.get("branch_id"), actor_id=actor,
            guard=guard, authorize_source=authorize_source)

    def inspect(self, nid, scope, actor, aid, version_id, guard, *, operation_id, authority, authorize_source=None):
        body = AudioHistoryRestorePreview(operation_id=operation_id)
        with self.workspace.store.existing_owner_only(), self.workspace._asset_scope(nid, scope):
            incarnation = self._context(nid, scope, actor, aid, authority, guard, authorize_source)
            detail = self._detail(aid, version_id, scope, actor, guard, authorize_source)
            head = detail["head"]
            current_detail = self._detail(aid, head, scope, actor, guard, authorize_source)
            target, current = _snapshot(detail["version"], version_id), _snapshot(current_detail["version"], head)
            available = True
            try:
                self.assets.audio_history_content(aid, version_id, branch_id=scope.get("branch_id"), actor_id=actor,
                    guard=guard, authorize_source=authorize_source, max_bytes=self.assets.MAX_BYTES)
            except AudioHistoryIntegrityError:
                available = False
            guard()
            differences = [{"field": key, "current": current["metadata"].get(key), "target": target["metadata"].get(key)}
                for key in sorted(set(current["metadata"]) | set(target["metadata"]))
                if current["metadata"].get(key) != target["metadata"].get(key)]
            return {"contract": "studio-audio-history-restore-preview/1", "asset_id": aid, "incarnation": incarnation,
                "operation_id": body.operation_id, "current": current, "target": target, "diff": differences,
                "diff_scope": "SAFE_DISPLAY_FIELDS", "metadata_changed": current["metadata_digest"] != target["metadata_digest"],
                "source_available": available, "binary_content_verified": available,
                "source_availability_scope": "TARGET_BYTES_AND_AUTHORIZED_SOURCE_METADATA",
                "candidate": {"kind": "audio", "status": "DRAFT", "private": True, "sha256": target["sha256"],
                    "size": target["size"], "approved": False, "created": False},
                "confirmation_available": False, "admission_available": False, "review_path_available": False,
                "restore_limitation": "AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE",
                "review_limitation": "HISTORY_CANDIDATE_REVIEW_ROUTE_NOT_IMPLEMENTED",
                "observation_token": None, "expires_at": None, "execution_authority": False}

    def confirm(self, nid, scope, actor, aid, version_id, value, guard, *, authority, authorize_source=None):
        AudioHistoryRestoreConfirm.model_validate(value)
        with self.workspace.store.existing_owner_only(), self.workspace._asset_scope(nid, scope):
            self._context(nid, scope, actor, aid, authority, guard, authorize_source)
            guard()
            raise ValueError("AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE")

    def resolve(self, nid, scope, actor, aid, value, guard, *, authority, authorize_source=None):
        AudioHistoryRestoreResolve.model_validate(value)
        with self.workspace.store.existing_owner_only(), self.workspace._asset_scope(nid, scope):
            self._context(nid, scope, actor, aid, authority, guard, authorize_source)
            guard()
            raise ValueError("AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE")
