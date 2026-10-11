"""Bounded local media composition for the original VideoAssemblyService.

This is a renderer, not a provider or scheduler. The caller supplies freshly
authorized original asset snapshots and bytes; no user path, URL, executable,
filter expression, subtitle file or output destination is accepted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from ..media_files import MediaValidationError, inspect_media

MAX_DURATION_MS = 600_000
MAX_CLIPS = 30
MAX_SOURCE_BYTES = 200 * 1024 * 1024
MAX_CAPTION_CHARACTERS = 32_000
RENDER_TIMEOUT_SECONDS = 120


def _object(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("STUDIO_TIMELINE_FIELDS_INVALID")
    return value


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("STUDIO_TIMELINE_INTEGER_INVALID")
    return value


def _identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", value):
        raise ValueError("STUDIO_TIMELINE_ID_INVALID")
    return value


def _boolean(value):
    if type(value) is not bool:
        raise ValueError("STUDIO_TIMELINE_BOOLEAN_INVALID")
    return value


def timeline_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def normalize_studio_timeline(value):
    """Return a closed, deterministic DTO; all trim/placement times are ms.

    Video tracks overlay in ascending order. A clip's start_ms is timeline
    placement; in_ms/out_ms trim its source. Audio clips are mixed with their
    track gain/mute. Captions are literal author text, not transcription claims.
    """
    row = _object(value, ("duration_ms", "width", "height", "fps", "tracks", "captions"),
                  ("duration_ms", "tracks"))
    duration = _integer(row["duration_ms"], 1, MAX_DURATION_MS)
    width = _integer(row.get("width", 1280), 16, 1920)
    height = _integer(row.get("height", 720), 16, 1080)
    fps = _integer(row.get("fps", 24), 1, 60)
    if width % 2 or height % 2:
        raise ValueError("STUDIO_TIMELINE_EVEN_DIMENSIONS_REQUIRED")
    raw_tracks = row["tracks"]
    if not isinstance(raw_tracks, list) or not 1 <= len(raw_tracks) <= 8:
        raise ValueError("STUDIO_TIMELINE_TRACK_LIMIT")
    tracks, ids, orders, clip_ids, sources = [], set(), set(), set(), {}
    counts, clip_count = {"VIDEO": 0, "AUDIO": 0}, 0
    for raw in raw_tracks:
        track = _object(raw, ("id", "kind", "order", "muted", "gain_db", "clips"),
                        ("id", "kind", "order", "clips"))
        tid, kind = _identity(track["id"]), track["kind"]
        order = _integer(track["order"], 0, 7)
        if kind not in counts or tid in ids or order in orders:
            raise ValueError("STUDIO_TIMELINE_TRACK_ID_ORDER_KIND_INVALID")
        ids.add(tid); orders.add(order); counts[kind] += 1
        if counts[kind] > 4:
            raise ValueError("STUDIO_TIMELINE_TRACK_KIND_LIMIT")
        muted = _boolean(track.get("muted", False))
        gain = track.get("gain_db", 0.0)
        if type(gain) not in (int, float) or not math.isfinite(gain) or not -60 <= gain <= 12:
            raise ValueError("STUDIO_TIMELINE_AUDIO_GAIN_INVALID")
        if kind != "AUDIO" and gain != 0:
            raise ValueError("STUDIO_TIMELINE_GAIN_REQUIRES_AUDIO")
        if not isinstance(track["clips"], list) or not 1 <= len(track["clips"]) <= MAX_CLIPS:
            raise ValueError("STUDIO_TIMELINE_CLIP_LIMIT")
        clips = []
        for raw_clip in track["clips"]:
            clip = _object(raw_clip, ("id", "source_snapshot", "start_ms", "in_ms", "out_ms", "x", "y", "width", "height"),
                           ("id", "source_snapshot", "start_ms", "in_ms", "out_ms"))
            cid = _identity(clip["id"])
            if cid in clip_ids:
                raise ValueError("STUDIO_TIMELINE_CLIP_ID_DUPLICATE")
            clip_ids.add(cid); clip_count += 1
            if clip_count > MAX_CLIPS:
                raise ValueError("STUDIO_TIMELINE_CLIP_LIMIT")
            source = _object(clip["source_snapshot"], ("id", "kind", "asset_kind", "version", "digest"),
                             ("id", "kind", "asset_kind", "version", "digest"))
            snapshot = {"id": _identity(source["id"]), "kind": "ASSET", "asset_kind": kind.lower(),
                        "version": _integer(source["version"], 1, 2**53 - 1), "digest": source["digest"]}
            if (source["kind"] != "ASSET" or source["asset_kind"] != kind.lower()
                    or not isinstance(source["digest"], str) or not re.fullmatch(r"[a-f0-9]{64}", source["digest"])):
                raise ValueError("STUDIO_TIMELINE_SOURCE_INVALID")
            previous = sources.setdefault(snapshot["id"], snapshot)
            if previous != snapshot:
                raise ValueError("STUDIO_TIMELINE_SOURCE_SNAPSHOT_CONFLICT")
            placement = _integer(clip["start_ms"], 0, duration - 1)
            start = _integer(clip["in_ms"], 0, 36_000_000)
            end = _integer(clip["out_ms"], 1, 36_000_000)
            if end <= start or placement + end - start > duration:
                raise ValueError("STUDIO_TIMELINE_CLIP_RANGE_INVALID")
            item = {"id": cid, "source_snapshot": snapshot, "start_ms": placement, "in_ms": start, "out_ms": end}
            if kind == "VIDEO":
                x = _integer(clip.get("x", 0), 0, width - 16)
                y = _integer(clip.get("y", 0), 0, height - 16)
                cw = _integer(clip.get("width", width - x), 16, width - x)
                ch = _integer(clip.get("height", height - y), 16, height - y)
                if cw % 2 or ch % 2:
                    raise ValueError("STUDIO_TIMELINE_EVEN_DIMENSIONS_REQUIRED")
                item.update(x=x, y=y, width=cw, height=ch)
            elif any(key in clip for key in ("x", "y", "width", "height")):
                raise ValueError("STUDIO_TIMELINE_VIDEO_GEOMETRY_REQUIRES_VIDEO")
            clips.append(item)
        clips.sort(key=lambda item: (item["start_ms"], item["id"]))
        if kind == "VIDEO" and any(left["start_ms"] + left["out_ms"] - left["in_ms"] > right["start_ms"]
                                    for left, right in zip(clips, clips[1:])):
            raise ValueError("STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP")
        tracks.append({"id": tid, "kind": kind, "order": order, "muted": muted, "gain_db": float(gain), "clips": clips})
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
    return {"duration_ms": duration, "width": width, "height": height, "fps": fps,
            "tracks": sorted(tracks, key=lambda track: track["order"]), "captions": captions}


def studio_sources(timeline):
    sources = {}
    for track in timeline["tracks"]:
        for clip in track["clips"]:
            source = clip["source_snapshot"]
            sources[source["id"]] = copy.deepcopy(source)
    return [sources[key] for key in sorted(sources)]


def _seconds(milliseconds):
    return f"{milliseconds // 1000}.{milliseconds % 1000:03d}"


def _cue_time(milliseconds):
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def render_studio_timeline(timeline, *, source_guard, guard, max_bytes):
    """Decode exact server bytes, compose bounded tracks, return validated MP4.

    source_guard(snapshot) rechecks scope/version/hash and returns data, measured,
    snapshot and original row. No callback is invoked under an assembly lock.
    """
    timeline = normalize_studio_timeline(timeline)
    if not callable(source_guard) or not callable(guard):
        raise ValueError("STUDIO_TIMELINE_SOURCE_GUARD_REQUIRED")
    decoder = shutil.which("ffmpeg")
    if not decoder:
        raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED")
    _integer(max_bytes, 1, 25 * 1024 * 1024)
    verified, total_bytes = {}, 0
    for snapshot in studio_sources(timeline):
        guard()
        resolved = source_guard(copy.deepcopy(snapshot))
        if not isinstance(resolved, dict) or resolved.get("snapshot") != snapshot:
            raise ValueError("STUDIO_TIMELINE_SOURCE_SNAPSHOT_CHANGED")
        data, original = resolved.get("data"), resolved.get("row")
        if (not isinstance(data, bytes) or not 0 < len(data) <= max_bytes
                or hashlib.sha256(data).hexdigest() != snapshot["digest"]
                or not isinstance(original, dict) or original.get("id") != snapshot["id"]
                or original.get("version") != snapshot["version"] or original.get("sha256") != snapshot["digest"]
                or original.get("kind") != snapshot["asset_kind"] or original.get("deleted_at")):
            raise ValueError("STUDIO_TIMELINE_SOURCE_BYTES_CHANGED")
        total_bytes += len(data)
        if total_bytes > MAX_SOURCE_BYTES:
            raise ValueError("STUDIO_TIMELINE_SOURCE_BYTES_LIMIT")
        measured = inspect_media(data, snapshot["asset_kind"])
        verified[snapshot["id"]] = {"data": data, "measured": measured}
    for track in timeline["tracks"]:
        for clip in track["clips"]:
            if clip["out_ms"] > verified[clip["source_snapshot"]["id"]]["measured"]["duration_ms"]:
                raise ValueError("STUDIO_TIMELINE_TRIM_OUTSIDE_SOURCE")
    guard()
    with tempfile.TemporaryDirectory(prefix="novel-studio-timeline-") as directory:
        directory = Path(directory)
        files = {}
        for index, (identity, source) in enumerate(verified.items()):
            path = directory / f"source-{index}.{source['measured']['extension']}"
            path.write_bytes(source["data"]); files[identity] = path
        duration = _seconds(timeline["duration_ms"])
        command = [decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "1",
                   "-f", "lavfi", "-i", f"color=c=black:s={timeline['width']}x{timeline['height']}:r={timeline['fps']}:d={duration}"]
        filters = ["[0:v]setpts=PTS-STARTPTS[vbase]",
                   f"anullsrc=r=48000:cl=stereo,atrim=duration={duration}[abase]"]
        video, audio, index = "vbase", ["abase"], 1
        for track in timeline["tracks"]:
            for clip in track["clips"]:
                if track["muted"]:
                    continue
                command += ["-threads", "1", "-protocol_whitelist", "file,pipe", "-i", str(files[clip["source_snapshot"]["id"]])]
                start, end, placement = _seconds(clip["in_ms"]), _seconds(clip["out_ms"]), _seconds(clip["start_ms"])
                if track["kind"] == "VIDEO":
                    label, output = f"vc{index}", f"vo{index}"
                    filters.append(f"[{index}:v:0]trim=start={start}:end={end},setpts=PTS-STARTPTS+{placement}/TB,"
                                   f"scale={clip['width']}:{clip['height']}:force_original_aspect_ratio=decrease,"
                                   f"pad={clip['width']}:{clip['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={timeline['fps']}[{label}]")
                    finish = _seconds(clip["start_ms"] + clip["out_ms"] - clip["in_ms"])
                    filters.append(f"[{video}][{label}]overlay=x={clip['x']}:y={clip['y']}:eof_action=pass:repeatlast=0:"
                                   f"enable='gte(t,{placement})*lt(t,{finish})'[{output}]")
                    video = output
                else:
                    label = f"ac{index}"
                    filters.append(f"[{index}:a:0]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=48000,"
                                   f"aformat=sample_fmts=fltp:channel_layouts=stereo,volume={track['gain_db']:.4f}dB,"
                                   f"adelay=delays={clip['start_ms']}|{clip['start_ms']}[{label}]")
                    audio.append(label)
                index += 1
        if timeline["captions"]:
            captions = directory / "captions.srt"
            captions.write_text("\n\n".join(f"{number}\n{_cue_time(cue['start_ms'])} --> {_cue_time(cue['end_ms'])}\n{cue['text']}"
                                              for number, cue in enumerate(timeline["captions"], 1)) + "\n", encoding="utf-8")
            filters.append(f"[{video}]subtitles=filename=captions.srt:charenc=UTF-8[vcaption]"); video = "vcaption"
        filters.append("".join(f"[{label}]" for label in audio)
                       + f"amix=inputs={len(audio)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]")
        output = directory / "timeline.mp4"
        bitrate = max(100_000, min(8_000_000, int(max_bytes * 8 * 0.85 / (timeline["duration_ms"] / 1000)) - 96_000))
        command += ["-filter_complex_threads", "1", "-filter_complex", ";".join(filters), "-map", f"[{video}]", "-map", "[aout]",
                    "-t", duration, "-c:v", "mpeg4", "-b:v", str(bitrate), "-pix_fmt", "yuv420p", "-r", str(timeline["fps"]),
                    "-c:a", "aac", "-b:a", "96000", "-ar", "48000", "-ac", "2", "-fs", str(max_bytes + 1), "-y", str(output)]
        guard()
        subprocess.run(command, cwd=str(directory), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=RENDER_TIMEOUT_SECONDS, check=True, shell=False)
        if not output.is_file() or output.stat().st_size > max_bytes:
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_BYTES_LIMIT")
        data = output.read_bytes()
        measured = inspect_media(data, "video")
        audio_measurement = inspect_media(data, "audio")
        tolerance = max(100, math.ceil(2000 / timeline["fps"]))
        if (abs(measured["duration_ms"] - timeline["duration_ms"]) > tolerance
                or abs(audio_measurement["duration_ms"] - timeline["duration_ms"]) > tolerance):
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_DURATION_MISMATCH")
        guard()
        for snapshot in studio_sources(timeline):
            resolved = source_guard(copy.deepcopy(snapshot))
            if not isinstance(resolved, dict) or resolved.get("snapshot") != snapshot:
                raise ValueError("STUDIO_TIMELINE_SOURCE_SNAPSHOT_CHANGED")
        measured.update(width=timeline["width"], height=timeline["height"], fps=timeline["fps"], audio_policy="STEREO_48000_MIX",
                        render_profile="STUDIO_MULTITRACK_LOCAL_FFMPEG", model_called=False, byte_count=len(data))
        return data, measured
