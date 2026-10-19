"""Reserved creation markers must fail closed before receipt lookup/replay."""
import copy
import hashlib

import pytest

from app.creative.production_execution import TIMELINES
from app.experimental.comic_timeline_handoff import COLLECTION
from test_comic_timeline_handoff import handoff, page
from test_comic_timeline_handoff_recovery import body, confirm, status, timelines
from test_v2_independent_workspace import rig


def durable_effects(rig):
    return {'timelines': copy.deepcopy(timelines(rig)),
            'assets': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in rig.assets.root.iterdir() if path.is_file()}}


@pytest.mark.parametrize('operation', ['confirm', 'status', 'resume'])
@pytest.mark.parametrize('case', ['null', 'false', 'empty_dict', 'string', 'list',
                                 'wrong_contract', 'missing_field', 'wrong_field_type'])
def test_missing_receipt_with_malformed_reserved_marker_never_replays(rig, handoff, case, operation):
    value = body(rig, handoff, [page(rig, handoff)])
    created = confirm(rig, handoff, value)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        del state['collections'][COLLECTION][created['id']]
        timeline = state['collections'][TIMELINES][created['timeline_snapshot']['id']]
        origin = copy.deepcopy(timeline['comic_handoff_origin'])
        if case == 'null': origin = None
        elif case == 'false': origin = False
        elif case == 'empty_dict': origin = {}
        elif case == 'string': origin = 'not-a-creation-proof'
        elif case == 'list': origin = []
        elif case == 'wrong_contract': origin['contract'] = 'unknown-contract/1'
        elif case == 'missing_field': del origin['creation_snapshot']
        else: origin['receipt_id'] = False
        timeline['comic_handoff_origin'] = origin
    before = copy.deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    effects = durable_effects(rig)
    try:
        if operation == 'confirm': confirm(rig, handoff, value)
        elif operation == 'status': status(rig, handoff)
        else: handoff.resume(rig.nid, rig.scope, rig.actor, 'create', created['version'])
    except ValueError as error:
        assert str(error) == 'COMIC_HANDOFF_RECEIPT_CORRUPT'
    else:
        pytest.fail('Malformed creation marker accepted; native Asset/Timeline counts '
                    f'1/1 -> {len(list(rig.assets.root.glob("*.bin")))}/{len(timelines(rig))}')
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    assert durable_effects(rig) == effects
    assert len(effects['timelines']) == len(list(rig.assets.root.glob('*.bin'))) == 1


def test_ordinary_original_timeline_without_reserved_key_is_allowed(rig, handoff):
    value = body(rig, handoff, [page(rig, handoff)])
    created = confirm(rig, handoff, value)
    ordinary = handoff.production.timeline_save(rig.nid, rig.scope, rig.actor, None,
        {'expected_version': 0, 'title': 'Ordinary original Timeline',
         'timeline': copy.deepcopy(created['timeline']['timeline'])}, lambda: None)
    assert 'comic_handoff_origin' not in ordinary
    original = copy.deepcopy(timelines(rig)[ordinary['id']])
    effects = durable_effects(rig)
    assert status(rig, handoff)['id'] == created['id']
    assert confirm(rig, handoff, value)['id'] == created['id']
    with pytest.raises(ValueError, match='^COMIC_HANDOFF_NOT_RESUMABLE$'):
        handoff.resume(rig.nid, rig.scope, rig.actor, 'create', created['version'])
    assert durable_effects(rig) == effects
    assert timelines(rig)[ordinary['id']] == original
    assert len(timelines(rig)) == 2 and len(list(rig.assets.root.glob('*.bin'))) == 1
