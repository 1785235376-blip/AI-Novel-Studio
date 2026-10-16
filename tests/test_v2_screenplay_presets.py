"""Starter guides are read-only; original manual document owners persist explicit drafts."""
import copy
from uuid import uuid4

import pytest
from test_v2_creative_foundation import rig, client, public


def prototype(rig, index=0):
    return rig.service.screenplay_presets(rig.nid, rig.scope)['templates'][index]


@pytest.mark.parametrize('index', range(4))
def test_each_starter_uses_original_create_edit_history_and_export_without_source(rig, index):
    from app.creative.service import CreativeService
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    source = copy.deepcopy(rig.chapters.list(rig.nid))
    item = prototype(rig, index)
    assert rig.store.read(rig.nid, rig.scope) == before
    value = copy.deepcopy(item['document'])
    for scene in value['scenes']: scene['id'] = str(uuid4())
    row = rig.service.create(rig.nid, rig.scope, rig.actor, value)
    assert row['version'] == 1 and row['source_evidence'] == {} and row['source_independent']
    changed = public(row); changed['scenes'][0]['action'] = 'Author replaces the starter with a saved scene.'
    row = rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, changed)
    reopened = CreativeService(rig.store, rig.novels, rig.chapters)
    assert reopened.get(rig.nid, rig.scope, row['id']) == row
    assert [v['version'] for v in reopened.history(rig.nid, rig.scope, row['id'])['items']] == [1, 2]
    result = reopened.export_screenplay(rig.nid, rig.scope, row['id'], 2, 'markdown')
    assert b'Author replaces the starter' in result['content'] and result['document_version'] == 2
    assert rig.chapters.list(rig.nid) == source
    assert all(not scene['id'].startswith('starter-') for scene in row['scenes'])


def test_catalog_does_not_read_chapters_or_open_a_mutation_transaction(rig, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('catalog cannot read manuscript or write')
    monkeypatch.setattr(rig.chapters, 'get', forbidden)
    monkeypatch.setattr(rig.chapters, 'list', forbidden)
    monkeypatch.setattr(rig.service.store, 'transaction', forbidden)
    result = rig.service.screenplay_presets(rig.nid, rig.scope)
    assert len(result['templates']) == 4
    with pytest.raises(FileNotFoundError): rig.service.screenplay_presets('missing-project', {'mode':'local','novel_id':'missing-project'})


def test_catalog_api_requires_current_scope_and_never_creates_content(rig, client):
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope));url=f'/api/novels/{rig.nid}/experimental/creative/screenplay-presets'
    response = client.get(url, headers={'X-Session-Token':'reader'})
    assert response.status_code == 200 and response.json()['schema_version'] == 1
    assert response.headers['Cache-Control']=='no-store' and response.headers['X-Content-Type-Options']=='nosniff'
    assert client.get(url).status_code == 401
    # This fixture authorizes every syntactically valid branch. Immutable public
    # guides have no private row to hide; real project membership stays in authorize.
    other = client.get(url, headers={'X-Session-Token':'owner','X-Branch-Id':'foreign'})
    assert other.status_code == 200 and other.json() == response.json()
    assert client.get(url.replace(rig.nid, 'foreign-project'), headers={'X-Session-Token':'owner'}).status_code == 404
    assert rig.store.read(rig.nid, rig.scope) == before


@pytest.mark.parametrize('v1',[False,True])
def test_catalog_api_is_default_off_and_v1_off(rig, client, monkeypatch, v1):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2' if v1 else '')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','true' if v1 else 'false')
    response=client.get(f'/api/novels/{rig.nid}/experimental/creative/screenplay-presets',headers={'X-Session-Token':'owner'})
    assert response.status_code==404 and response.json()['detail']['code']=='EXPERIMENTAL_FEATURE_DISABLED'


def test_catalog_rechecks_authority_after_building_public_guides(rig, client, monkeypatch):
    from fastapi import HTTPException
    from app.creative import screenplay_presets
    original=screenplay_presets.catalog
    def replaced():
        value=original()
        # The route's original access/guard calls this exact scope check again.
        def denied(*args): raise HTTPException(403, {'code':'REVOKED_DURING_CATALOG'})
        monkeypatch.setattr(rig.service.store, 'key', denied)
        return value
    monkeypatch.setattr(screenplay_presets,'catalog',replaced)
    response=client.get(f'/api/novels/{rig.nid}/experimental/creative/screenplay-presets',headers={'X-Session-Token':'reader'})
    assert response.status_code==403 and 'templates' not in response.json()
