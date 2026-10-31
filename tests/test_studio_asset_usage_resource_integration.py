"""Original File owners retain integrity and reject dangerous input pre-decode."""
import json

import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, snapshot

pytestmark = pytest.mark.file_backend_only


def test_original_asset_content_uses_cumulative_usage_budget(usage_rig):
    from app.creative.asset_usage_budget import usage_read_budget, UsageBudgetError
    e = usage_rig
    meta = e.rig.assets._load(e.asset['id'])
    path = e.rig.assets._bin_path(e.asset['id'])
    expected = path.read_bytes()
    with usage_read_budget() as budget:
        budget.MAX_READ_BYTES = len(expected)
        assert e.rig.assets._verified_content(meta) == expected
        assert budget.read_bytes == len(expected) and budget.reads == 1
        with pytest.raises(UsageBudgetError):
            e.rig.assets._verified_content(meta)
        assert budget.read_bytes == len(expected)


def test_original_asset_integrity_failure_is_not_suppressed(usage_rig):
    from app.creative.asset_usage_budget import usage_read_budget
    from app.services.asset_library_service import AssetIntegrityError
    e = usage_rig
    meta = {**e.rig.assets._load(e.asset['id']), 'sha256': '0' * 64}
    with usage_read_budget():
        with pytest.raises(AssetIntegrityError):
            e.rig.assets._verified_content(meta)


@pytest.mark.parametrize('kind', ['large_file', 'large_string', 'deep', 'many_objects'])
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_http_dangerous_scope_is_refused_before_original_json_decoder(usage_rig, monkeypatch, kind, prefix):
    from app.creative.asset_usage_budget import UsageReadBudget
    from app.creative import asset_usage_paging as paging
    e = usage_rig
    graph_create(e)
    path = e.graph.store.path(e.rig.nid, e.rig.scope)
    doc = path.read_bytes().rstrip()
    if kind == 'large_file':
        payload = b'"' + b'x' * UsageReadBudget.MAX_SCOPE_BYTES + b'"'
    elif kind == 'large_string':
        payload = b'"' + b'x' * (UsageReadBudget.MAX_JSON_STRING_BYTES + 1) + b'"'
    elif kind == 'deep':
        payload = b'[' * (UsageReadBudget.MAX_JSON_DEPTH + 1) + b'0' + b']' * (UsageReadBudget.MAX_JSON_DEPTH + 1)
    else:
        payload = b'[' + b'{},' * (UsageReadBudget.MAX_JSON_TOKENS // 3 + 1) + b'{}]'
    path.write_bytes(doc[:-1] + b',"SYNTHETIC_PARSE_SENTINEL":' + payload + b'}')
    original = json.loads
    decoded = []
    def checked(value, *args, **kwargs):
        probe = value.encode() if isinstance(value, str) else value
        if b'SYNTHETIC_PARSE_SENTINEL' in probe:
            decoded.append(True)
        return original(value, *args, **kwargs)
    monkeypatch.setattr(json, 'loads', checked)
    monkeypatch.setattr(paging, '_tokens', {})
    before = snapshot(e.rig.root)
    response = e.client.get(e.usage_base.replace('/api/', prefix + '/', 1) + '/studio-asset-usages',
                            headers=e.headers, params={'limit': 1})
    assert response.status_code == 409, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['code'] == 'STUDIO_ASSET_USAGE_UNAVAILABLE'
    assert not decoded, 'rejected scope reached the original JSON object decoder'
    assert 'items' not in response.json() and 'SYNTHETIC' not in response.text
    assert str(e.rig.root) not in response.text
    assert not paging._tokens
    assert snapshot(e.rig.root) == before
