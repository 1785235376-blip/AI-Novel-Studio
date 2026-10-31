"""Self-contained original File/Text renderer recovery proof on public efd.

Reimplemented after scratch reset; no unpublished TaskCenter helpers are used.
Only gates wrap original rendering and post-artifact progress; rows/results are
created by original services. Binary formats and distributed semantics excluded.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from app.repositories.factory import create_repository_bundle
from app.services.novel_service import NovelService
from app.services.chapter_service import ChapterService
from app.services.export_job_service import ExportJobService

WORKER = r'''
import json,sys,time
from pathlib import Path
from types import SimpleNamespace
from app.repositories.factory import create_repository_bundle
from app.services.novel_service import NovelService
from app.services.export_job_service import ExportJobService
root,control,nid,fmt,role,stage=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6]
bundle=create_repository_bundle(config=SimpleNamespace(storage_backend='file'),data_root=root)
novels=NovelService(bundle.novels,bundle.chapters)
def gate():
 (control/(role+'-gated')).touch()
 deadline=time.monotonic()+45
 while not (control/(role+'-release')).exists():
  if time.monotonic()>deadline:raise RuntimeError('synthetic gate expired')
  time.sleep(.01)
def exporter(nid,fmt,*,snapshot=None,progress_callback=None):
 result=novels.export(nid,fmt,snapshot=snapshot,progress_callback=progress_callback)
 (control/(role+'-rendered')).write_bytes(ExportJobService._result_bytes(result))
 if stage=='rendered':gate()
 return result
original_progress=ExportJobService._set_progress
def progress(self,jid,value,message=None):
 result=original_progress(self,jid,value,message)
 if stage=='persisted' and value==95:gate()
 return result
ExportJobService._set_progress=progress
service=ExportJobService(root,exporter,snapshotter=novels.export_snapshot)
(control/(role+'-constructed')).touch()
if role=='a':
 row=service.create(nid,fmt,'synthetic-original-generator')
 (control/'job.json').write_text(json.dumps(row))
service._pool.shutdown(wait=True)
'''

def wait(path):
 deadline=time.monotonic()+20
 while not path.exists():
  assert time.monotonic()<deadline,str(path)
  time.sleep(.01)


def finish(child):
 out,err=child.communicate(timeout=20)
 assert child.returncode==0,(out,err)


@pytest.mark.parametrize('stage',['rendered','persisted'])
@pytest.mark.parametrize('fmt',['txt','markdown','json'])
@pytest.mark.parametrize('transition',['finish','dead-recovery'])
def test_original_generator_snapshot_artifact_survives_owner_restart(tmp_path,fmt,transition,stage):
 if transition=='dead-recovery' and os.name=='nt':pytest.skip('actual POSIX SIGKILL only')
 root=tmp_path/'data';control=tmp_path/'controls';control.mkdir()
 bundle=create_repository_bundle(config=SimpleNamespace(storage_backend='file'),data_root=root)
 novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters)
 nid=novels.create({'id':'synthetic-render-book','title':'合成原始书名'})['id']
 chapter=chapters.create(nid,{'title':'第一章','content':'原始正文 Ω\n\n第二段：合成证据。'})
 children=[];source=Path(__file__).resolve().parents[1]
 def launch(role):
  child=subprocess.Popen([sys.executable,'-c',WORKER,str(root),str(control),nid,fmt,role,stage],cwd=source,
   env={**os.environ,'PYTHONPATH':str(source)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  children.append(child);return child
 try:
  a=launch('a');wait(control/'a-gated');wait(control/'job.json')
  row=json.loads((control/'job.json').read_text());jid=row['id'];snapshot=row['snapshot']
  expected=ExportJobService._result_bytes(novels.export(nid,fmt,snapshot=snapshot))
  assert (control/'a-rendered').read_bytes()==expected
  assert '原始正文 Ω' in expected.decode('utf-8')
  if fmt=='txt':assert expected=='第一章\n\n原始正文 Ω\n第二段：合成证据。'.encode('utf-8')
  artifacts=list((root/'export_artifacts').glob('*.artifact'))
  assert len(artifacts)==(1 if stage=='persisted' else 0)
  persisted_before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in artifacts}
  chapters.save(chapter['id'],{'content':'LATE_LIVE_MANUSCRIPT_MUST_NOT_LEAK'})
  novels.update(nid,{'title':'LATE_LIVE_TITLE_MUST_NOT_LEAK'})
  assert b'LATE_LIVE_MANUSCRIPT' in ExportJobService._result_bytes(novels.export(nid,fmt))
  b=launch('b');wait(control/'b-constructed');(control/'b-release').touch();finish(b)
  assert a.poll() is None
  assert not (control/'b-rendered').exists(),'live owner duplicated'
  assert {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in (root/'export_artifacts').glob('*.artifact')}==persisted_before
  if transition=='dead-recovery':
   a.kill();a.communicate(timeout=10);assert a.returncode<0
   c=launch('c');wait(control/'c-gated')
   assert (control/'c-rendered').read_bytes()==expected
   (control/'c-release').touch();finish(c)
  else:
   (control/'a-release').touch();finish(a)
  def forbidden(*args,**kwargs):pytest.fail('terminal reopen invoked exporter')
  service=ExportJobService(root,forbidden);service._pool.shutdown(wait=True)
  final=service.get(jid);assert final['status']=='succeeded'
  assert final['recovery_count']==(1 if transition=='dead-recovery' else 0)
  assert final['snapshot']==snapshot
  artifact=final['artifact'];assert artifact is not None
  path=root/'export_artifacts'/artifact['path'];assert path.is_file()
  actual=path.read_bytes();assert actual==expected
  assert artifact['size']==len(expected)
  assert artifact['sha256']==hashlib.sha256(expected).hexdigest()
  assert service.download(jid)['content']==actual
  if fmt=='json':
   decoded=json.loads(actual);assert decoded['novel']['title']=='合成原始书名'
   assert decoded['chapters'][0]['id']==chapter['id']
  else:assert '第一章' in actual.decode('utf-8')
  assert b'LATE_LIVE' not in actual
  observation=service.binding_observation([jid]);stat=path.stat()
  d=launch('d');wait(control/'d-constructed');(control/'d-release').touch();finish(d)
  assert not (control/'d-rendered').exists()
  assert service.binding_observation([jid])==observation
  assert path.read_bytes()==expected and path.stat().st_mtime_ns==stat.st_mtime_ns
  print(json.dumps({'format':fmt,'transition':transition,'stage':stage,'bytes':len(actual),
   'sha256':hashlib.sha256(actual).hexdigest(),'recovery_count':final['recovery_count'],
   'snapshot_preserved':True,'artifact_present':True},sort_keys=True))
 finally:
  for role in ('a','b','c','d'):(control/(role+'-release')).touch()
  for child in children:
   if child.poll() is None:child.kill()
   child.communicate(timeout=10)
