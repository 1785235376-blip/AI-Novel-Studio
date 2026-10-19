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
from test_r3_mounted_contracts import mounted, prefix, checked, scoped as mounted_scoped


def scoped(mounted, monkeypatch):
    """Record only this test's freshly generated authority owners for teardown."""
    try:
        return mounted_scoped(mounted, monkeypatch)
    finally:
        # scoped assigns these unique IDs before its first persistent write, so
        # even a partial setup is reclaimed by the enclosing owner's finally.
        if hasattr(mounted, 'workspace'):
            mounted.comic_test_scopes.append((mounted.workspace, mounted.nid,
                mounted.storyline, mounted.branch, mounted.other_branch,
                mounted.lead, mounted.viewer))


@pytest.fixture(autouse=True)
def original_independent_owner(request, monkeypatch):
    if 'mounted' not in request.fixturenames:
        yield
        return
    e = request.getfixturevalue('mounted')
    monkeypatch.setattr(e.experimental.comic_layouts_service, 'independent_store', CreativeProjectStore(e.store))
    e.comic_test_projects = []
    e.comic_test_scopes = []
    try:
        yield
    finally:
        # Only exact IDs created by this test; scope documents have no FK cascade.
        if e.backend == 'postgres':
            with e.store._connect() as connection:
                for workspace, project, storyline, branch, other_branch, lead, viewer in e.comic_test_scopes:
                    # The generated workspace belongs exclusively to this fixture.
                    # Include later IMAGE grants and membership/revocation audits,
                    # but never sweep pre-existing workspaces or unrelated actors.
                    for table in ('domain_role_assignments', 'permission_assignments', 'authorization_audit_events'):
                        connection.execute(f"DELETE FROM {table} WHERE payload->'scope'->>'workspace_id'=%s", (workspace,))
                    connection.execute('DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id IN (%s,%s)', (workspace, lead, viewer))
                    connection.execute("DELETE FROM storyline_branches WHERE id IN (%s,%s) AND payload->>'workspace_id'=%s AND payload->>'project_id'=%s", (branch, other_branch, workspace, project))
                    connection.execute("DELETE FROM storylines WHERE id=%s AND payload->>'workspace_id'=%s AND payload->>'project_id'=%s", (storyline, workspace, project))
                    connection.execute('DELETE FROM project_workspaces WHERE project_id=%s AND workspace_id=%s', (project, workspace))
                    connection.execute("UPDATE novels SET workspace_id='default-workspace' WHERE slug=%s AND workspace_id=%s", (project, workspace))
                    connection.execute('DELETE FROM workspaces WHERE id=%s', (workspace,))
                    connection.execute('DELETE FROM users WHERE id IN (%s,%s)', (lead, viewer))
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


def test_image_only_role_admits_source_free_without_novel_sources(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_role(DomainRoleAssignment('image-' + e.role, e.lead, DomainRole.DOMAIN_LEAD,
                                                    ModalityDomain.IMAGE, scope, e.lead))
    base = e.base + '/comic-layouts'
    # Even an empty character lookup traverses private NOVEL data. It must not run.
    def forbidden(*args, **kwargs): raise AssertionError('NOVEL source resolution')
    monkeypatch.setattr(e.experimental.comic_layouts_service, '_director', forbidden)
    catalog = checked(e.client.get(base + '/catalog', headers=e.headers))
    assert catalog['screenplays'] == catalog['characters'] == catalog['assets'] == []
    created = checked(e.client.post(base + '/records', headers=e.headers, json=blank()), 201)
    changed = checked(e.client.put(base + '/records/' + created['id'], headers=e.headers,
                                  json={**blank(), 'panels': [panel()], 'expected_version': 1}))
    assert changed['version'] == 2 and changed['document']['panels'][0]['bubbles'][0]['text'].startswith('Hello')
    assert checked(e.client.get(base + '/records', headers=e.headers))['items'] == [changed]
    restored = checked(e.client.post(base + '/records/' + created['id'] + '/restore', headers=e.headers,
                                     json={'expected_version': 2, 'target_version': 1}))
    assert restored['version'] == 3 and restored['document']['panels'] == []
    for suffix in ['/images/private', '/records/' + created['id'] + '/export-ora?expected_version=3']:
        assert e.client.get(base + suffix, headers=e.headers).status_code == 404
    assert e.client.get(e.base + '/director/catalog', headers=e.headers).status_code == 403
    e.authorization.revoke_role('image-' + e.role, e.lead)
    assert e.client.get(base + '/records', headers=e.headers).status_code == 403


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


def image_scope(e, *, permissions=None):
    from app.authorization import PermissionAssignment
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.revoke_role(e.role, e.lead)
    for permission in permissions or ['domain.read', 'domain.write', 'domain.review']:
        e.authorization.assign_permission(PermissionAssignment('image-' + permission + e.role, e.lead,
            permission, ModalityDomain.IMAGE, scope, e.lead))
    return scope


def test_image_policy_hides_adapted_refs_history_and_mixed_books_before_resolution(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); base = e.base + '/comic-layouts'
    original = checked(e.client.post(base + '/records', headers=e.headers, json=blank()), 201)
    service = e.experimental.comic_layouts_service
    # Represent retained legacy/mixed rows in the ORIGINAL owner; no second store.
    with e.store.transaction(e.nid, e.scope) as state:
        source = copy.deepcopy(state['collections'][service.RECORDS][original['id']])
        variants = []
        for kind in ['adapted', 'character', 'bubble', 'asset', 'appearance', 'raster', 'history']:
            row = copy.deepcopy(source); row['id'] = 'private-' + kind
            row['document']['title'] = 'PRIVATE-' + kind
            row['document']['panels'] = [panel()]
            p = row['document']['panels'][0]
            if kind == 'adapted': row['document'].update(source_mode='SCREENPLAY', screenplay_id='PRIVATE-SCREENPLAY')
            elif kind == 'character': p['character_ids'] = ['PRIVATE-CHARACTER']
            elif kind == 'bubble': p['bubbles'][0]['character_id'] = 'PRIVATE-CHARACTER'
            elif kind == 'asset': p.update(artwork_mode='IMAGE', asset_id='PRIVATE-ASSET', expected_asset_version=1)
            elif kind == 'appearance': p['appearance_references'] = [{'asset_id': 'PRIVATE-ASSET'}]
            elif kind == 'raster': row['document']['layer_stack'] = {'items': [{'kind': 'RASTER', 'target_id': 'PRIVATE-ASSET'}]}
            else:
                historical = copy.deepcopy(source); historical['document']['screenplay_id'] = 'PRIVATE-HISTORY'
                row['history'] = [historical]
            state['collections'][service.RECORDS][row['id']] = row; variants.append(row['id'])
    book = checked(e.client.post(base + '/books', headers=e.headers,
        json={'title': 'Safe book', 'chapters': [{'id': 'chapter', 'title': 'Chapter', 'pages': []}]}), 201)
    with e.store.transaction(e.nid, e.scope) as state:
        bad_book = copy.deepcopy(state['collections'][service.BOOKS][book['id']]); bad_book['id'] = 'private-book'
        bad_book['document']['title'] = 'PRIVATE-BOOK'; bad_book['document']['chapters'][0]['pages'] = variants
        state['collections'][service.BOOKS][bad_book['id']] = bad_book
    image_scope(e)
    def forbidden(*args, **kwargs): raise AssertionError('Unauthorized source traversed')
    monkeypatch.setattr(service, '_director', forbidden)
    monkeypatch.setattr(service, '_asset', forbidden)
    assert [r['id'] for r in checked(e.client.get(base + '/records', headers=e.headers))['items']] == [original['id']]
    assert [b['id'] for b in checked(e.client.get(base + '/books', headers=e.headers))['items']] == [book['id']]
    for rid in variants:
        path = base + '/records/' + rid
        responses = [e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': 1}),
            e.client.put(path, headers=e.headers, json={**blank(), 'expected_version': 1}),
            e.client.post(path + '/restore', headers=e.headers, json={'expected_version': 1, 'target_version': 1}),
            e.client.get(path + '/segments/0?expected_version=1', headers=e.headers),
            e.client.get(path + '/export?expected_version=1', headers=e.headers),
            e.client.post(base + '/books/' + book['id'] + '/pages', headers=e.headers,
                json={'expected_version': 1, 'chapter_id': 'chapter', 'source_layout_id': rid, 'expected_source_version': 1})]
        assert all(r.status_code == 404 and 'PRIVATE-' not in r.text for r in responses)
    for suffix, body in [('restore', {'expected_version': 1, 'target_version': 1}),
                         ('publication-preflight', {'expected_version': 1, 'reading_direction': 'LTR'})]:
        response = e.client.post(base + '/books/private-book/' + suffix, headers=e.headers, json=body)
        assert response.status_code == 404 and 'PRIVATE-' not in response.text
    # New references are rejected before any original source owner is invoked.
    for patch in [{'character_ids': ['PRIVATE-CHARACTER']}, {'bubbles': [{**panel()['bubbles'][0], 'character_id': 'PRIVATE'}]}]:
        response = e.client.post(base + '/records', headers=e.headers, json={**blank(), 'panels': [{**panel(), **patch}]})
        assert response.status_code == 404 and 'PRIVATE' not in response.text


@pytest.mark.parametrize('permissions', [[], ['domain.read'], ['domain.write'], ['domain.review']])
def test_image_permissions_are_separate_and_actor_branch_fenced(mounted, monkeypatch, permissions):
    e = scoped(mounted, monkeypatch); base = e.base + '/comic-layouts'
    created = checked(e.client.post(base + '/records', headers=e.headers, json={**blank(), 'panels': [{**panel(), 'bubbles': []}]}), 201)
    report = checked(e.client.post(base + '/records/' + created['id'] + '/preflight', headers=e.headers, json={'expected_version': 1}))
    image_scope(e, permissions=permissions or ['unused.permission'])
    assert e.client.get(base + '/records', headers=e.headers).status_code == (200 if 'domain.read' in permissions else 403)
    assert e.client.post(base + '/records', headers=e.headers, json=blank()).status_code == (201 if 'domain.write' in permissions else 403)
    response = e.client.post(base + '/records/' + created['id'] + '/approve', headers=e.headers,
        json={'expected_version': 1, 'review_digest': report['review_digest'], 'acknowledge_warnings': True})
    assert response.status_code == (200 if 'domain.review' in permissions else 403)
    assert e.client.get(base + '/records', headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code == 403
    assert e.client.get(base + '/records', headers={'X-Branch-ID': e.branch, 'X-Session-Token': 'wrong'}).status_code == 401


def test_mixed_novel_read_image_write_cannot_mutate_source_page(mounted, monkeypatch):
    from app.authorization import PermissionAssignment
    e = scoped(mounted, monkeypatch); base = e.base + '/comic-layouts'
    page = checked(e.client.post(base + '/records', headers=e.headers, json=blank()), 201)
    service = e.experimental.comic_layouts_service
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections'][service.RECORDS][page['id']]['document']['panels'] = [{**panel(), 'character_ids': ['PRIVATE']}]
    scope = image_scope(e, permissions=['domain.write'])
    e.authorization.assign_permission(PermissionAssignment('novel-read-' + e.role, e.lead, 'domain.read', ModalityDomain.NOVEL, scope, e.lead))
    assert e.client.put(base + '/records/' + page['id'], headers=e.headers, json={**blank(), 'expected_version': 1}).status_code == 404
    assert e.client.post(base + '/records', headers=e.headers, json=blank()).status_code == 201


def test_image_membership_wrong_project_and_recreated_owner_are_denied(mounted, monkeypatch):
    from app.identity import IdentityStatus
    from app.authorization import PermissionAssignment
    e = scoped(mounted, monkeypatch); auth_scope = image_scope(e)
    base = e.base + '/comic-layouts'
    created = checked(e.client.post(base + '/records', headers=e.headers, json=blank()), 201)
    e.authorization.assign_permission(PermissionAssignment('viewer-image-' + e.role, e.viewer, 'domain.read', ModalityDomain.IMAGE, auth_scope, e.lead))
    # The viewer retains NOVEL read, but has no ownership of the author's rows.
    assert checked(e.client.get(base + '/records', headers=e.viewer_headers)) == {'items': []}
    assert e.client.post(base + '/records/' + created['id'] + '/preflight', headers=e.viewer_headers, json={'expected_version': 1}).status_code == 404
    wrong = e.novels.create({'id': 'comic-other-' + uuid.uuid4().hex, 'title': 'Other'})['id']
    e.comic_test_projects.append(wrong)
    assert e.client.get(e.prefix + f'/novels/{wrong}/experimental/comic-layouts/records', headers=e.headers).status_code == 403
    e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    assert e.client.get(base + '/records', headers=e.headers).status_code == 403
    e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.ACTIVE)
    archived = e.store.read(e.nid, e.scope)
    e.novels.delete(e.nid); e.novels.create({'id': e.nid, 'title': 'Recreated'})
    with e.store.transaction(e.nid, e.scope) as state: state.update(copy.deepcopy(archived))
    assert e.client.get(base + '/records', headers=e.headers).status_code == 403
    service = e.experimental.comic_layouts_service
    with service.access_policy(True):
        assert service.records(e.nid, e.scope, e.lead) == {'items': []}
        with pytest.raises(FileNotFoundError): service.preflight(e.nid, e.scope, e.lead, created['id'], 1)
    path = base + '/records/' + created['id']
    for response in [e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': 1}),
                     e.client.post(path + '/restore', headers=e.headers, json={'expected_version': 1, 'target_version': 1})]:
        assert response.status_code == 403
    if e.backend == 'file': assert not (e.root / 'novels' / e.nid / 'creative_project_v2.json').exists()


def test_image_source_free_book_copy_restore_layers_review_and_publication(mounted, monkeypatch):
    import zipfile
    e = scoped(mounted, monkeypatch); image_scope(e)
    base = e.base + '/comic-layouts'
    body = {**blank(), 'panels': [{**panel(), 'bubbles': []}],
        'layer_stack': {'schema_version': 1, 'items': [{'id': 'layer_art', 'kind': 'PANEL_ART', 'target_id': 'panel', 'name': 'Art'}, {'id': 'layer_frame', 'kind': 'PANEL_FRAME', 'target_id': 'panel', 'name': 'Frame'}]}}
    # Opted-in layer schema is the original schema, not an IMAGE-specific DTO.
    page = checked(e.client.post(base + '/records', headers=e.headers, json=body), 201)
    path = base + '/records/' + page['id']
    preflight = checked(e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': 1}))
    page = checked(e.client.post(path + '/approve', headers=e.headers,
        json={'expected_version': 1, 'review_digest': preflight['review_digest'], 'acknowledge_warnings': True}))
    book = checked(e.client.post(base + '/books', headers=e.headers, json={'title': 'Book',
        'chapters': [{'id': 'chapter', 'title': 'Chapter', 'pages': [page['id']]}],
        'expected_page_versions': {page['id']: page['version']}}), 201)
    book_path = base + '/books/' + book['id']
    receipt = checked(e.client.post(book_path + '/publication-preflight', headers=e.headers,
        json={'expected_version': 1, 'reading_direction': 'LTR'}))
    exported = e.client.post(book_path + '/export-cbz', headers=e.headers,
        json={'expected_version': 1, 'reading_direction': 'LTR', 'pages': receipt['pages'], 'publication_digest': receipt['publication_digest']})
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive: assert archive.testzip() is None
    copied = checked(e.client.post(book_path + '/pages', headers=e.headers,
        json={'expected_version': 1, 'chapter_id': 'chapter', 'source_layout_id': page['id'], 'expected_source_version': page['version']}), 201)
    assert copied['page']['document']['panels'][0]['id'] != 'panel'
    restored = checked(e.client.post(book_path + '/restore', headers=e.headers,
        json={'expected_version': 2, 'target_version': 1}))
    assert restored['version'] == 3 and restored['chapters'][0]['pages'] == [page['id']]
