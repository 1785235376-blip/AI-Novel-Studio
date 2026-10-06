from copy import deepcopy
import pytest
from fastapi import HTTPException
from app.experimental.common import StaleSourceError
from app.experimental.interactive_story import InteractiveStoryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r4_revision_intelligence import revision_env
from test_r5_interactive_story import interactive_env, create, approve, spec


def test_interactive_history_exact_restore_requires_review_and_retains_sources(interactive_env):
    e = interactive_env; row = create(e); original = e.chapters.get(e.cid)
    edited = deepcopy(row['spec']); edited['nodes'][0]['dialogue'] = 'Edited dialogue'
    row = e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'spec': edited})
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    history = e.service.revisions(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    old = history['items'][0]; assert old['version'] == 1
    body = {'expected_version': row['version'], 'restore_version': 1, 'preview_digest': old['preview_digest']}
    restored = e.service.restore_revision(e.nid, e.scope, 'author', row['id'], body)
    assert restored['version'] == 3 and restored['status'] == 'DRAFT'
    assert restored['spec']['nodes'][0]['dialogue'] != 'Edited dialogue'
    assert e.chapters.get(e.cid) == original
    with pytest.raises(CapabilityVersionConflict): e.service.restore_revision(e.nid, e.scope, 'author', row['id'], body)
    with pytest.raises(FileNotFoundError): e.service.revisions(e.nid, e.scope, 'other', row['id'], {'expected_version': 3})


def test_interactive_restore_revocation_is_atomic_and_drift_blocks_history(interactive_env):
    e = interactive_env; row = approve(e, create(e)); old = e.service.revisions(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})['items'][0]
    before = e.store.read(e.nid, e.scope); calls = []
    def revoke():
        calls.append(1)
        if len(calls) == 2: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): e.service.restore_revision(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'restore_version': old['version'], 'preview_digest': old['preview_digest']}, reauthorize=revoke)
    assert e.store.read(e.nid, e.scope) == before
    e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'Changed source'})
    with pytest.raises(StaleSourceError): e.service.revisions(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})


def test_archived_linked_character_cannot_be_injected_by_current_catalog_or_new_story(interactive_env):
    e = interactive_env; row = create(e)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Private archived name', 'status': 'ARCHIVED'})
    catalog = e.service.catalog(e.nid, e.scope)
    assert catalog['characters'] == [] and catalog['graphs'] == []
    view = e.service.story(e.nid, e.scope, 'author', row['id'])
    assert view['content_withheld'] and 'spec' not in view
    with pytest.raises(FileNotFoundError): create(e)
    contract = e.service.engine_contract()
    assert contract['third_party_execution'] == 'DENY_ALL' and contract['runtime_status'] == 'NOT_RUN'
    assert contract['input_schema']['additionalProperties'] is False
