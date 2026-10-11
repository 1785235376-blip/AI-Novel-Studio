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
import tempfile

from ..media_files import MediaValidationError, inspect_media, inspect_image
from .studio_timeline_export import normalize_export_profile

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


def clip_duration_ms(clip):
    """Rational speed must resolve to exact milliseconds before editing."""
    num, den = clip.get("speed_num", 1), clip.get("speed_den", 1)
    if (type(num) is not int or not 1 <= num <= 4 or type(den) is not int or not 1 <= den <= 4
            or type(clip.get("in_ms")) is not int or type(clip.get("out_ms")) is not int):
        raise ValueError("STUDIO_TIMELINE_SPEED_INVALID")
    duration, remainder = divmod((clip["out_ms"] - clip["in_ms"]) * den, num)
    if duration < 1 or remainder:
        raise ValueError("STUDIO_TIMELINE_SPEED_REQUIRES_EXACT_MILLISECONDS")
    return duration


def normalize_studio_timeline(value):
    """Return a closed, deterministic DTO; all trim/placement times are ms.

    Video tracks overlay in ascending order. A clip's start_ms is timeline
    placement; in_ms/out_ms trim its source. Audio clips are mixed with their
    track gain/mute. Captions are literal author text, not transcription claims.
    """
    if isinstance(value, dict) and "schema_version" in value:
        from .studio_timeline_schema import normalize_timeline_v2
        return normalize_timeline_v2(value)
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
        if not isinstance(kind, str) or kind not in counts or tid in ids or order in orders:
            raise ValueError("STUDIO_TIMELINE_TRACK_ID_ORDER_KIND_INVALID")
        ids.add(tid); orders.add(order); counts[kind] += 1
        if counts[kind] > 4:
            raise ValueError("STUDIO_TIMELINE_TRACK_KIND_LIMIT")
        muted = _boolean(track.get("muted", False))
        gain = track.get("gain_db", 0.0)
        if type(gain) not in (int, float) or not -60 <= gain <= 12 or not math.isfinite(gain):
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


def render_studio_timeline(timeline, *, source_guard, guard, max_bytes, export_profile=None):
    """Decode exact server bytes and return an actually validated local export.

    source_guard(snapshot) rechecks scope/version/hash and returns data, measured,
    snapshot and original row. No callback is invoked under an assembly lock.
    """
    from .studio_timeline_export import compiler_profile, require_encoders, probe_media_file, prove_output, run_guarded_process
    timeline = normalize_studio_timeline(timeline)
    if not callable(source_guard) or not callable(guard):
        raise ValueError("STUDIO_TIMELINE_SOURCE_GUARD_REQUIRED")
    decoder = shutil.which("ffmpeg")
    if not decoder:
        raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED")
    _integer(max_bytes, 1, 25 * 1024 * 1024)
    compiled = compiler_profile({"preset": "REVIEW_MP4"} if export_profile is None else export_profile,
                                duration_ms=timeline["duration_ms"], max_bytes=max_bytes)
    enriched = timeline.get("schema_version") == 2
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
        measured = inspect_image(data) if snapshot["asset_kind"] == "image" else inspect_media(data, snapshot["asset_kind"])
        verified[snapshot["id"]] = {"data": data, "measured": measured}
    for track in timeline["tracks"]:
        for clip in track["clips"]:
            if (clip["source_snapshot"]["asset_kind"] != "image"
                    and clip["out_ms"] > verified[clip["source_snapshot"]["id"]]["measured"]["duration_ms"]):
                raise ValueError("STUDIO_TIMELINE_TRIM_OUTSIDE_SOURCE")
    def sources_current():
        for snapshot in studio_sources(timeline):
            resolved = source_guard(copy.deepcopy(snapshot))
            if (not isinstance(resolved, dict) or resolved.get("snapshot") != snapshot
                    or not isinstance(resolved.get("data"), bytes)
                    or hashlib.sha256(resolved["data"]).hexdigest() != snapshot["digest"]):
                raise ValueError("STUDIO_TIMELINE_SOURCE_SNAPSHOT_CHANGED")
        guard()
    guard()
    with tempfile.TemporaryDirectory(prefix="novel-studio-timeline-") as directory:
        directory = Path(directory)
        files = {}
        for index, (identity, source) in enumerate(verified.items()):
            path = directory / f"source-{index}.{source['measured']['extension']}"
            path.write_bytes(source["data"]); files[identity] = path
        require_encoders(decoder, compiled, cwd=directory, guard=guard)
        audio_sources = {clip["source_snapshot"]["id"] for track in timeline["tracks"] for clip in track["clips"]
                         if clip.get("include_audio") and not track["muted"] and not clip.get("muted", False)}
        for identity in sorted(audio_sources):
            probe = probe_media_file(files[identity], guard=guard)
            if not any(isinstance(stream, dict) and stream.get("codec_type") == "audio" for stream in probe["streams"]):
                raise MediaValidationError("STUDIO_TIMELINE_VIDEO_AUDIO_STREAM_REQUIRED")
        duration = _seconds(timeline["duration_ms"])
        command = [decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "1",
                   "-f", "lavfi", "-i", f"color=c=black:s={timeline['width']}x{timeline['height']}:r={timeline['fps']}:d={duration}"]
        filters = ["[0:v]setpts=PTS-STARTPTS[vbase]",
                   f"anullsrc=r=48000:cl=stereo,atrim=duration={duration}[abase]"]
        video, audio, index = "vbase", ["abase"], 1
        for track in timeline["tracks"]:
            for clip in track["clips"]:
                if track["muted"] or clip.get("muted", False):
                    continue
                command += ["-threads", "1", "-protocol_whitelist", "file,pipe"]
                if clip["source_snapshot"]["asset_kind"] == "image":
                    command += ["-loop", "1", "-framerate", str(timeline["fps"]), "-t", _seconds(clip_duration_ms(clip))]
                command += ["-i", str(files[clip["source_snapshot"]["id"]])]
                start, end, placement = _seconds(clip["in_ms"]), _seconds(clip["out_ms"]), _seconds(clip["start_ms"])
                if track["kind"] == "VIDEO":
                    label, output = f"vc{index}", f"vo{index}"
                    if enriched:
                        visual = (f"[{index}:v:0]trim=start={start}:end={end},setpts=(PTS-STARTPTS)*{clip['speed_den']}/{clip['speed_num']},"
                            f"scale={clip['width']}:{clip['height']}:force_original_aspect_ratio=decrease,"
                            f"format=rgba,pad={clip['width']}:{clip['height']}:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,fps={timeline['fps']},")
                        # Geometry, opacity and fades are numbers from the closed DTO.
                        visual += f"colorchannelmixer=aa={clip['opacity']:.8f}"
                        if clip["fade_in_ms"]:
                            visual += f",fade=t=in:st=0:d={_seconds(clip['fade_in_ms'])}:alpha=1"
                        if clip["fade_out_ms"]:
                            visual += f",fade=t=out:st={_seconds(clip_duration_ms(clip)-clip['fade_out_ms'])}:d={_seconds(clip['fade_out_ms'])}:alpha=1"
                        filters.append(visual + f",setpts=PTS+{placement}/TB[{label}]")
                    else:
                        filters.append(f"[{index}:v:0]trim=start={start}:end={end},setpts=PTS-STARTPTS+{placement}/TB,"
                                       f"scale={clip['width']}:{clip['height']}:force_original_aspect_ratio=decrease,"
                                       f"pad={clip['width']}:{clip['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={timeline['fps']}[{label}]")
                    finish = _seconds(clip["start_ms"] + clip_duration_ms(clip))
                    filters.append(f"[{video}][{label}]overlay=x={clip['x']}:y={clip['y']}:eof_action=pass:repeatlast=0:"
                                   f"enable='gte(t,{placement})*lt(t,{finish})'[{output}]")
                    video = output
                if track["kind"] == "AUDIO" or clip.get("include_audio", False):
                    label = f"ac{index}"
                    mix = (f"[{index}:a:0]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=48000,"
                           "aformat=sample_fmts=fltp:channel_layouts=stereo")
                    if enriched:
                        ratio = clip["speed_num"] / clip["speed_den"]
                        while ratio > 2:
                            mix += ",atempo=2"; ratio /= 2
                        while ratio < 0.5:
                            mix += ",atempo=0.5"; ratio /= 0.5
                        if ratio != 1:
                            mix += f",atempo={ratio:.12g}"
                        mix += f",volume={track['gain_db']+clip['gain_db']:.4f}dB"
                        if clip["fade_in_ms"]:
                            mix += f",afade=t=in:st=0:d={_seconds(clip['fade_in_ms'])}"
                        if clip["fade_out_ms"]:
                            mix += f",afade=t=out:st={_seconds(clip_duration_ms(clip)-clip['fade_out_ms'])}:d={_seconds(clip['fade_out_ms'])}"
                    else:
                        mix += f",volume={track['gain_db']:.4f}dB"
                    filters.append(mix + f",adelay=delays={clip['start_ms']}|{clip['start_ms']}[{label}]")
                    audio.append(label)
                index += 1
        if timeline["captions"]:
            captions = directory / "captions.srt"
            captions.write_text("\n\n".join(f"{number}\n{_cue_time(cue['start_ms'])} --> {_cue_time(cue['end_ms'])}\n{cue['text']}"
                                              for number, cue in enumerate(timeline["captions"], 1)) + "\n", encoding="utf-8")
            filters.append(f"[{video}]subtitles=filename=captions.srt:charenc=UTF-8[vcaption]"); video = "vcaption"
        filters.append("".join(f"[{label}]" for label in audio)
                       + f"amix=inputs={len(audio)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]")
        output = directory / ("timeline." + compiled["extension"])
        command += ["-filter_complex_threads", "1", "-filter_complex", ";".join(filters), "-map", f"[{video}]", "-map", "[aout]",
                    "-t", duration, *compiled["options"], "-pix_fmt", "yuv420p", "-r", str(timeline["fps"]),
                    "-ar", "48000", "-ac", "2", "-threads", "1", "-fs", str(max_bytes + 1), "-y", str(output)]
        guard()
        sources_current()
        run_guarded_process(command, cwd=directory, guard=guard, timeout=RENDER_TIMEOUT_SECONDS)
        if not output.is_file() or output.stat().st_size > max_bytes:
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_BYTES_LIMIT")
        data = output.read_bytes()
        measured = inspect_media(data, "video")
        audio_measurement = inspect_media(data, "audio")
        tolerance = max(100, math.ceil(2000 / timeline["fps"]))
        if (abs(measured["duration_ms"] - timeline["duration_ms"]) > tolerance
                or abs(audio_measurement["duration_ms"] - timeline["duration_ms"]) > tolerance):
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_DURATION_MISMATCH")
        output_proof = prove_output(output, timeline, compiled, guard=guard)
        guard()
        sources_current()
        measured.update(**output_proof, audio_policy="STEREO_48000_MIX",
                        render_profile="STUDIO_MULTITRACK_LOCAL_FFMPEG", model_called=False, byte_count=len(data))
        if export_profile is not None:
            measured.update(export_profile=copy.deepcopy(compiled["profile"]),
                            render_profile="STUDIO_MULTITRACK_LOCAL_FFMPEG_" + compiled["profile"]["preset"])
        return data, measured
