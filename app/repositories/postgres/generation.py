from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import select
from .common import chapter_or_raise,external_uuid,novel_or_raise
from .models import GenerationJobModel

class PostgresGenerationRepository:
    def __init__(self,database):self.database=database
    @staticmethod
    def _payload(row):
        saved=dict((row.request or {}).get("_repository_payload",{}));saved.update({"id":saved.get("id",str(row.id)),"status":row.status})
        if row.context_snapshot_id is not None:saved["context_snapshot_id"]=str(row.context_snapshot_id)
        if row.result is not None:saved["result"]=row.result
        if row.error_code is not None:saved["error_code"]=row.error_code
        if row.error_message is not None:saved["error"]=row.error_message
        return saved
    def save(self,item):
        with self.database.session() as session:
            iid=external_uuid(item["id"]);row=session.get(GenerationJobModel,iid);novel_uuid=chapter_uuid=None
            if item.get("novel_id"):novel_uuid=novel_or_raise(session,item["novel_id"]).id
            if item.get("chapter_id"):_,chapter=chapter_or_raise(session,item["chapter_id"]);chapter_uuid=chapter.id
            request=dict(item.get("request") or {});request["_repository_payload"]=dict(item)
            values={"novel_id":novel_uuid,"chapter_id":chapter_uuid,"operation":item.get("operation",item.get("agent","unknown")),"status":item.get("status","QUEUED"),"request":request,"draft_path":item.get("draft_path"),"provider":item.get("provider"),"model":item.get("model"),"fallback_used":bool(item.get("fallback_used",False)),"error_code":item.get("error_code"),"error_message":item.get("error_message") or item.get("error"),"result":item.get("result"),"retry_count":int(item.get("retry_count",0)),"timeout_seconds":int(item.get("timeout_seconds",120)),"context_snapshot_id":external_uuid(item["context_snapshot_id"]) if item.get("context_snapshot_id") else None,"updated_at":datetime.now(timezone.utc)}
            if row is None:row=GenerationJobModel(id=iid,**values);session.add(row)
            else:
                for key,value in values.items():setattr(row,key,value)
            session.flush()
    def get(self,jid):
        with self.database.session() as session:
            row=session.get(GenerationJobModel,external_uuid(jid))
            if row is None:raise KeyError(jid)
            return self._payload(row)
    def load_all(self):
        with self.database.session() as session:return [self._payload(x) for x in session.scalars(select(GenerationJobModel).order_by(GenerationJobModel.created_at)).all()]
