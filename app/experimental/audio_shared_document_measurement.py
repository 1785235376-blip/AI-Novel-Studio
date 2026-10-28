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
        ExperimentalStore.validate(document, nid, scope)
        if canonical(document).encode('utf-8') != raw:
            raise ValueError('not canonical')
        rows = document['collections'].get(MIX_COLLECTION, {})
        if not isinstance(rows, dict):
            raise ValueError('invalid collection')
        for row in rows.values():
            _candidate(row)
            history = row.get('history', [])
            if not isinstance(history, list):
                raise ValueError('invalid candidate history')
            for snapshot in history:
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
