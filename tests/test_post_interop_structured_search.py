"""Mounted original-owner search contracts, File + opted-in PostgreSQL."""
import copy
import json

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.experimental.store import ExperimentalStore
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_r4_mounted_workspaces import workspace


def search(e, kind, headers=None, **params):
    return checked(e.client.get(e.base + '/workspace/search', headers=headers or {}, params={'kind': kind, **params}))


def target(row):
    return {key: row[key] for key in ('kind', 'id', 'novel_id', 'branch_id', 'revision', 'offset')}


def create_world(e, kind='CIVILIZATION', headers=None, title='合成组织'):
    return checked(e.client.post(e.base + '/world/records', headers=headers or {}, json={
        'kind': kind, 'title': title, 'data': {'name': title, **({'principles': ['PRIVATE_ORGANIZATION_BODY']} if kind == 'CIVILIZATION' else {'description': 'PRIVATE_ABILITY_BODY'})}}), 201)


def test_all_original_owner_search_types_exact_navigation_and_safe_projection(workspace):
    e = workspace
    organization = create_world(e)
    ability = create_world(e, 'ABILITY', title='合成能力')
    graph = checked(e.client.post(e.base + '/story-graph/records', json={'kind': 'STORY_CONCEPT',
        'title': '合成物件', 'chapter_id': e.chapter['id'], 'data': {'concept_type': 'OBJECT', 'description': 'PRIVATE_GRAPH_BODY'}}), 201)
    evidence = checked(e.client.post(e.prefix + f'/novels/{e.nid}/lore/evidence', json={'source_id': 'structured-search-fixture', 'excerpt': 'PRIVATE_RULE_EVIDENCE'}), 201)
    e.lore_cleanup['evidence'].append(evidence['id'])
    rule = checked(e.client.post(e.prefix + f'/novels/{e.nid}/world-rules', json={'payload': {'statement': '合成规则需要代价', 'forbidden_terms': ['PRIVATE_RULE_PATTERN']}, 'relations': [{'evidence_id': evidence['id'], 'relevance': 'PRIMARY'}]}), 201)
    e.lore_cleanup['proposals'].append(rule['id'])
    asset = e.assets.create(e.nid, '合成素材.txt', 'U1lOVEhFVElD', 'text/plain', 'file')
    e.sessions.register('structured-owner', SessionContext('structured-session', 'structured-client', 'local-author', 'local-workspace'))
    headers = {'X-Session-Token': 'structured-owner'}
    workflow = checked(e.client.post(e.prefix + '/workflows', headers=headers, json={'novel_id': e.nid, 'title': '合成流程',
        'description': 'PRIVATE_WORKFLOW_BODY', 'nodes': [{'id': 'gate', 'type': 'manual_approval', 'name': 'Review', 'config': {}}], 'edges': []}), 201)
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    expected = [('organization', organization['id'], 'world_record', organization['id']),
        ('rule', ability['id'], 'world_record', ability['id']), ('rule', 'legacy:' + rule['id'], 'world_rule', rule['id']),
        ('story_graph', graph['id'], 'graph_record', graph['id']), ('asset', asset['id'], 'asset_record', asset['id']),
        ('workflow', workflow['id'], 'workflow_definition', workflow['id'])]
    for kind, indexed_id, authority, original_id in expected:
        rows = search(e, kind, headers, q='合成')
        row = next(item for item in rows['items'] if item['id'] == indexed_id)
        assert 'PRIVATE_' not in json.dumps(rows)
        resolved = checked(e.client.post(e.base + '/workspace/search/resolve', headers=headers, json=target(row)))
        assert resolved['task_authority'] == authority and resolved['id'] == original_id
        assert resolved['novel_id'] == e.nid and resolved['branch_id'] is None
        assert row['snippet'] == ''
        assert not search(e, kind, headers, q='PRIVATE_')['items']
    assert search(e, 'rule', headers, q='需要代价')['items'][0]['title'] == '合成规则需要代价'
    assert search(e, 'organization', headers, fulltext='true')['items']
    assert not search(e, 'organization', headers, q='PRIVATE_ORGANIZATION_BODY', fulltext='true')['items']
    assert e.store.read(e.nid, e.scope) == before
    e.sessions.register('structured-other-owner', SessionContext('other-session', 'other-client', 'other-author', 'local-workspace'))
    assert not search(e, 'workflow', {'X-Session-Token': 'structured-other-owner'})['items']
    # Reopening the persisted original authority does not need another search DB.
    restarted = ExperimentalStore(e.root, e.backend, e.url)
    assert restarted.read(e.nid, e.scope) == before


def test_source_digest_detects_nonindexed_body_edits_archive_and_flags(workspace, monkeypatch):
    e = workspace
    row = create_world(e)
    old = target(search(e, 'organization')['items'][0])
    updated = checked(e.client.put(e.base + '/world/records/' + row['id'], json={
        'kind': 'CIVILIZATION', 'title': row['title'], 'data': {'name': row['title'], 'principles': ['CHANGED_PRIVATE_BODY']}, 'expected_version': row['version']}))
    assert e.client.post(e.base + '/workspace/search/resolve', json=old).status_code == 409
    current = checked(e.client.post(e.base + '/workspace/search/resolve', json={**old, 'open_current': True}))
    assert current['id'] == row['id'] and current['stale']
    checked(e.client.post(e.base + f"/world/records/{row['id']}/archive", json={'expected_version': updated['version']}))
    assert not search(e, 'organization')['items']
    assert e.client.post(e.base + '/workspace/search/resolve', json={**old, 'open_current': True}).status_code == 404
    create_world(e, title='Flag private title')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    assert not search(e, 'organization')['items']
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert e.client.get(e.base + '/workspace/search', params={'kind': 'organization'}).status_code == 404


def test_scoped_structured_sources_do_not_borrow_local_or_foreign_branch_authority(workspace, monkeypatch):
    e = workspace
    local = create_world(e, title='PRIVATE_LOCAL_ORG')
    e = scoped(e, monkeypatch)
    row = create_world(e, headers=e.headers, title='可读分支组织')
    rows = search(e, 'organization', e.viewer_headers)['items']
    assert [item['id'] for item in rows] == [row['id']]
    assert local['id'] not in json.dumps(rows)
    # Author graph records require write authority even if search itself is read-only.
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections']['world_records']['graph-hidden'] = {**row, 'id': 'graph-hidden', 'kind': 'STORY_CONCEPT', 'title': 'PRIVATE_AUTHOR_GRAPH', 'data': {'concept_type': 'SECRET', 'description': 'PRIVATE_CONTENT'}}
    assert not search(e, 'story_graph', e.viewer_headers)['items']
    assert [item['id'] for item in search(e, 'story_graph', e.headers)['items']] == ['graph-hidden']
    assert e.client.get(e.base + '/workspace/search', params={'kind': 'organization'}, headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code == 403
    old = target(rows[0])
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(e.base + '/workspace/search/resolve', headers=e.headers, json=old).status_code == 403


def test_hidden_source_titles_and_payload_never_enter_results_or_warm_cache(workspace):
    e = workspace
    row = create_world(e)
    old = target(search(e, 'organization')['items'][0])
    with e.store.transaction(e.nid, e.scope) as state:
        source = state['collections']['world_records'][row['id']]
        source.update(visibility='PRIVATE', title='PRIVATE_HIDDEN_NAME', aliases=['PRIVATE_ALIAS'])
    result = search(e, 'organization')
    assert result['items'] == [] and 'PRIVATE_' not in json.dumps(result)
    assert e.client.post(e.base + '/workspace/search/resolve', json={**old, 'open_current': True}).status_code == 404
    assert 'PRIVATE_' not in json.dumps(e.experimental.workspace_tools_service._indexes)


def test_asset_branch_reader_matches_original_owner_and_deleted_assets_disappear(workspace, monkeypatch):
    e = workspace
    local = e.assets.create(e.nid, 'PRIVATE_LOCAL_ASSET.txt', 'U1lOVEhFVElD', 'text/plain', 'file')
    e = scoped(e, monkeypatch)
    current = e.assets.create(e.nid, '当前分支素材.txt', 'U1lOVEhFVElD', 'text/plain', 'file', branch_id=e.branch)
    foreign = e.assets.create(e.nid, 'PRIVATE_OTHER_BRANCH_ASSET.txt', 'U1lOVEhFVElD', 'text/plain', 'file', branch_id=e.other_branch)
    # Asset authority requires BOTH project and branch grants. A search grant
    # on the branch alone must not silently bypass its stronger original owner.
    assert not search(e, 'asset', e.viewer_headers)['items']
    project_scope = AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid)
    e.authorization.assign_permission(PermissionAssignment('asset-project-read-' + e.nid, e.viewer, 'domain.read', ModalityDomain.NOVEL, project_scope, e.lead))
    e.authorization.assign_permission(PermissionAssignment('asset-project-write-' + e.nid, e.lead, 'domain.write', ModalityDomain.NOVEL, project_scope, e.lead))
    e.authorization.assign_permission(PermissionAssignment('asset-owner-read-' + e.nid, e.lead, 'domain.read', ModalityDomain.NOVEL, project_scope, e.lead))
    rows = search(e, 'asset', e.viewer_headers)['items']
    assert [row['id'] for row in rows] == [current['id']]
    assert local['id'] not in json.dumps(rows) and foreign['id'] not in json.dumps(rows)
    old = target(rows[0])
    deleted = e.client.delete(e.prefix + f"/assets/{current['id']}", params={'novel_id': e.nid}, headers=e.headers)
    assert deleted.status_code in {200, 204}, deleted.text
    assert not search(e, 'asset', e.headers)['items']
    assert e.client.post(e.base + '/workspace/search/resolve', headers=e.headers, json=old).status_code == 404
