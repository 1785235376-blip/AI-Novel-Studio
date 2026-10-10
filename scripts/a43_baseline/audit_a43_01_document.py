from pathlib import Path
import os,sys,tempfile,json,io,zipfile
root=Path(tempfile.mkdtemp(prefix='pr43-doc-audit-'))
os.environ.update(PROJECT_ROOT=str(root),NOVEL_DATA_PATH=str(root/'data'),STORAGE_BACKEND='file',ENABLE_CLOUD='false',MOCK_PROVIDER='true',CREDENTIAL_VAULT_BACKEND='memory',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
sys.path.insert(0,os.environ.get('AUDIT_SOURCE_ROOT', str(Path.cwd())))
from app.repository import FileRepository
from app.repositories.file.chapter import FileChapterRepository
from app.services.chapter_service import ChapterService
from app.document import document_to_markdown,plain_text
from app.export_formats import novel_to_docx
b=FileRepository(root/'data'); n=b.create_novel({'title':'审计合成作品','id':'audit-prose'})
r=FileChapterRepository(b);s=ChapterService(r)
c=s.create(n['id'],{'title':'第一章','content':'原始合成正文'})
doc={'type':'doc','content':[
 {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'第一章'}]},
 {'type':'paragraph','content':[{'type':'text','text':'普通段落保留'}]},
 {'type':'bulletList','content':[{'type':'listItem','content':[{'type':'paragraph','content':[{'type':'text','text':'清单关键线索LISTSECRET'}]}]}]},
 {'type':'blockquote','content':[{'type':'paragraph','content':[{'type':'text','text':'证言关键线索QUOTESECRET'}]}]},
 {'type':'paragraph','content':[{'type':'text','text':'前句'}, {'type':'hardBreak'}, {'type':'text','text':'后句'}]},
]}
x=s.save(c['id'],{'version':1,'document':doc})
y=s.get(c['id']);dup=s.duplicate(c['id'])
blob=novel_to_docx('审计合成作品',[y])
xml=zipfile.ZipFile(io.BytesIO(blob)).read('word/document.xml').decode()
res={'saved_version':x['version'],'original_document_preserved':y['document']==doc,'projected_content':y['content'],
'duplicate_document':dup['document'],'duplicate_list_text_present':'LISTSECRET' in json.dumps(dup['document']),
'duplicate_quote_text_present':'QUOTESECRET' in json.dumps(dup['document']),
'docx_list_text_present':'LISTSECRET' in xml,'docx_quote_text_present':'QUOTESECRET' in xml,'plain_text':plain_text(doc),'root':str(root)}

# Exercise original NovelService snapshot and export entry, not only the renderer.
from app.repositories.file.novel import FileNovelRepository
from app.services.novel_service import NovelService
ns=NovelService(FileNovelRepository(b),r)
snap=ns.export_snapshot(n['id'],format='docx')
service_export=ns.export(n['id'],'docx',snapshot=snap)
import base64
service_xml=zipfile.ZipFile(io.BytesIO(base64.b64decode(service_export['content_base64']))).read('word/document.xml').decode()
res['original_novel_service_snapshot_export']={'list_text_present':'LISTSECRET' in service_xml,'quote_text_present':'QUOTESECRET' in service_xml,'snapshot_chapter_count':len(snap['source']['chapters'])}
print(json.dumps(res,ensure_ascii=False,indent=2))
