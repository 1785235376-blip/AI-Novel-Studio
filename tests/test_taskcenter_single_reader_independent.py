"""Independent transient-denial recovery and observer exception boundaries."""
import inspect

import pytest
from fastapi import HTTPException
from test_taskcenter_local_mixed_http import mixed, get, snapshot
from test_taskcenter_lifecycle_http import cursor_rig, rig
from app.experimental.ux import WorkspaceToolsService

pytestmark = pytest.mark.file_backend_only


def install_actual_denial(e, which, status):
    source = e.e.source if which == 'semantic_import' else e.source
    method = 'jobs' if which == 'semantic_import' else 'list'
    original = getattr(source, method)
    calls = []
    def denied(*args, **kwargs):
        frame = inspect.currentframe()
        while frame is not None:
            if frame.f_code is WorkspaceToolsService.tasks.__code__:
                calls.append(True)
                raise HTTPException(status, {'private': 'independent-reader-denial'})
            frame = frame.f_back
        return original(*args, **kwargs)
    e.monkeypatch.setattr(source, method, denied)
    return source, method, original, calls


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('status', [403, 404])
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_transient_denial_does_not_destroy_earlier_valid_cursor(mixed, which, status, prefix):
    e = mixed
    params = {'authority': which}
    first = get(e, params, prefix)
    assert first.status_code == 200, first.text
    params['cursor'] = first.json()['next_cursor']
    expected = get(e, params, prefix)
    assert expected.status_code == 200, expected.text
    adapter = e.e.adapter if which == 'semantic_import' else e.e.adapter.export_adapter
    state = list(adapter.engine._states.items())
    files = snapshot(e.rig.root)
    source, method, original, calls = install_actual_denial(e, which, status)
    denied = get(e, params, prefix)
    assert denied.status_code == 409, denied.text
    assert denied.headers['cache-control'] == 'no-store'
    assert calls == [True]
    assert 'independent-reader-denial' not in denied.text
    assert 'items' not in denied.json()
    assert list(adapter.engine._states.items()) == state
    e.monkeypatch.setattr(source, method, original)
    recovered = get(e, params, prefix)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json() == expected.json()
    assert list(adapter.engine._states.items()) == state
    assert snapshot(e.rig.root) == files


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('status', [403, 404])
@pytest.mark.parametrize('shape', ['source_empty', 'filter_empty'])
def test_empty_denial_cannot_create_engine_state_and_recovery_stays_empty(mixed, which, status, shape):
    e = mixed
    params = {'authority': which}
    if shape == 'source_empty':
        if which == 'semantic_import': e.e.seed(0)
        else: e.source._write({})
    else:
        params['q'] = 'independent-no-match'
    adapter = e.e.adapter if which == 'semantic_import' else e.e.adapter.export_adapter
    before = list(adapter.engine._states.items())
    files = snapshot(e.rig.root)
    source, method, original, calls = install_actual_denial(e, which, status)
    denied = get(e, params)
    assert denied.status_code == 501, denied.text
    assert denied.headers['cache-control'] == 'no-store'
    assert 'items' not in denied.json() and 'independent-reader-denial' not in denied.text
    assert calls == [True]
    assert list(adapter.engine._states.items()) == before
    e.monkeypatch.setattr(source, method, original)
    recovered = get(e, params)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['items'] == [] and recovered.json()['next_cursor'] is None
    assert recovered.json()['observed_total'] == 0
    assert list(adapter.engine._states.items()) == before
    assert snapshot(e.rig.root) == files


@pytest.mark.parametrize('which', ['semantic_import', 'exports'])
@pytest.mark.parametrize('failure', ['runtime', 'http'])
def test_observer_failure_is_not_swallowed_as_source_availability(mixed, which, failure):
    e = mixed
    original = e.e.svc.tasks
    sentinel = RuntimeError('synthetic observer failure') if failure == 'runtime' else HTTPException(418, {'code': 'SYNTHETIC_OBSERVER_FAILURE'})
    observed = []
    def observed_tasks(*args, **kwargs):
        observer = kwargs.pop('_read_observer')
        def broken(reader, completed):
            observed.append((reader.name, completed))
            observer(reader, completed)
            raise sentinel
        return original(*args, **kwargs, _read_observer=broken)
    e.monkeypatch.setattr(e.e.svc, 'tasks', observed_tasks)
    files = snapshot(e.rig.root)
    if failure == 'runtime':
        with pytest.raises(RuntimeError) as caught:
            get(e, {'authority': which})
        assert caught.value is sentinel
    else:
        response = get(e, {'authority': which})
        assert response.status_code == 418, response.text
        assert response.json()['detail'] == {'code': 'SYNTHETIC_OBSERVER_FAILURE'}
    assert observed == [(which, True)]
    assert snapshot(e.rig.root) == files
