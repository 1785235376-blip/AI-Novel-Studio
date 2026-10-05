"""Persistent screenplay CAS, immutable history and concurrent-writer checks."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier

import pytest

from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.chapter_repository import VersionConflict
from app.services.screenplay_service import ScreenplayService


def make_service(tmp_path):
    bundle=create_repository_bundle(Settings(storage_backend="file"),data_root=tmp_path)
    nid=bundle.novels.create({"title":"Synthetic screenplay versioning"})["id"]
    bundle.chapters.create(nid,{"title":"Chapter","content":"Synthetic prose"})
    return bundle,nid,ScreenplayService(bundle.novels,bundle.chapters)


def test_service_edit_precondition_history_restart_and_historical_fork(tmp_path):
    bundle,nid,service=make_service(tmp_path)
    original=service.create(nid,"Screenplay")
    assert original["edit_version"]==1
    scene=original["scenes"][0]
    payload={**scene,"action":"Version two action","expected_version":1}
    changed=service.update_scene(nid,original["id"],scene["id"],payload)
    assert changed["edit_version"]==2
    with pytest.raises(VersionConflict) as conflict:
        service.update_scene(nid,original["id"],scene["id"],{**payload,"action":"stale body"})
    assert conflict.value.expected_version==1 and conflict.value.actual_version==2
    approved=service.approve(nid,original["id"],2)
    assert approved["edit_version"]==3
    # Reopen a new repository/service instance using only persisted data.
    reopened=create_repository_bundle(Settings(storage_backend="file"),data_root=tmp_path)
    restored=ScreenplayService(reopened.novels,reopened.chapters)
    history=restored.history(nid,original["id"])
    assert [row["edit_version"] for row in history["items"]]==[1,2,3]
    assert all("version_history" not in row for row in history["items"])
    assert history["items"][0]["scenes"][0]["action"]==scene["action"]
    assert history["items"][1]["scenes"][0]["action"]=="Version two action"
    fork=restored.revise(nid,original["id"],3,1)
    assert fork["edit_version"]==1 and fork["status"]=="DRAFT"
    assert fork["derived_from"]["edit_version"]==1
    assert fork["scenes"][0]["action"]==scene["action"]
    assert restored.history(nid,original["id"])==history


def test_two_repository_instances_allow_only_one_same_version_writer(tmp_path):
    bundle,nid,service=make_service(tmp_path)
    original=service.create(nid,"Synthetic")
    other=create_repository_bundle(Settings(storage_backend="file"),data_root=tmp_path)
    barrier=Barrier(2)
    def update(repo,title):
        barrier.wait()
        try:return repo.save_screenplay(nid,{**original,"title":title},expected_version=1)
        except VersionConflict:return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(update,bundle.novels,"Writer A");b=pool.submit(update,other.novels,"Writer B")
        results=[a.result(),b.result()]
    assert sum(row=="conflict" for row in results)==1
    saved=bundle.novels.list_screenplays(nid)[0]
    assert saved["edit_version"]==2
    assert len(saved["version_history"])==1
    assert saved["version_history"][0]["title"]=="Synthetic"


def test_cross_process_stale_write_cannot_overwrite_saved_screenplay(tmp_path):
    bundle,nid,service=make_service(tmp_path)
    original=service.create(nid,"Synthetic")
    bundle.novels.save_screenplay(nid,{**original,"title":"Newest"},expected_version=1)
    program='''import json,sys
from pathlib import Path
from app.repository import FileRepository
from app.repositories.file.novel import FileNovelRepository
from app.repositories.chapter_repository import VersionConflict
repo=FileNovelRepository(FileRepository(Path(sys.argv[1])))
try: repo.save_screenplay(sys.argv[2],json.loads(sys.argv[3]),expected_version=1)
except VersionConflict: print("conflict")
else: raise AssertionError("stale write was accepted")
'''
    result=subprocess.run([sys.executable,"-c",program,str(tmp_path),nid,json.dumps(original)],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True,check=True)
    assert result.stdout.strip()=="conflict"
    assert bundle.novels.list_screenplays(nid)[0]["title"]=="Newest"


def test_history_is_server_owned_and_branch_cannot_change(tmp_path):
    bundle,nid,service=make_service(tmp_path)
    original=service.create(nid,"Synthetic",branch_id="branch-a")
    with pytest.raises(ValueError,match="ownership"):
        bundle.novels.save_screenplay(nid,{**original,"branch_id":"branch-b"},expected_version=1)
    saved=bundle.novels.save_screenplay(nid,{**original,"version_history":[{"fake":True}],"edit_version":900},expected_version=1)
    assert saved["edit_version"]==2
    assert saved["version_history"]==[{key:value for key,value in original.items() if key!="version_history"}]


def test_api_reports_409_with_original_editor_version_and_preserves_history(tmp_path,monkeypatch):
    import app.api as api
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    _,nid,service=make_service(tmp_path)
    monkeypatch.setattr(api,"screenplay_service",service)
    monkeypatch.setattr(api,"settings",SimpleNamespace(enable_collaboration_runtime=False))
    app=FastAPI();app.include_router(api.router,prefix="/api");client=TestClient(app)
    created=service.create(nid,"Synthetic")
    scene=created["scenes"][0]
    path=f"/api/novels/{nid}/screenplays/{created['id']}"
    body={**scene,"action":"Saved action","expected_version":1}
    assert client.put(path+f"/scenes/{scene['id']}",json=body).json()["edit_version"]==2
    stale=client.put(path+f"/scenes/{scene['id']}",json={**body,"action":"Must not overwrite"})
    assert stale.status_code==409
    assert stale.json()["detail"]["conflict"]["expected_version"]==1
    assert stale.json()["detail"]["conflict"]["actual_version"]==2
    history=client.get(path+"/revisions").json()
    assert history["current_version"]==2
    assert history["items"][-1]["scenes"][0]["action"]=="Saved action"
