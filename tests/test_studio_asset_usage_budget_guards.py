"""Preventive admission on synthetic files; no replacement authority owners."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from threading import Barrier
import time
import tracemalloc

import pytest

from app.creative.asset_usage_budget import (
    UsageBudgetError, UsageReadBudget, current_usage_budget, usage_read_budget,
)

pytestmark = pytest.mark.file_backend_only


def synthetic(tmp_path, payload=b'{"safe":1}'):
    path = tmp_path / 'synthetic.json'
    path.write_bytes(payload)
    return path


def test_original_numeric_read_and_actual_cumulative_bytes_remain_supported(tmp_path):
    path = synthetic(tmp_path, b'12345678')
    budget = UsageReadBudget()
    budget.MAX_READ_BYTES = 10
    assert budget.read(path) == '12345678'
    assert budget.snapshot() == {'reads': 1, 'read_bytes': 8, 'json_tokens': 1,
                                 'json_documents': 1, 'json_input_bytes': 8}
    with pytest.raises(UsageBudgetError, match='^STUDIO_USAGE_RESOURCE_UNAVAILABLE$'):
        budget.read(path)
    assert budget.reads == 2 and budget.read_bytes == 8


def test_single_file_limit_prevents_open_and_decode(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path, b'"' + b'x' * 128 + b'"')
    budget = UsageReadBudget()
    budget.MAX_SCOPE_BYTES = 64
    reached = []
    monkeypatch.setattr(module, '_open_read', lambda *a, **kw: reached.append(True))
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert reached == []
    assert budget.read_bytes == budget.json_input_bytes == 0


def test_read_count_prevents_open_even_for_empty_documents(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path, b'')
    budget = UsageReadBudget()
    budget.MAX_READS = 1
    assert budget.read(path) == ''
    reached = []
    monkeypatch.setattr(module, '_open_read', lambda *a, **kw: reached.append(True))
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert reached == []


@pytest.mark.parametrize('limit', [0, -1, True, '10'])
def test_invalid_internal_file_limit_fails_closed(tmp_path, limit):
    path = synthetic(tmp_path)
    with pytest.raises(UsageBudgetError):
        UsageReadBudget().read(path, limit)


def test_chunks_are_bounded_before_each_read(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path, b'"' + b'x' * 128 + b'"')
    original = module._open_read
    requested = []

    class Observed:
        def __init__(self, handle):
            self.handle = handle
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return self.handle.__exit__(*args)
        def fileno(self):
            return self.handle.fileno()
        def read(self, count):
            requested.append(count)
            assert 0 < count <= 16
            return self.handle.read(count)

    monkeypatch.setattr(module, '_open_read', lambda p: Observed(original(p)))
    budget = UsageReadBudget()
    budget.READ_CHUNK_BYTES = 16
    assert len(budget.read(path)) == 130
    assert requested == [16] * 8 + [2]
    assert budget.read_bytes == 130


@pytest.mark.parametrize('stage', ['before_open', 'after_chunk'])
def test_growth_rejected_before_decode_and_failed_reads_stay_charged(tmp_path, monkeypatch, stage):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path, b'"' + b'x' * 128 + b'"')
    budget = UsageReadBudget()
    budget.READ_CHUNK_BYTES = 16
    fired = []

    def grow(phase, target):
        if phase == stage and not fired:
            fired.append(phase)
            with target.open('ab') as handle:
                handle.write(b'x' * 1024)

    monkeypatch.setattr(module, '_read_checkpoint', grow)
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert fired == [stage]
    assert budget.read_bytes == (0 if stage == 'before_open' else 16)
    assert budget.json_documents == budget.json_input_bytes == 0
    # Retry cannot erase the read already consumed by the failed request.
    budget.MAX_READ_BYTES = budget.read_bytes
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert budget.reads == 2


def test_same_size_replacement_between_stat_and_open_is_rejected(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path, b'{"safe":1}')
    replacement = tmp_path / 'replacement.json'
    replacement.write_bytes(b'{"safe":2}')

    def replace(stage, target):
        if stage == 'before_open':
            replacement.replace(target)

    monkeypatch.setattr(module, '_read_checkpoint', replace)
    budget = UsageReadBudget()
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert budget.read_bytes == budget.json_documents == 0


def test_disappearance_after_initial_admission_is_not_an_empty_document(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path)

    def disappear(stage, target):
        if stage == 'before_open':
            target.unlink()

    monkeypatch.setattr(module, '_read_checkpoint', disappear)
    with pytest.raises(UsageBudgetError):
        UsageReadBudget().read(path)


@pytest.mark.skipif(os.name != 'nt', reason='Windows native sharing contract')
def test_windows_competing_writer_is_denied_and_query_refusal_is_not_claimed_mutation(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    payload = b'"' + b'a' * (module.UsageReadBudget.READ_CHUNK_BYTES * 2) + b'"'
    path = synthetic(tmp_path, payload)
    budget = UsageReadBudget()
    denied = []

    def overwrite(stage, target):
        if stage == 'after_chunk' and not denied:
            try:
                with target.open('r+b') as handle:
                    handle.seek(1)
                    handle.write(b'Z')
            except PermissionError as error:
                denied.append({'errno': error.errno, 'winerror': getattr(error, 'winerror', None)})
                raise
            raise AssertionError('native read admitted a competing direct writer')

    monkeypatch.setattr(module, '_read_checkpoint', overwrite)
    with pytest.raises(UsageBudgetError, match='^STUDIO_USAGE_RESOURCE_UNAVAILABLE$'):
        budget.read(path)
    assert len(denied) == 1 and path.read_bytes() == payload
    assert budget.read_bytes == budget.READ_CHUNK_BYTES
    # The failed read must release the native handle; later ordinary writes work.
    with path.open('ab') as handle:
        handle.write(b' ')
    print('WINDOWS_NATIVE_WRITE_DENIAL ' + json.dumps({
        'competing_direct_write': 'OS_DENIED', 'query': 'RESOURCE_UNAVAILABLE',
        'original_content_unchanged': True, 'handle_released_after_failure': True,
        'denial': denied[0], 'charged_read_bytes': budget.read_bytes,
    }, sort_keys=True))


@pytest.mark.skipif(os.name != 'nt', reason='Windows native sharing contract')
def test_windows_atomic_replace_remains_possible_and_replaced_observation_is_refused(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    payload = b'"' + b'a' * (module.UsageReadBudget.READ_CHUNK_BYTES * 2) + b'"'
    path = synthetic(tmp_path, payload)
    replacement = tmp_path / 'replacement.json'
    replacement.write_bytes(payload.replace(b'a', b'b'))
    replaced = []

    def replace(stage, target):
        if stage == 'after_chunk' and not replaced:
            replacement.replace(target)
            replaced.append(True)

    monkeypatch.setattr(module, '_read_checkpoint', replace)
    with pytest.raises(UsageBudgetError):
        UsageReadBudget().read(path)
    assert replaced == [True]
    assert path.read_bytes() == payload.replace(b'a', b'b')


@pytest.mark.skipif(os.name != 'nt', reason='Windows native sharing contract')
def test_windows_preexisting_direct_writer_prevents_read_admission(tmp_path):
    path = synthetic(tmp_path)
    budget = UsageReadBudget()
    with path.open('r+b'):
        with pytest.raises(UsageBudgetError):
            budget.read(path)
    assert budget.read_bytes == budget.json_documents == 0


@pytest.mark.parametrize('payload', [
    b'[' * 65 + b'0' + b']' * 65,
    b'{"huge":"' + b'x' * (256 * 1024 + 1) + b'"}',
    b'[' + b'{},' * 33_333 + b'{}]',
    b'{"number":' + b'1' * 1025 + b'}',
], ids=['depth', 'long-string', 'objects', 'long-number'])
def test_dangerous_shape_rejected_before_original_json_decoder(tmp_path, monkeypatch, payload):
    from app.experimental import store as store_module
    store = store_module.ExperimentalStore(tmp_path)
    scope = {'mode': 'local', 'novel_id': 'synthetic-project'}
    path = store.path('synthetic-project', scope)
    path.parent.mkdir()
    path.write_bytes(payload)
    reached = []

    def forbidden_decoder(*args, **kwargs):
        reached.append(True)
        raise AssertionError('dangerous input reached JSON decoder')

    monkeypatch.setattr(store_module.json, 'loads', forbidden_decoder)
    with usage_read_budget() as budget, pytest.raises(UsageBudgetError):
        store._file_read('synthetic-project', scope)
    assert reached == []
    assert budget.read_bytes == len(payload)
    assert budget.json_documents == 0


def test_valid_escaped_strings_and_unicode_are_still_original_decoder_inputs(tmp_path):
    value = {'quoted': 'a"b\\c', 'many_slashes': '\\\\"', 'unicode': '合成😀',
             'arr': [True, None, -42, 1.25]}
    path = synthetic(tmp_path, json.dumps(value, ensure_ascii=False).encode())
    budget = UsageReadBudget()
    assert json.loads(budget.read(path)) == value
    assert budget.json_documents == 1


def test_request_token_accounting_includes_repeated_reads(tmp_path):
    path = synthetic(tmp_path, b'[0]')
    budget = UsageReadBudget()
    budget.MAX_REQUEST_JSON_TOKENS = 5
    assert budget.read(path) == '[0]'
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert budget.json_tokens == 6 and budget.json_documents == 1
    assert budget.read_bytes == 6


def test_shape_cache_never_reuses_file_bytes_or_changed_parser_limits(tmp_path):
    path = synthetic(tmp_path, b'"12345678"')
    budget = UsageReadBudget()
    assert budget.read(path) == '"12345678"'
    budget.MAX_JSON_STRING_BYTES = 4
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert budget.read_bytes == 20 and budget.reads == 2
    path.write_bytes(b'[' * 65 + b'0' + b']' * 65)
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert budget.json_documents == 1


def test_shape_cache_retains_bounded_metadata_only(tmp_path):
    path = synthetic(tmp_path)
    budget = UsageReadBudget()
    for value in range(70):
        path.write_text(str(value), encoding='utf-8')
        assert budget.read(path) == str(value)
    assert len(budget._json_shapes) == budget.MAX_JSON_CACHED_SHAPES == 64
    assert all(isinstance(key[0], bytes) and len(key[0]) == 32 and type(tokens) is int
               for key, tokens in budget._json_shapes.items())
    assert budget.reads == 70 and budget.json_documents == 70


def test_binary_integrity_read_shares_cumulative_budget_without_json_decoder(tmp_path):
    binary = synthetic(tmp_path, b'\xff\x00\x01\x02')
    text = tmp_path / 'text.json'
    text.write_bytes(b'0')
    budget = UsageReadBudget()
    budget.MAX_READ_BYTES = 5
    assert budget.read_binary(binary) == b'\xff\x00\x01\x02'
    assert budget.json_input_bytes == budget.json_tokens == 0
    assert budget.read(text) == '0'
    assert budget.read_bytes == 5
    with pytest.raises(UsageBudgetError):
        budget.read_binary(binary)
    assert budget.read_bytes == 5


def test_binary_single_file_cap_prevents_open(tmp_path, monkeypatch):
    from app.creative import asset_usage_budget as module
    path = synthetic(tmp_path, b'\x00' * 17)
    budget = UsageReadBudget()
    budget.MAX_BINARY_BYTES = 16
    reached = []
    monkeypatch.setattr(module, '_open_read', lambda *a, **kw: reached.append(True))
    with pytest.raises(UsageBudgetError):
        budget.read_binary(path, limit=1000)
    assert reached == []
    assert budget.read_bytes == 0


def test_nested_contexts_reuse_budget_and_cleanup_after_failure(tmp_path):
    path = synthetic(tmp_path, b'0')
    assert current_usage_budget() is None
    with pytest.raises(UsageBudgetError):
        with usage_read_budget() as outer:
            outer.MAX_READS = 1
            outer.read(path)
            with usage_read_budget() as inner, usage_read_budget(enabled=False) as disabled:
                assert inner is disabled is outer
                inner.read(path)
    assert current_usage_budget() is None
    with usage_read_budget() as fresh:
        assert fresh is not outer and fresh.reads == fresh.read_bytes == 0
        assert fresh.read(path) == '0'
    assert current_usage_budget() is None


def test_fresh_http_request_scope_overrides_inherited_budget_and_restores_it(tmp_path):
    path = synthetic(tmp_path, b'0')
    with usage_read_budget() as inherited:
        inherited.MAX_READ_BYTES = 0
        with usage_read_budget(fresh=True) as request:
            assert request is not inherited
            assert current_usage_budget() is request
            assert request.read(path) == '0'
            with usage_read_budget() as owner:
                assert owner is request
        assert current_usage_budget() is inherited
        assert inherited.read_bytes == inherited.reads == 0
        with usage_read_budget(fresh=True) as second:
            assert second is not request and second.read_bytes == second.reads == 0
    assert current_usage_budget() is None


def test_separate_request_contexts_do_not_share_budget_across_threads(tmp_path):
    path = synthetic(tmp_path, b'0')
    barrier = Barrier(2)

    def request():
        with usage_read_budget() as budget:
            barrier.wait(timeout=10)
            budget.read(path)
            barrier.wait(timeout=10)
            return budget

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(request)
        second = workers.submit(request)
        budgets = [first.result(timeout=15), second.result(timeout=15)]
    assert budgets[0] is not budgets[1]
    assert all(b.reads == b.read_bytes == 1 for b in budgets)
    assert current_usage_budget() is None


def test_invalid_utf8_is_rejected_without_json_decode(tmp_path):
    path = synthetic(tmp_path, b'{"bad":"\xff"}')
    with pytest.raises(UsageBudgetError):
        UsageReadBudget().read(path)


@pytest.mark.parametrize('shape', ['oversized', 'long-string', 'depth', 'objects'])
def test_resource_refusal_allocation_measurement_is_not_rss(tmp_path, shape):
    payloads = {
        'oversized': b' ' * (UsageReadBudget.MAX_SCOPE_BYTES + 1),
        'long-string': b'"' + b'x' * (UsageReadBudget.MAX_JSON_STRING_BYTES + 1) + b'"',
        'depth': b'[' * 65 + b'0' + b']' * 65,
        'objects': b'[' + b'{},' * 33_333 + b'{}]',
    }
    path = synthetic(tmp_path, payloads[shape])
    budget = UsageReadBudget()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        with pytest.raises(UsageBudgetError):
            budget.read(path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        elapsed = time.perf_counter() - started
        tracemalloc.stop()
    print('RESOURCE_REFUSAL_MEASUREMENT ' + json.dumps({
        'shape': shape, 'input_bytes': len(payloads[shape]), 'elapsed_seconds': elapsed,
        'python_peak_bytes': peak, 'measurement_scope': 'tracemalloc during budget.read; not RSS',
        **budget.snapshot(),
    }, sort_keys=True))


@pytest.mark.parametrize('shape', ['long-string', 'depth', 'objects', 'encoded-ceiling'])
def test_accepted_shape_boundary_allocation_measurement_is_not_rss(tmp_path, shape):
    # A single non-BMP code point makes each otherwise ASCII decoded Python
    # string use wide storage. This measures encoded-vs-decoded amplification.
    wide_string = b'"' + b'x' * (UsageReadBudget.MAX_JSON_STRING_BYTES - 4) + '\U0001f600'.encode() + b'"'
    payloads = {
        'long-string': b'"' + b'x' * UsageReadBudget.MAX_JSON_STRING_BYTES + b'"',
        'depth': b'[' * UsageReadBudget.MAX_JSON_DEPTH + b'0' + b']' * UsageReadBudget.MAX_JSON_DEPTH,
        # 100,000 structural tokens, exactly the per-document admission cap.
        'objects': b'[' + b'{},' * 33_332 + b'{}]',
        'encoded-ceiling': b'[' + b','.join([wide_string] * 15) + b']',
    }
    path = synthetic(tmp_path, payloads[shape])
    budget = UsageReadBudget()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        value = json.loads(budget.read(path))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        elapsed = time.perf_counter() - started
        tracemalloc.stop()
    assert value is not None and budget.json_documents == 1
    print('RESOURCE_ACCEPTED_MEASUREMENT ' + json.dumps({
        'shape': shape, 'input_bytes': len(payloads[shape]), 'elapsed_seconds': elapsed,
        'python_peak_bytes': peak, 'measurement_scope': 'tracemalloc read and json.loads; not RSS',
        **budget.snapshot(),
    }, sort_keys=True))
