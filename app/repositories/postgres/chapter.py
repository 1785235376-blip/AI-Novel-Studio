from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from ...document import document_to_markdown, markdown_to_document
from ..chapter_repository import VersionConflict
from .common import chapter_or_raise, iso, novel_or_raise, split_chapter_id
from .models import ChapterModel, ChapterSummaryModel, DocumentVersionModel


class PostgresChapterRepository:
    def __init__(self, database): self.database = database

    @staticmethod
    def _external(novel, chapter):
        document = chapter.document or markdown_to_document("")
        content = document_to_markdown(document)
        return {"id": f"{novel.slug}:{chapter.chapter_number}", "novel_id": novel.slug,
                "number": chapter.chapter_number, "volume": 1, "title": chapter.title or f"Chapter {chapter.chapter_number}",
                "word_count": len("".join(content.split())), "status": chapter.workflow_status.title(),
                "content": content, "version": chapter.version, "document": document,
                "is_archived": bool(chapter.is_archived),
                "updated_at": iso(chapter.updated_at)}

    def list(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            rows = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id, ChapterModel.is_archived.is_(False)).order_by(ChapterModel.chapter_number)).all()
            return [self._external(novel, row) for row in rows]

    def list_archived(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            rows = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id, ChapterModel.is_archived.is_(True)).order_by(ChapterModel.chapter_number)).all()
            return [self._external(novel, row) for row in rows]

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

    def create(self, novel_id, payload):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            number = payload.get("number") or (session.scalar(select(func.max(ChapterModel.chapter_number)).where(ChapterModel.novel_id == novel.id)) or 0) + 1
            if session.scalar(select(ChapterModel.id).where(ChapterModel.novel_id == novel.id, ChapterModel.chapter_number == number)):
                raise FileExistsError(f"{novel_id}:{number}")
            title = payload.get("title", f"Chapter {number}")
            markdown = f"# {title}\n\n{payload.get('content', '')}"
            model = ChapterModel(novel_id=novel.id, chapter_number=number, title=title,
                                 markdown_path=f"chapters/chapter-{number:04d}.md",
                                 content_hash=hashlib.sha256(markdown.encode()).hexdigest(),
                                 document=markdown_to_document(markdown), version=1)
            session.add(model); session.flush(); return self._external(novel, model)

    def get(self, chapter_id):
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            return self._external(novel, chapter)

    def save(self, chapter_id, document, expected_version, source="USER", operator="local-user", create_revision=True):
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            old_document = chapter.document or markdown_to_document("")
            old_updated_at = chapter.updated_at
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

    def delete(self, chapter_id):
        with self.database.session() as session:
            _, chapter = chapter_or_raise(session, chapter_id); session.delete(chapter)

    def duplicate(self, chapter_id):
        current = self.get(chapter_id)
        created = self.create(current["novel_id"], {"title": current["title"] + " Copy", "content": ""})
        with self.database.session() as session:
            _, old = chapter_or_raise(session, chapter_id); novel, new = chapter_or_raise(session, created["id"])
            new.document = current["document"]
            nodes = list((new.document or {}).get("content", []))
            if nodes and nodes[0].get("type") == "heading":
                nodes[0] = {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": new.title}]}
                new.document = {**new.document, "content": nodes}
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
        slug, number = split_chapter_id(chapter_id)
        with self.database.session() as session:
            novel, chapter = chapter_or_raise(session, chapter_id)
            order = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id).order_by(ChapterModel.chapter_number)).all()
            index = order.index(chapter); target_index = index + (-1 if direction == "up" else 1)
            if 0 <= target_index < len(order):
                other = order[target_index]; original, target = chapter.chapter_number, other.chapter_number
                chapter.chapter_number = -1; session.flush(); other.chapter_number = original; session.flush(); chapter.chapter_number = target
                order[index], order[target_index] = order[target_index], order[index]
            session.flush(); return [f"{slug}:{item.chapter_number}" for item in order]

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

    def save_summary(self, novel_id, chapter_number, summary):
        chapter_id = f"{novel_id}:{chapter_number}"
        with self.database.session() as session:
            _, chapter = chapter_or_raise(session, chapter_id)
            old = session.scalars(select(ChapterSummaryModel).where(ChapterSummaryModel.chapter_id == chapter.id)).all()
            for item in old: session.delete(item)
            session.add(ChapterSummaryModel(chapter_id=chapter.id, summary=summary, structured_summary={}))
            return {"chapter": chapter_number, "summary": summary}
