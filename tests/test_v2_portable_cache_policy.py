"""U14 budgets and plans use only disposable original-owner File fixtures."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import base64

import pytest

from app.experimental.common import StaleSourceError
from app.experimental.portable_cache_policy import CachePolicyInput, cache_budget
from app.experimental.portable_projects import PortableProjectsService
from app.experimental.ux import ReadContext
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig
from test_r4_portable_batches import work, add_media


def export(r, count=1):
    return [r.portable.export(r.ctx, {'chapter_ids': [r.chapter['id']]}) for _ in range(count)]


def cleanup(preview, ids):
    return {'record_ids': ids, 'preview_digest': preview['preview_digest'], 'confirmed': True}


def test_policy_reads_do_not_create_rows_or_touch_cache_and_roundtrip_is_author_scope_bound(work, monkeypatch):
    r = work; before = deepcopy(r.store.read(r.nid, r.scope))
    monkeypatch.setattr(r.portable, '_file', lambda *a, **k: pytest.fail('Policy must not inspect filesystem'))
    assert r.portable.cache_policy(r.ctx) == {'version': 0, 'limit_bytes': None}
    assert r.store.read(r.nid, r.scope) == before
    assert r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': 4096}) == {'version': 1, 'limit_bytes': 4096}
    reopened = PortableProjectsService(r.store, r.novels, r.chapters, sources=r.sources, assets=r.assets)
    assert reopened.cache_policy(r.ctx) == {'version': 1, 'limit_bytes': 4096}
    other = ReadContext(r.nid, r.scope, 'other-author')
    assert reopened.cache_policy(other)['version'] == 0
    reopened.set_cache_policy(other, {'expected_version': 0, 'limit_bytes': 0})
    branch = ReadContext(r.nid, {'mode': 'collaboration', 'novel_id': r.nid,
        'workspace_id': 'workspace', 'storyline_id': 'story', 'branch_id': 'branch'}, r.actor)
    assert reopened.cache_policy(branch)['version'] == 0
    assert reopened.cache_policy(r.ctx) == {'version': 1, 'limit_bytes': 4096}


def test_policy_create_cas_has_one_winner_and_rejects_stale_updates(work):
    r = work
    def save(limit):
        try: return r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': limit})
        except CapabilityVersionConflict: return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [1000, 2000]))
    assert results.count('CONFLICT') == 1 and r.portable.cache_policy(r.ctx)['version'] == 1
    with pytest.raises(CapabilityVersionConflict):
        r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': None})


@pytest.mark.parametrize('field,value', [('expected_version', True), ('expected_version', -1),
    ('limit_bytes', True), ('limit_bytes', -1), ('limit_bytes', 1.5), ('limit_bytes', 2**53)])
def test_policy_bytes_are_strict_safe_integers(field, value):
    body = {'expected_version': 0, 'limit_bytes': None, field: value}
    with pytest.raises(ValueError): CachePolicyInput.model_validate(body)


def test_budget_plans_oldest_verified_cache_without_deletion_then_reuses_original_cleanup(work):
    r = work; asset, _ = add_media(r); exports = export(r, 3)
    original = {row['id']: r.portable.download(r.ctx, row['id'], 1) for row in exports}
    before_history = r.chapters.history(r.chapter['id']); before_asset = r.assets.content(asset['id'])
    view = r.portable.storage(r.ctx); total = sum(row['bytes'] for row in view['eligible'])
    assert view['cache_budget']['state'] == 'UNCONFIGURED' and view['cache_budget']['plan']['record_ids'] == []
    oldest = view['eligible'][0]
    r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': total - oldest['bytes']})
    preview = r.portable.storage(r.ctx); budget = preview['cache_budget']
    assert budget['measurement']['bytes'] == total and budget['excess_bytes'] == oldest['bytes']
    assert budget['plan']['record_ids'] == [oldest['id']] and budget['plan']['complete']
    assert budget['advisory_only'] and budget['automatic_cleanup'] is False
    assert all(r.portable._file(r.ctx, row['id']).is_file() for row in exports)
    r.portable.cleanup(r.ctx, cleanup(preview, budget['plan']['record_ids']))
    assert not r.portable._file(r.ctx, oldest['id']).exists()
    assert sum(r.portable._file(r.ctx, row['id']).is_file() for row in exports) == 2
    assert r.chapters.history(r.chapter['id']) == before_history and r.assets.content(asset['id']) == before_asset
    assert r.portable.download(r.ctx, oldest['id'], 1) == original[oldest['id']]


def test_plan_limit_is_original_100_record_cleanup_limit():
    budget = cache_budget({'version': 1, 'limit_bytes': 0}, [{'id': str(i), 'bytes': 1} for i in range(101)], 0)
    assert len(budget['plan']['record_ids']) == 100 and budget['plan']['remaining_excess_bytes'] == 1
    assert budget['plan']['complete'] is False


def test_unreadable_or_unverified_occupancy_is_unknown_and_no_plan_is_fabricated(work, monkeypatch):
    r = work; exports = export(r, 2)
    r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': 0})
    original = r.portable._read_file
    def unreadable(ctx, row, *args):
        if row['id'] == exports[0]['id']: raise PermissionError('PRIVATE_CACHE_PATH')
        return original(ctx, row, *args)
    monkeypatch.setattr(r.portable, '_read_file', unreadable)
    preview = r.portable.storage(r.ctx); budget = preview['cache_budget']
    assert budget['measurement']['state'] == 'UNKNOWN' and budget['measurement']['bytes'] is None
    assert budget['measurement']['verified_reproducible_bytes'] > 0
    assert budget['excess_bytes'] is None and budget['plan']['record_ids'] == []
    assert 'PRIVATE_CACHE_PATH' not in str(preview)
    assert all(r.portable._file(r.ctx, row['id']).exists() for row in exports)


@pytest.mark.parametrize('change', ['policy', 'source'])
def test_policy_aba_or_source_change_rejects_old_cleanup_without_removing_cache(work, change):
    r = work; row = export(r)[0]; preview = r.portable.storage(r.ctx)
    if change == 'policy':
        r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': 0})
        r.portable.set_cache_policy(r.ctx, {'expected_version': 1, 'limit_bytes': None})
    else: r.chapters.save(r.chapter['id'], {'content': 'New original fixture revision'})
    with pytest.raises(StaleSourceError): r.portable.cleanup(r.ctx, cleanup(preview, [row['id']]))
    assert r.portable._file(r.ctx, row['id']).exists()


@pytest.mark.parametrize('guard_call', [1, 2, 3])
def test_source_change_at_each_confirmation_guard_is_rechecked_before_unlink(work, guard_call):
    r = work; row = export(r)[0]; preview = r.portable.storage(r.ctx); calls = []
    def guard():
        calls.append(True)
        if len(calls) == guard_call:
            r.chapters.save(r.chapter['id'], {'content': 'Concurrent fixture revision'})
    with pytest.raises(StaleSourceError): r.portable.cleanup(r.ctx, cleanup(preview, [row['id']]), guard)
    assert r.portable._file(r.ctx, row['id']).exists()


def test_advisory_zero_budget_does_not_block_export_or_touch_recovery_inputs(work):
    r = work; r.portable.set_cache_policy(r.ctx, {'expected_version': 0, 'limit_bytes': 0})
    row = export(r)[0]
    raw = r.portable.download(r.ctx, row['id'], row['version'])
    recovery = r.portable.preflight_import(r.ctx, {'filename': 'fixture.zip', 'content_base64': base64.b64encode(raw).decode()})
    before = r.portable._file(r.ctx, recovery['id']).read_bytes()
    preview = r.portable.storage(r.ctx)
    assert preview['cache_budget']['state'] == 'OVER_BUDGET'
    assert recovery['id'] not in preview['cache_budget']['plan']['record_ids']
    r.portable.cleanup(r.ctx, cleanup(preview, [row['id']]))
    assert r.portable._file(r.ctx, recovery['id']).read_bytes() == before
