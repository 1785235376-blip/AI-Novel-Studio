"""Bounded revision metadata embedded in the original story record owner.

No second record store: public V1 rows remain the authority and their exact
serialization is the digest input. Metadata is private to the versioned API.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone

from .chapter_repository import VersionConflict
from .structured_cas import FIELDS, UNGUARDED, assert_record_cas, record_digest

KINDS = frozenset(FIELDS)
PATHS = {'characters': 'characters/characters.json', 'locations': 'locations/locations.json',
         'relationships': 'relationships.json', 'timeline': 'timeline/events.json',
         'foreshadowing': 'foreshadowing.json'}
META = '_story_record'
HISTORY_LIMIT = 20


def public_record(row):
    return {key: deepcopy(value) for key, value in row.items() if key != META}


def envelope(record, metadata=None):
    meta = deepcopy(metadata or {})
    return {'record': deepcopy(record), 'digest': record_digest(record),
            'version': meta.get('version', 0), 'history': meta.get('history', []),
            'source_versions': meta.get('source_versions', []),
            'feedback': meta.get('feedback'), 'updated_at': meta.get('updated_at'),
            'actor_id': meta.get('actor_id'), 'action': meta.get('action', 'LEGACY'),
            'history_limit': HISTORY_LIMIT}


def prepare(kind, rid, current, metadata, payload, expected_digest, mutation):
    """Validate under the repository lock; resolve restore from stored history."""
    assert_record_cas(kind, rid, current, payload, expected_digest)
    if mutation is None:
        return payload
    version = (metadata or {}).get('version', 0)
    if mutation['expected_version'] != version:
        raise VersionConflict({'id': rid, 'version': version}, resource_id=rid,
                              expected_version=mutation['expected_version'])
    action = mutation['action']
    if action == 'RESTORE':
        previous = next((row for row in (metadata or {}).get('history', [])
                         if row['version'] == mutation['restore_version']), None)
        if previous is None: raise FileNotFoundError('story record revision')
        # Opaque extension data is retained, never supplied by clients.
        return {key: deepcopy(value) for key, value in previous['record'].items() if key != 'id'}
    if action == 'FEEDBACK':
        if current is None: raise FileNotFoundError(rid)
        feedback = (metadata or {}).get('feedback')
        if feedback and feedback.get('record_digest') == record_digest(current) and feedback.get('source_versions', []) == (metadata or {}).get('source_versions', []):
            raise VersionConflict({'id': rid, 'version': version}, resource_id=rid,
                                  expected_version=mutation['expected_version'])
        return {key: deepcopy(value) for key, value in current.items() if key != 'id'}
    if action != 'SAVE': raise ValueError('unsupported story record action')
    return payload


def finish(current, metadata, proposed, mutation):
    if mutation is None and not metadata:
        return None
    old = deepcopy(metadata or {})
    history = old.get('history', [])
    if current is not None:
        history = [*history, {'version': old.get('version', 0), 'record': deepcopy(current),
                             'digest': record_digest(current), 'source_versions': old.get('source_versions', []),
                             'feedback': old.get('feedback'), 'updated_at': old.get('updated_at'),
                             'actor_id': old.get('actor_id'), 'action': old.get('action', 'LEGACY')}][-HISTORY_LIMIT:]
    action = mutation['action'] if mutation else 'LEGACY_SAVE'
    sources = deepcopy(mutation.get('source_versions', [])) if mutation else []
    if action == 'RESTORE':
        snapshot = next(row for row in old['history'] if row['version'] == mutation['restore_version'])
        sources = deepcopy(snapshot.get('source_versions', []))
    if action == 'FEEDBACK': sources = deepcopy(old.get('source_versions', []))
    result = {'version': old.get('version', 0) + 1, 'history': history,
              'source_versions': sources, 'updated_at': datetime.now(timezone.utc).isoformat(),
              'actor_id': mutation.get('actor_id', 'local-user') if mutation else 'legacy-client',
              'action': action, 'feedback': old.get('feedback')}
    if action == 'FEEDBACK':
        result['feedback'] = {**deepcopy(mutation['feedback']), 'record_digest': record_digest(proposed),
                              'source_versions': sources, 'actor_id': result['actor_id'], 'at': result['updated_at']}
    return result


def core_record(kind, rid, current, payload, mutation, *, legacy_defaults=None):
    """Original structured fields plus server-owned extensions, never a new store."""
    from ..privacy import privacy_for_update
    if mutation and mutation['action'] in {'RESTORE', 'FEEDBACK'}:
        return {'id': rid, **deepcopy(payload)}
    defaults = {
        'characters': {'age': None, 'role': '', 'personality': '', 'goal': '',
                       'current_location': '', 'status': 'ALIVE'},
        'locations': {'location_type': '', 'description': '', 'rules': '',
                      'atmosphere': '', 'status': 'ACTIVE'},
        'relationships': {'relationship_type': '', 'description': '', 'status': 'ACTIVE',
                          'valid_from_event_id': '', 'valid_to_event_id': '', 'certainty': 'CONFIRMED'},
    }
    # Plain V1/digest-only callers keep their established replace-known-fields
    # semantics; versioned edits merge partial structured fields. Both retain
    # opaque imports that clients cannot author.
    retained = current or {}
    if mutation is None:
        retained = {key: value for key, value in retained.items() if key not in FIELDS[kind]}
    initial = legacy_defaults if mutation is None and legacy_defaults is not None else defaults[kind]
    result = {**initial, **deepcopy(retained), **deepcopy(payload), 'id': rid}
    result['privacy_level'] = privacy_for_update(payload, current)
    if 'privacy_level' not in payload and (current is None or current.get('privacy_status') == 'UNKNOWN'):
        result['privacy_status'] = 'UNKNOWN'
    elif 'privacy_level' in payload:
        result.pop('privacy_status', None)
    return result
