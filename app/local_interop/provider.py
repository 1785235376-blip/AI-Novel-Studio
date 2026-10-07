"""Read-only projection of live Host-owned repositories and authorization.

No provider, model, discovery probe, credential store or project mutation is
invoked. Source locators are opaque labels, never paths to dereference.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import HTTPException

from .errors import InteropFailure

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SECRET = re.compile(r"(?i)(?:sk-[a-z0-9]{6}|bearer|password|api.?key|secret|token|dsn|cookie|-----BEGIN)")
FEATURES = frozenset({"editor", "model-center", "task-center", "error-panel", "story-simulator", "world", "screenplay", "media", "export", "local-ai", "workflow", "settings"})


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def safe_label(value, fallback=None):
    value = str(value) if value is not None else ""
    return value if ID.fullmatch(value) and not SECRET.search(value) else fallback


def anchor_text(doc: dict) -> str:
    """ProseMirror textBetween(blockSeparator='\\n', hardBreak='\\n')."""
    from ..document import plain_text
    return plain_text(doc)


class InteropContextProvider:
    def __init__(self, collaboration, *, model_center=None, jobs: Callable | None = None, export_jobs=None, workflow_reader: Callable | None = None):
        self.collaboration = collaboration
        self.model_center = model_center
        self.jobs = jobs
        self.export_jobs = export_jobs
        self.workflow_reader = workflow_reader

    def actor(self, token):
        try:
            if not token: raise KeyError()
            return self.collaboration.sessions.resolve(token)
        except (KeyError, ValueError):
            raise InteropFailure("SESSION_REQUIRED", 401) from None

    def authorize(self, token, scope):
        try:
            actor, authorized = self.collaboration.context(token, **scope)
            project = self.collaboration.novels.get(scope["project_id"])
            # Retained scope rows are never authority for a deleted project.
            identity = self.collaboration.identity
            membership = identity.get_membership(actor.actor_id, actor.workspace_id)
            proof = self.collaboration.authorization.explain(actor.actor_id, "domain.read", __import__("app.authorization", fromlist=["ModalityDomain"]).ModalityDomain.NOVEL, authorized)
            fingerprint = digest({"session": asdict(actor.session), "membership": asdict(membership), "user": asdict(identity.get_user(actor.actor_id)), "proof": proof, "scope": scope,
                "branch": self.collaboration.scopes.repository.get("branches", scope["branch_id"]),
                "storyline": self.collaboration.scopes.repository.get("storylines", scope["storyline_id"])})
            return actor, fingerprint, project
        except (HTTPException, KeyError, ValueError, FileNotFoundError, PermissionError):
            raise InteropFailure("PERMISSION_DENIED", 403) from None

    def chapter(self, scope, chapter_id):
        if not chapter_id: return None
        try:
            row = self.collaboration.chapters.get(chapter_id)
        except (KeyError, FileNotFoundError, ValueError):
            raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404) from None
        if row.get("novel_id") != scope["project_id"]:
            raise InteropFailure("PERMISSION_DENIED", 403)
        return row

    def task(self, token, scope, task_id, *, surface=None):
        if not task_id: return None
        actor = self.actor(token)
        if surface in {"export", "workflow"}:
            return self._owned_task(actor, scope, task_id, surface)
        try:
            obj = self.jobs().get(task_id) if self.jobs else None
            row = obj.public() if obj is not None and hasattr(obj, "public") else self.collaboration.generations.get(task_id)
        except (KeyError, FileNotFoundError):
            raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404) from None
        # Preserve generation's owning-actor boundary and exact branch scope.
        if row.get("actor_id") != actor.actor_id or row.get("workspace_id") != actor.workspace_id or row.get("novel_id") != scope["project_id"]:
            raise InteropFailure("PERMISSION_DENIED", 403)
        recorded = row.get("scope") or {}
        if any(recorded.get(key) != value for key, value in scope.items()):
            raise InteropFailure("PERMISSION_DENIED", 403)
        return row

    def _owned_task(self, actor, scope, task_id, surface):
        """Read actual export/workflow owners without invoking mutation-on-read."""
        try:
            if surface == "export" and self.export_jobs is not None:
                row = self.export_jobs.get(task_id)
                authority = row.get("permission_context") or {}
                valid = authority.get("mode") == "collaboration" and authority.get("actor_id") == actor.actor_id and authority.get("workspace_id") == actor.workspace_id
                valid = valid and authority.get("novel_id") == scope["project_id"] and authority.get("branch_id") == scope["branch_id"] and authority.get("storyline_id") == scope["storyline_id"]
            elif surface == "workflow" and self.workflow_reader is not None:
                row = self.workflow_reader(task_id)
                valid = row.get("owner") == {"actor_id": actor.actor_id, "workspace_id": actor.workspace_id} and row.get("branch_id") == scope["branch_id"]
            else:
                raise KeyError(task_id)
        except (KeyError, FileNotFoundError, ValueError):
            raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404) from None
        if not valid or row.get("novel_id") != scope["project_id"]:
            raise InteropFailure("PERMISSION_DENIED", 403)
        status = str(row.get("status", "UNKNOWN")).upper()
        status = {"SUCCEEDED": "COMPLETED", "WAITING_APPROVAL": "WAITING", "PAUSED": "WAITING", "WORKING": "RUNNING"}.get(status, status)
        error = row.get("error")
        return {"id": task_id, "novel_id": scope["project_id"], "actor_id": actor.actor_id,
            "workspace_id": actor.workspace_id, "scope": dict(scope), "operation": surface,
            "status": self.task_status(status), "error_code": safe_label(error.get("code")) if isinstance(error, dict) else None,
            "updated_at": row.get("updated_at") or row.get("version")}

    def snapshot(self, token, scope, *, module, surface, chapter_id=None, task_id=None):
        actor, fingerprint, project = self.authorize(token, scope)
        chapter = self.chapter(scope, chapter_id)
        task = self.task(token, scope, task_id, surface=surface)
        model_id = safe_label((task or {}).get("model"))
        runtime_id = None
        runtime_status = None
        models = self.model_rows()
        model = next((row for row in models if row["model_id"] == model_id), None)
        if model:
            runtime_id = model["runtime_id"]
            runtime_status = {"AVAILABLE": "READY", "UNAVAILABLE": "UNAVAILABLE", "UNKNOWN": "UNKNOWN"}[model["availability"]]
        state = {**scope, "project_version": digest(project), "module": module, "surface": surface,
            "chapter_id": chapter_id, "chapter_version": chapter["version"] if chapter else None,
            "task_id": task_id, "task_type": safe_label((task or {}).get("operation")),
            "task_status": self.task_status((task or {}).get("status")),
            "error_code": safe_label((task or {}).get("error_code")), "model_id": model_id,
            "runtime_id": runtime_id, "runtime_status": runtime_status}
        # Include document hash internally so same-version tampering is stale.
        source_version = digest({"state": state, "project": digest(project), "document": digest(chapter.get("document", {})) if chapter else None,
                                 "task_updated_at": (task or {}).get("updated_at")})
        self.authorize(token, scope)
        return {"actor": actor, "authorization": fingerprint, "state": state,
                "source_version": source_version, "chapter": chapter}

    def specific_context(self, token, scope, context_ids):
        # V1 uses an explicitly enumerated chapter-ID set, never whole-project
        # fallback, directory traversal, freeform locators or implicit expansion.
        if not 1 <= len(context_ids) <= 4 or len(set(context_ids)) != len(context_ids):
            raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        self.authorize(token, scope)
        rows = [self.chapter(scope, item) for item in context_ids]
        text = "\n\n".join(anchor_text(row["document"]) for row in rows)
        if len(text.encode()) > 65536: raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 413)
        versions = {row["id"]: {"version": row["version"], "hash": digest(row["document"])} for row in rows}
        self.authorize(token, scope)
        return text, versions

    @staticmethod
    def task_status(value):
        if value is None: return None
        aliases = {"GENERATING": "RUNNING", "REVIEWING": "RUNNING", "SETTLING": "WAITING"}
        value = aliases.get(value, value)
        return value if value in {"PENDING", "QUEUED", "RUNNING", "WAITING", "FAILED", "COMPLETED", "CANCELLED", "BLOCKED"} else "UNKNOWN"

    def model_rows(self):
        """Exact metadata allowlist. No serialize(model) or credential access."""
        center = self.model_center
        if center is None: return []
        rows = []
        for model in list(center.models.values())[:128]:
            if str(model.source).upper() != "LOCAL": continue
            for runtime in list(center.runtimes.values())[:64]:
                if model.runtime_type != runtime.runtime_type: continue
                if runtime.bind_address != "127.0.0.1": continue
                mid, rid = safe_label(model.id), safe_label(runtime.id)
                if not mid or not rid: continue
                instance = center.lifecycle.instances.get(runtime.id)
                observed = None
                if instance and instance.last_health_check:
                    try:
                        observed = datetime.fromisoformat(instance.last_health_check)
                        if observed.tzinfo is None or not 0 <= (datetime.now(UTC) - observed).total_seconds() <= 60: observed = None
                    except (TypeError, ValueError): observed = None
                # A missing/old cached probe is UNKNOWN, never proof of readiness.
                status = ("AVAILABLE" if instance.http_reachable else "UNAVAILABLE") if observed else "UNKNOWN"
                declared = tuple(safe_label(str(c)) for c in model.capabilities if safe_label(str(c)))
                rows.append({"runtime_id": rid, "model_id": mid, "family": safe_label(model.family, "unknown"),
                    "modality": ("TEXT",) if any("TEXT" in c for c in declared) else ("IMAGE",) if any("IMAGE" in c for c in declared) else ("MULTIMODAL",),
                    "runtime_type": str(runtime.runtime_type), "local": True,
                    "declared_capabilities": declared, "verified_capabilities": (),
                    "model_version": safe_label(model.version), "model_hash_if_available": None,
                    "context_window": runtime.context_size if isinstance(runtime.context_size, int) and not isinstance(runtime.context_size, bool) and 1 <= runtime.context_size <= 100_000_000 else None, "compatibility": (),
                    "availability": status, "last_validated": observed})
        return rows[:128]
