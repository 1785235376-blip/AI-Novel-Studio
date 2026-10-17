"""Actual app HTTP Director-to-Graph persistence, without browser/model claims."""
from contextlib import contextmanager
from copy import deepcopy
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from creative_director_execution_fixture import lifecycle, FLAGS
from test_director_application_host_additive import application_host
from test_director_model_transport_additive import pending
from test_v2_independent_director_adoption import review_body

pytestmark = pytest.mark.file_backend_only


@contextmanager
def native_client(app):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(32)
    server = uvicorn.Server(uvicorn.Config(app, loop='asyncio', lifespan='off',
        access_log=False, log_level='warning'))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    try:
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}',
                          trust_env=False, timeout=10) as client:
            yield client
    finally:
        server.should_exit = True
        if thread.ident is not None:
            thread.join(10)
        listener.close()
        assert not thread.is_alive()


@pytest.mark.parametrize('execute_planning', [False, True])
def test_reviewed_director_pin_saves_and_reopens_over_actual_app(application_host, monkeypatch, execute_planning):
    import app.main as main
    import app.experimental.api as experimental
    from app.services.asset_library_service import AssetLibraryService
    from app.creative.graph import CreativeGraphService
    from app.creative.graph_asset_inputs import GraphAssetInputs
    from app.creative.workspace import IndependentWorkspaceService
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore

    e, m = application_host
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS + ',asset_lineage_v2')
    workspace = experimental.independent_workspace_service
    assets = AssetLibraryService(e.root)
    # Rebind owned synthetic storage on captured original application objects.
    # Original HTTP authority, validation, graph persistence and CAS stay intact.
    for name, value in [('creative', e.documents), ('store', e.documents.store),
                        ('novels', e.novels), ('assets', assets)]:
        monkeypatch.setattr(workspace, name, value)
    graph = experimental.creative_graph_service
    monkeypatch.setattr(graph, 'store', e.documents.store)
    monkeypatch.setattr(graph, 'workspace', workspace)
    monkeypatch.setattr(graph, 'asset_inputs', GraphAssetInputs(graph))
    prefix = m.base.split('/novels/', 1)[0]
    base = prefix + f'/projects/{e.nid}/studio'
    with native_client(main.app) as client:
        m.client = client
        candidate = pending(e, m)
        body = review_body(candidate)
        result = client.post(m.url + '/review', headers=m.headers, json=body)
        assert result.status_code == 200, result.text
        receipt = result.json()['receipt']['document']
        pin = {'id': receipt['document_id'], 'version': receipt['version'], 'digest': receipt['digest']}
        source = deepcopy(e.documents.get(e.nid, e.scope, pin['id']))
        activation = client.post(base + '/activate', headers=m.headers)
        assert activation.status_code == 200, activation.text
        definition = {'schema_version': 4, 'title': 'Reviewed Director planning', 'nodes': [
            {'id': 'reviewed-director', 'definition_id': 'director_plan',
             'parameters': {'document_snapshot': pin}, 'position': {'x': 120, 'y': 80}}], 'edges': []}
        created = client.post(base + '/graphs', headers=m.headers,
            json={'request_id': 'reviewed-director-pin', 'definition': definition})
        assert created.status_code == 201, created.text
        saved = created.json()
        path = base + '/graphs/' + saved['id']
        reopened = client.get(path, headers=m.headers)
        assert reopened.status_code == 200, reopened.text
        assert reopened.json() == saved
        assert saved['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
        assert saved['reference_states'][0]['state'] == 'CURRENT'
        duplicate = client.post(base + '/graphs', headers=m.headers,
            json={'request_id': 'reviewed-director-pin', 'definition': definition})
        assert duplicate.status_code == 201 and duplicate.json() == saved
        # Explicit authored position edit uses the original versioned Save.
        changed_definition = deepcopy(saved['definition'])
        changed_definition['nodes'][0]['position'] = {'x': 240, 'y': 160}
        edit = {'expected_version': saved['version'], 'definition': changed_definition}
        updated = client.put(path, headers=m.headers, json=edit)
        assert updated.status_code == 200, updated.text
        updated = updated.json()
        assert updated['version'] == saved['version'] + 1
        assert updated['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
        assert updated['execution_digest'] == saved['execution_digest']
        assert client.put(path, headers=m.headers, json=edit).status_code == 409
        assert client.get(path, headers=m.headers).json() == updated
        saved = updated
        assert e.documents.get(e.nid, e.scope, pin['id']) == source
        assert len(e.requests) == len(e.persistence.load_all()) == 1
        assert not e.raw.read(e.nid, e.scope)['collections'].get(graph.RUNS)
        run_path = None
        if execute_planning:
            flight = client.post(path + '/preflight', headers=m.headers,
                                 json={'expected_version': saved['version']})
            assert flight.status_code == 200, flight.text
            flight = flight.json()
            assert flight['executable'], flight['issues']
            run = client.post(path + '/runs', headers=m.headers, json={
                'expected_graph_version': saved['version'], 'request_id': 'explicit-planning-run',
                'reviewed_preflight_digest': flight['preflight_digest'],
                'target_node_ids': flight['target_node_ids']})
            assert run.status_code == 201, run.text
            run = run.json()
            run_path = base + '/graph-runs/' + run['id']
            executed = client.post(run_path + '/execute', headers=m.headers,
                                   json={'expected_version': run['version']})
            assert executed.status_code == 200, executed.text
            executed = executed.json()
            assert executed['status'] == 'SUCCEEDED' and executed['model_called'] is False
            assert len(e.requests) == len(e.persistence.load_all()) == 1
        # A fresh original owner reads persisted bytes, not an in-memory graph.
        documents = CreativeService(ExperimentalStore(e.root, 'file', ''),
                                    e.novels, e.documents.chapters)
        fresh_workspace = IndependentWorkspaceService(documents, assets, workspace.lineage)
        fresh_graph = CreativeGraphService(documents.store, fresh_workspace)
        assert fresh_graph.get(e.nid, e.scope, e.actor, saved['id']) == saved
        assert documents.get(e.nid, e.scope, pin['id']) == source
        # Rebind the captured app dependencies to freshly constructed File owners.
        # This is a fresh-owner HTTP read, not a claimed packaged-process restart.
        monkeypatch.setattr(workspace, 'creative', documents)
        monkeypatch.setattr(workspace, 'store', documents.store)
        monkeypatch.setattr(graph, 'store', documents.store)
        monkeypatch.setattr(graph, 'asset_inputs', GraphAssetInputs(graph))
        after_restart = client.get(path, headers=m.headers)
        assert after_restart.status_code == 200 and after_restart.json() == saved
        if run_path:
            restored_run = client.get(run_path, headers=m.headers)
            assert restored_run.status_code == 200, restored_run.text
            assert restored_run.json() == executed
        from test_v2_director_storyboard_production import production_input
        authored = production_input(source)
        authored['title'] = 'Later explicit Director edit'
        documents.update(e.nid, e.scope, e.actor, source['id'], source['version'], authored)
        stale = client.get(path, headers=m.headers)
        assert stale.status_code == 200, stale.text
        assert stale.json()['reference_states'][0]['state'] == 'STALE'
        assert stale.json()['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
        assert stale.json()['version'] == saved['version']
        assert len(e.requests) == len(e.persistence.load_all()) == 1
        assert len(e.raw.read(e.nid, e.scope)['collections'].get(graph.RUNS, {})) == int(execute_planning)
