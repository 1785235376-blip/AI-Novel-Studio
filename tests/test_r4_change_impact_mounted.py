"""U06 through both production API aliases and real legacy media composition."""
import pytest

from test_r3_mounted_contracts import mounted, prefix, checked, scoped


def test_change_impact_actual_composition_selects_one_refresh_and_preserves_original(mounted, monkeypatch):
    e = mounted; c = e.client; base = e.base
    # Original adapter + budget path is the registered production service; this
    # offline contract does not need model discovery. U06 preserves that mode.
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'change_impact_v2,temporal_story_graph_v2,world_character_engines_v2,asset_lineage_v2,media_adapter_registry,cover_storyboard_generation,production_manifest_v2')
    brief = checked(c.post(base + '/media/cover-briefs', json={'title': 'Synthetic source', 'chapter_ids': [e.chapter['id']]}), 201)
    task = checked(c.post(base + '/media/tasks', json={'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1', 'candidate_count': 1}), 201)
    task = checked(c.post(base + f"/media/tasks/{task['id']}/execute", json={'expected_version': 1}))
    e.chapters.save(e.chapter['id'], {'content': 'Changed synthetic chapter.'})
    response = c.get(base + '/change-impact/sources')
    assert response.headers['cache-control'] == 'no-store'
    assert any(r['id'] == e.chapter['id'] for r in checked(response)['items'])
    impact = checked(c.post(base + '/change-impact/query', json={'source': {'kind': 'CHAPTER', 'id': e.chapter['id']}}))
    selected = next(r for r in impact['items'] if r['kind'] == 'MEDIA_TASK')
    assert selected['stale'] and selected['refresh_candidate']
    preflight = checked(c.post(base + '/change-impact/preflights', json={'source': {'kind': 'CHAPTER', 'id': e.chapter['id']}, 'selected': [{'key': selected['key'], 'expected_version': selected['version']}]}), 201)
    assert preflight['ready']
    refreshed = checked(c.post(base + f"/change-impact/preflights/{preflight['id']}/prepare", json={'expected_version': 1, 'preflight_digest': preflight['preflight_digest'], 'idempotency_key': 'mounted'}), 201)['items'][0]
    assert c.post(base + f"/media/tasks/{refreshed['task_id']}/execute", json={'expected_version': 1}).status_code == 422
    completed = checked(c.post(base + f"/change-impact/refreshes/{refreshed['id']}/execute", json={'expected_task_version': 1}))
    assert completed['status'] == 'SUCCEEDED' and completed['outputs'][0]['status'] == 'PENDING_REVIEW'
    assert not e.assets.list(e.nid)
    assert e.experimental.media_service.get(e.nid, e.scope, e.experimental.media_service.TASKS, task['id'])['proposal_ids'] == task['proposal_ids']
    pid = completed['outputs'][0]['id']
    for mode in ('off', 'v1'):
        if mode == 'off': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'cover_storyboard_generation,media_adapter_registry')
        else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        assert c.get(base + '/change-impact/sources').status_code == 404
        assert c.post(base + f"/change-impact/refreshes/{refreshed['id']}/execute", json={'expected_task_version': completed['task_version']}).status_code == 404
        assert c.get(base + f'/media/proposals/{pid}/preview').status_code == 404
        assert c.post(base + f'/media/proposals/{pid}/approve', json={'expected_version': 999}).status_code == 404
        if mode == 'off':
            tasks = checked(c.get(base + '/media/tasks'))['items']
            assert [row['id'] for row in tasks] == [task['id']]
            assert refreshed['task_id'] not in c.get(base + '/media/cover-briefs').text


def test_change_impact_actual_reader_and_branch_authority(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    # This author-wide projection must not turn the reader's character view
    # into an omniscient graph, including an empty/count side channel.
    viewer_headers = {'X-Session-Token': e.viewer, 'X-Branch-Id': e.branch}
    assert e.client.get(e.base + '/change-impact/sources', headers=viewer_headers).status_code == 403
