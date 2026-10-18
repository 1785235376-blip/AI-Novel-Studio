"""Original mounted Comic owner: blank authored pages, real persistence, no model."""
import copy
import io
import uuid
import pytest
from pydantic import ValidationError
from app.experimental.comic_layouts import ComicLayoutsService, LayoutIn, compose
from app.experimental.store import ExperimentalStore
from app.creative.project_store import CreativeProjectStore
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.screenplay_service import ScreenplayService
from app.services.asset_library_service import AssetLibraryService
from app.authorization import AuthorizationScope, ScopeKind, ModalityDomain, DomainRole, DomainRoleAssignment
from test_r3_mounted_contracts import mounted, prefix, checked, scoped


@pytest.fixture(autouse=True)
def original_independent_owner(request, monkeypatch):
    if 'mounted' not in request.fixturenames:
        yield
        return
    e = request.getfixturevalue('mounted')
    monkeypatch.setattr(e.experimental.comic_layouts_service, 'independent_store', CreativeProjectStore(e.store))
    e.comic_test_projects = []
    try:
        yield
    finally:
        # Only exact IDs created by this test; scope documents have no FK cascade.
        if e.backend == 'postgres':
            with e.store._connect() as connection:
                for nid in e.comic_test_projects:
                    connection.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))
        for nid in e.comic_test_projects:
            try: e.novels.delete(nid)
            except FileNotFoundError: pass

def blank():
    return {'title': '独立页', 'source_mode': 'INDEPENDENT', 'panels': []}


def panel():
    return {'id': 'panel', 'shot_id': None, 'artwork_mode': 'BLANK', 'order': 1,
            'x': 24, 'y': 24, 'width': 752, 'height': 320, 'bubbles': [
                {'id': 'dialogue', 'text': 'Hello\n你好\nこんにちは', 'x': 40, 'y': 40, 'width': 600, 'height': 180}]}


def test_blank_page_mounted_save_reopen_text_history_and_cas(mounted, monkeypatch):
    e = mounted
    nid = checked(e.client.post(e.prefix + '/novels', json={'id': 'blank-comic-' + uuid.uuid4().hex, 'title': 'Blank Image project'}), 201)['id']
    e.comic_test_projects.append(nid)
    base = e.prefix + f'/novels/{nid}/experimental/comic-layouts'
    # No manuscript or screenplay prerequisite, and no rendering prerequisite for storage.
    import app.experimental.comic_layouts as module
    monkeypatch.setattr(module, 'renderer_status', lambda: {'available': False, 'code': 'COMIC_RENDERER_UNAVAILABLE'})
    assert e.chapters.list(nid) == [] and e.screenplays.list(nid) == [] and e.assets.list(nid) == []
    created = checked(e.client.post(base + '/records', json=blank()), 201)
    body = copy.deepcopy(created['document']); body['panels'] = [panel()]
    path = base + '/records/' + created['id']
    saved = checked(e.client.put(path, json={**body, 'expected_version': 1}))
    original = copy.deepcopy(saved['document']); body = copy.deepcopy(original)
    body['panels'][0]['bubbles'][0]['text'] = 'Changed only text\n只改对白'
    edited = checked(e.client.put(path, json={**body, 'expected_version': 2}))
    rejected = e.client.put(path, json={**original, 'expected_version': 2})
    assert rejected.status_code == 409 and 'Changed only text' not in rejected.text
    # Reconstruct all original file/repository readers, not only the service object.
    bundle = create_repository_bundle(e.config, data_root=e.root)
    reopened_store = ExperimentalStore(e.root, e.backend, e.url)
    reopened = ComicLayoutsService(reopened_store,
        NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters),
        ScreenplayService(bundle.novels, bundle.chapters), AssetLibraryService(e.root), independent_store=CreativeProjectStore(reopened_store))
    scope = {'mode': 'local', 'novel_id': nid}
    assert reopened.records(nid, scope, 'local-author')['items'][0]['document'] == body
    report = checked(e.client.post(path + '/preflight', json={'expected_version': edited['version']}))
    assert not report['can_render'] and any(i['code'] == 'COMIC_RENDERER_UNAVAILABLE' for i in report['issues'])
    assert not any(i['code'] == 'COMIC_MISSING_APPROVED_IMAGE' for i in report['issues'])
    empty = {**body, 'panels': []}
    deleted = checked(e.client.put(path, json={**empty, 'expected_version': 3}))
    assert deleted['document']['panels'] == []
    restored = checked(e.client.post(path + '/restore', json={'expected_version': 4, 'target_version': 2}))
    assert restored['version'] == 5 and restored['status'] == 'DRAFT' and restored['document'] == original
    assert e.chapters.list(nid) == [] and e.screenplays.list(nid) == [] and e.assets.list(nid) == []
    assert set(reopened.store.read(nid, scope)['collections']) == {'comic_layouts_v2'}
    response = e.client.get(base + '/records')
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    if e.backend == 'postgres':
        with reopened.store._connect() as connection:
            connection.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))
        e.novels.delete(nid); bundle.novels.database.engine.dispose()


def test_intentional_blank_renders_but_legacy_missing_image_still_blocks():
    body = LayoutIn.model_validate({**blank(), 'panels': [{**panel(), 'bubbles': []}]}).model_dump()
    report, output = compose(body, {}, render=True)
    assert report['can_render'] and output
    from PIL import Image
    with Image.open(io.BytesIO(output[0])) as image:
        assert image.getpixel((24, 24)) == (0, 0, 0) and image.getpixel((100, 100)) == (255, 255, 255)
    body['panels'][0].pop('artwork_mode')
    report, output = compose(body, {}, render=True)
    assert not output and not report['can_render']
    assert any(i['code'] == 'COMIC_MISSING_APPROVED_IMAGE' for i in report['issues'])


@pytest.mark.parametrize('patch', [
    {'screenplay_id': 'fake'}, {'expected_screenplay_version': 1},
    {'panels': [{**panel(), 'shot_id': 'fake'}]},
    {'panels': [{**panel(), 'asset_id': 'fake', 'expected_asset_version': 1}]},
])
def test_independent_rejects_contradictory_bindings(patch):
    with pytest.raises(ValidationError): LayoutIn.model_validate({**blank(), **patch})


def test_legacy_field_omission_and_required_source_contract():
    raw = {'title': 'Old page', 'screenplay_id': 'source', 'expected_screenplay_version': 1,
           'panels': [{**panel(), 'shot_id': 'shot', 'artwork_mode': 'IMAGE'}]}
    raw['panels'][0].pop('artwork_mode')
    first = LayoutIn.model_validate(raw).model_dump()
    assert 'source_mode' not in first and 'artwork_mode' not in first['panels'][0]
    assert 'cover_x_percent' not in first['panels'][0]
    assert LayoutIn.model_validate(first).model_dump() == first
    for patch in ({'panels': []}, {'screenplay_id': None}, {'expected_screenplay_version': None}, {'panels': [panel()]}):
        with pytest.raises(ValidationError): LayoutIn.model_validate({**raw, **patch})


def test_image_only_role_does_not_bypass_original_novel_authority(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_role(DomainRoleAssignment('image-' + e.role, e.lead, DomainRole.DOMAIN_LEAD,
                                                    ModalityDomain.IMAGE, scope, e.lead))
    for method, suffix, body in [('get', '/catalog', None), ('get', '/records', None), ('post', '/records', blank())]:
        response = getattr(e.client, method)(e.base + '/comic-layouts' + suffix, headers=e.headers, **({'json': body} if body else {}))
        assert response.status_code == 403
    assert not e.store.read(e.nid, e.scope)['collections'].get('comic_layouts_v2')


@pytest.mark.parametrize('invalid', ['binding', 'duplicate_panel', 'duplicate_bubble', 'oversized_bubble', 'pixel_limit'])
def test_independent_invalid_input_has_private_bounded_response(mounted, invalid):
    e = mounted; body = {**blank(), 'panels': [panel()]}
    if invalid == 'binding': body['screenplay_id'] = 'PRIVATE-SOURCE-ID'
    elif invalid == 'duplicate_panel': body['panels'].append(panel())
    elif invalid == 'duplicate_bubble': body['panels'][0]['bubbles'].append(copy.deepcopy(body['panels'][0]['bubbles'][0]))
    elif invalid == 'oversized_bubble': body['panels'][0]['bubbles'][0]['text'] = 'PRIVATE' * 200
    else: body.update(width=1600, height=12000)
    response = e.client.post(e.base + '/comic-layouts/records', json=body)
    assert response.status_code == 422 and response.json() == {'detail': {'code': 'COMIC_INPUT_INVALID'}}
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    assert 'PRIVATE' not in response.text
    assert not e.store.read(e.nid, e.scope)['collections'].get('comic_layouts_v2')


def test_independent_dialogue_edit_preserves_original_approved_image(mounted):
    import base64
    from test_r5_comic_layouts import synthetic_png
    e = mounted
    asset = e.assets.create(e.nid, 'synthetic-approved.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
    result = checked(e.client.post(e.base + '/comic-layouts/images/' + asset['id'] + '/approve', json={'expected_version': asset['version']}))
    asset = e.assets.get(result['id']); content = e.assets.content(asset['id'])
    body = {**blank(), 'panels': [{**panel(), 'artwork_mode': 'IMAGE', 'asset_id': asset['id'], 'expected_asset_version': asset['version']}]}
    row = checked(e.client.post(e.base + '/comic-layouts/records', json=body), 201)
    body = row['document']; body['panels'][0]['bubbles'][0]['text'] = 'Only dialogue changed'
    changed = checked(e.client.put(e.base + '/comic-layouts/records/' + row['id'], json={**body, 'expected_version': row['version']}))
    assert changed['version'] == 2 and changed['status'] == 'DRAFT'
    assert e.assets.get(asset['id']) == asset and e.assets.content(asset['id']) == content
    assert e.screenplays.list(e.nid) == []


def test_project_recreation_never_rebinds_independent_rows_or_history(mounted):
    e = mounted
    nid = e.novels.create({'id': 'comic-epoch-' + uuid.uuid4().hex, 'title': 'Original owner'})['id']
    e.comic_test_projects.append(nid)
    scope = {'mode': 'local', 'novel_id': nid}; service = e.experimental.comic_layouts_service
    first = service.save(nid, scope, 'local-author', blank())
    edited = service.save(nid, scope, 'local-author', {**blank(), 'title': 'Private old title'}, rid=first['id'], expected_version=1)
    archived = e.store.read(nid, scope)
    original_identity = archived['collections']['comic_layouts_v2'][first['id']]['project_incarnation']
    e.novels.delete(nid); e.novels.create({'id': nid, 'title': 'Different owner'})
    # A historical import must never grant the new project authority to old rows.
    with e.store.transaction(nid, scope) as state: state.update(copy.deepcopy(archived))
    assert service.records(nid, scope, 'local-author') == {'items': []}
    if e.backend == 'file': assert not (e.root / 'novels' / nid / 'creative_project_v2.json').exists()
    path = e.prefix + f'/novels/{nid}/experimental/comic-layouts/records/' + first['id']
    for response in [
        e.client.put(path, json={**blank(), 'expected_version': 2}),
        e.client.post(path + '/preflight', json={'expected_version': 2}),
        e.client.post(path + '/restore', json={'expected_version': 2, 'target_version': 1}),
        e.client.post(path + '/approve', json={'expected_version': 2, 'review_digest': 'a' * 64, 'acknowledge_warnings': True}),
        e.client.get(path + '/segments/0?expected_version=2'),
        e.client.get(path + '/export?expected_version=2'),
    ]:
        assert response.status_code == 404 and 'Private old title' not in response.text
    assert e.store.read(nid, scope) == archived
    if e.backend == 'file': assert not (e.root / 'novels' / nid / 'creative_project_v2.json').exists()
    fresh = service.save(nid, scope, 'local-author', blank())
    new_identity = e.store.read(nid, scope)['collections']['comic_layouts_v2'][fresh['id']]['project_incarnation']
    assert new_identity != original_identity
    assert [row['id'] for row in service.records(nid, scope, 'local-author')['items']] == [fresh['id']]
    assert e.store.read(nid, scope)['collections']['comic_layouts_v2'][first['id']] == archived['collections']['comic_layouts_v2'][first['id']]
    e.novels.delete(nid)


def test_unbound_independent_record_hidden_and_not_adopted(mounted):
    e = mounted; service = e.experimental.comic_layouts_service
    created = service.save(e.nid, e.scope, 'local-author', blank())
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections']['comic_layouts_v2'][created['id']].pop('project_incarnation')
        state['collections']['unrelated-owner'] = {'untouched': {'text': 'Preserve exact bytes as JSON'}}
    before = e.store.read(e.nid, e.scope)
    assert service.records(e.nid, e.scope, 'local-author')['items'] == []
    with pytest.raises(FileNotFoundError): service.save(e.nid, e.scope, 'local-author', blank(), rid=created['id'], expected_version=1)
    assert e.store.read(e.nid, e.scope) == before
    service.save(e.nid, e.scope, 'local-author', blank())
    assert e.store.read(e.nid, e.scope)['collections']['unrelated-owner'] == before['collections']['unrelated-owner']


def test_missing_invalid_and_denied_creates_never_provision_epoch(mounted):
    e = mounted; service = e.experimental.comic_layouts_service
    if e.backend != 'file': pytest.skip('File marker-specific observation; PostgreSQL uses original project UUID')
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    assert not marker.exists()
    service.records(e.nid, e.scope, 'local-author'); assert not marker.exists()
    with pytest.raises(ValidationError): service.save(e.nid, e.scope, 'local-author', {**blank(), 'screenplay_id': 'contradiction'})
    with pytest.raises(FileNotFoundError): service.save(e.nid, e.scope, 'local-author', {**blank(), 'panels': [{**panel(), 'artwork_mode': 'IMAGE', 'asset_id': 'absent', 'expected_asset_version': 1}]})
    def denied(): raise PermissionError('denied before create')
    with pytest.raises(PermissionError): service.save(e.nid, e.scope, 'local-author', blank(), guard=denied)
    with pytest.raises(FileNotFoundError): service.save('missing', {'mode': 'local', 'novel_id': 'missing'}, 'local-author', blank())
    assert not marker.exists() and not (e.root / 'novels' / 'missing').exists()


def test_file_project_lease_held_until_raw_comic_commit(mounted, monkeypatch):
    e = mounted
    if e.backend != 'file': pytest.skip('File atomic commit hook; PostgreSQL uses original row lock')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import app.experimental.store as store_module
    nid = e.novels.create({'id': 'comic-lease-' + uuid.uuid4().hex, 'title': 'Original owner'})['id']
    e.comic_test_projects.append(nid)
    scope = {'mode': 'local', 'novel_id': nid}; path = e.store.path(nid, scope)
    started, finished = Event(), Event()
    original_write = store_module.atomic_write
    futures = []
    def replace_owner():
        started.set(); e.novels.delete(nid); e.novels.create({'id': nid, 'title': 'Replacement'}); finished.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        def bounded_commit(target, content):
            if target == path:
                futures.append(pool.submit(replace_owner)); assert started.wait(2)
                assert not finished.wait(.05), 'project deletion escaped the original commit lease'
            return original_write(target, content)
        monkeypatch.setattr(store_module, 'atomic_write', bounded_commit)
        e.experimental.comic_layouts_service.save(nid, scope, 'local-author', blank())
        for future in futures: future.result(timeout=5)
    assert finished.is_set()
    assert e.experimental.comic_layouts_service.records(nid, scope, 'local-author') == {'items': []}
    assert not (e.root / 'novels' / nid / 'creative_project_v2.json').exists()


def test_original_asset_lock_precedes_project_and_outlives_comic_commit(mounted, monkeypatch):
    e = mounted
    if e.backend != 'file': pytest.skip('File lock instrumentation; no alternate lock implementation')
    from contextlib import contextmanager
    import app.experimental.comic_layouts as comic_module
    import app.experimental.store as store_module
    service = e.experimental.comic_layouts_service; owner = service.independent_store
    original_workspace = comic_module.workspace_mutation; original_owner = owner.owner_lease
    original_write = store_module.atomic_write
    asset_active = [False]; project_active = [False]; commits = []
    @contextmanager
    def workspace(root, key):
        with original_workspace(root, key):
            if key == 'asset-library': asset_active[0] = True
            try: yield
            finally:
                if key == 'asset-library': asset_active[0] = False
    @contextmanager
    def lease(nid):
        assert e.assets._lock._is_owned() and asset_active[0]
        with original_owner(nid) as identity:
            project_active[0] = True
            try: yield identity
            finally: project_active[0] = False
    def write(path, content):
        if path == e.store.path(e.nid, e.scope):
            assert e.assets._lock._is_owned() and asset_active[0] and project_active[0]
            commits.append(True)
        return original_write(path, content)
    monkeypatch.setattr(comic_module, 'workspace_mutation', workspace)
    monkeypatch.setattr(owner, 'owner_lease', lease)
    monkeypatch.setattr(store_module, 'atomic_write', write)
    row = service.save(e.nid, e.scope, 'local-author', blank())
    row = service.save(e.nid, e.scope, 'local-author', {**blank(), 'title': 'Edited'}, rid=row['id'], expected_version=row['version'])
    report = service.preflight(e.nid, e.scope, 'local-author', row['id'], row['version'])
    service.approve(e.nid, e.scope, 'local-author', row['id'], row['version'], report['review_digest'], True)
    assert len(commits) == 3
