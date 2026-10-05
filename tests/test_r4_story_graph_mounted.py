"""A04/A05 mounted production routes, real authorization and File/PG stores."""
import copy
import json

import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def graph_app(mounted, monkeypatch):
    e = mounted
    for key, value in (('store', e.store), ('novels', e.novels), ('chapters', e.chapters)):
        monkeypatch.setattr(e.experimental.story_graph_service, key, value)
    return e


def relation(e):
    return checked(e.client.post(e.base + '/story-graph/records', json={
        'kind': 'STORY_RELATION', 'title': 'Synthetic secret', 'chapter_id': e.chapter['id'],
        'data': {'subject': {'kind': 'CHARACTER', 'id': 'alice'}, 'object': {'kind': 'LOCATION', 'id': 'city'},
                 'relation': 'ABOUT', 'layer': 'WORLD_FACT', 'statement': 'Only Alice knows the silver password.'}}), 201)


def approve(e, row):
    return checked(e.client.post(e.base + f"/story-graph/records/{row['id']}/approve", json={'expected_version': row['version']}))


def test_mounted_graph_flags_dependencies_and_acceptance(graph_app, monkeypatch):
    e = graph_app
    for flags, acceptance in [('', 'false'), ('*', 'false'), ('temporal_story_graph_v2', 'false'),
            ('temporal_story_graph_v2,character_mind_v2,world_character_engines_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags)
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        assert e.client.get(e.base + '/story-graph/records').status_code == 404
        assert e.client.get(e.base + '/story-graph/query', params={'chapter_id': e.chapter['id']}).status_code == 404
        assert e.client.post(e.base + '/story-graph/character-context', json={'chapter_id': e.chapter['id'], 'character_id': 'alice'}).status_code == 404


def test_mounted_graph_explicit_review_knowledge_and_atomic_revocation(graph_app):
    e = graph_app; original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    r = approve(e, relation(e))
    body = {'chapter_id': e.chapter['id'], 'character_id': 'alice'}
    context = lambda: checked(e.client.post(e.base + '/story-graph/character-context', json=body))
    assert not context()['secrets']
    event = checked(e.client.post(e.base + '/story-graph/records', json={'kind': 'KNOWLEDGE_EVENT', 'title': 'Alice learns',
        'chapter_id': e.chapter['id'], 'data': {'character_id': 'alice', 'operation': 'LEARN', 'category': 'SECRET', 'relation_id': r['id']}}), 201)
    assert not context()['secrets']
    event = approve(e, event)
    assert context()['secrets'][0]['text'] == r['data']['statement']
    # Older world endpoints and inbox do not become a flag bypass.
    assert e.client.get(e.base + f"/world/records/{r['id']}").status_code == 404
    assert not checked(e.client.get(e.base + '/world/records'))['items']
    assert r['id'] not in json.dumps(checked(e.client.get(e.base + '/review-inbox')))
    checked(e.client.post(e.base + f"/story-graph/records/{event['id']}/archive", json={'expected_version': event['version']}))
    assert not context()['secrets']
    assert e.chapters.get(e.chapter['id']) == original


def test_mounted_graph_real_membership_revocation_and_branch_fail_closed(graph_app, monkeypatch):
    e = scoped(graph_app, monkeypatch)
    assert e.client.get(e.base + '/story-graph/catalog', headers=e.viewer_headers).status_code == 403
    params = {'chapter_id': e.chapter['id'], 'character_id': 'alice'}
    assert e.client.get(e.base + '/story-graph/query', headers=e.headers, params=params).status_code == 422
    assert e.client.get(e.base + '/story-graph/records', headers=e.headers).status_code == 200
    e.authorization.revoke_role(e.role, e.lead)
    for path in ('/story-graph/records', '/story-graph/catalog'):
        assert e.client.get(e.base + path, headers=e.headers).status_code == 403
    assert e.client.get(e.base + '/story-graph/query', headers=e.headers, params=params).status_code == 403


def test_mounted_graph_current_manuscript_invalidates_relation_and_evidence(graph_app):
    e = graph_app; r = approve(e, relation(e))
    event = checked(e.client.post(e.base + '/story-graph/records', json={'kind': 'KNOWLEDGE_EVENT', 'title': 'Knowledge',
        'chapter_id': e.chapter['id'], 'data': {'character_id': 'alice', 'operation': 'LEARN', 'category': 'KNOWN_FACT', 'relation_id': r['id']}}), 201)
    approve(e, event)
    before = e.chapters.get(e.chapter['id'])
    e.chapters.save(before['id'], {'content': 'The actual evidence changed.', 'version': before['version']})
    body = {'chapter_id': e.chapter['id'], 'character_id': 'alice'}
    assert not checked(e.client.post(e.base + '/story-graph/character-context', json=body))['known_facts']
    assert checked(e.client.get(e.base + f"/story-graph/records/{r['id']}"))['stale']


def test_mounted_character_preview_and_actual_local_adapter_have_identical_safe_payload(graph_app, monkeypatch):
    import time
    from types import SimpleNamespace as S
    import app.jobs as jobs_module
    import app.experimental.author_context_api as author_api
    from app.author_request import request_payload
    from app.model_runtime import TextModelNode
    from app.router import Route
    from app.services.generation_service import GenerationService
    from test_local_ai_discovery_egress import enabled
    e = graph_app; secret = 'HIDDEN_IN_MANUSCRIPT_紫色钥匙'
    current = e.chapters.get(e.chapter['id'])
    e.chapters.save(current['id'], {'content': secret, 'version': current['version']})
    current = e.chapters.get(current['id'])
    r = approve(e, relation(e))
    _, registered, candidate, adapter, wire = enabled(e.root / 'character-wire')
    captured = []; original_generate = adapter.generate_text
    def capture(request):
        captured.append(copy.deepcopy(request_payload(request)))
        return original_generate(request)
    monkeypatch.setattr(adapter, 'generate_text', capture)
    manager = e.api.jobs
    def forbidden(*_): pytest.fail('Must not discover omniscient author context')
    for key, value in (('chapters', e.chapters), ('contexts', S(novels=e.novels, for_chapter=forbidden, save_snapshot=lambda *_args, **_kwargs: None)),
                       ('persistence', GenerationService(e.bundle.generations)), ('snapshot_required', False), ('jobs', {})):
        monkeypatch.setattr(manager, key, value)
    route = Route(candidate['provider_id'], candidate['id'])
    runtime = S(is_remote_text_provider=lambda _: False, router=lambda *_: S(routes={'writer': [route]}),
                packaged_author_route_ready=lambda _: True,
                prepare_text_route=lambda *_: TextModelNode(registered.provider_registry, registered.model_registry))
    monkeypatch.setattr(jobs_module, 'runtime', runtime); monkeypatch.setattr(author_api, 'runtime', runtime)
    monkeypatch.setattr(jobs_module, 'runtime_log', S(write=lambda **_: None))
    monkeypatch.setattr(jobs_module, 'deterministic_review', lambda *_: [])
    body = {'novel_id': e.nid, 'chapter_id': current['id'], 'chapter_version': current['version'], 'operation': 'continue',
        'character_id': 'alice', 'provider_id': candidate['provider_id'], 'model_id': candidate['id'],
        'instruction': 'Stay within the selected fictional viewpoint.', 'source': secret, 'style': secret,
        'style_profile_id': 'do-not-fetch-style', 'plot_plan_id': 'do-not-fetch-plan'}
    preview = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert secret not in json.dumps(preview, ensure_ascii=False)
    assert r['data']['statement'] not in json.dumps(preview)
    assert preview['source_strategy'] == 'CHARACTER_KNOWLEDGE_ONLY' and not wire.calls
    result = checked(e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': preview['preview_digest']}), 202)
    for _ in range(200):
        value = manager.get(result['job_id'])
        if value.status in manager.terminal: break
        time.sleep(.01)
    assert value.status == 'COMPLETED', value.error
    assert captured == [preview['request']]
    assert wire.generations[0][2]['prompt'] == preview['request']['prompt']
    stored = manager.persistence.get(value.id)
    assert stored['character_viewpoint'] == preview['character_viewpoint']
    assert stored['source'] == stored['style'] == '' and stored['creation_records'] == []
    assert not set(stored) & {'request_authorization', 'character_context_resolver', 'before_dispatch', 'on_terminal'}
    assert e.chapters.get(current['id']) == current
