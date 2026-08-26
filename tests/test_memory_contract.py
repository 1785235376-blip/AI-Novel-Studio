from __future__ import annotations
import hashlib,json,uuid
from datetime import datetime,timezone
import pytest
from app.repository import FileRepository
from app.repositories.file.lore import FileLoreRepository
from app.services import LoreService,MemoryService
from app.storage import atomic_write

def setup(tmp_path):
 b=FileRepository(tmp_path);b.create_novel({"id":"memory-test","title":"Memory"});b.create_chapter("memory-test",{"number":1});atomic_write(b.novels/"memory-test"/"characters"/"characters.json",json.dumps([{"id":"hero","name":"Hero"}]))
 return FileLoreRepository(b)
def prepare(repo):
 lore=LoreService(repo);excerpt="Hero remembers";eid=str(uuid.uuid4());pid=str(uuid.uuid4());stamp=datetime(2026,8,9,tzinfo=timezone.utc)
 ev=lore.create_evidence({"id":eid,"novel_id":"memory-test","source_type":"CHAPTER_VERSION","source_id":"memory-test:1:v1","chapter_id":"memory-test:1","chapter_version":1,"excerpt":excerpt,"locator":{"kind":"DOCUMENT_RANGE"},"content_hash":hashlib.sha256(excerpt.encode()).hexdigest(),"privacy":"CLOUD_ALLOWED","created_at":stamp,"updated_at":stamp})
 prop=lore.create_proposal({"id":pid,"novel_id":"memory-test","proposal_type":"CHARACTER_MEMORY","payload":{"candidate":True},"status":"PENDING","created_at":stamp,"updated_at":stamp},[{"evidence_id":eid,"relevance":"PRIMARY","created_at":stamp}]);return lore,MemoryService(repo),prop
def test_approval_creates_memory_atomically(tmp_path):
 repo=setup(tmp_path);_,memory,prop=prepare(repo);approved,created=memory.approve_character_memory(prop["id"],{"character_id":"hero","memory_type":"EXPERIENCE","content":{"event":"storm"},"valid_from_chapter":1},"tester",memory_id="memory-one",business_id="hero-storm")
 assert approved["status"]=="APPROVED" and created==repo.get_memory("memory-one") and repo.list_character_memories("hero","ACTIVE")==[created]
 with pytest.raises(ValueError):memory.approve_character_memory(prop["id"],approved["approved_payload"],"tester")
def test_failed_memory_creation_keeps_proposal_pending(tmp_path):
 repo=setup(tmp_path);_,memory,prop=prepare(repo)
 with pytest.raises(FileNotFoundError):memory.approve_character_memory(prop["id"],{"character_id":"missing","memory_type":"EXPERIENCE","content":{}},"tester")
 assert repo.get_proposal(prop["id"])["status"]=="PENDING" and repo.list_memories("memory-test")==[]
def test_reject_creates_no_memory(tmp_path):
 repo=setup(tmp_path);lore,_,prop=prepare(repo);lore.reject_proposal(prop["id"],"tester");assert repo.list_memories("memory-test")==[]
def test_supersede_retract_and_snapshot(tmp_path):
 repo=setup(tmp_path);_,memory,prop=prepare(repo);_,first=memory.approve_character_memory(prop["id"],{"character_id":"hero","memory_type":"STATE_CHANGE","content":{"state":"hurt"}},"tester",memory_id="m1",business_id="state-1")
 replacement=memory.supersede("m1",{**first,"id":"m2","business_id":"state-2","content":{"state":"healed"},"status":"ACTIVE","supersedes_id":"m1"});assert repo.get_memory("m1")["status"]=="SUPERSEDED"
 assert memory.retract("m2","corrected")["status"]=="RETRACTED"
 snap1=memory.create_snapshot("memory-test","NOVEL","novel","tester",snapshot_id="s1");snap2=memory.create_snapshot("memory-test","NOVEL","novel","tester",snapshot_id="s2")
 assert snap2["version"]==2 and snap2["supersedes_id"]=="s1" and snap1["content_hash"]==hashlib.sha256(json.dumps(snap1["memory"],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
