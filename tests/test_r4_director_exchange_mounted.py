"""Actual application routes, dual prefixes, real File/PG scopes; no stub auth."""
import json
import pytest
from app.experimental.flags import FLAGS
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_director import plan_body
from test_r4_timeline_exchange import source_timeline, as_text, otio
pytestmark = pytest.mark.skipif(otio is None, reason="NOT_RUN: mounted exchange journey needs pinned optional otio extra")


@pytest.fixture
def production_mounted(mounted, monkeypatch):
    e=mounted
    for service in (e.experimental.director_service,e.experimental.timeline_exchange_service):
        for key,value in [('store',e.store),('novels',e.novels),('chapters',e.chapters),('screenplays',e.screenplays)]:
            monkeypatch.setattr(service,key,value)
        if hasattr(service,'assets'):monkeypatch.setattr(service,'assets',e.assets)
    e.director=e.experimental.director_service;e.exchange=e.experimental.timeline_exchange_service
    return e


def create_shots(e,headers=None):
    headers=headers or {}
    row=checked(e.client.post(e.prefix+f'/novels/{e.nid}/screenplays',json={'title':'Synthetic camera review'},headers=headers),201)
    row=checked(e.client.post(e.prefix+f"/novels/{e.nid}/screenplays/{row['id']}/approve",json={'expected_version':row['edit_version']},headers=headers))
    return checked(e.client.post(e.prefix+f"/novels/{e.nid}/screenplays/{row['id']}/shots",json={'expected_version':row['edit_version']},headers=headers),201)


def test_mounted_original_review_camera_metadata_off_and_real_otio_file(production_mounted,monkeypatch):
    e=production_mounted;row=create_shots(e)
    created=checked(e.client.post(e.base+'/director/plans',json=plan_body(row)),201)
    comparison=checked(e.client.post(e.base+'/director/compare',json={'plan_ids':[created['id']]}))
    applied=checked(e.client.post(e.base+f"/director/plans/{created['id']}/apply",json={'expected_version':1,'comparison_digest':comparison['application_digests'][created['id']]}))
    assert applied['edit_version']==row['edit_version']+1
    old_path=e.prefix+f'/novels/{e.nid}/screenplays'
    listed=checked(e.client.get(old_path));assert listed[0]['shots'][0]['director']['scene_purpose']=='Reveal the harbor'
    assert 'director_applied_plan_id' not in json.dumps(listed)
    row=checked(e.client.post(old_path+f"/{row['id']}/shots/approve",json={'expected_version':applied['edit_version']}))
    exported=checked(e.client.post(e.base+'/timeline-exchange/from-screenplay',json={'screenplay_id':row['id'],'expected_screenplay_version':row['edit_version'],'shots':[{'shot_id':row['shots'][0]['id']}]}),201)
    file_path=e.base+f"/timeline-exchange/records/{exported['id']}/file?expected_version=1&acknowledge_losses=true"
    download=e.client.get(file_path);assert download.status_code==200 and download.headers['cache-control']=='no-store'
    assert json.loads(download.content)['OTIO_SCHEMA'].startswith('Timeline.')
    assert download.headers['content-disposition'].endswith('.otio"')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(e.base+'/director/catalog').status_code==404
    assert e.client.get(file_path).status_code==404
    assert 'Reveal the harbor' not in json.dumps(checked(e.client.get(old_path)))
    history=checked(e.client.get(old_path+f"/{row['id']}/revisions"))
    assert 'Reveal the harbor' not in json.dumps(history) and 'director_stale_outputs' not in json.dumps(history)


def test_all_off_wildcard_missing_dependency_and_v1_force_disabled(production_mounted,monkeypatch):
    e=production_mounted
    for flags,v1 in [('', 'false'),('*','false'),('timeline_exchange_v2','false'),(','.join(FLAGS),'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES',flags);monkeypatch.setenv('V1_ACCEPTANCE_MODE',v1)
        assert e.client.get(e.base+'/timeline-exchange/catalog').status_code==404
        assert e.client.post(e.base+'/timeline-exchange/import',json={'filename':'x.otio','content':as_text(source_timeline())}).status_code==404
    assert not e.store.read(e.nid,e.scope)['collections'].get(e.exchange.RECORDS)


def test_real_session_branch_and_actor_hide_imported_external_references(production_mounted,monkeypatch):
    e=scoped(production_mounted,monkeypatch)
    row=checked(e.client.post(e.base+'/timeline-exchange/import',json={'filename':'private.otio','content':as_text(source_timeline())},headers=e.headers),201)
    for headers in [{},e.viewer_headers,{**e.headers,'X-Branch-ID':e.other_branch}]:
        response=e.client.get(e.base+'/timeline-exchange/records',headers=headers)
        assert row['id'] not in response.text and 'media/a.mp4' not in response.text
    assert checked(e.client.get(e.base+'/timeline-exchange/records',headers=e.headers))['items'][0]['id']==row['id']
    response=e.client.get(e.base+f"/timeline-exchange/records/{row['id']}/file?expected_version=1&acknowledge_losses=true",headers=e.viewer_headers)
    assert response.status_code==404 and 'media/a.mp4' not in response.text


@pytest.mark.parametrize('change',['role','flag','v1'])
def test_import_rechecks_authority_after_parser_before_persist(production_mounted,monkeypatch,change):
    import app.experimental.timeline_exchange as module
    e=scoped(production_mounted,monkeypatch);original=module.write_otio
    def parsing(doc):
        result=original(doc)
        if change=='role':e.authorization.revoke_role(e.role,e.lead)
        elif change=='flag':monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
        else:monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
        return result
    monkeypatch.setattr(module,'write_otio',parsing)
    response=e.client.post(e.base+'/timeline-exchange/import',json={'filename':'x.otio','content':as_text(source_timeline())},headers=e.headers)
    assert response.status_code in {403,404} and 'media/a.mp4' not in response.text
    assert not e.store.read(e.nid,e.scope)['collections'].get(e.exchange.RECORDS)


def test_read_rechecks_current_authority_before_emitting_projection(production_mounted,monkeypatch):
    e=scoped(production_mounted,monkeypatch)
    checked(e.client.post(e.base+'/timeline-exchange/import',json={'filename':'x.otio','content':as_text(source_timeline())},headers=e.headers),201)
    original=e.exchange.records
    def projection(*args):
        result=original(*args);e.sessions.revoke(e.lead);return result
    monkeypatch.setattr(e.exchange,'records',projection)
    response=e.client.get(e.base+'/timeline-exchange/records',headers=e.headers)
    assert response.status_code==401 and 'media/a.mp4' not in response.text


def test_legacy_reads_and_conflict_snapshots_hide_applied_metadata_after_privacy_change(production_mounted):
    from app.source_privacy import review_source_privacy, content_digest
    e=production_mounted;row=create_shots(e)
    plan=checked(e.client.post(e.base+'/director/plans',json=plan_body(row)),201)
    compared=checked(e.client.post(e.base+'/director/compare',json={'plan_ids':[plan['id']]}))
    applied=checked(e.client.post(e.base+f"/director/plans/{plan['id']}/apply",json={'expected_version':1,'comparison_digest':compared['application_digests'][plan['id']]}))
    review_source_privacy(e.chapter,None,'local-author','CLOUD_ALLOWED',e.chapter['version'],content_digest(e.chapter),e.root)
    path=e.prefix+f'/novels/{e.nid}/screenplays'
    assert 'Reveal the harbor' not in e.client.get(path).text
    assert 'Reveal the harbor' not in e.client.get(path+f"/{row['id']}/revisions").text
    conflict=e.client.post(path+f"/{row['id']}/shots/approve",json={'expected_version':row['edit_version']})
    assert conflict.status_code==409 and 'Reveal the harbor' not in conflict.text
    assert applied['edit_version']==e.screenplays.list(e.nid)[0]['edit_version']


def test_legacy_mid_read_flag_revocation_hides_new_metadata(production_mounted,monkeypatch):
    e=production_mounted;row=create_shots(e)
    plan=checked(e.client.post(e.base+'/director/plans',json=plan_body(row)),201)
    compared=checked(e.client.post(e.base+'/director/compare',json={'plan_ids':[plan['id']]}))
    checked(e.client.post(e.base+f"/director/plans/{plan['id']}/apply",json={'expected_version':1,'comparison_digest':compared['application_digests'][plan['id']]}))
    original=e.screenplays.list
    def changed(*args,**kwargs):
        result=original(*args,**kwargs);monkeypatch.setenv('V1_ACCEPTANCE_MODE','true');return result
    monkeypatch.setattr(e.screenplays,'list',changed)
    response=e.client.get(e.prefix+f'/novels/{e.nid}/screenplays')
    assert response.status_code==200 and 'Reveal the harbor' not in response.text
