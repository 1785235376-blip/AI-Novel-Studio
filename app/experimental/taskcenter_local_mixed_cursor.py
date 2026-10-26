"""Bounded File/local semantic-import + exports composition.

Sequential original-owner observations are revalidated around the original
aggregate and after token issuance. They are not a cross-file atomic snapshot.
"""
from dataclasses import replace
from pathlib import Path
from .taskcenter_cursor_http import TaskCenterCursorHTTPAdapter
from .taskcenter_export_cursor import LocalExportTaskCenterCursorAdapter
from .taskcenter_query import cursor_not_supported
from .ux import WorkspaceToolsService


class LocalMixedTaskCenterCursorAdapter(TaskCenterCursorHTTPAdapter):
    _window_limit = 300
    _selection = ('exports', 'semantic_import')
    _caps = {'semantic_import': 200, 'exports': 100}

    def __init__(self, service, semantic_import, exports, *, actual_sources):
        super().__init__(service, semantic_import.source, semantic_import.reader,
                         actual_repositories=semantic_import.actual_repositories,
                         runtime_mode=semantic_import.runtime_mode)
        self.components = {'semantic_import': semantic_import, 'exports': exports}
        self.actual_sources = actual_sources

    def _sources_current(self, selection):
        try:
            actual = self.actual_sources()
            if (len(actual) != 2 or actual[0] is not self.components['semantic_import'].source
                    or actual[1] is not self.components['exports'].source):
                raise ValueError('original source replaced')
        except Exception:
            self._unavailable(selection)

    def _gate(self, ctx, selection):
        if (self.engine is None or selection.authorities != self._selection
                or type(self.service) is not WorkspaceToolsService
                or type(self.components['semantic_import']) is not TaskCenterCursorHTTPAdapter
                or type(self.components['exports']) is not LocalExportTaskCenterCursorAdapter
                or any(component.service is not self.service for component in self.components.values())):
            cursor_not_supported()
        for name, component in self.components.items():
            component._gate(ctx, replace(selection, authorities=(name,)))
        self._sources_current(selection)

    def _owner(self, selection):
        self._sources_current(selection)
        owners = [component._owner(replace(selection, authorities=(name,)))
                  for name, component in self.components.items()]
        if any(Path(owner.root).resolve() != Path(owners[0].root).resolve() for owner in owners):
            self._unavailable(selection)
        return owners[0]

    def _read_aggregate(self, ctx, selection, require_flag, query, failed_only, reauthorize):
        # Account for the ACTUAL aggregate invocations, not separate probes.
        # The normal aggregate may omit 403/404 sources; a mixed cursor must
        # not bind even an empty denied source. Receipts are request-local and
        # contain no task payload. Shared readers/registries are never wrapped.
        self._gate(ctx, selection)
        self._owner(selection)
        expected = [reader for reader in self.service.task_readers if reader.name in self.components]
        receipts = []
        def observed(reader, completed):
            receipts.append((reader.name, reader, completed))
        result = self.service.tasks(ctx, require_flag, query, failed_only, reauthorize,
                                    authorities=selection.authorities, _read_observer=observed)
        current = [reader for reader in self.service.task_readers if reader.name in self.components]
        if (len(receipts) != 2 or len(expected) != 2 or len(current) != 2
                or any(current[i] is not expected[i] for i in range(2))
                or any(name != expected[i].name or reader is not expected[i]
                       or reader is not self.components[name].reader or completed is not True
                       for i, (name, reader, completed) in enumerate(receipts))):
            self._unavailable(selection)
        self._gate(ctx, selection)
        self._owner(selection)
        return result

    def _checked_capture(self, ctx, selection, require_flag, owner, identity, query, failed_only):
        self._gate(ctx, selection)
        if Path(self._owner(selection).root).resolve() != Path(owner.root).resolve():
            self._unavailable(selection)
        # Registry order, not lexicographic query normalization or caller order.
        names = [reader.name for reader in self.service.task_readers if reader.name in self.components]
        if len(names) != 2 or set(names) != set(self.components):
            self._unavailable(selection)
        items, nonces, documents, truncated = [], [], [], False
        for name in names:
            part = self.components[name]._checked_capture(
                ctx, replace(selection, authorities=(name,)), require_flag,
                owner, identity, query, failed_only)
            if (part['project_identity'] != identity
                    or not 0 <= len(part['items']) <= self._caps[name]
                    or any(item.get('authority') != name for item in part['items'])):
                self._unavailable(selection)
            items.extend(part['items'])
            nonces.extend((name, rid, nonce) for rid, nonce in part['row_lifecycles'])
            # Include even empty-source incarnation and actual reader order.
            documents.append((name, part['document_incarnation']))
            truncated = truncated or part['source_truncated']
        self._gate(ctx, selection)
        if (Path(self._owner(selection).root).resolve() != Path(owner.root).resolve()
                or self._identity(ctx, selection, owner) != identity
                or names != [reader.name for reader in self.service.task_readers
                             if reader.name in self.components]):
            self._unavailable(selection)
        return {'items': items, 'row_lifecycles': nonces,
                'document_incarnation': documents, 'project_identity': identity,
                'source_truncated': truncated}
