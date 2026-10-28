"""Local single-source cursors require the actual aggregate read to complete."""
import inspect
import pytest
from fastapi import HTTPException
from test_taskcenter_local_mixed_http import mixed, get, snapshot
from test_taskcenter_lifecycle_http import cursor_rig, rig
from app.experimental.ux import WorkspaceToolsService
from test_taskcenter_return_deadline import tcp_client
from dataclasses import replace

pytestmark = pytest.mark.file_backend_only

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('status', [403, 404])
@pytest.mark.parametrize('transport', ['mounted', 'tcp'])
@pytest.mark.parametrize('shape', ['empty', 'filtered', 'nonempty', 'continuation'])
def test_actual_single_reader_denial(mixed, prefix, which, status, shape, transport, request):
    e = mixed
    if transport == 'tcp':
        e.monkeypatch.setattr(e.rig, 'client', request.getfixturevalue('tcp_client'))
    if shape == 'empty':
        if which == 'semantic_import': e.e.seed(0)
        else: e.source._write({})
    params = {'authority': which}
    if shape == 'filtered': params['q'] = 'synthetic-no-match'
    if shape == 'continuation':
        first = get(e, params, prefix)
        assert first.status_code == 200, first.text
        params['cursor'] = first.json()['next_cursor']
        assert params['cursor']
    else:
        original_ok = get(e, params, prefix)
        assert original_ok.status_code == 200, original_ok.text
    source = e.e.source if which == 'semantic_import' else e.source
    method = 'jobs' if which == 'semantic_import' else 'list'
    original = getattr(source, method)
    calls = []
    def deny_actual_aggregate(*args, **kwargs):
        frame = inspect.currentframe()
        while frame is not None:
            if frame.f_code is WorkspaceToolsService.tasks.__code__:
                calls.append(True)
                raise HTTPException(status, {'private': 'single source denial'})
            frame = frame.f_back
        return original(*args, **kwargs)
    e.monkeypatch.setattr(source, method, deny_actual_aggregate)
    before = snapshot(e.rig.root)
    response = get(e, params, prefix)
    assert calls == [True], calls
    assert snapshot(e.rig.root) == before
    assert 'single source denial' not in response.text
    assert response.status_code == (409 if shape == 'continuation' else 501), response.text


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_healthy_empty_read_stays_successful_without_allocating(mixed, which, prefix, tcp_client):
    e = mixed
    e.monkeypatch.setattr(e.rig, 'client', tcp_client)
    if which == 'semantic_import': e.e.seed(0)
    else: e.source._write({})
    adapter = e.e.adapter if which == 'semantic_import' else e.e.adapter.export_adapter
    before = snapshot(e.rig.root)
    before_states = list(adapter.engine._states.items())
    result = get(e, {'authority': which}, prefix)
    assert result.status_code == 200, result.text
    assert result.json()['items'] == [] and result.json()['next_cursor'] is None
    assert result.json()['observed_total'] == 0
    assert list(adapter.engine._states.items()) == before_states
    assert snapshot(e.rig.root) == before
    assert 'receipt' not in result.text and 'row_lifecycles' not in result.text


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'wrong_reader', 'not_bool'])
def test_receipt_must_be_one_exact_successful_reader(mixed, which, fault):
    e = mixed
    original = e.e.svc.tasks
    def faulty(*args, **kwargs):
        observer = kwargs.pop('_read_observer', None)
        assert observer is not None
        def proxy(reader, completed):
            if fault == 'missing': return
            if fault == 'duplicate': observer(reader, completed)
            observer(replace(reader) if fault == 'wrong_reader' else reader,
                     1 if fault == 'not_bool' else completed)
        return original(*args, **kwargs, _read_observer=proxy)
    e.monkeypatch.setattr(e.e.svc, 'tasks', faulty)
    before = snapshot(e.rig.root)
    response = get(e, {'authority': which})
    assert response.status_code == 501, response.text
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('change', ['replace', 'remove', 'duplicate', 'reverse_others'])
def test_selected_reader_identity_survives_actual_aggregate(mixed, which, change):
    e = mixed
    original = e.e.svc.tasks
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        readers = e.e.svc.task_readers
        selected = next(r for r in readers if r.name == which)
        if change == 'replace': readers = tuple(replace(r) if r is selected else r for r in readers)
        elif change == 'remove': readers = tuple(r for r in readers if r is not selected)
        elif change == 'duplicate': readers = (*readers, selected)
        else: readers = tuple(reversed(readers))
        e.monkeypatch.setattr(e.e.svc, 'task_readers', readers)
        return result
    e.monkeypatch.setattr(e.e.svc, 'tasks', changed)
    before = snapshot(e.rig.root)
    response = get(e, {'authority': which})
    assert response.status_code == (200 if change == 'reverse_others' else 501), response.text
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('mode', ['offset', 'legacy'])
def test_denied_source_keeps_original_non_cursor_soft_skip(mixed, which, mode):
    e = mixed
    source = e.e.source if which == 'semantic_import' else e.source
    method = 'jobs' if which == 'semantic_import' else 'list'
    def denied(*args, **kwargs): raise HTTPException(403, {'private': 'denied'})
    e.monkeypatch.setattr(source, method, denied)
    params = {'authority': which}
    if mode == 'offset': params['page_mode'] = 'offset'
    before = snapshot(e.rig.root)
    response = e.rig.client.get(f'/api/novels/{e.rig.nid}/experimental/workspace/tasks', params=params)
    assert response.status_code == 200, response.text
    assert response.json()['items'] == [] and response.json()['unavailable'] == []
    assert snapshot(e.rig.root) == before
