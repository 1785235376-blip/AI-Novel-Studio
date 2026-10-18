"""Original route response guard covers current projections, not only history."""
import pytest
from test_r3_mounted_contracts import mounted,prefix,checked
from test_r4_research_library_mounted import research_mounted
from test_r4_research_library import payload

@pytest.mark.parametrize('operation',['source','sources','original'])
def test_local_recreation_after_current_projection_blocks_response(research_mounted,monkeypatch,operation):
    e=research_mounted
    row=checked(e.client.post(e.path+'/sources/import',json=payload()),201)
    original=getattr(e.research,operation)
    def projection(*args):
        value=original(*args)
        title=e.novels.get(e.nid)['title']
        e.novels.delete(e.nid)
        assert e.novels.create({'id':e.nid,'title':title})['id']==e.nid
        e.research.history_identity(e.nid,provision=True)
        return value
    monkeypatch.setattr(e.research,operation,projection)
    suffix='/sources' if operation=='sources' else '/sources/'+row['id']+('/original' if operation=='original' else '')
    response=e.client.get(e.path+suffix)
    assert response.status_code==404
    assert 'Tidal gates' not in response.text
