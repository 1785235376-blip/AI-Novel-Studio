from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from app.services.import_apply_service import ImportApplyInterrupted, ImportApplyService


class Novels:
    def __init__(self):self.rows={};self.calls=[];self.fail_kind=None;self.fail_after=False
    def data_set(self,nid,kind):return copy.deepcopy(list(self.rows.get(kind,{}).values()))
    def review_import_knowledge(self,nid,decision,candidates):
        kind,items=next(iter(candidates.items()));self.calls.append(kind)
        if kind==self.fail_kind and not self.fail_after:raise OSError("synthetic failure")
        dataset={"timeline_events":"timeline"}.get(kind,kind)
        row={**items[0],"privacy_level":"LOCAL_ONLY"};self.rows.setdefault(dataset,{})[row["id"]]=row
        if kind==self.fail_kind and self.fail_after:raise OSError("synthetic failure after mutation")
        return {"applied":{kind:[row]}}


def candidates():return {"characters":[{"name":"Alice"}],"locations":[{"name":"Harbor"}],"timeline_events":[{"title":"Arrival"}]}


def test_partial_apply_resumes_only_unfinished_steps_after_reopen(tmp_path):
    novels=Novels();novels.fail_kind="locations"
    service=ImportApplyService(novels,tmp_path)
    with pytest.raises(ImportApplyInterrupted) as caught:service.apply("review","n",candidates(),actor_id="author")
    assert caught.value.detail["status"]=="PARTIAL" and caught.value.detail["completed"]==1
    original_id=next(iter(novels.rows["characters"]))
    novels.fail_kind=None
    reopened=ImportApplyService(novels,tmp_path)
    result=reopened.apply("review","n",candidates(),actor_id="author")
    assert result["apply_status"]=="COMPLETED" and result["checkpoint_count"]==3
    assert novels.calls.count("characters")==1
    assert next(iter(novels.rows["characters"]))==original_id
    again=reopened.apply("review","n",candidates(),actor_id="author")
    assert result==again and len(novels.calls)==4


def test_uncertain_written_candidate_blocks_without_overwrite(tmp_path):
    novels=Novels();novels.fail_kind="locations";novels.fail_after=True
    service=ImportApplyService(novels,tmp_path)
    with pytest.raises(ImportApplyInterrupted):service.apply("review","n",candidates(),actor_id="author")
    before=copy.deepcopy(novels.rows);count=len(novels.calls);novels.fail_kind=None
    with pytest.raises(ImportApplyInterrupted) as caught:service.apply("review","n",candidates(),actor_id="author")
    assert caught.value.detail["code"]=="IMPORT_APPLY_AMBIGUOUS"
    assert novels.rows==before and len(novels.calls)==count


def test_later_edit_and_changed_review_cannot_be_overwritten_on_retry(tmp_path):
    novels=Novels();service=ImportApplyService(novels,tmp_path);service.apply("review","n",candidates(),actor_id="author")
    row=next(iter(novels.rows["characters"].values()));row["name"]="Author's newer edit"
    with pytest.raises(ImportApplyInterrupted) as caught:service.apply("review","n",candidates(),actor_id="author")
    assert caught.value.detail["code"]=="IMPORT_APPLIED_RECORD_CHANGED"
    changed=candidates();changed["characters"][0]["name"]="replacement"
    with pytest.raises(ValueError,match="selection changed"):service.apply("review","n",changed,actor_id="author")
    assert row["name"]=="Author's newer edit"


def test_validation_completes_before_any_entity_mutation(tmp_path):
    novels=Novels();service=ImportApplyService(novels,tmp_path)
    with pytest.raises(ValueError):service.apply("review","n",{"characters":[{"name":"Alice"},{}]},actor_id="author")
    assert novels.calls==[]
    with pytest.raises(ValueError,match="duplicate"):service.apply("review","n",{"characters":[{"id":"same","name":"A"},{"id":"same","name":"B"}]},actor_id="author")
    assert novels.calls==[]


def test_file_repository_integration_is_durable_and_does_not_duplicate(tmp_path):
    from app.repository import FileRepository
    from app.repositories.file.novel import FileNovelRepository
    from app.services.novel_service import NovelService
    repo=FileNovelRepository(FileRepository(tmp_path/"runtime"));repo.create({"id":"n","title":"Test"})
    novels=NovelService(repo,SimpleNamespace())
    svc=ImportApplyService(novels,tmp_path/"runtime")
    first=svc.apply("review","n",candidates(),actor_id="author")
    again=ImportApplyService(novels,tmp_path/"runtime").apply("review","n",candidates(),actor_id="author")
    assert first==again
    assert len(repo.get_data_set("n","characters"))==1
    assert len(repo.get_data_set("n","timeline"))==1


def test_existing_target_is_a_reviewable_conflict_not_an_overwrite(tmp_path):
    novels=Novels();novels.rows={"characters":{"existing":{"id":"existing","name":"Author's original"}}}
    service=ImportApplyService(novels,tmp_path)
    with pytest.raises(ImportApplyInterrupted) as caught:
        service.apply("review","n",{"characters":[{"id":"existing","name":"Replacement"}]},actor_id="author")
    assert caught.value.detail["code"]=="IMPORT_TARGET_EXISTS"
    assert caught.value.detail["status"]=="REVIEW_REQUIRED"
    assert novels.rows["characters"]["existing"]["name"]=="Author's original"
    assert novels.calls==[]
