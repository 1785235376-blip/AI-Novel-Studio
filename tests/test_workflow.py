import shutil
from pathlib import Path
from app.workflow import NovelWorkflow

def test_local_workflow_persists_and_pending(tmp_path):
    source=Path(__file__).parents[1]/"novel_data"/"novels"/"sample_novel"
    target=tmp_path/"novels"/"sample_novel"; shutil.copytree(source,target)
    result=NovelWorkflow(tmp_path).run("sample_novel",3,"旧港相遇","LOCAL_ONLY",draft_override="林海在雨中见到沈船长，但没有得到答案。")
    assert result["status"]=="COMPLETED"
    assert (target/"chapters"/"chapter-0003.md").exists()
    assert list((target/"pending_canon").glob("*.json"))

