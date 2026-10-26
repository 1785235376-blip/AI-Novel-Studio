"""Deny only the actual aggregate read, not any separate access probe."""
import inspect
import pytest
from fastapi import HTTPException
from test_taskcenter_mixed_external import rig,export_rig,mixed_rig,get
from test_taskcenter_mixed_external_cases import token,import_write


@pytest.mark.parametrize('source',['import','export'])
@pytest.mark.parametrize('status',[403,404])
@pytest.mark.parametrize('empty',[True,False])
def test_aggregate_only_empty_reader_denial_cannot_be_masked_by_other_successful_reads(mixed_rig,monkeypatch,source,status,empty):
    e=mixed_rig
    if source=='import':
        if empty:import_write(e,lambda rows:rows.clear())
        owner=e.importer;name='jobs'
    else:
        if empty:e.source._write({})
        owner=e.source;name='list'
    t=token(e);original=getattr(owner,name);denials=[]
    def conditional(*a,**kw):
        frames=inspect.stack(context=0)
        try:
            actual=any(f.function=='tasks' and f.frame.f_locals.get('self') is e.api.workspace_tools_service for f in frames)
        finally:del frames
        if actual:
            denials.append(True)
            raise HTTPException(status,{'code':'SYNTHETIC_ACTUAL_AGGREGATE_READER_DENIED'})
        return original(*a,**kw)
    monkeypatch.setattr(owner,name,conditional)
    initial=get(e);assert denials and initial.status_code==501,initial.text
    continued=get(e,{'cursor':t});assert len(denials)==2 and continued.status_code==409,continued.text
    assert 'items' not in initial.json() and 'items' not in continued.json()
