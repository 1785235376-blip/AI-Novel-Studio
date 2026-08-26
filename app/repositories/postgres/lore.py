from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import inspect,select
from sqlalchemy.exc import IntegrityError
from app.lore.schemas import Evidence,LoreProposal,ProposalEvidenceRelation,CharacterMemory,MemorySnapshot
from app.lore.validators import require_evidence_transition,require_proposal_transition
from app.models.lore import EvidenceModel,LoreProposalEvidenceModel,LoreProposalModel,CharacterMemoryModel,MemorySnapshotModel
from .common import chapter_or_raise,external_uuid,novel_or_raise
from .models import ChapterModel,NovelModel,CharacterModel
REQUIRED_TABLES={"evidence_records","lore_proposals","lore_proposal_evidence","character_memories","memory_snapshots"}
def now():return datetime.now(timezone.utc)
class PostgresLoreRepository:
 def __init__(self,database):self.database=database
 def _require_tables(self):
  missing=REQUIRED_TABLES-set(inspect(self.database.engine).get_table_names())
  if missing:raise RuntimeError("Lore PostgreSQL schema is unavailable; missing tables: "+", ".join(sorted(missing)))
 @staticmethod
 def _chapter(session,cid):
  if not cid:return None
  row=session.get(ChapterModel,cid);novel=session.get(NovelModel,row.novel_id) if row else None
  return f"{novel.slug}:{row.chapter_number}" if row and novel else None
 def _ev(self,s,x):
  novel=s.get(NovelModel,x.novel_id);loc=dict(x.locator or {});eid=loc.pop("_external_id",str(x.id))
  return Evidence.model_validate({"id":eid,"novel_id":novel.slug,"schema_version":x.schema_version,"source_type":x.source_type,"source_id":x.source_id,"chapter_id":self._chapter(s,x.chapter_id),"chapter_version":x.chapter_version,"generation_job_id":str(x.generation_job_id) if x.generation_job_id else None,"excerpt":x.excerpt,"locator":loc,"content_hash":x.content_hash,"privacy":x.privacy,"status":x.status,"invalidation_reason":x.invalidation_reason,"created_at":x.created_at,"updated_at":x.updated_at}).model_dump(mode="json")
 def _prop(self,s,x):
  novel=s.get(NovelModel,x.novel_id);payload=dict(x.payload or {});pid=payload.pop("_external_id",str(x.id))
  return LoreProposal.model_validate({"id":pid,"novel_id":novel.slug,"proposal_type":x.proposal_type,"schema_version":x.schema_version,"payload":payload,"approved_payload":x.approved_payload,"status":x.status,"source_chapter_id":self._chapter(s,x.source_chapter_id),"source_version":x.source_version,"agent_name":x.agent_name,"generation_job_id":str(x.generation_job_id) if x.generation_job_id else None,"confidence":float(x.confidence) if x.confidence is not None else None,"reviewed_by":x.reviewed_by,"reviewed_at":x.reviewed_at,"rejection_reason":x.rejection_reason,"created_at":x.created_at,"updated_at":x.updated_at}).model_dump(mode="json")
 def create_evidence(self,item):
  self._require_tables();m=Evidence.model_validate(item)
  with self.database.session() as s:
   n=novel_or_raise(s,m.novel_id);c=None
   if m.chapter_id:_,c=chapter_or_raise(s,m.chapter_id)
   row=EvidenceModel(id=external_uuid(m.id),novel_id=n.id,schema_version=m.schema_version,source_type=m.source_type,source_id=m.source_id,chapter_id=c.id if c else None,chapter_version=m.chapter_version,generation_job_id=external_uuid(m.generation_job_id) if m.generation_job_id else None,excerpt=m.excerpt,locator={**m.locator,"_external_id":m.id},content_hash=m.content_hash,privacy=m.privacy,status=m.status,invalidation_reason=m.invalidation_reason,created_at=m.created_at,updated_at=m.updated_at);s.add(row)
   try:s.flush()
   except IntegrityError as e:raise FileExistsError(m.id) from e
   return self._ev(s,row)
 def get_evidence(self,eid):
  self._require_tables()
  with self.database.session() as s:
   row=s.get(EvidenceModel,external_uuid(eid))
   if not row:raise FileNotFoundError(eid)
   return self._ev(s,row)
 def list_evidence(self,nid):
  self._require_tables()
  with self.database.session() as s:n=novel_or_raise(s,nid);return [self._ev(s,x) for x in s.scalars(select(EvidenceModel).where(EvidenceModel.novel_id==n.id).order_by(EvidenceModel.created_at,EvidenceModel.id)).all()]
 def invalidate_evidence(self,eid,reason):
  self._require_tables()
  with self.database.session() as s:
   row=s.scalar(select(EvidenceModel).where(EvidenceModel.id==external_uuid(eid)).with_for_update())
   if not row:raise FileNotFoundError(eid)
   require_evidence_transition(row.status,"INVALIDATED");row.status="INVALIDATED";row.invalidation_reason=reason;row.updated_at=now();s.flush();return self._ev(s,row)
 def create_proposal(self,item):
  self._require_tables();m=LoreProposal.model_validate(item)
  with self.database.session() as s:
   n=novel_or_raise(s,m.novel_id);c=None
   if m.source_chapter_id:_,c=chapter_or_raise(s,m.source_chapter_id)
   row=LoreProposalModel(id=external_uuid(m.id),novel_id=n.id,proposal_type=m.proposal_type,schema_version=m.schema_version,payload={**m.payload,"_external_id":m.id},status=m.status,source_chapter_id=c.id if c else None,source_version=m.source_version,agent_name=m.agent_name,generation_job_id=external_uuid(m.generation_job_id) if m.generation_job_id else None,confidence=m.confidence,created_at=m.created_at,updated_at=m.updated_at);s.add(row)
   try:s.flush()
   except IntegrityError as e:raise FileExistsError(m.id) from e
   return self._prop(s,row)
 def get_proposal(self,pid):
  self._require_tables()
  with self.database.session() as s:
   row=s.get(LoreProposalModel,external_uuid(pid))
   if not row:raise FileNotFoundError(pid)
   return self._prop(s,row)
 def list_proposals(self,nid,status=None):
  self._require_tables()
  with self.database.session() as s:
   n=novel_or_raise(s,nid);q=select(LoreProposalModel).where(LoreProposalModel.novel_id==n.id)
   if status:q=q.where(LoreProposalModel.status==status)
   return [self._prop(s,x) for x in s.scalars(q.order_by(LoreProposalModel.created_at,LoreProposalModel.id)).all()]
 def link_evidence(self,item):
  self._require_tables();m=ProposalEvidenceRelation.model_validate(item)
  with self.database.session() as s:
   p=s.get(LoreProposalModel,external_uuid(m.proposal_id));e=s.get(EvidenceModel,external_uuid(m.evidence_id))
   if not p or not e:raise FileNotFoundError("proposal or evidence")
   if p.novel_id!=e.novel_id:raise ValueError("proposal and evidence must belong to the same novel")
   s.add(LoreProposalEvidenceModel(proposal_id=p.id,evidence_id=e.id,schema_version=m.schema_version,relevance=m.relevance,note=m.note,created_at=m.created_at));s.flush();return m.model_dump(mode="json")
 create_relation=link_evidence
 def list_proposal_evidence(self,pid):
  self._require_tables()
  with self.database.session() as s:
   p=s.get(LoreProposalModel,external_uuid(pid))
   if not p:raise FileNotFoundError(pid)
   rows=s.scalars(select(LoreProposalEvidenceModel).where(LoreProposalEvidenceModel.proposal_id==p.id).order_by(LoreProposalEvidenceModel.created_at)).all();out=[]
   for r in rows:
    e=s.get(EvidenceModel,r.evidence_id);eloc=dict(e.locator or {});eid=eloc.get("_external_id",str(e.id));out.append(ProposalEvidenceRelation(proposal_id=pid,evidence_id=eid,relevance=r.relevance,note=r.note,created_at=r.created_at,schema_version=r.schema_version).model_dump(mode="json"))
   return out
 def approve_proposal(self,pid,approved_payload,reviewer):
  self._require_tables()
  with self.database.session() as s:
   row=s.scalar(select(LoreProposalModel).where(LoreProposalModel.id==external_uuid(pid)).with_for_update())
   if not row:raise FileNotFoundError(pid)
   require_proposal_transition(row.status,"APPROVED");row.status="APPROVED";row.approved_payload=approved_payload;row.reviewed_by=reviewer;row.reviewed_at=now();row.updated_at=now();s.flush();return self._prop(s,row)
 def reject_proposal(self,pid,reviewer,reason=None):
  self._require_tables()
  with self.database.session() as s:
   row=s.scalar(select(LoreProposalModel).where(LoreProposalModel.id==external_uuid(pid)).with_for_update())
   if not row:raise FileNotFoundError(pid)
   require_proposal_transition(row.status,"REJECTED");row.status="REJECTED";row.reviewed_by=reviewer;row.reviewed_at=now();row.rejection_reason=reason;row.updated_at=now();s.flush();return self._prop(s,row)
 def _mem(self,s,x):
  n=s.get(NovelModel,x.novel_id);c=s.get(CharacterModel,x.character_id);content=dict(x.content or {});mid=content.pop("_external_id",str(x.id));p=s.get(LoreProposalModel,x.proposal_id);pp=dict(p.payload or {}) if p else {};pid=pp.get("_external_id",str(x.proposal_id));sid=None
  if x.supersedes_id:
   old=s.get(CharacterMemoryModel,x.supersedes_id);sid=(old.content or {}).get("_external_id",str(x.supersedes_id)) if old else str(x.supersedes_id)
  return CharacterMemory.model_validate({"id":mid,"novel_id":n.slug,"character_id":c.slug,"business_id":x.business_id,"memory_type":x.memory_type,"schema_version":x.schema_version,"content":content,"status":x.status,"valid_from_chapter":x.valid_from_chapter,"valid_to_chapter":x.valid_to_chapter,"proposal_id":pid,"supersedes_id":sid,"retraction_reason":x.retraction_reason,"created_at":x.created_at,"updated_at":x.updated_at}).model_dump(mode="json")
 def _add_memory(self,s,m):
  n=novel_or_raise(s,m.novel_id);c=s.scalar(select(CharacterModel).where(CharacterModel.novel_id==n.id,CharacterModel.slug==m.character_id));p=s.get(LoreProposalModel,external_uuid(m.proposal_id))
  if not c:raise FileNotFoundError(m.character_id)
  if not p or p.status!="APPROVED":raise ValueError("memory requires APPROVED proposal")
  row=CharacterMemoryModel(id=external_uuid(m.id),novel_id=n.id,character_id=c.id,business_id=m.business_id,memory_type=m.memory_type,schema_version=m.schema_version,content={**m.content,"_external_id":m.id},status=m.status,valid_from_chapter=m.valid_from_chapter,valid_to_chapter=m.valid_to_chapter,proposal_id=p.id,supersedes_id=external_uuid(m.supersedes_id) if m.supersedes_id else None,retraction_reason=m.retraction_reason,created_at=m.created_at,updated_at=m.updated_at);s.add(row);s.flush();return row
 def create_memory(self,item):
  self._require_tables();m=CharacterMemory.model_validate(item)
  with self.database.session() as s:return self._mem(s,self._add_memory(s,m))
 def get_memory(self,mid):
  self._require_tables()
  with self.database.session() as s:
   row=s.get(CharacterMemoryModel,external_uuid(mid))
   if not row:raise FileNotFoundError(mid)
   return self._mem(s,row)
 def list_character_memories(self,character_id,status=None):
  self._require_tables()
  with self.database.session() as s:
   c=s.scalar(select(CharacterModel).where(CharacterModel.slug==character_id))
   if not c:raise FileNotFoundError(character_id)
   q=select(CharacterMemoryModel).where(CharacterMemoryModel.character_id==c.id)
   if status:q=q.where(CharacterMemoryModel.status==status)
   return [self._mem(s,x) for x in s.scalars(q.order_by(CharacterMemoryModel.created_at)).all()]
 def list_memories(self,nid,status=None):
  self._require_tables()
  with self.database.session() as s:
   n=novel_or_raise(s,nid);q=select(CharacterMemoryModel).where(CharacterMemoryModel.novel_id==n.id)
   if status:q=q.where(CharacterMemoryModel.status==status)
   return [self._mem(s,x) for x in s.scalars(q.order_by(CharacterMemoryModel.created_at)).all()]
 def approve_proposal_with_memory(self,pid,approved_payload,reviewer,memory):
  self._require_tables()
  with self.database.session() as s:
   p=s.scalar(select(LoreProposalModel).where(LoreProposalModel.id==external_uuid(pid)).with_for_update())
   if not p:raise FileNotFoundError(pid)
   evidence=s.scalars(select(EvidenceModel).join(LoreProposalEvidenceModel,LoreProposalEvidenceModel.evidence_id==EvidenceModel.id).where(LoreProposalEvidenceModel.proposal_id==p.id).with_for_update()).all()
   if not evidence:raise ValueError("proposal requires evidence")
   if any(e.status!="ACTIVE" or e.novel_id!=p.novel_id for e in evidence):raise ValueError("all proposal evidence must be ACTIVE and in the same novel")
   require_proposal_transition(p.status,"APPROVED");p.status="APPROVED";p.approved_payload=approved_payload;p.reviewed_by=reviewer;p.reviewed_at=now();p.updated_at=now()
   ext=dict(p.payload or {}).get("_external_id",pid);n=s.get(NovelModel,p.novel_id);m=CharacterMemory.model_validate({**memory,"proposal_id":ext,"novel_id":n.slug});created=self._add_memory(s,m);s.flush();return self._prop(s,p),self._mem(s,created)
 def supersede_memory(self,mid,replacement):
  self._require_tables()
  with self.database.session() as s:
   old=s.scalar(select(CharacterMemoryModel).where(CharacterMemoryModel.id==external_uuid(mid)).with_for_update())
   if not old:raise FileNotFoundError(mid)
   if old.status!="ACTIVE":raise ValueError("only ACTIVE memory can be superseded")
   base=self._mem(s,old);m=CharacterMemory.model_validate({**replacement,"novel_id":base["novel_id"],"character_id":base["character_id"],"supersedes_id":mid});new=self._add_memory(s,m);old.status="SUPERSEDED";old.updated_at=now();s.flush();return self._mem(s,new)
 def retract_memory(self,mid,reason):
  self._require_tables()
  with self.database.session() as s:
   row=s.scalar(select(CharacterMemoryModel).where(CharacterMemoryModel.id==external_uuid(mid)).with_for_update())
   if not row:raise FileNotFoundError(mid)
   if row.status!="ACTIVE":raise ValueError("only ACTIVE memory can be retracted")
   row.status="RETRACTED";row.retraction_reason=reason;row.updated_at=now();s.flush();return self._mem(s,row)
 def _snap(self,s,x):
  n=s.get(NovelModel,x.novel_id);mem=dict(x.memory or {});sid=mem.pop("_external_id",str(x.id));sup=None
  if x.supersedes_id:
   old=s.get(MemorySnapshotModel,x.supersedes_id);sup=(old.memory or {}).get("_external_id",str(x.supersedes_id)) if old else str(x.supersedes_id)
  return MemorySnapshot.model_validate({"id":sid,"novel_id":n.slug,"scope":x.scope,"scope_key":x.scope_key,"schema_version":x.schema_version,"range_start":x.range_start,"range_end":x.range_end,"memory":mem,"version":x.version,"source_watermark":x.source_watermark,"content_hash":x.content_hash,"supersedes_id":sup,"created_by":x.created_by,"created_at":x.created_at}).model_dump(mode="json")
 def create_snapshot(self,item):
  self._require_tables();m=MemorySnapshot.model_validate(item)
  with self.database.session() as s:
   n=novel_or_raise(s,m.novel_id);row=MemorySnapshotModel(id=external_uuid(m.id),novel_id=n.id,scope=m.scope,scope_key=m.scope_key,schema_version=m.schema_version,range_start=m.range_start,range_end=m.range_end,memory={**m.memory,"_external_id":m.id},version=m.version,source_watermark=m.source_watermark,content_hash=m.content_hash,supersedes_id=external_uuid(m.supersedes_id) if m.supersedes_id else None,created_by=m.created_by,created_at=m.created_at);s.add(row);s.flush();return self._snap(s,row)
 def list_snapshots(self,nid,scope=None):
  self._require_tables()
  with self.database.session() as s:
   n=novel_or_raise(s,nid);q=select(MemorySnapshotModel).where(MemorySnapshotModel.novel_id==n.id)
   if scope:q=q.where(MemorySnapshotModel.scope==scope)
   return [self._snap(s,x) for x in s.scalars(q.order_by(MemorySnapshotModel.created_at)).all()]
 def get_latest_snapshot(self,nid,scope,scope_key):
  self._require_tables()
  with self.database.session() as s:
   n=novel_or_raise(s,nid);row=s.scalar(select(MemorySnapshotModel).where(MemorySnapshotModel.novel_id==n.id,MemorySnapshotModel.scope==scope,MemorySnapshotModel.scope_key==scope_key).order_by(MemorySnapshotModel.version.desc()).limit(1));return self._snap(s,row) if row else None
