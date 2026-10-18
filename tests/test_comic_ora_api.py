"""Mounted ORA boundary over actual File/Postgres Asset and Comic owners."""
import base64
import hashlib
import io
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from test_v2_independent_workspace import rig
from test_comic_ora_staging import staging
from test_comic_ora_import import archive
from test_comic_ora_review_attach import page
from app.experimental.comic_ora_api import create_comic_ora_router, MAX_BODY
from app.experimental.comic_layouts_api import create_comic_layouts_router


def body(raw=None, **kw):
    raw = raw or archive()
    return dict(archive_base64=base64.b64encode(raw).decode(), archive_sha256=hashlib.sha256(raw).hexdigest(), **kw)


@pytest.fixture
def mounted(rig, staging):
    state = SimpleNamespace(actor=rig.actor, permission=None, leased=0, deny=False, calls=0)
    def authorize(nid, token, branch, permission):
        state.calls += 1
        if state.deny: raise HTTPException(403, {'code': 'DENIED'})
        assert token == 'owner-session'
        assert nid == rig.nid
        state.permission = permission
        return state.actor, dict(rig.scope)
    @contextmanager
    def lease(nid, token, actor, scope):
        state.leased += 1
        try: yield
        finally: state.leased -= 1
    app = FastAPI()
    ora_router=create_comic_ora_router(staging, authorize, lambda f: None, authority_lease=lease)
    app.include_router(ora_router)
    app.include_router(create_comic_layouts_router(staging.comic, authorize, lambda f: None))
    client = TestClient(app, headers={'x-session-token': 'owner-session'})
    return SimpleNamespace(client=client, state=state, ora_router=ora_router,
        root=f'/novels/{rig.nid}/experimental/comic-layouts/ora-imports')


def test_mounted_explicit_workflow_and_private_legacy_routes(rig, staging, mounted):
    c, root = mounted.client, mounted.root
    preview = c.post(root+'/preview', json=body())
    assert preview.status_code == 200, preview.text
    value = preview.json()
    assert value['report']['writes_performed'] is False
    image = Image.open(io.BytesIO(base64.b64decode(value['thumbnail_base64'])))
    assert max(image.size) <= 256 and len(base64.b64decode(value['thumbnail_base64'])) < 300000
    assert c.get(root).json() == {'receipts': []}
    receipt = c.post(root, json=body(request_key='explicit')).json()
    rid = receipt['id']; path = root+'/'+rid
    assert c.get(path+'/candidates/0').status_code == 404
    receipt = c.post(path+'/stage', json=body(max_steps=8)).json()
    png = c.get(path+'/candidates/0')
    assert png.status_code == 200 and png.content.startswith(b'\x89PNG')
    for response in (preview, png, c.get(path)):
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
    aid = receipt['steps'][0]['asset_id']
    legacy = root.removesuffix('/ora-imports')+'/images/'+aid
    assert c.get(legacy).status_code == 404
    assert c.post(legacy+'/approve',json={'expected_version':1}).status_code == 404
    manifest = c.post(path+'/review-manifest',json=body()).json()
    review_body = body(manifest_digest=manifest['manifest_digest'],license_note='Author-owned fixture',acknowledge_raster_text=True,max_steps=8)
    reviewed = c.post(path+'/review',json=review_body)
    assert reviewed.status_code == 200, reviewed.text
    assert mounted.state.permission == 'domain.review'
    target = page(rig,staging)
    attach_body = {'page_id':target['id'],'expected_page_version':1,'review_digest':reviewed.json()['review_digest']}
    attached = c.post(path+'/attach',json=attach_body)
    assert attached.status_code == 200, attached.text
    assert attached.json()['page']['status'] == 'DRAFT'
    assert c.post(path+'/attach',json=attach_body).json() == attached.json()
    assert c.get(root).json()['receipts'][0]['status'] == 'ATTACHED'
    mounted.state.actor='foreign'
    assert c.get(root).json() == {'receipts':[]}
    for suffix in ('','/candidates/0'):
        response=c.get(path+suffix)
        assert response.status_code == 404 and aid not in response.text


def test_authentication_before_body_and_reauthorization_before_processing(rig, staging, mounted, monkeypatch):
    c,root=mounted.client,mounted.root
    mounted.state.deny=True
    assert c.post(root+'/preview',content=b'{bad').status_code==403
    mounted.state.deny=False
    original=staging.prepare
    def check(*args,**kwargs):
        assert mounted.state.leased == 1
        return original(*args,**kwargs)
    monkeypatch.setattr(staging,'prepare',check)
    assert c.post(root,json=body(request_key='lease')).status_code==200
    assert mounted.state.leased==0


@pytest.mark.parametrize('length',[None,'1'])
def test_stream_bound_independent_of_content_length(rig, staging, mounted, length):
    headers={} if length is None else {'content-length':length}
    response=mounted.client.post(mounted.root+'/preview',content=iter([b'x'*65536 for _ in range(MAX_BODY//65536+1)]),headers=headers)
    assert response.status_code==413, response.text
    assert response.headers['cache-control']=='no-store'
    assert mounted.client.get(mounted.root).json()=={'receipts':[]}


@pytest.mark.parametrize('change',[
    {'archive_base64':'%%%%'}, {'archive_sha256':'0'*64}, {'archive_base64':'YQ=='},
    {'archive_base64':123}, {'unexpected':'secret'}])
def test_invalid_upload_is_private(rig,staging,mounted,change):
    response=mounted.client.post(mounted.root+'/preview',json={**body(),**change})
    assert response.status_code in (413,422),response.text
    assert 'secret' not in response.text and 'archive_base64' not in response.text
    assert response.headers['x-content-type-options']=='nosniff'


def test_archive_manifest_and_batch_exactness(rig,staging,mounted):
    c,root=mounted.client,mounted.root
    row=c.post(root,json=body(request_key='exact')).json();path=root+'/'+row['id']
    assert c.post(path+'/stage',json=body(max_steps=9)).status_code==422
    different=archive(xml=b'<image w="320" h="320" name="Changed"><stack><layer name="Red" src="data/red.png"/></stack></image>')
    assert c.post(path+'/stage',json=body(different,max_steps=1)).status_code==422
    assert c.post(path+'/stage',json=body()).status_code==200
    assert c.post(path+'/review',json=body(manifest_digest='0'*64,license_note='Fixture',acknowledge_raster_text=True)).status_code==422
    assert c.post(path+'/review',json=body(manifest_digest='0'*64,license_note='Fixture',acknowledge_raster_text=False)).status_code==422


def test_missing_existing_owner_never_provisioned(rig,staging,mounted,monkeypatch):
    original=staging.owner.incarnation
    seen=[]
    def missing(nid):
        seen.append(staging.owner._existing_only.get())
        raise FileNotFoundError(nid)
    monkeypatch.setattr(staging.owner,'incarnation',missing)
    for method,suffix in [('get',''),('post','/preview')]:
        response=getattr(mounted.client,method)(mounted.root+suffix,**({'json':body()} if method=='post' else {}))
        assert response.status_code==404
    assert seen and all(seen)


def test_lost_ack_status_explicit_recovery_and_cas(rig,staging,mounted,monkeypatch):
    c,root=mounted.client,mounted.root
    row=c.post(root,json=body(request_key='lost')).json();path=root+'/'+row['id']
    original=staging.stage
    def lost(*a,**kw):
        original(*a,**kw)
        raise OSError('private filesystem path')
    monkeypatch.setattr(staging,'stage',lost)
    response=c.post(path+'/stage',json=body())
    assert response.status_code==500 and 'filesystem' not in response.text
    assert c.get(path).json()['status']=='STAGED_PRIVATE_REVIEW_PENDING'
    monkeypatch.setattr(staging,'stage',original)
    assert c.post(path+'/stage',json=body()).status_code==200
    manifest=c.post(path+'/review-manifest',json=body()).json()
    review=c.post(path+'/review',json=body(manifest_digest=manifest['manifest_digest'],license_note='Fixture',acknowledge_raster_text=True)).json()
    target=page(rig,staging)
    response=c.post(path+'/attach',json={'page_id':target['id'],'expected_page_version':2,'review_digest':review['review_digest']})
    assert response.status_code==409 and 'document' not in response.text
    assert c.get(path).json()['status']=='REVIEWED_READY_FOR_ATTACHMENT'


def test_authority_and_incarnation_change_during_stream_deny_before_processing(rig,staging,mounted,monkeypatch):
    import json
    c,root=mounted.client,mounted.root
    payload=json.dumps(body(request_key='drift')).encode()
    original=staging.owner.incarnation
    changed={'yes':False}
    def incarnation(nid):
        return 'file:00000000-0000-0000-0000-000000000000' if changed['yes'] else original(nid)
    monkeypatch.setattr(staging.owner,'incarnation',incarnation)
    def chunks():
        yield payload[:20]
        changed['yes']=True
        yield payload[20:]
    response=c.post(root,content=chunks())
    assert response.status_code==403,response.text
    changed['yes']=False
    assert c.get(root).json()=={'receipts':[]}


def test_prepared_receipt_commit_retains_authority_lease(rig,staging,mounted,monkeypatch):
    original=staging.store.transaction
    @contextmanager
    def transaction(*args,**kwargs):
        assert mounted.state.leased == 1
        with original(*args,**kwargs) as state:
            yield state
            assert mounted.state.leased == 1
        assert mounted.state.leased == 1
    monkeypatch.setattr(staging.store,'transaction',transaction)
    response=mounted.client.post(mounted.root,json=body(request_key='commit'))
    assert response.status_code==200,response.text


def test_thumbnail_additional_work_is_bounded(monkeypatch):
    import app.experimental.comic_ora_import as parser
    raw=archive()
    original=parser.preview_ora(raw)
    budget=original.report['decoded_work_pixels']
    monkeypatch.setattr(parser,'MAX_DECODE_WORK',budget)
    with pytest.raises(ValueError,match='WORK'):
        parser.preview_ora(raw,thumbnail_only=True)


@pytest.mark.parametrize('drift',['permission','incarnation','overflow'])
@pytest.mark.parametrize('length',[None,'1'])
def test_direct_asgi_stream_authority_no_lease_across_await(rig,staging,mounted,monkeypatch,drift,length):
    import asyncio
    import json
    from starlette.requests import Request
    import app.experimental.comic_ora_api as routes
    payload=json.dumps(body(request_key='direct-stream')).encode()
    original=staging.owner.incarnation
    state={'receives':0,'changed':False}
    def incarnation(nid):
        return 'file:00000000-0000-0000-0000-000000000000' if state['changed'] else original(nid)
    monkeypatch.setattr(staging.owner,'incarnation',incarnation)
    def forbidden(*a,**kw): pytest.fail('No parser or mutation after streamed authority change')
    monkeypatch.setattr(staging,'prepare',forbidden)
    if drift=='overflow': monkeypatch.setattr(routes,'MAX_BODY',50)
    endpoint=next(route.endpoint for route in mounted.ora_router.routes if getattr(route,'path','')==mounted.root.replace(rig.nid,'{nid}') and 'POST' in getattr(route,'methods',set()))
    async def receive():
        assert mounted.state.leased==0
        state['receives']+=1
        if state['receives']==1:
            return {'type':'http.request','body':payload[:20],'more_body':True}
        if drift=='permission': mounted.state.deny=True
        if drift=='incarnation': state['changed']=True
        await asyncio.sleep(0)
        assert mounted.state.leased==0
        return {'type':'http.request','body':payload[20:],'more_body':False}
    headers=[(b'x-session-token',b'owner-session')]
    if length is not None: headers.append((b'content-length',length.encode()))
    request=Request({'type':'http','method':'POST','path':mounted.root,'headers':headers},receive)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(endpoint(rig.nid,request))
    assert failure.value.status_code==(413 if drift=='overflow' else 403)
    assert state['receives']==2 and mounted.state.leased==0


def test_http_retired_owner_never_recreated_and_receipt_not_rebound(rig,staging,mounted):
    c,root=mounted.client,mounted.root
    row=c.post(root,json=body(request_key='retired')).json()
    c.post(root+'/'+row['id']+'/stage',json=body()).raise_for_status()
    rig.novels.delete(rig.nid)
    for suffix in ('','/'+row['id'],'/'+row['id']+'/candidates/0'):
        assert c.get(root+suffix).status_code==404
    if rig.backend=='file':
        assert not (rig.root/'novels'/rig.nid/'creative_project_v2.json').exists()
    rig.create_project(nid=rig.nid)
    if rig.backend=='file':
        assert c.get(root).status_code==404
        assert not (rig.root/'novels'/rig.nid/'creative_project_v2.json').exists()
    rig.service.store.incarnation(rig.nid)  # explicit creation by fixture, never GET
    assert c.get(root).json()=={'receipts':[]}
    assert c.get(root+'/'+row['id']).status_code==404
    assert c.get(root+'/'+row['id']+'/candidates/0').status_code==404
