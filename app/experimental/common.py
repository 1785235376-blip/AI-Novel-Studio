"""Shared strict scope, revision and source fencing for opt-in domains."""
from __future__ import annotations
import copy
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from ..services.v1_capability_service import CapabilityVersionConflict
from ..source_privacy import content_digest


class StaleSourceError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def snapshot(row):
    return copy.deepcopy({k: v for k, v in row.items() if k != "history"})


def check_version(row, expected_version):
    if expected_version != row["version"]:
        raise CapabilityVersionConflict(copy.deepcopy(row))


def new_row(nid, scope, actor, payload):
    stamp = now()
    row = copy.deepcopy(payload)
    row.setdefault("status", "DRAFT")
    row.setdefault("privacy_level", "LOCAL_ONLY")
    row.update(id=new_id(), novel_id=nid, scope=copy.deepcopy(scope), version=1,
               created_by=actor, updated_by=actor, created_at=stamp, updated_at=stamp, history=[])
    return row


def change_row(row, actor, expected_version, callback):
    check_version(row, expected_version)
    before = snapshot(row)
    callback(row)
    for key in ("id", "novel_id", "scope", "created_by", "created_at"):
        row[key] = before[key]
    row.update(version=before["version"] + 1, updated_by=actor, updated_at=now(),
               history=row.get("history", []) + [before])
    return row


def api_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except CapabilityVersionConflict as exc:
        raise HTTPException(409, {"code": "EXPERIMENTAL_VERSION_CONFLICT", "current": exc.current}) from exc
    except StaleSourceError as exc:
        raise HTTPException(409, {"code": "EXPERIMENTAL_SOURCE_STALE", "message": str(exc)}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, {"code": "EXPERIMENTAL_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(422, {"code": "EXPERIMENTAL_INVALID", "message": str(exc)}) from exc


class DomainService:
    def __init__(self, store, novels, chapters):
        self.store, self.novels, self.chapters = store, novels, chapters

    def chapters_for(self, scope):
        from ..manuscript_sources import scoped_chapters
        return scoped_chapters(self.chapters, scope)

    def list(self, nid, scope, collection):
        self.novels.get(nid)
        rows = list(self.store.read(nid, scope)["collections"].get(collection, {}).values())
        if any(not isinstance(row, dict) or row.get("novel_id") != nid or row.get("scope") != scope for row in rows):
            raise ValueError("experimental collection contains invalid scope metadata")
        return rows

    def get(self, nid, scope, collection, rid):
        self.novels.get(nid)
        row = self.store.read(nid, scope)["collections"].get(collection, {}).get(rid)
        if row is None or row.get("novel_id") != nid or row.get("scope") != scope:
            raise FileNotFoundError(rid)
        return copy.deepcopy(row)

    def create(self, nid, scope, actor, collection, payload):
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            row = new_row(nid, scope, actor, payload)
            doc["collections"].setdefault(collection, {})[row["id"]] = row
            return copy.deepcopy(row)

    def mutate(self, nid, scope, actor, collection, rid, expected_version, callback):
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            row = doc["collections"].get(collection, {}).get(rid)
            if row is None or row.get("novel_id") != nid or row.get("scope") != scope:
                raise FileNotFoundError(rid)
            change_row(row, actor, expected_version, callback)
            return copy.deepcopy(row)

    def sources(self, nid, chapter_ids, scope=None):
        sources = {}
        for cid in dict.fromkeys(chapter_ids):
            chapter = self.chapters_for(scope).get(cid)
            if chapter.get("novel_id") != nid:
                raise ValueError("chapter belongs to another project")
            sources[cid] = {"version": chapter["version"], "digest": content_digest(chapter)}
            if scope and scope.get("mode") == "collaboration":
                sources[cid]["scope"] = copy.deepcopy(scope)
        return sources

    def assert_sources(self, nid, sources, scope=None):
        for cid, expected in sources.items():
            try:
                if scope is not None and expected.get('scope') is not None and expected['scope'] != scope:
                    raise StaleSourceError('source scope changed')
                source_scope = scope if scope is not None else expected.get('scope')
                chapter = self.chapters_for(source_scope).get(cid)
            except (FileNotFoundError, KeyError) as exc:
                raise StaleSourceError("source chapter no longer exists") from exc
            if chapter.get("novel_id") != nid or chapter.get("version") != expected.get("version") or content_digest(chapter) != expected.get("digest"):
                raise StaleSourceError("source chapter changed; review the current version")

    def stale(self, nid, sources, scope=None):
        try:
            self.assert_sources(nid, sources, scope)
            return False
        except StaleSourceError:
            return True
