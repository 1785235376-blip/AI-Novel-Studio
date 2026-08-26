from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from sqlalchemy import func, select, text, update

from ..document import document_to_markdown, markdown_to_document
from ..repositories.chapter_repository import VersionConflict, _file_save_lock
from ..repositories.postgres.common import chapter_or_raise, novel_or_raise
from ..repositories.postgres.models import ChapterModel, DocumentVersionModel
from ..storage import atomic_write
from .audit_service import AuditService


def _scope_metadata(event: dict) -> tuple[str | None, str | None]:
    scope = event.get("scope") or {}
    kind = scope.get("kind")
    keys = {"WORKSPACE": "workspace_id", "PROJECT": "project_id",
            "STORYLINE": "storyline_id", "BRANCH": "branch_id"}
    return kind, scope.get(keys.get(kind, ""))


class PostgresAtomicChapterAuditPort:
    """Commits chapter CAS, immutable history and success audit in one transaction."""

    def __init__(self, chapter_repository):
        self.repository = chapter_repository

    def save_chapter_with_audit(self, chapter_id, document, expected_version,
                                source, operator, audit_event):
        database = self.repository.database
        with database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            old_document = chapter.document or markdown_to_document("")
            old_updated_at = chapter.updated_at
            markdown = document_to_markdown(document)
            title = chapter.title
            if document.get("content") and document["content"][0].get("type") == "heading":
                title = "".join(x.get("text", "") for x in document["content"][0].get("content", []))
            changed = session.execute(update(ChapterModel).where(
                ChapterModel.id == chapter.id, ChapterModel.version == expected_version,
            ).values(document=document, version=expected_version + 1,
                     updated_at=datetime.now(timezone.utc),
                     content_hash=hashlib.sha256(markdown.encode()).hexdigest(),
                     title=title).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                session.expire_all()
                actual = session.scalar(select(ChapterModel).where(ChapterModel.id == chapter.id))
                raise VersionConflict(self.repository._external(novel, actual),
                                      resource_id=chapter_id, expected_version=expected_version)
            scope_type, scope_id = _scope_metadata(audit_event)
            session.add(DocumentVersionModel(
                chapter_id=chapter.id, version=expected_version, document=old_document,
                created_at=old_updated_at, operator=operator, source=source,
                actor_id=operator, session_id=(audit_event.get("metadata") or {}).get("session_id"),
                scope_type=scope_type, scope_id=scope_id,
                metadata_={"correlation_id": (audit_event.get("metadata") or {}).get("correlation_id")},
                reason=source,
            ))
            session.execute(text(
                "INSERT INTO authorization_audit_events(id,payload) VALUES (:id,CAST(:payload AS jsonb))"
            ), {"id": audit_event["id"], "payload": json.dumps(audit_event, ensure_ascii=False)})
            session.flush(); session.refresh(chapter)
            return self.repository._external(novel, chapter)

    def create_chapter_with_audit(self, project_id, title, operator, audit_event_factory):
        database = self.repository.database
        with database.session() as session:
            novel = novel_or_raise(session, project_id)
            session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                            {"key": f"chapter-create:{project_id}"})
            number = (session.scalar(select(func.max(ChapterModel.chapter_number)).where(
                ChapterModel.novel_id == novel.id)) or 0) + 1
            markdown = f"# {title}\n"
            chapter = ChapterModel(
                novel_id=novel.id, chapter_number=number, title=title,
                markdown_path=f"chapters/chapter-{number:04d}.md",
                content_hash=hashlib.sha256(markdown.encode()).hexdigest(),
                document=markdown_to_document(markdown), version=1,
            )
            session.add(chapter); session.flush()
            created = self.repository._external(novel, chapter)
            event = audit_event_factory(created)
            session.execute(text(
                "INSERT INTO authorization_audit_events(id,payload) VALUES (:id,CAST(:payload AS jsonb))"
            ), {"id": event["id"], "payload": json.dumps(event, ensure_ascii=False)})
            session.flush(); session.refresh(chapter)
            return self.repository._external(novel, chapter)

    def set_chapter_archived_with_audit(self, chapter_id, expected_version, archived, audit_event):
        with self.repository.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            if chapter.version != expected_version:
                raise VersionConflict(self.repository._external(novel, chapter), resource_id=chapter_id, expected_version=expected_version)
            if bool(chapter.is_archived) != archived:
                chapter.is_archived = archived
                chapter.version += 1
                chapter.updated_at = datetime.now(timezone.utc)
                session.execute(text("INSERT INTO authorization_audit_events(id,payload) VALUES (:id,CAST(:payload AS jsonb))"), {"id": audit_event["id"], "payload": json.dumps(audit_event, ensure_ascii=False)})
            session.flush(); session.refresh(chapter)
            return self.repository._external(novel, chapter)


class FileAtomicChapterAuditPort:
    """Same-process File semantic parity with compensating restoration on failure."""

    def __init__(self, chapter_repository, authorization_repository):
        self.repository = chapter_repository
        self.authorization = authorization_repository

    @staticmethod
    def _capture(paths: list[Path]) -> dict[Path, bytes | None]:
        return {path: path.read_bytes() if path.exists() else None for path in paths}

    @staticmethod
    def _restore(snapshot: dict[Path, bytes | None]) -> None:
        for path, value in snapshot.items():
            if value is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(path, value.decode("utf-8"))

    def save_chapter_with_audit(self, chapter_id, document, expected_version,
                                source, operator, audit_event):
        root, number, package_path = self.repository._paths(chapter_id)
        history_path = root / "history" / f"chapter-{number:04d}" / f"v{expected_version:06d}.json"
        markdown_path = root / "chapters" / f"chapter-{number:04d}.md"
        audit_path = self.authorization.path
        with self.authorization.lock, _file_save_lock(package_path):
            snapshot = self._capture([package_path, history_path, markdown_path, audit_path])
            try:
                saved = self.repository.save(chapter_id, document, expected_version, source, operator)
                self.authorization.append_audit_event(audit_event)
                return saved
            except Exception:
                self._restore(snapshot)
                raise

    def create_chapter_with_audit(self, project_id, title, operator, audit_event_factory):
        del operator
        root = self.repository.backend.novels / project_id
        lock_path = root / "chapter_order.json"
        with self.authorization.lock, _file_save_lock(lock_path):
            current = self.repository.list(project_id)
            number = max((row["number"] for row in current), default=0) + 1
            markdown_path = root / "chapters" / f"chapter-{number:04d}.md"
            package_path = root / "documents" / f"chapter-{number:04d}.json"
            snapshot = self._capture([markdown_path, package_path, lock_path, self.authorization.path])
            try:
                created = self.repository.create(project_id, {"title": title, "number": number})
                created = self.repository.get(created["id"])
                self.authorization.append_audit_event(audit_event_factory(created))
                return created
            except Exception:
                self._restore(snapshot)
                raise

    def set_chapter_archived_with_audit(self, chapter_id, expected_version, archived, audit_event):
        root, number, package_path = self.repository._paths(chapter_id)
        state_path = root / "chapter_state.json"
        audit_path = self.authorization.path
        with self.authorization.lock, _file_save_lock(package_path):
            snapshot = self._capture([package_path, state_path, audit_path])
            try:
                before = self.repository.get(chapter_id).get("is_archived", False)
                result = self.repository.archive(chapter_id, expected_version) if archived else self.repository.restore_archive(chapter_id, expected_version)
                if before != archived:
                    self.authorization.append_audit_event(audit_event)
                return result
            except Exception:
                self._restore(snapshot)
                raise


def create_atomic_chapter_audit_port(chapter_repository, authorization_repository):
    if hasattr(chapter_repository, "database"):
        return PostgresAtomicChapterAuditPort(chapter_repository)
    return FileAtomicChapterAuditPort(chapter_repository, authorization_repository)


class AtomicPathMutationPort:
    """Atomic Project/Storyline/Branch creation using existing stores only."""
    def __init__(self, novels, scopes, authorization):
        self.novels, self.scopes, self.authorization = novels, scopes, authorization
        self.audit = AuditService(authorization)

    @property
    def postgres(self): return hasattr(self.novels, "database")

    def _event(self, actor, action, target_type, target_id, scope):
        return self.audit.build(actor, action, target_type, target_id, scope)

    def create_project(self, workspace_id, title, genre, actor):
        from ..authorization import AuthorizationScope, ScopeKind
        project_id, storyline_id, branch_id = str(uuid4()), str(uuid4()), str(uuid4())
        scope = AuthorizationScope(ScopeKind.PROJECT, workspace_id, project_id)
        event = self._event(actor,"PROJECT_CREATED","Project",project_id,scope)
        if self.postgres:
            from ..repositories.postgres.models import NovelModel, StoryStateModel
            with self.novels.database.session() as session:
                now=datetime.now(timezone.utc); novel=NovelModel(slug=project_id,title=title,metadata_json={"genre":genre,"status":"Writing","style_profile":{}},created_at=now,updated_at=now)
                session.add(novel);session.flush();session.add(StoryStateModel(novel_id=novel.id,chapter_number=0,state={"volume":1,"chapter":0,"active_characters":[]}))
                session.execute(text("INSERT INTO project_workspaces(project_id,workspace_id) VALUES (:p,:w)"),{"p":project_id,"w":workspace_id})
                sl={"id":storyline_id,"workspace_id":workspace_id,"project_id":project_id,"name":"Default Storyline","description":""};br={"id":branch_id,"workspace_id":workspace_id,"project_id":project_id,"storyline_id":storyline_id,"name":"main","parent_branch_id":None,"revision":0}
                session.execute(text("INSERT INTO storylines(id,payload) VALUES (:id,CAST(:v AS jsonb))"),{"id":storyline_id,"v":json.dumps(sl)})
                session.execute(text("INSERT INTO storyline_branches(id,payload,revision) VALUES (:id,CAST(:v AS jsonb),0)"),{"id":branch_id,"v":json.dumps(br)})
                session.execute(text("INSERT INTO authorization_audit_events(id,payload) VALUES (:id,CAST(:v AS jsonb))"),{"id":event["id"],"v":json.dumps(event)})
            return {"id":project_id,"title":title,"genre":genre}
        root=self.novels.backend.data;novel_root=self.novels.backend.novels/project_id;paths=[self.scopes.path,self.authorization.path]
        before={p:(p.read_bytes() if p.exists() else None) for p in paths}
        try:
            created=self.novels.create({"id":project_id,"title":title,"genre":genre});self.scopes.link_project(project_id,workspace_id)
            self.scopes.create("storylines",{"id":storyline_id,"workspace_id":workspace_id,"project_id":project_id,"name":"Default Storyline","description":""})
            self.scopes.create("branches",{"id":branch_id,"workspace_id":workspace_id,"project_id":project_id,"storyline_id":storyline_id,"name":"main","parent_branch_id":None,"revision":0});self.audit.append(event);return created
        except Exception:
            if novel_root.exists():shutil.rmtree(novel_root)
            for p,v in before.items(): p.unlink(missing_ok=True) if v is None else atomic_write(p,v.decode("utf-8"))
            raise

    def _create_scope_item(self, kind, item, actor, scope):
        action="STORYLINE_CREATED" if kind=="storylines" else "BRANCH_CREATED";target=action.split("_")[0].title();event=self._event(actor,action,target,item["id"],scope)
        if self.postgres:
            table="storylines" if kind=="storylines" else "storyline_branches"
            with self.novels.database.session() as session:
                if kind=="storylines":session.execute(text("INSERT INTO storylines(id,payload) VALUES (:id,CAST(:v AS jsonb))"),{"id":item["id"],"v":json.dumps(item)})
                else:session.execute(text("INSERT INTO storyline_branches(id,payload,revision) VALUES (:id,CAST(:v AS jsonb),0)"),{"id":item["id"],"v":json.dumps(item)})
                session.execute(text("INSERT INTO authorization_audit_events(id,payload) VALUES (:id,CAST(:v AS jsonb))"),{"id":event["id"],"v":json.dumps(event)})
            return item
        before={p:(p.read_bytes() if p.exists() else None) for p in (self.scopes.path,self.authorization.path)}
        try:self.scopes.create(kind,item);self.audit.append(event);return item
        except Exception:
            for p,v in before.items():p.unlink(missing_ok=True) if v is None else atomic_write(p,v.decode("utf-8"))
            raise

    def create_storyline(self,w,p,name,actor):
        from ..authorization import AuthorizationScope,ScopeKind
        if self.scopes.project_workspace(p)!=w:raise KeyError(p)
        item={"id":str(uuid4()),"workspace_id":w,"project_id":p,"name":name,"description":""}
        return self._create_scope_item("storylines",item,actor,AuthorizationScope(ScopeKind.PROJECT,w,p))

    def create_branch(self,w,p,s,name,actor):
        from ..authorization import AuthorizationScope,ScopeKind
        story=self.scopes.get("storylines",s)
        if story["workspace_id"]!=w or story["project_id"]!=p:raise KeyError(s)
        item={"id":str(uuid4()),"workspace_id":w,"project_id":p,"storyline_id":s,"name":name,"parent_branch_id":None,"revision":0}
        return self._create_scope_item("branches",item,actor,AuthorizationScope(ScopeKind.STORYLINE,w,p,s))
