"""Original A02/A11 job identity resolves to its own review surface, never Accept."""
import json
import pytest
from app.jobs import mark_generation_origin
from test_r3_mounted_contracts import mounted,prefix
from test_r4_author_task_projection import author_tasks,add,read


@pytest.mark.parametrize('origin,feature,authority',[('style_analysis_model','style_dna_v2','style_model_job'),('revision_comparison_model','revision_intelligence_v2','revision_model_job')])
def test_original_model_task_routes_exact_job_and_chapter_without_private_content(author_tasks,monkeypatch,origin,feature,authority):
    e=author_tasks;job=add(e,'original-'+origin);mark_generation_origin(job,origin)
    monkeypatch.setattr(e.api.jobs,'create',lambda *a,**kw:pytest.fail('Task projection must not create a job'))
    monkeypatch.setattr(e.api.jobs,'_persist',lambda *a,**kw:pytest.fail('Task projection must not persist a job'))
    result,rows=read(e)
    assert len(rows)==1
    assert rows[0]['source']=={'kind':'feature','id':job.id,'feature':feature,'task_authority':authority,'chapter_id':job.chapter_id,'version':job.base_chapter_version}
    assert rows[0]['authority']=='author_generation' and len(e.api.jobs.jobs)==1
    assert 'PRIVATE' not in json.dumps(result)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2')
    assert read(e)[1]==[]
