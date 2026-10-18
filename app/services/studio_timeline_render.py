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
        return normalize_timeline_v2(value, audio_only=value.get("schema_version") == 3)
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


def validate_source_crop(clip, source_width, source_height):
    """Compare closed integer crop to actually decoded/probed coded pixels.

    Callers must supply dimensions from the original validated source bytes,
    never from an author/client claim or the output canvas.
    """
    crop = clip.get("crop")
    if crop is None:
        return
    crop = _object(crop, ("x", "y", "width", "height"), ("x", "y", "width", "height"))
    _integer(crop["x"], 0, 32767); _integer(crop["y"], 0, 32767)
    _integer(crop["width"], 1, 32768); _integer(crop["height"], 1, 32768)
    if (type(source_width) is not int or type(source_height) is not int
            or source_width < 1 or source_height < 1
            or crop["x"] + crop["width"] > source_width or crop["y"] + crop["height"] > source_height):
        raise ValueError("STUDIO_TIMELINE_CROP_OUTSIDE_SOURCE")


def _overlay_video(filters, video, label, clip, finish, output):
    placement = _seconds(clip["start_ms"])
    filters.append(f"[{video}][{label}]overlay=x={clip['x']}:y={clip['y']}:eof_action=pass:repeatlast=0:"
                   f"enable='gte(t,{placement})*lt(t,{_seconds(finish)})'[{output}]")
    return output


def _dissolve_track(filters, video, visuals):
    """Compile bounded adjacent groups using real two-input linear xfade.

    Premultiplication keeps transparent letterboxing correct while blending;
    the common author opacity is applied once after unpremultiplication. All
    source crops, source speed and geometry are compiled before this step.
    """
    labels = {clip["id"]: (clip, label, index) for clip, label, index in visuals}
    position = 0
    while position < len(visuals):
        first, label, source_index = visuals[position]
        last = first
        if first.get("transition_out"):
            while last.get("transition_out"):
                transition = last["transition_out"]
                right, right_label, right_index = labels[transition["to_clip_id"]]
                merged = f"vxf{right_index}"
                offset = right["start_ms"] - first["start_ms"]
                filters.append(f"[{label}][{right_label}]xfade=transition=fade:"
                    f"duration={_seconds(transition['duration_ms'])}:offset={_seconds(offset)}[{merged}]")
                label, last = merged, right
                position += 1
            finished = f"vxd{source_index}"
            span = last["start_ms"] + clip_duration_ms(last) - first["start_ms"]
            filters.append(f"[{label}]trim=duration={_seconds(span)},unpremultiply=inplace=1,"
                f"format=rgba,colorchannelmixer=aa={first['opacity']:.8f},"
                f"setpts=PTS+{_seconds(first['start_ms'])}/TB[{finished}]")
            label = finished
        video = _overlay_video(filters, video, label, first,
            last["start_ms"] + clip_duration_ms(last), f"vo{source_index}")
        position += 1
    return video


def render_studio_timeline(timeline, *, source_guard, guard, max_bytes, export_profile=None):
    """Decode exact server bytes and return an actually validated local export.

    source_guard(snapshot) rechecks scope/version/hash and returns data, measured,
    snapshot and original row. No callback is invoked under an assembly lock.
    """
    from .studio_timeline_export import compiler_profile, require_encoders, probe_media_file, prove_output, run_guarded_process, validate_export_admission
    timeline = normalize_studio_timeline(timeline)
    if not callable(source_guard) or not callable(guard):
        raise ValueError("STUDIO_TIMELINE_SOURCE_GUARD_REQUIRED")
    decoder = shutil.which("ffmpeg")
    if not decoder:
        raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED")
    _integer(max_bytes, 1, 25 * 1024 * 1024)
    audio_only = timeline.get("schema_version") == 3
    profile = {"preset": "AUDIO_WAV_PCM16" if audio_only else "REVIEW_MP4"} if export_profile is None else export_profile
    validate_export_admission(timeline, profile, max_bytes)
    compiled = compiler_profile(profile,
                                duration_ms=timeline["duration_ms"], max_bytes=max_bytes)
    enriched = timeline.get("schema_version") in (2, 3)
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
        measured = inspect_image(data) if snapshot["asset_kind"] == "image" else inspect_media(data, snapshot["asset_kind"], guard=guard)
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
        dimensions = {}
        for track in timeline["tracks"]:
            for clip in track["clips"]:
                if "crop" not in clip:
                    continue
                identity = clip["source_snapshot"]["id"]
                if identity not in dimensions:
                    if clip["source_snapshot"]["asset_kind"] == "image":
                        measured = verified[identity]["measured"]
                        dimensions[identity] = (measured.get("width"), measured.get("height"))
                    else:
                        # The actual pinned source file is probed once. No
                        # author-supplied source dimensions are accepted.
                        probe = probe_media_file(files[identity], guard=guard)
                        streams = [stream for stream in probe["streams"]
                            if isinstance(stream, dict) and stream.get("codec_type") == "video"]
                        if not streams:
                            raise MediaValidationError("STUDIO_TIMELINE_CROP_VIDEO_STREAM_REQUIRED")
                        dimensions[identity] = (streams[0].get("width"), streams[0].get("height"))
                validate_source_crop(clip, *dimensions[identity])
                guard()
        require_encoders(decoder, compiled, cwd=directory, guard=guard)
        audio_sources = {clip["source_snapshot"]["id"] for track in timeline["tracks"] for clip in track["clips"]
                         if clip.get("include_audio") and not track["muted"] and not clip.get("muted", False)}
        for identity in sorted(audio_sources):
            probe = probe_media_file(files[identity], guard=guard)
            if not any(isinstance(stream, dict) and stream.get("codec_type") == "audio" for stream in probe["streams"]):
                raise MediaValidationError("STUDIO_TIMELINE_VIDEO_AUDIO_STREAM_REQUIRED")
        duration = _seconds(timeline["duration_ms"])
        command = [decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "1"]
        filters = [f"anullsrc=r=48000:cl=stereo,atrim=duration={duration}[abase]"]
        if not audio_only:
            command += ["-f", "lavfi", "-i", f"color=c=black:s={timeline['width']}x{timeline['height']}:r={timeline['fps']}:d={duration}"]
            filters.insert(0, "[0:v]setpts=PTS-STARTPTS[vbase]")
        video, audio, index = "vbase", ["abase"], 0 if audio_only else 1
        transition_proof = []
        for track in timeline["tracks"]:
            transitions = {clip["id"]: clip["transition_out"] for clip in track["clips"] if "transition_out" in clip}
            incoming = {item["to_clip_id"]: item["duration_ms"] for item in transitions.values()}
            participants = set(transitions) | set(incoming)
            visuals = []
            if not track["muted"]:
                for clip in track["clips"]:
                    if clip["id"] in transitions:
                        item = transitions[clip["id"]]
                        transition_proof.append({"track_id": track["id"], "from_clip_id": clip["id"],
                            "to_clip_id": item["to_clip_id"], "kind": "CROSS_DISSOLVE", "duration_ms": item["duration_ms"],
                            "start_ms": clip["start_ms"] + clip_duration_ms(clip) - item["duration_ms"],
                            "end_ms": clip["start_ms"] + clip_duration_ms(clip)})
            for clip in track["clips"]:
                if track["muted"] or clip.get("muted", False):
                    continue
                command += ["-threads", "1", "-protocol_whitelist", "file,pipe"]
                if "crop" in clip:
                    # Optional crop uses coded-source pixel coordinates. Do
                    # not silently rotate the decoder frame before applying
                    # this exact rectangle; untouched inputs keep old behavior.
                    command += ["-noautorotate"]
                if clip["source_snapshot"]["asset_kind"] == "image":
                    command += ["-loop", "1", "-framerate", str(timeline["fps"]), "-t", _seconds(clip_duration_ms(clip))]
                command += ["-i", str(files[clip["source_snapshot"]["id"]])]
                start, end, placement = _seconds(clip["in_ms"]), _seconds(clip["out_ms"]), _seconds(clip["start_ms"])
                if track["kind"] == "VIDEO":
                    label, output = f"vc{index}", f"vo{index}"
                    if enriched:
                        visual = f"[{index}:v:0]trim=start={start}:end={end},setpts=(PTS-STARTPTS)*{clip['speed_den']}/{clip['speed_num']},"
                        if "crop" in clip:
                            crop = clip["crop"]
                            visual += f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']}:exact=1,"
                        visual += (f"scale={clip['width']}:{clip['height']}:force_original_aspect_ratio=decrease,"
                            f"format=rgba,pad={clip['width']}:{clip['height']}:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,fps={timeline['fps']},")
                        if clip["id"] in participants:
                            # Both inputs have the exact same planar alpha
                            # format, CFR and timebase required by xfade. One
                            # frame of bounded tail padding covers decode edge
                            # rounding; it never extends the authored interval.
                            visual += (f"settb=AVTB,setpts=PTS-STARTPTS,format=gbrap,premultiply=inplace=1,"
                                f"tpad=stop_mode=clone:stop_duration={_seconds(math.ceil(1000 / timeline['fps']))},"
                                f"trim=duration={_seconds(clip_duration_ms(clip))}")
                            filters.append(visual + f"[{label}]")
                        else:
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
                    if transitions:
                        visuals.append((clip, label, index))
                    else:
                        video = _overlay_video(filters, video, label, clip,
                            clip["start_ms"] + clip_duration_ms(clip), output)
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
                        # Video source audio follows the exact visual overlap.
                        # Missing/unselected audio means silence on that side;
                        # independent AUDIO tracks retain their own envelopes.
                        if clip["id"] in incoming:
                            mix += f",afade=t=in:st=0:d={_seconds(incoming[clip['id']])}:curve=tri"
                        if clip["id"] in transitions:
                            window = transitions[clip["id"]]["duration_ms"]
                            mix += f",afade=t=out:st={_seconds(clip_duration_ms(clip)-window)}:d={_seconds(window)}:curve=tri"
                    else:
                        mix += f",volume={track['gain_db']:.4f}dB"
                    filters.append(mix + f",adelay=delays={clip['start_ms']}|{clip['start_ms']}[{label}]")
                    audio.append(label)
                index += 1
            if transitions and not track["muted"]:
                video = _dissolve_track(filters, video, visuals)
        if timeline.get("captions"):
            captions = directory / "captions.srt"
            captions.write_text("\n\n".join(f"{number}\n{_cue_time(cue['start_ms'])} --> {_cue_time(cue['end_ms'])}\n{cue['text']}"
                                              for number, cue in enumerate(timeline["captions"], 1)) + "\n", encoding="utf-8")
            filters.append(f"[{video}]subtitles=filename=captions.srt:charenc=UTF-8[vcaption]"); video = "vcaption"
        # Preserve the historical video filter byte-for-byte. Audio-only WAV
        # compensates limiter delay and disables auto boost so authored gain
        # and placement are retained for samples below the safety ceiling.
        limiter = "alimiter=limit=0.95:level=0:latency=1" if audio_only else "alimiter=limit=0.95"
        filters.append("".join(f"[{label}]" for label in audio)
                       + f"amix=inputs={len(audio)}:duration=first:dropout_transition=0:normalize=0,{limiter}[aout]")
        output = directory / ("timeline." + compiled["extension"])
        command += ["-filter_complex_threads", "1", "-filter_complex", ";".join(filters)]
        if not audio_only:
            command += ["-map", f"[{video}]"]
        command += ["-map", "[aout]", "-t", duration, *compiled["options"]]
        if not audio_only:
            command += ["-pix_fmt", "yuv420p", "-r", str(timeline["fps"])]
        command += ["-ar", "48000", "-ac", "2", "-threads", "1", "-fs", str(max_bytes + 1), "-y", str(output)]
        guard()
        sources_current()
        run_guarded_process(command, cwd=directory, guard=guard, timeout=RENDER_TIMEOUT_SECONDS)
        if not output.is_file() or output.stat().st_size > max_bytes:
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_BYTES_LIMIT")
        data = output.read_bytes()
        measured = inspect_media(data, "audio" if audio_only else "video", guard=guard)
        audio_measurement = measured if audio_only else inspect_media(data, "audio", guard=guard)
        tolerance = 1 if audio_only else max(100, math.ceil(2000 / timeline["fps"]))
        if (abs(measured["duration_ms"] - timeline["duration_ms"]) > tolerance
                or abs(audio_measurement["duration_ms"] - timeline["duration_ms"]) > tolerance):
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_DURATION_MISMATCH")
        output_proof = prove_output(output, timeline, compiled, guard=guard)
        guard()
        sources_current()
        measured.update(**output_proof, audio_policy="STEREO_48000_MIX",
                        render_profile="STUDIO_MULTITRACK_LOCAL_FFMPEG", model_called=False, byte_count=len(data))
        if transition_proof:
            measured.update(video_transition_policy="PREMULTIPLIED_ALPHA_LINEAR_CROSS_DISSOLVE",
                video_audio_transition_policy="LINEAR_SELECTED_VIDEO_AUDIO_SILENCE_FOR_UNSELECTED",
                transition_windows=transition_proof)
        if export_profile is not None:
            measured.update(export_profile=copy.deepcopy(compiled["profile"]),
                            render_profile="STUDIO_MULTITRACK_LOCAL_FFMPEG_" + compiled["profile"]["preset"])
        return data, measured
