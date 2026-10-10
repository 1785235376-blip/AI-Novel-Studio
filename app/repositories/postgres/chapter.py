from __future__ import annotations
from ...runtime_events import committed_change

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from ...document import duplicate_document, document_to_markdown, markdown_to_document
from ..chapter_repository import VersionConflict
from .common import chapter_external_id, chapter_or_raise, iso, lock_chapter_namespace, novel_or_raise, require_chapter_identity, split_chapter_id
from .models import ChapterIdentityModel, ChapterModel, ChapterSummaryModel, DocumentVersionModel


class PostgresChapterRepository:
    def __init__(self, database): self.database = database

    @staticmethod
    def _external(novel, chapter):
        document = chapter.document or markdown_to_document("")
        content = document_to_markdown(document)
        return {"id": chapter_external_id(novel, chapter), "novel_id": novel.slug,
                "number": chapter.chapter_number, "volume": 1, "title": chapter.title or f"Chapter {chapter.chapter_number}",
                "word_count": len("".join(content.split())), "status": chapter.workflow_status.title(),
                "content": content, "version": chapter.version, "document": document,
                "is_archived": bool(chapter.is_archived),
                "updated_at": iso(chapter.updated_at)}

    def list(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            rows = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id, ChapterModel.is_archived.is_(False)).order_by(func.coalesce(ChapterModel.sort_order, ChapterModel.chapter_number), ChapterModel.chapter_number)).all()
            for row in rows:
                require_chapter_identity(row)
            return [self._external(novel, row) for row in rows]

    def list_archived(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            rows = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id, ChapterModel.is_archived.is_(True)).order_by(func.coalesce(ChapterModel.sort_order, ChapterModel.chapter_number), ChapterModel.chapter_number)).all()
            for row in rows:
                require_chapter_identity(row)
            return [self._external(novel, row) for row in rows]

    @committed_change("CHAPTER")
    def _set_archived(self, chapter_id, archived, expected_version=None):
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            if expected_version is not None and chapter.version != expected_version:
                raise VersionConflict(self._external(novel, chapter), resource_id=chapter_id, expected_version=expected_version)
            if chapter.is_archived != archived:
                chapter.is_archived = archived
                chapter.version += 1
                chapter.updated_at = datetime.now(timezone.utc)
            session.flush(); session.refresh(chapter)
            return self._external(novel, chapter)

    def archive(self, chapter_id, expected_version=None): return self._set_archived(chapter_id, True, expected_version)
    def restore_archive(self, chapter_id, expected_version=None): return self._set_archived(chapter_id, False, expected_version)

    def _create_in_session(self, session, novel_id, payload):
        novel = lock_chapter_namespace(session, novel_id)
        allocated = session.scalar(select(func.max(ChapterIdentityModel.chapter_number)).where(ChapterIdentityModel.novel_id == novel.id)) or 0
        existing = session.scalar(select(func.max(ChapterModel.chapter_number)).where(ChapterModel.novel_id == novel.id)) or 0
        number = payload.get("number")
        number = max(allocated, existing) + 1 if number is None else number
        if type(number) is not int or number <= 0:
            raise ValueError("chapter number must be a positive integer")
        if (session.get(ChapterIdentityModel, (novel.id, number)) is not None
                or session.scalar(select(ChapterModel.id).where(ChapterModel.novel_id == novel.id, ChapterModel.chapter_number == number))):
            raise FileExistsError(f"{novel_id}:{number}")
        position = (session.scalar(select(func.max(func.coalesce(ChapterModel.sort_order, ChapterModel.chapter_number))).where(ChapterModel.novel_id == novel.id)) or 0) + 1
        title = payload.get("title", f"Chapter {number}")
        markdown = f"# {title}\n\n{payload.get('content', '')}"
        model = ChapterModel(id=uuid.uuid4(), novel_id=novel.id, chapter_number=number,
                             sort_order=position, identity_status="ACTIVE", title=title,
                             markdown_path=f"chapters/chapter-{number:04d}.md",
                             content_hash=hashlib.sha256(markdown.encode()).hexdigest(),
                             document=markdown_to_document(markdown), version=1)
        if novel.chapter_identity_provenance != "ALLOCATED":
            model.public_token = "~" + str(model.id)
        if (session.get(ChapterModel,model.id) is not None
                or session.scalar(select(ChapterIdentityModel.chapter_number).where(ChapterIdentityModel.chapter_id == model.id)) is not None
                or (model.public_token and session.scalar(select(ChapterIdentityModel.chapter_number).where(
                    ChapterIdentityModel.novel_id == novel.id, ChapterIdentityModel.public_token == model.public_token)) is not None)):
            raise FileExistsError(chapter_external_id(novel,model))
        session.add(model)
        session.add(ChapterIdentityModel(novel_id=novel.id, chapter_number=number,
                                        chapter_id=model.id, public_token=model.public_token, state="ACTIVE", provenance="ALLOCATED"))
        session.flush()
        return novel, model

    @committed_change("CHAPTER")
    def create(self, novel_id, payload):
        with self.database.session() as session:
            novel, model = self._create_in_session(session, novel_id, payload)
            return self._external(novel, model)

    def get(self, chapter_id):
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            return self._external(novel, chapter)

    @committed_change("CHAPTER")
    def save(self, chapter_id, document, expected_version, source="USER", operator="local-user", create_revision=True):
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            old_document = chapter.document or markdown_to_document("")
            old_updated_at = chapter.updated_at
            from ...revision_constraints import preserve_revision_constraints
            document = preserve_revision_constraints(old_document, document, source)
            markdown = document_to_markdown(document)
            title = chapter.title
            if document.get("content") and document["content"][0].get("type") == "heading":
                title = "".join(x.get("text", "") for x in document["content"][0].get("content", []))
            result = session.execute(
                update(ChapterModel).where(
                    ChapterModel.id == chapter.id,
                    ChapterModel.version == expected_version,
                ).values(
                    document=document,
                    version=expected_version + 1,
                    updated_at=datetime.now(timezone.utc),
                    content_hash=hashlib.sha256(markdown.encode()).hexdigest(),
                    title=title,
                ).execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.expire_all()
                actual = session.scalar(select(ChapterModel).where(ChapterModel.id == chapter.id))
                if actual is None:
                    raise FileNotFoundError(chapter_id)
                raise VersionConflict(self._external(novel, actual), resource_id=chapter_id,
                                      expected_version=expected_version)
            if create_revision:
                reason=source if source in {"MANUAL_SAVE","AI_ACCEPT","RESTORE","CHAPTER_SWITCH","EXPLICIT_CHECKPOINT"} else "MANUAL_SAVE"
                session.add(DocumentVersionModel(chapter_id=chapter.id, version=expected_version,
                                                 document=old_document, created_at=old_updated_at,
                                                 operator=operator, source=source,reason=reason))
            session.flush()
            session.refresh(chapter)
            return self._external(novel, chapter)

    @committed_change("CHAPTER")
    def delete(self, chapter_id):
        with self.database.session() as session:
            slug, _ = split_chapter_id(chapter_id)
            novel = lock_chapter_namespace(session, slug)
            _, chapter = chapter_or_raise(session, chapter_id)
            number = chapter.chapter_number
            reservation = session.get(ChapterIdentityModel, (novel.id, number))
            if reservation is None:
                reservation = ChapterIdentityModel(novel_id=novel.id, chapter_number=number,
                                                   chapter_id=chapter.id, public_token=chapter.public_token, provenance="LEGACY_UNKNOWN")
                session.add(reservation)
            reservation.state = "DELETED"
            session.delete(chapter)

    def duplicate(self, chapter_id):
        current = self.get(chapter_id)
        created = self.create(current["novel_id"], {"title": current["title"] + " Copy", "content": ""})
        with self.database.session() as session:
            _, old = chapter_or_raise(session, chapter_id); novel, new = chapter_or_raise(session, created["id"])
            new.document = duplicate_document(current["document"], new.title)
            new.content_hash = hashlib.sha256(document_to_markdown(new.document).encode()).hexdigest()
            latest = session.scalar(select(ChapterSummaryModel).where(ChapterSummaryModel.chapter_id == old.id).order_by(ChapterSummaryModel.created_at.desc()))
            if latest: session.add(ChapterSummaryModel(chapter_id=new.id, summary=latest.summary, structured_summary=dict(latest.structured_summary or {})))
            session.flush(); return self._external(novel, new)

    def rename(self, chapter_id, title, expected_version):
        current = self.get(chapter_id); doc = dict(current["document"]); nodes = list(doc.get("content", []))
        heading = {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]}
        if nodes and nodes[0].get("type") == "heading": nodes[0] = heading
        else: nodes.insert(0, heading)
        doc["content"] = nodes
        return self.save(chapter_id, doc, expected_version, "USER")

    def move(self, chapter_id, direction):
        slug, _ = split_chapter_id(chapter_id)
        with self.database.session() as session:
            # Serialize reorder/create/delete, while document CAS remains on
            # the immutable UUID and can proceed concurrently with a move.
            novel = lock_chapter_namespace(session, slug)
            _, chapter = chapter_or_raise(session, chapter_id)
            order = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id).order_by(func.coalesce(ChapterModel.sort_order, ChapterModel.chapter_number), ChapterModel.chapter_number)).all()
            for item in order:
                require_chapter_identity(item)
            index = order.index(chapter); target_index = index + (-1 if direction == "up" else 1)
            if 0 <= target_index < len(order):
                order[index], order[target_index] = order[target_index], order[index]
                for position, item in enumerate(order, 1):
                    item.sort_order = position
            session.flush()
            return [chapter_external_id(novel,item) for item in order]

    def history(self, chapter_id):
        with self.database.session() as session:
            _, chapter = chapter_or_raise(session, chapter_id)
            rows = session.scalars(select(DocumentVersionModel).where(DocumentVersionModel.chapter_id == chapter.id).order_by(DocumentVersionModel.version.desc())).all()
            return [{"version": x.version, "document": x.document, "timestamp": iso(x.created_at),
                     "source": x.source, "operator": x.operator, "reason": x.reason,
                     "actor_id": x.actor_id, "session_id": x.session_id,
                     "scope_type": x.scope_type, "scope_id": x.scope_id,
                     "metadata": x.metadata_ or {}} for x in rows]

    def restore(self, chapter_id, version, expected_version):
        with self.database.session() as session:
            _, chapter = chapter_or_raise(session, chapter_id)
            item = session.scalar(select(DocumentVersionModel).where(DocumentVersionModel.chapter_id == chapter.id, DocumentVersionModel.version == version))
            if item is None: raise FileNotFoundError(version)
            document = dict(item.document)
        return self.save(chapter_id, document, expected_version, "RESTORE")

    def save_summary(self, novel_id, chapter_ref, summary):
        chapter_id = chapter_ref if isinstance(chapter_ref,str) and ":" in chapter_ref else f"{novel_id}:{chapter_ref}"
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            if novel.slug != novel_id:
                raise FileNotFoundError(chapter_id)
            chapter_number=chapter.chapter_number
            old = session.scalars(select(ChapterSummaryModel).where(ChapterSummaryModel.chapter_id == chapter.id)).all()
            for item in old: session.delete(item)
            session.add(ChapterSummaryModel(chapter_id=chapter.id, summary=summary, structured_summary={}))
            return {"chapter": chapter_number, "summary": summary, **({"chapter_id":chapter_id} if chapter.public_token else {})}
