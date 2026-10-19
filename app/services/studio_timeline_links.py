"""Bounded, metadata-only VIDEO/AUDIO pairs owned by the original timeline."""
from __future__ import annotations

MAX_CLIP_LINKS = 15  # Existing 30-clip document limit; each clip belongs to one pair.


def normalize_clip_links(value, tracks):
    from .studio_timeline_render import _object, _identity, _integer, MAX_DURATION_MS
    if not isinstance(value, list) or len(value) > MAX_CLIP_LINKS:
        raise ValueError('STUDIO_TIMELINE_LINK_LIMIT')
    clips = {clip['id']: (track, clip) for track in tracks for clip in track['clips']}
    result, used = [], set()
    for raw in value:
        row = _object(raw, ('video_clip_id', 'audio_clip_id', 'offset_ms'),
                      ('video_clip_id', 'audio_clip_id', 'offset_ms'))
        video, audio = _identity(row['video_clip_id']), _identity(row['audio_clip_id'])
        offset = _integer(row['offset_ms'], -MAX_DURATION_MS, MAX_DURATION_MS)
        if (video == audio or video in used or audio in used or video not in clips or audio not in clips
                or clips[video][0]['kind'] != 'VIDEO' or clips[audio][0]['kind'] != 'AUDIO'):
            raise ValueError('STUDIO_TIMELINE_LINK_PAIR_INVALID')
        if clips[audio][1]['start_ms'] - clips[video][1]['start_ms'] != offset:
            raise ValueError('STUDIO_TIMELINE_LINK_OFFSET_CHANGED')
        used.update((video, audio))
        result.append({'video_clip_id': video, 'audio_clip_id': audio, 'offset_ms': offset})
    return sorted(result, key=lambda row: (row['video_clip_id'], row['audio_clip_id']))


def clip_link(timeline, identity):
    return next((row for row in timeline.get('clip_links', [])
                 if identity in (row['video_clip_id'], row['audio_clip_id'])), None)


def require_clip_link_preservation(before, after):
    """Fence full DTO saves too; unsupported timing edits cannot bypass /edit.

    Explicit removal of a pair permits later independent edits. A pair retained
    across the save keeps its original offset, source snapshots and source ranges.
    """
    previous, current = before.get('clip_links', []), after.get('clip_links', [])
    old = {clip['id']: (track, clip) for track in before['tracks'] for clip in track['clips']}
    new = {clip['id']: (track, clip) for track in after['tracks'] for clip in track['clips']}
    for pair in previous:
        match = next((row for row in current if row['video_clip_id'] == pair['video_clip_id']
                      and row['audio_clip_id'] == pair['audio_clip_id']), None)
        if match is not None:
            if match['offset_ms'] != pair['offset_ms']:
                raise ValueError('STUDIO_TIMELINE_LINK_OFFSET_CHANGED')
            for identity in (pair['video_clip_id'], pair['audio_clip_id']):
                left, right = old[identity][1], new[identity][1]
                if any(left.get(key, 1) != right.get(key, 1)
                       for key in ('source_snapshot', 'in_ms', 'out_ms', 'speed_num', 'speed_den')):
                    raise ValueError('STUDIO_TIMELINE_LINK_EDIT_UNSUPPORTED_UNLINK_FIRST')
                if ((old[identity][0].get('locked') is True or new[identity][0].get('locked') is True)
                        and (old[identity][0]['id'] != new[identity][0]['id'] or left['start_ms'] != right['start_ms'])):
                    raise ValueError('STUDIO_TIMELINE_TRACK_LOCKED')
    changed = [pair for pair in previous if pair not in current] + [pair for pair in current if pair not in previous]
    for pair in changed:
        if any(old.get(identity, new.get(identity))[0].get('locked') is True
               for identity in (pair['video_clip_id'], pair['audio_clip_id'])):
            raise ValueError('STUDIO_TIMELINE_TRACK_LOCKED')
