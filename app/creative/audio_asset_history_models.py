"""Closed, source-free public projection of historical audio metadata."""
from __future__ import annotations
import re

def version_view(record):
    if not isinstance(record, dict):
        raise ValueError('AUDIO_HISTORY_INVALID')
    metadata = record.get('metadata')
    if not isinstance(metadata, dict):
        raise ValueError('AUDIO_HISTORY_INVALID')
    result = {}
    for key in ('version_id', 'metadata_digest', 'sha256'):
        value = record.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
            raise ValueError('AUDIO_HISTORY_INVALID')
        result[key] = value
    for key in ('asset_version', 'history_sequence', 'size'):
        value = record.get(key)
        if type(value) is not int or value < (1 if key in ('asset_version', 'history_sequence') else 0):
            raise ValueError('AUDIO_HISTORY_INVALID')
        result[key] = value
    media_type = metadata.get('media_type')
    if metadata.get('kind') != 'audio' or not isinstance(media_type, str) or not re.fullmatch(r'[A-Za-z0-9!#$&^_.+*-]+/[A-Za-z0-9!#$&^_.+*-]+', media_type):
        raise ValueError('AUDIO_HISTORY_INVALID')
    result['metadata'] = {'kind': 'audio', 'media_type': media_type,
                          'deleted': bool(metadata.get('deleted_at')),
                          'historically_approved': bool(metadata.get('approved_at'))}
    return result
