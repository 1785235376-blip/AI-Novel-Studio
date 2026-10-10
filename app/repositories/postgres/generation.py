from __future__ import annotations
from ...runtime_events import committed_change
from datetime import datetime,timezone
from sqlalchemy import select, text
from .common import chapter_or_raise,external_uuid,novel_or_raise
from .models import GenerationJobModel, NovelModel
from ..generation_repository import (GenerationProjectIdentityError, graph_job_binding,
                                     check_graph_job_update)

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
    @staticmethod
    def _graph_owner(session, item, binding):
        try:
            # Lock the original project row through the same save transaction.
            # DELETE cannot pass validation and then replace this slug midway.
            # KEY SHARE also composes with a CreativeProjectStore owner lease
            # on a different connection; UPDATE would deadlock that caller.
            owner = session.scalar(select(NovelModel).where(
                NovelModel.slug == item["novel_id"]).with_for_update(read=True, key_share=True))
            if owner is None: raise FileNotFoundError(item["novel_id"])
            if binding["project_incarnation"] != "postgres:" + str(owner.id):
                raise ValueError("different project owner")
            return owner.id
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            raise GenerationProjectIdentityError("GENERATION_GRAPH_PROJECT_OWNER_CHANGED") from None

    @committed_change("TASK")
    def save(self,item):
        with self.database.session() as session:
            binding = graph_job_binding(item)
            novel_uuid = self._graph_owner(session, item, binding) if binding is not None else None
            iid=external_uuid(item["id"]);row=session.get(GenerationJobModel,iid);chapter_uuid=None
            if binding is None and item.get("novel_id"):novel_uuid=novel_or_raise(session,item["novel_id"]).id
            if binding is not None and row is not None:
                check_graph_job_update(self._payload(row), item)
                if row.novel_id != novel_uuid:
                    raise GenerationProjectIdentityError("GENERATION_GRAPH_JOB_BINDING_CHANGED")
            from ..branch_manuscript import is_branch_chapter_id
            branch_owned = is_branch_chapter_id(item.get('novel_id'), item.get('chapter_id'))
            if branch_owned:
                from ...services.branch_manuscript_service import experimental_scope
                from ...experimental.store import ExperimentalStore
                from ..branch_manuscript import COLLECTION, OWNER, branch_scope
                scope = branch_scope(experimental_scope(item.get("scope") or {}))
                if scope["novel_id"] != item.get("novel_id"): raise ValueError("GENERATION_BRANCH_PROJECT_MISMATCH")
                key = ExperimentalStore.key(item["novel_id"], scope)
                doc = session.execute(text("SELECT document FROM experimental_scope_documents WHERE scope_key=:key"), {"key": key}).scalar_one_or_none()
                manuscript = (doc or {}).get("collections", {}).get(COLLECTION, {}).get(scope["branch_id"], {})
                chapter = manuscript.get("chapters", {}).get(item["chapter_id"])
                if (manuscript.get("owner") != OWNER or manuscript.get("scope") != scope or not isinstance(chapter, dict)
                        or chapter.get('id') != item['chapter_id'] or chapter.get('novel_id') != item['novel_id']
                        or chapter.get('scope') != scope or chapter.get('branch_id') != scope['branch_id']
                        or chapter.get('authority') != OWNER):
                    raise FileNotFoundError(item["chapter_id"])
                if chapter.get('deleted') and row is None:
                    raise FileNotFoundError(item['chapter_id'])
            elif item.get("chapter_id"):
                _,chapter=chapter_or_raise(session,item["chapter_id"]);chapter_uuid=chapter.id
            if row is not None:
                previous = dict((row.request or {}).get("_repository_payload", {}))
                if ((previous.get("scope") != item.get("scope") and branch_owned)
                        or (row.chapter_id is not None and row.chapter_id != chapter_uuid)
                        or (previous.get("chapter_id") and previous["chapter_id"] != item.get("chapter_id"))):
                    from ...chapter_identity import ChapterIdentityConflict
                    raise ChapterIdentityConflict("GENERATION_CHAPTER_IDENTITY_CHANGED")
            request=dict(item.get("request") or {});request["_repository_payload"]=dict(item)
            values={"novel_id":novel_uuid,"chapter_id":chapter_uuid,"operation":item.get("operation",item.get("agent","unknown")),"status":item.get("status","QUEUED"),"request":request,"draft_path":item.get("draft_path"),"provider":item.get("provider"),"model":item.get("model"),"fallback_used":bool(item.get("fallback_used",False)),"error_code":item.get("error_code"),"error_message":item.get("error_message") or item.get("error"),"result":item.get("result"),"retry_count":int(item.get("retry_count",0)),"timeout_seconds":int(item.get("timeout_seconds",120)),"context_snapshot_id":external_uuid(item["context_snapshot_id"]) if item.get("context_snapshot_id") and not branch_owned else None,"updated_at":datetime.now(timezone.utc)}
            if row is None:row=GenerationJobModel(id=iid,**values);session.add(row)
            else:
                for key,value in values.items():setattr(row,key,value)
            session.flush()
    def get(self,jid):
        with self.database.session() as session:
            row=session.get(GenerationJobModel,external_uuid(jid))
            if row is None:raise KeyError(jid)
            item = self._payload(row)
            binding = graph_job_binding(item)
            if binding is not None:
                try:
                    owner_id = self._graph_owner(session, item, binding)
                    if row.novel_id != owner_id: raise GenerationProjectIdentityError("GENERATION_GRAPH_PROJECT_OWNER_CHANGED")
                except GenerationProjectIdentityError: raise KeyError(jid) from None
            return item
    def load_all(self):
        with self.database.session() as session:
            result = []
            for row in session.scalars(select(GenerationJobModel).order_by(GenerationJobModel.created_at)).all():
                item = self._payload(row)
                try:
                    binding = graph_job_binding(item)
                    if binding is not None and row.novel_id != self._graph_owner(session, item, binding):
                        continue
                except GenerationProjectIdentityError:
                    continue
                result.append(item)
            return result
