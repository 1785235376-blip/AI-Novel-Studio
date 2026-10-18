"""Direct saved usages preserve original route admission and never dispatch."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_timeline_waveform_preview import durable_files, persist_audio, persist_visual, timeline, wav

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('mounted', ['file'], indirect=True)]
FLAGS = 'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2'


@pytest.fixture
def usages(client, monkeypatch):
    e = client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS)
    e.host = 'usage-' + uuid4().hex
    e.session = SessionContext('session-' + e.host, 'client-' + e.host, 'usage-author', 'usage-workspace')
    e.sessions.register(e.host, e.session)
    e.headers = {'X-Session-Token': e.host}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.graphs = e.experimental.creative_graph_service
    e.production = e.experimental.studio_production_service
    for owner in (e.graphs, e.graphs.asset_inputs, e.production, e.production.timeline_inputs):
        monkeypatch.setattr(owner, 'workspace', e.studio)
        monkeypatch.setattr(owner, 'store', e.studio.store)
    e.source = persist_audio(e.studio, e.nid, e.scope, wav([0] * 800))
    e.visual = persist_visual(e.studio, e.nid, e.scope)
    e.timeline = checked(e.client.post(e.studio_base + '/production/timelines', headers=e.headers,
        json={'expected_version': 0, 'title': 'Private consumer title', 'timeline': timeline(e.source, e.visual)}), 201)
    e.usage_base = e.prefix + f'/novels/{e.nid}/experimental/production/assets/'
    return e


def graph(e, schema=1, *, headers=None, nodes=1):
    source = e.visual if schema == 4 else e.source
    return checked(e.client.post(e.studio_base + '/graphs', headers=headers or e.headers, json={
        'request_id': uuid4().hex, 'expected_version': 0,
        'definition': {'schema_version': schema, 'title': 'Private graph title', 'nodes': [
            {'id': f'Pin{i:02}', 'definition_id': 'asset_reference', 'enabled': i != 1,
             'parameters': {'asset_id': source['id'], 'version': source['version'],
                 'digest': source['sha256'], 'kind': source['kind']}} for i in range(nodes)], 'edges': []}}), 201)


def get(e, owner, aid=None, headers=None):
    return e.client.get(e.usage_base + (aid or e.source['id']) + '/studio-' + owner + '-usages',
                        headers=e.headers if headers is None else headers)


def forbid(monkeypatch, e):
    def denied(*args, **kwargs):
        pytest.fail('Observation attempted a write, dispatch, or execution')
    import app.experimental.store as scope_store
    import app.creative.project_store as project_store
    monkeypatch.setattr(scope_store, 'atomic_write', denied)
    monkeypatch.setattr(project_store, 'atomic_write', denied)
    for owner, names in ((e.production, ('create', 'execute', 'timeline_save', 'timeline_render', 'review')),
                         (e.graphs, ('create', 'save', 'create_run')),
                         (e.studio.assets, ('create',))):
        for name in names:
            if hasattr(owner, name): monkeypatch.setattr(owner, name, denied)


@pytest.mark.parametrize('schema', [1, 2, 3, 4, 5])
def test_exact_graph_pin_and_timeline_clip_are_separate_read_only_views(usages, monkeypatch, schema):
    e = usages; saved = graph(e, schema, nodes=2); forbid(monkeypatch, e)
    before = durable_files(e.root)
    response = get(e, 'graph', e.visual['id'] if schema == 4 else None); result = checked(response)
    assert response.headers['cache-control'] == 'no-store'
    assert len(result['items']) == 2  # disabled saved references remain uses
    assert result['items'][0]['id'] == saved['id']
    assert result['items'][0]['digest'] == saved['definition_digest']
    assert result['items'][0]['node_id'] == 'Pin00'
    assert result['items'][0]['source'] == result['items'][0]['current_source'] == result['source']
    assert result['items'][0]['state'] == 'CURRENT'
    result = checked(get(e, 'timeline'))
    assert result['items'][0]['id'] == e.timeline['id']
    assert result['items'][0]['digest'] == e.timeline['timeline_digest']
    assert result['items'][0]['track_id'] == 'sound' and result['items'][0]['clip_id'] == 'measured'
    assert result['read_only'] and not result['automatic_regeneration'] and not result['truncated']
    assert result['other_dependencies'] == 'UNKNOWN'
    assert 'Private consumer title' not in str(result)
    assert durable_files(e.root) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
@pytest.mark.parametrize('change', ['missing', 'forged', 'origin', 'forwarded', 'revoke', 'feature', 'acceptance'])
def test_original_admission_denial_never_returns_partial_evidence(usages, monkeypatch, owner, change):
    e = usages; graph(e, 3)
    if change == 'missing': e.headers = {}
    elif change == 'forged': e.headers = {'X-Session-Token': 'forged-usage-host'}
    elif change == 'origin': e.headers['Origin'] = 'https://untrusted.invalid'
    elif change == 'forwarded': e.headers['Forwarded'] = 'for=127.0.0.1'
    elif change == 'revoke': e.sessions.revoke(e.host)
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'asset_lineage_v2')
    elif change == 'acceptance': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    before = durable_files(e.root); response = get(e, owner)
    assert response.status_code in {401, 403, 404}, response.text
    assert e.source['id'] not in response.text and e.timeline['id'] not in response.text
    assert 'items' not in response.json() and durable_files(e.root) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_actor_private_usage_is_not_an_empty_global_inventory(usages, owner):
    e = usages; graph(e, 1)
    private_graph = e.graphs.create(e.nid, e.scope, 'other-actor', {
        'request_id': uuid4().hex, 'expected_version': 0, 'definition': {
            'title': 'Another actor', 'nodes': [{'id': 'PrivatePin', 'definition_id': 'asset_reference',
                'parameters': {'asset_id': e.source['id'], 'version': 1, 'digest': e.source['sha256'], 'kind': 'audio'}}],
            'edges': []}})
    private_timeline = e.production.timeline_save(e.nid, e.scope, 'other-actor', None,
        {'expected_version': 0, 'title': 'Another actor', 'timeline': e.timeline['timeline']}, lambda: None)
    result = checked(get(e, owner))
    assert len(result['items']) == 1 and result['other_dependencies'] == 'UNKNOWN'
    assert private_graph['id'] not in str(result) and private_timeline['id'] not in str(result)



@pytest.mark.parametrize('owner', ['graph', 'timeline'])
@pytest.mark.parametrize('change', ['source-version', 'source-digest', 'revoke', 'aba'])
def test_mid_read_change_discards_every_row(usages, monkeypatch, owner, change):
    e = usages; graph(e, 1)
    target = e.graphs if owner == 'graph' else e.production
    name = 'list' if owner == 'graph' else 'timeline_list'
    original = getattr(target, name); calls = []
    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        if not calls:
            calls.append(True)
            if change.startswith('source-'):
                original_row = e.studio._row
                def changed(*args, **kwargs):
                    row = deepcopy(original_row(*args, **kwargs))
                    if row['id'] == e.source['id']:
                        if change == 'source-version': row['version'] += 1
                        else: row['sha256'] = '0' * 64
                    return row
                monkeypatch.setattr(e.studio, '_row', changed)
            else:
                e.sessions.revoke(e.host)
                if change == 'aba': e.sessions.register(e.host, e.session)
        return result
    monkeypatch.setattr(target, name, altered)
    before = durable_files(e.root); response = get(e, owner)
    assert response.status_code in {401, 403, 409}, response.text
    assert 'items' not in response.json() and e.source['id'] not in response.text
    assert durable_files(e.root) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_authorized_source_drift_retains_exact_old_pin(usages, monkeypatch, owner):
    e = usages; graph(e, 1)
    original = e.studio._row
    def newer(*args, **kwargs):
        row = deepcopy(original(*args, **kwargs))
        if row['id'] == e.source['id']: row['version'] += 1
        return row
    monkeypatch.setattr(e.studio, '_row', newer)
    result = checked(get(e, owner))
    assert result['items'][0]['state'] == 'STALE'
    assert result['items'][0]['source']['version'] == 1
    assert result['items'][0]['current_source']['version'] == 2


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_unavailable_source_is_not_zero_coverage(usages, owner):
    e = usages; before = durable_files(e.root)
    response = get(e, owner, 'unavailable-private-sentinel')
    assert response.status_code in {404, 409}
    assert 'unavailable-private-sentinel' not in response.text
    assert 'items' not in response.json() and durable_files(e.root) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_missing_or_replaced_incarnation_never_adopts_or_provisions(usages, owner):
    import json
    e = usages; graph(e, 1)
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    marker.unlink()  # Only the owned temporary fixture identity.
    before = durable_files(e.root)
    response = get(e, owner)
    assert response.status_code in {404, 409} and not marker.exists()
    assert durable_files(e.root) == before
    marker.write_text(json.dumps({'schema_version': 1, 'project_incarnation': str(uuid4())}))
    before = durable_files(e.root); response = get(e, owner)
    assert response.status_code in {404, 409}
    assert e.source['id'] not in response.text and e.timeline['id'] not in response.text
    assert durable_files(e.root) == before


@pytest.mark.parametrize('schema', ['legacy', 'audio'])
def test_original_timeline_schema_compatibility(usages, schema):
    e = usages
    pin = deepcopy(e.timeline['timeline']['tracks'][0]['clips'][0]['source_snapshot'])
    value = {'duration_ms': 1000, 'tracks': [{'id': 'voice', 'kind': 'AUDIO', 'order': 0,
        'clips': [{'id': 'clip', 'source_snapshot': pin, 'start_ms': 0, 'in_ms': 0, 'out_ms': 100}]}]}
    if schema == 'audio': value.update(schema_version=3, media_kind='AUDIO')
    else:
        import base64
        # Opaque original-owner bytes for metadata-only compatibility; never
        # claim this sentinel is playable media and never render/probe it.
        with e.studio._asset_scope(e.nid, e.scope):
            video = e.studio.assets.create(e.nid, 'metadata-fixture.mp4',
                base64.b64encode(b'synthetic metadata-only video fixture').decode(),
                'video/mp4', 'video', 'legacy-usage-fixture', branch_id=e.scope.get('branch_id'),
                required_features=('narrative_production_v2',))
        value['tracks'].append({'id': 'video', 'kind': 'VIDEO', 'order': 1, 'clips': [
            {'id': 'still', 'source_snapshot': {**pin, 'id': video['id'], 'asset_kind': 'video', 'digest': video['sha256']},
             'start_ms': 0, 'in_ms': 0, 'out_ms': 100}]})
    saved = checked(e.client.post(e.studio_base + '/production/timelines', headers=e.headers,
        json={'expected_version': 0, 'title': 'Schema fixture', 'timeline': value}), 201)
    before = durable_files(e.root); rows = checked(get(e, 'timeline'))['items']
    actual = next(row for row in rows if row['id'] == saved['id'])
    assert actual['digest'] == saved['timeline_digest'] and actual['clip_id'] == 'clip'
    assert durable_files(e.root) == before


def test_result_limit_is_deterministic_and_explicit(usages, monkeypatch):
    e = usages
    for _ in range(13): graph(e, 1, nodes=16)
    forbid(monkeypatch, e); before = durable_files(e.root)
    first = checked(get(e, 'graph')); second = checked(get(e, 'graph'))
    assert first == second and len(first['items']) == 200 and first['truncated']
    assert first['other_dependencies'] == 'UNKNOWN' and durable_files(e.root) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_corrupt_original_consumer_has_no_partial_projection(usages, owner):
    e = usages; saved = graph(e, 1)
    with e.studio.store.transaction(e.nid, e.scope) as state:
        if owner == 'graph':
            state['collections'][e.graphs.GRAPHS][saved['id']]['definition_digest'] = 'private-corrupt-sentinel'
        else:
            state['collections']['creative_production_timelines_v2'][e.timeline['id']]['timeline_digest'] = 'private-corrupt-sentinel'
    before = durable_files(e.root); response = get(e, owner)
    assert response.status_code in {409, 422} and 'items' not in response.json()
    assert 'private-corrupt-sentinel' not in response.text and e.source['id'] not in response.text
    assert durable_files(e.root) == before


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_consumer_change_during_second_read_discards_projection(usages, monkeypatch, owner):
    e = usages; saved = graph(e, 1)
    target = e.graphs if owner == 'graph' else e.production
    name = 'get' if owner == 'graph' else 'timeline_get'
    original = getattr(target, name); calls = []
    def changed(*args, **kwargs):
        value = deepcopy(original(*args, **kwargs)); calls.append(True)
        if len(calls) == 2:
            value['version'] += 1
        return value
    monkeypatch.setattr(target, name, changed)
    response = get(e, owner)
    assert response.status_code == 409 and 'items' not in response.json()
    assert saved['id'] not in response.text and e.timeline['id'] not in response.text


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_owner_scan_limit_never_claims_complete_coverage(usages, monkeypatch, owner):
    e = usages; graph(e, 1)
    target = e.graphs if owner == 'graph' else e.production
    name = 'list' if owner == 'graph' else 'timeline_list'
    original = getattr(target, name)
    def overflow(*args, **kwargs):
        value = original(*args, **kwargs)
        return {'items': value['items'] * 26}
    monkeypatch.setattr(target, name, overflow)
    response = get(e, owner)
    assert response.status_code == 409 and 'items' not in response.json()
    assert e.source['id'] not in response.text


def test_empty_owner_result_retains_authorized_exact_source(usages):
    e = usages
    result = checked(get(e, 'graph'))
    assert result['items'] == []
    assert result['source'] == {'kind': 'ASSET', 'id': e.source['id'], 'version': e.source['version'],
        'digest': e.source['sha256'], 'asset_kind': 'audio'}


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_owner_discovery_identity_mismatch_fails_closed(usages, monkeypatch, owner):
    e = usages; graph(e, 1)
    target = e.graphs if owner == 'graph' else e.production
    name = 'list' if owner == 'graph' else 'timeline_list'
    original = getattr(target, name)
    def wrong_identity(*args, **kwargs):
        value = deepcopy(original(*args, **kwargs))
        value['items'][0]['id'] = 'private-mismatched-id'
        return value
    monkeypatch.setattr(target, name, wrong_identity)
    response = get(e, owner)
    assert response.status_code == 409 and 'private-mismatched-id' not in response.text
    assert 'items' not in response.json()


@pytest.mark.parametrize('owner', ['graph', 'timeline'])
def test_original_source_permission_loss_on_final_read_clears_everything(usages, monkeypatch, owner):
    e = usages; graph(e, 1)
    target = e.graphs if owner == 'graph' else e.production
    name = 'list' if owner == 'graph' else 'timeline_list'
    original = getattr(target, name); calls = []
    def unavailable(*args, **kwargs):
        result = original(*args, **kwargs); calls.append(True)
        if len(calls) == 2:
            def denied(*args, **kwargs): raise FileNotFoundError('private-permission-sentinel')
            monkeypatch.setattr(e.studio, '_row', denied)
        return result
    monkeypatch.setattr(target, name, unavailable)
    response = get(e, owner)
    assert response.status_code == 409 and 'items' not in response.json()
    assert 'private-permission-sentinel' not in response.text and e.source['id'] not in response.text
