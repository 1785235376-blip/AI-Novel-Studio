"""Atomic author edits of an original timeline document; no binary/state owner."""
from __future__ import annotations

from copy import deepcopy
import re
import json

from .studio_timeline_render import normalize_studio_timeline


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", value):
        raise ValueError("STUDIO_TIMELINE_EDIT_ID_INVALID")
    return value


def _integer(value):
    if type(value) is not int:
        raise ValueError("STUDIO_TIMELINE_EDIT_INTEGER_INVALID")
    return value


def _duration(clip):
    if not isinstance(clip, dict) or "out_ms" not in clip or "in_ms" not in clip:
        raise ValueError("STUDIO_TIMELINE_EDIT_CLIP_FIELDS_INVALID")
    span = _integer(clip["out_ms"]) - _integer(clip["in_ms"])
    numerator, denominator = clip.get("speed_num", 1), clip.get("speed_den", 1)
    if (type(numerator) is not int or type(denominator) is not int or not 1 <= numerator <= 4
            or not 1 <= denominator <= 4 or span <= 0 or span * denominator % numerator):
        raise ValueError("STUDIO_TIMELINE_EDIT_FRACTIONAL_MS")
    return span * denominator // numerator


def apply_timeline_edits(timeline, operations):
    """Apply one closed batch to a detached normalized document, then validate.

    Intermediate states may overlap during an explicit two-clip move or track
    reorder. Only the final state is admitted. A failed batch writes nothing.
    IDs are author-supplied and stable; edits never create tasks or assets.
    """
    result = deepcopy(normalize_studio_timeline(timeline))
    if not isinstance(operations, list) or not 1 <= len(operations) <= 40:
        raise ValueError("STUDIO_TIMELINE_EDIT_OPERATION_LIMIT")
    if len(json.dumps(operations, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 128_000:
        raise ValueError("STUDIO_TIMELINE_EDIT_BYTES_LIMIT")

    def track(identity):
        _id(identity)
        rows = [row for row in result["tracks"] if row["id"] == identity]
        if len(rows) != 1:
            raise ValueError("STUDIO_TIMELINE_EDIT_TRACK_NOT_FOUND")
        return rows[0]

    def locate(identity):
        _id(identity)
        rows = [(row, clip) for row in result["tracks"] for clip in row["clips"] if clip["id"] == identity]
        if len(rows) != 1:
            raise ValueError("STUDIO_TIMELINE_EDIT_CLIP_NOT_FOUND")
        return rows[0]

    def shift(row, boundary, delta, excluding):
        for clip in row["clips"]:
            if clip["id"] != excluding and clip["start_ms"] >= boundary:
                clip["start_ms"] += delta

    for raw in operations:
        if not isinstance(raw, dict):
            raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
        operation = raw.get("op")
        if not isinstance(operation, str):
            raise ValueError("STUDIO_TIMELINE_EDIT_OPERATION_UNSUPPORTED")
        if operation == "canvas.update":
            body = _fields(raw, ("op", "changes"))
            changes = _fields(body["changes"], (), ("duration_ms", "width", "height", "fps", "schema_version"))
            if not changes:
                raise ValueError("STUDIO_TIMELINE_EDIT_EMPTY")
            # Explicit upgrade only; newer editing fields are never injected
            # into existing saved timelines by an implicit normalization step.
            if "schema_version" in changes and changes["schema_version"] != 2:
                raise ValueError("STUDIO_TIMELINE_EDIT_SCHEMA_UPGRADE_REQUIRED")
            result.update(deepcopy(changes))
        elif operation == "track.insert":
            body = _fields(raw, ("op", "track"))
            _fields(body["track"], ("id", "kind", "order", "clips"), ("muted", "gain_db", "role"))
            _id(body["track"]["id"])
            if not isinstance(body["track"]["clips"], list) or body["track"]["clips"]:
                raise ValueError("STUDIO_TIMELINE_EDIT_INSERT_EMPTY_TRACK_REQUIRED")
            result["tracks"].append(deepcopy(body["track"]))
        elif operation == "track.remove":
            body = _fields(raw, ("op", "track_id", "remove_clips"))
            row = track(body["track_id"])
            if type(body["remove_clips"]) is not bool or row["clips"] and not body["remove_clips"]:
                raise ValueError("STUDIO_TIMELINE_EDIT_TRACK_DELETE_CONFIRMATION_REQUIRED")
            result["tracks"].remove(row)
        elif operation == "track.update":
            body = _fields(raw, ("op", "track_id", "changes"))
            changes = _fields(body["changes"], (), ("muted", "gain_db", "role"))
            if not changes:
                raise ValueError("STUDIO_TIMELINE_EDIT_EMPTY")
            track(body["track_id"]).update(deepcopy(changes))
        elif operation == "track.reorder":
            body = _fields(raw, ("op", "track_ids"))
            identities = body["track_ids"]
            if (not isinstance(identities, list) or any(not isinstance(item, str) for item in identities)
                    or len(identities) != len(result["tracks"]) or len(set(identities)) != len(identities)
                    or set(identities) != {row["id"] for row in result["tracks"]}):
                raise ValueError("STUDIO_TIMELINE_EDIT_TRACK_ORDER_INVALID")
            for order, identity in enumerate(identities):
                track(identity)["order"] = order
        elif operation == "clip.insert":
            body = _fields(raw, ("op", "track_id", "clip"))
            _fields(body["clip"], ("id", "source_snapshot", "start_ms", "in_ms", "out_ms"),
                ("x", "y", "width", "height", "speed_num", "speed_den", "opacity", "gain_db", "muted", "include_audio", "fade_in_ms", "fade_out_ms"))
            _id(body["clip"]["id"])
            _integer(body["clip"]["start_ms"])
            _duration(body["clip"])
            track(body["track_id"])["clips"].append(deepcopy(body["clip"]))
        elif operation == "clip.update":
            body = _fields(raw, ("op", "clip_id", "changes"))
            changes = _fields(body["changes"], (), ("source_snapshot", "start_ms", "in_ms", "out_ms", "x", "y", "width", "height",
                "speed_num", "speed_den", "opacity", "gain_db", "muted", "include_audio", "fade_in_ms", "fade_out_ms"))
            if not changes:
                raise ValueError("STUDIO_TIMELINE_EDIT_EMPTY")
            for key in ("start_ms", "in_ms", "out_ms", "x", "y", "width", "height", "speed_num", "speed_den", "fade_in_ms", "fade_out_ms"):
                if key in changes:
                    _integer(changes[key])
            locate(body["clip_id"])[1].update(deepcopy(changes))
        elif operation == "clip.remove":
            body = _fields(raw, ("op", "clip_id", "ripple"))
            row, clip = locate(body["clip_id"])
            if type(body["ripple"]) is not bool:
                raise ValueError("STUDIO_TIMELINE_EDIT_BOOLEAN_INVALID")
            if body["ripple"]:
                shift(row, clip["start_ms"] + _duration(clip), -_duration(clip), clip["id"])
            row["clips"].remove(clip)
        elif operation == "clip.move":
            body = _fields(raw, ("op", "clip_id", "track_id", "start_ms"))
            row, clip = locate(body["clip_id"])
            target = track(body["track_id"])
            if target["kind"] != row["kind"]:
                raise ValueError("STUDIO_TIMELINE_EDIT_MOVE_KIND_INVALID")
            row["clips"].remove(clip)
            clip["start_ms"] = _integer(body["start_ms"])
            target["clips"].append(clip)
        elif operation == "clip.duplicate":
            body = _fields(raw, ("op", "clip_id", "new_clip_id", "track_id", "start_ms"))
            row, clip = locate(body["clip_id"])
            target = track(body["track_id"])
            if target["kind"] != row["kind"]:
                raise ValueError("STUDIO_TIMELINE_EDIT_MOVE_KIND_INVALID")
            copied = deepcopy(clip)
            copied.update(id=_id(body["new_clip_id"]), start_ms=_integer(body["start_ms"]))
            target["clips"].append(copied)
        elif operation == "clip.split":
            body = _fields(raw, ("op", "clip_id", "at_ms", "new_clip_id"))
            row, clip = locate(body["clip_id"])
            offset = _integer(body["at_ms"]) - clip["start_ms"]
            if not 0 < offset < _duration(clip):
                raise ValueError("STUDIO_TIMELINE_EDIT_SPLIT_OUTSIDE_CLIP")
            numerator, denominator = clip.get("speed_num", 1), clip.get("speed_den", 1)
            if offset * numerator % denominator:
                raise ValueError("STUDIO_TIMELINE_EDIT_FRACTIONAL_MS")
            cut = clip["in_ms"] + offset * numerator // denominator
            copied = deepcopy(clip)
            copied.update(id=_id(body["new_clip_id"]), start_ms=body["at_ms"], in_ms=cut)
            if isinstance(clip.get("source_snapshot"), dict) and clip["source_snapshot"].get("asset_kind") == "image":
                copied.update(in_ms=0, out_ms=clip["out_ms"] - offset)
            clip["out_ms"] = cut
            if "fade_out_ms" in clip:
                clip["fade_out_ms"] = 0
            if "fade_in_ms" in copied:
                copied["fade_in_ms"] = 0
            row["clips"].append(copied)
        elif operation == "clip.trim":
            body = _fields(raw, ("op", "clip_id", "in_ms", "out_ms", "ripple"))
            row, clip = locate(body["clip_id"])
            if type(body["ripple"]) is not bool:
                raise ValueError("STUDIO_TIMELINE_EDIT_BOOLEAN_INVALID")
            previous = _duration(clip)
            clip.update(in_ms=_integer(body["in_ms"]), out_ms=_integer(body["out_ms"]))
            if body["ripple"]:
                shift(row, clip["start_ms"] + previous, _duration(clip) - previous, clip["id"])
        elif operation == "clip.slip":
            body = _fields(raw, ("op", "clip_id", "offset_ms"))
            _, clip = locate(body["clip_id"])
            _duration(clip)
            if not isinstance(clip.get("source_snapshot"), dict) or clip["source_snapshot"].get("asset_kind") == "image":
                raise ValueError("STUDIO_TIMELINE_EDIT_STILL_SLIP_INVALID")
            delta = _integer(body["offset_ms"])
            clip.update(in_ms=clip["in_ms"] + delta, out_ms=clip["out_ms"] + delta)
        elif operation in {"caption.insert", "caption.update", "caption.remove"}:
            required = ("op", "caption") if operation == "caption.insert" else ("op", "index", "caption") if operation == "caption.update" else ("op", "index")
            body = _fields(raw, required)
            if operation == "caption.insert":
                result["captions"].append(deepcopy(body["caption"]))
            else:
                index = _integer(body["index"])
                if not 0 <= index < len(result["captions"]):
                    raise ValueError("STUDIO_TIMELINE_EDIT_CAPTION_NOT_FOUND")
                if operation == "caption.update":
                    result["captions"][index] = deepcopy(body["caption"])
                else:
                    result["captions"].pop(index)
        else:
            raise ValueError("STUDIO_TIMELINE_EDIT_OPERATION_UNSUPPORTED")
    return normalize_studio_timeline(result)
