"""Original File / real PostgreSQL knowledge-owner CAS, without new editable stores."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from app.repositories.chapter_repository import VersionConflict
from app.repositories.structured_cas import record_digest
from test_r5_project_forks import env


@pytest.mark.parametrize('kind,rid,payload', [
    ('characters', 'hero', {'name': 'Synthetic hero', 'status': 'ALIVE', 'privacy_level': 'LOCAL_ONLY'}),
    ('locations', 'harbor', {'name': 'Synthetic harbor', 'status': 'ACTIVE', 'privacy_level': 'LOCAL_ONLY'}),
    ('relationships', 'allies', {'source_character_id': 'hero', 'target_character_id': 'other', 'relationship_type': 'ally', 'privacy_level': 'LOCAL_ONLY'}),
])
def test_original_record_create_compare_swap_and_no_private_conflict_payload(env, kind, rid, payload):
    e = env; novel = e.novels
    created = novel.compare_and_swap_record(e.nid, kind, rid, payload, None)
    assert created['id'] == rid
    original = next(r for r in novel.data_set(e.nid, kind) if r['id'] == rid)
    assert created == original
    with pytest.raises(VersionConflict) as err: novel.compare_and_swap_record(e.nid, kind, rid, payload, None)
    assert err.value.current == {'id': rid, 'version': 0}
    changed = {k: v for k, v in original.items() if k not in {'id', 'privacy_status'}}; changed['status'] = 'ARCHIVED'
    result = novel.compare_and_swap_record(e.nid, kind, rid, changed, record_digest(original))
    assert result['status'] == 'ARCHIVED'
    with pytest.raises(VersionConflict): novel.compare_and_swap_record(e.nid, kind, rid, changed, record_digest(original))
    restored = novel.compare_and_swap_record(e.nid, kind, rid, payload, record_digest(result))
    assert restored.get('status') != 'ARCHIVED'


def test_record_cas_serializes_two_original_clients_and_rechecks_after_legacy_upsert(env):
    e = env; created = e.novels.upsert_character(e.nid, 'same', {'name': 'Before', 'privacy_level': 'LOCAL_ONLY'})
    fingerprint = record_digest(created); gate = Barrier(2)
    def writer(name):
        gate.wait()
        try: return e.novels.compare_and_swap_record(e.nid, 'characters', 'same', {'name': name, 'privacy_level': 'LOCAL_ONLY'}, fingerprint)
        except VersionConflict: return None
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(writer, ['A', 'B']))
    assert sum(r is not None for r in results) == 1
    current = next(r for r in e.novels.data_set(e.nid, 'characters') if r['id'] == 'same')
    e.novels.upsert_character(e.nid, 'same', {'name': 'Ordinary editor', 'privacy_level': 'LOCAL_ONLY'})
    with pytest.raises(VersionConflict): e.novels.compare_and_swap_record(e.nid, 'characters', 'same', {'name': 'Must not win'}, record_digest(current))


def test_cas_rejects_unknown_payload_without_silent_extension_loss(env):
    e = env
    with pytest.raises(ValueError, match='extension'):
        e.novels.compare_and_swap_record(e.nid, 'characters', 'bad', {'name': 'Synthetic', 'embedded_graph': {'id': 'private'}}, None)
    assert not any(r['id'] == 'bad' for r in e.novels.data_set(e.nid, 'characters'))
