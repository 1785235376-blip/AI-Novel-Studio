"""Opt-in original authority readers retain defaults and charge every reread."""
import json
from pathlib import Path
from uuid import uuid4

import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, snapshot

pytestmark = pytest.mark.file_backend_only


def authority_reader(tmp_path, owner):
    from app.repository import read_json
    from app.repositories.file.identity import FileIdentityRepository
    from app.repositories.file.scope import FileScopeRepository, FileAuthorizationRepository
    from app.creative.project_store import _read_marker
    values = {
        'project': ({'title': 'Synthetic original metadata'}, tmp_path / 'novel.json',
                    lambda path: lambda: read_json(path, {})),
        'identity': ({'users': [], 'memberships': []}, tmp_path / 'identity.json',
                     lambda path: FileIdentityRepository(tmp_path)._read),
        'scope': ({'workspaces': [], 'project_workspaces': [], 'storylines': [], 'branches': []},
                  tmp_path / 'collaboration_scope.json', lambda path: FileScopeRepository(tmp_path)._read),
        'authorization': ({'role_assignments': [], 'permission_assignments': [], 'audit_events': []},
                          tmp_path / 'authorization.json', lambda path: FileAuthorizationRepository(tmp_path)._read),
        'marker': ({'schema_version': 1, 'project_incarnation': str(uuid4())},
                   tmp_path / 'creative_project_v2.json', lambda path: lambda: _read_marker(path)),
    }
    value, path, make_reader = values[owner]
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, value, make_reader(path)


@pytest.mark.parametrize('owner', ['project', 'identity', 'scope', 'authorization', 'marker'])
def test_original_authority_input_is_admitted_before_decode(tmp_path, monkeypatch, owner):
    from app.creative.asset_usage_budget import usage_read_budget, UsageBudgetError
    path, expected, read = authority_reader(tmp_path, owner)
    assert read() == expected
    original = path.read_bytes()
    with usage_read_budget() as budget:
        budget.MAX_READ_BYTES = len(original) - 1
        def forbidden(*args, **kwargs):
            pytest.fail('JSON decoding occurred after input admission should have refused')
        with monkeypatch.context() as scoped:
            scoped.setattr(json, 'loads', forbidden)
            with pytest.raises(UsageBudgetError):
                read()
        assert budget.reads == 1 and budget.read_bytes == 0
    assert read() == expected and path.read_bytes() == original


@pytest.mark.parametrize('owner', ['project', 'identity', 'scope', 'authorization', 'marker'])
def test_original_authority_rereads_share_request_count(tmp_path, owner):
    from app.creative.asset_usage_budget import usage_read_budget, UsageBudgetError
    path, expected, read = authority_reader(tmp_path, owner)
    size = path.stat().st_size
    with usage_read_budget() as budget:
        budget.MAX_READS = 2
        assert read() == expected
        assert read() == expected
        with pytest.raises(UsageBudgetError):
            read()
        assert budget.reads == 3 and budget.read_bytes == 2 * size
    with usage_read_budget() as separate:
        assert read() == expected
        assert separate.reads == 1 and separate.read_bytes == size


def test_mounted_authority_growth_refuses_before_decode_and_returns_no_store(usage_rig, monkeypatch):
    from app.creative import asset_usage_paging
    from app.creative.asset_usage_budget import UsageReadBudget
    e = usage_rig
    graph_create(e, 1)
    path = e.rig.root / 'novels' / e.rig.nid / 'novel.json'
    original = path.read_bytes()
    grew = []
    def checkpoint(stage):
        if stage == 'after_source' and not grew:
            # Deterministic original-authority reread after initial admission.
            path.write_bytes(b' ' * (UsageReadBudget.MAX_SCOPE_BYTES + 1))
            grew.append(True)
    monkeypatch.setattr(asset_usage_paging, '_checkpoint', checkpoint)
    response = e.client.get(e.usage_base + '/studio-asset-usages',
        params={'limit': 2}, headers=e.headers)
    assert grew
    assert response.status_code == 409, response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.json()['detail']['code'] == 'STUDIO_ASSET_USAGE_UNAVAILABLE'
    assert 'items' not in response.json() and e.asset['id'] not in response.text
    path.write_bytes(original)


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_mounted_missing_host_authority_still_refuses_before_bad_query(usage_rig, prefix):
    e = usage_rig
    before = snapshot(e.rig.root)
    url = e.usage_base.replace('/api/', prefix + '/', 1) + '/studio-asset-usages'
    response = e.client.get(url, params={'limit': 0, 'cursor': 'bad'})
    assert response.status_code == 401, response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.json()['detail']['code'] == 'SESSION_REQUIRED'
    assert snapshot(e.rig.root) == before
