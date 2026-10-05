from types import SimpleNamespace as S
from unittest.mock import patch

import pytest

from app.jobs import Job, JobManager
from app.model_runtime import GenerationEvent, GenerationUsage, TextGenerationResponse
from app.router import Route
from app.source_privacy import review_source_privacy, content_digest


def rig(monkeypatch, tmp_path, policy=None, approve=False):
    import app.jobs as module
    from app.config import settings
    object.__setattr__(settings,"novel_data",tmp_path / "novels")
    chapter={"id":"n:1","novel_id":"n","number":1,"version":1,"content":"SYNTHETIC_CHAPTER_CANARY"}
    if policy is not None:chapter["privacy_level"]=policy
    if approve:review_source_privacy(chapter,None,"test","CLOUD_ALLOWED",1,content_digest(chapter))
    captured=[]
    class Node:
        def stream(self,value):
            captured.append(value.request.prompt)
            yield GenerationEvent("generation.delta",None,delta="draft")
            yield GenerationEvent("generation.completed",None,response=TextGenerationResponse("draft","stop","remote","selected",GenerationUsage(3,2,5),provider_reference_id="synthetic-reference"))
    runtime=S(is_remote_text_provider=lambda _:True,router=lambda *_:S(routes={"writer":[Route("remote","selected")]}),packaged_author_route_ready=lambda _:True,prepare_text_route=lambda *_:Node())
    monkeypatch.setattr(module,"runtime",runtime)
    monkeypatch.setattr(module,"runtime_log",S(write=lambda **_:None))
    monkeypatch.setattr(module,"deterministic_review",lambda *_:[])
    manager=JobManager.__new__(JobManager)
    manager.chapters=S(get=lambda _:chapter)
    manager.contexts=S(for_chapter=lambda *_:{"chapter":1},save_snapshot=lambda *_:None)
    manager.snapshot_required=False
    def emit(job,chunk=""):job.output+=chunk
    manager._emit=emit
    return manager,chapter,captured,runtime


@pytest.mark.parametrize("policy",[None,"LOCAL_ONLY","REDACT_BEFORE_CLOUD","UNKNOWN","cloud_allowed"])
def test_restricted_or_unknown_source_never_reaches_transport(monkeypatch,tmp_path,policy):
    manager,_,captured,_=rig(monkeypatch,tmp_path,policy)
    job=Job("synthetic","continue","n","n:1","Continue","QUALITY")
    manager._run(job)
    assert job.status=="FAILED" and captured==[]


def test_reviewed_revision_reaches_transport_and_records_real_usage(monkeypatch,tmp_path):
    manager,_,captured,_=rig(monkeypatch,tmp_path,approve=True)
    job=Job("synthetic","continue","n","n:1","Continue","QUALITY")
    manager._run(job)
    assert job.status=="COMPLETED" and len(captured)==1
    assert "SYNTHETIC_CHAPTER_CANARY" in captured[0]
    assert job.usage=={"input_tokens":3,"output_tokens":2,"total_tokens":5}
    assert job.provider_reference_id=="synthetic-reference" and job.execution_mode=="real"


def test_revocation_during_context_assembly_blocks_final_send(monkeypatch,tmp_path):
    manager,chapter,captured,_=rig(monkeypatch,tmp_path,approve=True)
    def context(*_):
        review_source_privacy(chapter,None,"test","LOCAL_ONLY",1,content_digest(chapter))
        return {}
    manager.contexts.for_chapter=context
    job=Job("synthetic","continue","n","n:1","Continue","QUALITY")
    manager._run(job)
    assert job.status=="FAILED" and not captured


def test_changed_or_unreviewed_selection_does_not_use_previous_review(monkeypatch,tmp_path):
    manager,chapter,captured,_=rig(monkeypatch,tmp_path,approve=True)
    job=Job("synthetic","continue","n","n:1","Continue","QUALITY",source="OTHER_PRIVATE_SOURCE")
    manager._run(job)
    assert job.status=="FAILED" and captured==[]
    chapter["content"]+=" changed"
    job=Job("synthetic-2","continue","n","n:1","Continue","QUALITY")
    manager._run(job)
    assert job.status=="FAILED" and captured==[]


def test_partial_stream_cannot_fallback_to_second_route(monkeypatch,tmp_path):
    manager,_,captured,runtime=rig(monkeypatch,tmp_path,approve=True)
    runtime.router=lambda *_:S(routes={"writer":[Route("remote","selected"),Route("other","second")]})
    class Interrupted:
        def stream(self,_):
            captured.append("first")
            yield GenerationEvent("generation.delta",None,delta="partial")
            raise RuntimeError("interrupted")
    runtime.prepare_text_route=lambda *_:Interrupted()
    job=Job("synthetic","continue","n","n:1","Continue","QUALITY")
    manager._run(job)
    assert job.status=="FAILED" and captured==["first"] and job.output=="partial"


def test_creation_record_revocation_is_rechecked_before_dispatch(monkeypatch,tmp_path):
    import app.api as api
    manager,_,captured,_=rig(monkeypatch,tmp_path,approve=True)
    monkeypatch.setattr(api,"creation_workbench_service",S(local_scope=lambda nid:{"mode":"local","novel_id":nid},get_record=lambda *_:{"version":2,"status":"DRAFT","privacy_level":"LOCAL_ONLY"}))
    job=Job("synthetic","continue","n","n:1","Continue","QUALITY",style="copied style")
    job.creation_records=[{"id":"revoked","version":1,"privacy_level":"CLOUD_ALLOWED"}]
    manager._run(job)
    assert job.status=="FAILED" and captured==[]
