"""Opt-in original knowledge-record digest CAS; legacy upserts remain compatible."""
from __future__ import annotations
import hashlib
import json
from .chapter_repository import VersionConflict

UNGUARDED = object()
FIELDS = {
    'timeline': {'id', 'sequence', 'time', 'title', 'description', 'location', 'characters', 'chapter_id', 'status', 'privacy_level', 'privacy_status'},
    'foreshadowing': {'id', 'title', 'description', 'planted_chapter', 'target_chapter', 'status', 'characters', 'events', 'privacy_level', 'privacy_status'},
    'characters': {'id', 'name', 'age', 'role', 'personality', 'goal', 'current_location', 'status', 'privacy_level', 'privacy_status'},
    'locations': {'id', 'name', 'location_type', 'description', 'rules', 'atmosphere', 'status', 'privacy_level', 'privacy_status'},
    'relationships': {'id', 'source_character_id', 'target_character_id', 'relationship_type', 'description', 'status', 'valid_from_event_id', 'valid_to_event_id', 'certainty', 'privacy_level', 'privacy_status'},
}


def record_digest(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def assert_record_cas(kind, rid, current, payload, expected_digest):
    if expected_digest is UNGUARDED: return
    if expected_digest is not None and (not isinstance(expected_digest, str) or len(expected_digest) != 64):
        raise ValueError('expected record digest is invalid')
    if (record_digest(current) if current is not None else None) != expected_digest:
        # Do not include private current content in a failed CAS response.
        raise VersionConflict({'id': rid, 'version': 0}, resource_id=rid)
    if set(payload) - (FIELDS[kind] - {'id', 'privacy_status'}):
        raise ValueError('structured CAS cannot discard unsupported extension fields')
