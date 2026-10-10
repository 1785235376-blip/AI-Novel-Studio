from pathlib import Path
import os,sys,tempfile,json
r=Path(tempfile.mkdtemp(prefix='pr43-identity-audit-'))
os.environ.update(PROJECT_ROOT=str(r),NOVEL_DATA_PATH=str(r/'data'),STORAGE_BACKEND='file',ENABLE_CLOUD='false',MOCK_PROVIDER='true',CREDENTIAL_VAULT_BACKEND='memory')
sys.dont_write_bytecode=True;sys.path.insert(0,os.environ.get('AUDIT_SOURCE_ROOT', str(Path.cwd())))
from app.repository import FileRepository
from app.repositories.file.chapter import FileChapterRepository
from app.services.chapter_service import ChapterService
b=FileRepository(r/'data');b.create_novel({'id':'identity','title':'合成身份试验'}); s=ChapterService(FileChapterRepository(b))
old=s.create('identity',{'title':'旧章节','content':'OLD-CONTENT-NOT-NEW'})
old=s.save(old['id'],{'version':1,'content':'旧章第二版'})
old_id=old['id'];old_history=s.history(old_id)
s.delete(old_id)
new=s.create('identity',{'title':'全新章节','content':'NEW-CONTENT'})
new=s.get(new['id']);new_history=s.history(new['id'])
restored=s.restore(new['id'],1,new['version'])
res={'old_id':old_id,'new_id':new['id'],'new_document_before_restore':new['document'],
'old_history_count':len(old_history),'new_history_count':len(new_history),'new_history_contains_old': 'OLD-CONTENT-NOT-NEW' in json.dumps(new_history),
'restored_new_document':restored['document'],'restored_contains_old':'OLD-CONTENT-NOT-NEW' in json.dumps(restored['document']),
'after_restore_version':restored['version']}
# Explicit-number creation against an existing chapter has no guard in File owner.
b.create_novel({'id':'collision','title':'合成冲突'});a=s.create('collision',{'number':1,'title':'应保留','content':'KEEP-THIS'})
again=s.create('collision',{'number':1,'title':'第二次创建','content':'OVERWROTE'})
res['explicit_duplicate_number']={'same_id':a['id']==again['id'],'listed_content':b.chapter(a['id'])['content'],'raise_conflict':False}

# Archive/delete/create is a normal lifecycle; old archive bit must not hide a new chapter.
b.create_novel({'id':'archived-reuse','title':'Archive lifecycle'})
a=s.create('archived-reuse',{'title':'archived old','content':'OLD'})
s.archive(a['id'],1);s.delete(a['id'])
fresh=s.create('archived-reuse',{'title':'new visible expected','content':'NEW'})
res['archive_inheritance']={'new_id':fresh['id'],'new_is_archived':fresh.get('is_archived'),'visible_chapters':s.list('archived-reuse')}
print(json.dumps(res,ensure_ascii=False,indent=2))
