"""Actual mounted IMAGE/Comic bootstrap, original authority and File owners."""
import json
import os
from pathlib import Path

import pytest
from app.authorization import ModalityDomain, PermissionAssignment
from app.creative.project_store import CreativeProjectStore
from app.creative.workspace_api import is_independent_studio_route
from app.experimental.flags import FLAGS
from test_comic_independent import (mounted, prefix, scoped, checked, image_scope,
                                    original_independent_owner, blank)

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.parametrize('mounted', ['file'], indirect=True)]


@pytest.fixture
def bootstrap(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join((*FLAGS, 'narrative_production_v2')))
    service = e.experimental.independent_workspace_service
    monkeypatch.setattr(service, 'store', CreativeProjectStore(e.store))
    monkeypatch.setattr(service, 'novels', e.novels)
    e.studio_base = e.prefix + f'/projects/{e.nid}/studio'
    e.bootstrap_path = e.studio_base + '/comic-workspace'
    return e


def test_image_bootstrap_is_read_only_and_captures_actual_wire(bootstrap, monkeypatch):
    e = bootstrap; image_scope(e)
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    before = e.store.read(e.nid, e.scope)
    assert not marker.exists()
    def forbidden(*args, **kwargs): raise AssertionError('NOVEL source resolution during bootstrap')
    monkeypatch.setattr(e.experimental.comic_layouts_service, '_director', forbidden)
    response = e.client.get(e.bootstrap_path, headers=e.headers)
    data = checked(response)
    assert data == {'contract': 'studio-comic-workspace/1', 'project': {'id': e.nid, 'title': e.novels.get(e.nid)['title']},
                    'source_free': True, 'capabilities': {'can_mutate': True, 'can_review': True}}
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    assert e.store.read(e.nid, e.scope) == before and not marker.exists()
    assert e.client.get(e.studio_base, headers=e.headers).status_code == 403
    assert e.client.get(e.studio_base + '/assets', headers=e.headers).status_code == 403
    assert e.client.get(e.studio_base + '/prompts', headers=e.headers).status_code == 403
    assert not marker.exists()
    page = checked(e.client.post(e.base + '/comic-layouts/records', headers=e.headers, json=blank()), 201)
    assert page['document']['source_mode'] == 'INDEPENDENT' and marker.exists()
    capture = {'capture_contract': 'actual-mounted-comic-bootstrap/1', 'project_id': e.nid,
               'scope': {'workspaceId': e.workspace, 'projectId': e.nid, 'storylineId': e.storyline, 'branchId': e.branch},
               'branch_id': e.branch, 'bootstrap': data, 'page': page,
               'catalog': checked(e.client.get(e.base + '/comic-layouts/catalog', headers=e.headers)),
               'records': checked(e.client.get(e.base + '/comic-layouts/records', headers=e.headers)),
               'books': checked(e.client.get(e.base + '/comic-layouts/books', headers=e.headers))}
    output = Path(os.environ.get('COMIC_BOOTSTRAP_CAPTURE', e.root / 'comic-bootstrap-wire.json'))
    output.write_text(json.dumps(capture, ensure_ascii=False, indent=2) + '\n')
    print('COMIC_BOOTSTRAP_CAPTURE=' + str(output))


def test_mixed_novel_read_and_image_write_have_distinct_capabilities(bootstrap):
    e = bootstrap; scope = image_scope(e, permissions=['domain.write'])
    e.authorization.assign_permission(PermissionAssignment('novel-read-' + e.role, e.lead, 'domain.read', ModalityDomain.NOVEL, scope, e.lead))
    comic = checked(e.client.get(e.bootstrap_path, headers=e.headers))
    assert comic['source_free'] is False
    assert comic['capabilities'] == {'can_mutate': True, 'can_review': False}
    generic = checked(e.client.get(e.studio_base, headers=e.headers))
    assert generic['capabilities']['can_mutate'] is False and generic['capabilities']['can_review'] is False


@pytest.mark.parametrize('permissions,expected', [(['domain.read'], {'can_mutate': False, 'can_review': False}),
    (['domain.read', 'domain.review'], {'can_mutate': False, 'can_review': True})])
def test_bootstrap_recomputes_exact_permissions_and_rejects_wrong_scope(bootstrap, permissions, expected):
    e = bootstrap; image_scope(e, permissions=permissions)
    assert checked(e.client.get(e.bootstrap_path, headers=e.headers))['capabilities'] == expected
    assert e.client.get(e.bootstrap_path, headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code == 403
    assert e.client.get(e.bootstrap_path, headers={'X-Branch-ID': e.branch, 'X-Session-Token': 'wrong'}).status_code == 401
    e.authorization.revoke_permission('image-domain.read' + e.role, e.lead)
    assert e.client.get(e.bootstrap_path, headers=e.headers).status_code == 403


def test_bootstrap_admission_is_exact_and_flags_stay_required(bootstrap, monkeypatch):
    e = bootstrap; image_scope(e)
    path = f'/api/projects/{e.nid}/studio/comic-workspace'
    assert is_independent_studio_route('GET', path)
    for method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        assert not is_independent_studio_route(method, path)
    assert not is_independent_studio_route('GET', path + '/anything')
    for disabled in ['comic_layouts_v2', 'asset_lineage_v2', 'ai_director_v2']:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in (*FLAGS, 'narrative_production_v2') if flag != disabled))
        assert e.client.get(e.bootstrap_path, headers=e.headers).status_code == 404
