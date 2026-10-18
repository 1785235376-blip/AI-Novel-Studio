"""Real CPU reference-frame evidence and bounded native-owner contracts."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

import pytest

from app import media_files
from app.services import studio_timeline_export as native
from app.services import studio_video_reference_frames as reference


@pytest.fixture
def cpu(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.fail("Real ffmpeg/ffprobe are required for reference-frame evidence")
    def create(name="source.mp4", *, size="64x48", rate=10, duration="1", filter=None, options=(), codec=None):
        target = tmp_path / name
        codec = codec or ("libvpx-vp9" if name.endswith("webm") else "libx264")
        command = [shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-threads", "1", "-filter_threads", "1",
                   "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={duration}"]
        if filter:
            command += ["-vf", filter]
        command += ["-c:v", codec, "-threads", "1", "-pix_fmt", "yuv420p", "-an", "-fs", "4000000"]
        if codec == "libx264":
            command += ["-preset", "ultrafast"]
        command += list(options) + ["-y", str(target)]
        native.run_guarded_process(command, cwd=tmp_path, guard=lambda: None, timeout=20)
        return target.read_bytes()
    return create


def prepare(data, start=0, end=1000, count=4, guard=lambda: None):
    return reference.prepare_frames(data, start, end, count, guard=guard)


def pixels(png):
    assert png[:8] == reference._PNG_SIGNATURE
    width, height = struct.unpack_from(">II", png, 16)
    offset = 8
    while png[offset + 4:offset + 8] != b"IDAT":
        offset += 12 + struct.unpack_from(">I", png, offset)[0]
    length = struct.unpack_from(">I", png, offset)[0]
    rows = zlib.decompress(png[offset + 8:offset + 8 + length])
    stride = width * 3 + 1
    assert len(rows) == height * stride
    assert all(rows[i * stride] == 0 for i in range(height))
    return b"".join(rows[i * stride + 1:(i + 1) * stride] for i in range(height))


def independent_decode(data, tmp_path, *, extension="mp4"):
    source = tmp_path / ("independent." + extension)
    source.write_bytes(data)
    raw = tmp_path / "independent.rgb"
    native.run_guarded_process([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-xerror", "-threads", "1",
        "-filter_threads", "1", "-i", str(source), "-map", "0:v:0", "-vsync", "0", "-threads", "1",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"], cwd=tmp_path, guard=lambda: None,
        timeout=10, stdout_path=raw)
    return raw.read_bytes()


@pytest.mark.parametrize("extension", ["mp4", "webm"])
def test_real_cfr_actual_frame_indices_exact_pts_and_canonical_rgb(cpu, tmp_path, extension):
    data = cpu("cfr." + extension)
    result = prepare(data)
    media, frames = result["media"], result["frames"]
    assert media["duration_ms"] == 1000
    assert (media["width"], media["height"], media["frame_count"]) == (64, 48, 10)
    assert media["timing_policy"] == "MONOTONIC_ZERO_ORIGIN_PTS"
    assert media["orientation"] == "UNROTATED_SQUARE_PIXELS"
    assert [f["index"] for f in frames] == [0, 1, 2, 3]
    assert [f["requested_ms"] for f in frames] == [0, 250, 500, 750]
    assert [f["source_frame_index"] for f in frames] == [0, 3, 5, 8]
    assert [f["time_ms"] for f in frames] == [{"num": n, "den": 1} for n in (0, 300, 500, 800)]
    tick = Fraction(media["time_base"]["num"], media["time_base"]["den"])
    assert (tick.numerator, tick.denominator) == (media["time_base"]["num"], media["time_base"]["den"])
    raw = independent_decode(data, tmp_path, extension=extension)
    stride = 64 * 48 * 3
    for frame in frames:
        png = base64.b64decode(frame["content_base64"], validate=True)
        assert reference.validate_png(png, 64, 48)
        assert hashlib.sha256(png).hexdigest() == frame["png_sha256"]
        assert pixels(png) == raw[frame["source_frame_index"] * stride:(frame["source_frame_index"] + 1) * stride]
        assert Fraction(frame["time_ms"]["num"], frame["time_ms"]["den"]) == frame["pts"] * tick * 1000
    assert prepare(data) == result


def test_real_vfr_uses_actual_pts_and_preserves_duplicate_requested_positions(cpu, tmp_path):
    data = cpu("vfr.mp4", duration="1.3",
        filter="select='eq(n,0)+eq(n,1)+eq(n,4)+eq(n,8)+eq(n,12)'",
        options=("-vsync", "vfr", "-video_track_timescale", "1000"))
    result = prepare(data, 0, 1250, 8)
    frames = result["frames"]
    assert result["media"]["frame_count"] == 5
    assert [f["requested_ms"] for f in frames] == [0, 156, 312, 468, 625, 781, 937, 1093]
    assert [f["source_frame_index"] for f in frames] == [0, 2, 2, 3, 3, 3, 4, 4]
    assert [f["time_ms"]["num"] for f in frames] == [0, 400, 400, 800, 800, 800, 1200, 1200]
    raw = independent_decode(data, tmp_path)
    for frame in frames:
        index = frame["source_frame_index"]
        assert pixels(base64.b64decode(frame["content_base64"])) == raw[index * 9216:(index + 1) * 9216]


def test_actual_b_frames_are_selected_in_decoded_order(cpu, tmp_path):
    data = cpu("bframes.mp4", options=("-bf", "2", "-g", "10"))
    result = prepare(data, 101, 901, 4)
    assert [frame["source_frame_index"] for frame in result["frames"]] == [2, 4, 6, 8]
    raw = independent_decode(data, tmp_path)
    for frame in result["frames"]:
        index = frame["source_frame_index"]
        assert pixels(base64.b64decode(frame["content_base64"])) == raw[index * 9216:(index + 1) * 9216]


def test_fractional_timestamps_remain_exact_rationals(cpu):
    result = prepare(cpu(rate="30000/1001"), 1, 101, 3)
    assert [frame["source_frame_index"] for frame in result["frames"]] == [1, 2, 3]
    assert result["frames"][0]["time_ms"] == {"num": 1001, "den": 30}


@pytest.mark.parametrize("size,expected", [("640x360", (320, 180)), ("360x640", (180, 320)), ("320x320", (320, 320)), ("64x48", (64, 48))])
def test_preview_downscales_aspect_and_never_upscales(cpu, size, expected):
    result = prepare(cpu(size=size), count=1)
    frame = result["frames"][0]
    assert (frame["width"], frame["height"]) == expected
    png = base64.b64decode(frame["content_base64"])
    assert len(png) <= 512 * 1024
    assert reference.validate_png(png, *expected)


@pytest.mark.parametrize("args,code", [
    ((b"", 0, 100, 1), "BYTES_LIMIT"), ((b"x" * (25 * 1024 * 1024 + 1), 0, 100, 1), "BYTES_LIMIT"),
    ((bytearray(b"x"), 0, 100, 1), "BYTES_LIMIT"), ((b"x", True, 100, 1), "REQUEST_INVALID"),
    ((b"x", 0, 100, True), "REQUEST_INVALID"), ((b"x", -1, 100, 1), "REQUEST_INVALID"),
    ((b"x", 0, 0, 1), "REQUEST_INVALID"), ((b"x", 0, 10001, 1), "REQUEST_INVALID"),
    ((b"x", 59001, 60001, 1), "REQUEST_INVALID"), ((b"x", 0, 100, 0), "REQUEST_INVALID"),
    ((b"x", 0, 100, 9), "REQUEST_INVALID"), ((b"x", 0, 100.0, 1), "REQUEST_INVALID"),
    ((b"x", 0, 100, 1), "CONTAINER_UNSUPPORTED"),
])
def test_invalid_requests_fail_before_native(monkeypatch, args, code):
    monkeypatch.setattr(native, "run_guarded_process", lambda *a, **k: pytest.fail("invalid request launched native work"))
    with pytest.raises(media_files.MediaValidationError, match="^VIDEO_REFERENCE_" + code + "$"):
        reference.prepare_frames(*args, guard=lambda: None)


def test_half_open_interval_no_fallback_and_out_of_source(cpu):
    data = cpu(rate=2)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_NO_FRAME_IN_INTERVAL$"):
        prepare(data, 1, 500, 1)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_INTERVAL_OUTSIDE_SOURCE$"):
        prepare(data, 0, 1001, 1)
    assert prepare(data, 0, 1, 8)["frames"][-1]["source_frame_index"] == 0


@pytest.mark.parametrize("variant,code", [("sar", "ORIENTATION_UNSUPPORTED"), ("origin", "TIMING_UNSUPPORTED"),
    ("long", "DURATION_LIMIT"), ("dimensions", "DIMENSION_LIMIT"), ("matroska", "CONTAINER_UNSUPPORTED")])
def test_real_unsupported_source_subset(cpu, variant, code):
    arguments = {
        "sar": {"filter": "setsar=2"}, "origin": {"filter": "setpts=PTS+1/TB"},
        "long": {"rate": 1, "duration": "61"}, "dimensions": {"size": "4100x2", "duration": "0.1"},
        "matroska": {"name": "source.mkv", "codec": "libx264"},
    }[variant]
    data = cpu(**arguments)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_" + code + "$"):
        prepare(data, count=1)


def test_real_rotated_display_matrix_is_rejected(cpu, tmp_path):
    data = bytearray(cpu())
    # Write a real 90-degree track-header matrix. This avoids ffmpeg versions
    # that ignore the legacy rotate metadata tag when remuxing.
    matrix = data.index(b"tkhd") + 44
    assert struct.unpack_from(">9i", data, matrix) == (65536, 0, 0, 0, 65536, 0, 0, 0, 1073741824)
    struct.pack_into(">9i", data, matrix, 0, -65536, 0, 65536, 0, 0, 0, 0, 1073741824)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_ORIENTATION_UNSUPPORTED$"):
        prepare(bytes(data))


def test_real_multiple_video_streams_are_rejected(cpu, tmp_path):
    source = tmp_path / "stream-in.mp4"
    source.write_bytes(cpu())
    target = tmp_path / "two-streams.mp4"
    native.run_guarded_process([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:v:0", "-c", "copy", "-y", str(target)], cwd=tmp_path, guard=lambda: None, timeout=10)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_STREAMS_UNSUPPORTED$"):
        prepare(target.read_bytes())


def test_same_original_runner_bounded_outputs_one_probe_and_deduplicated_decodes(cpu, monkeypatch):
    data = cpu(rate=2)
    real = native.run_guarded_process
    calls, paths = [], []
    def observe(command, **kwargs):
        calls.append((command, kwargs))
        result = real(command, **kwargs)
        path = Path(kwargs["stdout_path"])
        paths.append(path)
        assert path.stat().st_size <= 1_048_576
        return result
    monkeypatch.setattr(native, "run_guarded_process", observe)
    result = prepare(data, 0, 501, 8)
    assert [f["source_frame_index"] for f in result["frames"]] == [0, 1, 1, 1, 1, 1, 1, 1]
    assert len(calls) == 3
    assert "-show_frames" in calls[0][0] and "-show_entries" in calls[0][0]
    assert "avg_frame_rate" not in calls[0][0][calls[0][0].index("-show_entries") + 1]
    for command, _ in calls:
        assert command[command.index("-f") + 1] == "mov"
        assert command[command.index("-enable_drefs") + 1] == "0"
        assert command[command.index("-use_absolute_path") + 1] == "0"
        assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
    for command, kwargs in calls[1:]:
        assert command[-1] == "pipe:1"
        assert "-ss" not in command and "-copyts" in command and "-noautorotate" in command
        assert "eq(pts\\," in command[command.index("-vf") + 1]
        assert kwargs["timeout"] <= 10
    assert all(not path.exists() and not path.parent.exists() for path in paths)


def test_native_decode_requires_matching_index_and_pts(cpu, monkeypatch):
    data = cpu()
    original = native.run_guarded_process
    def alter_pts(command, **kwargs):
        if "-vf" in command:
            command = list(command)
            index = command.index("-vf") + 1
            command[index] = command[index].replace("eq(pts\\,0)", "eq(pts\\,1)")
        return original(command, **kwargs)
    monkeypatch.setattr(native, "run_guarded_process", alter_pts)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_FRAME_DECODE_MISMATCH$"):
        prepare(data, count=1)


def test_native_corrupt_media_error_is_sanitized(cpu):
    data = cpu()
    with pytest.raises(ValueError, match=r"^VIDEO_REFERENCE_[A-Z_]+$") as error:
        prepare(data[:100])
    assert error.value.__cause__ is None
    assert "/" not in str(error.value)


@pytest.mark.parametrize("phase", ["probe", "decode"])
def test_cancellation_reaps_actual_child_and_preserves_guard_exception(cpu, monkeypatch, phase):
    data = cpu()
    original = native.run_guarded_process
    real_popen = native.subprocess.Popen
    children, directories = [], []
    cancelled = RuntimeError("specific authority cancellation")
    active = [False]
    def popen(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child
    def run(command, **kwargs):
        directories.append(Path(kwargs["cwd"]))
        active[0] = ("-show_frames" in command) == (phase == "probe")
        return original(command, **kwargs)
    def guard():
        if active[0] and children and children[-1].poll() is None:
            raise cancelled
    monkeypatch.setattr(native.subprocess, "Popen", popen)
    monkeypatch.setattr(native, "run_guarded_process", run)
    with pytest.raises(RuntimeError) as error:
        prepare(data, guard=guard)
    assert error.value is cancelled
    assert len(children) == (1 if phase == "probe" else 2)
    assert all(child.poll() is not None for child in children)
    assert all(not path.exists() for path in directories)
    assert all(stream is None or stream.closed for child in children for stream in (child.stdout, child.stderr))
    if os.name != "nt":
        for child in children:
            with pytest.raises(ChildProcessError):
                os.waitpid(child.pid, os.WNOHANG)


def test_guard_error_retained_when_cleanup_also_fails(cpu, monkeypatch):
    data = cpu()
    original_directory = media_files._media_inspection_directory
    cancelled = OSError("authority changed")
    calls = [0]
    @contextmanager
    def directory():
        with original_directory() as folder:
            try:
                yield folder
            finally:
                raise OSError("private cleanup detail")
    def guard():
        calls[0] += 1
        if calls[0] == 2:
            raise cancelled
    monkeypatch.setattr(media_files, "_media_inspection_directory", directory)
    with pytest.raises(OSError) as error:
        prepare(data, guard=guard)
    assert error.value is cancelled
    assert "private cleanup detail" not in str(error.value)


def test_real_native_stdout_limit_is_enforced_while_running(cpu, monkeypatch):
    data = cpu()
    original = native.run_guarded_process
    paths = []
    def overflow(command, **kwargs):
        path = Path(kwargs["stdout_path"])
        paths.append(path)
        try:
            return original([sys.executable, "-c", "import os; os.write(1, b'x' * 1048577)"], **kwargs)
        finally:
            assert path.stat().st_size == 1_048_576
    monkeypatch.setattr(native, "run_guarded_process", overflow)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_OUTPUT_LIMIT$"):
        prepare(data)
    assert all(not path.exists() for path in paths)


def test_shared_deadline_stops_before_another_decode(cpu, monkeypatch):
    data = cpu()
    original = native.run_guarded_process
    real_clock = reference.time.monotonic
    elapsed = [0]
    calls = []
    monkeypatch.setattr(reference.time, "monotonic", lambda: real_clock() + elapsed[0])
    def consume_budget(command, **kwargs):
        calls.append(command)
        result = original(command, **kwargs)
        if "-vf" in command:
            elapsed[0] += 31
        return result
    monkeypatch.setattr(native, "run_guarded_process", consume_budget)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_TIMEOUT$"):
        prepare(data)
    assert len(calls) == 2


def test_source_decoding_work_admitted_before_preview_decode(cpu, monkeypatch):
    data = cpu()
    monkeypatch.setattr(reference, "_MAX_DECODED_PIXELS", 64 * 48 * 10)
    original = native.run_guarded_process
    def only_probe(command, **kwargs):
        assert "-show_frames" in command
        return original(command, **kwargs)
    monkeypatch.setattr(native, "run_guarded_process", only_probe)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_WORK_LIMIT$"):
        prepare(data)


def test_png_rejects_foreign_dimensions_crc_extra_chunks_and_bombs(cpu):
    frame = prepare(cpu(), count=1)["frames"][0]
    png = base64.b64decode(frame["content_base64"])
    for bad, width, height in [(png, 63, 48), (png, True, 48), (png + b"tail", 64, 48),
        (png[:-1] + bytes([png[-1] ^ 1]), 64, 48), (b"not png", 64, 48), (png, 10000, 10000),
        (png[:-12] + reference._chunk(b"tEXt", b"injected") + png[-12:], 64, 48)]:
        with pytest.raises(ValueError, match="^VIDEO_REFERENCE_PNG_INVALID$"):
            reference.validate_png(bad, width, height)
    bomb = (reference._PNG_SIGNATURE + reference._chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + reference._chunk(b"IDAT", zlib.compress(b"\0" * 1_000_000)) + reference._chunk(b"IEND", b""))
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_PNG_INVALID$"):
        reference.validate_png(bomb, 1, 1)


def test_webm_uses_fixed_matroska_demuxer_for_probe_and_decode(cpu, monkeypatch):
    data = cpu("closed.webm")
    original = native.run_guarded_process
    commands = []
    def observe(command, **kwargs):
        commands.append(command)
        assert command[command.index("-f") + 1] == "matroska"
        assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
        return original(command, **kwargs)
    monkeypatch.setattr(native, "run_guarded_process", observe)
    prepare(data, count=1)
    assert len(commands) == 2


def test_actual_frame_count_limit_is_enforced_before_preview_decode(cpu, monkeypatch):
    data = cpu()
    monkeypatch.setattr(reference, "_MAX_FRAMES", 9)
    original = native.run_guarded_process
    def only_probe(command, **kwargs):
        assert "-show_frames" in command
        return original(command, **kwargs)
    monkeypatch.setattr(native, "run_guarded_process", only_probe)
    with pytest.raises(ValueError, match="^VIDEO_REFERENCE_FRAME_LIMIT$"):
        prepare(data)
