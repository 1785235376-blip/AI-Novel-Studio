"""Explicit real-PostgreSQL parity; never relabel the File-only suite.

Original mounted fixtures own unique project IDs and clean their own rows.
Assets remain in their original scoped filesystem owner on both backends.
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_studio_asset_usages_api import usages, graph, get, forbid
from test_v2_timeline_waveform_preview import durable_files, persist_audio, wav

pytestmark = [pytest.mark.postgres_backend_only,
              pytest.mark.parametrize('mounted', ['postgres'], indirect=True)]


def state(e):
    assert e.backend == 'postgres' and e.store.backend == 'postgres'
    with e.store._connect() as connection:
        database = connection.execute('SELECT current_database(), current_setting(\'server_encoding\')').fetchone()
        scopes = connection.execute('''SELECT scope_key, document, revision, updated_at, xmin::text
            FROM experimental_scope_documents WHERE novel_id = %s ORDER BY scope_key''', (e.nid,)).fetchall()
        owner = connection.execute('SELECT id, xmin::text FROM novels WHERE slug = %s', (e.nid,)).fetchone()
    assert database[0].startswith('v2_') and database[1] == 'UTF8'
    assert scopes and owner
    return deepcopy((database, scopes, owner, durable_files(e.root)))


@pytest.mark.parametrize('schema', [1, 2, 3, 4, 5])
def test_real_postgres_exact_reads_preserve_sql_revisions_and_files(usages, monkeypatch, schema):
    e = usages; saved = graph(e, schema, nodes=2)
    selected = e.visual if schema == 4 else e.source
    forbid(monkeypatch, e)
    before = state(e)
    graph_result = checked(get(e, 'graph', selected['id']))
    timeline_result = checked(get(e, 'timeline', selected['id']))
    expected = {'kind': 'ASSET', 'id': selected['id'], 'version': selected['version'],
                'digest': selected['sha256'], 'asset_kind': selected['kind']}
    assert graph_result['source'] == timeline_result['source'] == expected
    assert len(graph_result['items']) == 2
    assert {row['node_id'] for row in graph_result['items']} == {'Pin00', 'Pin01'}
    for row in graph_result['items']:
        assert row['id'] == saved['id'] and row['version'] == saved['version']
        assert row['digest'] == saved['definition_digest']
        assert row['source'] == row['current_source'] == expected and row['state'] == 'CURRENT'
    assert len(timeline_result['items']) == 1
    row = timeline_result['items'][0]
    assert row['id'] == e.timeline['id'] and row['version'] == e.timeline['version']
    assert row['digest'] == e.timeline['timeline_digest']
    assert row['clip_id'] == ('still' if schema == 4 else 'measured')
    assert row['source'] == row['current_source'] == expected
    assert state(e) == before  # SQL document/revision/time/xmin and original files.


def test_real_postgres_private_original_owner_rows_are_not_enumerated(usages, monkeypatch):
    e = usages; own = graph(e, 3)
    private_graph = e.graphs.create(e.nid, e.scope, 'private-other-actor', {
        'request_id': uuid4().hex, 'expected_version': 0, 'definition': {
            'title': 'Private unrelated owner', 'nodes': [{'id': 'PrivatePin', 'definition_id': 'asset_reference',
                'parameters': {'asset_id': e.source['id'], 'version': 1, 'digest': e.source['sha256'], 'kind': 'audio'}}],
            'edges': []}})
    private_timeline = e.production.timeline_save(e.nid, e.scope, 'private-other-actor', None,
        {'expected_version': 0, 'title': 'Private unrelated owner', 'timeline': e.timeline['timeline']}, lambda: None)
    forbid(monkeypatch, e); before = state(e)
    graph_result = checked(get(e, 'graph')); timeline_result = checked(get(e, 'timeline'))
    assert [row['id'] for row in graph_result['items']] == [own['id']]
    assert [row['id'] for row in timeline_result['items']] == [e.timeline['id']]
    for result in (graph_result, timeline_result):
        assert private_graph['id'] not in str(result) and private_timeline['id'] not in str(result)
        assert result['other_dependencies'] == 'UNKNOWN'
    assert state(e) == before


def test_real_postgres_reused_slug_keeps_new_uuid_separate(usages, monkeypatch):
    e = usages; old_graph = graph(e, 3); old_source = e.source['id']; old_timeline = e.timeline['id']
    old_identity = e.studio.store.incarnation(e.nid)
    e.novels.delete(e.nid)
    recreated = e.novels.create({'id': e.nid, 'title': 'Recreated synthetic usages owner'})
    assert recreated['id'] == e.nid
    assert e.studio.store.incarnation(e.nid) != old_identity
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.source = persist_audio(e.studio, e.nid, e.scope, wav([0] * 800), key='new-incarnation-source')
    before = state(e)
    for owner in ('graph', 'timeline'):
        denied = get(e, owner, old_source)
        assert denied.status_code in {404, 409}
        assert old_source not in denied.text and old_graph['id'] not in denied.text and old_timeline not in denied.text
        empty = checked(get(e, owner))
        assert empty['items'] == [] and empty['source']['id'] == e.source['id']
        assert empty['other_dependencies'] == 'UNKNOWN'
    assert state(e) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_real_postgres_mid_read_revocation_returns_no_partial_evidence(usages, monkeypatch, owner):
    e = usages; graph(e, 3)
    target = e.graphs if owner == 'graph' else e.production
    name = 'list' if owner == 'graph' else 'timeline_list'
    original = getattr(target, name)
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.host)
        return result
    monkeypatch.setattr(target, name, revoked)
    before = state(e); response = get(e, owner)
    assert response.status_code in {401, 403}
    assert 'items' not in response.json() and e.source['id'] not in response.text
    assert state(e) == before
