"""Mixed certification requires successful original readers even if empty."""
import pytest
from fastapi import HTTPException
from test_taskcenter_mixed_external import rig,export_rig,mixed_rig,get
from test_taskcenter_mixed_external_cases import token,import_write


@pytest.mark.parametrize('source',['import','export'])
def test_empty_selected_source_denial_cannot_certify_mixed_continuation(mixed_rig,monkeypatch,source):
    e=mixed_rig
    if source=='import':import_write(e,lambda rows:rows.clear());owner=e.importer;name='jobs'
    else:e.source._write({});owner=e.source;name='list'
    t=token(e)
    def denied(*a,**kw):raise HTTPException(403,{'code':'SYNTHETIC_ORIGINAL_EMPTY_SOURCE_DENIED'})
    monkeypatch.setattr(owner,name,denied)
    initial=get(e);assert initial.status_code==501,initial.text
    continued=get(e,{'cursor':t});assert continued.status_code==409,continued.text
    assert 'items' not in initial.json() and 'items' not in continued.json()
