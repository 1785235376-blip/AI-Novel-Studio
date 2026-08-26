from __future__ import annotations
import os,uuid
import pytest
from sqlalchemy import text
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.session import Database
from app.services import CanonService,ChapterService,GenerationService,NovelService

URL=os.getenv("TEST_POSTGRES_DATABASE_URL","")
pytestmark=[pytest.mark.postgres_backend_only,pytest.mark.skipif(not URL or not Database(URL).health_check(),reason="NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is unavailable")]

@pytest.fixture
def bundle():
    value=create_repository_bundle(Settings(storage_backend="postgres",database_url=URL));yield value
    with value.novels.database.session() as session:session.execute(text("TRUNCATE generation_jobs,pending_canon,canon_entries,chapter_summaries,chapter_versions,chapters,story_states,novels CASCADE"))

def test_postgres_contract_flow(bundle):
    novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);canon=CanonService(bundle.canon);jobs=GenerationService(bundle.generations)
    nid=novels.create({"title":"Postgres Contract","genre":"Test"})["id"];assert novels.get(nid)["id"]==nid
    created=chapters.create(nid,{"title":"One","content":"Body"});saved=chapters.save(created["id"],{"content":"Changed","version":1});assert saved["version"]==2 and chapters.history(created["id"])
    assert chapters.restore(created["id"],1,2)["version"]==3;assert chapters.duplicate(created["id"])["id"]!=created["id"]
    pid=str(uuid.uuid4());canon.save_pending({"id":pid,"novel_id":nid,"chapter":1,"status":"PENDING","proposals":[{"fact":"A"}]});canon.approve(pid,[{"fact":"Edited"}]);assert canon.list(nid)[0]["fact"]=="Edited"
    jobs.save({"id":"job-contract","novel_id":nid,"chapter_id":created["id"],"status":"QUEUED"});assert jobs.get("job-contract")["status"]=="QUEUED"
