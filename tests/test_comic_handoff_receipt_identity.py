"""Real File receipt identity corruption must never look like a new request."""
import copy
import json

import pytest

from app.experimental.comic_timeline_handoff import COLLECTION
from app.experimental.media import digest
from test_comic_timeline_handoff import handoff, page
from test_comic_timeline_handoff_recovery import body, confirm, status, timelines
from test_v2_independent_workspace import rig


FOREIGN = 'file:00000000-0000-0000-0000-000000000001'
MISSING = object()
CASES = [
    ('top-incarnation-foreign', ('incarnation',), FOREIGN),
    ('top-incarnation-missing', ('incarnation',), MISSING),
    ('top-incarnation-type', ('incarnation',), 1),
    ('top-incarnation-invalid', ('incarnation',), 'file:invalid'),
    ('top-actor-foreign', ('actor',), 'another-actor'),
    ('top-actor-missing', ('actor',), MISSING),
    ('top-actor-type', ('actor',), True),
    ('top-request-missing', ('request_id',), MISSING),
    ('top-request-foreign', ('request_id',), 'another-request'),
    ('top-request-type', ('request_id',), ['create']),
    ('top-novel-missing', ('novel_id',), MISSING),
    ('top-scope-foreign', ('scope',), {'mode': 'local', 'novel_id': 'another-project'}),
    ('top-scope-type', ('scope',), []),
    ('top-id-missing', ('id',), MISSING),
    ('nested-incarnation-foreign', ('preview', 'incarnation'), FOREIGN),
    ('nested-incarnation-missing', ('preview', 'incarnation'), MISSING),
    ('nested-incarnation-type', ('preview', 'incarnation'), False),
    ('nested-actor-foreign', ('preview', 'actor'), 'another-actor'),
    ('nested-scope-foreign', ('preview', 'scope_key'), 'f' * 64),
    ('nested-request-foreign', ('confirm', 'request_id'), 'another-request'),
]


def stored_counts(rig):
    return {'assets': sorted(p.stem for p in rig.assets.root.glob('*.bin')),
            'timelines': sorted(timelines(rig)),
            'receipts': sorted(rig.raw_store.read(rig.nid, rig.scope)['collections'].get(COLLECTION, {}))}


@pytest.mark.parametrize('label,path,value', CASES, ids=[item[0] for item in CASES])
@pytest.mark.parametrize('phase', ['PLANNED', 'DRAFT_CREATED'])
def test_identity_corruption_rejects_every_entry_without_new_effects(rig, handoff, monkeypatch, tmp_path,
                                                                  label, path, value, phase):
    request = body(rig, handoff, [page(rig, handoff)])
    if phase == 'PLANNED':
        original = rig.assets.create
        def fail(*args, **kwargs): raise OSError('leave the exact intent before any Asset')
        monkeypatch.setattr(rig.assets, 'create', fail)
        with pytest.raises(OSError): confirm(rig, handoff, request)
        monkeypatch.setattr(rig.assets, 'create', original)
    else:
        confirm(rig, handoff, request)
    observed = status(rig, handoff)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        row = state['collections'][COLLECTION][observed['id']]
        target = row
        for key in path[:-1]: target = target[key]
        if value is MISSING: target.pop(path[-1])
        else: target[path[-1]] = copy.deepcopy(value)
        if path[0] == 'preview':
            # Do not rely only on a stale checksum: keep the nested envelope's
            # digests self-consistent while leaving its conflicting top identity.
            row['preview']['preview_digest'] = digest({k: v for k, v in row['preview'].items() if k != 'preview_digest'})
            row['confirm']['reviewed_preview_digest'] = row['preview']['preview_digest']
    before = stored_counts(rig)
    outcomes = {}
    operations = {
        'status': lambda: status(rig, handoff),
        'confirm': lambda: confirm(rig, handoff, request),
        'resume': lambda: handoff.resume(rig.nid, rig.scope, rig.actor, 'create', observed['version']),
        'usage': lambda: checked_usage(rig, handoff),
    }
    for name, operation in operations.items():
        try:
            operation(); outcomes[name] = {'rejected': False}
        except Exception as error:
            outcomes[name] = {'rejected': True, 'type': type(error).__name__, 'code': str(error)}
    after = stored_counts(rig)
    (tmp_path / 'identity-probe.json').write_text(json.dumps({
        'mutation': label, 'phase': phase, 'before': before, 'after': after, 'outcomes': outcomes,
    }, indent=2), encoding='utf-8')
    assert after == before, {'before': before, 'after': after, 'outcomes': outcomes}
    assert all(item.get('rejected') and item.get('type') == 'ValueError'
               and item.get('code') == 'COMIC_HANDOFF_RECEIPT_CORRUPT' for item in outcomes.values()), outcomes


def checked_usage(rig, handoff):
    with handoff._write_phase(rig.nid, rig.scope, rig.actor, lambda: None) as (state, context):
        return handoff._usage(state, rig.nid, rig.scope, context, lambda: None)


def test_consistent_historical_receipt_survives_real_project_recreation(rig, handoff):
    original_request = body(rig, handoff, [page(rig, handoff)])
    first = confirm(rig, handoff, original_request)
    old_receipt = copy.deepcopy(rig.raw_store.read(rig.nid, rig.scope)['collections'][COLLECTION][first['id']])
    old_counts = stored_counts(rig)
    old_incarnation = handoff.owner.incarnation(rig.nid)
    rig.novels.delete(rig.nid)
    rig.create_project('Recreated original owner', nid=rig.nid)
    rig.service.activate(rig.nid, rig.scope, rig.actor)
    assert handoff.owner.incarnation(rig.nid) != old_incarnation
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'][COLLECTION][first['id']] == old_receipt
    with pytest.raises(FileNotFoundError): status(rig, handoff)
    new_request = body(rig, handoff, [page(rig, handoff)])  # same request ID, new actual owner/source
    second = confirm(rig, handoff, new_request)
    assert second['id'] != first['id'] and second['timeline_snapshot']['id'] != first['timeline_snapshot']['id']
    assert second['preview']['incarnation'] != first['preview']['incarnation']
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'][COLLECTION][first['id']] == old_receipt
    counts = stored_counts(rig)
    assert set(old_counts['assets']).issubset(counts['assets'])
    assert len(counts['assets']) == len(old_counts['assets']) + 1
    assert len(counts['timelines']) == len(old_counts['timelines']) + 1
    assert confirm(rig, handoff, new_request)['timeline_snapshot'] == second['timeline_snapshot']
    assert stored_counts(rig) == counts


def test_consistent_different_actor_receipt_is_not_corruption(rig, handoff):
    original_request = body(rig, handoff, [page(rig, handoff)])
    first = confirm(rig, handoff, original_request)
    other = copy.copy(rig); other.actor = 'second-author'
    other_request = body(other, handoff, [page(other, handoff)])
    second = confirm(other, handoff, other_request)
    assert second['id'] != first['id']
    assert confirm(rig, handoff, original_request)['timeline_snapshot'] == first['timeline_snapshot']
    assert confirm(other, handoff, other_request)['timeline_snapshot'] == second['timeline_snapshot']
    assert len(stored_counts(rig)['assets']) == len(timelines(rig)) == 2


def test_conflicting_duplicate_identity_is_rejected_without_effects(rig, handoff, monkeypatch):
    from uuid import uuid4
    request = body(rig, handoff, [page(rig, handoff)])
    original = rig.assets.create
    def fail(*args, **kwargs): raise OSError('retain a pending identity without any result')
    monkeypatch.setattr(rig.assets, 'create', fail)
    with pytest.raises(OSError): confirm(rig, handoff, request)
    monkeypatch.setattr(rig.assets, 'create', original)
    created = status(rig, handoff)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        duplicate = copy.deepcopy(state['collections'][COLLECTION][created['id']])
        duplicate['id'] = str(uuid4())
        state['collections'][COLLECTION][duplicate['id']] = duplicate
    before = stored_counts(rig)
    with pytest.raises(ValueError, match='RECEIPT_AMBIGUOUS'): confirm(rig, handoff, request)
    assert stored_counts(rig) == before


@pytest.mark.parametrize('phase', ['PLANNED', 'DRAFT_CREATED'])
def test_retagged_envelope_cannot_claim_foreign_owner_of_actual_page(rig, handoff, monkeypatch, phase):
    request = body(rig, handoff, [page(rig, handoff)])
    if phase == 'PLANNED':
        original = rig.assets.create
        def fail(*args, **kwargs): raise OSError('leave intent only')
        monkeypatch.setattr(rig.assets, 'create', fail)
        with pytest.raises(OSError): confirm(rig, handoff, request)
        monkeypatch.setattr(rig.assets, 'create', original)
    else: confirm(rig, handoff, request)
    observed = status(rig, handoff)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        row = state['collections'][COLLECTION][observed['id']]
        row['incarnation'] = row['preview']['incarnation'] = FOREIGN
        row['preview']['preview_digest'] = digest({k: v for k, v in row['preview'].items() if k != 'preview_digest'})
        row['confirm']['reviewed_preview_digest'] = row['preview']['preview_digest']
    before = stored_counts(rig)
    try: confirm(rig, handoff, request)
    except ValueError as error: assert str(error) == 'COMIC_HANDOFF_RECEIPT_CORRUPT'
    else: pytest.fail('Re-signed conflicting identity was silently treated as history')
    assert stored_counts(rig) == before
