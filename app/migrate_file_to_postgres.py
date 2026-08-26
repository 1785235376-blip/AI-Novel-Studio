from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .document import markdown_to_document
from .repository import FileRepository, read_json
from .repositories.postgres.common import external_uuid
from .repositories.postgres.models import (
    CanonModel, ChapterModel, ChapterSummaryModel, CharacterModel,
    DocumentVersionModel, ForeshadowingModel, GenerationJobModel,
    LocationModel, NovelModel, PendingCanonModel, SecretModel,
    StoryStateModel, TimelineModel,
)
from .repositories.postgres.session import Database


TIMELINE_NAMESPACE = uuid.UUID("e526b376-2842-5b54-8fcd-9a127137bbbf")
SECRET_NAMESPACE = uuid.UUID("680e0df9-1fce-59ba-9329-240bc4ff9225")
FORESHADOWING_NAMESPACE = uuid.UUID("8ae4cfd0-e99e-530c-9f69-6a800900bf87")
ACTIONS = ("imported", "updated", "skipped", "conflicts", "failed")


def stable_source_uuid(namespace: uuid.UUID, novel_id: str, source_id: str) -> uuid.UUID:
    return uuid.uuid5(namespace, f"{novel_id}:{source_id}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_json_compare(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def _new_report() -> dict:
    return {**{action: [] for action in ACTIONS}, "summary": {}, "timestamp": datetime.now(timezone.utc).isoformat()}


def _record(report: dict, action: str, table: str, source_id: str, target_id: Any = None, reason: str = "") -> None:
    item = {"table": table, "source_id": str(source_id), "target_id": str(target_id) if target_id is not None else None, "reason": reason}
    report[action].append(item)


def _finalize(report: dict) -> None:
    tables = sorted({item["table"] for action in ACTIONS for item in report[action]})
    report["summary"] = {
        table: {action: sum(1 for item in report[action] if item["table"] == table) for action in ACTIONS}
        for table in tables
    }


def _privacy(item: dict, default: str = "CLOUD_ALLOWED") -> str:
    return str(item.get("privacy_level", default))


def _sync_novel(session, repo: FileRepository, source: dict, report: dict) -> NovelModel:
    novel_id = source["id"]
    root = repo.novels / novel_id
    file_meta = repo.get_novel(novel_id)
    style_profile = read_json(root / "style/profile.json", {})
    secrets = read_json(root / "secrets.json", [])
    secret_mapping = {
        str(stable_source_uuid(SECRET_NAMESPACE, novel_id, str(item["id"]))): {"id": str(item["id"]), "order": order}
        for order, item in enumerate(secrets) if item.get("id") is not None
    }
    desired_metadata = {key: value for key, value in file_meta.items() if key not in {"id", "title", "created_at", "updated_at"}}
    desired_metadata["style_profile"] = style_profile
    model = session.scalar(select(NovelModel).where(NovelModel.slug == novel_id))
    if model is None:
        desired_metadata["context_source_ids"] = {"secrets": secret_mapping}
        model = NovelModel(slug=novel_id, title=file_meta.get("title", novel_id), metadata_json=desired_metadata)
        session.add(model); session.flush()
        _record(report, "imported", "novels", novel_id, model.id, "novel and context metadata created")
        return model
    merged = dict(model.metadata_json or {})
    before = dict(merged)
    merged.update(desired_metadata)
    context_ids = dict(merged.get("context_source_ids", {}))
    context_ids["secrets"] = secret_mapping
    merged["context_source_ids"] = context_ids
    changed = model.title != file_meta.get("title", novel_id) or not canonical_json_compare(before, merged)
    if changed:
        model.title = file_meta.get("title", novel_id); model.metadata_json = merged; model.updated_at = datetime.now(timezone.utc)
        _record(report, "updated", "novels", novel_id, model.id, "metadata/style/secret mapping synchronized")
    else:
        _record(report, "skipped", "novels", novel_id, model.id, "unchanged")
    return model


def _sync_locations(session, root: Path, novel: NovelModel, report: dict) -> dict[str, LocationModel]:
    output = {}
    for order, item in enumerate(read_json(root / "locations/locations.json", [])):
        source_id = str(item.get("id", ""))
        if not source_id:
            _record(report, "conflicts", "locations", f"index:{order}", reason="source id is missing"); continue
        facts = {key: value for key, value in item.items() if key not in {"id", "name", "privacy_level"}}
        facts["_source_order"] = order
        model = session.scalar(select(LocationModel).where(LocationModel.novel_id == novel.id, LocationModel.slug == source_id))
        values = (str(item.get("name", source_id)), facts, _privacy(item))
        if model is None:
            model = LocationModel(novel_id=novel.id, slug=source_id, name=values[0], facts=values[1], privacy=values[2]); session.add(model); session.flush()
            _record(report, "imported", "locations", source_id, model.id, "created")
        elif model.name != values[0] or not canonical_json_compare(model.facts, values[1]) or model.privacy != values[2]:
            model.name, model.facts, model.privacy = values; _record(report, "updated", "locations", source_id, model.id, "content changed")
        else: _record(report, "skipped", "locations", source_id, model.id, "unchanged")
        output[source_id] = model
    return output


def _sync_characters(session, root: Path, novel: NovelModel, locations: dict[str, LocationModel], report: dict) -> None:
    reserved = {"id", "name", "age", "status", "life_status", "privacy_level", "current_location", "current_location_id"}
    for order, item in enumerate(read_json(root / "characters/characters.json", [])):
        source_id = str(item.get("id", ""))
        if not source_id:
            _record(report, "conflicts", "characters", f"index:{order}", reason="source id is missing"); continue
        location_slug = item.get("current_location") or item.get("current_location_id")
        if location_slug and str(location_slug) not in locations:
            _record(report, "conflicts", "characters", source_id, reason=f"location {location_slug!r} was not resolved"); continue
        facts = {key: value for key, value in item.items() if key not in reserved}; facts["_source_order"] = order
        location_id = locations[str(location_slug)].id if location_slug else None
        expected = {"name": str(item.get("name", source_id)), "age": item.get("age"), "life_status": str(item.get("status", item.get("life_status", "ALIVE"))), "current_location_id": location_id, "facts": facts, "privacy": _privacy(item)}
        model = session.scalar(select(CharacterModel).where(CharacterModel.novel_id == novel.id, CharacterModel.slug == source_id))
        if model is None:
            model = CharacterModel(novel_id=novel.id, slug=source_id, **expected); session.add(model); session.flush(); _record(report, "imported", "characters", source_id, model.id, "created")
        elif any((canonical_json_compare(getattr(model, key), value) is False) for key, value in expected.items()):
            for key, value in expected.items(): setattr(model, key, value)
            _record(report, "updated", "characters", source_id, model.id, "content changed")
        else: _record(report, "skipped", "characters", source_id, model.id, "unchanged")


def _sync_timeline(session, root: Path, novel: NovelModel, locations: dict[str, LocationModel], report: dict) -> None:
    reserved = {"id", "sequence", "time", "event_time", "title", "privacy_level", "location", "location_id"}
    for order, item in enumerate(read_json(root / "timeline/events.json", [])):
        source_id = str(item.get("id", f"index-{order}")); target_id = stable_source_uuid(TIMELINE_NAMESPACE, novel.slug, source_id)
        location_slug = item.get("location") or item.get("location_id")
        if location_slug and str(location_slug) not in locations:
            _record(report, "conflicts", "timeline_events", source_id, target_id, f"location {location_slug!r} was not resolved"); continue
        details = {key: value for key, value in item.items() if key not in reserved}; details.update({"_source_id": source_id, "_source_order": order})
        if "privacy_level" in item: details["privacy_level"] = item["privacy_level"]
        expected = {"novel_id": novel.id, "event_time": str(item.get("time", item.get("event_time", ""))), "sequence": int(item.get("sequence", order)), "location_id": locations[str(location_slug)].id if location_slug else None, "title": str(item.get("title", source_id)), "details": details, "privacy": _privacy(item)}
        model = session.get(TimelineModel, target_id)
        if model is None:
            model = TimelineModel(id=target_id, **expected); session.add(model); _record(report, "imported", "timeline_events", source_id, target_id, "created")
        elif any(not canonical_json_compare(getattr(model, key), value) for key, value in expected.items()):
            for key, value in expected.items(): setattr(model, key, value)
            _record(report, "updated", "timeline_events", source_id, target_id, "content changed")
        else: _record(report, "skipped", "timeline_events", source_id, target_id, "unchanged")


def _sync_secrets(session, root: Path, novel: NovelModel, report: dict) -> None:
    mapping = dict((novel.metadata_json or {}).get("context_source_ids", {}).get("secrets", {}))
    for order, item in enumerate(read_json(root / "secrets.json", [])):
        source_id = str(item.get("id", f"index-{order}")); target_id = stable_source_uuid(SECRET_NAMESPACE, novel.slug, source_id)
        expected_mapping = {"id": source_id, "order": order}
        if not canonical_json_compare(mapping.get(str(target_id)), expected_mapping):
            _record(report, "conflicts", "secrets", source_id, target_id, "novel metadata mapping is inconsistent"); continue
        expected = {"novel_id": novel.id, "title": str(item.get("title", source_id)), "content": str(item.get("content", "")), "earliest_reveal_chapter": int(item.get("earliest_reveal_chapter", 0)), "status": str(item.get("status", "ACTIVE")), "privacy": _privacy(item, "LOCAL_ONLY")}
        model = session.get(SecretModel, target_id)
        if model is None:
            model = SecretModel(id=target_id, **expected); session.add(model); _record(report, "imported", "secrets", source_id, target_id, "created")
        elif any(not canonical_json_compare(getattr(model, key), value) for key, value in expected.items()):
            for key, value in expected.items(): setattr(model, key, value)
            _record(report, "updated", "secrets", source_id, target_id, "content changed")
        else: _record(report, "skipped", "secrets", source_id, target_id, "unchanged")


def _sync_foreshadowing(session, root: Path, novel: NovelModel, report: dict) -> None:
    reserved = {"id", "title", "status", "planted_chapter", "target_chapter"}
    for order, item in enumerate(read_json(root / "foreshadowing.json", [])):
        source_id = str(item.get("id", f"index-{order}")); target_id = stable_source_uuid(FORESHADOWING_NAMESPACE, novel.slug, source_id)
        details = {key: value for key, value in item.items() if key not in reserved}; details.update({"_source_id": source_id, "_source_order": order})
        expected = {"novel_id": novel.id, "title": str(item.get("title", source_id)), "planted_chapter": item.get("planted_chapter"), "target_chapter": item.get("target_chapter"), "status": str(item.get("status", "OPEN")), "details": details}
        model = session.get(ForeshadowingModel, target_id)
        if model is None:
            model = ForeshadowingModel(id=target_id, **expected); session.add(model); _record(report, "imported", "foreshadowing", source_id, target_id, "created")
        elif any(not canonical_json_compare(getattr(model, key), value) for key, value in expected.items()):
            for key, value in expected.items(): setattr(model, key, value)
            _record(report, "updated", "foreshadowing", source_id, target_id, "content changed")
        else: _record(report, "skipped", "foreshadowing", source_id, target_id, "unchanged")


def _sync_story_state(session, root: Path, novel: NovelModel, report: dict) -> None:
    state = read_json(root / "story_state.json", {})
    if not state:
        _record(report, "skipped", "story_states", novel.slug, reason="source is empty"); return
    chapter_number = int(state.get("chapter", 0)); source_id = f"{novel.slug}:{chapter_number}"
    model = session.scalar(select(StoryStateModel).where(StoryStateModel.novel_id == novel.id, StoryStateModel.chapter_number == chapter_number))
    if model is None:
        model = StoryStateModel(novel_id=novel.id, chapter_number=chapter_number, state=state); session.add(model); session.flush(); _record(report, "imported", "story_states", source_id, model.id, "created")
    elif not canonical_json_compare(model.state, state):
        model.state = state; _record(report, "updated", "story_states", source_id, model.id, "state changed")
    else: _record(report, "skipped", "story_states", source_id, model.id, "unchanged")


def _sync_chapters(session, repo: FileRepository, root: Path, novel: NovelModel, report: dict) -> None:
    summaries = {int(item["chapter"]): item for item in read_json(root / "summaries/index.json", []) if item.get("chapter") is not None}
    for item in repo.list_chapters(novel.slug):
        number = int(item["number"]); source_id = item["id"]
        package = read_json(root / "documents" / f"chapter-{number:04d}.json", {})
        document = package.get("document") or markdown_to_document(item["content"]); file_version = int(package.get("version", 1))
        chapter = session.scalar(select(ChapterModel).where(ChapterModel.novel_id == novel.id, ChapterModel.chapter_number == number))
        if chapter is None:
            chapter = ChapterModel(novel_id=novel.id, chapter_number=number, title=item["title"], markdown_path=f"chapters/chapter-{number:04d}.md", content_hash=hashlib.sha256(item["content"].encode()).hexdigest(), document=document, version=file_version); session.add(chapter); session.flush(); _record(report, "imported", "chapters", source_id, chapter.id, "created")
        elif chapter.version > file_version:
            _record(report, "conflicts", "chapters", source_id, chapter.id, "PostgreSQL version is newer")
        elif chapter.version == file_version and not canonical_json_compare(chapter.document, document):
            _record(report, "conflicts", "chapters", source_id, chapter.id, "same version has different document")
        elif chapter.version < file_version:
            chapter.document, chapter.version, chapter.title = document, file_version, item["title"]; _record(report, "updated", "chapters", source_id, chapter.id, "File version is newer")
        else: _record(report, "skipped", "chapters", source_id, chapter.id, "unchanged")
        for history_path in sorted((root / "history" / f"chapter-{number:04d}").glob("v*.json")):
            history = read_json(history_path, {}); version = int(history["version"]); history_id = f"{source_id}:v{version}"
            existing = session.scalar(select(DocumentVersionModel).where(DocumentVersionModel.chapter_id == chapter.id, DocumentVersionModel.version == version))
            if existing is None:
                session.add(DocumentVersionModel(chapter_id=chapter.id, version=version, document=history["document"], operator=history.get("operator", "migration"), source=history.get("source", "MIGRATED"))); _record(report, "imported", "chapter_versions", history_id, reason="created")
            elif canonical_json_compare(existing.document, history["document"]): _record(report, "skipped", "chapter_versions", history_id, existing.id, "unchanged")
            else: _record(report, "conflicts", "chapter_versions", history_id, existing.id, "same version has different document")
        summary = summaries.get(number)
        if summary:
            existing_summaries = session.scalars(select(ChapterSummaryModel).where(ChapterSummaryModel.chapter_id == chapter.id).order_by(ChapterSummaryModel.created_at)).all()
            target = existing_summaries[-1] if existing_summaries else None; text = str(summary.get("summary", "")); summary_id = f"{novel.slug}:{number}"
            if target is None:
                target = ChapterSummaryModel(chapter_id=chapter.id, summary=text, structured_summary=summary.get("structured_summary", {})); session.add(target); session.flush(); _record(report, "imported", "chapter_summaries", summary_id, target.id, "created")
            elif target.summary != text:
                target.summary = text
                if "structured_summary" in summary: target.structured_summary = summary["structured_summary"]
                _record(report, "updated", "chapter_summaries", summary_id, target.id, "content changed")
            else: _record(report, "skipped", "chapter_summaries", summary_id, target.id, "unchanged")


def _sync_canon_pending(session, root: Path, novel: NovelModel, report: dict) -> None:
    for index, item in enumerate(read_json(root / "canon.json", [])):
        source_id = str(item.get("id") or f"{novel.slug}:canon:{index}"); target_id = external_uuid(source_id)
        expected = {"fact_value": item, "source": str(item.get("source", "MIGRATED")), "privacy": _privacy(item)}; model = session.get(CanonModel, target_id)
        if model is None:
            model = CanonModel(id=target_id, novel_id=novel.id, entity_type=str(item.get("entity_type", "story")), entity_id=None, fact_key=str(item.get("fact_key") or source_id), **expected); session.add(model); _record(report, "imported", "canon_entries", source_id, target_id, "created")
        elif any(not canonical_json_compare(getattr(model, key), value) for key, value in expected.items()):
            for key, value in expected.items(): setattr(model, key, value)
            _record(report, "updated", "canon_entries", source_id, target_id, "content changed")
        else: _record(report, "skipped", "canon_entries", source_id, target_id, "unchanged")
    for path in (root / "pending_canon").glob("*.json"):
        item = read_json(path, {}); source_id = str(item.get("id", path.stem)); target_id = external_uuid(source_id); model = session.get(PendingCanonModel, target_id)
        if model is None:
            model = PendingCanonModel(id=target_id, novel_id=novel.id, proposal=item, status=item.get("status", "PENDING")); session.add(model); _record(report, "imported", "pending_canon", source_id, target_id, "created")
        elif not canonical_json_compare(model.proposal, item) or model.status != item.get("status", "PENDING"):
            model.proposal, model.status = item, item.get("status", "PENDING"); _record(report, "updated", "pending_canon", source_id, target_id, "content changed")
        else: _record(report, "skipped", "pending_canon", source_id, target_id, "unchanged")


def _sync_jobs(session, source: Path, novels: dict[str, NovelModel], report: dict) -> None:
    jobs_root = source / "runtime/jobs"
    for path in jobs_root.glob("*.json") if jobs_root.exists() else []:
        item = read_json(path, {}); source_id = str(item.get("id", path.stem)); target_id = external_uuid(source_id); model = session.get(GenerationJobModel, target_id)
        if model:
            payload = dict((model.request or {}).get("_repository_payload", {}))
            if model.status != item.get("status", "QUEUED"): _record(report, "conflicts", "generation_jobs", source_id, target_id, "status differs")
            elif not canonical_json_compare(payload, item): _record(report, "conflicts", "generation_jobs", source_id, target_id, "payload differs")
            else: _record(report, "skipped", "generation_jobs", source_id, target_id, "unchanged")
            continue
        novel = novels.get(item.get("novel_id")); chapter_id = None
        if novel and item.get("chapter_id"):
            try:
                number = int(item["chapter_id"].rsplit(":", 1)[1]); chapter_id = session.scalar(select(ChapterModel.id).where(ChapterModel.novel_id == novel.id, ChapterModel.chapter_number == number))
            except (ValueError, AttributeError): pass
        session.add(GenerationJobModel(id=target_id, novel_id=novel.id if novel else None, chapter_id=chapter_id, operation=item.get("operation", item.get("agent", "unknown")), status=item.get("status", "QUEUED"), request={"_repository_payload": item}, result=item.get("result"))); _record(report, "imported", "generation_jobs", source_id, target_id, "created")


def migrate(source: Path, database_url: str, report_path: Path) -> dict:
    repo = FileRepository(source); database = Database(database_url); database.require_healthy(); report = _new_report()
    with database.session() as session:
        novels: dict[str, NovelModel] = {}
        for source_novel in repo.list_novels():
            novel_id = source_novel["id"]
            try:
                novel = _sync_novel(session, repo, source_novel, report); novels[novel_id] = novel; root = repo.novels / novel_id
                locations = _sync_locations(session, root, novel, report)
                _sync_characters(session, root, novel, locations, report)
                _sync_timeline(session, root, novel, locations, report)
                _sync_secrets(session, root, novel, report)
                _sync_foreshadowing(session, root, novel, report)
                _sync_story_state(session, root, novel, report)
                _sync_chapters(session, repo, root, novel, report)
                _sync_canon_pending(session, root, novel, report)
            except Exception as exc:
                _record(report, "failed", "novels", novel_id, reason=f"{type(exc).__name__}: {exc}")
                raise
        _sync_jobs(session, source, novels, report)
    _finalize(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="novel_data")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--report", default="migration_report.json")
    args = parser.parse_args()
    print(json.dumps(migrate(Path(args.source), args.database_url, Path(args.report)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
