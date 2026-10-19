"""Real PostgreSQL screenplay transactions; explicit disposable DB opt-in."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
import uuid

import pytest

from app.repositories.postgres.novel import PostgresNovelRepository
from app.repositories.postgres.session import Database
from app.repositories.chapter_repository import VersionConflict

URL=os.getenv("TEST_POSTGRES_DATABASE_URL","")
pytestmark=[pytest.mark.postgres_backend_only,pytest.mark.skipif(not URL,reason="NOT_RUN: disposable PostgreSQL not configured")]


@pytest.fixture
def repository():
    repo=PostgresNovelRepository(Database(URL))
    nid=repo.create({"id":"screenplay-cas-"+uuid.uuid4().hex,"title":"Synthetic screenplay CAS"})["id"]
    yield repo,nid
    repo.delete(nid)  # Only the synthetic project created by this fixture.


def test_postgres_two_writers_keep_one_history_and_reject_stale_version(repository):
    repo,nid=repository
    original=repo.save_screenplay(nid,{"id":"script","title":"Original","status":"DRAFT","branch_id":"branch-a","scenes":[]},expected_version=0)
    barrier=Barrier(2)
    def update(title):
        barrier.wait()
        try:return repo.save_screenplay(nid,{**original,"title":title},expected_version=1)
        except VersionConflict:return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(update,"Writer A");b=pool.submit(update,"Writer B")
        results=[a.result(timeout=20),b.result(timeout=20)]
    assert results.count("conflict")==1
    saved=repo.list_screenplays(nid)[0]
    assert saved["edit_version"]==2 and len(saved["version_history"])==1
    assert saved["version_history"][0]["title"]=="Original"
    assert "version_history" not in saved["version_history"][0]


def test_postgres_other_metadata_writer_cannot_erase_screenplay_history(repository):
    repo,nid=repository
    original=repo.save_screenplay(nid,{"id":"script","title":"Original","scenes":[]},expected_version=0)
    barrier=Barrier(2)
    def screenplay():
        barrier.wait()
        return repo.save_screenplay(nid,{**original,"title":"Changed"},expected_version=1)
    def goal():
        barrier.wait()
        return repo.update(nid,{"writing_goal":{"target_words":3000}})
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(screenplay);b=pool.submit(goal)
        a.result(timeout=20);b.result(timeout=20)
    reopened=PostgresNovelRepository(Database(URL))
    assert reopened.get(nid)["writing_goal"]=={"target_words":3000}
    saved=reopened.list_screenplays(nid)[0]
    assert saved["title"]=="Changed" and saved["edit_version"]==2
    assert saved["version_history"][0]["title"]=="Original"


def test_postgres_new_process_reads_history_and_cannot_restore_old_version(repository):
    repo,nid=repository
    original=repo.save_screenplay(nid,{"id":"script","title":"Original","scenes":[]},expected_version=0)
    repo.save_screenplay(nid,{**original,"title":"Changed"},expected_version=1)
    program='''import os,sys
from app.repositories.postgres.novel import PostgresNovelRepository
from app.repositories.postgres.session import Database
from app.repositories.chapter_repository import VersionConflict
repo=PostgresNovelRepository(Database(os.environ["TEST_POSTGRES_DATABASE_URL"]))
row=repo.list_screenplays(sys.argv[1])[0]
assert row["edit_version"]==2 and row["version_history"][0]["title"]=="Original"
try: repo.save_screenplay(sys.argv[1],{**row,"title":"stale"},expected_version=1)
except VersionConflict: print("history-reopened; stale-write-rejected")
else: raise AssertionError("stale write accepted")
'''
    result=subprocess.run([sys.executable,"-c",program,nid],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True,check=True,timeout=30)
    assert result.stdout.strip()=="history-reopened; stale-write-rejected"
    assert repo.list_screenplays(nid)[0]["title"]=="Changed"
