import shutil,time
from pathlib import Path

import pytest
from app import jobs as jobs_module
from app.jobs import JobManager
from app.config import settings
from app.providers import MockProvider

def wait(job):
    for _ in range(100):
        if job.status in JobManager.terminal:return
        time.sleep(.01)
@pytest.mark.file_backend_only
def test_generate_accept_requires_explicit_commit(tmp_path,monkeypatch):
    source=Path(__file__).parents[1]/"novel_data"/"novels"/"sample_novel"; target=tmp_path/"novels"/"sample_novel"; shutil.copytree(source,target)
    monkeypatch.setattr(jobs_module.repo,"data",tmp_path); monkeypatch.setattr(jobs_module.repo,"novels",tmp_path/"novels")
    object.__setattr__(settings,"mock_provider",True)
    jobs_module.runtime.providers["mock"] = MockProvider(delay_ms=0)
    class NoopMemoryAgent:
        def enqueue(self,*args,**kwargs): return "test-memory-job"
    manager=JobManager(memory_extractor=NoopMemoryAgent()); before=(target/"chapters/chapter-0002.md").read_text(encoding="utf-8")
    job=manager.create("continue",{"novel_id":"sample_novel","chapter_id":"sample_novel:2","profile":"LOCAL_ONLY","instruction":"continue"}); wait(job)
    assert job.status=="COMPLETED" and (target/"chapters/chapter-0002.md").read_text(encoding="utf-8")==before
    result=manager.accept(job.id); assert result["chapter"]["content"]!=before and result["pending_canon"]["status"]=="PENDING"
@pytest.mark.file_backend_only
def test_cancel_mock_job(tmp_path,monkeypatch):
    source=Path(__file__).parents[1]/"novel_data"/"novels"/"sample_novel"; target=tmp_path/"novels"/"sample_novel"; shutil.copytree(source,target)
    monkeypatch.setattr(jobs_module.repo,"data",tmp_path); monkeypatch.setattr(jobs_module.repo,"novels",tmp_path/"novels")
    object.__setattr__(settings,"mock_provider",True)
    jobs_module.runtime.providers["mock"] = MockProvider(delay_ms=0)
    manager=JobManager(memory_extractor=type("NoopMemoryAgent",(),{"enqueue":lambda self,*args,**kwargs:"test-memory-job"})()); job=manager.create("continue",{"novel_id":"sample_novel","chapter_id":"sample_novel:2","profile":"LOCAL_ONLY"}); manager.cancel(job.id); wait(job); assert job.status in {"CANCELLED","FAILED"}
