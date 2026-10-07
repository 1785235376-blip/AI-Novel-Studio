from __future__ import annotations
import hashlib
from datetime import datetime,timezone
from sqlalchemy import select
from .common import chapter_or_raise,external_uuid,novel_or_raise
from .models import CanonModel,NovelModel,PendingCanonModel
from .serialization import serialize_canon
from ...privacy import merge_privacy, privacy_record

class PostgresCanonRepository:
    def __init__(self,database):self.database=database
    @staticmethod
    def _pending(row,slug):
        payload=dict(row.proposal or {});return {**payload,"id":payload.get("id",str(row.id)),"novel_id":slug,"status":row.status}
    def _find(self,session,pid,lock=False):
        row=session.scalar(select(PendingCanonModel).where(PendingCanonModel.id==external_uuid(pid)).with_for_update()) if lock else session.get(PendingCanonModel,external_uuid(pid))
        if row is None:raise FileNotFoundError(pid)
        return session.get(NovelModel,row.novel_id),row
    def list(self,nid):
        with self.database.session() as session:
            novel=novel_or_raise(session,nid);rows=session.scalars(select(CanonModel).where(CanonModel.novel_id==novel.id).order_by(CanonModel.approved_at)).all()
            return [{**serialize_canon(x),"source":x.source,"confidence":(x.fact_value or {}).get("confidence","USER_APPROVED"),"id":str(x.id)} for x in rows]
    def list_pending(self,nid):
        with self.database.session() as session:
            novel=novel_or_raise(session,nid);rows=session.scalars(select(PendingCanonModel).where(PendingCanonModel.novel_id==novel.id,PendingCanonModel.status=="PENDING").order_by(PendingCanonModel.created_at)).all();return [self._pending(x,novel.slug) for x in rows]
    def get_pending(self,pid):
        with self.database.session() as session:novel,row=self._find(session,pid);return self._pending(row,novel.slug)
    def save_pending(self,item):
        if "id" not in item:raise ValueError("pending canon id is required")
        with self.database.session() as session:
            novel=novel_or_raise(session,item["novel_id"]);iid=external_uuid(item["id"]);row=session.scalar(select(PendingCanonModel).where(PendingCanonModel.id==iid).with_for_update());chapter_uuid=None
            if row is not None and row.novel_id!=novel.id:raise FileNotFoundError(item["id"])
            if row is not None and row.status in {"APPROVED","REJECTED"}:
                if (row.proposal or {}).get("proposals")!=item.get("proposals"):raise ValueError("CANON_TERMINAL_EDIT_FORBIDDEN")
                return self._pending(row,novel.slug)
            if row is not None and (row.proposal or {}).get("review_owner"):raise ValueError("VERSIONED_CANON_REVIEW_REQUIRED")
            ref=item.get("chapter_id") or (f"{novel.slug}:{item['chapter']}" if item.get("chapter") is not None else None)
            if ref:
                try:_,chapter=chapter_or_raise(session,ref);chapter_uuid=chapter.id
                except FileNotFoundError:pass
            if row is None:row=PendingCanonModel(id=iid,novel_id=novel.id,chapter_id=chapter_uuid,proposal=dict(item),status=item.get("status","PENDING"));session.add(row)
            else:row.proposal=dict(item);row.status=item.get("status",row.status);row.chapter_id=chapter_uuid
            session.flush();return self._pending(row,novel.slug)
    def approve(self,pid,proposals=None):
        with self.database.session() as session:
            novel,row=self._find(session,pid,True);payload=dict(row.proposal or {})
            if payload.get("review_owner"):raise ValueError("VERSIONED_CANON_REVIEW_REQUIRED")
            if row.status=="APPROVED":
                if proposals is not None and proposals!=payload.get("proposals",[]):raise ValueError("CANON_TERMINAL_EDIT_FORBIDDEN")
                return self._pending(row,novel.slug)
            if row.status!="PENDING":raise ValueError("CANON_ALREADY_REVIEWED")
            if proposals is not None:payload["proposals"]=proposals
            session.scalar(select(NovelModel).where(NovelModel.id==novel.id).with_for_update())
            row.proposal=payload;row.status="APPROVED";row.reviewed_by="local-user";row.reviewed_at=datetime.now(timezone.utc)
            for index,proposal in enumerate(payload.get("proposals",[])):
                value={**privacy_record(proposal),"confidence":"USER_APPROVED"};entity_type=str(proposal.get("entity_type","story"));key=str(proposal.get("fact_key") or proposal.get("key") or hashlib.sha256(f"{pid}:{index}".encode()).hexdigest())
                existing=session.scalar(select(CanonModel).where(CanonModel.novel_id==novel.id,CanonModel.entity_type==entity_type,CanonModel.entity_id.is_(None),CanonModel.fact_key==key))
                if existing:
                    value["privacy_level"]=merge_privacy(value["privacy_level"],serialize_canon(existing)["privacy_level"])
                    existing.fact_value=value;existing.privacy=value["privacy_level"];existing.source=f"pending:{pid}";existing.approved_at=datetime.now(timezone.utc)
                else:session.add(CanonModel(novel_id=novel.id,entity_type=entity_type,entity_id=None,fact_key=key,fact_value=value,privacy=value["privacy_level"],source=f"pending:{pid}"))
            session.flush();return self._pending(row,novel.slug)
    def reject(self,pid):
        with self.database.session() as session:
            novel,row=self._find(session,pid,True)
            if (row.proposal or {}).get("review_owner"):raise ValueError("VERSIONED_CANON_REVIEW_REQUIRED")
            if row.status=="REJECTED":return self._pending(row,novel.slug)
            if row.status!="PENDING":raise ValueError("CANON_ALREADY_REVIEWED")
            row.status="REJECTED";row.reviewed_by="local-user";row.reviewed_at=datetime.now(timezone.utc);session.flush();return self._pending(row,novel.slug)

    def review_pending_atomic(self,nid,pid,operation_id,request_digest,callback,check):
        with self.database.session() as session:
            novel,row=self._find(session,pid,True)
            if novel.slug!=nid:raise FileNotFoundError(pid)
            result,approve=callback(self._pending(row,novel.slug))
            check()
            if approve:
                # Serialize Canon key ownership, and bind promotion to the exact
                # chapter row in the same PostgreSQL transaction.
                session.scalar(select(NovelModel).where(NovelModel.id==novel.id).with_for_update())
                source=result.get("review_source")
                if source:
                    from .chapter import PostgresChapterRepository
                    from ...source_privacy import content_digest
                    from ...services.finding_review_service import FindingReviewConflict
                    _,chapter=chapter_or_raise(session,source["chapter_id"])
                    session.refresh(chapter,with_for_update=True)
                    current=PostgresChapterRepository._external(novel,chapter)
                    if current.get("is_archived") or current["version"]!=source["version"] or content_digest(current)!=source["digest"]:raise FindingReviewConflict("CANON_PREVIEW_STALE")
                for index,proposal in enumerate(result.get("proposals",[])):
                    value={**privacy_record(proposal),"confidence":"USER_APPROVED"}
                    entity_type=str(proposal.get("entity_type","story"))
                    key=str(proposal.get("fact_key") or proposal.get("key") or hashlib.sha256(f"{pid}:{index}".encode()).hexdigest())
                    existing=session.scalar(select(CanonModel).where(CanonModel.novel_id==novel.id,CanonModel.entity_type==entity_type,CanonModel.entity_id.is_(None),CanonModel.fact_key==key).with_for_update())
                    if existing:
                        value["privacy_level"]=merge_privacy(value["privacy_level"],serialize_canon(existing)["privacy_level"])
                        existing.fact_value=value;existing.privacy=value["privacy_level"];existing.source=f"pending:{pid}";existing.approved_at=datetime.now(timezone.utc)
                    else:session.add(CanonModel(novel_id=novel.id,entity_type=entity_type,entity_id=None,fact_key=key,fact_value=value,privacy=value["privacy_level"],source=f"pending:{pid}"))
            row.proposal=dict(result);row.status=result["status"]
            row.reviewed_by=result.get("reviewed_by");row.reviewed_at=datetime.now(timezone.utc)
            session.flush();check()
            return self._pending(row,novel.slug)

    def cancel_pending_recovery(self,nid,pid,actor,expected_version,check):
        from ...services.finding_review_service import FindingReviewConflict
        with self.database.session() as session:
            novel,row=self._find(session,pid,True);check()
            if novel.slug!=nid:raise FileNotFoundError(pid)
            if (row.proposal or {}).get("review_version",1)!=expected_version:raise FindingReviewConflict("CANON_VERSION_CONFLICT")
            raise ValueError("CANON_NO_PENDING_RECOVERY: PostgreSQL rolls back interrupted transactions")

    def list_reviewable(self,nid):
        with self.database.session() as session:
            novel=novel_or_raise(session,nid)
            rows=session.scalars(select(PendingCanonModel).where(PendingCanonModel.novel_id==novel.id).order_by(PendingCanonModel.created_at)).all()
            return [self._pending(row,novel.slug) for row in rows]

    def recover_pending_committed(self,nid,pid,expected_version,check):
        with self.database.session() as session:
            novel,row=self._find(session,pid,True);check()
            if novel.slug!=nid:raise FileNotFoundError(pid)
            raise ValueError("CANON_NO_PENDING_RECOVERY: PostgreSQL commits the receipt and facts together")
