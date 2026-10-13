"""Fresh original-owner File/actual-PG contracts for manual-mask reconstruction."""
import base64
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_pixels import source_png, plane


@pytest.fixture
def mask(rig):
    with rig.service._asset_scope(rig.nid, rig.scope):
        rig.source = rig.assets.create(rig.nid, 'source.png', base64.b64encode(source_png()).decode(),
            'image/png', 'image', 'source', required_features=('narrative_production_v2',))
    rig.body = {'contract': 'manual-binary-mask/1', 'source_version': rig.source['version'],
        'source_sha256': rig.source['sha256'], 'width': 64, 'height': 64,
        'bitplane_base64': plane(), 'idempotency_key': 'authored-mask'}
    return rig


def save(e, *, body=None, actor=None, guard=lambda: None, service=None):
    return (service or e.service).author_mask(e.nid, e.scope, actor or e.actor, e.source['id'], body or e.body, guard)


def asset_files(e):
    return {p.name: p.read_bytes() for p in e.assets.root.iterdir() if p.is_file()}


def test_first_metadata_write_is_complete_real_pixels_and_replay_reopens(mask, monkeypatch):
    e = mask; original = e.assets._write_meta; seen = []
    def write(row):
        if row.get('_manual_mask_origin'):
            assert row['version'] == 1 and row['source_asset_ids'] == [e.source['id']]
            assert row['parameters']['asset_lineage_v2']['origin'] == 'MANUAL_EDIT'
            assert row['parameters']['asset_lineage_v2']['parents'] == {e.source['id']: {'version': 1, 'digest': e.source['sha256']}}
            seen.append(row['id'])
        return original(row)
    monkeypatch.setattr(e.assets, '_write_meta', write)
    result = save(e); row = result['asset']; p = row['provenance']
    assert seen == [row['id']]
    assert (p['origin'], p['integrity'], p['stale'], p['generation']) == ('MANUAL_EDIT', 'VERIFIED', False, None)
    assert p['parents'] == [{'id': e.source['id'], 'label': 'source.png', 'version': 1, 'digest': e.source['sha256'], 'state': 'CURRENT'}]
    assert p['sources'] == [] and row.get('provider_id') is None and row.get('model_id') is None and row.get('source_job_id') is None
    assert result['receipt']['mask_sha256'] == row['sha256'] and result['receipt']['keep_pixels'] == 512
    from app.services.studio_image_mask_authoring import verify_mask
    meta, pixels = e.service.download(e.nid, e.scope, row['id'])
    assert verify_mask(pixels)['mask_sha256'] == row['sha256']
    assert save(e, service=reopened(e)) == result
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2
    assert '_manual_mask_origin' not in json.dumps(result)
    assert not any(e.root.rglob('*image-jobs*'))


@pytest.mark.parametrize('change', ['pixels', 'actor', 'source_version', 'source_digest'])
def test_same_key_changed_identity_never_creates_another_asset(mask, change):
    e = mask; save(e); before = asset_files(e); body = copy.deepcopy(e.body); actor = None
    if change == 'pixels': body['bitplane_base64'] = base64.b64encode(b'\x40' * 512).decode()
    elif change == 'actor': actor = 'another-author'
    elif change == 'source_version': body['source_version'] += 1
    else: body['source_sha256'] = '0' * 64
    with pytest.raises(ValueError): save(e, body=body, actor=actor)
    assert asset_files(e) == before


def test_retry_after_mutable_annotation_keeps_identity_and_original_parent(mask):
    e = mask; result = save(e); row = result['asset']
    changed = e.service.annotate(e.nid, e.scope, e.actor, row['id'], {'expected_version': 1, 'origin': 'MANUAL_EDIT',
        'parent_asset_ids': [e.source['id']], 'license': {'label': 'Author declaration'}, 'operation': 'Changed description'})
    replay = save(e)
    assert replay['asset'] == changed and changed['version'] == 2
    assert replay['receipt'] == result['receipt']
    with e.service._asset_scope(e.nid, e.scope):
        e.assets.update_metadata(e.source['id'], {'scene_id': 'new-source-revision'}, expected_version=1)
    later = e.service.annotate(e.nid, e.scope, e.actor, row['id'], {'expected_version': 2, 'origin': 'MANUAL_EDIT',
        'parent_asset_ids': [e.source['id']], 'operation': 'Still the old painted source'})
    assert later['provenance']['parents'][0]['state'] == 'STALE'
    with e.service._asset_scope(e.nid, e.scope):
        saved = e.assets.get(row['id'])['parameters']['asset_lineage_v2']['parents']
    assert saved[e.source['id']]['version'] == 1
    before = asset_files(e)
    with pytest.raises(ValueError, match='IMAGE_MASK_SOURCE_STALE'): save(e)
    assert asset_files(e) == before


@pytest.mark.parametrize('field,value', [('source_asset_ids', []), ('source_job_id', 'fake-job'), ('provider_id', 'fake-provider'), ('model_id', 'fake-model'), ('approved_at', 'fake')])
def test_generic_metadata_cannot_relabel_manual_source(mask, field, value):
    e = mask; row = save(e)['asset']; before = asset_files(e)
    with e.service._asset_scope(e.nid, e.scope), pytest.raises(ValueError, match='IMAGE_MASK_SOURCE_IMMUTABLE'):
        e.assets.update_metadata(row['id'], {field: value}, expected_version=1)
    assert asset_files(e) == before


@pytest.mark.parametrize('change', ['origin', 'parent', 'digest', 'version', 'sources', 'erase'])
def test_generic_privileged_lineage_cannot_forge_or_refresh_pin(mask, change):
    e = mask; row = save(e)['asset']; before = asset_files(e)
    with e.service._asset_scope(e.nid, e.scope):
        parameters = copy.deepcopy(e.assets.get(row['id'])['parameters']); lineage = parameters['asset_lineage_v2']
        if change == 'origin': lineage['origin'] = 'GENERATED_RESULT'
        elif change == 'parent': lineage['parents'] = {}
        elif change == 'digest': lineage['parents'][e.source['id']]['digest'] = '0' * 64
        elif change == 'version': lineage['parents'][e.source['id']]['version'] = 999
        elif change == 'sources': lineage['sources'] = {'private-canary': {}}
        else: parameters = {}
        with pytest.raises(ValueError, match='IMAGE_MASK_SOURCE_IMMUTABLE'):
            e.assets.update_metadata(row['id'], {'parameters': parameters}, expected_version=1, _lineage_write=True)
    assert asset_files(e) == before


def test_low_disk_existing_replay_is_allocation_free_and_changed_payload_conflicts(mask, monkeypatch):
    e = mask; expected = save(e); before = asset_files(e)
    def no_space(*a): raise AssertionError('existing replay must not reserve disk')
    monkeypatch.setattr(e.service.storage_admission, 'require', no_space)
    assert save(e) == expected
    with pytest.raises(ValueError): save(e, body={**e.body, 'bitplane_base64': base64.b64encode(b'\x40' * 512).decode()})
    assert asset_files(e) == before


@pytest.mark.parametrize('field', ['novel_id', 'branch_id', '_manual_mask_origin', 'parameters', 'json'])
def test_damaged_same_key_receipt_never_falls_through_to_new_creation(mask, field, monkeypatch):
    e = mask; row = save(e)['asset']; path = e.assets._meta_path(row['id']); value = json.loads(path.read_text())
    if field == 'json': path.write_text('unreadable-private-canary')
    else:
        value[field] = 'private-canary'; path.write_text(json.dumps(value))
    before = asset_files(e)
    # Source validation legitimately reads its existing binary, so trap staging
    # through mkstemp instead of any source/candidate read.
    import app.services.asset_library_service as owner
    monkeypatch.setattr(owner.tempfile, 'mkstemp', lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not stage')))
    with pytest.raises(ValueError, match='IMAGE_MASK_RECEIPT_UNAVAILABLE'): save(e)
    assert asset_files(e) == before


def test_precommit_authority_loss_never_publishes_mask(mask, monkeypatch):
    e = mask; before = asset_files(e); original = e.assets.create
    def intercepted(*a, **k):
        if k.get('_initial_manual_mask'):
            k['guard'] = lambda: (_ for _ in ()).throw(RuntimeError('revoked'))
        return original(*a, **k)
    monkeypatch.setattr(e.assets, 'create', intercepted)
    with pytest.raises(RuntimeError, match='revoked'): save(e)
    assert asset_files(e) == before


def test_two_same_request_saves_share_one_original_asset(mask):
    e = mask; other = reopened(e); gate = Barrier(2)
    def run(service): gate.wait(); return save(e, service=service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run, e.service); b = pool.submit(run, other)
        one, two = a.result(timeout=10), b.result(timeout=10)
    assert one == two and len(e.service.list_assets(e.nid, e.scope)['items']) == 2


@pytest.mark.parametrize('damage', ['missing', 'replaced'])
def test_observed_retry_cannot_become_unreserved_creation(mask, monkeypatch, damage):
    import app.services.studio_image_mask_authoring as pixels
    import app.services.asset_library_service as owner
    e = mask; result = save(e); path = e.assets._meta_path(result['asset']['id']); original = pixels.encode_mask
    def changed(*a, **k):
        answer = original(*a, **k)
        path.rename(path.with_suffix('.retained'))
        if damage == 'replaced':
            value = json.loads(path.with_suffix('.retained').read_text()); value['id'] = 'different-mask'
            e.assets._meta_path(value['id']).write_text(json.dumps(value))
        return answer
    monkeypatch.setattr(pixels, 'encode_mask', changed)
    monkeypatch.setattr(owner.tempfile, 'mkstemp', lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not stage')))
    monkeypatch.setattr(e.service.storage_admission, 'require', lambda *a: (_ for _ in ()).throw(AssertionError('must not reserve')))
    with pytest.raises(ValueError, match='IMAGE_MASK_RETRY_CHANGED'): save(e)
    assert len(list(e.assets.root.glob('*.bin'))) == 2


@pytest.mark.parametrize('change', ['revision', 'delete', 'recreate'])
def test_source_drift_after_encoding_never_publishes(mask, monkeypatch, change):
    import app.services.studio_image_mask_authoring as pixels
    e = mask; original = pixels.encode_mask
    def changed(*a, **k):
        result = original(*a, **k)
        if change == 'recreate':
            e.novels.delete(e.nid); e.create_project(nid=e.nid)
        else:
            with e.service._asset_scope(e.nid, e.scope):
                if change == 'revision': e.assets.update_metadata(e.source['id'], {'scene_id': 'changed'}, expected_version=1)
                else: e.assets.delete(e.source['id'])
        return result
    monkeypatch.setattr(pixels, 'encode_mask', changed)
    with pytest.raises((ValueError, FileNotFoundError)): save(e)
    assert len(list(e.assets.root.glob('*.json'))) == len(list(e.assets.root.glob('*.bin'))) == 1


def test_new_creation_preserves_original_disk_admission(mask, monkeypatch):
    from app.creative.storage_admission import StudioStorageCapacityError
    e = mask; before = asset_files(e)
    monkeypatch.setattr(e.service.storage_admission, 'require', lambda *a: (_ for _ in ()).throw(StudioStorageCapacityError('CREATIVE_STORAGE_LOW_SPACE')))
    with pytest.raises(StudioStorageCapacityError): save(e)
    assert asset_files(e) == before


def test_private_source_is_never_admitted(mask):
    e = mask
    with e.service._asset_scope(e.nid, e.scope):
        private = e.assets.create(e.nid, 'private.png', base64.b64encode(source_png()).decode(), 'image/png', 'image',
            'private', required_features=('narrative_production_v2',), owner_actor_id=e.actor)
    before = asset_files(e)
    with pytest.raises(FileNotFoundError):
        e.service.author_mask(e.nid, e.scope, e.actor, private['id'], {**e.body, 'source_sha256': private['sha256']}, lambda: None)
    assert asset_files(e) == before


def test_source_features_are_inherited_and_cannot_disappear(mask, monkeypatch):
    e = mask; flags = 'narrative_production_v2,asset_lineage_v2,creative_workspace_v2'
    # Use a registered runtime flag already present in the original owner.
    from app.experimental.flags import RUNTIME_FLAGS
    extra = next(x for x in sorted(RUNTIME_FLAGS) if x not in {'narrative_production_v2', 'asset_lineage_v2'})
    flags = 'narrative_production_v2,asset_lineage_v2,' + extra
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags)
    path = e.assets._meta_path(e.source['id']); value = json.loads(path.read_text()); value['_required_features'].append(extra); path.write_text(json.dumps(value))
    row = save(e)['asset']
    with e.service._asset_scope(e.nid, e.scope): assert extra in e.assets.get(row['id'])['_required_features']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    with pytest.raises(FileNotFoundError): save(e)


@pytest.mark.parametrize('other', ['_initial_text_result', '_initial_studio_result'])
def test_initial_manual_origin_cannot_mix_with_other_server_origins(mask, other):
    e = mask; row = save(e)['asset']; before = asset_files(e)
    with e.service._asset_scope(e.nid, e.scope):
        raw = e.assets.get(row['id']); data = e.assets.content(row['id'])
        with pytest.raises(ValueError, match='IMAGE_MASK_ORIGIN_CONFLICT'):
            e.assets.create(e.nid, 'manual-mask.png', base64.b64encode(data).decode(), 'image/png', 'image', 'another',
                required_features=tuple(raw['_required_features']), guard=lambda: None,
                _initial_manual_mask=raw['_manual_mask_origin'], **{other: {}})
    assert asset_files(e) == before


def test_private_marker_recursively_redacted(mask):
    e = mask; row = save(e)['asset']
    with e.service._asset_scope(e.nid, e.scope):
        raw = e.assets.get(row['id']); raw['nested'] = [{'nested': {'_manual_mask_origin': {'private': 'canary'}}}]
    assert '_manual_mask_origin' not in json.dumps(e.assets.public(raw))
    assert 'canary' not in json.dumps(e.assets.public(raw))


@pytest.mark.parametrize('exception', [OSError('private-path-canary'), RecursionError('private-content-canary')])
def test_retry_read_errors_are_sanitized(mask, monkeypatch, exception):
    e = mask; row = save(e)['asset']; original = e.assets._load
    def damaged(aid):
        if aid == row['id']: raise exception
        return original(aid)
    monkeypatch.setattr(e.assets, '_load', damaged)
    with pytest.raises(ValueError, match='^IMAGE_MASK_RECEIPT_UNAVAILABLE$'): save(e)


def test_maximum_size_guard_reads_are_coalesced_and_final_guard_is_fresh(mask, monkeypatch):
    e = mask; data = source_png(1024, 1024)
    with e.service._asset_scope(e.nid, e.scope):
        e.source = e.assets.create(e.nid, 'maximum.png', base64.b64encode(data).decode(), 'image/png', 'image', 'maximum', required_features=('narrative_production_v2',))
    e.body.update(source_sha256=e.source['sha256'], width=1024, height=1024, bitplane_base64=plane(1024, 1024))
    calls = 0
    def current():
        nonlocal calls
        calls += 1
        assert e.store.incarnation(e.nid)
    result = save(e, guard=current)
    assert result['receipt']['keep_pixels'] == 131072
    assert 30 <= calls <= 64


def test_revocation_between_sample_checks_is_caught_before_commit(mask, monkeypatch):
    import app.services.studio_image_mask_authoring as pixels
    e = mask; live = True; original = pixels.encode_mask; before = asset_files(e)
    def changed(*a, **k):
        nonlocal live
        result = original(*a, **k); live = False; return result
    def current():
        if not live: raise RuntimeError('revoked')
    monkeypatch.setattr(pixels, 'encode_mask', changed)
    with pytest.raises(RuntimeError, match='revoked'): save(e, guard=current)
    assert asset_files(e) == before
