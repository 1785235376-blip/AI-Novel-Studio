"""Pure, bounded conversion using the original Studio timeline authority.

No parser, file, asset content, process, provider, or persistence is invoked here.
The calling owner must check Host/scope, formal asset versions and preview CAS.
Native NLE edits always win over stale Studio round-trip metadata; the latter is
restored only when its complete native projection still matches.
"""
from __future__ import annotations

import copy
import json
import re
from fractions import Fraction

from .studio_timeline_render import (normalize_studio_timeline, timeline_digest,
    studio_sources, clip_duration_ms, MAX_DURATION_MS, MAX_CLIPS)

EXTENSION_SCHEMA = "studio-timeline-otio/1"


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("STUDIO_EXCHANGE_FIELDS_INVALID")
    return value


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("STUDIO_EXCHANGE_INTEGER_INVALID")
    return value


def _name(value):
    if not isinstance(value, str) or len(value) > 240 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("STUDIO_EXCHANGE_NAME_INVALID")
    return value


def _source(value):
    row = _fields(value, ("kind", "id", "version", "digest", "asset_kind"),
                  ("kind", "id", "version", "digest", "asset_kind"))
    if (row["kind"] != "ASSET" or not isinstance(row["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", row["id"])
            or row["asset_kind"] not in ("video", "audio", "image")
            or not isinstance(row["digest"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["digest"])):
        raise ValueError("STUDIO_EXCHANGE_FORMAL_ASSET_REQUIRED")
    _integer(row["version"], 1, 2**53 - 1)
    return copy.deepcopy(row)


def _reference(source):
    # Opaque, portable text. It is never interpreted as a path or fetched URL.
    return f"media/{source['id']}-{source['digest']}"


def _bindings(value):
    from ..experimental.timeline_exchange import _url
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_CLIPS:
        raise ValueError("STUDIO_EXCHANGE_MEDIA_BINDING_LIMIT")
    result, assets = {}, {}
    for raw in value:
        row = _fields(raw, ("reference", "source_snapshot"), ("reference", "source_snapshot"))
        reference = _url(row["reference"])
        if not reference or reference in result:
            raise ValueError("STUDIO_EXCHANGE_DUPLICATE_OR_EMPTY_REFERENCE")
        source = _source(row["source_snapshot"])
        if assets.setdefault(source["id"], source) != source:
            raise ValueError("STUDIO_EXCHANGE_SOURCE_SNAPSHOT_CONFLICT")
        result[reference] = source
    return result


def validate_studio_extension(value):
    """Closed versioned payload; never a replacement for owner authorization."""
    row = _fields(value, ("schema", "timeline", "projection_digest"),
                  ("schema", "timeline", "projection_digest"))
    if (row["schema"] != EXTENSION_SCHEMA or not isinstance(row["projection_digest"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", row["projection_digest"])):
        raise ValueError("STUDIO_EXCHANGE_EXTENSION_INVALID")
    timeline = normalize_studio_timeline(row["timeline"])
    if timeline.get("schema_version") != 2:
        raise ValueError("STUDIO_EXCHANGE_EXTENSION_SCHEMA_2_REQUIRED")
    return {"schema": EXTENSION_SCHEMA, "timeline": timeline,
            "projection_digest": row["projection_digest"]}


def _projection(document):
    result = copy.deepcopy(document)
    result.pop("studio", None)
    for track in result["tracks"]:
        for item in track["items"]:
            item.pop("media_state", None)
    return result


def _document(value):
    from ..experimental.timeline_exchange import fraction, rational, seconds, _url, MAX_BYTES, validate_document
    doc = copy.deepcopy(_fields(value, ("name", "tracks", "global_start_time", "studio"),
                                ("name", "tracks", "global_start_time")))
    _name(doc["name"])
    count = 0

    def time(row, *, duration=False):
        row = _fields(row, ("frames", "rate"), ("frames", "rate"))
        rate = fraction(row["rate"])
        if not 0 < rate <= 1000000:
            raise ValueError("STUDIO_EXCHANGE_TIME_RATE_INVALID")
        result = seconds(row)
        if result < 0 or result > 86400 or duration and result <= 0:
            raise ValueError("STUDIO_EXCHANGE_TIME_RANGE_INVALID")
        row["frames"] = rational(fraction(row["frames"]))
        row["rate"] = rational(rate)
        return result

    if doc["global_start_time"] is not None:
        time(doc["global_start_time"])
    if not isinstance(doc["tracks"], list) or not 1 <= len(doc["tracks"]) <= 16:
        raise ValueError("STUDIO_EXCHANGE_TRACK_LIMIT")
    for track in doc["tracks"]:
        _fields(track, ("name", "kind", "items"), ("name", "kind", "items"))
        _name(track["name"])
        if track["kind"] not in ("Video", "Audio") or not isinstance(track["items"], list):
            raise ValueError("STUDIO_EXCHANGE_TRACK_KIND_INVALID")
        for row in track["items"]:
            count += 1
            if count > 2000:
                raise ValueError("STUDIO_EXCHANGE_ITEM_LIMIT")
            kind = row.get("kind") if isinstance(row, dict) else None
            if kind == "Transition":
                _fields(row, ("kind", "name", "transition_type", "in_offset", "out_offset"),
                        ("kind", "name", "transition_type", "in_offset", "out_offset"))
                if row["transition_type"] != "SMPTE_Dissolve":
                    raise ValueError("STUDIO_EXCHANGE_TRANSITION_INVALID")
                time(row["in_offset"]); time(row["out_offset"])
            elif kind in ("Clip", "Gap"):
                _fields(row, ("kind", "name", "start", "duration", "target_url", "media_state", "available_range", "speed")
                        if kind == "Clip" else ("kind", "name", "start", "duration"),
                        ("kind", "name", "start", "duration"))
                time(row["start"]); time(row["duration"], duration=True)
                if kind == "Clip":
                    if row.get("target_url") is not None:
                        _url(row["target_url"])
                    if row.get("media_state") is not None and row["media_state"] not in {
                            "EXTERNAL_REFERENCE_NOT_OPENED", "REFERENCE_ONLY_NOT_PACKAGED", "MISSING", "UNSUPPORTED_REFERENCE"}:
                        raise ValueError("STUDIO_EXCHANGE_MEDIA_STATE_INVALID")
                    if "available_range" in row:
                        span = _fields(row["available_range"], ("start", "duration"), ("start", "duration"))
                        time(span["start"]); time(span["duration"], duration=True)
                    if "speed" in row and not 0 < fraction(row["speed"]) <= 1000000:
                        raise ValueError("STUDIO_EXCHANGE_SPEED_INVALID")
                    if "speed" in row:
                        row["speed"] = rational(fraction(row["speed"]))
            else:
                raise ValueError("STUDIO_EXCHANGE_ITEM_KIND_INVALID")
            _name(row["name"])
    validate_document(doc)
    if "studio" in doc:
        doc["studio"] = validate_studio_extension(doc["studio"])
    try:
        encoded = json.dumps(doc, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise ValueError("STUDIO_EXCHANGE_DOCUMENT_INVALID") from None
    if len(encoded) > MAX_BYTES:
        raise ValueError("STUDIO_EXCHANGE_DOCUMENT_SIZE_LIMIT")
    return doc


def normalize_exchange_document(value):
    """Closed JSON-safe subset shared by the original official parser owner."""
    return _document(value)


def _loss(report, path, code, severity="LOSS"):
    report.append({"path": path, "code": code, "severity": severity})


def _time_ms(value):
    from ..experimental.timeline_exchange import seconds
    result = seconds(value) * 1000
    if result.denominator != 1:
        raise ValueError("STUDIO_EXCHANGE_TIME_REQUIRES_EXACT_MILLISECONDS")
    return result.numerator


def _studio_v2(value):
    original = normalize_studio_timeline(value)
    if original.get("schema_version") == 2:
        return original
    # Additive schema upgrade on a detached value, never a historical rewrite.
    original["schema_version"] = 2
    return normalize_studio_timeline(original)


def _native_tracks(timeline, report):
    """Represent bounded overlaps with parallel lanes, retaining placement.

    A native lane projection does not reproduce Studio's two-source dissolve;
    that exact relationship stays in the existing Studio extension and loss
    receipt. Only unchanged native projections can restore the extension.
    """
    from ..experimental.timeline_exchange import time_value, rational
    result = []
    rate = timeline["fps"]

    def at(milliseconds):
        return time_value(Fraction(milliseconds * rate, 1000), rate)

    for ti, track in enumerate(timeline["tracks"]):
        lanes = []
        for clip in track["clips"]:
            lane = next((row for row in lanes if row["end"] <= clip["start_ms"]), None)
            if lane is None:
                lane = {"end": 0, "items": []}
                lanes.append(lane)
            if clip["start_ms"] > lane["end"]:
                lane["items"].append({"kind": "Gap", "name": "Gap", "start": at(0),
                                      "duration": at(clip["start_ms"] - lane["end"])})
            length = clip_duration_ms(clip)
            item = {"kind": "Clip", "name": clip["id"], "start": at(clip["in_ms"]),
                    "duration": at(length), "target_url": _reference(clip["source_snapshot"]),
                    "media_state": "REFERENCE_ONLY_NOT_PACKAGED"}
            if clip["speed_num"] != clip["speed_den"]:
                item["speed"] = rational(Fraction(clip["speed_num"], clip["speed_den"]))
                _loss(report, f"tracks[{ti}].clips.{clip['id']}", "NLE_LINEAR_TIME_WARP_INTEROPERABILITY_NOT_RUN", "WARNING")
            lane["items"].append(item)
            lane["end"] = clip["start_ms"] + length
        if len(lanes) > 1:
            _loss(report, f"tracks[{ti}]", track["kind"] + "_OVERLAP_EXPORTED_AS_PARALLEL_LANES", "WARNING")
        for li, lane in enumerate(lanes):
            if lane["end"] < timeline["duration_ms"]:
                lane["items"].append({"kind": "Gap", "name": "Tail", "start": at(0),
                                      "duration": at(timeline["duration_ms"] - lane["end"])})
            track_name = track["id"] + (f" lane {li + 1}" if len(lanes) > 1 else "")
            if len(track_name) > 240:
                _loss(report, f"tracks[{ti}].name", "LANE_NAME_TRUNCATED_ID_RETAINED_IN_STUDIO_METADATA")
                track_name = track_name[:240]
            result.append({"name": track_name,
                           "kind": "Video" if track["kind"] == "VIDEO" else "Audio", "items": lane["items"]})
            if len(result) > 16:
                raise ValueError("STUDIO_EXCHANGE_AUDIO_OVERLAP_LANE_LIMIT_16")
    return result


def studio_timeline_to_exchange(timeline, *, title):
    """Concrete schema-two projection plus loss receipt and formal bindings."""
    normalized = _studio_v2(timeline)
    title = _name(title)
    report = []
    for ti, track in enumerate(normalized["tracks"]):
        path = f"tracks[{ti}]"
        if track.get("locked"):
            _loss(report, path, "TRACK_LOCK_REQUIRES_STUDIO_METADATA")
        if track["muted"] or track["gain_db"] != 0:
            _loss(report, path, "TRACK_MUTE_GAIN_REQUIRES_STUDIO_METADATA")
        if track["role"] not in ("PRIMARY", "DIALOGUE"):
            _loss(report, path, "TRACK_ROLE_REQUIRES_STUDIO_METADATA")
        for ci, clip in enumerate(track["clips"]):
            ip = f"{path}.clips[{ci}]"
            if clip["muted"] or clip["gain_db"] != 0 or clip["fade_in_ms"] or clip["fade_out_ms"]:
                _loss(report, ip, "CLIP_MIX_FADES_REQUIRE_STUDIO_METADATA")
            if track["kind"] == "VIDEO":
                if "transition_out" in clip:
                    _loss(report, ip + ".transition_out", "VIDEO_CROSS_DISSOLVE_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA")
                if "color_adjustment" in clip:
                    _loss(report, ip, "BASIC_COLOR_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA")
                if "crop" in clip:
                    _loss(report, ip, "CLIP_PIXEL_CROP_REQUIRES_STUDIO_METADATA")
                if (clip["x"], clip["y"], clip["width"], clip["height"], clip["opacity"]) != (
                        0, 0, normalized["width"], normalized["height"], 1.0):
                    _loss(report, ip, "VIDEO_GEOMETRY_OPACITY_REQUIRE_STUDIO_METADATA")
                if clip["include_audio"]:
                    _loss(report, ip, "EMBEDDED_VIDEO_AUDIO_MIX_REQUIRES_STUDIO_METADATA")
                if clip["source_snapshot"]["asset_kind"] == "image":
                    _loss(report, ip, "STILL_IMAGE_DURATION_INTEROPERABILITY_NOT_RUN", "WARNING")
    if normalized["captions"]:
        _loss(report, "captions", "CAPTIONS_REQUIRE_STUDIO_METADATA_NO_NLE_SUBTITLE_TRACK")
    _loss(report, "canvas", "CANVAS_RATE_DIMENSIONS_REQUIRE_STUDIO_METADATA", "WARNING")
    _loss(report, "media", "FORMAL_ASSET_REFERENCES_ONLY_NO_MEDIA_PACKAGING", "WARNING")
    _loss(report, "applications", "RESOLVE_PREMIERE_INTEROPERABILITY_NOT_RUN", "WARNING")
    document = {"name": title, "global_start_time": None, "tracks": _native_tracks(normalized, report)}
    document["studio"] = {"schema": EXTENSION_SCHEMA, "timeline": normalized,
                          "projection_digest": timeline_digest(_projection(document))}
    document = _document(document)
    return {"document": document, "report": report,
            "media_bindings": [{"reference": _reference(source), "source_snapshot": source}
                               for source in studio_sources(normalized)]}


def _canvas(value, duration):
    row = _fields(value, ("duration_ms", "width", "height", "fps"))
    result = {"duration_ms": duration, "width": row.get("width", 1280),
              "height": row.get("height", 720), "fps": row.get("fps", 24)}
    if "duration_ms" in row:
        result["duration_ms"] = _integer(row["duration_ms"], max(1, duration), MAX_DURATION_MS)
    _integer(result["width"], 16, 1920); _integer(result["height"], 16, 1080)
    _integer(result["fps"], 1, 60)
    if result["width"] % 2 or result["height"] % 2:
        raise ValueError("STUDIO_TIMELINE_EVEN_DIMENSIONS_REQUIRED")
    return result


def exchange_to_studio_timeline(document, *, media_bindings, canvas):
    """Import native timing with explicit current formal asset bindings.

    Unsupported transitions are reported as cuts. Fractional milliseconds,
    missing bindings, topology limits, and unsupported source kinds fail closed.
    No reference in the exchange can authorize a source by itself.
    """
    from ..experimental.timeline_exchange import fraction
    doc, bindings, report = _document(document), _bindings(media_bindings), []
    references = {item.get("target_url") for track in doc["tracks"] for item in track["items"]
                  if item["kind"] == "Clip"}
    if None in references or "" in references or set(bindings) != references:
        raise ValueError("STUDIO_EXCHANGE_EXACT_FORMAL_MEDIA_BINDINGS_REQUIRED")
    extension = doc.get("studio")
    if extension is not None and timeline_digest(_projection(doc)) == extension["projection_digest"]:
        restored = copy.deepcopy(extension["timeline"])
        # A matching digest only proves unchanged native structure. Re-derive the
        # projection to reject fabricated metadata unrelated to the actual cuts.
        projected = studio_timeline_to_exchange(restored, title=doc["name"])["document"]
        if _projection(projected) != _projection(doc):
            raise ValueError("STUDIO_EXCHANGE_EXTENSION_PROJECTION_MISMATCH")
        expected = {_reference(source): source for source in studio_sources(restored)}
        if bindings != expected:
            raise ValueError("STUDIO_EXCHANGE_EXTENSION_SOURCE_BINDING_MISMATCH")
        canvas = _fields(canvas, ("duration_ms", "width", "height", "fps"))
        requested = _canvas({**{key: restored[key] for key in ("duration_ms", "width", "height", "fps")},
                             **canvas}, restored["duration_ms"])
        if requested != {key: restored[key] for key in requested}:
            raise ValueError("STUDIO_EXCHANGE_CANVAS_DIFFERS_FROM_RESTORED_SNAPSHOT")
        return {"timeline": restored, "report": report}
    if extension is not None:
        _loss(report, "studio", "STUDIO_METADATA_STALE_AFTER_NATIVE_EDIT_NOT_RESTORED")
    if doc["global_start_time"] is not None:
        _loss(report, "global_start_time", "GLOBAL_TIMECODE_NOT_STUDIO_TIMELINE_PLACEMENT")
    if doc["name"]:
        _loss(report, "name", "EXCHANGE_TITLE_IS_NOT_A_STUDIO_TIMELINE_FIELD", "WARNING")
    tracks, length, count = [], 0, 0
    for ti, track in enumerate(doc["tracks"]):
        cursor, clips = 0, []
        for ii, item in enumerate(track["items"]):
            path = f"tracks[{ti}].items[{ii}]"
            if item["kind"] == "Transition":
                _loss(report, path, "NATIVE_DISSOLVE_IMPORTED_AS_CUT")
                continue
            duration = _time_ms(item["duration"])
            if item["kind"] == "Clip":
                source = bindings[item["target_url"]]
                allowed = {"video", "image"} if track["kind"] == "Video" else {"audio"}
                if source["asset_kind"] not in allowed:
                    raise ValueError("STUDIO_EXCHANGE_TRACK_MEDIA_KIND_MISMATCH")
                speed = fraction(item["speed"]) if "speed" in item else Fraction(1)
                if not Fraction(1, 4) <= speed <= 4 or speed.numerator > 4 or speed.denominator > 4:
                    raise ValueError("STUDIO_EXCHANGE_SPEED_REQUIRES_SUPPORTED_EXACT_RATIONAL")
                source_length = duration * speed
                if source_length.denominator != 1:
                    raise ValueError("STUDIO_EXCHANGE_SOURCE_TIME_REQUIRES_EXACT_MILLISECONDS")
                start = _time_ms(item["start"])
                if "available_range" in item:
                    available_in = _time_ms(item["available_range"]["start"])
                    available_out = available_in + _time_ms(item["available_range"]["duration"])
                    if start < available_in or start + source_length > available_out:
                        raise ValueError("STUDIO_EXCHANGE_CLIP_EXCEEDS_DECLARED_AVAILABLE_RANGE")
                clip = {"id": f"exchange-clip-{ti + 1}-{ii + 1}", "source_snapshot": source,
                        "start_ms": cursor, "in_ms": start, "out_ms": start + source_length.numerator,
                        "speed_num": speed.numerator, "speed_den": speed.denominator}
                clips.append(clip); count += 1
                if item["name"]:
                    _loss(report, path + ".name", "NATIVE_CLIP_NAME_NORMALIZED_TO_STUDIO_ID")
                if count > MAX_CLIPS:
                    raise ValueError("STUDIO_EXCHANGE_CLIP_LIMIT")
            cursor += duration
            if cursor > MAX_DURATION_MS:
                raise ValueError("STUDIO_EXCHANGE_DURATION_LIMIT")
        length = max(length, cursor)
        if clips:
            if track["name"]:
                _loss(report, f"tracks[{ti}].name", "NATIVE_TRACK_NAME_NORMALIZED_TO_STUDIO_ID")
            tracks.append({"id": f"exchange-track-{ti + 1}", "kind": "VIDEO" if track["kind"] == "Video" else "AUDIO",
                           "order": len(tracks), "clips": clips})
        else:
            _loss(report, f"tracks[{ti}]", "GAP_ONLY_TRACK_NOT_IMPORTED")
    if not tracks:
        raise ValueError("STUDIO_EXCHANGE_NO_FORMAL_MEDIA_CLIPS")
    if len(tracks) > 8:
        raise ValueError("STUDIO_EXCHANGE_STUDIO_TRACK_LIMIT_8")
    selected = _canvas(canvas, length)
    if any(fraction(item["duration"]["rate"]) != selected["fps"] for track in doc["tracks"]
           for item in track["items"] if item["kind"] != "Transition"):
        _loss(report, "canvas.fps", "NATIVE_FRAME_RATES_DIFFER_FROM_REQUESTED_STUDIO_OUTPUT_FPS", "WARNING")
    result = normalize_studio_timeline({"schema_version": 2, **selected, "tracks": tracks, "captions": []})
    return {"timeline": result, "report": report}
