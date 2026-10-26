"""Resource failures and replay over real mounted owners, without providers."""
import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline, snapshot

pytestmark = pytest.mark.file_backend_only


def query(e, **params):
    return e.client.get(e.usage_base + '/studio-graph-usages', headers=e.headers, params=params)


def test_scope_budget_refuses_before_any_scope_content_read(usage_rig, monkeypatch):
    from app.creative.asset_usage_budget import UsageReadBudget
    e = usage_rig
    graph_create(e)
    before = snapshot(e.rig.root)
    monkeypatch.setattr(UsageReadBudget, 'MAX_SCOPE_BYTES', 64)
    response = query(e, limit=1)
    assert response.status_code == 409
    assert response.json()['code'] == 'STUDIO_GRAPH_USAGE_UNAVAILABLE'
    assert snapshot(e.rig.root) == before


def test_byte_accounting_is_actual_and_hard_bounded(tmp_path):
    from app.creative.asset_usage_budget import UsageReadBudget, UsageBudgetError
    path = tmp_path / 'bounded.json'
    path.write_bytes(b'12345678')
    budget = UsageReadBudget()
    budget.MAX_READ_BYTES = 10
    assert budget.read(path) == '12345678'
    assert budget.read_bytes == 8 and budget.reads == 1
    with pytest.raises(UsageBudgetError):
        budget.read(path)
    assert budget.read_bytes == 8


def test_token_replay_expiration_capacity_and_cleanup(usage_rig, monkeypatch):
    from app.creative import asset_usage_paging as paging
    e = usage_rig
    graph_create(e, 3)
    monkeypatch.setattr(paging, '_tokens', {})
    first = query(e, limit=1).json()
    assert first['supported_sources'] == ['graph', 'timeline']
    assert first['selected_sources'] == ['graph']
    assert first['excluded_graph_schemas'] == [6, 7]
    assert first['total_scope'] == 'VISIBLE_SELECTED_SAVED_DIRECT_ASSET_REFERENCES'
    assert first['budgets']['authority_reads_in_budget'] is False
    assert 'file_read_bytes' not in first['budgets']
    assert first['budgets']['scope_asset_metadata_read_bytes'] > 0
    token = first['next_cursor']
    replay1 = query(e, limit=1, cursor=token)
    replay2 = query(e, limit=1, cursor=token)
    assert replay1.status_code == replay2.status_code == 200
    assert replay1.json()['items'] == replay2.json()['items']
    assert replay1.json()['observed_count'] == replay2.json()['observed_count'] == 2
    with paging._lock:
        paging._tokens[token]['expires'] = 0
    assert query(e, limit=1, cursor=token).status_code == 409
    monkeypatch.setattr(paging, 'MAX_TOKENS', 0)
    assert query(e, limit=1).status_code == 409


def test_after_issue_mutation_discards_new_token(usage_rig, monkeypatch):
    from app.creative import asset_usage_paging as paging
    e = usage_rig
    graph_create(e, 2)
    monkeypatch.setattr(paging, '_tokens', {})
    fired = []
    def checkpoint(stage):
        if stage == 'before_return' and not fired:
            fired.append(True)
            assert len(paging._tokens) == 1
            with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
                row = e.rig.workspace._row(e.rig.nid, e.rig.scope, e.asset['id'])
                row['version'] += 1
                e.rig.assets._write_meta(row)
    monkeypatch.setattr(paging, '_checkpoint', checkpoint)
    assert query(e, limit=1).status_code == 409
    assert paging._tokens == {}


def test_oversized_query_and_duplicate_fields_are_rejected(usage_rig):
    e = usage_rig
    graph_create(e)
    url = e.usage_base + '/studio-graph-usages'
    for suffix in ('?limit=1&cursor=' + 'a' * 3000, '?limit=1&limit=1'):
        response = e.client.get(url + suffix, headers=e.headers)
        assert response.status_code == 409
        assert len(response.content) < 1024


def test_page_scans_empty_consumers_with_explicit_continuation(usage_rig):
    e = usage_rig
    for index in range(17):
        graph_create(e, 1, 'empty-page-' + str(index))
    response = query(e, limit=200, state='STALE')
    assert response.status_code == 200, response.text
    first = response.json()
    assert first['items'] == [] and first['has_more'] and first['total'] is None
    assert first['scanned_consumers'] == 16 and first['scanned_references'] == 16
    last = query(e, limit=200, state='STALE', cursor=first['next_cursor']).json()
    assert last['items'] == [] and not last['has_more'] and last['total'] == 0
