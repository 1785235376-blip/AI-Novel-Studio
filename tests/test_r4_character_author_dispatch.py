"""Main JobManager + production local adapter serialization, synthetic wire only.

The graph is durable File/real PG. No model server, paid API, or external network
is called. These tests require the character branch in the shared coordinator.
"""
import copy
import json
from types import SimpleNamespace as S

import pytest

from app.author_request import request_payload
from app.experimental.character_author_context import configure_character_job
from app.jobs import JobManager
from app.model_runtime import TextModelNode
from app.router import Route
from test_local_ai_discovery_egress import enabled
from test_r3_planning import planning_env
from test_r4_story_graph import env, relation, learn
from test_r4_character_author_context import binding


@pytest.fixture
def dispatch(binding, tmp_path, monkeypatch):
    import app.jobs as jobs_module
    e = binding
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'world_character_engines_v2,temporal_story_graph_v2,character_mind_v2,author_context_inspector_v2')
    _, registered, candidate, adapter, wire = enabled(tmp_path / 'synthetic-local-adapter')
    e.candidate, e.wire, e.adapter_requests = candidate, wire, []
    original = adapter.generate_text
    def capture(request):
        e.adapter_requests.append(copy.deepcopy(request_payload(request)))
        return original(request)
    monkeypatch.setattr(adapter, 'generate_text', capture)
    manager = JobManager.__new__(JobManager)
    manager.chapters = e.chapter_service
    def omniscient(*_): pytest.fail('Character mode must not even build the omniscient source context')
    manager.contexts = S(for_chapter=omniscient, save_snapshot=lambda *_args, **_kwargs: None, novels=e.novels)
    manager.snapshot_required = False
    manager._emit = lambda job, chunk='': setattr(job, 'output', job.output + chunk)
    manager._persist = lambda _: None
    route = Route(candidate['provider_id'], candidate['id'])
    e.route = route; e.manager = manager
    runtime = S(is_remote_text_provider=lambda _: False, router=lambda *_: S(routes={'writer': [route], 'plot_planner': [route]}),
        packaged_author_route_ready=lambda _: True,
        prepare_text_route=lambda *_: TextModelNode(registered.provider_registry, registered.model_registry))
    monkeypatch.setattr(jobs_module, 'runtime', runtime)
    monkeypatch.setattr(jobs_module, 'runtime_log', S(write=lambda **_: None))
    monkeypatch.setattr(jobs_module, 'deterministic_review', lambda *_: [])
    return e


def prepared(e, secret):
    e.chapters[e.order[3]]['content'] = 'Narrator-only chapter tail: ' + secret
    value = e.manager.prepare_job('continue', {'novel_id': e.nid, 'chapter_id': e.order[3],
        'instruction': e.ctx.user_instruction + '\nDerived approved plan: ' + secret,
        'source': secret, 'style': secret, 'profile': 'LOCAL_ONLY',
        'creation_records': [{'id': 'private-derived-plan', 'text': secret}],
        'provider_id': e.candidate['provider_id'], 'model_id': e.candidate['id']})
    configure_character_job(value, e.ctx, 'alice', e.order[3], authorize=e.authorize)
    return value


def test_actual_adapter_excludes_unknown_secret_from_all_automatic_sources(dispatch):
    e = dispatch; secret = 'ONLY_THE_VILLAIN_KNOWS_紫色铜钥'
    r = relation(e, secret); learn(e, r, character='bob')
    value = prepared(e, secret)
    _, _, preview = e.manager.prepare_author_request(value, e.route)
    assert e.wire.calls == []
    e.manager._run(value)
    assert value.status == 'COMPLETED', value.error
    assert e.adapter_requests == [request_payload(preview)]
    assert len(e.wire.generations) == 1
    serialized = json.dumps({'adapter': e.adapter_requests, 'wire': e.wire.generations}, ensure_ascii=False)
    assert secret not in serialized
    assert r['id'] not in serialized
    assert e.wire.generations[0][2]['prompt'] == preview.prompt
    assert e.ctx.user_instruction in preview.prompt
    assert '\nSOURCE:\n' not in preview.prompt
    assert set(preview.context) == {'character_viewpoint'}


def test_actual_adapter_only_includes_secret_after_explicit_learn_and_new_preview(dispatch):
    e = dispatch; secret = 'REVIEWED_SECRET_玻璃门'; r = relation(e, secret)
    value = prepared(e, secret)
    learn(e, r)
    e.manager._run(value)
    assert value.status == 'FAILED' and not e.wire.generations
    fresh = prepared(e, secret)
    _, _, preview = e.manager.prepare_author_request(fresh, e.route)
    e.manager._run(fresh)
    assert fresh.status == 'COMPLETED', fresh.error
    assert secret in e.wire.generations[-1][2]['prompt']
    assert e.adapter_requests[-1] == request_payload(preview)
    assert '\nSOURCE:\n' not in preview.prompt


def test_actual_adapter_false_belief_never_includes_true_secret(dispatch):
    e = dispatch; secret = 'TRUE_BUT_UNKNOWN_SECRET'; r = relation(e, secret)
    learn(e, r, operation='MISUNDERSTAND', category='FALSE_BELIEF', value='The trusted gate is open')
    value = prepared(e, secret)
    e.manager._run(value)
    assert value.status == 'COMPLETED', value.error
    prompt = e.wire.generations[-1][2]['prompt']
    assert 'The trusted gate is open' in prompt and 'FALSE_BELIEF' in prompt
    assert secret not in json.dumps(e.adapter_requests)
    assert secret not in prompt


@pytest.mark.parametrize('change', ['knowledge', 'permission', 'flag', 'cancel'])
def test_local_adapter_metadata_wait_rechecks_character_authority_before_wire(dispatch, monkeypatch, change):
    e = dispatch; secret = 'CURRENTLY_AUTHORIZED_SECRET'; r = relation(e, secret); learned = learn(e, r)
    value = prepared(e, secret)
    def revoke():
        e.wire.on_show = None
        if change == 'knowledge': e.graph.review(e.nid, e.scope, 'reviewer', learned['id'], 'archive', learned['version'])
        elif change == 'permission': e.authority[0] = 'revoked-author'
        elif change == 'flag': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        else: value.cancelled.set()
    e.wire.on_show = revoke
    e.manager._run(value)
    assert value.status in {'FAILED', 'CANCELLED'}
    assert not e.wire.generations
