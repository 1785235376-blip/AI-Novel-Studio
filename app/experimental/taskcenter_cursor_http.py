"""Narrow File/local TaskCenter cursor composition, never a permission owner.

Every request executes the original authorizer and original task reader. The
original scope owner supplies committed row lifecycles; the original project
owner is observed with its existing-only policy. Only the selected, matching
200-row safe window is bound, not unrelated collections or the hidden tail.
No project lease is held while calling a reader, and no read provisions identity.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from ..services.generation_idempotency_authority import GenerationIdempotencyAuthority
from .imports import SemanticImportService
from .store import ExperimentalStore
from .taskcenter_cursor import (
    TaskCenterCursorEngine, TaskCenterCursorInvalid, TaskCenterCursorRestart,
    TaskCenterCursorUnsupported, canonical_digest,
)
from .taskcenter_query import add_query_metadata, cursor_not_supported
from .ux import WorkspaceToolsService, projected_task

QUERY_ERROR = {"code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID"}
RESTART_ERROR = {"code": "TASKCENTER_CURSOR_RESTART_REQUIRED",
                 "message": "TASKCENTER_CURSOR_RESTART_REQUIRED"}


def _no_store(exc):
    return HTTPException(exc.status_code, exc.detail,
                         headers={**(exc.headers or {}), "Cache-Control": "no-store"})


class TaskCenterQueryRoute(APIRoute):
    """Only exact GET /tasks opt-ins alter errors or cache behavior.

    A per-router subclass supplies the very same access callback as its endpoint,
    so a FastAPI q/bool validation error cannot outrun original authorization.
    Middleware-level failures remain the application's separate responsibility.
    """
    taskcenter_access = None

    def get_route_handler(self):
        original = super().get_route_handler()
        selected = self.path.endswith("/novels/{nid}/experimental/workspace/tasks")

        async def handler(request):
            opted_in = (selected and request.method == "GET" and
                        any(name in request.query_params for name in ("authority", "page_mode")))
            if not opted_in:
                return await original(request)
            try:
                try:
                    result = await original(request)
                except RequestValidationError:
                    await run_in_threadpool(self.taskcenter_access, request.path_params["nid"],
                                            request.headers.get("x-session-token"),
                                            request.headers.get("x-branch-id"))
                    raise HTTPException(422, QUERY_ERROR) from None
                result.headers["Cache-Control"] = "no-store"
                return result
            except HTTPException as exc:
                raise _no_store(exc) from None
        return handler


class TaskCenterCursorHTTPAdapter:
    """Explicit composition-root dependency supporting only one proven mode."""
    _window_limit = 200

    def __init__(self, service, source, reader, *, actual_repositories, runtime_mode,
                 engine=None):
        self.service, self.source, self.reader = service, source, reader
        self.actual_repositories, self.runtime_mode = actual_repositories, runtime_mode
        try:
            self.engine = engine if engine is not None else TaskCenterCursorEngine()
        except TaskCenterCursorUnsupported:
            # A secure metadata engine is optional; its absence must not break
            # original offset readers or unrelated application startup.
            self.engine = None

    def _gate(self, ctx, selection):
        packaged, collaboration = self.runtime_mode()
        if (self.engine is None or packaged or collaboration or ctx.actor != "local-author"
                or ctx.scope != {"mode": "local", "novel_id": ctx.novel_id}
                or ctx.token is not None or ctx.branch is not None
                or selection.authorities != ("semantic_import",)
                or type(self.service) is not WorkspaceToolsService
                or type(self.source) is not SemanticImportService
                or type(self.source.store) is not ExperimentalStore
                or self.service.store is not self.source.store
                or self.source.store.backend != "file"
                or [reader for reader in self.service.task_readers
                    if reader.name == "semantic_import"] != [self.reader]):
            cursor_not_supported()

    @staticmethod
    def _unavailable(selection):
        if selection.cursor is not None:
            raise HTTPException(409, RESTART_ERROR)
        cursor_not_supported()

    def _owner(self, selection):
        """Verify actual repositories, never a settings-selected shadow root."""
        try:
            novels, chapters = self.actual_repositories()
            owners = [GenerationIdempotencyAuthority(n, c) for n, c in (
                (novels, chapters), (self.service.novels, self.service.chapters),
                (self.source.novels, self.source.chapters),
            )]
            root = Path(self.source.store.root).resolve()
            if any(owner.backend != "file" or owner.root != root for owner in owners):
                raise ValueError("unverified owner")
            return owners[0].owner
        except Exception:
            self._unavailable(selection)

    def _identity(self, ctx, selection, owner):
        try:
            with owner.existing_owner_only():
                return owner.incarnation(ctx.novel_id)
        except Exception:
            self._unavailable(selection)

    def _capture(self, ctx, selection, require_flag):
        # Check the existing feature authority before observing source evidence.
        require_flag("semantic_import_v2")
        try:
            return self.source.jobs_observation(ctx.novel_id, ctx.scope)
        except HTTPException:
            raise
        except Exception:
            self._unavailable(selection)

    def _window(self, ctx, observation, query, failed_only):
        """Use the original scope fence/projection/filter ordering and cap.

        This is checked against the real aggregate, never used instead of its
        authorization or reader. Private payload is never included; unmatched
        rows and hidden tail lifecycles cannot influence this fingerprint.
        A matched row's nonce tracks its original owner's committed changes,
        including changes to fields omitted from the public safe projection.
        """
        items, lifecycles, visible = [], [], False
        rows = observation["rows"]
        for row in rows[:200]:
            if not self.service._task_in_scope(ctx, self.reader, row):
                continue
            visible = True
            task = projected_task(self.reader, row)
            if failed_only and task["status"] not in {"FAILED", "UNKNOWN"}:
                continue
            if query.casefold() not in (task["id"] + task["label"] + task["stage_label"]).casefold():
                continue
            items.append(task)
            lifecycles.append((task["id"], observation["row_lifecycles"][task["id"]]))
        return {"items": items, "row_lifecycles": lifecycles,
                "source_truncated": visible and len(rows) > 200,
                "project_identity": observation["project_identity"],
                "document_incarnation": observation["document_incarnation"]}

    def _checked_capture(self, ctx, selection, require_flag, owner, identity,
                         query, failed_only):
        self._gate(ctx, selection)
        current_owner = self._owner(selection)
        if Path(current_owner.root).resolve() != Path(owner.root).resolve():
            self._unavailable(selection)
        observation = self._capture(ctx, selection, require_flag)
        # Validate actual repository/service ownership again after the source
        # callback, not just the owner object captured at request entrance.
        self._gate(ctx, selection)
        after_owner = self._owner(selection)
        if (Path(after_owner.root).resolve() != Path(owner.root).resolve()
                or observation.get("project_identity") != identity
                or self._identity(ctx, selection, after_owner) != identity):
            self._unavailable(selection)
        try:
            return self._window(ctx, observation, query, failed_only)
        except Exception:
            self._unavailable(selection)

    def _read_aggregate(self, ctx, selection, require_flag, query, failed_only, reauthorize):
        return self.service.tasks(ctx, require_flag, query, failed_only,
                                  reauthorize, authorities=selection.authorities)

    def tasks(self, ctx, selection, page, require_flag, query, failed_only,
              reauthorize):
        if (ctx.scope.get("mode") == "local" and selection.authorities == ("exports", "semantic_import")
                and getattr(self, "mixed_adapter", None) is not None):
            return self.mixed_adapter.tasks(ctx, selection, page, require_flag, query,
                                            failed_only, reauthorize)
        if (ctx.scope.get("mode") == "local" and selection.authorities == ("exports",)
                and getattr(self, "export_adapter", None) is not None):
            return self.export_adapter.tasks(ctx, selection, page, require_flag, query,
                                             failed_only, reauthorize)
        if ctx.scope.get("mode") == "collaboration" and getattr(self, "collaboration_adapter", None) is not None:
            return self.collaboration_adapter.tasks(ctx, selection, page, require_flag, query,
                                                    failed_only, reauthorize)
        reauthorize()
        self._gate(ctx, selection)
        # Use the existing engine's exact token grammar/MAC behavior. Tokens
        # remain metadata only and cannot restore authorization or cached rows.
        try:
            if selection.cursor is not None:
                self.engine._decode(selection.cursor)
        except TaskCenterCursorInvalid:
            raise HTTPException(422, QUERY_ERROR) from None
        except TaskCenterCursorRestart:
            raise HTTPException(409, RESTART_ERROR) from None
        owner = self._owner(selection)
        identity = self._identity(ctx, selection, owner)
        before = self._checked_capture(ctx, selection, require_flag, owner,
                                       identity, query, failed_only)
        reauthorize()
        result = self._read_aggregate(ctx, selection, require_flag, query, failed_only, reauthorize)
        reauthorize()
        after = self._checked_capture(ctx, selection, require_flag, owner,
                                      identity, query, failed_only)
        if (before != after or result.get("unavailable") != []
                or result.get("items") != after["items"]
                or result.get("observed_total") != len(after["items"])
                or not 0 <= len(after["items"]) <= self._window_limit
                or result.get("source_truncated") != after["source_truncated"]):
            self._unavailable(selection)
        limit = page.limit if page.limit is not None else 50
        binding = canonical_digest({"project": ctx.novel_id, "scope": ctx.scope,
            "actor": ctx.actor, "project_identity": identity,
            "document_incarnation": after["document_incarnation"],
            "session_member_grant": after.get("authority", "NOT_APPLICABLE_LOCAL_SINGLE_PRINCIPAL")})
        query_digest = canonical_digest({"authorities": selection.authorities,
            "query_casefold": query.casefold(), "failed_only": failed_only,
            "limit": limit, "order": "ORIGINAL_READER_COLLECTION_ORDER_V1"})
        projection = canonical_digest({"items": result["items"],
            "row_lifecycles": after["row_lifecycles"],
            "source_truncated": result["source_truncated"], "coverage": result["coverage"]})
        reauthorize()
        self._gate(ctx, selection)
        try:
            issuing_engine = self.engine
            position = issuing_engine.page(binding=binding, query=query_digest,
                projection=projection, observed_total=len(result["items"]),
                limit=limit, token=selection.cursor, supported=True)
        except TaskCenterCursorInvalid:
            raise HTTPException(422, QUERY_ERROR) from None
        except TaskCenterCursorRestart:
            raise HTTPException(409, RESTART_ERROR) from None
        except TaskCenterCursorUnsupported:
            self._unavailable(selection)
        # Returning a token/page needs fresh original authorization and lifecycle
        # evidence even after the engine has issued its metadata-only position.
        reauthorize()
        final = self._checked_capture(ctx, selection, require_flag, owner,
                                      identity, query, failed_only)
        if final != after:
            self._unavailable(selection)
        self._gate(ctx, selection)
        # Final observations above may be slow. They cannot extend the fixed
        # cursor deadline, nor return a position from a replaced/evicted engine.
        if self.engine is not issuing_engine:
            raise HTTPException(409, RESTART_ERROR)
        try:
            issuing_engine.validate_return(position)
        except TaskCenterCursorRestart:
            raise HTTPException(409, RESTART_ERROR) from None
        except TaskCenterCursorUnsupported:
            self._unavailable(selection)
        return add_query_metadata({**result,
            "items": result["items"][position.offset:position.offset + limit],
            "page_mode": "cursor", "limit": limit, "has_more": position.has_more,
            "next_cursor": position.next_cursor,
            "truncated": result["source_truncated"] or position.has_more}, selection)
