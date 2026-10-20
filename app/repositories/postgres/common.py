from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from .models import ChapterIdentityModel, ChapterModel, NovelModel
from ...chapter_identity import canonical_token, ChapterIdentityConflict

EXTERNAL_ID_NAMESPACE = uuid.UUID("a791395c-dc48-4f63-a6a5-bdb1a719f2b4")


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def external_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return uuid.uuid5(EXTERNAL_ID_NAMESPACE, str(value))


def novel_or_raise(session, slug: str, for_update: bool = False) -> NovelModel:
    statement = select(NovelModel).where(NovelModel.slug == slug)
    model = session.scalar(statement.with_for_update() if for_update else statement)
    if model is None:
        raise FileNotFoundError(slug)
    return model


def split_chapter_id(chapter_id: str) -> tuple[str, int | str]:
    try:
        slug, token = chapter_id.rsplit(":", 1)
        if not slug:
            raise ValueError("invalid chapter identity")
        token = canonical_token(token)
        return slug, token if token.startswith("~") else int(token)
    except (ValueError, AttributeError) as exc:
        raise FileNotFoundError(chapter_id) from exc


def chapter_external_id(novel, chapter) -> str:
    return f"{novel.slug}:{getattr(chapter, 'public_token', None) or chapter.chapter_number}"


def chapter_or_raise(session, chapter_id: str) -> tuple[NovelModel, ChapterModel]:
    slug, token = split_chapter_id(chapter_id)
    novel = novel_or_raise(session, slug)
    query = select(ChapterModel).where(ChapterModel.novel_id == novel.id)
    if isinstance(token, int):
        query = query.where(ChapterModel.chapter_number == token, ChapterModel.public_token.is_(None))
    else:
        query = query.where(ChapterModel.public_token == token)
    chapter = session.scalar(query)
    if chapter is None:
        raise FileNotFoundError(chapter_id)
    require_chapter_identity(chapter)
    reservation = session.get(ChapterIdentityModel, (novel.id, chapter.chapter_number))
    if reservation is not None and (reservation.state != "ACTIVE" or reservation.chapter_id != chapter.id or reservation.public_token != chapter.public_token):
        raise ChapterIdentityConflict(f"CHAPTER_IDENTITY_AMBIGUOUS: {chapter_id}")
    return novel, chapter


def require_chapter_identity(chapter):
    if chapter is None:
        raise FileNotFoundError("chapter")
    if chapter.identity_status != "ACTIVE":
        raise ChapterIdentityConflict("CHAPTER_IDENTITY_AMBIGUOUS")


def lock_chapter_namespace(session, novel_id):
    novel = session.scalar(select(NovelModel).where(NovelModel.slug == novel_id).with_for_update())
    if novel is None:
        raise FileNotFoundError(novel_id)
    return novel
