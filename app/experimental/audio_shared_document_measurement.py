"""Pure measurement of one canonical File scope document's mix candidates.

This module neither reads nor writes a store, reserves capacity, verifies a
project incarnation, or authorizes access. Only the original mix-proposals
collection is measured; unrelated audio configuration is not swept into it.
"""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import hmac
import json
import re

from .store import ExperimentalStore, _unique_object, canonical

MIX_COLLECTION = 'audio_v2_mix_proposals'
MAX_DOCUMENT_BYTES = 128 * 1024 * 1024
MAX_MIX_BYTES = 25 * 1024 * 1024

# AudiobookV2Service.mix / new_row, promotion checkpoint and review, including
# DirectedAudiobookService._mix_origin. Unknown fields are not proof that the
# bytes belong to an audio candidate and therefore make measurement unknown.
ROW_FIELDS = frozenset('id novel_id scope version created_by updated_by created_at updated_at status privacy_level plan_id plan_version sources source_asset_ids mixer_id content_base64 content_sha256 verification media asset_id required_features voice_direction timeline promotion_token promotion_started_at promotion_actor promotion_asset_id promotion_asset_digest promotion_state approved_at approved_by'.split())
REQUIRED_FIELDS = frozenset('id novel_id scope version created_by updated_by created_at updated_at status privacy_level plan_id plan_version sources source_asset_ids mixer_id content_base64 content_sha256 verification media asset_id'.split())
MEDIA_FIELDS = frozenset('media_type extension duration_ms sample_rate channels sample_width validation codec'.split())
TIMELINE_FIELDS = frozenset('id audio_asset_id start_ms end_ms pause_after_ms frame_timing'.split())


def _scalar(value):
    return value is None or type(value) in (str, int, float, bool)


def _fields(value, allowed):
    if not isinstance(value, dict) or not set(value) <= allowed:
        raise ValueError('unknown candidate fields')


def _shape(row, item_id, nid, scope, snapshot=False):
    _fields(row, ROW_FIELDS if snapshot else ROW_FIELDS | {'history'})
    if not REQUIRED_FIELDS <= set(row) or row['id'] != item_id or row['novel_id'] != nid or row['scope'] != scope:
        raise ValueError('invalid candidate identity')
    if (type(row['version']) is not int or row['version'] < 1
            or type(row['plan_version']) is not int or row['plan_version'] < 1
            or row['status'] not in {'PENDING_REVIEW', 'APPROVING', 'APPROVED', 'REJECTED'}):
        raise ValueError('invalid candidate state')
    for key, value in row.items():
        if key not in {'scope', 'sources', 'media', 'source_asset_ids', 'required_features', 'timeline', 'history'} and not _scalar(value):
            raise ValueError('unknown candidate value')
    for key in ('source_asset_ids', 'required_features'):
        if key in row and (not isinstance(row[key], list) or any(not isinstance(v, str) for v in row[key])):
            raise ValueError('invalid candidate list')
    _fields(row['media'], MEDIA_FIELDS)
    if any(not _scalar(v) for v in row['media'].values()):
        raise ValueError('invalid candidate media')
    sources = row['sources']
    if not isinstance(sources, dict):
        raise ValueError('invalid sources')
    for chapter, source in sources.items():
        if not isinstance(chapter, str):
            raise ValueError('invalid source id')
        _fields(source, {'version', 'digest', 'scope'})
        if any(not _scalar(v) for k, v in source.items() if k != 'scope') or ('scope' in source and source['scope'] != scope):
            raise ValueError('invalid source metadata')
    if 'timeline' in row:
        if not isinstance(row['timeline'], list):
            raise ValueError('invalid timeline')
        for item in row['timeline']:
            _fields(item, TIMELINE_FIELDS)
            if any(not _scalar(v) for k, v in item.items() if k != 'frame_timing'):
                raise ValueError('invalid timeline value')
            frames = item.get('frame_timing')
            if frames is not None:
                _fields(frames, {'frames', 'sample_rate'})
                if any(not _scalar(v) for v in frames.values()):
                    raise ValueError('invalid frame timing')


def _candidate(row):
    """Check actual embedded bytes, including retained snapshot copies."""
    if not isinstance(row, dict):
        raise ValueError('AUDIO_DOCUMENT_CANDIDATE_INVALID')
    encoded, digest = row.get('content_base64'), row.get('content_sha256')
    if (not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_MIX_BYTES + 2) // 3)
            or not isinstance(digest, str) or re.fullmatch(r'[a-f0-9]{64}', digest) is None):
        raise ValueError('AUDIO_DOCUMENT_CANDIDATE_INVALID')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('AUDIO_DOCUMENT_CANDIDATE_INVALID') from None
    if not 0 < len(raw) <= MAX_MIX_BYTES or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), digest):
        raise ValueError('AUDIO_DOCUMENT_CANDIDATE_INVALID')


def measure_file_scope_document(raw, nid, scope):
    """Return exact candidate contribution and full rewrite staging size.

    Only a byte-for-byte canonical File document is supported. Whole-document
    UTF-8 bytes minus the same document without the mix collection allocates
    that field, its complete rows/history and necessary comma exactly once.
    The full serialized document is the temporary file size needed for an
    atomic replacement. Existing live documents and other storage owners must
    still be accounted for separately by the caller.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_DOCUMENT_BYTES:
        raise ValueError('AUDIO_DOCUMENT_MEASUREMENT_UNAVAILABLE')
    try:
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite')))
        if not isinstance(document, dict) or type(document.get('schema_version')) is not int:
            raise ValueError('invalid document schema version')
        ExperimentalStore.validate(document, nid, scope)
        if canonical(document).encode('utf-8') != raw:
            raise ValueError('not canonical')
        rows = document['collections'].get(MIX_COLLECTION, {})
        if not isinstance(rows, dict):
            raise ValueError('invalid collection')
        for item_id, row in rows.items():
            _shape(row, item_id, nid, scope)
            _candidate(row)
            history = row.get('history', [])
            if not isinstance(history, list):
                raise ValueError('invalid candidate history')
            for snapshot in history:
                _shape(snapshot, item_id, nid, scope, snapshot=True)
                _candidate(snapshot)
        without = copy.deepcopy(document)
        without['collections'].pop(MIX_COLLECTION, None)
        excluded = len(canonical(without).encode('utf-8'))
        return {'mix_collection_bytes': len(raw) - excluded,
                'other_document_bytes': excluded,
                'full_document_bytes': len(raw),
                'atomic_temporary_bytes': len(raw)}
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise ValueError('AUDIO_DOCUMENT_MEASUREMENT_UNAVAILABLE') from None
