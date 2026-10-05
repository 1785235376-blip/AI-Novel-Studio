"""Real graph projection binding; shared JobManager dispatch is a separate gate."""
import copy
import json

import pytest
from fastapi import HTTPException

from app.experimental.character_author_context import CharacterContextSource, configure_character_job, is_character_job, resolve_character_author_context
from app.experimental.common import StaleSourceError
from app.jobs import Job
from test_r3_planning import planning_env
from test_r4_story_graph import env, relation, learn


@pytest.fixture
def binding(env, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'world_character_engines_v2,temporal_story_graph_v2,character_mind_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    e = env
    e.ctx = CharacterContextSource(novel_id=e.nid, scope=e.scope, actor='local-author', token='synthetic-session-token', service=e.graph, user_instruction='Describe the viewpoint character cautiously.')
    e.authority = ['local-author', copy.deepcopy(e.scope)]
    e.authorize = lambda: copy.deepcopy(e.authority)
    return e


def job(e, **kwargs):
    return Job('synthetic-character-job', 'continue', e.nid, e.order[3],
               'USER REQUEST plus LEAKING_DERIVED_PLAN', 'LOCAL_ONLY',
               source='LEAKING_SELECTION', style='LEAKING_DERIVED_STYLE',
               creation_records=[{'id': 'private-plan', 'text': 'LEAKING_DERIVED_CONTEXT'}], **kwargs)


def configure(e, value=None):
    value = value or job(e)
    configure_character_job(value, e.ctx, 'alice', e.order[3], authorize=e.authorize)
    return value


def test_binding_replaces_enrichment_and_transmits_only_explicit_user_instruction(binding):
    e = binding; secret = 'VILLAIN_ONLY_HIDDEN_SECRET'; r = relation(e, secret); learn(e, r, character='bob')
    value = configure(e)
    serialized = json.dumps(resolve_character_author_context(value, cloud=False))
    assert secret not in serialized and r['id'] not in serialized
    assert 'LEAKING_' not in serialized
    assert value.instruction == e.ctx.user_instruction
    assert value.source == value.style == '' and value.creation_records == []
    assert set(resolve_character_author_context(value, cloud=False)) == {'character_viewpoint'}
    descriptor = json.dumps(value.character_viewpoint)
    assert e.ctx.token not in descriptor and 'scope' not in descriptor and secret not in descriptor
    assert is_character_job(value)


def test_revoke_or_learn_requires_fresh_character_binding(binding):
    e = binding; r = relation(e, 'Secret only learned later'); value = configure(e)
    learned = learn(e, r)
    with pytest.raises(StaleSourceError, match='SOURCE_CHANGED'):
        resolve_character_author_context(value, cloud=False)
    fresh = configure(e)
    assert resolve_character_author_context(fresh, cloud=False)['character_viewpoint']['secrets'][0]['text'] == r['data']['statement']
    e.graph.review(e.nid, e.scope, 'reviewer', learned['id'], 'archive', learned['version'])
    with pytest.raises(StaleSourceError): resolve_character_author_context(fresh, cloud=False)


def test_same_version_evidence_drift_blocks_bound_character_context(binding):
    e = binding; r = relation(e); learn(e, r); value = configure(e)
    e.chapters[e.order[0]]['content'] += ' same-version drift'
    with pytest.raises(StaleSourceError): resolve_character_author_context(value, cloud=False)


@pytest.mark.parametrize('field', ['source', 'style', 'creation_records', 'instruction', 'chapter_id', 'novel_id', 'scope', 'profile', 'character_viewpoint'])
def test_late_enrichment_identity_or_profile_tampering_fails_closed(binding, field):
    e = binding; value = configure(e)
    changes = {'source': 'Private source', 'style': 'Private style', 'creation_records': [{'id': 'p'}],
               'instruction': 'Changed enriched instruction', 'chapter_id': e.order[0], 'novel_id': 'other',
               'scope': {'branch_id': 'another'}, 'profile': 'QUALITY', 'character_viewpoint': {}}
    setattr(value, field, changes[field])
    with pytest.raises(ValueError): resolve_character_author_context(value, cloud=False)
    assert is_character_job(value)


def test_flags_authority_cancel_cloud_and_restart_are_last_hop_fences(binding, monkeypatch):
    e = binding; value = configure(e)
    with pytest.raises(ValueError, match='LOCAL_ONLY'): resolve_character_author_context(value, cloud=True)
    e.authority[0] = 'different-author'
    with pytest.raises(ValueError, match='AUTHORITY_CHANGED'): resolve_character_author_context(value, cloud=False)
    e.authority[0] = 'local-author'; value.cancelled.set()
    with pytest.raises(ValueError, match='CANCELLED'): resolve_character_author_context(value, cloud=False)
    value.cancelled.clear(); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    with pytest.raises(HTTPException) as exc: resolve_character_author_context(value, cloud=False)
    assert exc.value.status_code == 404
    monkeypatch.delenv('V1_ACCEPTANCE_MODE')
    restored = job(e); restored.character_viewpoint = copy.deepcopy(value.character_viewpoint)
    assert is_character_job(restored)
    with pytest.raises(ValueError, match='SESSION_REQUIRED'): resolve_character_author_context(restored, cloud=False)


@pytest.mark.parametrize('operation', ['rewrite', 'polish', 'review'])
def test_source_required_operations_are_blocked_instead_of_fake_rewrite(binding, operation):
    e = binding; value = job(e); value.operation = operation
    with pytest.raises(ValueError, match='OPERATION_UNSUPPORTED'): configure(e, value)
    assert value.source == 'LEAKING_SELECTION'
    assert not is_character_job(value)


def test_empty_or_unknown_ctx_does_not_infer_safe_authority(binding):
    e = binding; value = job(e)
    wrong = CharacterContextSource(novel_id=e.nid, scope=e.scope, actor='local-author')
    with pytest.raises(ValueError, match='AUTHORIZATION_REQUIRED'):
        configure_character_job(value, wrong, 'alice', e.order[3], authorize=e.authorize)
    value.scope = {'kind': 'BRANCH', 'branch_id': 'b'}
    with pytest.raises(ValueError, match='SCOPE_MISMATCH'):
        configure_character_job(value, e.ctx, 'alice', e.order[3], authorize=e.authorize)


def test_injected_projection_extra_fields_or_epistemic_changes_are_rejected(binding, monkeypatch):
    e = binding; r = relation(e); learn(e, r)
    original = e.graph.character_context
    def unsafe(*args, **kwargs): return {**original(*args, **kwargs), 'omniscient': 'UNKNOWN_SECRET'}
    monkeypatch.setattr(e.graph, 'character_context', unsafe)
    with pytest.raises(ValueError): configure(e)


def test_original_instruction_is_empty_unless_explicitly_supplied(binding):
    e = binding
    ctx = CharacterContextSource(novel_id=e.nid, scope=e.scope, actor='local-author', service=e.graph)
    value = job(e)
    configure_character_job(value, ctx, 'alice', e.order[3], authorize=e.authorize)
    assert value.instruction == ''
    with pytest.raises(ValueError, match='ALREADY_BOUND'):
        configure_character_job(value, ctx, 'alice', e.order[3], authorize=e.authorize)
