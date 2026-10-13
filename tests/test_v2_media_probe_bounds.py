"""Additive inspection evidence using controlled real children and CPU codecs.

No providers, downloads, user devices, models, or accelerators are involved.
The controlled harness substitutes only the executable at the Popen boundary;
the actual process owner still drains pipes, checks guards, and reaps children.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import wave

import pytest

from app import media_files as media
from app.services import studio_timeline_export as native
from app.services.audiobook_service import AudiobookError


STDOUT_LIMIT = 1_048_576
STDERR_LIMIT = 65_536
FLAC_BYTES = b"fLaCcontrolled-local-fixture"
MP4_BYTES = b"\x00\x00\x00\x18ftypisomcontrolled-local-fixture"
ROOT = Path(__file__).resolve().parents[1]


def probe_json(*, kind="audio", duration="0.125", **stream):
    row = {"codec_type": kind, "codec_name": "flac" if kind == "audio" else "mpeg4"}
    row.update(stream)
    return json.dumps({"streams": [row], "format": {"duration": duration}}).encode()


def writer_code(payload, *, stderr=0, stdout_noise=0, exitcode=0, wait=False):
    # Payloads are read from a private fixture file so a boundary-size probe does
    # not depend on host command-line length limits.
    return (
        "import os, pathlib, sys, time\n"
        f"payload = pathlib.Path({str(payload)!r}).read_bytes()\n"
        "sys.stdout.buffer.write(payload); sys.stdout.buffer.flush()\n"
        f"sys.stdout.buffer.write(b'o' * {stdout_noise}); sys.stdout.buffer.flush()\n"
        f"sys.stderr.buffer.write(b'private-diagnostic:' + b'e' * {stderr}); sys.stderr.buffer.flush()\n"
        + ("pathlib.Path('ready').write_text('ready'); time.sleep(30)\n" if wait else "")
        + f"raise SystemExit({exitcode})\n"
    )


@pytest.fixture
def controlled(tmp_path, monkeypatch):
    original_popen = subprocess.Popen
    original_directory = tempfile.TemporaryDirectory
    original_runner = native.run_guarded_process
    original_open = open
    state = SimpleNamespace(
        children=[], directories=[], captures=[], handles=[], runs=[], completed=[], errors=[],
        probe_payload=probe_json(), decode_payload=b"", probe_stderr=0, decode_stderr=0,
        probe_exitcode=0, decode_exitcode=0, probe_wait=False, decode_wait=False,
        decode_stdout_noise=0, short_timeout=None,
    )

    def directory(*args, **kwargs):
        kwargs["dir"] = tmp_path
        result = original_directory(*args, **kwargs)
        state.directories.append(Path(result.name))
        if os.name != "nt":
            assert Path(result.name).stat().st_mode & 0o077 == 0
        return result

    def recording_open(*args, **kwargs):
        handle = original_open(*args, **kwargs)
        state.handles.append(handle)
        return handle

    def popen(command, **kwargs):
        phase = "probe" if command[0] == "controlled-ffprobe" else "decode"
        assert command[0] in {"controlled-ffprobe", "controlled-ffmpeg"}
        payload_path = tmp_path / (phase + "-payload")
        payload_path.write_bytes(getattr(state, phase + "_payload"))
        code = writer_code(payload_path, stderr=getattr(state, phase + "_stderr"),
            stdout_noise=state.decode_stdout_noise if phase == "decode" else 0,
            exitcode=getattr(state, phase + "_exitcode"), wait=getattr(state, phase + "_wait"))
        process = original_popen([sys.executable, "-c", code], **kwargs)
        state.children.append((phase, process, list(command), kwargs))
        return process

    def runner(command, **kwargs):
        requested = dict(kwargs)
        state.runs.append((list(command), requested))
        phase = "probe" if command[0] == "controlled-ffprobe" else "decode"
        if state.short_timeout is not None and getattr(state, phase + "_wait"):
            kwargs["timeout"] = state.short_timeout
        try:
            result = original_runner(command, **kwargs)
        except BaseException as error:
            state.errors.append(error)
            raise
        finally:
            capture = requested.get("stdout_path")
            if capture is not None and Path(capture).exists():
                state.captures.append((Path(capture), Path(capture).stat().st_size))
        state.completed.append(command[0])
        return result

    def assert_clean():
        assert all(not directory.exists() for directory in state.directories)
        assert all(handle.closed for handle in state.handles)
        for _, process, _, _ in state.children:
            assert process.poll() is not None, "inspection leaked a running child"
            assert process.returncode is not None
            assert all(stream is None or stream.closed for stream in (process.stdout, process.stderr))
            if os.name != "nt":
                with pytest.raises(ChildProcessError):
                    os.waitpid(process.pid, os.WNOHANG)

    state.assert_clean = assert_clean
    monkeypatch.setattr(media.shutil, "which", lambda name: {
        "ffprobe": "controlled-ffprobe", "ffmpeg": "controlled-ffmpeg"}.get(name))
    monkeypatch.setattr(media.tempfile, "TemporaryDirectory", directory)
    monkeypatch.setattr(native, "open", recording_open, raising=False)
    monkeypatch.setattr(native.subprocess, "Popen", popen)
    monkeypatch.setattr(native, "run_guarded_process", runner)
    try:
        yield state
    finally:
        try:
            assert_clean()
        finally:
            # Failing implementation assertions must not strand test processes.
            for _, process, _, _ in state.children:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()


def expected_audio(duration_ms=125, codec="flac", extension="flac"):
    return {"media_type": "audio/mpeg" if extension == "mp3" else "audio/" + extension,
        "extension": extension, "duration_ms": duration_ms, "validation": "DECODED", "codec": codec}


@pytest.mark.parametrize("extra", [0, 1])
def test_actual_probe_capture_at_limit_and_one_byte_over(controlled, extra):
    payload = probe_json()
    controlled.probe_payload = payload + b" " * (STDOUT_LIMIT + extra - len(payload))
    if extra:
        with pytest.raises(media.MediaValidationError, match="^media decoding failed$"):
            media.inspect_media(FLAC_BYTES, "audio")
        assert [item[0] for item in controlled.children] == ["probe"]
    else:
        assert media.inspect_media(FLAC_BYTES, "audio") == expected_audio()
        assert [item[0] for item in controlled.children] == ["probe", "decode"]
    assert len(controlled.captures) == 1
    path, size = controlled.captures[0]
    assert path.name == "probe.json" and path.parent in controlled.directories
    assert size == STDOUT_LIMIT


def test_original_native_arguments_private_capture_and_timeouts(controlled):
    assert media.inspect_media(FLAC_BYTES, "audio") == expected_audio()
    probe, decode = controlled.runs
    directory = controlled.directories[0]
    source = str(directory / "input.flac")
    assert probe[0] == ["controlled-ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
        "-show_streams", "-show_format", "-of", "json", source]
    assert decode[0] == ["controlled-ffmpeg", "-nostdin", "-v", "error", "-xerror", "-threads", "1",
        "-protocol_whitelist", "file,pipe", "-i", source, "-map", "0:a:0", "-f", "null", "-"]
    assert [call[1]["timeout"] for call in controlled.runs] == [20, 30]
    assert all(Path(call[1]["cwd"]) == directory for call in controlled.runs)
    assert Path(probe[1]["stdout_path"]) == directory / "probe.json"
    assert decode[1].get("stdout_path") is None
    assert [child[3]["stdout"] for child in controlled.children] == [subprocess.PIPE, subprocess.DEVNULL]
    assert all(child[3]["stderr"] == subprocess.PIPE and child[3]["stdin"] == subprocess.DEVNULL
        and child[3]["shell"] is False for child in controlled.children)
    assert all(child[1].returncode == 0 for child in controlled.children)


def test_both_native_phases_drain_large_stderr_and_discard_decoder_stdout(controlled):
    controlled.probe_stderr = controlled.decode_stderr = 4 * 1024 * 1024
    controlled.decode_stdout_noise = 4 * 1024 * 1024
    assert media.inspect_media(FLAC_BYTES, "audio") == expected_audio()
    assert [size for _, size in controlled.captures] == [len(probe_json())]
    assert all(child[1].returncode == 0 for child in controlled.children)


@pytest.mark.parametrize("phase", ["probe", "decode"])
def test_native_failure_has_bounded_private_stderr_and_generic_public_error(controlled, phase):
    setattr(controlled, phase + "_stderr", 2 * 1024 * 1024)
    setattr(controlled, phase + "_exitcode", 7)
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$") as error:
        media.inspect_media(FLAC_BYTES, "audio")
    cause = controlled.errors[-1]
    assert isinstance(cause, subprocess.CalledProcessError)
    assert cause.returncode == 7 and len(cause.stderr) == STDERR_LIMIT
    assert cause.stderr.startswith(b"private-diagnostic:")
    assert "private-diagnostic:" not in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__
    assert [child[0] for child in controlled.children] == (["probe"] if phase == "probe" else ["probe", "decode"])


@pytest.mark.parametrize("phase", ["probe", "decode"])
def test_actual_timeout_reaps_child_removes_private_files_and_preserves_public_error(controlled, phase):
    controlled.short_timeout = 0.15
    setattr(controlled, phase + "_wait", True)
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$") as error:
        media.inspect_media(FLAC_BYTES, "audio")
    assert isinstance(controlled.errors[-1], subprocess.TimeoutExpired)
    assert error.value.__cause__ is None and error.value.__suppress_context__
    assert [call[1]["timeout"] for call in controlled.runs] == ([20] if phase == "probe" else [20, 30])


@pytest.mark.parametrize("fault", ["spawn", "read"])
def test_native_resource_failures_are_sanitized_and_cleaned(controlled, monkeypatch, fault):
    def fail(*args, **kwargs):
        raise OSError("private-path-or-native-detail")

    if fault == "spawn":
        monkeypatch.setattr(native.subprocess, "Popen", fail)
    else:
        controlled.probe_wait = True
        monkeypatch.setattr(native, "_read_process_pipe", fail)
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$") as error:
        media.inspect_media(FLAC_BYTES, "audio")
    assert error.value.__cause__ is None and error.value.__suppress_context__
    assert "private-path-or-native-detail" not in str(error.value)
    assert len(controlled.children) == (0 if fault == "spawn" else 1)


@pytest.mark.parametrize("payload", [
    b"", b"not-json", b"\xff", b"{", b"null", b"[]", b"1", b'"text"',
    b'{"streams": null}', b'{"streams": {}}', b'{"streams": [null]}',
    b'{"streams": [1]}', b'{"streams": ["audio"]}',
    b'{"streams": [], "format": {"duration": "1"}}',
    b'{"streams": [{"codec_type": "audio"}], "format": null}',
    b'{"streams": [{"codec_type": "audio"}], "format": []}',
    b'{"streams": [{"codec_type": "audio"}], "format": {"duration": []}}',
    b'{"streams": [{"codec_type": "audio"}], "format": {"duration": {"bad": 1}}}',
    pytest.param(b"[" * 1500 + b"0" + b"]" * 1500, id="excessive-json-depth"),
    pytest.param(b'{"streams":[],"format":{"duration":' + b"9" * 5000 + b"}}", id="excessive-integer-digits"),
])
def test_malformed_probe_json_shapes_fail_closed_without_decoder(controlled, payload):
    controlled.probe_payload = payload
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$"):
        media.inspect_media(FLAC_BYTES, "audio")
    assert [child[0] for child in controlled.children] == ["probe"]


@pytest.mark.parametrize("duration", [None, "", "bad", "NaN", "Infinity", "-Infinity", True, False,
    0, -1, 36_000.1, [], {}, pytest.param(10**400, id="float-conversion-overflow")])
def test_invalid_duration_values_fail_closed_without_decoder(controlled, duration):
    controlled.probe_payload = probe_json(duration=duration)
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$"):
        media.inspect_media(FLAC_BYTES, "audio")
    assert [child[0] for child in controlled.children] == ["probe"]


@pytest.mark.parametrize("field", ["format", "stream"])
@pytest.mark.parametrize("malformed", [[], {}, False])
def test_falsey_malformed_duration_is_rejected_even_with_valid_fallback(controlled, field, malformed):
    details = {"streams": [{"codec_type": "audio", "codec_name": "flac", "duration": "1"}],
        "format": {"duration": "2"}}
    target = details["format"] if field == "format" else details["streams"][0]
    target["duration"] = malformed
    controlled.probe_payload = json.dumps(details).encode()
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$"):
        media.inspect_media(FLAC_BYTES, "audio")
    assert [child[0] for child in controlled.children] == ["probe"]


@pytest.mark.parametrize("width,height", [(0, 64), (-1, 64), (4097, 1), (1, 4097),
    ("bad", 64), (None, 64), ([], 64), ({}, 64), (float("inf"), 64), (True, 64), (64.5, 64)])
def test_invalid_video_dimensions_fail_closed_before_decoder(controlled, width, height):
    controlled.probe_payload = probe_json(kind="video", width=width, height=height)
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$"):
        media.inspect_media(MP4_BYTES, "video")
    assert [child[0] for child in controlled.children] == ["probe"]


def test_video_dimension_boundary_and_original_video_map(controlled):
    controlled.probe_payload = probe_json(kind="video", width=4096, height=4096)
    assert media.inspect_media(MP4_BYTES, "video") == {
        "media_type": "video/mp4", "extension": "mp4", "duration_ms": 125,
        "validation": "DECODED", "codec": "mpeg4"}
    assert controlled.runs[1][0][controlled.runs[1][0].index("-map") + 1] == "0:v:0"


@pytest.mark.parametrize("codec", [[], {}, 1, True])
def test_invalid_codec_values_fail_closed_before_decode(controlled, codec):
    controlled.probe_payload = probe_json(codec_name=codec)
    with pytest.raises(media.MediaValidationError, match="^media decoding failed$"):
        media.inspect_media(FLAC_BYTES, "audio")
    assert [child[0] for child in controlled.children] == ["probe"]


@pytest.mark.parametrize("details,expected", [
    ({"streams": [{"codec_type": "audio", "duration": "1.2345", "codec_name": "flac"}]}, expected_audio(1234)),
    ({"streams": [{"codec_type": "video"}, {"codec_type": "audio"}], "format": {"duration": "36000"}}, expected_audio(36_000_000, None)),
    ({"streams": [{"codec_type": "audio", "duration": "3", "codec_name": "flac"}], "format": {"duration": "2"}}, expected_audio(2000)),
])
def test_legacy_duration_fallback_codec_none_and_rounding(controlled, details, expected):
    controlled.probe_payload = json.dumps(details).encode()
    assert media.inspect_media(FLAC_BYTES, "audio") == expected


@pytest.mark.parametrize("missing", ["ffprobe", "ffmpeg", "both"])
def test_missing_native_tools_fail_closed_before_private_directory_or_launch(controlled, monkeypatch, missing):
    monkeypatch.setattr(media.shutil, "which", lambda name: None if missing in {name, "both"} else "controlled-" + name)
    with pytest.raises(media.MediaValidationError, match="^MEDIA_VALIDATOR_NOT_CONFIGURED: ffprobe and ffmpeg are required$"):
        media.inspect_media(FLAC_BYTES, "audio")
    assert not controlled.children and not controlled.directories


@pytest.mark.parametrize("data,kind,message", [
    (b"", "audio", "media is empty"), (b"not-media", "audio", "unsupported or invalid audio container"),
    (FLAC_BYTES, "video", "video container must be MP4 or WebM"),
])
def test_original_container_rejections_never_launch(controlled, data, kind, message):
    with pytest.raises(media.MediaValidationError, match="^" + message + "$"):
        media.inspect_media(data, kind)
    assert not controlled.children


def guard_error(name):
    if name == "audiobook":
        return AudiobookError("AUDIOBOOK_CANCELLED", "controlled cancellation", status=410)
    return {"value": ValueError, "media": media.MediaValidationError, "runtime": RuntimeError,
        "interrupt": KeyboardInterrupt, "os": OSError, "wave": wave.Error,
        "eof": EOFError}[name]("controlled cancellation")


@pytest.mark.parametrize("failure", ["audiobook", "value", "media", "runtime", "interrupt", "os"])
@pytest.mark.parametrize("phase", ["before_launch", "during_probe", "between", "during_decode", "after_exit"])
def test_guard_identity_at_every_native_boundary_and_cleanup(controlled, monkeypatch, failure, phase):
    refused = guard_error(failure)
    eof = set()
    original_read = native._read_process_pipe
    if phase == "during_probe":
        controlled.probe_wait = True
    if phase == "during_decode":
        controlled.decode_wait = True

    def read(stream):
        chunk = original_read(stream)
        if chunk == b"":
            eof.add(stream)
        return chunk

    monkeypatch.setattr(native, "_read_process_pipe", read)

    def guard():
        if phase == "before_launch":
            raise refused
        if phase == "between" and controlled.completed == ["controlled-ffprobe"]:
            raise refused
        if not controlled.children:
            return
        active, process, _, options = controlled.children[-1]
        if phase == "during_" + active and (Path(options["cwd"]) / "ready").exists():
            assert process.poll() is None
            raise refused
        if phase == "after_exit" and active == "decode" and process.stderr in eof and process.poll() is not None:
            raise refused

    with pytest.raises(type(refused)) as raised:
        media.inspect_media(FLAC_BYTES, "audio", guard=guard)
    assert raised.value is refused
    if failure == "audiobook":
        assert raised.value.code == "AUDIOBOOK_CANCELLED" and raised.value.status == 410
    expected_phases = {"before_launch": [], "during_probe": ["probe"], "between": ["probe"],
        "during_decode": ["probe", "decode"], "after_exit": ["probe", "decode"]}
    assert [item[0] for item in controlled.children] == expected_phases[phase]
    if phase == "after_exit":
        assert controlled.children[-1][1].returncode == 0


@pytest.mark.parametrize("order", ["media_first", "runner_first"])
def test_cold_import_orders_do_not_form_a_cycle(order):
    modules = ["app.media_files", "app.services.studio_timeline_export"]
    if order == "runner_first":
        modules.reverse()
    code = (
        "import importlib, io, wave\n"
        + "\n".join(f"importlib.import_module({module!r})" for module in modules)
        + "\nfrom app.media_files import inspect_media\n"
        "buffer = io.BytesIO()\n"
        "with wave.open(buffer, 'wb') as writer:\n"
        " writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8000); writer.writeframes(b'\\x00\\x00' * 800)\n"
        "assert inspect_media(buffer.getvalue(), 'audio')['duration_ms'] == 100\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def pcm_wav():
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\x00\x00" * 8000)
    return output.getvalue()


def test_pcm_wav_keeps_exact_legacy_dictionary_without_optional_tools(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("PCM inspection must not use optional native tools")

    monkeypatch.setattr(media.shutil, "which", forbidden)
    monkeypatch.setattr(media.subprocess, "Popen", forbidden)
    assert media.inspect_media(pcm_wav(), "audio") == {
        "media_type": "audio/wav", "extension": "wav", "duration_ms": 1000,
        "sample_rate": 8000, "channels": 1, "sample_width": 2, "validation": "PCM_DECODED"}


@pytest.mark.parametrize("failure", ["audiobook", "value", "wave", "eof", "interrupt"])
@pytest.mark.parametrize("phase", ["before", "after"])
def test_pcm_guard_refusal_keeps_original_exception_identity(monkeypatch, failure, phase):
    refused = guard_error(failure)
    checks = []

    def guard():
        checks.append(True)
        if phase == "before" or len(checks) > 1:
            raise refused

    def forbidden(*args, **kwargs):
        raise AssertionError("PCM guard tests must not start optional programs")

    monkeypatch.setattr(media.subprocess, "Popen", forbidden)
    with pytest.raises(type(refused)) as raised:
        media.inspect_media(pcm_wav(), "audio", guard=guard)
    assert raised.value is refused
    assert len(checks) == (1 if phase == "before" else 2)


@pytest.mark.parametrize("extension,kind,codec", [
    ("flac", "audio", "flac"), ("mp3", "audio", "libmp3lame"),
    ("mp4", "video", "mpeg4"), ("webm", "video", "libvpx-vp9"),
])
def test_real_installed_cpu_codecs_match_exact_legacy_result(tmp_path, extension, kind, codec):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    assert ffmpeg and ffprobe, "explicit local CPU round trip requires installed ffmpeg and ffprobe"
    source = tmp_path / "source.wav"
    source.write_bytes(pcm_wav())
    output = tmp_path / ("fixture." + extension)
    command = [ffmpeg, "-nostdin", "-v", "error", "-threads", "1"]
    if kind == "audio":
        command += ["-i", str(source), "-c:a", codec]
    else:
        command += ["-f", "lavfi", "-i", "color=c=black:s=64x64:r=10:d=1", "-c:v", codec,
            "-pix_fmt", "yuv420p", "-threads", "1"]
        if extension == "webm":
            command += ["-deadline", "realtime", "-cpu-used", "8"]
    command += ["-y", str(output)]
    subprocess.run(command, cwd=tmp_path, capture_output=True, timeout=20, check=True)
    # Independently obtain the tiny local fixture's measurements and preserve
    # the original inspector's exact public keys, MIME, codec, and rounding.
    result = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)],
        cwd=tmp_path, capture_output=True, timeout=10, check=True)
    details = json.loads(result.stdout)
    stream = next(row for row in details["streams"] if row["codec_type"] == kind)
    duration = float(details.get("format", {}).get("duration") or stream.get("duration") or 0)
    expected = {"media_type": "audio/mpeg" if extension == "mp3" else kind + "/" + extension,
        "extension": extension, "duration_ms": round(duration * 1000), "validation": "DECODED",
        "codec": stream.get("codec_name")}
    data = output.read_bytes()
    assert media.inspect_media(data, kind) == expected
    checks = []
    assert media.inspect_media(data, kind, guard=lambda: checks.append(True)) == expected
    assert checks
