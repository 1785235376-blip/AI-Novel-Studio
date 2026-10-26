"""Synthetic-only transparent request I/O/decode cost meter.

This is test instrumentation, not a product resource guard. Paths are relative
to a synthetic data root and never enter an HTTP response. Stack labels record
where a real original reader ran; no reader or authorization is replaced.
"""
from collections import defaultdict
from contextlib import contextmanager
import builtins
import io
import json
import os
from pathlib import Path
import sys
from threading import local
import time
import tracemalloc


class ResourceCostMeter:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.rows = defaultdict(lambda: {"read_calls": 0, "read_bytes": 0,
            "json_decodes": 0, "json_input_bytes": 0, "file_sizes": set()})
        self.thread = local()
        self.descriptors = {}
        self.write_opens = self.write_calls = self.written_bytes = 0
        self.mkdir_attempts = self.created_directories = 0
        self.owner_calls = defaultdict(int)
        self.budgets = []
        self.reader_errors = []

    def relative(self, name):
        try:
            path = Path(name).resolve()
            return path.relative_to(self.root).as_posix()
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def category(path):
        if path.endswith('/novel.json'):
            return 'project_metadata'
        if path.endswith('/creative_project_v2.json'):
            return 'incarnation_marker'
        if path.startswith('experimental_v1/'):
            return 'scope_json'
        if path in {'identity.json', 'authorization.json', 'collaboration_scope.json'}:
            return 'authority_json'
        if path.endswith('.bin'):
            return 'asset_binary'
        if path.endswith('.json') and 'assets/' in path:
            return 'asset_metadata'
        return 'other_UNCLASSIFIED'

    @staticmethod
    def via_usage_reader():
        frame = sys._getframe(1)
        while frame is not None:
            if (frame.f_code.co_filename.replace('\\', '/').endswith('/app/creative/asset_usage_budget.py')
                    and frame.f_code.co_name in {'read', 'read_binary', '_read_bytes'}):
                return True
            frame = frame.f_back
        return False

    @contextmanager
    def stage(self, label):
        previous = getattr(self.thread, 'stage', 'HTTP_outer')
        self.thread.stage = label
        try:
            yield
        finally:
            self.thread.stage = previous

    def row(self, path, guarded):
        return self.rows[(getattr(self.thread, 'query_phase', 'HTTP_entry'),
            getattr(self.thread, 'stage', 'HTTP_outer'), self.category(path), path, guarded)]

    def wrap(self, handle, name, mode):
        if getattr(handle, '_resource_meter_wrapped', False):
            return handle
        path = self.relative(name)
        if path is None:
            return handle
        if any(character in str(mode) for character in 'wax+'):
            self.write_opens += 1
        meter = self
        class File:
            _resource_meter_wrapped = True
            def __getattr__(self, key):
                return getattr(handle, key)
            def __enter__(self):
                handle.__enter__()
                return self
            def __exit__(self, *args):
                return handle.__exit__(*args)
            def read(self, *args):
                result = handle.read(*args)
                size = len(result.encode('utf-8') if isinstance(result, str) else result)
                guarded = meter.via_usage_reader()
                row = meter.row(path, guarded)
                row['read_calls'] += 1
                row['read_bytes'] += size
                try:
                    row['file_sizes'].add(os.fstat(handle.fileno()).st_size)
                except OSError:
                    pass
                meter.thread.last_path = path
                meter.thread.last_guarded = guarded
                return result
            def write(self, data, *args):
                count = handle.write(data, *args)
                meter.write_calls += 1
                meter.written_bytes += len(data[:count].encode('utf-8') if isinstance(data, str) else data[:count])
                return count
        return File()

    def install(self, patch):
        for owner in (builtins, io):
            original = owner.open
            def opened(name, mode='r', *args, _original=original, **kwargs):
                return self.wrap(_original(name, mode, *args, **kwargs), name, mode)
            patch.setattr(owner, 'open', opened)
        original_open, original_fdopen = os.open, os.fdopen
        def descriptor(name, *args, **kwargs):
            value = original_open(name, *args, **kwargs)
            self.descriptors[value] = name
            return value
        def fdopen(fd, mode='r', *args, **kwargs):
            return self.wrap(original_fdopen(fd, mode, *args, **kwargs), self.descriptors.get(fd), mode)
        patch.setattr(os, 'open', descriptor)
        patch.setattr(os, 'fdopen', fdopen)

        original_mkdir = Path.mkdir
        def mkdir(path, *args, **kwargs):
            included = self.relative(path) is not None
            existed = path.exists() if included else True
            if included:
                self.mkdir_attempts += 1
            result = original_mkdir(path, *args, **kwargs)
            if included and not existed:
                self.created_directories += 1
            return result
        patch.setattr(Path, 'mkdir', mkdir)

        original_loads = json.loads
        reader_suffixes = ('/app/repository.py', '/app/experimental/store.py',
            '/app/creative/project_store.py', '/app/services/asset_library_service.py',
            '/app/repositories/file/identity.py', '/app/repositories/file/scope.py')
        def loads(value, *args, **kwargs):
            caller = sys._getframe(1).f_code.co_filename.replace('\\', '/')
            path = getattr(self.thread, 'last_path', None)
            if path is not None and caller.endswith(reader_suffixes):
                row = self.row(path, getattr(self.thread, 'last_guarded', False))
                row['json_decodes'] += 1
                row['json_input_bytes'] += len(value.encode('utf-8') if isinstance(value, str) else value)
                self.thread.last_path = None
            return original_loads(value, *args, **kwargs)
        patch.setattr(json, 'loads', loads)

        from app import api
        from app.creative import asset_usages, asset_usage_paging, asset_usage_budget, graph, production_execution
        original_budget_init = asset_usage_budget.UsageReadBudget.__init__
        def budget_init(budget, *args, **kwargs):
            original_budget_init(budget, *args, **kwargs)
            self.budgets.append(budget)
        patch.setattr(asset_usage_budget.UsageReadBudget, '__init__', budget_init)
        if hasattr(asset_usage_budget, '_open_read'):
            # Native Windows admitted handles need a path label even when the
            # owner obtains the descriptor without Python os.open(). Reads
            # still execute on the original admitted handle, unchanged.
            original_open_read = asset_usage_budget._open_read
            def budget_open(path):
                return self.wrap(original_open_read(path), path, 'rb')
            patch.setattr(asset_usage_budget, '_open_read', budget_open)
        def stage_method(owner, name, label):
            original = getattr(owner, name)
            def observed(*args, **kwargs):
                self.owner_calls[name] += 1
                with self.stage(label):
                    try:
                        return original(*args, **kwargs)
                    except Exception as error:
                        # Synthetic evidence only, never a product response.
                        self.reader_errors.append({'reader': name, 'type': type(error).__name__,
                                                   'synthetic_error': str(error)[:256]})
                        raise
            patch.setattr(owner, name, observed)
        stage_method(api, '_workbench_authorize', 'original_authorization_or_reauthorization')
        stage_method(asset_usages, '_source', 'source_asset_validation')
        for owner, names in ((graph.CreativeGraphService, ('usage_directory', 'usage_get')),
                             (production_execution.ProductionExecutionService,
                              ('timeline_usage_directory', 'timeline_usage_get'))):
            for name in names:
                stage_method(owner, name, 'consumer_discovery' if 'directory' in name else 'consumer_content_validation')
        original_checkpoint = asset_usage_paging._checkpoint
        def checkpoint(stage):
            self.thread.stage = stage
            self.thread.query_phase = stage
            return original_checkpoint(stage)
        patch.setattr(asset_usage_paging, '_checkpoint', checkpoint)

    def result(self):
        rows = [{"query_checkpoint_phase": phase, "stage": stage, "category": category,
                 "synthetic_relative_file": path, 'physical_input_via_usage_budget': guarded,
                 **{name: value for name, value in values.items() if name != 'file_sizes'},
                 "observed_file_sizes": sorted(values['file_sizes'])}
                for (phase, stage, category, path, guarded), values in sorted(self.rows.items())]
        return {"rows": rows, "read_calls": sum(row['read_calls'] for row in rows),
            "read_bytes": sum(row['read_bytes'] for row in rows),
            "json_decodes": sum(row['json_decodes'] for row in rows),
            "json_input_bytes": sum(row['json_input_bytes'] for row in rows),
            "write_opens": self.write_opens, "write_calls": self.write_calls,
            "written_bytes": self.written_bytes, "mkdir_attempts": self.mkdir_attempts,
            "created_directories": self.created_directories,
            "owner_calls": dict(self.owner_calls),
            "reader_errors": self.reader_errors,
            "usage_budgets": [{'charged_read_bytes': budget.read_bytes,
                               'charged_file_attempts': budget.reads} for budget in self.budgets]}


def measured_cost(root, patch, callback):
    meter = ResourceCostMeter(root)
    with patch.context() as scoped:
        meter.install(scoped)
        tracemalloc.start()
        started = time.perf_counter()
        try:
            response = callback()
            elapsed = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return response, {**meter.result(), 'elapsed_seconds': elapsed,
        'instrumented_python_peak_bytes': peak,
        'memory_scope': 'tracemalloc during instrumented request; not RSS, not a hard process limit'}


def four_page_observations(client, root, nid, aid, headers, patch):
    """Observe first, continuation, replayed continuation and repeated first page."""
    base = f'/api/novels/{nid}/experimental/production/assets/{aid}/studio-asset-usages'
    cursor = None
    records = []
    expected_continuation = None
    for label in ('first_page', 'continuation_page', 'repeat_continuation_page', 'repeat_first_page'):
        params = {'limit': 2}
        if label in {'continuation_page', 'repeat_continuation_page'}:
            params['cursor'] = cursor
        response, metrics = measured_cost(root, patch, lambda: client.get(base, params=params, headers=headers))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['other_dependencies'] == 'UNKNOWN'
        assert len(body['items']) == 2
        if label == 'first_page':
            cursor = body['next_cursor']
            assert body['has_more'] and cursor
        elif label == 'continuation_page':
            expected_continuation = body['items']
            assert not body['has_more'] and body['total'] == 4
        elif label == 'repeat_continuation_page':
            assert body['items'] == expected_continuation
        records.append({'request_phase': label, 'returned': len(body['items']),
            'declared_authority_reads_in_budget': body['budgets'].get('authority_reads_in_budget', False),
            'response_bytes': len(response.content), **metrics})
    return records
