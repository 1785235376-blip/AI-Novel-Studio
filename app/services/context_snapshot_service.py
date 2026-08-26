from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from ..lore.context_intelligence import ContextSnapshot, canonical_hash
from ..storage import atomic_write


class ContextSnapshotService:
    def __init__(self, lore_repository):
        self.repository = lore_repository

    def create(
        self,
        chapter_id: str,
        chapter_version: int,
        context: dict,
        prompt_version: str,
        model: str,
        *,
        actor_id: str | None = None,
        session_id: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        context_mode: str | None = None,
        ordering: list[str] | None = None,
        budget: dict | None = None,
        generation_id: str | None = None,
        cloud: bool = False,
    ) -> dict:
        if cloud and _contains_local_only(context):
            raise ValueError("LOCAL_ONLY context cannot be persisted for cloud generation")
        memory_version = context.get("lore_memory", {}).get("memory_version", {})
        mode = context_mode or ("V2" if "context_pack_v2" in context else "V1")
        resolved_ordering = ordering if ordering is not None else _context_ordering(context, mode)
        resolved_budget = budget if budget is not None else _context_budget(context, mode)
        snapshot = ContextSnapshot(
            chapter_version_id=f"{chapter_id}:v{chapter_version}",
            context_pack_hash=canonical_hash(context),
            canon_version=canonical_hash(context.get("canon", [])),
            memory_version=memory_version,
            character_state_version=canonical_hash(context.get("characters", [])),
            timeline_version=canonical_hash(context.get("timeline", [])),
            prompt_version=prompt_version,
            model=model,
            actor_id=actor_id,
            session_id=session_id,
            scope_type=scope_type,
            scope_id=scope_id,
            context_mode=mode,
            ordering=resolved_ordering,
            budget=resolved_budget,
            generation_id=generation_id,
        ).model_dump(mode="json")
        if hasattr(self.repository, "backend"):
            novel_id = chapter_id.rsplit(":", 1)[0]
            root: Path = self.repository.backend.novels / novel_id / "lore" / "context_snapshots"
            root.mkdir(parents=True, exist_ok=True)
            for path in root.glob("*.json"):
                existing = json.loads(path.read_text(encoding="utf-8"))
                if all(existing.get(key) == snapshot.get(key) for key in (
                    "chapter_version_id", "context_pack_hash", "prompt_version", "model"
                )) and existing.get("generation_id") == generation_id:
                    return {key: existing[key] for key in snapshot}
            atomic_write(root / f"{snapshot['id']}.json", json.dumps({**snapshot, "context": context}, ensure_ascii=False, indent=2))
            return snapshot
        database = getattr(self.repository, "database", None)
        if database is None:
            raise RuntimeError("Context snapshot storage is unavailable")
        novel_slug, chapter_number = chapter_id.rsplit(":", 1)
        with database.session() as session:
            row = session.execute(text(
                "SELECT c.id, c.novel_id FROM chapters c JOIN novels n ON n.id=c.novel_id "
                "WHERE n.slug=:slug AND c.chapter_number=:number"
            ), {"slug": novel_slug, "number": int(chapter_number)}).one_or_none()
            if row is None:
                raise FileNotFoundError(chapter_id)
            inserted = None
            if generation_id is None:
                inserted = session.execute(text(
                    "SELECT id FROM chapter_context_snapshots WHERE chapter_id=:chapter_id AND chapter_version=:chapter_version "
                    "AND context_pack_hash=:context_hash AND prompt_version=:prompt_version AND model=:model "
                    "AND COALESCE(snapshot->>'generation_id','')='' ORDER BY created_at LIMIT 1"
                ), {"chapter_id": row.id, "chapter_version": chapter_version,
                    "context_hash": snapshot["context_pack_hash"], "prompt_version": prompt_version,
                    "model": model}).scalar_one_or_none()
            else:
                inserted = session.execute(text(
                    "SELECT id FROM chapter_context_snapshots WHERE chapter_id=:chapter_id "
                    "AND snapshot->>'generation_id'=:generation_id ORDER BY created_at LIMIT 1"
                ), {"chapter_id": row.id, "generation_id": generation_id}).scalar_one_or_none()
            if inserted is None:
                inserted = session.execute(text(
                "INSERT INTO chapter_context_snapshots "
                "(id,novel_id,chapter_id,chapter_version,context_pack_hash,canon_version,memory_version,"
                "character_state_version,timeline_version,prompt_version,model,actor_id,session_id,scope_type,scope_id,"
                "context_mode,ordering,budget,snapshot,created_at) "
                "VALUES (:id,:novel_id,:chapter_id,:chapter_version,:context_hash,:canon_version,CAST(:memory AS jsonb),"
                ":character_version,:timeline_version,:prompt_version,:model,:actor_id,:session_id,:scope_type,:scope_id,"
                ":context_mode,CAST(:ordering AS jsonb),CAST(:budget AS jsonb),CAST(:snapshot AS jsonb),:created_at) "
                "RETURNING id"
            ), {
                "id": snapshot["id"], "novel_id": row.novel_id, "chapter_id": row.id,
                "chapter_version": chapter_version, "context_hash": snapshot["context_pack_hash"],
                "canon_version": snapshot["canon_version"], "memory": json.dumps(memory_version),
                "character_version": snapshot["character_state_version"],
                "timeline_version": snapshot["timeline_version"], "prompt_version": prompt_version,
                "model": model, "snapshot": json.dumps({**snapshot, "context": context}, ensure_ascii=False),
                "actor_id": actor_id, "session_id": session_id, "scope_type": scope_type, "scope_id": scope_id,
                "context_mode": mode, "ordering": json.dumps(resolved_ordering), "budget": json.dumps(resolved_budget),
                "created_at": snapshot["created_at"],
            }).scalar_one()
            snapshot["id"] = str(inserted)
        return snapshot


def _contains_local_only(value) -> bool:
    if isinstance(value, dict):
        return any(value.get(key) == "LOCAL_ONLY" for key in ("privacy", "privacy_level", "locality")) or any(_contains_local_only(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_local_only(v) for v in value)
    return False


def _context_ordering(context: dict, mode: str) -> list[str]:
    if mode == "V2":
        return [str(item.get("chunk_id") or item.get("source_id")) for item in context.get("context_pack_v2", {}).get("chunks", [])]
    policy = context.get("context_policy", {})
    return [str(item.get("metadata", {}).get("source_id")) for item in policy.get("items", [])]


def _context_budget(context: dict, mode: str) -> dict:
    source = context.get("context_pack_v2", {}) if mode == "V2" else context.get("context_policy", {})
    return {key: source[key] for key in ("token_budget", "token_count", "used_tokens") if key in source}


class GenerationSnapshotGuard:
    """Enforces snapshot persistence as a precondition to invoking a model."""

    def __init__(self, snapshots: ContextSnapshotService):
        self.snapshots = snapshots

    def invoke(self, model_call, *, snapshot_kwargs: dict):
        snapshot = self.snapshots.create(**snapshot_kwargs)
        return snapshot, model_call()
