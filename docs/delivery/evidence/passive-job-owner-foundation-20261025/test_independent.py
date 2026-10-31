from copy import deepcopy
import json
from uuid import uuid4, UUID
from types import SimpleNamespace
from contextlib import contextmanager
import pytest
from app.services.generation_project_binding import ordinary_job_binding, FIELD
from app.repositories.generation_repository import GenerationRepository, GenerationProjectIdentityError
from app.repositories.postgres.generation import PostgresGenerationRepository


def record(backend='file'):
    item = dict(id=str(uuid4()), novel_id='book', chapter_id=None, operation='brainstorm',actor_id=None,workspace_id=None,scope=None,scope_type=None,scope_id=None,experimental_origin=None,status='QUEUED')
    item[FIELD] = dict(schema_version=1,project_incarnation=backend+':'+str(uuid4()),job_id=item['id'],project_id='book',**{k:item[k] for k in ('chapter_id','operation','actor_id','workspace_id','scope','scope_type','scope_id','experimental_origin')})
    return item

def setup(tmp_path):
    item=record(); repo=GenerationRepository(tmp_path)
    owner=tmp_path/'novels'/'book';owner.mkdir(parents=True)
    marker=owner/'creative_project_v2.json'
    marker.write_text(json.dumps({'schema_version':1,'project_incarnation':item[FIELD]['project_incarnation'][5:]}))
    return item,repo,marker

@pytest.mark.parametrize('bad',[None,{},False,[],{'schema_version':2}])
def test_invalid_presence(bad):
    item=record();item[FIELD]=bad
    with pytest.raises(ValueError):ordinary_job_binding(item)

@pytest.mark.parametrize('key',['graph_binding','adaptation_binding','creative_director_binding','director_image_binding','research_ocr_binding'])
def test_mixed_null_specialized(key):
    item=record();item[key]=None
    with pytest.raises(ValueError):ordinary_job_binding(item)

@pytest.mark.parametrize('version',[True,1.0,'1',2,None])
def test_strict_version(version):
    item=record();item[FIELD]['schema_version']=version
    with pytest.raises(ValueError):ordinary_job_binding(item)

@pytest.mark.parametrize('key',['schema_version','project_incarnation','job_id','project_id','chapter_id','operation','actor_id','workspace_id','scope','scope_type','scope_id'])
def test_required_binding_keys(key):
    item=record();del item[FIELD][key]
    with pytest.raises(ValueError):ordinary_job_binding(item)

def test_file_mutations_and_no_upgrade(tmp_path):
    item,repo,marker=setup(tmp_path); repo.save(item)
    for key,new in [('chapter_id','book:c'),('operation','review'),('project_incarnation','file:'+str(uuid4()))]:
        changed=deepcopy(item);changed[FIELD][key]=new
        if key!='project_incarnation':changed[key]=new
        with pytest.raises(ValueError):repo.save(changed)
        assert repo.get(item['id'])==item
    unbound=deepcopy(item);unbound.pop(FIELD)
    with pytest.raises(ValueError):repo.save(unbound)
    other=record();unbound=deepcopy(other);unbound.pop(FIELD);repo.save(unbound)
    other[FIELD]['project_incarnation']=item[FIELD]['project_incarnation']
    with pytest.raises(ValueError):repo.save(other)

def test_no_marker_creation_and_stale_reads(tmp_path):
    item,repo,marker=setup(tmp_path);repo.save(item);marker.unlink()
    with pytest.raises(ValueError):repo.save(item)
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[] and not marker.exists()
    marker.write_text(json.dumps({'schema_version':1,'project_incarnation':str(uuid4())}))
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[]

def test_file_foreign_filename(tmp_path):
    item,repo,marker=setup(tmp_path);other=str(uuid4())
    (repo.root/(other+'.json')).write_text(json.dumps(item))
    with pytest.raises(KeyError):repo.get(other)
    assert repo.load_all()==[]

def test_malformed_get_is_missing(tmp_path):
    item,repo,marker=setup(tmp_path);item[FIELD]=None
    (repo.root/(item['id']+'.json')).write_text(json.dumps(item))
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[]

class Session:
    def __init__(self,row,owner):self.row,self.owner=row,owner;self.statements=[];self.flushed=False
    def get(self,*args):return self.row
    def scalar(self,statement):
        self.statements.append(str(statement));return self.owner if 'FROM novels' in str(statement) else self.row
    def scalars(self,*args):return SimpleNamespace(all=lambda:[self.row])
    def flush(self):self.flushed=True
class DB:
    def __init__(self,s):self.s=s
    @contextmanager
    def session(self):yield self.s

def pg_setup():
    item=record('postgres');uid=UUID(item[FIELD]['project_incarnation'][9:]);row=SimpleNamespace(id=UUID(item['id']),novel_id=uid,chapter_id=None,operation=item['operation'],request={'_repository_payload':deepcopy(item)},status='QUEUED',context_snapshot_id=None,result=None,error_code=None,error_message=None)
    s=Session(row,SimpleNamespace(id=uid));return item,row,s,PostgresGenerationRepository(DB(s))

def test_pg_offline_payload_row_id_mismatch():
    item,row,s,repo=pg_setup();row.id=uuid4()
    with pytest.raises(KeyError):repo.get(str(row.id))
    assert repo.load_all()==[]

def test_pg_offline_row_operation_mismatch():
    item,row,s,repo=pg_setup();row.operation='review'
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[]

def test_pg_offline_mutation_and_owner():
    item,row,s,repo=pg_setup();repo.save(item);assert s.flushed
    assert 'FROM novels' in s.statements[0] and 'FOR UPDATE' in s.statements[0]
    s.owner.id=uuid4();s.flushed=False
    with pytest.raises(ValueError):repo.save(item)
    assert not s.flushed
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[]

@pytest.mark.parametrize('kind',['WORKSPACE','PROJECT','STORYLINE','BRANCH'])
def test_scope_exact_variants(kind):
    item=record();scope=dict(kind=kind,workspace_id='ws',project_id=None,storyline_id=None,branch_id=None)
    if kind!='WORKSPACE':scope['project_id']='book'
    if kind in ('STORYLINE','BRANCH'):scope['storyline_id']='story'
    if kind=='BRANCH':scope['branch_id']='branch'
    update=dict(actor_id='actor',workspace_id='ws',scope=scope,scope_type=kind,scope_id={'WORKSPACE':'ws','PROJECT':'book','STORYLINE':'story','BRANCH':'branch'}[kind],experimental_origin='branch_manuscript' if kind=='BRANCH' else None)
    item.update(deepcopy(update));item[FIELD].update(deepcopy(update));ordinary_job_binding(item)
    bad=deepcopy(item);bad['scope']['extra']='hidden'
    with pytest.raises(ValueError):ordinary_job_binding(bad)
    bad=deepcopy(item);bad[FIELD]['scope']['extra']='hidden'
    with pytest.raises(ValueError):ordinary_job_binding(bad)

@pytest.mark.parametrize('origin',['creative_graph_model','creative_adaptation_model','creative_director_source_model','creative_director_image_model_v3','research_ocr_model'])
def test_reserved_origins(origin):
    item=record();item['experimental_origin']=origin;item[FIELD]['experimental_origin']=origin
    with pytest.raises(ValueError):ordinary_job_binding(item)

def test_pg_offline_null_binding_filtered():
    item,row,s,repo=pg_setup();row.request['_repository_payload'][FIELD]=None
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[]

def test_original_specialized_classifier_equivalence():
    from pathlib import Path
    from types import ModuleType
    from app.repositories.generation_repository import graph_job_binding
    module=ModuleType('app.repositories.baseline_generation');module.__package__='app.repositories'
    exec(Path(__file__).with_name('baseline_generation.py').read_text(),module.__dict__)
    def outcome(call,item):
        try:return ('ok',call(item))
        except Exception as e:return ('error',type(e).__name__,str(e))
    fixtures=[{},dict(id='legacy',operation='continue')]
    for key in ('graph_binding','adaptation_binding','creative_director_binding','director_image_binding','research_ocr_binding','research_ocr_output_evidence'):
        for value in (None,{},[],False,'bad'):
            fixtures.append(dict(id=str(uuid4()),novel_id='book',operation='brainstorm',**{key:value}))
    for op,origin in [('graph_text','creative_graph_model'),('brainstorm','creative_adaptation_model'),('creative_director_text','creative_director_source_model'),('creative_director_image_v3','creative_director_image_model_v3'),('research_ocr','research_ocr_model')]:
        fixtures += [dict(id=str(uuid4()),operation=op),dict(id=str(uuid4()),experimental_origin=origin)]
    for item in fixtures:assert outcome(graph_job_binding,item)==outcome(module.graph_job_binding,item),item

@pytest.mark.parametrize('key',['research_ocr_output_evidence','_creative_director_terminal_evidence','director_image_terminal_v3'])
def test_specialized_terminal_markers_refused(key):
    item=record();item[key]=None
    with pytest.raises(ValueError):ordinary_job_binding(item)

def test_pg_offline_missing_saved_id_filtered():
    item,row,s,repo=pg_setup();del row.request['_repository_payload']['id']
    with pytest.raises(KeyError):repo.get(item['id'])
    assert repo.load_all()==[]
