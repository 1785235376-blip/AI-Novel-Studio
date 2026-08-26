from __future__ import annotations
import hashlib
from datetime import datetime,timezone
from sqlalchemy import select
from .common import chapter_or_raise,external_uuid,novel_or_raise
from .models import CanonModel,NovelModel,PendingCanonModel

class PostgresCanonRepository:
    def __init__(self,database):self.database=database
    @staticmethod
    def _pending(row,slug):
        payload=dict(row.proposal or {});return {**payload,"id":payload.get("id",str(row.id)),"novel_id":slug,"status":row.status}
    def _find(self,session,pid):
        row=session.get(PendingCanonModel,external_uuid(pid))
        if row is None:raise FileNotFoundError(pid)
        return session.get(NovelModel,row.novel_id),row
    def list(self,nid):
        with self.database.session() as session:
            novel=novel_or_raise(session,nid);rows=session.scalars(select(CanonModel).where(CanonModel.novel_id==novel.id).order_by(CanonModel.approved_at)).all()
            return [{**(x.fact_value or {}),"source":x.source,"confidence":(x.fact_value or {}).get("confidence","USER_APPROVED"),"privacy_level":x.privacy,"id":str(x.id)} for x in rows]
    def list_pending(self,nid):
        with self.database.session() as session:
            novel=novel_or_raise(session,nid);rows=session.scalars(select(PendingCanonModel).where(PendingCanonModel.novel_id==novel.id,PendingCanonModel.status=="PENDING").order_by(PendingCanonModel.created_at)).all();return [self._pending(x,novel.slug) for x in rows]
    def get_pending(self,pid):
        with self.database.session() as session:novel,row=self._find(session,pid);return self._pending(row,novel.slug)
    def save_pending(self,item):
        if "id" not in item:raise ValueError("pending canon id is required")
        with self.database.session() as session:
            novel=novel_or_raise(session,item["novel_id"]);iid=external_uuid(item["id"]);row=session.get(PendingCanonModel,iid);chapter_uuid=None
            ref=item.get("chapter_id") or (f"{novel.slug}:{item['chapter']}" if item.get("chapter") is not None else None)
            if ref:
                try:_,chapter=chapter_or_raise(session,ref);chapter_uuid=chapter.id
                except FileNotFoundError:pass
            if row is None:row=PendingCanonModel(id=iid,novel_id=novel.id,chapter_id=chapter_uuid,proposal=dict(item),status=item.get("status","PENDING"));session.add(row)
            else:row.proposal=dict(item);row.status=item.get("status",row.status);row.chapter_id=chapter_uuid
            session.flush();return self._pending(row,novel.slug)
    def approve(self,pid,proposals=None):
        with self.database.session() as session:
            novel,row=self._find(session,pid);payload=dict(row.proposal or {})
            if proposals is not None:payload["proposals"]=proposals
            row.proposal=payload;row.status="APPROVED";row.reviewed_by="local-user";row.reviewed_at=datetime.now(timezone.utc)
            for index,proposal in enumerate(payload.get("proposals",[])):
                value={**proposal,"confidence":"USER_APPROVED"};entity_type=str(proposal.get("entity_type","story"));key=str(proposal.get("fact_key") or proposal.get("key") or hashlib.sha256(f"{pid}:{index}".encode()).hexdigest())
                existing=session.scalar(select(CanonModel).where(CanonModel.novel_id==novel.id,CanonModel.entity_type==entity_type,CanonModel.entity_id.is_(None),CanonModel.fact_key==key))
                if existing:existing.fact_value=value;existing.source=f"pending:{pid}";existing.approved_at=datetime.now(timezone.utc)
                else:session.add(CanonModel(novel_id=novel.id,entity_type=entity_type,entity_id=None,fact_key=key,fact_value=value,privacy=proposal.get("privacy_level","CLOUD_ALLOWED"),source=f"pending:{pid}"))
            session.flush();return self._pending(row,novel.slug)
    def reject(self,pid):
        with self.database.session() as session:
            novel,row=self._find(session,pid);row.status="REJECTED";row.reviewed_by="local-user";row.reviewed_at=datetime.now(timezone.utc);session.flush();return self._pending(row,novel.slug)
