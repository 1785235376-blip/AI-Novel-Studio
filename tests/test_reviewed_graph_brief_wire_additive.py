"""Original local Graph review output used by the read-only brief importer."""
import json,os
from pathlib import Path
import pytest
from test_v2_independent_workspace import rig
from test_v2_creative_graph_persistence import service,create,run,definition
from test_v2_creative_graph_execution import action,approve

@pytest.mark.parametrize('rig',[pytest.param('file',marks=pytest.mark.file_backend_only)],indirect=True)
def test_original_reviewed_text_reopens_and_tampering_is_not_accepted(rig):
    e=rig;body=definition();body['schema_version']=3
    text={'purpose':'保留作者约束','writing_goals':'完成日式场景短片','constraints':'不自动执行模型','checklist':'核对来源与许可'}
    body['nodes'][0]['parameters']['text']=json.dumps(text,ensure_ascii=False)
    graph=create(e,body);waiting=action(e,run(e,graph),'execute');assert waiting['status']=='WAITING_APPROVAL'
    assert 'reviewed_draft' not in (waiting['node_states']['review']['output'] or {})
    done=approve(e,waiting);assert done['status']=='SUCCEEDED' and done['reviewed']
    original=service(e).get_run(e.nid,e.scope,e.actor,done['id']);assert original==done
    assert json.loads(done['node_states']['review']['output']['reviewed_draft']['text'])==text
    Path(os.environ['NOVEL_DATA_PATH']).parent.joinpath('reviewed-brief-wire.json').write_text(json.dumps({'graph':graph,'run':done,'text':text},ensure_ascii=False,indent=2)+'\n')
    with e.raw_store.transaction(e.nid,e.scope) as data:
        row=data['collections'][service(e).RUNS][done['id']]
        row['typed_outputs']['review']['reviewed_draft']['text']='forged'
    with pytest.raises(ValueError):service(e).get_run(e.nid,e.scope,e.actor,done['id'])
    assert e.chapters.list(e.nid)==[]
