from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.document import markdown_to_document
from app.experimental.adaptation_projection import adaptation_reader,mount_adaptation_projections
from app.experimental.flags import require_flag
from app.experimental.inbox import UnifiedReviewInbox
from app.experimental.ux import ReadContext
from test_surface_adaptation_lifecycle import env,materialized


def fixture(e):
    host=SimpleNamespace(collaboration_scope_service=SimpleNamespace(repository=SimpleNamespace(project_workspace=lambda _:None)),_adaptation_context=lambda *args:(None,None))
    ctx=ReadContext(e.nid,{'mode':'local','novel_id':e.nid},'local-author',None,None)
    return host,ctx


def test_original_task_projection_binds_both_ids_and_stale_target(env,monkeypatch):
    e=env;p=materialized(e);tid=p['execution_manifest'][0]['id'];e.service.generate_draft(e.nid,p['id'],tid)
    other=materialized(e);other_tid=other['execution_manifest'][0]['id']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','adaptation_lifecycle_v1');host,ctx=fixture(e);read=adaptation_reader(e.service,host,require_flag)
    rows=read(ctx);row=next(r for r in rows if r['id']==tid)
    assert row['proposal_id']==p['id'] and row['source_navigation']['parent_id']==p['id'] and row['source_navigation']['id']==tid
    assert row['allowed_actions']==[] and row['source_versions']['source_version']==e.source['version'] and row['stale'] is False
    assert all('draft' not in r and 'document' not in r for r in rows)
    target=e.bundle.chapters.get(row['source_versions']['target_chapter_id']);e.bundle.chapters.save(target['id'],markdown_to_document('New target'),target['version'])
    changed=read(ctx);assert next(r for r in changed if r['id']==tid)['stale'] is True
    assert next(r for r in changed if r['id']==other_tid)['proposal_id']==other['id']
    assert [r for r in changed if r['proposal_id']=='missing-proposal']==[]
    workspace=SimpleNamespace(task_readers=());inbox=UnifiedReviewInbox();mount_adaptation_projections(workspace,inbox,e.service,host,require_flag)
    assert workspace.task_readers[0].name=='adaptation' and workspace.task_readers[0].cancel is None
    from app.experimental.ux import projected_task
    normalized=projected_task(workspace.task_readers[0],row)
    assert normalized['source']['parent_id']==p['id'] and normalized['source']['version']==row['proposal_revision']
    assert normalized['source']['source_version']==e.source['version'] and normalized['source']['target_version']==row['source_versions']['target_version']
    assert inbox.list(ctx,domain='adaptation')['items'][0]['allowed_actions']==[]
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    with pytest.raises(HTTPException) as error:read(ctx)
    assert error.value.status_code==404


def test_projection_checks_authority_again_and_rejects_forged_scope(env,monkeypatch):
    e=env;materialized(e);monkeypatch.setenv('EXPERIMENTAL_FEATURES','adaptation_lifecycle_v1');host,ctx=fixture(e)
    read=adaptation_reader(e.service,host,require_flag)
    forged=ReadContext(e.nid,{'mode':'local','novel_id':'other'},'local-author',None,None)
    with pytest.raises(HTTPException) as error:read(forged)
    assert error.value.status_code==403
    calls=[]
    def revoke(*args):
        calls.append(args)
        if len(calls)>1:raise HTTPException(403,'revoked')
        return None,None
    host._adaptation_context=revoke
    with pytest.raises(HTTPException) as error:read(ctx)
    assert error.value.status_code==403 and len(calls)==2
