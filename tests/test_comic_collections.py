"""Manual Comic books persist through the original owner and raw transaction."""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from pydantic import ValidationError
from app.experimental.comic_collections import ComicBookIn, ComicBookPageIn
from app.experimental.comic_layouts import ComicLayoutsService
from app.experimental.store import ExperimentalStore
from app.creative.project_store import CreativeProjectStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_comic_independent import original_independent_owner, blank, panel
from test_r3_mounted_contracts import mounted, prefix, checked, scoped


def book_body(pages=()):
    return {'title': '手工漫画册', 'chapters': [{'id': 'one', 'title': '第一章', 'pages': list(pages)},
                                         {'id': 'two', 'title': '第二章', 'pages': []}]}


def create_book(e, headers=None):
    return checked(e.client.post(e.base + '/comic-layouts/books', json=book_body(), headers=headers or {}), 201)


def fields(book, versions=None):
    return {k: copy.deepcopy(book[k]) for k in ('title', 'chapters')} | {'expected_page_versions': versions or {}, 'expected_version': book['version']}


def test_mounted_book_order_copy_remove_restore_reopen(mounted):
    e = mounted; service = e.experimental.comic_layouts_service
    original_sources = (e.chapters.list(e.nid), e.screenplays.list(e.nid), e.assets.list(e.nid))
    book = create_book(e); path = e.base + '/comic-layouts/books/' + book['id']
    result = checked(e.client.post(path + '/pages', json={'expected_version': 1, 'chapter_id': 'one'}), 201)
    page, book = result['page'], result['book']
    body = {**blank(), 'panels': [panel()]}
    page = service.save(e.nid, e.scope, 'local-author', body, rid=page['id'], expected_version=page['version'])
    original = copy.deepcopy(service._row(e.nid, e.scope, 'local-author', page['id']))
    result = checked(e.client.post(path + '/pages', json={'expected_version': book['version'], 'chapter_id': 'two',
                'source_layout_id': page['id'], 'expected_source_version': page['version']}), 201)
    copied, book = result['page'], result['book']; copy_id = copied['id']
    assert copied['id'] != page['id'] and copied['status'] == 'DRAFT' and copied['version'] == 1
    a, b = page['document']['panels'][0], copied['document']['panels'][0]
    assert a['id'] != b['id'] and a['bubbles'][0]['id'] != b['bubbles'][0]['id']
    assert {k:v for k,v in a.items() if k not in ('id','bubbles')} == {k:v for k,v in b.items() if k not in ('id','bubbles')}
    assert {k:v for k,v in a['bubbles'][0].items() if k != 'id'} == {k:v for k,v in b['bubbles'][0].items() if k != 'id'}
    assert 'cover_x_percent' not in b
    assert service._row(e.nid, e.scope, 'local-author', page['id']) == original
    reordered = fields(book, {page['id']: page['version'], copy_id: 1})
    reordered['chapters'].reverse()
    reordered['chapters'][0]['pages'] = [copy_id, page['id']]; reordered['chapters'][1]['pages'] = []
    book = checked(e.client.put(path, json=reordered)); keep_version = book['version']
    removed = fields(book); removed['chapters'] = []
    book = checked(e.client.put(path, json=removed))
    assert len(service.records(e.nid, e.scope, 'local-author')['items']) == 2
    restored = checked(e.client.post(path + '/restore', json={'expected_version': book['version'], 'target_version': keep_version}))
    assert restored['chapters'] == reordered['chapters'] and restored['snapshot_scope'] == 'STRUCTURE_ONLY'
    store = ExperimentalStore(e.root, e.backend, e.url)
    reopened = ComicLayoutsService(store, e.novels, e.chapters, e.screenplays, e.assets, independent_store=CreativeProjectStore(store))
    assert reopened.books(e.nid, e.scope, 'local-author')['items'] == [restored]
    assert set(store.read(e.nid, e.scope)['collections']) == {'comic_layouts_v2', 'comic_page_collections_v1'}
    assert (e.chapters.list(e.nid), e.screenplays.list(e.nid), e.assets.list(e.nid)) == original_sources


def test_attach_requires_current_page_pin_and_cas_private(mounted):
    e = mounted; service = e.experimental.comic_layouts_service; book = create_book(e)
    page = service.save(e.nid, e.scope, 'local-author', blank())
    path = e.base + '/comic-layouts/books/' + book['id']
    body = fields(book); body['chapters'][0]['pages'] = [page['id']]
    assert e.client.put(path, json=body).status_code == 422
    body['expected_page_versions'] = {page['id']: 1}
    service.save(e.nid, e.scope, 'local-author', {**blank(), 'title': 'Secret changed page'}, rid=page['id'], expected_version=1)
    conflict = e.client.put(path, json=body)
    assert conflict.status_code == 409 and 'Secret' not in conflict.text and 'document' not in conflict.text
    body['expected_page_versions'][page['id']] = 2
    saved = checked(e.client.put(path, json=body))
    assert saved['chapters'][0]['pages'] == [page['id']]
    conflict = e.client.put(path, json=body)
    assert conflict.status_code == 409 and book['title'] not in conflict.text and 'chapters' not in conflict.text
    assert conflict.headers['cache-control'] == 'no-store'


def test_restore_changes_only_structure_not_page_content(mounted):
    e = mounted; s = e.experimental.comic_layouts_service; book = create_book(e)
    result = s.book_page(e.nid, e.scope, 'local-author', book['id'], {'expected_version':1, 'chapter_id':'one'})
    page, book = result['page'], result['book']
    removed = fields(book); removed['chapters'] = []
    s.save_book(e.nid,e.scope,'local-author',{k:v for k,v in removed.items() if k != 'expected_version'},rid=book['id'],expected_version=2)
    current = s.save(e.nid,e.scope,'local-author',{**blank(),'title':'New content retained'},rid=page['id'],expected_version=1)
    restored = s.restore_book(e.nid,e.scope,'local-author',book['id'],3,2)
    assert restored['version'] == 4 and restored['chapters'][0]['pages'] == [page['id']]
    assert s.records(e.nid,e.scope,'local-author')['items'] == [current]


@pytest.mark.parametrize('operation', ['blank', 'copy', 'save', 'restore'])
def test_failed_final_guard_rolls_back_entire_scope(mounted, operation):
    e = mounted; s = e.experimental.comic_layouts_service; book = create_book(e)
    page = s.save(e.nid,e.scope,'local-author',blank())
    book = s.save_book(e.nid,e.scope,'local-author',book_body(),rid=book['id'],expected_version=1)
    before = e.store.read(e.nid,e.scope); calls = [0]
    def guard():
        calls[0] += 1
        if calls[0] == 3: raise PermissionError('authority revoked before commit')
    with pytest.raises(PermissionError):
        if operation in ('blank','copy'):
            body = {'expected_version':2,'chapter_id':'one'}
            if operation == 'copy': body.update(source_layout_id=page['id'],expected_source_version=1)
            s.book_page(e.nid,e.scope,'local-author',book['id'],body,guard)
        elif operation == 'save': s.save_book(e.nid,e.scope,'local-author',book_body(),guard,rid=book['id'],expected_version=2)
        else: s.restore_book(e.nid,e.scope,'local-author',book['id'],2,1,guard)
    assert e.store.read(e.nid,e.scope) == before


def test_two_writers_exactly_one_cas_winner(mounted):
    e = mounted; s = e.experimental.comic_layouts_service; book = create_book(e); barrier = Barrier(2)
    def write(title):
        body = {**book_body(), 'title':title}; barrier.wait(timeout=10)
        try: return s.save_book(e.nid,e.scope,'local-author',body,rid=book['id'],expected_version=1)
        except CapabilityVersionConflict: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ['A','B']))
    assert results.count('conflict') == 1
    current = s.books(e.nid,e.scope,'local-author')['items'][0]
    assert current['version'] == 2 and current['history_versions'] == [1]


@pytest.mark.parametrize('patch', [
    {'title':' '}, {'title':'bad\ntext'}, {'chapters':[{'id':'a','title':'A','pages':['p','p']}]},
    {'chapters':[{'id':'a','title':'A'},{'id':'a','title':'B'}]},
    {'expected_page_versions':{'p': True}}, {'expected_page_versions':{'p':'1'}},
    {'chapters':[{'id':str(i),'title':'C'} for i in range(21)]},
])
def test_book_bounded_input(patch):
    with pytest.raises(ValidationError): ComicBookIn.model_validate({**book_body(),**patch})


def test_copy_requires_paired_pin():
    with pytest.raises(ValidationError): ComicBookPageIn.model_validate({'expected_version':1,'chapter_id':'one','source_layout_id':'x'})


def test_legacy_adapted_page_never_attached_or_modified(mounted):
    from test_r5_comic_mounted import create_layout
    e = mounted; page, _, _ = create_layout(e); book = create_book(e)
    before = e.store.read(e.nid,e.scope)
    body = fields(book,{page['id']:page['version']}); body['chapters'][0]['pages'] = [page['id']]
    response = e.client.put(e.base + '/comic-layouts/books/' + book['id'],json=body)
    assert response.status_code == 404 and page['document']['title'] not in response.text
    assert e.store.read(e.nid,e.scope) == before


@pytest.fixture
def collection_scope(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    try:
        yield e
    finally:
        # Only this scoped fixture's generated workspace/users/project. The
        # enclosing mounted owner removes its novel and scope documents later.
        if e.backend == 'postgres':
            with e.store._connect() as connection:
                for table in ('domain_role_assignments', 'permission_assignments', 'authorization_audit_events'):
                    connection.execute(f"DELETE FROM {table} WHERE payload->'scope'->>'workspace_id'=%s", (e.workspace,))
                connection.execute('DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id IN (%s,%s)', (e.workspace, e.lead, e.viewer))
                for table in ('storyline_branches', 'storylines'):
                    connection.execute(f"DELETE FROM {table} WHERE payload->>'workspace_id'=%s AND payload->>'project_id'=%s", (e.workspace, e.nid))
                connection.execute('DELETE FROM project_workspaces WHERE project_id=%s AND workspace_id=%s', (e.nid, e.workspace))
                connection.execute("UPDATE novels SET workspace_id='default-workspace' WHERE slug=%s AND workspace_id=%s", (e.nid, e.workspace))
                connection.execute('DELETE FROM workspaces WHERE id=%s', (e.workspace,))
                connection.execute('DELETE FROM users WHERE id IN (%s,%s)', (e.lead, e.viewer))


def test_books_actor_branch_permissions_and_stale_projection(collection_scope):
    e = collection_scope; book = create_book(e,e.headers)
    path = e.base + '/comic-layouts/books/' + book['id']
    result = checked(e.client.post(path+'/pages',headers=e.headers,json={'expected_version':1,'chapter_id':'one'}),201)
    for headers in [{},e.viewer_headers,{**e.headers,'X-Branch-ID':e.other_branch}]:
        response = e.client.get(e.base+'/comic-layouts/books',headers=headers)
        assert book['id'] not in response.text and book['title'] not in response.text
    denied = e.client.put(path,headers=e.viewer_headers,json=fields(result['book'],{result['page']['id']:1}))
    assert denied.status_code == 403
    # Missing binding cannot disclose chapter/page names, membership or counts.
    with e.store.transaction(e.nid,e.scope) as state:
        state['collections']['comic_layouts_v2'][result['page']['id']].pop('project_incarnation')
    view = checked(e.client.get(e.base+'/comic-layouts/books',headers=e.headers))['items'][0]
    assert view == {'id':book['id'],'version':2,'status':'DRAFT','stale':True}
    e.authorization.revoke_role(e.role,e.lead)
    assert e.client.post(path+'/pages',headers=e.headers,json={'expected_version':2,'chapter_id':'one'}).status_code == 403


def test_old_epoch_books_history_hidden_and_never_adopted(mounted):
    e = mounted; s=e.experimental.comic_layouts_service; book=create_book(e)
    s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':1,'chapter_id':'one'})
    old=e.store.read(e.nid,e.scope)
    e.novels.delete(e.nid); e.novels.create({'id':e.nid,'title':'Replacement'})
    with e.store.transaction(e.nid,e.scope) as state: state.update(copy.deepcopy(old))
    assert s.books(e.nid,e.scope,'local-author') == {'items':[]}
    for operation in [lambda:s.restore_book(e.nid,e.scope,'local-author',book['id'],2,1),
                      lambda:s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':2,'chapter_id':'one'}),
                      lambda:s.save_book(e.nid,e.scope,'local-author',book_body(),rid=book['id'],expected_version=2)]:
        with pytest.raises(FileNotFoundError): operation()
    assert e.store.read(e.nid,e.scope)==old
    if e.backend=='file': assert not (e.root/'novels'/e.nid/'creative_project_v2.json').exists()
    new=s.save_book(e.nid,e.scope,'local-author',book_body())
    assert [b['id'] for b in s.books(e.nid,e.scope,'local-author')['items']]==[new['id']]
    assert e.store.read(e.nid,e.scope)['collections'][s.BOOKS][book['id']]==old['collections'][s.BOOKS][book['id']]


def test_book_reads_denied_invalid_create_no_epoch(mounted):
    e=mounted;s=e.experimental.comic_layouts_service
    assert s.books(e.nid,e.scope,'local-author')=={'items':[]}
    def denied():raise PermissionError('denied')
    with pytest.raises(PermissionError):s.save_book(e.nid,e.scope,'local-author',book_body(),denied)
    with pytest.raises(ValidationError):s.save_book(e.nid,e.scope,'local-author',{'title':''})
    with pytest.raises(FileNotFoundError):s.save_book(e.nid,e.scope,'local-author',{**book_body(['missing']),'expected_page_versions':{'missing':1}})
    assert e.store.read(e.nid,e.scope)['collections']=={}
    if e.backend=='file':assert not (e.root/'novels'/e.nid/'creative_project_v2.json').exists()


def test_copy_source_edit_between_admission_and_commit_is_rejected(mounted):
    e=mounted;s=e.experimental.comic_layouts_service;book=create_book(e)
    page=s.save(e.nid,e.scope,'local-author',blank());calls=[0]
    def guard():
        calls[0]+=1
        if calls[0]==1:
            s.save(e.nid,e.scope,'local-author',{**blank(),'title':'Racing edit'},rid=page['id'],expected_version=1)
    with pytest.raises(CapabilityVersionConflict):
        s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':1,'chapter_id':'one','source_layout_id':page['id'],'expected_source_version':1},guard)
    assert len(s.records(e.nid,e.scope,'local-author')['items'])==1
    assert s.books(e.nid,e.scope,'local-author')['items'][0]==book


def test_book_asset_and_original_project_locks_outlive_commit(mounted,monkeypatch):
    if mounted.backend!='file':pytest.skip('File atomic commit instrumentation')
    from contextlib import contextmanager
    import app.experimental.comic_layouts as module
    import app.experimental.store as store_module
    e=mounted;s=e.experimental.comic_layouts_service;owner=s.independent_store
    original_workspace=module.workspace_mutation;original_owner=owner.owner_lease;original_write=store_module.atomic_write
    assets=[False];project=[False];commits=[]
    @contextmanager
    def workspace(root,key):
        with original_workspace(root,key):
            if key=='asset-library':assets[0]=True
            try:yield
            finally:
                if key=='asset-library':assets[0]=False
    @contextmanager
    def lease(nid):
        assert e.assets._lock._is_owned() and assets[0]
        with original_owner(nid) as identity:
            project[0]=True
            try:yield identity
            finally:project[0]=False
    def write(path,content):
        if path==e.store.path(e.nid,e.scope):
            assert assets[0] and project[0] and e.assets._lock._is_owned();commits.append(True)
        return original_write(path,content)
    monkeypatch.setattr(module,'workspace_mutation',workspace);monkeypatch.setattr(owner,'owner_lease',lease);monkeypatch.setattr(store_module,'atomic_write',write)
    book=create_book(e)
    result=s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':1,'chapter_id':'one'})
    s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':2,'chapter_id':'two','source_layout_id':result['page']['id'],'expected_source_version':1})
    s.save_book(e.nid,e.scope,'local-author',book_body(),rid=book['id'],expected_version=3)
    s.restore_book(e.nid,e.scope,'local-author',book['id'],4,3)
    assert len(commits)==5


def test_file_failed_copy_commit_retains_exact_scope(mounted,monkeypatch):
    if mounted.backend!='file':pytest.skip('File atomic write failure')
    import app.experimental.store as store_module
    e=mounted;s=e.experimental.comic_layouts_service;book=create_book(e)
    page=s.save(e.nid,e.scope,'local-author',blank());before=e.store.read(e.nid,e.scope)
    original=store_module.atomic_write
    def fail(path,content):
        if path==e.store.path(e.nid,e.scope):raise OSError('synthetic failed atomic commit')
        return original(path,content)
    monkeypatch.setattr(store_module,'atomic_write',fail)
    with pytest.raises(OSError):s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':1,'chapter_id':'one','source_layout_id':page['id'],'expected_source_version':1})
    assert e.store.read(e.nid,e.scope)==before


@pytest.mark.parametrize('flags', ['', 'comic_layouts_v2'])
def test_collection_routes_flags_fail_closed(mounted,monkeypatch,flags):
    e=mounted;monkeypatch.setenv('EXPERIMENTAL_FEATURES',flags)
    for method,path,body in [('get','/books',None),('post','/books',book_body()),
            ('put','/books/missing',{**book_body(),'expected_version':1}),
            ('post','/books/missing/pages',{'expected_version':1,'chapter_id':'one'}),
            ('post','/books/missing/restore',{'expected_version':1,'target_version':1})]:
        response=getattr(e.client,method)(e.base+'/comic-layouts'+path,**({'json':body} if body is not None else {}))
        assert response.status_code==404 and response.headers['cache-control']=='no-store'
    assert not e.store.read(e.nid,e.scope)['collections'].get('comic_page_collections_v1')


def test_approved_image_page_copy_is_new_draft_and_asset_unchanged(mounted):
    import base64
    from test_r5_comic_layouts import synthetic_png
    e=mounted;s=e.experimental.comic_layouts_service;book=create_book(e)
    asset=e.assets.create(e.nid,'synthetic-comic-page.png',base64.b64encode(synthetic_png()).decode(),'image/png')
    approved=s.approve_image(e.nid,e.scope,'local-author',asset['id'],asset['version'])
    body={**blank(),'panels':[{**panel(),'artwork_mode':'IMAGE','asset_id':asset['id'],'expected_asset_version':approved['version'],'bubbles':[]}]}
    page=s.save(e.nid,e.scope,'local-author',body)
    report=s.preflight(e.nid,e.scope,'local-author',page['id'],1)
    page=s.approve(e.nid,e.scope,'local-author',page['id'],1,report['review_digest'],True)
    before_asset=e.assets.get(asset['id']);before_page=s._row(e.nid,e.scope,'local-author',page['id'])
    copied=s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':1,'chapter_id':'one','source_layout_id':page['id'],'expected_source_version':2})['page']
    raw=s._row(e.nid,e.scope,'local-author',copied['id'])
    assert raw['status']=='DRAFT' and raw['approval'] is None and raw['history']==[]
    assert raw['asset_sources']==before_page['asset_sources'] and e.assets.get(asset['id'])==before_asset
    assert s._row(e.nid,e.scope,'local-author',page['id'])==before_page
    # A later asset mutation prevents both copying and structure recovery from
    # silently adopting the new approved-version binding.
    e.assets.update_metadata(asset['id'],{'parameters':{'synthetic_change':True}})
    before=e.store.read(e.nid,e.scope)
    with pytest.raises(ValueError):s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':2,'chapter_id':'one','source_layout_id':page['id'],'expected_source_version':2})
    assert e.store.read(e.nid,e.scope)==before
    view=s.books(e.nid,e.scope,'local-author')['items'][0]
    assert set(view)=={'id','version','status','stale'} and view['stale']


def test_old_epoch_and_other_actor_do_not_consume_book_quota(mounted):
    e=mounted;s=e.experimental.comic_layouts_service;book=create_book(e)
    with e.store.transaction(e.nid,e.scope) as state:
        row=state['collections'][s.BOOKS][book['id']]
        archived=copy.deepcopy(row);archived.update(id='archived-owner-book',project_incarnation='file:retired-owner')
        archived['retained_archive_bytes']='x'*8_000_001
        other=copy.deepcopy(row);other.update(id='other-actor-book',created_by='other-actor')
        other['retained_archive_bytes']='y'*8_000_001
        state['collections'][s.BOOKS][archived['id']]=archived
        state['collections'][s.BOOKS][other['id']]=other
    before=e.store.read(e.nid,e.scope)
    created=s.save_book(e.nid,e.scope,'local-author',book_body())
    after=e.store.read(e.nid,e.scope)
    assert after['collections'][s.BOOKS][archived['id']]==before['collections'][s.BOOKS][archived['id']]
    assert after['collections'][s.BOOKS][other['id']]==before['collections'][s.BOOKS][other['id']]
    assert {b['id'] for b in s.books(e.nid,e.scope,'local-author')['items']}=={book['id'],created['id']}


def test_book_projection_holds_scope_until_all_page_checks_finish(mounted,monkeypatch):
    from threading import Event
    e=mounted;s=e.experimental.comic_layouts_service;book=create_book(e)
    result=s.book_page(e.nid,e.scope,'local-author',book['id'],{'expected_version':1,'chapter_id':'one'})
    pid=result['page']['id'];started,finished=Event(),Event();futures=[]
    original=s._book_page;checks=[0]
    def invalidate():
        started.set()
        with e.store.transaction(e.nid,e.scope) as state:
            state['collections'][s.RECORDS][pid].pop('project_incarnation')
        finished.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        def checked_page(*args,**kwargs):
            checks[0]+=1
            if checks[0]==1:
                futures.append(pool.submit(invalidate));assert started.wait(3)
                assert not finished.wait(.05),'page invalidation escaped the coherent book projection lease'
            return original(*args,**kwargs)
        monkeypatch.setattr(s,'_book_page',checked_page)
        view=s.books(e.nid,e.scope,'local-author')['items'][0]
        assert not view['stale'] and view['chapters'][0]['pages']==[pid]
        for future in futures:future.result(timeout=10)
    assert finished.is_set()
    assert s.books(e.nid,e.scope,'local-author')['items']==[{'id':book['id'],'version':2,'status':'DRAFT','stale':True}]


def test_epoch_replacement_before_projection_leaks_no_old_book_id(mounted,monkeypatch):
    from contextlib import contextmanager
    e=mounted;s=e.experimental.comic_layouts_service;book=create_book(e);old=e.store.read(e.nid,e.scope)
    original=s._independent_transaction;replaced=[False]
    @contextmanager
    def race(*args,**kwargs):
        if not replaced[0]:
            replaced[0]=True;e.novels.delete(e.nid);e.novels.create({'id':e.nid,'title':'Replacement'})
            with e.store.transaction(e.nid,e.scope) as state:state.update(copy.deepcopy(old))
        with original(*args,**kwargs) as state:yield state
    monkeypatch.setattr(s,'_independent_transaction',race)
    assert s.books(e.nid,e.scope,'local-author')=={'items':[]}
    assert e.store.read(e.nid,e.scope)==old
    if e.backend=='file':assert not (e.root/'novels'/e.nid/'creative_project_v2.json').exists()
