"""Explicit non-packaged File/local export task cursor composition.

Always calls the original reader/reauthorizer. The original queue supplies its
atomic local 100-row observation; this adapter is not an authorization owner.
"""
from pathlib import Path
from fastapi import HTTPException
from ..services.export_job_service import ExportJobService
from ..services.generation_idempotency_authority import GenerationIdempotencyAuthority
from .taskcenter_cursor_http import TaskCenterCursorHTTPAdapter
from .taskcenter_query import cursor_not_supported
from .store import ExperimentalStore
from .ux import WorkspaceToolsService


class LocalExportTaskCenterCursorAdapter(TaskCenterCursorHTTPAdapter):
    def __init__(self, *args, actual_source, **kwargs):
        super().__init__(*args, **kwargs)
        self.actual_source = actual_source

    def _gate(self, ctx, selection):
        packaged, collaboration = self.runtime_mode()
        if (self.engine is None or packaged or collaboration or ctx.actor != 'local-author'
                or ctx.scope != {'mode': 'local', 'novel_id': ctx.novel_id}
                or ctx.token is not None or ctx.branch is not None
                or selection.authorities != ('exports',)
                or type(self.service) is not WorkspaceToolsService
                or type(self.source) is not ExportJobService
                or type(self.service.store) is not ExperimentalStore
                or self.service.store.backend != 'file'
                or [reader for reader in self.service.task_readers if reader.name == 'exports'] != [self.reader]):
            cursor_not_supported()

    def _owner(self, selection):
        try:
            if self.actual_source() is not self.source:
                raise ValueError('source replaced')
            novels, chapters = self.actual_repositories()
            owners = [GenerationIdempotencyAuthority(n, c) for n, c in (
                (novels, chapters), (self.service.novels, self.service.chapters))]
            root = Path(self.source.path).parent.resolve()
            if (Path(self.source.path).resolve() != root / 'export_jobs.json'
                    or Path(self.service.store.root).resolve() != root
                    or any(owner.backend != 'file' or owner.root != root for owner in owners)):
                raise ValueError('unverified owner')
            return owners[0].owner
        except Exception:
            self._unavailable(selection)

    def _capture(self, ctx, selection, require_flag):
        owner = self._owner(selection)
        identity = self._identity(ctx, selection, owner)
        try:
            return {**self.source.local_task_observation(ctx.novel_id), 'project_identity': identity}
        except HTTPException:
            raise
        except Exception:
            self._unavailable(selection)

    def _window(self, ctx, observation, query, failed_only):
        result = super()._window(ctx, observation, query, failed_only)
        # Preserve the original reader's 100-row cap BEFORE q/failed filtering.
        # A wholly foreign/rejected source must not disclose a truncation hint.
        visible = any(self.service._task_in_scope(ctx, self.reader, row)
                      for row in observation['rows'])
        return {**result, 'source_truncated': visible and observation['source_more']}
