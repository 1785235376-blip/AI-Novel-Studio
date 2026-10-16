"""Mounted original adaptation API: scopes, permissions, CAS and recovery."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import adaptation_service, chapter_service, branch_manuscript_service, authorization_service, collaboration_scope_service, trusted_session_resolver
from app.collaboration import Branch
from app.document import markdown_to_document
from test_phase7_adaptation_authorization import setup_scope


def local(client):
    nid='adapt-api-'+uuid4().hex
    assert client.post('/api/novels',json={'id':nid,'title':'Adaptation API'}).status_code==201
    chapter=client.post(f'/api/novels/{nid}/chapters',json={'title':'One','content':'Source'}).json()
    return nid,chapter,f'/api/novels/{nid}/adaptations'

def approved(client,base):
    p=client.post(base,json={'target':'SCREEN'}).json()
    return client.post(base+'/'+p['id']+'/approve',json={'expected_revision':p['revision']}).json()

def test_original_routes_require_exact_revision_and_return_content_free_conflict(monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','adaptation_lifecycle_v1');client=TestClient(app);nid,_,base=local(client)
    p=client.post(base,json={'target':'SCREEN'}).json();endpoint=base+'/'+p['id']
    assert client.post(endpoint+'/approve').status_code==428
    body={**p['blueprint'],'focus':'One writer','expected_revision':p['revision']}
    updated=client.put(endpoint+'/blueprint',json=body);assert updated.status_code==200
    conflict=client.put(endpoint+'/blueprint',json={**body,'focus':'Stale writer'})
    assert conflict.status_code==409 and 'Source' not in conflict.text and 'source_snapshots' not in conflict.text
    assert client.post(endpoint+'/approve',json={'expected_revision':p['revision']}).status_code==409
    p=updated.json();p=client.post(endpoint+'/approve',json={'expected_revision':p['revision']}).json()
    result=client.post(endpoint+'/materialize',json={'expected_revision':p['revision']});assert result.status_code==201,result.text
    row=client.get(base).json()[0];tid=row['execution_manifest'][0]['id'];task_url=endpoint+'/tasks/'+tid
    generated=client.post(task_url+'/generate',json={'mode':'deterministic','expected_revision':row['revision']});assert generated.status_code==200,generated.text
    row=client.get(base).json()[0]
    reviewed=client.post(task_url+'/review',json={'decision':'ACCEPTED','expected_revision':row['revision']});assert reviewed.status_code==200,reviewed.text
    row=client.get(base).json()[0];target=chapter_service.get(row['execution_manifest'][0]['target_chapter_id'])
    newer=chapter_service.save(target['id'],{'document':markdown_to_document('New human revision'),'version':target['version']})
    assert client.post(task_url+'/apply',json={'expected_revision':row['revision']}).status_code==409
    assert chapter_service.get(target['id'])==newer
    history=client.get(endpoint+'/history').json();assert history['revision']==row['revision'] and len(history['items'])>3


def test_catalog_disabled_and_cancel_recovery_use_original_record(monkeypatch):
    client=TestClient(app);nid,_,base=local(client)
    assert client.get(base+'/catalog').json()['enabled'] is False
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','adaptation_lifecycle_v1')
    p=client.post(base,json={'target':'COMMERCIAL'}).json();endpoint=base+'/'+p['id']
    cancelled=client.post(endpoint+'/actions/cancel',json={'expected_revision':p['revision']}).json()
    assert cancelled['status']=='CANCELLED'
    assert client.post(endpoint+'/actions/recover',json={'expected_revision':p['revision']}).status_code==409
    recovered=client.post(endpoint+'/actions/recover',json={'expected_revision':cancelled['revision']}).json()
    assert recovered['status']=='DRAFT' and recovered['id']==p['id']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    assert client.get(base).json()==[]
    assert client.get(endpoint+'/history').status_code==404
    assert client.post(endpoint+'/approve',json={'expected_revision':recovered['revision']}).status_code==404


def team(monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','branch_manuscript_v1')
    return setup_scope()


def test_empty_branch_cannot_read_mainline_and_branch_record_cannot_cross_scope(monkeypatch):
    client,nid,branch,scope,headers=team(monkeypatch);base=f'/api/novels/{nid}/adaptations'
    empty='empty-'+uuid4().hex
    collaboration_scope_service.create_branch(Branch(empty,scope.workspace_id,nid,scope.storyline_id,'Empty'))
    p=client.post(base,params={'branch_id':empty},headers=headers['admin'],json={'target':'SCREEN'}).json()
    assert p['source_chapter_count']==0 and p['source_versions']==[] and p['source_snapshots']==[]
    assert chapter_service.list(nid) # Mainline exists but is not an empty branch fallback.
    assert client.get(base,params={'branch_id':branch},headers=headers['admin']).json()==[]
    assert client.post(base+'/'+p['id']+'/approve',params={'branch_id':branch},headers=headers['admin']).status_code==404


def test_mainline_and_branch_have_distinct_provenance_and_project_rights(monkeypatch):
    client,nid,branch,scope,headers=team(monkeypatch);base=f'/api/novels/{nid}/adaptations'
    view=branch_manuscript_service.for_scope(scope);original=view.list(nid)[0]
    view.save(original['id'],{'document':markdown_to_document('# Branch-only\n\nDifferent branch text'),'version':original['version']})
    branch_p=client.post(base,params={'branch_id':branch},headers=headers['lead'],json={'target':'SCREEN'}).json()
    assert 'Different branch text' in str(branch_p['source_snapshots']) and '敏感原作正文' not in str(branch_p['source_snapshots'])
    assert branch_p['source_versions'][0]['chapter_id']!=chapter_service.list(nid)[0]['id']
    assert client.get(base,headers=headers['lead']).status_code==403
    assert client.post(base,headers=headers['lead'],json={'target':'SCREEN'}).status_code==403
    assert client.get(base).status_code==401
    main_p=client.post(base,headers=headers['admin'],json={'target':'LITERARY'}).json()
    assert '敏感原作正文' in str(main_p['source_snapshots']) and 'Different branch text' not in str(main_p['source_snapshots'])
    assert main_p['branch_id'] is None


def test_branch_feature_off_and_revoked_grant_never_fall_back(monkeypatch):
    client,nid,branch,scope,headers=team(monkeypatch);base=f'/api/novels/{nid}/adaptations';params={'branch_id':branch}
    p=client.post(base,params=params,headers=headers['lead'],json={'target':'SCREEN'});assert p.status_code==201
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    assert client.get(base,params=params,headers=headers['lead']).status_code==404
    assert client.post(base,params=params,headers=headers['lead'],json={'target':'SCREEN'}).status_code==404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','branch_manuscript_v1')
    actor=trusted_session_resolver.resolve(headers['lead']['X-Session-Token'])
    authorization_service.revoke_role('lead-role-'+actor.actor_id.removeprefix('lead-'),actor.actor_id)
    denied=client.get(base,params=params,headers=headers['lead'])
    assert denied.status_code==403 and '敏感原作正文' not in denied.text
    assert chapter_service.list(nid)


def test_target_permission_revocation_blocks_idempotent_materialization(monkeypatch):
    client,nid,branch,scope,headers=team(monkeypatch);base=f'/api/novels/{nid}/adaptations';params={'branch_id':branch}
    # Branch-only source lead receives a separately scoped target grant.
    p=client.post(base,params=params,headers=headers['lead'],json={'target':'SCREEN'}).json()
    client.post(base+'/'+p['id']+'/approve',params=params,headers=headers['lead'])
    target=client.post(base+'/'+p['id']+'/materialize',params=params,headers=headers['lead']);assert target.status_code==201,target.text
    owner=trusted_session_resolver.resolve(headers['lead']['X-Session-Token'])
    target_id=target.json()['id']
    roles=authorization_service.repository.list_role_assignments()
    matched=[r for r in roles if r['principal_id']==owner.actor_id and r.get('scope',{}).get('project_id')==target_id]
    for role in matched:authorization_service.revoke_role(role['id'],owner.actor_id)
    assert matched
    denied=client.post(base+'/'+p['id']+'/materialize',params=params,headers=headers['lead'])
    assert denied.status_code==403


def test_reserved_team_target_replay_and_concurrent_writers_never_delete_existing(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.dependencies import collaboration_admin_service,novel_service
    client,nid,branch,scope,headers=team(monkeypatch)
    actor=trusted_session_resolver.resolve(headers['admin']['X-Session-Token']);port=collaboration_admin_service.path_mutations
    reservation={key:str(uuid4()) for key in ('project_id','storyline_id','branch_id')};barrier=Barrier(2)
    def create(label):
        barrier.wait()
        try:return port.create_project(scope.workspace_id,label,'Synthetic',actor,**reservation)
        except (FileExistsError,KeyError):return None
        except Exception as exc:
            # PostgreSQL uniqueness also atomically rejects the second writer.
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc,IntegrityError):return None
            raise
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(create,['Reserved A','Reserved B']))
    assert sum(row is not None for row in results)==1
    original=novel_service.get(reservation['project_id'])
    with pytest.raises(FileExistsError):port.create_project(scope.workspace_id,'Replay','Synthetic',actor,**reservation)
    assert novel_service.get(reservation['project_id'])==original
    with pytest.raises(ValueError):port.create_project(scope.workspace_id,'Invalid','Synthetic',actor,project_id='../unsafe')
    collision={**reservation,'project_id':str(uuid4())}
    with pytest.raises(FileExistsError):port.create_project(scope.workspace_id,'Wrong owner','Synthetic',actor,**collision)
    assert novel_service.get(reservation['project_id'])==original


def test_project_authorized_mainline_adaptation_creates_true_target_branch(monkeypatch):
    client,nid,branch,scope,headers=team(monkeypatch);base=f'/api/novels/{nid}/adaptations'
    p=client.post(base,headers=headers['admin'],json={'target':'SCREEN'}).json()
    assert p['branch_id'] is None and p['source_versions'][0]['chapter_id']==chapter_service.list(nid)[0]['id']
    assert client.post(base+'/'+p['id']+'/approve',headers=headers['admin']).status_code==200
    target=client.post(base+'/'+p['id']+'/materialize',headers=headers['admin']);assert target.status_code==201,target.text
    row=next(row for row in client.get(base,headers=headers['admin']).json() if row['id']==p['id'])
    task=row['execution_manifest'][0];owner=branch_manuscript_service.for_scope({'kind':'BRANCH',**target.json()['scope']})
    assert owner.get(task['target_chapter_id'])['document']==chapter_service.get(p['source_versions'][0]['chapter_id'])['document']
    assert chapter_service.list(target.json()['id'])==[]
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','branch_manuscript_v1,adaptation_lifecycle_v1')
    detail=client.get(base+'/'+p['id']+'/tasks/'+task['id'],headers=headers['admin'])
    assert detail.status_code==200 and detail.json()['stale'] is False
    missing=client.get(base+'/missing/tasks/'+task['id'],headers=headers['admin']);assert missing.status_code==404
