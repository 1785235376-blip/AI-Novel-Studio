import json,shutil
from pathlib import Path
import pytest
from app.document import markdown_to_document,document_to_markdown
from app.repository import FileRepository
from app.repositories.chapter_repository import ChapterRepository,VersionConflict
from app.repositories.generation_repository import GenerationRepository
from sample_novel_fixture import install_sample_novel

def test_document_round_trip():
    source="# Heading\n\nParagraph\n\n```python\nprint(1)\n```";assert document_to_markdown(markdown_to_document(source))==source+"\n\n"
def test_versions_conflict_and_restore(tmp_path):
    install_sample_novel(tmp_path);repo=ChapterRepository(FileRepository(tmp_path));current=repo.get("sample_novel:1");saved=repo.save("sample_novel:1",current["document"],current["version"]);assert saved["version"]==2
    with pytest.raises(VersionConflict):repo.save("sample_novel:1",current["document"],current["version"])
    assert repo.restore("sample_novel:1",1,2)["version"]==3
def test_job_repository_survives_new_instance(tmp_path):
    first=GenerationRepository(tmp_path);first.save({"id":"job","status":"COMPLETED","result":"draft"});assert GenerationRepository(tmp_path).get("job")["result"]=="draft"
def test_runtime_log_does_not_accept_secret_fields():
    from app.structured_log import RuntimeLogger
    assert "api_key" not in RuntimeLogger.allowed and "prompt" not in RuntimeLogger.allowed and "secret" not in RuntimeLogger.allowed
