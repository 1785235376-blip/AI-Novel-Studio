"""Native editable assetless author archive; original File/PG owner parity."""
import base64
import copy
import hashlib
import io
import json
import stat
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.experimental import comic_author_archive as a
from app.experimental.comic_layouts import ComicLayoutsService
from app.experimental.store import ExperimentalStore, canonical
from app.creative.project_store import CreativeProjectStore
from test_comic_independent import original_independent_owner, blank, panel
from test_comic_collections import book_body
from test_r3_mounted_contracts import mounted, checked, prefix


def source(e, actor='local-author'):
    s = e.experimental.comic_layouts_service
    doc = {**blank(),'panels':[panel()]}
    doc['panels'][0]['image_brief'] = 'Private future artwork brief'
    doc['layer_stack'] = {'schema_version':1,'items':[
        {'id':'layer_'+str(i),'kind':kind,'target_id':target,'name':kind,'visible':i != 3,'opacity_percent':65}
        for i,(kind,target) in enumerate([('PANEL_ART','panel'),('PANEL_FRAME','panel'),
                                         ('BUBBLE_SHAPE','dialogue'),('BUBBLE_TEXT','dialogue')])]}
    page = s.save(e.nid,e.scope,actor,doc)
    body = book_body([page['id']]); body['expected_page_versions'] = {page['id']:1}
    book = s.save_book(e.nid,e.scope,actor,body)
    return s,page,book


def exported(e):
    s,page,book = source(e); path = e.base+'/comic-layouts/books/'+book['id']
    preview = checked(e.client.post(path+'/author-archive-preview',json={'expected_version':1}))
    response = e.client.post(path+'/export-author-archive',json={'expected_version':1,
        'export_digest':preview['export_digest'],'acknowledge_author_content':True})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    raw = response.content
    return s,page,book,raw


def request(e,raw):
    envelope = {'archive_base64':base64.b64encode(raw).decode(),'archive_sha256':hashlib.sha256(raw).hexdigest()}
    inspection = checked(e.client.post(e.base+'/comic-layouts/author-archive/inspect',json=envelope))
    return {**envelope,'inspection_digest':inspection['inspection_digest'],
            'request_key':uuid.uuid4().hex,'acknowledge_restore_drafts':True}


def test_mounted_export_inspect_restore_reopen_edit_save_replay(mounted):
    e=mounted; s,page,book,raw=exported(e)
    old = copy.deepcopy(s.store.read(e.nid,e.scope)); before_assets=e.assets.list(e.nid)
    body=request(e,raw)
    assert s.store.read(e.nid,e.scope)==old
    restored=checked(e.client.post(e.base+'/comic-layouts/author-archive/restore',json=body))
    target=restored['pages'][0]; target_book=restored['book']
    assert target['id']!=page['id'] and target_book['id']!=book['id']
    assert target['status']=='DRAFT' and target['history_versions']==[]
    assert a._remap(target['document'],True)==a._remap(page['document'],True)
    assert target['document']['panels'][0]['id']!=page['document']['panels'][0]['id']
    assert target['document']['panels'][0]['bubbles'][0]['id']!=page['document']['panels'][0]['bubbles'][0]['id']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text=''.join(z.read(n).decode() for n in z.namelist())
        assert 'Private future artwork brief' in text
        for forbidden in (page['id'],book['id'],'local-author','approval','project_incarnation','history','created_by'):
            assert forbidden not in text
    store=ExperimentalStore(e.root,e.backend,e.url)
    reopened=ComicLayoutsService(store,e.novels,e.chapters,e.screenplays,e.assets,independent_store=CreativeProjectStore(store))
    document=copy.deepcopy(target['document'])
    document['panels'][0]['bubbles'][0]['text']='Edited imported native text'
    document['panels'][0]['x']=30
    document['layer_stack']['items'].reverse(); document['layer_stack']['items'][0]['visible']=True
    updated=reopened.save(e.nid,e.scope,'local-author',document,rid=target['id'],expected_version=1)
    replay=checked(e.client.post(e.base+'/comic-layouts/author-archive/restore',json=body))
    assert replay['replayed'] and replay['pages']==[updated] and replay['book']==target_book
    assert replay['result_state']=='CURRENT_EDITABLE_ROWS_FROM_COMPLETED_IMPORT'
    assert e.assets.list(e.nid)==before_assets
    assert s._row(e.nid,e.scope,'local-author',page['id'])==old['collections'][s.RECORDS][page['id']]
    assert len(store.read(e.nid,e.scope)['collections'][a.RECEIPTS])==1


def repack(raw, transform):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive: files={n:archive.read(n) for n in archive.namelist()}
    transform(files)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for name,data in files.items():
            item=zipfile.ZipInfo(name);item.external_attr=(stat.S_IFREG|0o600)<<16
            archive.writestr(item,data)
    return stream.getvalue()


def mutate_document(raw, mutator):
    def transform(files):
        doc=json.loads(files['pages/000.json']);mutator(doc)
        files['pages/000.json']=canonical(doc).encode()
        manifest=json.loads(files['manifest.json']);entry=manifest['pages'][0]
        entry['bytes']=len(files['pages/000.json']);entry['sha256']=hashlib.sha256(files['pages/000.json']).hexdigest()
        files['manifest.json']=canonical(manifest).encode()
    return repack(raw,transform)


@pytest.mark.parametrize('field,value', [('asset_id','foreign'),('expected_asset_version',1),('character_ids',['foreign']),
    ('shot_id','foreign'),('appearance_references',[{'character_id':'foreign','asset_id':'foreign','expected_asset_version':1}])])
def test_dependency_rejected_without_writes(mounted,field,value):
    e=mounted;s,_,_,raw=exported(e);old=s.store.read(e.nid,e.scope)
    raw=mutate_document(raw,lambda d:d['panels'][0].update({field:value}))
    envelope={'archive_base64':base64.b64encode(raw).decode(),'archive_sha256':hashlib.sha256(raw).hexdigest()}
    assert e.client.post(e.base+'/comic-layouts/author-archive/inspect',json=envelope).status_code==422
    assert s.store.read(e.nid,e.scope)==old


@pytest.mark.parametrize('attack',['unknown','hash','undeclared','traversal','duplicate','symlink','encrypted','compressed','depth','duplicate-json','nonfinite','wrong-alias','trailing','prefix','local-mismatch','authority','webtoon','character','raster'])
def test_untrusted_archive_rejected(mounted,attack):
    e=mounted;s,_,_,raw=exported(e)
    if attack=='unknown': raw=repack(raw,lambda f:f.update({'manifest.json':b'{"contract":"bad"}'}))
    elif attack=='hash': raw=repack(raw,lambda f:f.update({'pages/000.json':b'{}'}))
    elif attack in ('undeclared','traversal'): raw=repack(raw,lambda f:f.update({'extra.json' if attack=='undeclared' else '../page.json':b'{}'}))
    elif attack=='depth': raw=repack(raw,lambda f:f.update({'manifest.json':b'['*100+b']'*100}))
    elif attack=='duplicate-json': raw=repack(raw,lambda f:f.update({'manifest.json':b'{"contract":1,"contract":2}'}))
    elif attack=='nonfinite': raw=repack(raw,lambda f:f.update({'manifest.json':b'{"value":NaN}'}))
    elif attack=='wrong-alias': raw=mutate_document(raw,lambda d:d['panels'][0].update(id='persistent-source-id'))
    elif attack=='authority': raw=mutate_document(raw,lambda d:d.update(approval={'actor':'admin'}))
    elif attack=='webtoon': raw=mutate_document(raw,lambda d:d.update(preset='WEBTOON'))
    elif attack=='character': raw=mutate_document(raw,lambda d:d['panels'][0]['bubbles'][0].update(character_id='foreign'))
    elif attack=='raster': raw=mutate_document(raw,lambda d:d['layer_stack']['items'].append({'id':'layer_r','kind':'RASTER','target_id':'foreign','name':'foreign','x':0,'y':0,'width':1,'height':1,'pin':{'version':2,'sha256':'0'*64,'review_digest':'0'*64}}))
    elif attack=='trailing':raw+=b'junk'
    elif attack=='prefix':raw=b'junk'+raw
    elif attack=='local-mismatch':raw=raw[:14]+b'\x00'*4+raw[18:]
    else:
        with zipfile.ZipFile(io.BytesIO(raw)) as z: files={n:z.read(n) for n in z.namelist()}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED if attack=='compressed' else zipfile.ZIP_STORED) as z:
            for name,data in files.items():
                if attack=='symlink':
                    item=zipfile.ZipInfo(name);item.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(item,data)
                else:z.writestr(name,data)
            if attack=='duplicate':z.writestr('manifest.json',files['manifest.json'])
        raw=stream.getvalue()
        if attack=='encrypted':raw=raw[:6]+b'\x01\x00'+raw[8:]
    with pytest.raises(ValueError):a.decode(raw)


def test_explicit_ack_pins_limits_and_rollback(mounted):
    e=mounted;s,page,book,raw=exported(e);body=request(e,raw);before=s.store.read(e.nid,e.scope)
    path=e.base+'/comic-layouts/author-archive/restore'
    assert e.client.post(path,json={**body,'acknowledge_restore_drafts':False}).status_code==409
    assert e.client.post(path,json={**body,'acknowledge_restore_drafts':1}).status_code==422
    assert e.client.post(path,json={**body,'inspection_digest':'0'*64}).status_code==409
    def late_guard():
        active=s.store.read(e.nid,e.scope)
        if a.RECEIPTS in active['collections']:raise ValueError('late revoke')
    with pytest.raises(ValueError,match='late revoke'):
        a.restore_archive(s,e.nid,e.scope,'local-author',raw,a.RestoreIn.model_validate(body),late_guard)
    assert s.store.read(e.nid,e.scope)==before
    previews=checked(e.client.post(e.base+'/comic-layouts/books/'+book['id']+'/author-archive-preview',json={'expected_version':1}))
    s.save(e.nid,e.scope,'local-author',{**page['document'],'title':'Changed'},rid=page['id'],expected_version=1)
    r=e.client.post(e.base+'/comic-layouts/books/'+book['id']+'/export-author-archive',json={
        'expected_version':1,'export_digest':previews['export_digest'],'acknowledge_author_content':True})
    assert r.status_code==409


def test_concurrent_restore_lost_ack_and_changed_membership(mounted):
    e=mounted;s,_,_,raw=exported(e);body=a.RestoreIn.model_validate(request(e,raw))
    def run():return a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:run(),range(2)))
    assert results[0]['book']['id']==results[1]['book']['id']
    assert sorted(r['replayed'] for r in results)==[False,True]
    book=results[0]['book'];s.save_book(e.nid,e.scope,'local-author',{'title':book['title'],'chapters':[]},rid=book['id'],expected_version=1)
    before=s.store.read(e.nid,e.scope)
    with pytest.raises(ValueError,match='ALREADY_COMPLETED'):run()
    assert s.store.read(e.nid,e.scope)==before


def test_hash_collision_receipt_capacity_and_original_quota(mounted):
    e=mounted;s,_,_,raw=exported(e);body=a.RestoreIn.model_validate(request(e,raw))
    result=a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)
    changed=mutate_document(raw,lambda d:d.update(title='Different archive'))
    changed_body=a.RestoreIn.model_validate({**request(e,changed),'request_key':body.request_key})
    before=s.store.read(e.nid,e.scope)
    with pytest.raises(ValueError,match='REQUEST_CONFLICT'):
        a.restore_archive(s,e.nid,e.scope,'local-author',changed,changed_body,lambda:None)
    assert s.store.read(e.nid,e.scope)==before
    with s._independent_transaction(e.nid,e.scope) as state:
        original=next(iter(state['collections'][a.RECEIPTS].values()))
        for i in range(19):
            key=uuid.uuid4().hex
            state['collections'][a.RECEIPTS][a.digest(['local-author',e.scope,original['incarnation'],key])]={**original,'request_key':key}
    report=a.inspect_archive(s,e.nid,e.scope,'local-author',raw,lambda:None)
    assert report['receipt_capacity']==20 and report['receipt_remaining']==0
    before=s.store.read(e.nid,e.scope)
    with pytest.raises(ValueError,match='RECEIPT_LIMIT'):
        a.restore_archive(s,e.nid,e.scope,'local-author',raw,a.RestoreIn.model_validate(request(e,raw)),lambda:None)
    assert s.store.read(e.nid,e.scope)==before
    assert a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)['replayed']


@pytest.mark.parametrize('after_commit',[False,True])
def test_original_scope_commit_failure_replay(mounted,monkeypatch,after_commit):
    e=mounted;s,_,_,raw=exported(e);body=a.RestoreIn.model_validate(request(e,raw))
    before=s.store.read(e.nid,e.scope)
    from contextlib import contextmanager
    original=s.store.transaction
    @contextmanager
    def failing(nid,scope):
        with original(nid,scope) as state:
            yield state
            if not after_commit:raise OSError('injected before scope commit')
        if after_commit:raise OSError('lost commit acknowledgement')
    monkeypatch.setattr(s.store,'transaction',failing)
    with pytest.raises(OSError):a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)
    monkeypatch.setattr(s.store,'transaction',original)
    interim=s.store.read(e.nid,e.scope)
    if not after_commit:assert interim==before
    result=a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)
    assert result['replayed']==after_commit
    assert len(s.store.read(e.nid,e.scope)['collections'][a.RECEIPTS])==1


def test_absent_owner_preview_and_restore_never_provision(mounted):
    e=mounted;s,_,_,raw=exported(e)
    nid='archive-empty-'+uuid.uuid4().hex
    checked(e.client.post(e.prefix+'/novels',json={'id':nid,'title':'Empty target'}),201)
    e.comic_test_projects.append(nid)
    scope={'mode':'local','novel_id':nid}
    before=s.store.read(nid,scope)
    envelope={'archive_base64':base64.b64encode(raw).decode(),'archive_sha256':hashlib.sha256(raw).hexdigest()}
    result=e.client.post(e.prefix+f'/novels/{nid}/experimental/comic-layouts/author-archive/inspect',json=envelope)
    assert result.status_code in ((404,422) if e.backend=='file' else (200,))
    assert s.store.read(nid,scope)==before
    if e.backend=='file':
        with pytest.raises((FileNotFoundError,ValueError)):s._independent_identity(nid)


from test_comic_ora_mounted_authority import ora


def test_real_session_role_branch_and_flag_authority(ora,monkeypatch):
    e=ora;s,page,book=source(e,e.lead)
    path=e.base+'/comic-layouts/books/'+book['id']+'/author-archive-preview'
    assert e.client.post(path,json={'expected_version':1}).status_code==401
    assert e.client.post(path,json={'expected_version':1},headers=e.viewer_headers).status_code==403
    assert e.client.post(path,json={'expected_version':1},headers={**e.headers,'X-Branch-ID':e.other_branch}).status_code==403
    assert e.client.post(path,json={'expected_version':1},headers=e.headers).status_code==200
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','comic_layouts_v2,asset_lineage_v2')
    denied=e.client.post(path,json={'expected_version':1},headers=e.headers)
    assert denied.status_code==404 and denied.headers['cache-control']=='no-store'


def test_cross_project_transfer_and_old_owner_receipts(mounted):
    e=mounted;s,page,book,raw=exported(e)
    source_state=s.store.read(e.nid,e.scope)
    nid=e.novels.create({'id':'comic-author-destination-'+uuid.uuid4().hex,'title':'Destination'})['id']
    e.comic_test_projects.append(nid);scope={'mode':'local','novel_id':nid}
    # Explicit original create activates the destination owner; inspection cannot.
    s.save_book(nid,scope,'local-author',{'title':'Destination book','chapters':[]})
    report=a.inspect_archive(s,nid,scope,'local-author',raw,lambda:None)
    envelope={'archive_base64':base64.b64encode(raw).decode(),'archive_sha256':report['archive_sha256'],
              'inspection_digest':report['inspection_digest'],'request_key':uuid.uuid4().hex,'acknowledge_restore_drafts':True}
    body=a.RestoreIn.model_validate(envelope)
    result=a.restore_archive(s,nid,scope,'local-author',raw,body,lambda:None)
    assert a._remap(result['pages'][0]['document'],True)==a._remap(page['document'],True)
    assert s.store.read(e.nid,e.scope)==source_state
    discovered=a.inspect_archive(s,nid,scope,'local-author',raw,lambda:None)
    assert discovered['completed_attempts']==[{'request_key':body.request_key,'result_state':'COMPLETED'}]
    archived=s.store.read(nid,scope)
    old_identity=s._independent_identity(nid)
    e.novels.delete(nid);e.novels.create({'id':nid,'title':'Recreated owner'})
    with s.store.transaction(nid,scope) as state:state.update(copy.deepcopy(archived))
    s.save_book(nid,scope,'local-author',{'title':'New owner book','chapters':[]})
    assert s._independent_identity(nid)!=old_identity
    before=s.store.read(nid,scope)
    with pytest.raises(ValueError,match='PREVIEW_CHANGED'):
        a.restore_archive(s,nid,scope,'local-author',raw,body,lambda:None)
    assert s.store.read(nid,scope)==before
    fresh=a.inspect_archive(s,nid,scope,'local-author',raw,lambda:None)
    assert fresh['completed_attempts']==[] and fresh['receipt_remaining']==20
    assert len(s.books(nid,scope,'local-author')['items'])==1


@pytest.mark.parametrize('change',['missing-page','foreign-page','old-owner-page','missing-book','foreign-book'])
def test_completed_receipt_unavailable_never_recreates(mounted,change):
    e=mounted;s,_,_,raw=exported(e);body=a.RestoreIn.model_validate(request(e,raw))
    result=a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)
    with s._independent_transaction(e.nid,e.scope) as state:
        page=state['collections'][s.RECORDS][result['pages'][0]['id']]
        book=state['collections'][s.BOOKS][result['book']['id']]
        if change=='missing-page':del state['collections'][s.RECORDS][page['id']]
        if change=='foreign-page':page['created_by']='foreign'
        if change=='old-owner-page':page['project_incarnation']='file:'+str(uuid.uuid4())
        if change=='missing-book':del state['collections'][s.BOOKS][book['id']]
        if change=='foreign-book':book['created_by']='foreign'
    before=s.store.read(e.nid,e.scope)
    with pytest.raises(ValueError,match='ALREADY_COMPLETED_RESULTS_CHANGED_OR_UNAVAILABLE'):
        a.restore_archive(s,e.nid,e.scope,'local-author',raw,body,lambda:None)
    assert s.store.read(e.nid,e.scope)==before


@pytest.mark.parametrize('drift',['permission','incarnation','overflow'])
@pytest.mark.parametrize('length',[None,'1'])
def test_actual_authority_changes_during_stream_before_processing(ora,monkeypatch,drift,length):
    import asyncio
    from contextlib import contextmanager
    from fastapi import HTTPException
    from starlette.requests import Request
    import app.experimental.comic_author_archive_api as routes
    e=ora;s,page,book=source(e,e.lead)
    preview=a.export_preview(s,e.nid,e.scope,e.lead,book['id'],a.ExportPreviewIn(expected_version=1),lambda:None)
    raw=a.export_archive(s,e.nid,e.scope,e.lead,book['id'],a.ExportIn(expected_version=1,export_digest=preview['export_digest'],acknowledge_author_content=True),lambda:None)
    report=a.inspect_archive(s,e.nid,e.scope,e.lead,raw,lambda:None)
    payload=json.dumps({'archive_base64':base64.b64encode(raw).decode(),'archive_sha256':report['archive_sha256'],
                       'inspection_digest':report['inspection_digest'],'request_key':uuid.uuid4().hex,'acknowledge_restore_drafts':True}).encode()
    before=s.store.read(e.nid,e.scope);state={'receives':0,'changed':False,'leased':0}
    original=s._independent_owner().incarnation
    def incarnation(nid):return 'file:'+str(uuid.UUID(int=0)) if state['changed'] else original(nid)
    monkeypatch.setattr(s._independent_owner(),'incarnation',incarnation)
    @contextmanager
    def lease(*args):
        with e.api._workbench_authority_lease(*args):
            state['leased']+=1
            try:yield
            finally:state['leased']-=1
    router=routes.create_comic_author_archive_router(s,e.experimental.authorize,e.experimental.require_flag,authority_lease=lease)
    endpoint=next(r.endpoint for r in router.routes if r.path.endswith('/author-archive/restore'))
    def forbidden(*args,**kwargs):pytest.fail('No restore after streamed authority change')
    monkeypatch.setattr(routes,'restore_archive',forbidden)
    if drift=='overflow':monkeypatch.setattr(routes,'MAX_BODY',50)
    async def receive():
        assert state['leased']==0
        state['receives']+=1
        if state['receives']==1:return {'type':'http.request','body':payload[:20],'more_body':True}
        if drift=='permission':e.sessions.revoke(e.lead)
        if drift=='incarnation':state['changed']=True
        await asyncio.sleep(0)
        assert state['leased']==0
        return {'type':'http.request','body':payload[20:],'more_body':False}
    headers=[(k.lower().encode(),v.encode()) for k,v in e.headers.items()]
    if length is not None:headers.append((b'content-length',length.encode()))
    req=Request({'type':'http','method':'POST','path':'/author-archive/restore','headers':headers},receive)
    with pytest.raises(HTTPException) as failure:asyncio.run(endpoint(e.nid,req))
    assert failure.value.status_code=={'permission':401,'incarnation':403,'overflow':413}[drift]
    assert state['receives']==2 and state['leased']==0
    assert s.store.read(e.nid,e.scope)==before


def test_central_directory_limit_checked_before_zipfile(mounted,monkeypatch):
    import struct
    e=mounted;s,_,_,raw=exported(e)
    end=list(struct.unpack('<4s4H2LH',raw[-22:]));end[5]=2000
    forged=raw[:-22]+struct.pack('<4s4H2LH',*end)
    monkeypatch.setattr(a.zipfile,'ZipFile',lambda *args,**kwargs:pytest.fail('central directory must be bounded before ZipFile'))
    with pytest.raises(ValueError):a.decode(forged)
