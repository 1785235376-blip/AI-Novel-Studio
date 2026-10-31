"""Independent mixed-incarnation content privacy counterexamples."""
import json

import pytest

from app.creative.asset_usage_budget import usage_read_budget
from app.experimental.audio_scope_snapshot import AudioScopeObservationUnavailable, inspect_existing_audio_scope
from app.experimental.store import canonical
from test_audio_history_status_readonly import snapshot
from test_audio_scope_snapshot_independent import initialize
from test_studio_asset_query import rig


def observation(project, rig):
    try:
        return inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    except AudioScopeObservationUnavailable as exc:
        return str(exc)


def test_other_content_and_invalid_document_have_same_outcome(rig):
    project, store, _ = initialize(rig)
    path = store.path(rig.nid, rig.scope)
    doc = json.loads(path.read_bytes())
    doc['collections']['creative_documents_v2'] = {
        'old': {'project_incarnation': 'file:old-synthetic', 'body': 'old-only-A'}
    }
    path.write_text(canonical(doc), encoding='utf-8')
    before = snapshot(rig.root)
    first = observation(project, rig)
    assert snapshot(rig.root) == before
    doc['collections']['creative_documents_v2']['old']['body'] = 'old-only-B'
    path.write_text(canonical(doc), encoding='utf-8')
    before = snapshot(rig.root)
    second = observation(project, rig)
    assert snapshot(rig.root) == before
    assert first == second and first['scope_snapshot'] == 'UNKNOWN'
    path.write_bytes(b'{not valid synthetic json')
    before = snapshot(rig.root)
    corrupt = observation(project, rig)
    assert snapshot(rig.root) == before
    assert corrupt == first


def test_unbound_old_content_size_cannot_change_result_under_existing_budget(rig):
    project, store, _ = initialize(rig)
    path = store.path(rig.nid, rig.scope)
    doc = json.loads(path.read_bytes())
    doc['collections']['creative_documents_v2'] = {
        'old': {'project_incarnation': 'file:old-synthetic', 'body': 'A'}
    }
    small = canonical(doc).encode('utf-8')
    doc['collections']['creative_documents_v2']['old']['body'] = 'A' * 4096
    large = canonical(doc).encode('utf-8')
    assert len(small) < len(large)
    outcomes = []
    for data in (small, large):
        path.write_bytes(data)
        before = snapshot(rig.root)
        with usage_read_budget() as budget:
            budget.MAX_SCOPE_BYTES = len(small) + 1
            outcomes.append(observation(project, rig))
        assert snapshot(rig.root) == before
    assert outcomes[0]['scope_snapshot'] == 'UNKNOWN'
    assert outcomes[1] == outcomes[0]


def test_revoked_guard_stops_before_scope_read(rig, monkeypatch):
    project, store, _ = initialize(rig)
    def forbidden(*args, **kwargs):
        raise AssertionError('scope read occurred after authority rejection')
    monkeypatch.setattr(store, '_file_snapshot', forbidden)
    def revoked():
        raise PermissionError('synthetic revoked')
    before = snapshot(rig.root)
    with pytest.raises(PermissionError):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, revoked)
    assert snapshot(rig.root) == before
