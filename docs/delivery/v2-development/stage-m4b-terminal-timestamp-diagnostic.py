"""Isolated regression diagnosis over unchanged original fixture owners."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(Path.cwd()/'tests'))
import pytest
from test_v2_graph_text_assets import dispatch_asset
from test_v2_ai_execution_runtime import spy_transport,current

def case(model_rig,monkeypatch):
    e=model_rig;spy_transport(e,monkeypatch)
    sent,job=dispatch_asset(e)
    first=current(e,sent)
    assert first['asset_output']['state']=='DRAFT'
    old=job.updated_at
    e.manager._emit(job)
    assert job.updated_at!=old
    second=current(e,sent)
    assert second['asset_output']==first['asset_output'],'original terminal notification stranded an already archived result'
    assert len(e.calls)==1
class Plugin:
    def pytest_collection_modifyitems(self,items):
        for item in items:item.obj=case
raise SystemExit(pytest.main(['-q','tests/test_v2_graph_text_assets.py::test_existing_read_archives_one_draft_then_original_review_updates_version[file]','--tb=short','--basetemp=.runtime/m4b/timestamp-red1'],plugins=[Plugin()]))
