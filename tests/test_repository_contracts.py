from __future__ import annotations
import shutil,uuid
from pathlib import Path
import pytest
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.chapter_repository import VersionConflict
from app.services import NovelService,ChapterService,CanonService,ContextService,GenerationService
from sample_novel_fixture import install_sample_novel

@pytest.fixture
def bundle(tmp_path):return create_repository_bundle(Settings(storage_backend="file",novel_data=tmp_path),tmp_path)

def test_novel_contract(bundle):
    service=NovelService(bundle.novels,bundle.chapters);created=service.create({"title":"Contract Novel","genre":"Test"});nid=created["id"]
    assert service.get(nid)["title"]=="Contract Novel";assert any(x["id"]==nid for x in service.list());assert service.update(nid,{"title":"Updated"})["title"]=="Updated";service.delete(nid)
    with pytest.raises(FileNotFoundError):service.get(nid)

def test_chapter_contract(bundle):
    novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);nid=novels.create({"title":"Chapters"})["id"];created=chapters.create(nid,{"title":"One","content":"Body"});current=chapters.get(created["id"])
    saved=chapters.save(created["id"],{"content":"Changed","version":current["version"]});assert saved["version"]==2 and chapters.history(created["id"])
    with pytest.raises(VersionConflict):chapters.save(created["id"],{"content":"Stale","version":current["version"]})
    restored=chapters.restore(created["id"],1,saved["version"]);assert restored["version"]==3;duplicate=chapters.duplicate(created["id"]);assert duplicate["id"]!=created["id"] and "Body" in duplicate["content"]

def test_canon_contract(bundle):
    novels=NovelService(bundle.novels,bundle.chapters);canon=CanonService(bundle.canon);nid=novels.create({"title":"Canon"})["id"];pid=str(uuid.uuid4());item={"id":pid,"novel_id":nid,"status":"PENDING","proposals":[{"fact":"A"}]};canon.save_pending(item);assert canon.list_pending(nid)[0]["id"]==pid;canon.approve(pid,[{"fact":"Edited"}]);assert canon.list(nid)[0]["fact"]=="Edited"
    pid2=str(uuid.uuid4());canon.save_pending({"id":pid2,"novel_id":nid,"status":"PENDING","proposals":[]});assert canon.reject(pid2)["status"]=="REJECTED"

def test_generation_contract(bundle):
    jobs=GenerationService(bundle.generations);item={"id":"job-1","status":"QUEUED"};jobs.save(item);assert jobs.get("job-1")["status"]=="QUEUED";item["status"]="COMPLETED";jobs.save(item);assert jobs.load_all()[0]["status"]=="COMPLETED"

def test_context_service_matches_legacy_shape(tmp_path):
    install_sample_novel(tmp_path);bundle=create_repository_bundle(Settings(storage_backend="file",novel_data=tmp_path),tmp_path);context=ContextService(bundle.novels,bundle.chapters).build("sample_novel",3,"林海遇见沈船长",True)
    assert context["novel_id"]=="sample_novel" and context["chapter"]==3 and "privacy_omissions" in context and "forbidden_secrets" in context

def test_factory_rejects_unimplemented_and_unknown():
    with pytest.raises(ValueError):create_repository_bundle(Settings(storage_backend="postgres",database_url=""))
    with pytest.raises(ValueError):create_repository_bundle(Settings(storage_backend="mystery"))
