from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from .models import ChapterModel, NovelModel

EXTERNAL_ID_NAMESPACE = uuid.UUID("a791395c-dc48-4f63-a6a5-bdb1a719f2b4")


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def external_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return uuid.uuid5(EXTERNAL_ID_NAMESPACE, str(value))


def novel_or_raise(session, slug: str) -> NovelModel:
    model = session.scalar(select(NovelModel).where(NovelModel.slug == slug))
    if model is None:
        raise FileNotFoundError(slug)
    return model


def split_chapter_id(chapter_id: str) -> tuple[str, int]:
    try:
        slug, number = chapter_id.rsplit(":", 1)
        return slug, int(number)
    except (ValueError, AttributeError) as exc:
        raise FileNotFoundError(chapter_id) from exc


def chapter_or_raise(session, chapter_id: str) -> tuple[NovelModel, ChapterModel]:
    slug, number = split_chapter_id(chapter_id)
    novel = novel_or_raise(session, slug)
    chapter = session.scalar(select(ChapterModel).where(
        ChapterModel.novel_id == novel.id,
        ChapterModel.chapter_number == number,
    ))
    if chapter is None:
        raise FileNotFoundError(chapter_id)
    return novel, chapter
