"""Actual mounted app authorities, both route prefixes, File/real-PG matrix."""
import base64
import io
import json
import zipfile
import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from app.experimental.flags import FLAGS
from app.actor_context import SessionContext
from test_r4_portable_batches import confirm, version, project_inventory, unrelated_project

@pytest.fixture
def tools(mounted, monkeypatch):
    e=mounted;e.portable=e.experimental.portable_projects_service;e.batches=e.experimental.safe_batches_service
    monkeypatch.setattr(e.portable,'cache_root',e.root/'portable_cache_v2')
    e.sessions.register('portable-host', SessionContext('portable-session','portable-client','portable-actor','portable-workspace'))
    e.client.headers['X-Session-Token']='portable-host'
    return e


def test_mounted_portable_preflight_restore_actual_new_project_and_no_overwrite(tools):
    e=tools;before=e.chapters.get(e.chapter['id']);history=e.chapters.history(e.chapter['id']);base=e.base+'/portable-projects'
    with unrelated_project(e.novels, e.chapters) as neighbor:
        before_projects = project_inventory(e.novels)
        row=checked(e.client.post(base+'/export',json={'chapter_ids':[e.chapter['id']]}))
        archive=e.client.get(base+f"/records/{row['id']}/file?expected_version=1");assert archive.status_code==200 and archive.headers['cache-control']=='no-store'
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:assert 'manifest.json' in z.namelist()
        preview=checked(e.client.post(base+'/import-preflight',json={'filename':'new.zip','content_base64':base64.b64encode(archive.content).decode()}))
        assert project_inventory(e.novels) == before_projects
        restored=checked(e.client.post(base+f"/records/{preview['id']}/restore",json=confirm(preview)))
        target=restored['target_id'];assert target not in before_projects
        try:
            after_projects = project_inventory(e.novels)
            assert set(after_projects) == set(before_projects) | {target}
            assert {nid: after_projects[nid] for nid in before_projects} == before_projects
            assert e.novels.get(neighbor['project']['id']) == neighbor['project']
            assert e.chapters.get(neighbor['chapter']['id']) == neighbor['chapter']
            assert e.chapters.get(e.chapter['id'])==before and e.chapters.history(e.chapter['id'])==history
            assert e.chapters.list(target)
        finally:
            e.novels.delete(target)
        assert project_inventory(e.novels) == before_projects


def test_mounted_batch_actual_docx_selected_snapshot_and_explicit_stages(tools):
    e=tools;base=e.base+'/safe-batches';second=e.chapters.create(e.nid,{'title':'Not selected','content':'HIDDEN_FROM_EXPORT'})
    row=checked(e.client.post(base+'/preflight',json={'items':[{'kind':'EXPORT','format':'docx','chapter_ids':[e.chapter['id']]},{'kind':'PROOF','chapter_ids':[e.chapter['id']]}]}))
    assert row['status']=='PREFLIGHT';assert e.client.post(base+f"/{row['id']}/dispatch-next",json=version(row)).status_code==422
    row=checked(e.client.post(base+f"/{row['id']}/confirm",json=confirm(row)));assert all(i['attempts']==0 for i in row['items'])
    row=checked(e.client.post(base+f"/{row['id']}/dispatch-next",json=version(row)));assert row['items'][1]['status']=='PENDING'
    file=e.client.get(base+f"/{row['id']}/items/0/file");assert file.status_code==200
    with zipfile.ZipFile(io.BytesIO(file.content)) as z:
        body=z.read('word/document.xml');assert b'HIDDEN_FROM_EXPORT' not in body and b'city gate opened' in body
    row=checked(e.client.post(base+f"/{row['id']}/dispatch-next",json=version(row)));assert row['status']=='COMPLETED'


def test_mounted_off_wildcard_dependency_v1_suppress_new_routes(tools,monkeypatch):
    e=tools
    for flags,v1 in [('',False),('*',False),('safe_batches_v2',False),(','.join(FLAGS),True)]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES',flags);monkeypatch.setenv('V1_ACCEPTANCE_MODE',str(v1))
        assert e.client.get(e.base+'/safe-batches').status_code==404
        if flags!='safe_batches_v2':assert e.client.get(e.base+'/portable-projects/catalog').status_code==404
        assert e.client.post(e.base+'/safe-batches/preflight',json={'items':[{'kind':'PROOF','chapter_ids':[e.chapter['id']]}]}).status_code==404
    assert not e.store.read(e.nid,e.scope)['collections'].get(e.batches.BATCHES)


def test_mounted_real_actor_branch_restore_fail_closed_and_export_no_branch_fallback(tools,monkeypatch):
    e=scoped(tools,monkeypatch);e.client.headers.pop('X-Session-Token',None)
    catalog=checked(e.client.get(e.base+'/portable-projects/catalog',headers=e.headers));assert catalog['chapters']==[] and not catalog['restore_available']
    body={'items':[{'kind':'PROOF','chapter_ids':[e.chapter['id']]}]}
    assert e.client.post(e.base+'/safe-batches/preflight',json=body,headers=e.headers).status_code==404
    assert e.client.post(e.base+'/safe-batches/preflight',json=body,headers=e.viewer_headers).status_code==403
    assert e.client.get(e.base+'/safe-batches').status_code==401
    assert e.client.get(e.base+'/safe-batches',headers={**e.headers,'X-Branch-ID':e.other_branch}).status_code==403


@pytest.mark.parametrize('fence',['flag','v1','source'])
def test_mounted_final_dispatch_rechecks_before_accepting_output(tools,monkeypatch,fence):
    e=tools;base=e.base+'/safe-batches'
    row=checked(e.client.post(base+'/preflight',json={'items':[{'kind':'EXPORT','format':'txt','chapter_ids':[e.chapter['id']]}]}))
    row=checked(e.client.post(base+f"/{row['id']}/confirm",json=confirm(row)))
    original=e.novels.export_snapshot_result
    def rendering(*args,**kwargs):
        result=original(*args,**kwargs)
        if fence=='flag':monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
        elif fence=='v1':monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
        else:e.chapters.save(e.chapter['id'],{'version':e.chapters.get(e.chapter['id'])['version'],'content':'Changed source'})
        return result
    monkeypatch.setattr(e.novels,'export_snapshot_result',rendering)
    response=e.client.post(base+f"/{row['id']}/dispatch-next",json=version(row));assert response.status_code in {404,409}
    raw=e.store.read(e.nid,e.scope)['collections'][e.batches.BATCHES][row['id']]
    assert raw['items'][0]['result'] is None and raw['items'][0]['status']=='FAILED'


def test_mounted_batch_conflict_never_echoes_frozen_private_sources(tools):
    e=tools;base=e.base+'/safe-batches'
    e.chapters.save(e.chapter['id'],{'version':e.chapter['version'],'content':'PRIVATE_FROZEN_TEXT the the'})
    row=checked(e.client.post(base+'/preflight',json={'items':[{'kind':'PROOF','chapter_ids':[e.chapter['id']]}]}))
    confirmed=checked(e.client.post(base+f"/{row['id']}/confirm",json=confirm(row)))
    done=checked(e.client.post(base+f"/{row['id']}/dispatch-next",json=version(confirmed)))
    conflict=e.client.post(base+f"/{row['id']}/dispatch-next",json=version(confirmed))
    assert conflict.status_code==409 and 'PRIVATE_FROZEN_TEXT' not in conflict.text and 'current' not in conflict.json()['detail']


def test_mounted_batch_child_legacy_routes_and_asset_off_fence(tools,monkeypatch):
    e=tools;base=e.base+'/safe-batches'
    brief=checked(e.client.post(e.base+'/media/cover-briefs',json={'title':'SYNTHETIC_BATCH_PRIVATE','chapter_ids':[e.chapter['id']]}),201)
    row=checked(e.client.post(base+'/preflight',json={'items':[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':1}]}))
    row=checked(e.client.post(base+f"/{row['id']}/confirm",json=confirm(row)))
    row=checked(e.client.post(base+f"/{row['id']}/dispatch-next",json=version(row)))
    proposal=row['items'][0]['proposals'][0]
    raw=e.store.read(e.nid,e.scope)['collections'][e.batches.BATCHES][row['id']];tid=raw['items'][0]['task_id']
    for path in [f'/media/tasks/{tid}/execute',f'/media/tasks/{tid}/retry',f'/media/proposals/{proposal["id"]}/approve']:
        response=e.client.post(e.base+path,json={'expected_version':1});assert response.status_code==404 and 'SYNTHETIC_BATCH_PRIVATE' not in response.text
    assert checked(e.client.get(e.base+'/media/tasks'))['items']==[]
    approved=checked(e.client.post(base+f"/{row['id']}/approve-media",json={**confirm(row),'proposal_id':proposal['id'],'proposal_version':proposal['version']}))
    aid=approved['items'][0]['proposals'][0]['asset_id']
    legacy=e.prefix+f'/novels/{e.nid}/assets';assert aid in e.client.get(legacy).text
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(f for f in FLAGS if f!='safe_batches_v2'))
    assert aid not in e.client.get(legacy).text
    assert e.client.get(e.base+'/media/proposals').json()['items']==[]
    assert e.client.get(base).status_code==404


def test_restore_revocation_keeps_partial_new_target_without_original_overwrite(tools,monkeypatch):
    e=tools;base=e.base+'/portable-projects';before=e.chapters.get(e.chapter['id'])
    exported=checked(e.client.post(base+'/export',json={'chapter_ids':[e.chapter['id']]}))
    archive=e.client.get(base+f"/records/{exported['id']}/file?expected_version=1").content
    preview=checked(e.client.post(base+'/import-preflight',json={'filename':'new.zip','content_base64':base64.b64encode(archive).decode()}))
    original=e.novels.create
    def revoked(payload):
        created=original(payload);monkeypatch.setenv('EXPERIMENTAL_FEATURES','');return created
    monkeypatch.setattr(e.novels,'create',revoked)
    response=e.client.post(base+f"/records/{preview['id']}/restore",json=confirm(preview));assert response.status_code==404
    raw=e.store.read(e.nid,e.scope)['collections'][e.portable.RECORDS][preview['id']]
    assert raw['status']=='RECOVERY_REQUIRED' and raw['target_id']!=e.nid and e.novels.get(raw['target_id'])
    assert e.chapters.get(e.chapter['id'])==before
    e.novels.delete(raw['target_id'])


def test_relink_original_chapter_cas_conflict_is_sanitized_and_preserves_recovery(tools,monkeypatch):
    from app.repositories.chapter_repository import VersionConflict
    from test_r3_media_support import wav_bytes
    e=tools;base=e.base+'/portable-projects';raw=wav_bytes();asset=e.assets.create(e.nid,'synthetic.wav',base64.b64encode(raw).decode(),'audio/wav','audio')
    chapter=e.chapters.get(e.chapter['id']);doc=chapter['document'];doc['content'].append({'type':'audio','attrs':{'asset_id':asset['id']}})
    e.chapters.save(chapter['id'],{'version':chapter['version'],'document':doc});(e.assets.root/(asset['id']+'.bin')).unlink()
    preview=checked(e.client.post(base+'/relink-preflight',json={'filename':'same.wav','content_base64':base64.b64encode(raw).decode(),'kind':'audio','missing_id':asset['id'],'chapter_ids':[chapter['id']]}))
    def conflict(*args,**kwargs):raise VersionConflict({'id':chapter['id'],'version':99,'content':'PRIVATE_CONFLICT_BODY'})
    monkeypatch.setattr(e.chapters,'save',conflict)
    response=e.client.post(base+f"/records/{preview['id']}/relink",json=confirm(preview))
    assert response.status_code==409 and 'PRIVATE_CONFLICT_BODY' not in response.text
    record=e.store.read(e.nid,e.scope)['collections'][e.portable.RECORDS][preview['id']]
    assert record['status']=='RECOVERY_REQUIRED'


def test_original_broker_budget_change_invalidates_batch_confirmation_without_reserving(tools):
    e=tools;base=e.base+'/safe-batches'
    row=checked(e.client.post(base+'/preflight',json={'items':[{'kind':'PROOF','chapter_ids':[e.chapter['id']]}]}))
    assert row['budget']['state']=='ORIGINAL_BROKER_CONFIG' and row['budget']['known_cost_microusd']==0
    checked(e.client.put(e.base+'/model-broker/budget',json={'expected_version':0,'limit_microusd':0,'max_inflight':1,'require_known_estimate':True}))
    response=e.client.post(base+f"/{row['id']}/confirm",json=confirm(row));assert response.status_code==409
    broker=e.experimental.model_broker_service
    assert not e.store.read(e.nid,e.scope)['collections'].get(broker.LEDGER)
