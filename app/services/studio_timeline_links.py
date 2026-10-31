"""Bounded, metadata-only VIDEO/AUDIO pairs owned by the original timeline."""
from __future__ import annotations
from copy import deepcopy

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


def linked_pair_facts(timeline, video_id, audio_id, operation='SPLIT'):
    """Shared bounded mode/lock check on the original persisted pair."""
    from .studio_timeline_render import _identity
    _identity(video_id); _identity(audio_id)
    pair = clip_link(timeline, video_id)
    if timeline.get('schema_version') != 2 or not pair or pair['video_clip_id'] != video_id or pair['audio_clip_id'] != audio_id:
        raise ValueError(f'STUDIO_TIMELINE_LINKED_{operation}_PAIR_REQUIRED')
    clips = {clip['id']: (track, clip) for track in timeline['tracks'] for clip in track['clips']}
    video_track, video = clips[video_id]; audio_track, audio = clips[audio_id]
    if video_track.get('locked') or audio_track.get('locked'):
        raise ValueError('STUDIO_TIMELINE_TRACK_LOCKED')
    if (video['source_snapshot']['asset_kind'] != 'video' or audio['source_snapshot']['asset_kind'] != 'audio'
            or any(clip.get(key, 1) != 1 for clip in (video, audio) for key in ('speed_num', 'speed_den'))
            or any(clip.get(key, 0) for clip in (video, audio) for key in ('fade_in_ms', 'fade_out_ms'))
            or any(clip.get('transition_out') and (clip['id'] in (video_id, audio_id)
                   or clip['transition_out']['to_clip_id'] in (video_id, audio_id)) for _, clip in clips.values())):
        raise ValueError(f'STUDIO_TIMELINE_LINKED_{operation}_MODE_UNSUPPORTED')
    return {'pair': pair, 'video': (video_track, video), 'audio': (audio_track, audio),
            'common_length_ms': min(video['out_ms'] - video['in_ms'], audio['out_ms'] - audio['in_ms'])}


def linked_split_facts(timeline, video_id, audio_id, at_ms):
    """Video-referenced cut; audio cut is shifted by the saved start offset."""
    from .studio_timeline_render import _integer, MAX_DURATION_MS
    facts = linked_pair_facts(timeline, video_id, audio_id)
    video, audio = facts['video'][1], facts['audio'][1]
    at_ms = _integer(at_ms, 0, MAX_DURATION_MS)
    elapsed = at_ms - video['start_ms']
    if not 0 < elapsed < facts['common_length_ms']:
        raise ValueError('STUDIO_TIMELINE_LINKED_SPLIT_OUTSIDE_COMMON_RANGE')
    return {**facts, 'video_at_ms': at_ms, 'audio_at_ms': audio['start_ms'] + elapsed, 'elapsed_ms': elapsed}


def trim_linked_pair(timeline, video_id, audio_id, keep_from_ms, keep_to_ms):
    """Non-ripple source trim: same relative interval, original timeline starts."""
    from .studio_timeline_render import _integer, normalize_studio_timeline, MAX_DURATION_MS
    result = deepcopy(timeline)
    facts = linked_pair_facts(result, video_id, audio_id, 'TRIM')
    start = _integer(keep_from_ms, 0, MAX_DURATION_MS)
    end = _integer(keep_to_ms, 0, MAX_DURATION_MS)
    if not 0 <= start < end <= facts['common_length_ms']:
        raise ValueError('STUDIO_TIMELINE_LINKED_TRIM_OUTSIDE_COMMON_RANGE')
    if start == 0 and all(clip['out_ms'] - clip['in_ms'] == end for _, clip in (facts['video'], facts['audio'])):
        raise ValueError('STUDIO_TIMELINE_LINKED_TRIM_NO_CHANGE')
    for _, clip in (facts['video'], facts['audio']):
        clip.update(in_ms=clip['in_ms'] + start, out_ms=clip['in_ms'] + end)
    return normalize_studio_timeline(result)


def _matches_linked_trim(before, after, pair):
    old = {clip['id']: (track['id'], clip) for track in before['tracks'] for clip in track['clips']}
    new = {clip['id']: (track['id'], clip) for track in after['tracks'] for clip in track['clips']}
    video_id, audio_id = pair['video_clip_id'], pair['audio_clip_id']
    if video_id not in new or audio_id not in new:
        return False
    try:
        origin = old[video_id][1]['in_ms']
        expected = trim_linked_pair(before, video_id, audio_id, new[video_id][1]['in_ms'] - origin, new[video_id][1]['out_ms'] - origin)
    except ValueError:
        return False
    # A source trim cannot admit a split with orphaned tails or unrelated changes.
    return after == expected


def split_linked_pair(timeline, video_id, audio_id, at_ms, new_video_id, new_audio_id):
    from .studio_timeline_render import _identity, normalize_studio_timeline
    result = deepcopy(timeline)
    facts = linked_split_facts(result, video_id, audio_id, at_ms)
    existing = {clip['id'] for track in result['tracks'] for clip in track['clips']}
    ids = (_identity(new_video_id), _identity(new_audio_id))
    if ids[0] == ids[1] or any(identity in existing for identity in ids):
        raise ValueError('STUDIO_TIMELINE_LINKED_SPLIT_NEW_IDS_INVALID')
    if len(existing) + 2 > 30 or len(result['clip_links']) + 1 > MAX_CLIP_LINKS:
        raise ValueError('STUDIO_TIMELINE_LINKED_SPLIT_LIMIT')
    for kind, identity in zip(('video', 'audio'), ids):
        track, left = facts[kind]; right = deepcopy(left); elapsed = facts['elapsed_ms']
        right.update(id=identity, start_ms=left['start_ms'] + elapsed, in_ms=left['in_ms'] + elapsed)
        left['out_ms'] = left['in_ms'] + elapsed
        track['clips'].append(right)
    result['clip_links'].append({'video_clip_id': ids[0], 'audio_clip_id': ids[1], 'offset_ms': facts['pair']['offset_ms']})
    return normalize_studio_timeline(result)


def _matches_linked_split(before, after, pair):
    """Full Save accepts only an exact four-segment source partition, no marker."""
    old = {clip['id']: (track['id'], clip) for track in before['tracks'] for clip in track['clips']}
    new = {clip['id']: (track['id'], clip) for track in after['tracks'] for clip in track['clips']}
    video_id, audio_id = pair['video_clip_id'], pair['audio_clip_id']
    if video_id not in new or audio_id not in new:
        return False
    elapsed = new[video_id][1]['out_ms'] - old[video_id][1]['in_ms']
    matches = 0
    for tail in after.get('clip_links', []):
        ids = (tail['video_clip_id'], tail['audio_clip_id'])
        if any(identity in old for identity in ids) or tail['offset_ms'] != pair['offset_ms']:
            continue
        try:
            expected = split_linked_pair(before, video_id, audio_id, old[video_id][1]['start_ms'] + elapsed, *ids)
        except ValueError:
            continue
        expected_clips = {clip['id']: (track['id'], clip) for track in expected['tracks'] for clip in track['clips']}
        if all(new.get(identity) == expected_clips[identity] for identity in (video_id, audio_id, *ids)):
            matches += 1
    return matches == 1


def require_clip_link_preservation(before, after):
    """Fence full DTO saves too; unsupported timing edits cannot bypass /edit.

    Explicit removal of a pair permits later independent edits. A pair retained
    across the save keeps its original offset, source snapshots and source ranges,
    except for one exact linked partition or shared source trim checked against the prior DTO.
    """
    previous, current = before.get('clip_links', []), after.get('clip_links', [])
    old = {clip['id']: (track, clip) for track in before['tracks'] for clip in track['clips']}
    new = {clip['id']: (track, clip) for track in after['tracks'] for clip in track['clips']}
    linked_edit_count = 0
    for pair in previous:
        match = next((row for row in current if row['video_clip_id'] == pair['video_clip_id']
                      and row['audio_clip_id'] == pair['audio_clip_id']), None)
        if match is not None:
            if match['offset_ms'] != pair['offset_ms']:
                raise ValueError('STUDIO_TIMELINE_LINK_OFFSET_CHANGED')
            range_changed = any(old[identity][1].get(key, 1) != new[identity][1].get(key, 1)
                                for identity in (pair['video_clip_id'], pair['audio_clip_id'])
                                for key in ('source_snapshot', 'in_ms', 'out_ms', 'speed_num', 'speed_den'))
            paired_split = range_changed and _matches_linked_split(before, after, pair)
            paired_trim = range_changed and _matches_linked_trim(before, after, pair)
            if paired_split or paired_trim:
                linked_edit_count += 1
                if linked_edit_count > 1:
                    raise ValueError('STUDIO_TIMELINE_LINKED_EDIT_ONE_PAIR_REQUIRED')
            for identity in (pair['video_clip_id'], pair['audio_clip_id']):
                left, right = old[identity][1], new[identity][1]
                if not (paired_split or paired_trim) and any(left.get(key, 1) != right.get(key, 1)
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
