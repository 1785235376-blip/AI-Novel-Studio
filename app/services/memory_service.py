from __future__ import annotations
import hashlib,json,uuid
from datetime import datetime,timezone
from app.lore.schemas import CharacterMemory,MemorySnapshot
from app.repositories.lore_interfaces import LoreRepositoryProtocol

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
class MemoryService:
 def __init__(self,repository:LoreRepositoryProtocol):self.repository=repository
 def approve_character_memory(self,proposal_id,approved_payload,reviewer,memory_id=None,business_id=None):
  proposal=self.repository.get_proposal(proposal_id)
  if proposal["status"]!="PENDING":raise ValueError("proposal must be PENDING")
  if proposal["proposal_type"]!="CHARACTER_MEMORY":raise ValueError("proposal must be CHARACTER_MEMORY")
  if not reviewer.strip():raise ValueError("reviewer is required")
  relations=self.repository.list_proposal_evidence(proposal_id)
  if not relations:raise ValueError("proposal requires evidence")
  evidence=[self.repository.get_evidence(x["evidence_id"]) for x in relations]
  if any(x["status"]!="ACTIVE" or x["novel_id"]!=proposal["novel_id"] for x in evidence):raise ValueError("all proposal evidence must be ACTIVE and in the same novel")
  memory=CharacterMemory(id=memory_id or str(uuid.uuid4()),novel_id=proposal["novel_id"],character_id=approved_payload["character_id"],business_id=business_id or f"memory-{proposal_id}",memory_type=approved_payload["memory_type"],content=approved_payload["content"],status="ACTIVE",valid_from_chapter=approved_payload.get("valid_from_chapter"),valid_to_chapter=approved_payload.get("valid_to_chapter"),proposal_id=proposal_id)
  return self.repository.approve_proposal_with_memory(proposal_id,approved_payload,reviewer,memory.model_dump(mode="json"))
 def supersede(self,memory_id,replacement):return self.repository.supersede_memory(memory_id,replacement)
 def retract(self,memory_id,reason):
  if not reason.strip():raise ValueError("retraction reason is required")
  return self.repository.retract_memory(memory_id,reason.strip())
 def create_snapshot(self,novel_id,scope,scope_key,created_by,range_start=None,range_end=None,snapshot_id=None):
  memories=self.repository.list_memories(novel_id,"ACTIVE");latest=self.repository.get_latest_snapshot(novel_id,scope,scope_key);version=(latest["version"]+1) if latest else 1
  payload={"memories":memories};digest=hashlib.sha256(canonical(payload).encode()).hexdigest();watermark={"memory_ids":[x["id"] for x in memories],"memory_updated_at":[x["updated_at"] for x in memories]}
  model=MemorySnapshot(id=snapshot_id or str(uuid.uuid4()),novel_id=novel_id,scope=scope,scope_key=scope_key,range_start=range_start,range_end=range_end,memory=payload,version=version,source_watermark=watermark,content_hash=digest,supersedes_id=latest["id"] if latest else None,created_by=created_by,created_at=datetime.now(timezone.utc));return self.repository.create_snapshot(model.model_dump(mode="json"))
