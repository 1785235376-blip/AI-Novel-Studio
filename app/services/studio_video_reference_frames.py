"""Bounded, local reference previews backed by decoded source PTS, never FPS.

The intentionally limited subset is MP4/WebM, one video stream, at most 4,096
frames and 60 seconds, a conservative 1,000,000,000 decoded-pixel work
budget, strictly increasing PTS beginning at zero, constant
square-pixel dimensions, no display matrix, and the closed RGB-convertible
pixel formats below. Audio is ignored. No provider, network or model is used.

All native work belongs to the original guarded-process owner. Its captured
stdout is bounded while running; this module never lets a child write a file.
"""
from __future__ import annotations

import base64
from bisect import bisect_left
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
import zlib

from .. import media_files
from . import studio_timeline_export as native

_MAX_BYTES = 25 * 1024 * 1024
_MAX_PIXELS = 16 * 1024 * 1024
_MAX_FRAMES = 4096
_MAX_DECODED_PIXELS = 1_000_000_000
_MAX_PREVIEW_EDGE = 320
_MAX_CAPTURE = 1_048_576
_PREPARATION_SECONDS = 30
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PIXEL_FORMATS = frozenset({
    "yuv420p", "yuv422p", "yuv444p", "yuvj420p", "yuvj422p", "yuvj444p",
    "yuv420p10le", "yuv422p10le", "yuv444p10le", "yuv420p12le",
    "yuv422p12le", "yuv444p12le", "rgb24", "bgr24", "gbrp", "gray",
})
_MP4_BRANDS = frozenset({b"isom", b"iso2", b"iso3", b"iso4", b"iso5", b"iso6",
                         b"iso7", b"iso8", b"iso9", b"mp41", b"mp42", b"avc1",
                         b"dash", b"M4V ", b"MSNV"})
_PROBE_ENTRIES = (
    "format=format_name,duration,start_time:format_tags=:stream_disposition=:"
    "stream=index,codec_type,codec_name,time_base,width,height,pix_fmt,"
    "sample_aspect_ratio,start_pts,duration_ts,duration:stream_tags=rotate:"
    "stream_side_data=side_data_type,rotation,displaymatrix:"
    "frame=media_type,stream_index,pts,duration,pkt_duration,width,height,pix_fmt,sample_aspect_ratio:"
    "frame_tags=:frame_side_data=side_data_type,rotation,displaymatrix:log=level:error=code"
)


class _ReferenceError(media_files.MediaValidationError):
    pass


def _fail(code):
    raise _ReferenceError("VIDEO_REFERENCE_" + code)


def _integer(value, *, maximum=2**53 - 1):
    # Native JSON numbers and its decimal integer strings are accepted, never
    # floats/bools or unbounded numeric text. No binary floating-point timing.
    if type(value) is int:
        result = value
    elif type(value) is str and re.fullmatch(r"-?[0-9]{1,16}", value):
        result = int(value)
    else:
        _fail("PROBE_INVALID")
    if not -maximum <= result <= maximum:
        _fail("PROBE_INVALID")
    return result


def _duration(value):
    if type(value) not in (str, int) or not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,12})?", str(value)):
        _fail("PROBE_INVALID")
    result = Fraction(value)
    if not 0 < result <= 60:
        _fail("DURATION_LIMIT")
    return result


def _vint(data, offset, *, identifier=False):
    if offset >= len(data) or not data[offset]:
        _fail("CONTAINER_UNSUPPORTED")
    length = 1
    mask = 0x80
    while not data[offset] & mask:
        length += 1
        mask >>= 1
    if length > (4 if identifier else 8) or offset + length > len(data):
        _fail("CONTAINER_UNSUPPORTED")
    raw = int.from_bytes(data[offset:offset + length], "big")
    value = raw if identifier else raw & ((1 << (length * 7)) - 1)
    if not identifier and value == (1 << (length * 7)) - 1:
        _fail("CONTAINER_UNSUPPORTED")
    return value, offset + length


def _container(data):
    if len(data) >= 16 and data[4:8] == b"ftyp":
        size = int.from_bytes(data[:4], "big")
        if not 16 <= size <= min(len(data), 4096) or data[8:12] not in _MP4_BRANDS or size % 4:
            _fail("CONTAINER_UNSUPPORTED")
        return "mp4"
    if data[:4] == b"\x1aE\xdf\xa3":
        size, offset = _vint(data, 4)
        end = offset + size
        if size > 4096 or end > len(data):
            _fail("CONTAINER_UNSUPPORTED")
        document_types = []
        while offset < end:
            identifier, offset = _vint(data, offset, identifier=True)
            length, offset = _vint(data, offset)
            if offset + length > end:
                _fail("CONTAINER_UNSUPPORTED")
            if identifier == 0x4282:
                document_types.append(data[offset:offset + length])
            offset += length
        if document_types == [b"webm"]:
            return "webm"
    _fail("CONTAINER_UNSUPPORTED")


def _orientation(row):
    tags = row.get("tags", {})
    if not isinstance(tags, dict):
        _fail("PROBE_INVALID")
    if "rotate" in tags and _integer(tags["rotate"]) != 0:
        _fail("ORIENTATION_UNSUPPORTED")
    sides = row.get("side_data_list", [])
    if not isinstance(sides, list) or any(not isinstance(side, dict) for side in sides):
        _fail("PROBE_INVALID")
    for side in sides:
        # Reject matrices entirely, including a zero rotation with reflection.
        if "displaymatrix" in side or side.get("side_data_type") == "Display Matrix":
            _fail("ORIENTATION_UNSUPPORTED")
        if "rotation" in side and _integer(side["rotation"]) != 0:
            _fail("ORIENTATION_UNSUPPORTED")
    if row.get("sample_aspect_ratio") != "1:1":
        _fail("ORIENTATION_UNSUPPORTED")


def _parse_probe(data, extension):
    if len(data) > _MAX_CAPTURE:
        _fail("OUTPUT_LIMIT")
    def invalid_constant(_):
        _fail("PROBE_INVALID")
    info = json.loads(data, parse_constant=invalid_constant)
    if (not isinstance(info, dict) or not isinstance(info.get("streams"), list)
            or not isinstance(info.get("format"), dict) or not isinstance(info.get("frames"), list)):
        _fail("PROBE_INVALID")
    if "error" in info:
        _fail("DECODE_FAILED")
    streams, frames, container = info["streams"], info["frames"], info["format"]
    if len(streams) != 1 or not isinstance(streams[0], dict) or streams[0].get("codec_type") != "video":
        _fail("STREAMS_UNSUPPORTED")
    stream = streams[0]
    if type(container.get("format_name")) is not str or extension not in container["format_name"].split(","):
        _fail("CONTAINER_UNSUPPORTED")
    if not 1 <= len(frames) <= _MAX_FRAMES:
        _fail("FRAME_LIMIT")
    width, height = _integer(stream.get("width")), _integer(stream.get("height"))
    if not 1 <= width <= 4096 or not 1 <= height <= 4096 or width * height > _MAX_PIXELS:
        _fail("DIMENSION_LIMIT")
    _orientation(stream)
    if type(stream.get("pix_fmt")) is not str or stream["pix_fmt"] not in _PIXEL_FORMATS:
        _fail("PIXEL_FORMAT_UNSUPPORTED")
    time_base = stream.get("time_base")
    if type(time_base) is not str or not re.fullmatch(r"[0-9]{1,10}/[0-9]{1,10}", time_base):
        _fail("TIMING_UNSUPPORTED")
    num, den = map(int, time_base.split("/"))
    if not 1 <= num <= 2**31 - 1 or not 1 <= den <= 2**31 - 1:
        _fail("TIMING_UNSUPPORTED")
    tick = Fraction(num, den)
    stream_index = _integer(stream.get("index"))
    if stream_index < 0 or ("start_pts" in stream and _integer(stream["start_pts"]) != 0):
        _fail("TIMING_UNSUPPORTED")
    if "start_time" in container and container["start_time"] not in ("0.000000", "0", 0):
        _fail("TIMING_UNSUPPORTED")
    duration = _duration(container.get("duration"))
    if "duration_ts" in stream:
        stream_duration = _integer(stream["duration_ts"]) * tick
        if not 0 < stream_duration <= 60:
            _fail("DURATION_LIMIT")
        duration = min(duration, stream_duration)
    if "duration" in stream:
        _duration(stream["duration"])  # Also reject inconsistent over-limit metadata.
    points = []
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("media_type") != "video" or _integer(frame.get("stream_index")) != stream_index:
            _fail("PROBE_INVALID")
        if (_integer(frame.get("width")) != width or _integer(frame.get("height")) != height
                or frame.get("pix_fmt") != stream.get("pix_fmt")):
            _fail("FORMAT_CHANGED")
        _orientation(frame)
        if frame.get("logs", []) != []:
            _fail("DECODE_FAILED")
        pts = _integer(frame.get("pts"))
        if pts < 0 or (not points and pts != 0) or (points and pts <= points[-1]) or pts * tick >= duration:
            _fail("TIMING_UNSUPPORTED")
        for duration_key in ("duration", "pkt_duration"):
            if duration_key in frame:
                frame_duration = _integer(frame[duration_key])
                if frame_duration <= 0 or (pts + frame_duration) * tick > 60:
                    _fail("TIMING_UNSUPPORTED")
        points.append(pts)
    return stream, width, height, tick.numerator, tick.denominator, tick, duration, points


def _chunk(kind, value):
    return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xFFFFFFFF)


def _encode_png(rgb, width, height):
    stride = width * 3
    scanlines = b"".join(b"\0" + rgb[offset:offset + stride] for offset in range(0, len(rgb), stride))
    return (_PNG_SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(scanlines, 9)) + _chunk(b"IEND", b""))


def validate_png(data, width, height):
    """Accept only this service's bounded, metadata-free, canonical RGB PNG.

    This validates bytes and dimensions, not source provenance; callers must
    retain the original execution/source binding and SHA-256 separately.
    """
    if (type(width) is not int or type(height) is not int or not 1 <= width <= _MAX_PREVIEW_EDGE
            or not 1 <= height <= _MAX_PREVIEW_EDGE or type(data) is not bytes
            or not 57 <= len(data) <= _MAX_CAPTURE or not data.startswith(_PNG_SIGNATURE)):
        _fail("PNG_INVALID")
    try:
        offset, chunks = 8, []
        for expected in (b"IHDR", b"IDAT", b"IEND"):
            if offset + 12 > len(data):
                _fail("PNG_INVALID")
            length = struct.unpack_from(">I", data, offset)[0]
            kind = data[offset + 4:offset + 8]
            end = offset + 8 + length
            if end + 4 > len(data) or kind != expected:
                _fail("PNG_INVALID")
            value = data[offset + 8:end]
            if struct.unpack_from(">I", data, end)[0] != zlib.crc32(kind + value) & 0xFFFFFFFF:
                _fail("PNG_INVALID")
            chunks.append(value)
            offset = end + 4
        if (offset != len(data) or chunks[0] != struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
                or chunks[2]):
            _fail("PNG_INVALID")
        size = (width * 3 + 1) * height
        decoder = zlib.decompressobj()
        raw = decoder.decompress(chunks[1], size + 1)
        if len(raw) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            _fail("PNG_INVALID")
        stride = width * 3 + 1
        if any(raw[row * stride] != 0 for row in range(height)):
            _fail("PNG_INVALID")
        rgb = b"".join(raw[row * stride + 1:(row + 1) * stride] for row in range(height))
        if _encode_png(rgb, width, height) != data:
            _fail("PNG_INVALID")
    except (zlib.error, struct.error, OverflowError):
        _fail("PNG_INVALID")
    return True


def prepare_frames(data: bytes, in_ms: int, out_ms: int, sample_count: int, *, guard) -> dict:
    """Prepare source-index/PTS-bound previews for evenly spaced target times.

    Targets are in + floor((out-in)*i/count). Each resolves to the first actual
    frame PTS at or after it and strictly before out. Duplicates are intentional.
    There is no fallback to nominal/average FPS, nearest frames, or re-timing.
    """
    deadline = time.monotonic() + _PREPARATION_SECONDS
    guard_failure = None
    def current():
        nonlocal guard_failure
        try:
            guard()
        except BaseException as error:
            guard_failure = error
            raise
        if time.monotonic() >= deadline:
            _fail("TIMEOUT")
    current()
    if type(data) is not bytes or not 1 <= len(data) <= _MAX_BYTES:
        _fail("BYTES_LIMIT")
    if (type(in_ms) is not int or type(out_ms) is not int or type(sample_count) is not int
            or not 0 <= in_ms < out_ms <= 60_000 or out_ms - in_ms > 10_000 or not 1 <= sample_count <= 8):
        _fail("REQUEST_INVALID")
    extension = _container(data)
    demuxer = (["-f", "mov", "-enable_drefs", "0", "-use_absolute_path", "0"]
               if extension == "mp4" else ["-f", "matroska"])
    probe, decoder = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not decoder:
        _fail("NATIVE_UNAVAILABLE")
    try:
        with media_files._media_inspection_directory() as directory:
            source = Path(directory) / ("source." + extension)
            capture = Path(directory) / "probe.json"
            source.write_bytes(data)
            current()
            native.run_guarded_process([
                probe, "-v", "error", "-threads", "1", "-max_alloc", "67108864",
                "-max_pixels", str(_MAX_PIXELS), "-err_detect", "explode", "-protocol_whitelist", "file,pipe",
                "-select_streams", "v", "-show_streams", "-show_format", "-show_frames", "-show_log", "16", "-show_error",
                "-show_entries", _PROBE_ENTRIES, "-of", "json=compact=1", *demuxer, str(source)],
                cwd=directory, guard=current, timeout=min(15, deadline - time.monotonic()), stdout_path=capture)
            current()
            stream, width, height, num, den, tick, duration, points = _parse_probe(capture.read_bytes(), extension)
            if Fraction(out_ms, 1000) > duration:
                _fail("INTERVAL_OUTSIDE_SOURCE")
            longest = max(width, height)
            preview_width = max(1, width * min(longest, _MAX_PREVIEW_EDGE) // longest)
            preview_height = max(1, height * min(longest, _MAX_PREVIEW_EDGE) // longest)
            selected = []
            for index in range(sample_count):
                requested = in_ms + (out_ms - in_ms) * index // sample_count
                frame_index = bisect_left(points, Fraction(requested, 1000) / tick)
                if frame_index == len(points) or points[frame_index] * tick >= Fraction(out_ms, 1000):
                    _fail("NO_FRAME_IN_INTERVAL")
                selected.append((requested, frame_index))
            # Admit the probe plus each unique extraction pass by decoded source
            # pixels, independent of nominal FPS. The first probe itself is
            # fenced by its deadline, frame capture and per-frame pixel limit.
            work_frames = len(points) * (1 + len({item[1] for item in selected}))
            if width * height * work_frames > _MAX_DECODED_PIXELS:
                _fail("WORK_LIMIT")
            # Reuse one bounded raw capture; never accumulate native output files.
            raw_path = Path(directory) / "frame.rgb"
            previews = {}
            for _, frame_index in selected:
                if frame_index in previews:
                    continue
                current()
                pts = points[frame_index]
                filters = (f"select=eq(n\\,{frame_index})*eq(pts\\,{pts}),"
                           f"scale={preview_width}:{preview_height}:flags=bilinear,format=rgb24")
                native.run_guarded_process([
                    decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "1",
                    "-filter_threads", "1", "-max_alloc", "67108864", "-max_pixels", str(_MAX_PIXELS),
                    "-err_detect", "explode", "-protocol_whitelist", "file,pipe", "-noautorotate", "-copyts",
                    *demuxer, "-i", str(source), "-map", f"0:{stream['index']}", "-an", "-sn", "-dn",
                    "-vf", filters, "-frames:v", "1", "-vsync", "0", "-threads", "1",
                    "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                    cwd=directory, guard=current, timeout=min(10, deadline - time.monotonic()), stdout_path=raw_path)
                current()
                rgb = raw_path.read_bytes()
                if len(rgb) != preview_width * preview_height * 3:
                    _fail("FRAME_DECODE_MISMATCH")
                png = _encode_png(rgb, preview_width, preview_height)
                validate_png(png, preview_width, preview_height)
                previews[frame_index] = (hashlib.sha256(png).hexdigest(), base64.b64encode(png).decode("ascii"))
            frames = []
            for index, (requested, frame_index) in enumerate(selected):
                pts = points[frame_index]
                exact_ms = pts * tick * 1000
                digest, content = previews[frame_index]
                frames.append({"index": index, "requested_ms": requested, "source_frame_index": frame_index,
                               "pts": pts, "time_ms": {"num": exact_ms.numerator, "den": exact_ms.denominator},
                               "width": preview_width, "height": preview_height,
                               "png_sha256": digest, "content_base64": content})
            milliseconds = duration * 1000
            result = {"media": {"duration_ms": -(-milliseconds.numerator // milliseconds.denominator),
                                 "width": width, "height": height, "time_base": {"num": num, "den": den},
                                 "frame_count": len(points), "timing_policy": "MONOTONIC_ZERO_ORIGIN_PTS",
                                 "orientation": "UNROTATED_SQUARE_PIXELS"}, "frames": frames}
            current()
        current()
        return result
    except BaseException as error:
        # Cancellation/authority exceptions retain exact type, message and
        # identity, even if strict temporary cleanup independently failed.
        if guard_failure is not None:
            if error is not guard_failure:
                guard_failure.add_note("Reference preview temporary cleanup did not complete.")
            raise guard_failure from None
        if isinstance(error, _ReferenceError):
            raise
        if isinstance(error, subprocess.TimeoutExpired):
            raise _ReferenceError("VIDEO_REFERENCE_TIMEOUT") from None
        if isinstance(error, media_files.MediaValidationError) and str(error) == "STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT":
            raise _ReferenceError("VIDEO_REFERENCE_OUTPUT_LIMIT") from None
        if isinstance(error, (ValueError, OSError, subprocess.SubprocessError, RecursionError, OverflowError)):
            raise _ReferenceError("VIDEO_REFERENCE_DECODE_FAILED") from None
        raise
