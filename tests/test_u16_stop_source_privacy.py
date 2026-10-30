"""Mounted File stop: preserve source privacy before version conflict."""
from types import SimpleNamespace

import pytest

from app.actor_context import SessionContext
from app.experimental.common import new_row
from test_studio_asset_query import rig


@pytest.mark.parametrize('alias', ['', '/v1'])
@pytest.mark.parametrize('visible', [False, True])
def test_nonimage_stop_checks_source_visibility_before_cas(rig, monkeypatch, alias, visible):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    if visible:
        chapter = rig.workspace.creative.chapters.create(rig.nid, {'title': 'Synthetic', 'content': 'Synthetic text.'})
        chapter_id = chapter['id']
    else:
        chapter_id = rig.nid + ':1'
    batch = new_row(rig.nid, rig.scope, 'local-author', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': [{'input': {'kind': 'EXPORT'},
           'sources': {chapter_id: 'a' * 64}}]},
        'items': [{'index': 0, 'status': 'PENDING', 'attempts': 0, 'receipts': []}]})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, 'chapters', rig.workspace.creative.chapters)
    monkeypatch.setattr(mounted, 'sources', SimpleNamespace(novels=rig.novels, chapter_reader=None))
    before = rig.workspace.store.store._file_bytes(rig.nid, rig.scope)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop',
        headers={'X-Session-Token': 'synthetic-host'}, json={'expected_version': batch['version'] + 1})
    assert response.status_code == (409 if visible else 404), response.text
    assert rig.workspace.store.store._file_bytes(rig.nid, rig.scope) == before
    assert batch['id'] not in response.text
