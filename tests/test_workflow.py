import shutil
from pathlib import Path
from app.workflow import NovelWorkflow
from sample_novel_fixture import install_sample_novel

def test_local_workflow_persists_and_pending(tmp_path):
    target=install_sample_novel(tmp_path)
    result=NovelWorkflow(tmp_path).run("sample_novel",3,"旧港相遇","LOCAL_ONLY",draft_override="林海在雨中见到沈船长，但没有得到答案。")
    assert result["status"]=="COMPLETED"
    assert (target/"chapters"/"chapter-0003.md").exists()
    assert list((target/"pending_canon").glob("*.json"))
