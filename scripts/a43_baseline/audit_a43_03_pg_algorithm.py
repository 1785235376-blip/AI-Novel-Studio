"""Original PG repository algorithm with an explicit synthetic Session port.
No PostgreSQL server is present. This is NOT a real PostgreSQL integration test.
"""
import os,sys,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import patch
root=Path(tempfile.mkdtemp(prefix='pr43-move-algorithm-'))
os.environ.update(PROJECT_ROOT=str(root),NOVEL_DATA_PATH=str(root/'data'),ENABLE_CLOUD='false',MOCK_PROVIDER='true')
sys.dont_write_bytecode=True;sys.path.insert(0,os.environ.get('AUDIT_SOURCE_ROOT', str(Path.cwd())))
from app.repositories.postgres.chapter import PostgresChapterRepository
from app.document import markdown_to_document
novel=SimpleNamespace(id='internal-novel',slug='book')
rows=[SimpleNamespace(id='uuid-A',novel_id=novel.id,chapter_number=1,title='A',document=markdown_to_document('A manuscript'),version=1,workflow_status='DRAFT',is_archived=False,updated_at=None),SimpleNamespace(id='uuid-B',novel_id=novel.id,chapter_number=2,title='B',document=markdown_to_document('B manuscript'),version=1,workflow_status='DRAFT',is_archived=False,updated_at=None)]
class Session:
 def scalars(self,query):return SimpleNamespace(all=lambda:sorted(rows,key=lambda r:r.chapter_number))
 def flush(self):pass
class Database:
 @contextmanager
 def session(self):yield Session()
def resolve(session,cid):
 slug,num=cid.rsplit(':',1)
 return novel,next(r for r in rows if r.chapter_number==int(num))
repo=PostgresChapterRepository(Database())
with patch('app.repositories.postgres.chapter.chapter_or_raise',resolve):
 before=repo.get('book:1');returned=repo.move('book:1','down');after=repo.get('book:1')
result={'layer':'original move/get/_external code + synthetic Session/lookup; NO real PostgreSQL server','before_id':before['id'],'before_title':before['title'],'before_version':before['version'],'returned_order':returned,'after_id':after['id'],'after_title':after['title'],'after_version':after['version'],'same_id_and_version_now_different_document':before['id']==after['id'] and before['version']==after['version'] and before['document']!=after['document'],'internal_rows':[{'uuid':r.id,'number':r.chapter_number}for r in rows]}
assert result['same_id_and_version_now_different_document']
print(json.dumps(result,ensure_ascii=False,indent=2))
