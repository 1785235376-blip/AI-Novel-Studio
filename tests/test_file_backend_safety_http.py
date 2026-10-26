"""Combined real TCP HTTP protections using original File application owners.

Synthetic saved scale fixture remains 32 consumers / 540 direct references.
TaskCenter's three single-source combinations are checked independently; its
contract does not inherit the asset-only resource budget.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import httpx
import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, copied_graph_consumers, copied_timeline_consumers, graph_create
from test_studio_process_reopen_v2 import unused_port

pytestmark = pytest.mark.file_backend_only
FLAGS = 'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2,workspace_tools_v2,semantic_import_v2,agent_team_recipes'


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob('*') if p.is_file() and '.workspace-mutation-locks' not in p.parts}


def body(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


@contextmanager
def application(run, *, collaboration=False, budget=None, label='normal'):
    root = Path(__file__).resolve().parents[1]
    port = unused_port()
    env = os.environ.copy()
    for key in tuple(env):
        if key.endswith('_API_KEY') or key in {'DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL'}:
            env.pop(key, None)
    for folder in ('home', 'data', 'tmp', 'appdata', 'localappdata'):
        (run / folder).mkdir(parents=True, exist_ok=True)
    receipt = run / (label + '-receipt.json')
    env.update(PROJECT_ROOT=str(root), PYTHONPATH=str(root), NOVEL_DATA_PATH=str(run/'data'),
        HOME=str(run/'home'), USERPROFILE=str(run/'home'), APPDATA=str(run/'appdata'), LOCALAPPDATA=str(run/'localappdata'),
        TMP=str(run/'tmp'), TEMP=str(run/'tmp'), STORAGE_BACKEND='file', MOCK_PROVIDER='true', ENABLE_CLOUD='false',
        ENABLE_PACKAGED_RUNTIME='false', ENABLE_COLLABORATION_RUNTIME=str(collaboration).lower(),
        CREDENTIAL_VAULT_BACKEND='memory', CREATION_PROFILE='LOCAL_ONLY', EXPERIMENTAL_FEATURES=FLAGS,
        FILE_SAFETY_RECEIPT=str(receipt), COLLABORATION_DEV_SESSIONS_JSON=json.dumps([
            {'token':'token-local','session_id':'session-local','client_id':'client','actor_id':'local-author','workspace_id':'local-workspace'},
            {'token':'token-reader','session_id':'session-reader','client_id':'client','actor_id':'reader','workspace_id':'query-workspace'}]))
    env.pop('FILE_SAFETY_MAX_READ_BYTES', None)
    if budget is not None:
        env['FILE_SAFETY_MAX_READ_BYTES'] = str(budget)
    with (run/(label+'.log')).open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(root/'tests/file_safety_http_server.py'), str(port)], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=60, headers={'X-Session-Token':'token-local'}) as client:
                deadline = time.monotonic()+45
                while True:
                    assert process.poll() is None, (run/(label+'.log')).read_text(encoding='utf-8')
                    try:
                        if client.get('/health').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, 'original app startup timeout'
                    time.sleep(.05)
                yield client
                # Wait for observed app completion, including post-body cleanup,
                # before Windows process termination. This is an audit barrier,
                # not a timing mechanism for arranging any business mutation.
                deadline=time.monotonic()+10
                while True:
                    try:
                        latest=json.loads(receipt.read_text(encoding='utf-8'))
                        if latest['gets'] and all(r['completed'] for r in latest['gets']):
                            break
                    except (OSError, json.JSONDecodeError):
                        pass
                    assert time.monotonic()<deadline, 'GET completion audit did not flush'
                    time.sleep(.01)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    observed = json.loads(receipt.read_text(encoding='utf-8'))
    gets = [r for r in observed['gets'] if r['path'] != '/health']
    assert all(not r['command_calls'] for r in gets), gets
    assert observed['summary']['business_write_calls']==observed['summary']['strict_write_calls']==0
    assert observed['summary']['strict_file_creations']==observed['summary']['strict_directory_creations']==0
    assert all(not r['filesystem_mutations'] for r in gets), gets
    assert all(not [p for p in r['write_opens'] if '.workspace-mutation-locks' not in p.split('/')] for r in gets), gets
    assert observed['loaded_modules']['app.main']['path'].startswith(str(root))
    assert observed['synthetic_exporter']['mode']=='deterministic_stub'
    assert observed['synthetic_exporter']['calls']==(3 if label=='normal' and not collaboration else 0)
    if budget is not None:
        charged = [b for r in gets for b in r['budget_reads']]
        assert charged and max(b['read_bytes'] for b in charged) > 0
        assert all(b['read_bytes'] <= budget for b in charged)
    destination = Path(os.environ.get('STUDIO_TEST_RUN_ROOT', run.parent)) / 'http-evidence'
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(receipt, destination/(run.name+'-'+receipt.name))


def task_page(client, prefix, nid, authority, token=None, headers=None):
    params = {'authority': authority, 'page_mode':'cursor', 'limit':1}
    if token:
        params['cursor'] = token
    request = client.build_request('GET', f'{prefix}/novels/{nid}/experimental/workspace/tasks', params=params, headers=headers)
    if headers is None:
        request.headers.pop('X-Session-Token', None)
    response = client.send(request)
    assert response.headers['cache-control'] == 'no-store'
    return response


def traverse(client, prefix, nid, authority, ids, headers=None):
    first = body(task_page(client, prefix, nid, authority, headers=headers))
    second = body(task_page(client, prefix, nid, authority, first['next_cursor'], headers))
    assert body(task_page(client, prefix, nid, authority, first['next_cursor'], headers)) == second
    last = body(task_page(client, prefix, nid, authority, second['next_cursor'], headers))
    assert last['next_cursor'] is None and not last['has_more'] and last['observed_total'] == 3
    assert {r['id'] for page in (first,second,last) for r in page['items']} == set(ids)
    assert last['coverage']['completeness'] == 'NOT_ASSERTED'
    assert 'row_lifecycles' not in json.dumps(first) and 'private-source' not in json.dumps(first)
    return first['next_cursor']


def asset_page(client, url, token=None, strict=False, headers=None):
    params = {'limit':100}
    if strict:
        params['strict_read_only']='true'
    if token:
        params['cursor'] = token
    response = client.get(url, params=params, headers=headers)
    assert response.headers['cache-control'] == 'no-store'
    return response


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_socket_local_asset_and_two_task_sources_survive_mutation_reopen(usage_rig, prefix):
    e = usage_rig
    assert copied_graph_consumers(e,30,16)+copied_timeline_consumers(e,count=2) == 540
    run = e.rig.root.parent / ('combined-'+e.rig.root.name)
    shutil.copytree(e.rig.root, run/'data')
    nid = e.rig.nid
    url = f'{prefix}/novels/{nid}/experimental/production/assets/{e.asset["id"]}/studio-asset-usages'
    with application(run) as client:
        cold = snapshot(run/'data')
        assert body(asset_page(client,url,strict=True),409)['code'] == 'STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE'
        assert snapshot(run/'data') == cold
        first = body(asset_page(client,url))
        next_page = body(asset_page(client,url,first['next_cursor']))
        replay=body(asset_page(client,url,first['next_cursor']))
        assert replay['items']==next_page['items'] and replay['total']==next_page['total']
        pins=[]; page=body(asset_page(client,url,strict=True)); pages=0
        while True:
            pages+=1
            pins.extend((r['owner'],r['id'],r.get('node_id',r.get('clip_id'))) for r in page['items'])
            assert page['budgets']['authority_reads_in_budget'] and page['other_dependencies']=='UNKNOWN'
            if not page['has_more']:
                assert page['total']==540
                break
            page=body(asset_page(client,url,page['next_cursor'],strict=True))
        assert pages==6 and len(pins)==len(set(pins))==540
        assert snapshot(run/'data')==cold
        chapter=body(client.post(f'{prefix}/novels/{nid}/chapters',json={'title':'Synthetic source','content':'Alice entered the forest.'}),201)
        imports=[body(client.post(f'{prefix}/novels/{nid}/experimental/imports/jobs',json={'chapter_ids':[chapter['id']]}),201) for _ in range(3)]
        before=snapshot(run/'data')
        token=traverse(client,prefix,nid,'semantic_import',[r['id'] for r in imports])
        assert snapshot(run/'data')==before
        body(client.post(f'{prefix}/novels/{nid}/experimental/imports/jobs/{imports[0]["id"]}/cancel',json={'expected_version':imports[0]['version']}))
        assert body(task_page(client,prefix,nid,'semantic_import',token),409)['code']=='TASKCENTER_CURSOR_RESTART_REQUIRED'
        # Unselected task lifecycle changes must not invalidate saved asset pins.
        assert body(asset_page(client,url,first['next_cursor']))['items']==next_page['items']
        exports=[]
        for _ in range(3):
            job=body(client.post(prefix+'/exports',params={'novel_id':nid},json={'format':'txt'}),202)
            deadline=time.monotonic()+20
            while job['status'] in ('queued','running'):
                assert time.monotonic()<deadline
                job=body(client.get(prefix+'/exports/'+job['id']))
                time.sleep(.02)
            assert job['status']=='succeeded'
            exports.append(job)
        before=snapshot(run/'data')
        export_token=traverse(client,prefix,nid,'exports',[r['id'] for r in exports])
        assert snapshot(run/'data')==before
        from copy import deepcopy
        from app.services.export_job_service import ExportJobService
        owner=ExportJobService(run/'data',lambda *_: pytest.fail('terminal fixture must not export'))
        try:
            original=owner._read()
            changed=deepcopy(original)
            changed[exports[0]['id']]['error']={'code':'SYNTHETIC_PRIVATE_ABA'}
            owner._write(changed)
            owner._write(original)
        finally:
            owner._pool.shutdown(wait=True)
        assert body(task_page(client,prefix,nid,'exports',export_token),409)['code']=='TASKCENTER_CURSOR_RESTART_REQUIRED'
        mixed=task_page(client,prefix,nid,['semantic_import','exports'])
        assert body(mixed,501)['code']=='TASKCENTER_CURSOR_UNSUPPORTED'
        # Repeated asset read after a legal owner lifecycle mutation must restart.
        timeline=body(client.get(f'{prefix}/projects/{nid}/studio/production/timelines/synthetic-timeline-0000'))
        body(client.put(f'{prefix}/projects/{nid}/studio/production/timelines/synthetic-timeline-0000',json={'expected_version':timeline['version'],'title':'Changed owner title','timeline':timeline['timeline']}))
        assert asset_page(client,url,first['next_cursor']).status_code==409
    with application(run,label='reopened') as client:
        assert task_page(client,prefix,nid,'semantic_import',token).status_code==409
        assert task_page(client,prefix,nid,'exports',export_token).status_code==409
        before=snapshot(run/'data')
        traverse(client,prefix,nid,'semantic_import',[r['id'] for r in imports])
        traverse(client,prefix,nid,'exports',[r['id'] for r in exports])
        assert body(asset_page(client,url))['items']
        assert snapshot(run/'data')==before
    with application(run,budget=4096,label='exhausted') as client:
        before=snapshot(run/'data')
        rejected=asset_page(client,url)
        assert rejected.status_code==409 and 'items' not in rejected.json()
        assert rejected.json()['code']=='STUDIO_ASSET_USAGE_UNAVAILABLE'
        # TaskCenter is deliberately not the asset-only budget contract.
        traverse(client,prefix,nid,'semantic_import',[r['id'] for r in imports])
        assert snapshot(run/'data')==before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_socket_collaboration_team_original_no_chapters_and_revocation(usage_rig, prefix):
    from test_studio_asset_query import shared_scope
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.identity import IdentityStatus
    e=usage_rig
    scope,headers=shared_scope(e.rig)
    e.rig.grants.assign_permission(PermissionAssignment('http-write','reader','domain.write',ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',e.rig.nid),'synthetic fixture'))
    body(e.client.post(e.base+'/activate',headers=headers))
    asset=e.rig.seed('collaboration-synthetic.png',scope_value=scope)
    pin={'asset_id':asset['id'],'version':asset['version'],'digest':asset['sha256'],'kind':'image'}
    body(e.client.post(e.base+'/graphs',headers=headers,json={'request_id':'http-collaboration-graph',
        'definition':{'title':'Synthetic scoped pins','nodes':[{'id':f'pin-{i}','definition_id':'asset_reference','parameters':pin} for i in range(3)]}}),201)
    run=e.rig.root.parent/('collaboration-'+e.rig.root.name)
    shutil.copytree(e.rig.root,run/'data')
    nid=e.rig.nid
    url=f'{prefix}/novels/{nid}/experimental/production/assets/{asset["id"]}/studio-asset-usages'
    with application(run,collaboration=True) as client:
        rows=[body(client.post(f'{prefix}/novels/{nid}/experimental/teams/runs',headers=headers,
            json={'recipe_id':'outline_chapter_editor','source_text':f'private-source-{i}'}),201) for i in range(3)]
        assert all(not r['sources'] and not r['model_called'] and r['external_calls']==0 for r in rows)
        before=snapshot(run/'data')
        # Original Studio collaboration reads require packaged Host authority.
        # A dev session is sufficient for this original TaskCenter window, but
        # must not be promoted into a Host session by the test harness.
        assert body(asset_page(client,url,headers=headers),403)['code']=='LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE'
        token=traverse(client,prefix,nid,'agent_team',[r['id'] for r in rows],headers)
        assert snapshot(run/'data')==before
        for authority in ('exports',['agent_team','semantic_import']):
            assert body(task_page(client,prefix,nid,authority,headers=headers),501)['code']=='TASKCENTER_CURSOR_UNSUPPORTED'
        body(client.post(f'{prefix}/novels/{nid}/experimental/teams/runs/{rows[0]["id"]}/cancel',headers=headers,json={'expected_version':rows[0]['version']}))
        assert task_page(client,prefix,nid,'agent_team',token,headers).status_code==409
        token=traverse(client,prefix,nid,'agent_team',[r['id'] for r in rows],headers)
        # Original durable identity owner mutation, externally observed by HTTP.
        from app.config import Settings
        from app.repositories.factory import create_repository_bundle
        from app.services.identity_service import IdentityService
        from app.services.collaboration_scope_service import CollaborationScopeService
        bundle=create_repository_bundle(Settings(storage_backend='file',novel_data=run/'data',enable_cloud=False,mock_provider=True),data_root=run/'data')
        identity=IdentityService(bundle.identity,CollaborationScopeService(bundle.scope,bundle.novels))
        identity.set_membership_status('reader','query-workspace',IdentityStatus.INACTIVE)
        before=snapshot(run/'data')
        assert task_page(client,prefix,nid,'agent_team',token,headers).status_code==403
        assert asset_page(client,url,headers=headers).status_code==403
        assert snapshot(run/'data')==before
        identity.set_membership_status('reader','query-workspace',IdentityStatus.ACTIVE)
        assert task_page(client,prefix,nid,'agent_team',token,headers).status_code==409
    with application(run,collaboration=True,label='reopened') as client:
        before=snapshot(run/'data')
        traverse(client,prefix,nid,'agent_team',[r['id'] for r in rows],headers)
        assert body(asset_page(client,url,headers=headers),403)['code']=='LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE'
        assert snapshot(run/'data')==before
