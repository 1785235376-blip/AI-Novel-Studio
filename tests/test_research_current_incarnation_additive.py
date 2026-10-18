"""Native Research reads must not adopt retained records after public-id reuse."""
import copy
import hashlib
import json
import pytest
from app.experimental.research_library import ResearchLibraryService
from test_v2_creative_project_lifecycle import rig,TITLE
from test_r4_research_library import payload,citation


def capture(e,label,state,**extra):
    raw=json.dumps(state,ensure_ascii=False,sort_keys=True).encode()
    destination=e.root/'.incarnation-evidence';destination.mkdir(exist_ok=True)
    (destination/(label+'.json')).write_text(json.dumps({'backend':e.backend,'public_project_id':e.nid,
        'persisted_scope_sha256':hashlib.sha256(raw).hexdigest(),'persisted_scope':state,**extra},ensure_ascii=False,indent=2)+'\n')


def previous_project(e):
    service=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True)
    first=service.import_file(e.nid,e.scope,e.actor,payload('Old incarnation private evidence.'),guard=lambda:None)
    service.replace_file(e.nid,e.scope,e.actor,first['id'],{**payload('Old incarnation current replacement.'),'expected_version':1},guard=lambda:None)
    current=service.source(e.nid,e.scope,e.actor,first['id'])
    saved=copy.deepcopy(e.store.read(e.nid,e.scope));old_identity=service.history_identity(e.nid)
    capture(e,'before-recreation',saved,project_incarnation=old_identity)
    e.novels.delete(e.nid);assert e.novels.create({'title':TITLE})['id']==e.nid
    assert e.store.read(e.nid,e.scope)==saved
    capture(e,'after-recreation',e.store.read(e.nid,e.scope))
    return service,first,current,saved,old_identity


@pytest.mark.parametrize('operation',['source','original','history','resolve'])
def test_current_reads_refuse_previous_incarnation_without_rewriting_retained_records(rig,operation):
    e=rig;service,first,current,saved,_=previous_project(e)
    calls={'source':lambda:service.source(e.nid,e.scope,e.actor,first['id']),
           'original':lambda:service.original(e.nid,e.scope,e.actor,first['id']),
           'history':lambda:service.source_history(e.nid,e.scope,e.actor,first['id']),
           'resolve':lambda:service.resolve(e.nid,e.scope,e.actor,citation(current))}
    denied=False
    try:calls[operation]()
    except FileNotFoundError:denied=True
    capture(e,'after-'+operation,e.store.read(e.nid,e.scope),denied=denied)
    assert e.store.read(e.nid,e.scope)==saved
    assert denied,'Retained previous-project record was exposed through '+operation


def test_old_records_are_absent_from_current_list_and_new_owner_positive_still_works(rig):
    e=rig;service,first,current,saved,old_identity=previous_project(e)
    visible=service.sources(e.nid,e.scope,e.actor)
    assert e.store.read(e.nid,e.scope)==saved
    capture(e,'after-list',e.store.read(e.nid,e.scope),visible_ids=[r['id'] for r in visible['items']])
    assert visible['items']==[]
    fresh=service.import_file(e.nid,e.scope,e.actor,payload('New owner legitimate evidence.'),guard=lambda:None)
    assert service.history_identity(e.nid)!=old_identity
    assert [r['id'] for r in service.sources(e.nid,e.scope,e.actor)['items']]==[fresh['id']]
    assert service.resolve(e.nid,e.scope,e.actor,citation(fresh))['text']=='New owner legitimate evidence.'
    current_state=e.store.read(e.nid,e.scope)
    assert current_state['collections']['research_sources'][first['id']]==saved['collections']['research_sources'][first['id']]
    capture(e,'after-fresh-positive',current_state,current_visible_id=fresh['id'],project_incarnation=service.history_identity(e.nid))



@pytest.mark.parametrize('operation',['edit','delete','note-history'])
def test_retired_note_cannot_be_rebound_or_mutated(rig,operation):
    e=rig;service=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True)
    source=service.import_file(e.nid,e.scope,e.actor,payload(),guard=lambda:None)
    note=service.create_note(e.nid,e.scope,e.actor,{'title':'Old note','text':'Old private note','citations':[citation(source)]},guard=lambda:None)
    before=copy.deepcopy(e.store.read(e.nid,e.scope));capture(e,'note-before-recreation',before)
    e.novels.delete(e.nid);assert e.novels.create({'title':TITLE})['id']==e.nid
    fresh=service.import_file(e.nid,e.scope,e.actor,payload('Fresh source'),guard=lambda:None)
    saved=copy.deepcopy(e.store.read(e.nid,e.scope))
    calls={'edit':lambda:service.edit_note(e.nid,e.scope,e.actor,note['id'],{'title':'Rebound','text':'New text','citations':[citation(fresh)],'expected_version':1},guard=lambda:None),
           'delete':lambda:service.delete_note(e.nid,e.scope,e.actor,note['id'],1,guard=lambda:None),
           'note-history':lambda:service.note_history(e.nid,e.scope,e.actor,note['id'])}
    with pytest.raises(FileNotFoundError):calls[operation]()
    assert service.notes(e.nid,e.scope,e.actor)['items']==[]
    assert service.note_repairs(e.nid,e.scope,e.actor)['items']==[]
    assert e.store.read(e.nid,e.scope)==saved
    capture(e,'note-after-denial',e.store.read(e.nid,e.scope),denied=True)
    new_note=service.create_note(e.nid,e.scope,e.actor,{'title':'New note','text':'Legitimate','citations':[citation(fresh)]},guard=lambda:None)
    assert [r['id'] for r in service.notes(e.nid,e.scope,e.actor)['items']]==[new_note['id']]


def test_same_owner_stale_note_repair_and_unbound_revision_refusal(rig):
    e=rig;service=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True)
    source=service.import_file(e.nid,e.scope,e.actor,payload(),guard=lambda:None)
    note=service.create_note(e.nid,e.scope,e.actor,{'title':'Note','text':'Authored','citations':[citation(source)]},guard=lambda:None)
    current=service.replace_file(e.nid,e.scope,e.actor,source['id'],{**payload('Replacement'),'expected_version':1},guard=lambda:None)
    assert service.note_repairs(e.nid,e.scope,e.actor)['items'][0]['id']==note['id']
    edited=service.edit_note(e.nid,e.scope,e.actor,note['id'],{'title':'Note','text':'Repaired','citations':[citation(current)],'expected_version':1},guard=lambda:None)
    assert edited['version']==2
    with e.store.transaction(e.nid,e.scope) as state:
        state['collections']['research_sources'][source['id']]['history'][0].pop('research_project_incarnation')
    saved=copy.deepcopy(e.store.read(e.nid,e.scope))
    assert len(service.source_history(e.nid,e.scope,e.actor,source['id'])['items'])==1
    with pytest.raises(FileNotFoundError):service.historical_original(e.nid,e.scope,e.actor,source['id'],1)
    with pytest.raises(FileNotFoundError):service.restore_source(e.nid,e.scope,e.actor,source['id'],{'expected_version':2,'restore_version':1},guard=lambda:None)
    assert e.store.read(e.nid,e.scope)==saved


def test_reads_do_not_provision_identity_or_adopt_unbound_legacy(rig):
    from types import SimpleNamespace
    e=rig
    legacy=SimpleNamespace(list_research=lambda nid: {'items':[{'id':'old','status':'ACTIVE','version':1,'excerpt':'Previous legacy secret'}]})
    service=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True,legacy=legacy)
    before=service.current_identity(e.nid)
    assert service.sources(e.nid,e.scope,e.actor)['items']==[]
    assert service.current_identity(e.nid)==before


def test_retired_analysis_receipt_hidden_and_cannot_cancel(rig):
    e=rig;service=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True)
    source=service.import_file(e.nid,e.scope,e.actor,payload(),guard=lambda:None)
    # The original job owner validates source format. Use a real local PNG.
    import base64,io
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(4,4),'blue').save(stream,format='PNG')
    image=service.import_file(e.nid,e.scope,e.actor,{**payload(),'filename':'sample.png','content_base64':base64.b64encode(stream.getvalue()).decode()},guard=lambda:None)
    job=service.create_analysis(e.nid,e.scope,e.actor,{'source_id':image['id'],'source_version':1,'operation':'OCR'},guard=lambda:None)
    assert service.analysis_job(e.nid,e.scope,e.actor,job['id'])['id']==job['id']
    e.novels.delete(e.nid);assert e.novels.create({'title':TITLE})['id']==e.nid
    saved=copy.deepcopy(e.store.read(e.nid,e.scope))
    assert service.analysis_jobs(e.nid,e.scope,e.actor)['items']==[]
    with pytest.raises(FileNotFoundError):service.analysis_job(e.nid,e.scope,e.actor,job['id'])
    with pytest.raises(FileNotFoundError):service.analysis_action(e.nid,e.scope,e.actor,job['id'],'cancel',job['version'],guard=lambda:None)
    assert e.store.read(e.nid,e.scope)==saved
