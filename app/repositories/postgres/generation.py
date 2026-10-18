from __future__ import annotations
from ...runtime_events import committed_change
from datetime import datetime,timezone
from contextlib import contextmanager
from copy import deepcopy
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
        from ...creative.director_image_terminal import preserve as preserve_image
        from ...creative.director_terminal_evidence import FIELD, preserve_evidence
        if FIELD in item:
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_POSTGRES_UNSUPPORTED")
        with self.database.session() as session:
            binding = graph_job_binding(item)
            novel_uuid = self._graph_owner(session, item, binding) if binding is not None else None
            iid=external_uuid(item["id"]);row=session.scalar(select(GenerationJobModel).where(GenerationJobModel.id == iid).with_for_update());chapter_uuid=None
            item = preserve_image(self._payload(row) if row is not None else None,
                preserve_evidence(self._payload(row) if row is not None else None, item))
            if binding is None and row is not None and graph_job_binding(self._payload(row)) is not None:
                raise GenerationProjectIdentityError("GENERATION_GRAPH_JOB_BINDING_CHANGED")
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
    def _matches_director_store(self, store):
        """Same original PostgreSQL endpoint; never accept a second job database."""
        from sqlalchemy.engine import make_url
        from .session import Database
        if type(self.database) is not Database or getattr(store, 'backend', None) != 'postgres':
            return False
        try:
            url = store.database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
            return self.database.engine.url == make_url(url)
        except (ValueError, TypeError, AttributeError):
            return False

    @staticmethod
    def _validate_director_job_id(jid):
        from uuid import UUID
        if not isinstance(jid, str):
            raise ValueError('GENERATION_JOB_ID_INVALID')
        try:
            if str(UUID(jid)) != jid: raise ValueError('noncanonical')
        except ValueError:
            raise ValueError('GENERATION_JOB_ID_INVALID') from None

    def _publish_director_terminal(self, job, capability, evidence):
        """Live original worker only: owner KEY SHARE then generation-row leaf."""
        from threading import get_ident
        import hashlib
        from ...model_execution import _CreativeDirectorCapability
        from ...creative.director_terminal_evidence import FIELD, validate_evidence, digest, _PublicationAcknowledgment
        self._validate_director_job_id(job.id)
        if type(capability) is not _CreativeDirectorCapability:
            raise ValueError('CREATIVE_DIRECTOR_TERMINAL_OWNER_REQUIRED')
        capability._check(job, started=True)
        repository = getattr(capability.manager.persistence, 'repository', capability.manager.persistence)
        if (repository is not self or not capability.worker_claimed
                or capability.publication_state != 'PUBLISHING'
                or capability.publication_thread != get_ident()
                or capability._publication_binding is None
                or capability._publication_binding[1] is not self
                or capability._publication_binding[2] != job.expected_request_digest
                or capability.terminal_publication is not capability._publication_binding[0]):
            raise ValueError('CREATIVE_DIRECTOR_TERMINAL_OWNER_REQUIRED')
        item = job.public()
        if (item.get('status') != 'COMPLETED' or item.get('execution_outcome') != 'COMPLETED'
                or item.get('terminal_hook_status') != 'COMPLETED' or not job.output.strip()):
            raise ValueError('CREATIVE_DIRECTOR_TERMINAL_RESULT_REQUIRED')
        evidence = validate_evidence(evidence, item)
        if (evidence['output_digest'] != hashlib.sha256(job.output.encode('utf-8')).hexdigest()
                or evidence['output_bytes'] != len(job.output.encode('utf-8'))
                or evidence['route']['fingerprint'] != capability.route_fingerprint
                or evidence['route']['provider_id'] != job.requested_provider or job.provider != job.requested_provider
                or evidence['route']['model_id'] != job.requested_model or job.model != job.requested_model):
            raise ValueError('CREATIVE_DIRECTOR_TERMINAL_OUTPUT_CHANGED')
        binding = graph_job_binding(item)
        with self.database.session() as session:
            owner_id = self._graph_owner(session, item, binding)
            row = session.scalar(select(GenerationJobModel).where(
                GenerationJobModel.id == external_uuid(job.id)).with_for_update())
            if row is None: raise ValueError('CREATIVE_DIRECTOR_TERMINAL_ORIGINAL_JOB_REQUIRED')
            if row.novel_id != owner_id:
                raise GenerationProjectIdentityError('GENERATION_GRAPH_PROJECT_OWNER_CHANGED')
            previous = self._payload(row)
            check_graph_job_update(previous, item)
            if FIELD in previous: raise ValueError('CREATIVE_DIRECTOR_TERMINAL_ALREADY_ATTEMPTED')
            if any(previous.get(key) != item.get(key) for key in (
                    'status', 'execution_outcome', 'terminal_hook_status', 'output', 'provider', 'model',
                    'requested_provider', 'requested_model', 'generation_deadline', 'generation_max_output_bytes')):
                raise ValueError('CREATIVE_DIRECTOR_TERMINAL_ORIGINAL_JOB_CHANGED')
            item[FIELD] = evidence
            row.request = {**dict(row.request or {}), '_repository_payload': deepcopy(item)}
            session.flush()
        return _PublicationAcknowledgment(capability, self, job, digest(evidence))

    @contextmanager
    def _director_snapshot_leaf(self, jid):
        """Detached row under a leaf lock retained through original scope commit.

        Caller already holds raw scope and original owner. No authority/policy
        callback or owner acquisition is performed while this leaf is held.
        Generic saves take the same row lock, so clearing cannot interleave.
        """
        self._validate_director_job_id(jid)
        with self.database.session() as session:
            row = session.scalar(select(GenerationJobModel).where(
                GenerationJobModel.id == external_uuid(jid)).with_for_update())
            if row is None: raise KeyError(jid)
            yield deepcopy(self._payload(row))

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
