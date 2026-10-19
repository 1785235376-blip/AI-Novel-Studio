"""Synthetic owner-port contract tests, NOT original-owner API acceptance."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.experimental.common import StaleSourceError
from app.experimental.media import digest
from app.experimental.storyboard_impact_adapter import (
    GraphProjection, OwnerRead, StoryboardReaders, graph_index_projection,
    graph_projection, observe_storyboard, storyboard_projection,
)


def ports(nid='novel', scope=None, actor='author', *, targets=1):
    """The fake ports deliberately advertise no HTTP/Host verification."""
    scope = scope or {'mode': 'local', 'novel_id': nid}
    state = SimpleNamespace(nid=nid, actor=actor, scope=deepcopy(scope), epoch='original-epoch',
        denied=False, bad_owner=None, bad_actor=None, bad_scope=None, bad_epoch=None,
        active=[], opened=[], guards=0, graph_version=1,
        source={'contract': 'studio-storyboard/1', 'document_snapshot': {'id': 'board', 'version': 1, 'digest': 'a' * 64}})
    state.graphs = []
    for index in range((targets + 15) // 16):
        count = min(16, targets - 16 * index)
        state.graphs.append({'id': f'graph-{index}', 'version': 1,
            'definition_digest': digest(['definition', index]), 'execution_digest': digest(['execution', index]),
            'title': f'Authorized Graph {index}', 'references': [
                {'node_id': f'direct-{number}', 'definition_id': 'storyboard_plan', 'enabled': True,
                 'document_snapshot': deepcopy(state.source['document_snapshot']), 'state': 'CURRENT'}
                for number in range(count)]})

    def index_value():
        return {'items': [{key: row[key] for key in ('id', 'version', 'definition_digest', 'execution_digest')}
                          for row in state.graphs]}

    @contextmanager
    def capture(owner, key, read):
        value, identity = deepcopy(read()), (state.actor, deepcopy(state.scope), state.epoch)
        state.opened.append((owner, key)); state.active.append((owner, key))
        def guard():
            state.guards += 1
            if state.denied or (owner, key) not in state.active:
                raise PermissionError('original owner denied')
            if identity != (state.actor, state.scope, state.epoch):
                raise PermissionError('original owner identity changed')
            if value != read():
                raise StaleSourceError('original owner pin changed')
        try:
            yield OwnerRead(state.bad_owner or owner, nid, state.bad_actor or actor,
                state.bad_scope if state.bad_scope is not None else deepcopy(scope),
                state.bad_epoch if owner == 'GRAPH' and state.bad_epoch is not None else state.epoch,
                deepcopy(value), guard)
        finally:
            state.active.remove((owner, key))

    readers = StoryboardReaders(
        lambda n, rid: capture('STORYBOARD', rid, lambda: state.source),
        lambda n: capture('GRAPH_INDEX', n, index_value),
        lambda n, gid: capture('GRAPH', gid, lambda: next(row for row in state.graphs if row['id'] == gid)),
    )
    return state, readers


def test_direct_references_without_assets_are_manual_intent_only_and_leases_expire():
    state, readers = ports(targets=2)
    with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers) as observation:
        view = observation.view(state.nid, state.scope, state.actor, 'board')
        assert len(view['items']) == 2 and not view['truncated']
        assert all(item['kind'] == 'CREATIVE_GRAPH_NODE' and not item['refresh_candidate'] for item in view['items'])
        assert all(item['refresh_reason'] == 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED' for item in view['items'])
        assert view['source']['binding']['incarnation_digest'] == digest(state.epoch)
        assert state.epoch not in str(view) and not view['automatic_regeneration']
        assert state.opened == [('STORYBOARD', 'board'), ('GRAPH_INDEX', 'novel'), ('GRAPH', 'graph-0')]
    assert not state.active
    with pytest.raises(PermissionError, match='LEASE_CLOSED'):
        observation.guard()


@pytest.mark.parametrize('wrong', ['bad_owner', 'bad_actor', 'bad_scope', 'bad_epoch'])
def test_each_owner_identity_scope_and_incarnation_must_match(wrong):
    state, readers = ports()
    setattr(state, wrong, {'mode': 'local', 'novel_id': 'foreign'} if wrong == 'bad_scope' else 'foreign')
    with pytest.raises(PermissionError):
        with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers):
            pytest.fail('No observation may escape wrong-owner admission')
    assert not state.active


def test_missing_readers_and_duplicate_index_never_fall_back():
    state, readers = ports()
    with pytest.raises(FileNotFoundError, match='READ_OWNER_UNAVAILABLE'):
        with observe_storyboard(state.nid, state.scope, state.actor, 'board', None):
            pytest.fail('Missing original-owner wiring cannot create an observation')
    state.graphs.append(deepcopy(state.graphs[0]))
    with pytest.raises(ValidationError):
        with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers):
            pytest.fail('Duplicate owner identities are not deduplicated silently')
    assert not state.active


def test_each_graph_get_requires_its_own_original_owner_context():
    state, readers = ports()
    @contextmanager
    def denied(nid, graph_id):
        raise PermissionError('original graph get denied')
        yield  # A context manager shape is not authorization.
    readers = StoryboardReaders(readers.storyboard, readers.graph_index, denied)
    with pytest.raises(PermissionError, match='graph get denied'):
        with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers):
            pytest.fail('List admission cannot authorize a graph get')
    assert not state.active


def test_twenty_targets_are_complete_but_twenty_one_aborts_without_truncation():
    for count in (20, 21):
        state, readers = ports(targets=count)
        if count == 20:
            with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers) as observation:
                assert len(observation.view(state.nid, state.scope, state.actor, 'board')['items']) == 20
        else:
            with pytest.raises(ValueError, match='STORYBOARD_TARGET_LIMIT'):
                with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers):
                    pytest.fail('An incomplete inventory cannot be used for saved intent')
        assert not state.active


@pytest.mark.parametrize('change', ['permission', 'version'])
def test_retained_original_guards_reject_revocation_or_pin_change(change):
    state, readers = ports()
    with pytest.raises((PermissionError, StaleSourceError)):
        with observe_storyboard(state.nid, state.scope, state.actor, 'board', readers) as observation:
            if change == 'permission': state.denied = True
            else: state.graphs[0]['version'] += 1
            observation.guard()
    assert not state.active


def test_strict_projection_uses_only_actual_direct_pins_and_retains_redaction():
    pin = {'id': 'board', 'version': 1, 'digest': 'a' * 64}
    row = {'id': 'g', 'version': 1, 'definition_digest': 'b' * 64, 'execution_digest': 'c' * 64,
        'definition': {'schema_version': 4, 'title': 'Saved graph', 'nodes': [
            {'id': 'direct', 'definition_id': 'storyboard_plan', 'enabled': True, 'parameters': {'document_snapshot': pin}},
            {'id': 'hidden', 'definition_id': 'storyboard_plan', 'enabled': True, 'parameters': {}},
            {'id': 'derived', 'definition_id': 'storyboard_prompt', 'enabled': True, 'parameters': {'shot_id': 'shot'}}]},
        'reference_states': [{'node_id': 'direct', 'state': 'CURRENT'}, {'node_id': 'hidden', 'state': 'UNAVAILABLE'}]}
    value = graph_projection(row)
    assert [node['node_id'] for node in value['references']] == ['direct']
    assert graph_index_projection({'items': [row]})['items'][0]['id'] == 'g'
    assert storyboard_projection({'contract': 'studio-storyboard/1', 'document_snapshot': pin, 'shots': []})['document_snapshot'] == pin
    with pytest.raises(ValidationError): GraphProjection.model_validate({**value, 'can_execute': True})
    with pytest.raises(ValidationError): GraphProjection.model_validate({**value, 'version': True})
    row['reference_states'] = []
    with pytest.raises(ValueError, match='REFERENCE_STATE_INVALID'): graph_projection(row)
