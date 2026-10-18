"""Closed export profiles and bounded native process/output proof.

These functions run only during an explicitly authorized original timeline
execution. They accept server-built commands and temporary paths, never client
executables, paths, filter strings or arbitrary codec options.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from ..media_files import MediaValidationError

EXPORT_PRESETS = ("REVIEW_MP4", "DELIVERY_H264_MP4", "DELIVERY_VP9_WEBM", "AUDIO_WAV_PCM16")


def normalize_export_profile(value):
    if not isinstance(value, dict) or set(value) - {"preset", "video_bitrate_kbps", "audio_bitrate_kbps", "crf"}:
        raise ValueError("STUDIO_TIMELINE_EXPORT_PROFILE_INVALID")
    preset = value.get("preset")
    if preset not in EXPORT_PRESETS:
        raise ValueError("STUDIO_TIMELINE_EXPORT_PRESET_INVALID")
    if preset in {"REVIEW_MP4", "AUDIO_WAV_PCM16"}:
        if set(value) != {"preset"}:
            raise ValueError("STUDIO_TIMELINE_REVIEW_PROFILE_OPTIONS_INVALID")
        return {"preset": preset}
    video = value.get("video_bitrate_kbps", 4000 if preset == "DELIVERY_H264_MP4" else 2000)
    audio = value.get("audio_bitrate_kbps", 192 if preset == "DELIVERY_H264_MP4" else 128)
    crf = value.get("crf", 20 if preset == "DELIVERY_H264_MP4" else 30)
    if (type(video) is not int or not 100 <= video <= 20_000 or type(audio) is not int or not 32 <= audio <= 320
            or type(crf) is not int or not 0 <= crf <= (51 if preset == "DELIVERY_H264_MP4" else 63)):
        raise ValueError("STUDIO_TIMELINE_EXPORT_QUALITY_INVALID")
    return {"preset": preset, "video_bitrate_kbps": video, "audio_bitrate_kbps": audio, "crf": crf}


def export_profile_digest(profile):
    profile = normalize_export_profile(profile)
    return hashlib.sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def export_profile_kind(profile):
    """Output kind is derived only from the exact closed export profile."""
    return "audio" if normalize_export_profile(profile)["preset"] == "AUDIO_WAV_PCM16" else "video"


def bound_timeline_output_kind(context):
    """Validate the original immutable binding before candidate/review/recovery.

    Receipts predating explicit export profiles retain their video-only meaning.
    A caller's measured kind or arbitrary candidate kind never changes it.
    """
    profile = context.get("export_profile")
    if profile is None:
        if "export_profile" in context or "export_profile_digest" in context:
            raise ValueError("STUDIO_TIMELINE_EXPORT_CONTEXT_CHANGED")
        return "video"
    normalized = normalize_export_profile(profile)
    if normalized != profile or context.get("export_profile_digest") != export_profile_digest(profile):
        raise ValueError("STUDIO_TIMELINE_EXPORT_CONTEXT_CHANGED")
    return export_profile_kind(normalized)


def compiler_profile(profile, *, duration_ms, max_bytes):
    """Compile a closed encoder profile; reject delivery capacity beforehand.

    Delivery bitrates are ceilings, never silently lowered to fit an Asset.
    REVIEW_MP4 intentionally retains the original bounded review policy.
    """
    profile = normalize_export_profile(profile)
    if type(duration_ms) is not int or duration_ms < 1 or type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("STUDIO_TIMELINE_EXPORT_CAPACITY_INVALID")
    preset = profile["preset"]
    if preset == "AUDIO_WAV_PCM16":
        # Integer ms at 48 kHz gives an exact sample count. The closed bitexact
        # PCM16 stereo WAV consists of a 44-byte header plus uncompressed data.
        samples = duration_ms * 48
        estimate = 44 + samples * 2 * 2
        if estimate > max_bytes:
            raise ValueError("STUDIO_TIMELINE_EXPORT_BYTES_BUDGET_EXCEEDED")
        return {"profile": profile, "extension": "wav", "mime": "audio/wav", "video_codec": None,
                "audio_codec": "pcm_s16le", "encoder": "pcm_s16le", "audio_encoder": "pcm_s16le",
                "options": ["-vn", "-c:a", "pcm_s16le", "-map_metadata", "-1", "-fflags", "+bitexact"],
                "estimated_max_bytes": estimate, "sample_count": samples}
    if preset == "REVIEW_MP4":
        bitrate = max(100_000, min(8_000_000, int(max_bytes * 8 * 0.85 / (duration_ms / 1000)) - 96_000))
        return {"profile": profile, "extension": "mp4", "mime": "video/mp4", "video_codec": "mpeg4", "audio_codec": "aac",
                "encoder": "mpeg4", "audio_encoder": "aac", "options": ["-c:v", "mpeg4", "-b:v", str(bitrate),
                "-c:a", "aac", "-b:a", "96000"], "estimated_max_bytes": None}
    video, audio = profile["video_bitrate_kbps"] * 1000, profile["audio_bitrate_kbps"] * 1000
    # Explicit conservative mux/headroom admission, alongside final byte proof.
    estimate = math.ceil(duration_ms * (video + audio) / 8000 * 1.10) + 128_000
    if estimate > max_bytes:
        raise ValueError("STUDIO_TIMELINE_EXPORT_BYTES_BUDGET_EXCEEDED")
    if preset == "DELIVERY_H264_MP4":
        return {"profile": profile, "extension": "mp4", "mime": "video/mp4", "video_codec": "h264", "audio_codec": "aac",
                "encoder": "libx264", "audio_encoder": "aac", "options": ["-c:v", "libx264", "-preset", "medium",
                "-crf", str(profile["crf"]), "-maxrate", str(video), "-bufsize", str(video * 2), "-c:a", "aac",
                "-b:a", str(audio), "-movflags", "+faststart"], "estimated_max_bytes": estimate}
    return {"profile": profile, "extension": "webm", "mime": "video/webm", "video_codec": "vp9", "audio_codec": "opus",
            "encoder": "libvpx-vp9", "audio_encoder": "libopus", "options": ["-c:v", "libvpx-vp9", "-deadline", "good",
            "-cpu-used", "2", "-crf", str(profile["crf"]), "-b:v", str(video), "-maxrate", str(video),
            "-bufsize", str(video * 2), "-c:a", "libopus", "-b:a", str(audio)], "estimated_max_bytes": estimate}


def validate_export_admission(timeline, profile, max_bytes):
    """Pure preview admission; no tools, source reads or native processes."""
    from .studio_timeline_render import normalize_studio_timeline
    timeline = normalize_studio_timeline(timeline)
    if type(max_bytes) is not int or not 1 <= max_bytes <= 25 * 1024 * 1024:
        raise ValueError("STUDIO_TIMELINE_EXPORT_CAPACITY_INVALID")
    if (timeline.get("schema_version") == 3) != (export_profile_kind(profile) == "audio"):
        raise ValueError("STUDIO_TIMELINE_EXPORT_MEDIA_KIND_MISMATCH")
    compiled = compiler_profile(profile, duration_ms=timeline["duration_ms"], max_bytes=max_bytes)
    return {key: compiled[key] for key in ("profile", "extension", "mime", "estimated_max_bytes")}


# Bounds apply while the child is running, not only when reading its result.
_PROCESS_STDOUT_LIMIT = 1_048_576
_PROCESS_STDERR_LIMIT = 65_536
_PROCESS_READ_BYTES = 65_536
_PROCESS_POLL_SECONDS = 0.025


def _windows_pipe_available(stream):
    """Peek a Windows anonymous pipe without blocking (including Python 3.11).

    select() cannot poll these handles and Windows os.set_blocking(pipe) needs
    Python 3.12. A sized HANDLE also avoids truncating handles on 64-bit hosts.
    """
    import ctypes
    from ctypes import wintypes
    import msvcrt

    peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
    peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                     wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPDWORD]
    peek.restype = wintypes.BOOL
    available = wintypes.DWORD()
    if not peek(msvcrt.get_osfhandle(stream.fileno()), None, 0, None, ctypes.byref(available), None):
        error = ctypes.get_last_error()
        if error in (109, 232):  # ERROR_BROKEN_PIPE / ERROR_NO_DATA: writer closed.
            return -1
        raise ctypes.WinError(error)
    return available.value


def _read_process_pipe(stream):
    """Return one bounded chunk, None if idle, or b"" at EOF; never wait."""
    size = _PROCESS_READ_BYTES
    if os.name == "nt":
        available = _windows_pipe_available(stream)
        if available < 0:
            return b""
        if available == 0:
            return None
        size = min(size, available)
    try:
        return os.read(stream.fileno(), size)
    except BlockingIOError:
        return None


def _reap_guarded_process(process):
    if process.poll() is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass  # The child can exit between poll() and terminate().
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
    else:
        process.wait()


def run_guarded_process(command, *, cwd, guard, timeout, stdout_path=None):
    """Drain only the original server-built process under its execution fence.

    Unused stdout goes directly to DEVNULL. Captured stdout is written by this
    owner, never beyond 1 MiB; stderr retains only its original 64 KiB private
    diagnostic prefix and drains the rest without disk storage. Both streams
    drain fairly in fixed-size chunks, including after exit, under the same
    cancellation/deadline checks. No reader threads can outlive the execution.
    """
    guard()
    target = None
    process = None
    reaped = False
    stderr = bytearray()
    try:
        if stdout_path is not None:
            target = open(stdout_path, "wb")
        process = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if target is not None else subprocess.DEVNULL,
            stderr=subprocess.PIPE, shell=False, bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + timeout
        streams = [stream for stream in (process.stdout, process.stderr) if stream is not None]
        if os.name != "nt":
            for stream in streams:
                os.set_blocking(stream.fileno(), False)
        stdout_size = 0
        while True:
            guard()
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            progressed = False
            for stream in tuple(streams):
                chunk = _read_process_pipe(stream)
                if chunk is None:
                    continue
                if not chunk:
                    streams.remove(stream)
                    continue
                progressed = True
                if stream is process.stderr:
                    stderr.extend(chunk[:max(0, _PROCESS_STDERR_LIMIT - len(stderr))])
                else:
                    remaining = _PROCESS_STDOUT_LIMIT - stdout_size
                    target.write(chunk[:remaining])
                    stdout_size += min(len(chunk), remaining)
                    if len(chunk) > remaining:
                        raise MediaValidationError("STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT")
            # A fast-exiting child must still have its complete pipes checked.
            # Inherited writers cannot keep a drain alive beyond the deadline.
            if process.poll() is not None and not streams:
                break
            if not progressed:
                time.sleep(min(_PROCESS_POLL_SECONDS, max(0, deadline - time.monotonic())))
        guard()
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, stderr=bytes(stderr))
    finally:
        try:
            if process is not None:
                _reap_guarded_process(process)
                reaped = True
        finally:
            try:
                if process is not None:
                    try:
                        if process.stdout is not None:
                            process.stdout.close()
                    finally:
                        if process.stderr is not None:
                            process.stderr.close()
            finally:
                try:
                    if target is not None:
                        target.close()
                finally:
                    if reaped and os.name == "nt":
                        # wait() caches exit status but CPython otherwise holds
                        # this native HANDLE until Popen is garbage-collected.
                        # Guard/error tracebacks can retain Popen after exit;
                        # release our known-reaped handle before caller cleanup.
                        process._handle.Close()


def require_encoders(decoder, compiled, *, cwd, guard):
    path = Path(cwd) / "encoders.txt"
    run_guarded_process([decoder, "-nostdin", "-v", "error", "-encoders"], cwd=cwd, guard=guard, timeout=10, stdout_path=path)
    if path.stat().st_size > 1_048_576:
        raise MediaValidationError("STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT")
    # Match the encoder column, never a substring in a decoder description.
    names = {parts[1] for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
             if len(parts := line.split()) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS"}
    if compiled["encoder"] not in names or compiled["audio_encoder"] not in names:
        raise MediaValidationError("STUDIO_TIMELINE_EXPORT_ENCODER_UNAVAILABLE")


def probe_media_file(path, *, guard):
    probe = shutil.which("ffprobe")
    if not probe:
        raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED")
    path = Path(path)
    output = path.parent / (path.name + ".probe.json")
    run_guarded_process([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-print_format", "json",
        "-show_streams", "-show_format", str(path)], cwd=path.parent, guard=guard, timeout=20, stdout_path=output)
    if output.stat().st_size > 1_048_576:
        raise MediaValidationError("STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT")
    try:
        result = json.loads(output.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_PROBE_INVALID") from error
    if not isinstance(result, dict) or not isinstance(result.get("streams"), list) or not isinstance(result.get("format"), dict):
        raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_PROBE_INVALID")
    return result


def prove_output(path, timeline, compiled, *, guard):
    result = probe_media_file(path, guard=guard)
    videos = [item for item in result["streams"] if isinstance(item, dict) and item.get("codec_type") == "video"]
    audios = [item for item in result["streams"] if isinstance(item, dict) and item.get("codec_type") == "audio"]
    if compiled["profile"]["preset"] == "AUDIO_WAV_PCM16":
        import wave
        if videos or len(audios) != 1:
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_STREAMS_INVALID")
        audio = audios[0]
        try:
            with wave.open(str(path), "rb") as source:
                proof = (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes(), source.getcomptype())
            valid = (proof == (2, 2, 48000, compiled["sample_count"], "NONE")
                and audio.get("codec_name") == "pcm_s16le" and int(audio["sample_rate"]) == 48000
                and int(audio["channels"]) == 2 and result["format"].get("format_name") == "wav"
                and Path(path).stat().st_size == compiled["estimated_max_bytes"])
        except (wave.Error, EOFError, KeyError, TypeError, ValueError) as error:
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_PROBE_INVALID") from error
        if not valid:
            raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_PROFILE_MISMATCH")
        return {"audio_codec": "pcm_s16le", "sample_rate": 48000, "channels": 2,
                "sample_count": compiled["sample_count"], "bits_per_sample": 16, "container": "wav",
                "profile_validation": "NATIVE_FFPROBE_EXACT"}
    if len(videos) != 1 or len(audios) != 1:
        raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_STREAMS_INVALID")
    video, audio = videos[0], audios[0]
    try:
        numerator, denominator = (int(part) for part in video["avg_frame_rate"].split("/"))
        fps = numerator / denominator
        measured_duration = float(result["format"]["duration"]) * 1000
        rate, channels = int(audio["sample_rate"]), int(audio["channels"])
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as error:
        raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_PROBE_INVALID") from error
    formats = set(str(result["format"].get("format_name", "")).split(","))
    expected_format = "mp4" if compiled["extension"] == "mp4" else "webm"
    if (expected_format not in formats or video.get("codec_name") != compiled["video_codec"]
            or audio.get("codec_name") != compiled["audio_codec"] or video.get("width") != timeline["width"]
            or video.get("height") != timeline["height"] or video.get("pix_fmt") != "yuv420p"
            or not math.isfinite(fps) or abs(fps - timeline["fps"]) > 0.001 or rate != 48000 or channels != 2
            or not math.isfinite(measured_duration)
            or abs(measured_duration - timeline["duration_ms"]) > max(100, math.ceil(2000 / timeline["fps"]))):
        raise MediaValidationError("STUDIO_TIMELINE_OUTPUT_PROFILE_MISMATCH")
    return {"width": video["width"], "height": video["height"], "fps": fps,
            "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
            "sample_rate": rate, "channels": channels, "container": expected_format,
            "profile_validation": "NATIVE_FFPROBE_EXACT"}
