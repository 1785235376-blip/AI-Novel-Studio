"""Closed video schema two and explicit audio-only schema three.

Historical schema-one/two normalized bytes and defaults are never rewritten.
"""
from __future__ import annotations

import math


def normalize_timeline_v2(value, *, audio_only=False):
    # Imported on demand by the original normalizer, after its helpers exist.
    from .studio_timeline_render import (_object, _integer, _identity, _boolean,
        MAX_DURATION_MS, MAX_CLIPS, MAX_CAPTION_CHARACTERS, clip_duration_ms)
    import re

    if audio_only:
        row = _object(value, ("schema_version", "media_kind", "duration_ms", "tracks"),
                      ("schema_version", "media_kind", "duration_ms", "tracks"))
        if row["media_kind"] != "AUDIO":
            raise ValueError("STUDIO_TIMELINE_AUDIO_KIND_REQUIRED")
    else:
        row = _object(value, ("schema_version", "duration_ms", "width", "height", "fps", "tracks", "captions"),
                      ("schema_version", "duration_ms", "tracks"))
    if type(row["schema_version"]) is not int or row["schema_version"] != (3 if audio_only else 2):
        raise ValueError("STUDIO_TIMELINE_SCHEMA_INVALID")
    duration = _integer(row["duration_ms"], 1, MAX_DURATION_MS)
    width, height = _integer(row.get("width", 1280), 16, 1920), _integer(row.get("height", 720), 16, 1080)
    fps = _integer(row.get("fps", 24), 1, 60)
    if width % 2 or height % 2:
        raise ValueError("STUDIO_TIMELINE_EVEN_DIMENSIONS_REQUIRED")
    raw_tracks = row["tracks"]
    if not isinstance(raw_tracks, list) or not 1 <= len(raw_tracks) <= 8:
        raise ValueError("STUDIO_TIMELINE_TRACK_LIMIT")
    tracks, ids, orders, clip_ids, sources = [], set(), set(), set(), {}
    counts, clip_count = {"VIDEO": 0, "AUDIO": 0}, 0

    def number(value, low, high, code):
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValueError(code)
        try:
            numeric = float(value)
        except (ValueError, OverflowError) as error:
            raise ValueError(code) from error
        if not math.isfinite(numeric):
            raise ValueError(code)
        return numeric

    for raw in raw_tracks:
        track = _object(raw, ("id", "kind", "order", "role", "muted", "gain_db", "clips", "locked"),
                        ("id", "kind", "order", "clips"))
        tid, kind, order = _identity(track["id"]), track["kind"], _integer(track["order"], 0, 7)
        if not isinstance(kind, str) or kind not in counts or tid in ids or order in orders:
            raise ValueError("STUDIO_TIMELINE_TRACK_ID_ORDER_KIND_INVALID")
        if audio_only and kind != "AUDIO":
            raise ValueError("STUDIO_TIMELINE_AUDIO_TRACK_REQUIRED")
        ids.add(tid); orders.add(order); counts[kind] += 1
        if counts[kind] > 4:
            raise ValueError("STUDIO_TIMELINE_TRACK_KIND_LIMIT")
        role = track.get("role", "PRIMARY" if kind == "VIDEO" else "DIALOGUE")
        if not isinstance(role, str) or role not in ({"PRIMARY", "OVERLAY"} if kind == "VIDEO" else {"DIALOGUE", "MUSIC", "EFFECTS"}):
            raise ValueError("STUDIO_TIMELINE_TRACK_ROLE_INVALID")
        muted = _boolean(track.get("muted", False))
        gain = number(track.get("gain_db", 0.0), -60, 12, "STUDIO_TIMELINE_AUDIO_GAIN_INVALID")
        if kind != "AUDIO" and gain != 0:
            raise ValueError("STUDIO_TIMELINE_GAIN_REQUIRES_AUDIO")
        if not isinstance(track["clips"], list) or not 1 <= len(track["clips"]) <= MAX_CLIPS:
            raise ValueError("STUDIO_TIMELINE_CLIP_LIMIT")
        clips = []
        for raw_clip in track["clips"]:
            clip = _object(raw_clip, ("id", "source_snapshot", "start_ms", "in_ms", "out_ms", "x", "y", "width", "height",
                "speed_num", "speed_den", "opacity", "gain_db", "muted", "fade_in_ms", "fade_out_ms", "include_audio", "crop", "transition_out"),
                ("id", "source_snapshot", "start_ms", "in_ms", "out_ms"))
            cid = _identity(clip["id"])
            if cid in clip_ids:
                raise ValueError("STUDIO_TIMELINE_CLIP_ID_DUPLICATE")
            clip_ids.add(cid); clip_count += 1
            if clip_count > MAX_CLIPS:
                raise ValueError("STUDIO_TIMELINE_CLIP_LIMIT")
            source = _object(clip["source_snapshot"], ("id", "kind", "asset_kind", "version", "digest"),
                             ("id", "kind", "asset_kind", "version", "digest"))
            allowed_kinds = {"video", "image"} if kind == "VIDEO" else {"audio"}
            if (source["kind"] != "ASSET" or not isinstance(source["asset_kind"], str) or source["asset_kind"] not in allowed_kinds
                    or not isinstance(source["digest"], str) or not re.fullmatch(r"[a-f0-9]{64}", source["digest"])):
                raise ValueError("STUDIO_TIMELINE_SOURCE_INVALID")
            snapshot = {"id": _identity(source["id"]), "kind": "ASSET", "asset_kind": source["asset_kind"],
                        "version": _integer(source["version"], 1, 2**53 - 1), "digest": source["digest"]}
            if sources.setdefault(snapshot["id"], snapshot) != snapshot:
                raise ValueError("STUDIO_TIMELINE_SOURCE_SNAPSHOT_CONFLICT")
            placement = _integer(clip["start_ms"], 0, duration - 1)
            start, end = _integer(clip["in_ms"], 0, 36_000_000), _integer(clip["out_ms"], 1, 36_000_000)
            if end <= start:
                raise ValueError("STUDIO_TIMELINE_CLIP_RANGE_INVALID")
            num, den = _integer(clip.get("speed_num", 1), 1, 4), _integer(clip.get("speed_den", 1), 1, 4)
            divisor = math.gcd(num, den)
            num, den = num // divisor, den // divisor
            item = {"id": cid, "source_snapshot": snapshot, "start_ms": placement, "in_ms": start, "out_ms": end,
                    "speed_num": num, "speed_den": den, "muted": _boolean(clip.get("muted", False)),
                    "gain_db": number(clip.get("gain_db", 0.0), -60, 12, "STUDIO_TIMELINE_AUDIO_GAIN_INVALID")}
            length = clip_duration_ms(item)
            if placement + length > duration:
                raise ValueError("STUDIO_TIMELINE_CLIP_RANGE_INVALID")
            item["fade_in_ms"] = _integer(clip.get("fade_in_ms", 0), 0, length)
            item["fade_out_ms"] = _integer(clip.get("fade_out_ms", 0), 0, length)
            if item["fade_in_ms"] + item["fade_out_ms"] > length:
                raise ValueError("STUDIO_TIMELINE_FADE_RANGE_INVALID")
            if kind == "VIDEO":
                x, y = _integer(clip.get("x", 0), 0, width - 16), _integer(clip.get("y", 0), 0, height - 16)
                cw, ch = _integer(clip.get("width", width - x), 16, width - x), _integer(clip.get("height", height - y), 16, height - y)
                if cw % 2 or ch % 2:
                    raise ValueError("STUDIO_TIMELINE_EVEN_DIMENSIONS_REQUIRED")
                item.update(x=x, y=y, width=cw, height=ch,
                    opacity=number(clip.get("opacity", 1.0), 0, 1, "STUDIO_TIMELINE_OPACITY_INVALID"),
                    include_audio=_boolean(clip.get("include_audio", False)))
                if snapshot["asset_kind"] == "image" and (start != 0 or num != den or item["include_audio"]):
                    raise ValueError("STUDIO_TIMELINE_STILL_RANGE_INVALID")
                if not item["include_audio"] and item["gain_db"] != 0:
                    raise ValueError("STUDIO_TIMELINE_GAIN_REQUIRES_AUDIO")
                if "crop" in clip:
                    crop = _object(clip["crop"], ("x", "y", "width", "height"), ("x", "y", "width", "height"))
                    # Pixels refer to the original coded source, before display
                    # autorotation and output scaling. Actual source bounds are
                    # proved by the renderer; author values are never filters.
                    item["crop"] = {"x": _integer(crop["x"], 0, 32767), "y": _integer(crop["y"], 0, 32767),
                        "width": _integer(crop["width"], 1, 32768), "height": _integer(crop["height"], 1, 32768)}
                if "transition_out" in clip:
                    transition = _object(clip["transition_out"], ("kind", "to_clip_id", "duration_ms"),
                                         ("kind", "to_clip_id", "duration_ms"))
                    if transition["kind"] != "CROSS_DISSOLVE":
                        raise ValueError("STUDIO_TIMELINE_TRANSITION_KIND_INVALID")
                    item["transition_out"] = {"kind": "CROSS_DISSOLVE", "to_clip_id": _identity(transition["to_clip_id"]),
                        "duration_ms": _integer(transition["duration_ms"], math.ceil(2000 / fps), 10_000)}
            elif any(key in clip for key in ("x", "y", "width", "height", "opacity", "include_audio", "crop", "transition_out")):
                raise ValueError("STUDIO_TIMELINE_VIDEO_GEOMETRY_REQUIRES_VIDEO")
            clips.append(item)
        clips.sort(key=lambda item: (item["start_ms"], item["id"]))
        if kind == "VIDEO":
            incoming = 0
            for index, left in enumerate(clips):
                transition = left.get("transition_out")
                right = clips[index + 1] if index + 1 < len(clips) else None
                length = clip_duration_ms(left)
                overlap = left["start_ms"] + length - right["start_ms"] if right else 0
                if transition is None:
                    if overlap > 0:
                        raise ValueError("STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP")
                    incoming = 0
                    continue
                window = transition["duration_ms"]
                if (right is None or transition["to_clip_id"] != right["id"] or overlap != window
                        or window >= length or window >= clip_duration_ms(right) or incoming + window > length):
                    raise ValueError("STUDIO_TIMELINE_TRANSITION_WINDOW_INVALID")
                # A transition blends two pictures in one exact rectangle.
                # Keep lower tracks visible through the common opacity. Muting
                # one side or combining per-clip fades would change its meaning.
                if (any(left[key] != right[key] for key in ("x", "y", "width", "height", "opacity"))
                        or left["muted"] or right["muted"]
                        or any(clip[key] for clip in (left, right) for key in ("fade_in_ms", "fade_out_ms"))):
                    raise ValueError("STUDIO_TIMELINE_TRANSITION_VISUALS_INCOMPATIBLE")
                incoming = window
        normalized_track = {"id": tid, "kind": kind, "order": order, "role": role, "muted": muted, "gain_db": gain, "clips": clips}
        if "locked" in track:
            normalized_track["locked"] = _boolean(track["locked"])
        # New optional fields stay absent from old saved schema-two records, so
        # normalization does not rewrite their canonical digest or history.
        tracks.append(normalized_track)
    if audio_only:
        return {"schema_version": 3, "media_kind": "AUDIO", "duration_ms": duration,
                "tracks": sorted(tracks, key=lambda track: track["order"])}
    if not counts["VIDEO"]:
        raise ValueError("STUDIO_TIMELINE_VIDEO_TRACK_REQUIRED")
    raw_captions = row.get("captions", [])
    if not isinstance(raw_captions, list) or len(raw_captions) > 500:
        raise ValueError("STUDIO_TIMELINE_CAPTION_LIMIT")
    captions, characters = [], 0
    for raw in raw_captions:
        cue = _object(raw, ("start_ms", "end_ms", "text"), ("start_ms", "end_ms", "text"))
        start, end = _integer(cue["start_ms"], 0, duration - 1), _integer(cue["end_ms"], 1, duration)
        text = cue["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise ValueError("STUDIO_TIMELINE_CAPTION_TEXT_INVALID")
        text = text.replace("\r\n", "\n")
        if (end <= start or text.count("\n") > 7 or "-->" in text or any(not line.strip() for line in text.split("\n"))
                or any(ord(character) < 32 and character != "\n" or ord(character) == 127 or 0xD800 <= ord(character) <= 0xDFFF for character in text)
                or any(character in text for character in "{}<>\\")):
            raise ValueError("STUDIO_TIMELINE_CAPTION_LITERAL_TEXT_REQUIRED")
        characters += len(text)
        if characters > MAX_CAPTION_CHARACTERS:
            raise ValueError("STUDIO_TIMELINE_CAPTION_LIMIT")
        captions.append({"start_ms": start, "end_ms": end, "text": text})
    captions.sort(key=lambda cue: (cue["start_ms"], cue["end_ms"], cue["text"]))
    return {"schema_version": 2, "duration_ms": duration, "width": width, "height": height, "fps": fps,
            "tracks": sorted(tracks, key=lambda track: track["order"]), "captions": captions}
