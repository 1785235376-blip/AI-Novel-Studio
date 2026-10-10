"""Independent isolated File/service probes; no network, no product edits."""
from pathlib import Path
import sys,os,tempfile,json,base64
root=Path(tempfile.mkdtemp(prefix='pr43-boundaries-'))
os.environ.update(PROJECT_ROOT=str(root),NOVEL_DATA_PATH=str(root/'data'),STORAGE_BACKEND='file',ENABLE_CLOUD='false',MOCK_PROVIDER='true',CREDENTIAL_VAULT_BACKEND='memory',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
sys.path.insert(0,os.environ.get('AUDIT_SOURCE_ROOT', str(Path.cwd())))
from app.repository import FileRepository
from app.repositories.file.novel import FileNovelRepository
from app.repositories.file.chapter import FileChapterRepository
from app.services.chapter_service import ChapterService
from app.experimental.store import ExperimentalStore
from app.experimental.common import DomainService
from app.experimental.flags import enabled_flags,FLAGS,require_flag
from app.experimental.research_library import ResearchLibraryService
from app.experimental.embeddings import EmbeddingService,MockEmbeddingProvider
results=[]
def check(name,fn):
 try:
  result=fn()
  assert result is True,repr(result)
  results.append({'name':name,'status':'PASS'})
 except Exception as e: results.append({'name':name,'status':'FAIL','error':repr(e)})
def denies(fn,types=(FileNotFoundError,)):
 try: fn();return False
 except types:return True
os.environ['EXPERIMENTAL_FEATURES']=''; os.environ.pop('V1_ACCEPTANCE_MODE',None)
check('all experimental default OFF',lambda:not enabled_flags())
os.environ['EXPERIMENTAL_FEATURES']=','.join(FLAGS);os.environ['V1_ACCEPTANCE_MODE']='true'
check('V1 overrides explicit all feature request',lambda:not enabled_flags())
os.environ['V1_ACCEPTANCE_MODE']='false';os.environ['EXPERIMENTAL_FEATURES']='character_mind_v2'
check('missing dependencies do not auto-enable',lambda:not enabled_flags())
os.environ['EXPERIMENTAL_FEATURES']='*'
check('wildcard does not enable',lambda:not enabled_flags())
b=FileRepository(root/'data');n=b.create_novel({'title':'Boundary','id':'a'}); b.create_novel({'title':'Other','id':'b'})
nov=FileNovelRepository(b);ch=ChapterService(FileChapterRepository(b));store=ExperimentalStore(root/'data');scope={'novel_id':'a','mode':'local'}
d=DomainService(store,nov,ch)
row=d.create('a',scope,'alice','test',{'value':'ORIGINAL'})
from app.services.v1_capability_service import CapabilityVersionConflict
check('wrong version fails compare-and-swap',lambda:denies(lambda:d.mutate('a',scope,'alice','test',row['id'],99,lambda x:x.update(value='BAD')),(CapabilityVersionConflict,)))
check('wrong CAS leaves original state',lambda:d.get('a',scope,'test',row['id'])['value']=='ORIGINAL')
check('other project cannot address same scope row',lambda:denies(lambda:d.get('b',{'novel_id':'b','mode':'local'},'test',row['id'])))
def rollback():
 try:
  with store.transaction('a',scope) as st:
   st['collections']['test'][row['id']]['value']='BAD'
   raise RuntimeError('injected transaction interruption')
 except RuntimeError:pass
 return d.get('a',scope,'test',row['id'])['value']=='ORIGINAL'
check('transaction exception does not commit File metadata',rollback)
r=ResearchLibraryService(store,nov,ch)
raw=base64.b64encode('alpha secret\n\nsecond evidence'.encode()).decode()
src=r.import_file('a',scope,'alice',{'title':'private reference','filename':'sample.txt','content_base64':raw},guard=lambda:None)
check('private research hidden from different actor',lambda:denies(lambda:r.source('a',scope,'bob',src['id'])))
check('owner sees private original exact bytes',lambda:r.original('a',scope,'alice',src['id'])[0]==base64.b64decode(raw))
public=r.edit_source('a',scope,'alice',src['id'],{'title':'published','access':'PROJECT','expected_version':1},guard=lambda:None)
check('explicit PROJECT share permits current text',lambda:r.source('a',scope,'bob',src['id'])['id']==src['id'])
check('public share never exposes old private history',lambda:denies(lambda:r.source_history('a',scope,'bob',src['id'])))
restored=r.restore_source('a',scope,'alice',src['id'],{'expected_version':2,'restore_version':1},guard=lambda:None)
check('historical restore creates new PRIVATE version',lambda:restored['version']==3 and restored['access']=='PRIVATE')
check('restore removes prior public reader access',lambda:denies(lambda:r.source('a',scope,'bob',src['id'])))
em=EmbeddingService(store,nov,ch,research=r)
check('unconfigured embedding explicitly no lexical fallback',lambda:em.status()['status']=='NOT_CONFIGURED' and em.status()['lexical_fallback'] is False)
idx=em.create_index('a',scope,'alice',{'title':'Index','entities':[{'entity_type':'RESEARCH','entity_id':src['id']}]})
check('found research is not proof of runnable embedding',lambda:idx['status']=='NOT_CONFIGURED')
check('private research index has owner gate',lambda:denies(lambda:em.owned_index('a',scope,idx['id'],'bob')))
# Synthetic vector inference only, the storage and source lifecycle is real.
em.provider=MockEmbeddingProvider()
try:
 built=em.rebuild('a',scope,'alice',idx['id'],idx['version'],check_authority=lambda:None)
 check('synthetic embedding activation explicitly labelled mock',lambda:built['status']=='ACTIVE' and 'MOCK' in str(built['model']))
 r.transition_source('a',scope,'alice',src['id'],3,'revoke',guard=lambda:None)
 current=em.get('a',scope,em.INDEXES,idx['id'])
 vectors=store.read('a',scope)['collections'].get('embedding_vectors',{})
 check('research revocation invalidates index token',lambda:current['status']=='INVALIDATED' and current.get('execution_token') is None)
 check('research revocation erases cached vectors',lambda:bool(vectors) and all(not x['vector'] for x in vectors.values()))
except Exception as exc:results.append({'name':'embedding lifecycle harness setup','status':'BLOCKED','error':repr(exc)})
print(json.dumps({'layer':'real File + original services; synthetic actor/authority callbacks and vectors; not HTTP membership/native/model verification','results':results,'root':str(root)},ensure_ascii=False,indent=2))
