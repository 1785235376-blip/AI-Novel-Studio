import copy
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from app.services.creation_workbench_service import CreationWorkbenchService, WorkbenchRecordIn, CommentIn
from app.services.v1_capability_service import V1CapabilityService, CapabilityVersionConflict
from app.knowledge_extraction import extract_knowledge_candidates


@pytest.fixture
def workbench(tmp_path):
    chapter = {"id": "n:1", "novel_id": "n", "version": 1, "content": "Alice said hello. 第一章正文。"}
    novels = SimpleNamespace(get=lambda nid: {"id": nid}, data_set=lambda nid, kind: [{"id": "entity"}])
    chapters = SimpleNamespace(get=lambda cid: copy.deepcopy(chapter))
    store = V1CapabilityService(tmp_path, novels, chapters, None)
    return CreationWorkbenchService(store, chapters, novels), chapter


def test_record_versions_reopen_approve_and_restore(workbench):
    svc, chapter = workbench
    scope = svc.local_scope("n")
    body = WorkbenchRecordIn(kind="STYLE", title="克制", instructions="使用短句", chapter_ids=["n:1"])
    row = svc.save_record("n", scope, "author", body)
    assert row["status"] == "DRAFT"
    with pytest.raises(ValueError):
        svc.generation_inputs("n", scope, row["id"])
    approved = svc.transition_record("n", scope, "author", row["id"], "approve", 1)
    assert svc.generation_inputs("n", scope, row["id"])["style"] == "使用短句"
    with pytest.raises(CapabilityVersionConflict):
        svc.save_record("n", scope, "author", body, row["id"], 1)
    edited = svc.save_record("n", scope, "author", body.model_copy(update={"instructions": "自然对话"}), row["id"], 2)
    assert edited["status"] == "DRAFT"
    restored = svc.transition_record("n", scope, "author", row["id"], "restore", 3, 1)
    assert restored["version"] == 4 and restored["instructions"] == "使用短句"
    restarted = CreationWorkbenchService(svc.store, svc.chapters, svc.novels)
    assert restarted.get_record("n", scope, row["id"]) == restored
    assert len(restored["history"]) == 3
    assert chapter["version"] == 1


def test_plot_requires_real_structure_and_stale_source_review(workbench):
    svc, chapter = workbench
    with pytest.raises(ValidationError):
        WorkbenchRecordIn(kind="PLOT", title="not a plan")
    body = WorkbenchRecordIn(kind="PLOT", title="结局 A", acts=["设局", "对抗", "解决"], conflict="误解", climax="揭示", ending="和解", chapter_ids=["n:1"])
    row = svc.save_record("n", svc.local_scope("n"), "author", body)
    chapter["version"] = 2
    with pytest.raises(ValueError, match="source chapter changed"):
        svc.transition_record("n", svc.local_scope("n"), "author", row["id"], "approve", 1)


def test_workbench_branch_and_project_isolation(workbench):
    svc, _ = workbench
    a = {"mode": "collaboration", "branch_id": "a"}
    b = {"mode": "collaboration", "branch_id": "b"}
    row = svc.save_record("n", a, "server-actor", WorkbenchRecordIn(kind="ABILITY", title="规则", description="不能复活"))
    assert svc.list_records("n", b)["items"] == []
    with pytest.raises(FileNotFoundError):
        svc.get_record("n", b, row["id"])
    with pytest.raises(FileNotFoundError):
        svc.get_record("other", a, row["id"])


def test_comments_keep_version_anchor_history_and_restore(workbench):
    svc, chapter = workbench
    scope = svc.local_scope("n")
    row = svc.create_comment("n", scope, "server-actor", CommentIn(chapter_id="n:1", chapter_version=1, quote="Alice", text="核对人物动机"))
    assert row["messages"][0]["actor_id"] == "server-actor"
    chapter["version"] = 2
    assert svc.list_comments("n", scope)["items"][0]["anchor_state"] == "STALE"
    with pytest.raises(ValueError):
        svc.create_comment("n", scope, "actor", CommentIn(chapter_id="n:1", chapter_version=1, text="stale"))
    row = svc.update_comment("n", scope, "editor", row["id"], "reply", 1, "已核对")
    row = svc.update_comment("n", scope, "editor", row["id"], "resolve", 2)
    with pytest.raises(ValueError):
        svc.update_comment("n", scope, "editor", row["id"], "reply", 3, "closed")
    row = svc.update_comment("n", scope, "author", row["id"], "reopen", 3)
    assert row["status"] == "OPEN" and row["version"] == 4
    assert [r["action"] for r in row["history"]] == ["CREATED", "REPLY", "RESOLVE", "REOPEN"]


def test_corrupted_store_does_not_overwrite(workbench):
    svc, _ = workbench
    path = svc.store._path("creation_records")
    path.parent.mkdir(parents=True)
    path.write_text("{broken")
    with pytest.raises(ValueError):
        svc.save_record("n", svc.local_scope("n"), "actor", WorkbenchRecordIn(kind="STYLE", title="A", instructions="B"))
    assert path.read_text() == "{broken"


def test_chunked_extraction_has_exact_source_and_no_cross_chapter_identity_merge():
    text = "x" * 15990 + "\nAlice said hello. 林默说秘密会解开。"
    chapters = [{"id": f"n:{i}", "number": i, "version": 2, "title": f"Chapter {i}", "content": text} for i in (1, 2)]
    result = extract_knowledge_candidates(chapters)
    alice = [r for r in result["characters"] if r["name"] == "Alice"]
    assert len(alice) == 2 and alice[0]["candidate_id"] != alice[1]["candidate_id"]
    for rows in result.values():
        for row in rows:
            for evidence in row["source_evidence"]:
                assert text[evidence["start"]:evidence["end"]] == evidence["quote"]
                assert evidence["chapter_version"] == 2
            assert row["privacy_level"] == "LOCAL_ONLY"
    assert extract_knowledge_candidates([]) == {k: [] for k in result}


def test_approved_plan_cannot_be_used_after_source_revision_changes(workbench):
    svc, chapter = workbench
    scope=svc.local_scope('n')
    row=svc.save_record('n',scope,'author',WorkbenchRecordIn(kind='STYLE',title='Style',instructions='Short sentences',chapter_ids=['n:1']))
    svc.transition_record('n',scope,'author',row['id'],'approve',1)
    chapter['version']=2
    with pytest.raises(ValueError,match='source chapter changed'):
        svc.generation_inputs('n',scope,row['id'])


def test_import_review_concurrent_edits_preserve_newer_draft(tmp_path):
    from app.services.import_review_service import ImportReviewService
    service=ImportReviewService(tmp_path)
    row=service.ensure_pending('n',{'characters':[{'name':'Alice'}]})
    updated=service.update_candidates(row['id'],{'characters':[{'name':'Alice edited'}]},expected_version=1)
    assert updated['version']==2
    with pytest.raises(CapabilityVersionConflict):
        service.update_candidates(row['id'],{'characters':[{'name':'stale overwrite'}]},expected_version=1)
    assert service.get(row['id'])['candidates']['characters'][0]['name']=='Alice edited'


@pytest.mark.parametrize("content", ["{broken", "[]", '{"review": 1}'])
def test_import_review_corruption_is_not_silently_overwritten(tmp_path, content):
    from app.services.import_review_service import ImportReviewService
    service=ImportReviewService(tmp_path)
    service.path.write_text(content)
    with pytest.raises(ValueError):
        service.ensure_pending('n',{'characters':[{'name':'new'}]})
    assert service.path.read_text()==content
