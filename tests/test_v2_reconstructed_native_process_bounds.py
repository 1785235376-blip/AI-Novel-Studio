"""Additive reconstruction evidence: controlled children, no models or APIs."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.media_files import MediaValidationError
from app.services import studio_timeline_export as native

STDOUT_LIMIT = 1_048_576
STDERR_LIMIT = 65_536


def child(code):
    return [sys.executable, "-c", code]


@pytest.fixture
def spawned(monkeypatch):
    original = subprocess.Popen
    calls = []

    def record(*args, **kwargs):
        process = original(*args, **kwargs)
        calls.append((process, kwargs))
        return process

    monkeypatch.setattr(native.subprocess, "Popen", record)
    yield calls
    # Test cleanup also protects against a regressed runner leaking a child.
    for process, _ in calls:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)


def test_unused_stdout_is_discarded_without_a_capture_file(tmp_path, spawned):
    native.run_guarded_process(child("import os; os.write(1, b'x' * (4 * 1024 * 1024))"),
        cwd=tmp_path, guard=lambda: None, timeout=5)
    assert spawned[0][1]["stdout"] == subprocess.DEVNULL
    assert not list(tmp_path.iterdir())


def test_failing_stderr_is_pipe_drained_with_bounded_private_evidence(tmp_path, spawned):
    with pytest.raises(subprocess.CalledProcessError) as failed:
        native.run_guarded_process(child("import os; os.write(2, b'private-' + b'diagnostic:' + b'e' * (4 * 1024 * 1024)); raise SystemExit(7)"),
            cwd=tmp_path, guard=lambda: None, timeout=5)
    assert spawned[0][1]["stderr"] == subprocess.PIPE
    assert failed.value.returncode == 7
    assert len(failed.value.stderr) == STDERR_LIMIT
    assert failed.value.stderr.startswith(b"private-diagnostic:")
    assert "private-diagnostic:" not in str(failed.value)
    assert not list(tmp_path.iterdir())


def test_fast_stdout_overflow_never_grows_capture_past_limit(tmp_path):
    output = tmp_path / "probe.json"
    with pytest.raises(MediaValidationError, match="STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT"):
        native.run_guarded_process(child(f"import os; os.write(1, b'x' * {STDOUT_LIMIT * 2})"),
            cwd=tmp_path, guard=lambda: None, timeout=5, stdout_path=output)
    assert output.stat().st_size <= STDOUT_LIMIT


@pytest.mark.parametrize("size", [0, 1, STDOUT_LIMIT - 1, STDOUT_LIMIT])
def test_capture_round_trips_through_exact_limit(tmp_path, spawned, size):
    output = tmp_path / "probe.json"
    native.run_guarded_process(child(f"import os; os.write(1, b'x' * {size})"),
        cwd=tmp_path, guard=lambda: None, timeout=5, stdout_path=output)
    assert output.read_bytes() == b"x" * size
    process, options = spawned[0]
    assert options["stdin"] == subprocess.DEVNULL and options["shell"] is False
    assert options["stdout"] == options["stderr"] == subprocess.PIPE
    assert process.returncode == 0
    assert process.stdout.closed and process.stderr.closed


def test_stdout_one_byte_over_limit_is_rejected_and_reaped(tmp_path, spawned):
    output = tmp_path / "probe.json"
    with pytest.raises(MediaValidationError, match="STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT"):
        native.run_guarded_process(child(f"import os; os.write(1, b'x' * {STDOUT_LIMIT + 1})"),
            cwd=tmp_path, guard=lambda: None, timeout=5, stdout_path=output)
    assert output.stat().st_size == STDOUT_LIMIT
    process, _ = spawned[0]
    assert process.poll() is not None
    assert process.stdout.closed and process.stderr.closed
    output.unlink()  # Handles were closed even on the failure path (Windows too).


def test_both_streams_drain_fairly_without_deadlock(tmp_path):
    output = tmp_path / "probe.json"
    native.run_guarded_process(child(
        "import os\nfor _ in range(64):\n os.write(1, b'x' * 16384)\n os.write(2, b'e' * 65536)"),
        cwd=tmp_path, guard=lambda: None, timeout=10, stdout_path=output)
    assert output.read_bytes() == b"x" * STDOUT_LIMIT


def test_successful_stderr_flood_does_not_become_a_failure(tmp_path, spawned):
    native.run_guarded_process(child("import os; os.write(2, b'e' * (8 * 1024 * 1024))"),
        cwd=tmp_path, guard=lambda: None, timeout=10)
    assert spawned[0][0].returncode == 0
    assert spawned[0][0].stderr.closed
    assert not list(tmp_path.iterdir())


def test_initial_guard_refusal_never_opens_capture_or_launches(tmp_path, spawned):
    def guard():
        raise RuntimeError("execution fence closed")

    with pytest.raises(RuntimeError, match="execution fence closed"):
        native.run_guarded_process(child("raise AssertionError('must not run')"),
            cwd=tmp_path, guard=guard, timeout=5, stdout_path=tmp_path / "probe.json")
    assert not spawned and not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_guard_cancellation_during_noisy_output_reaps_and_closes(tmp_path, spawned, failure):
    import time

    started = time.monotonic()
    checks = []

    def guard():
        checks.append(time.monotonic())
        if checks[-1] - started > 0.15:
            raise failure("execution fence closed")

    with pytest.raises(failure, match="execution fence closed"):
        native.run_guarded_process(child("import os\nwhile True:\n os.write(1, b'x' * 65536)\n os.write(2, b'e' * 65536)"),
            cwd=tmp_path, guard=guard, timeout=5)
    assert 2 < len(checks)
    assert time.monotonic() - started < 4
    process, _ = spawned[0]
    assert process.poll() is not None and process.stderr.closed
    assert not list(tmp_path.iterdir())


def test_deadline_stops_idle_child_and_closes_partial_capture(tmp_path, spawned):
    output = tmp_path / "probe.json"
    with pytest.raises(subprocess.TimeoutExpired) as expired:
        native.run_guarded_process(child("import os, time; os.write(1, b'partial'); time.sleep(20)"),
            cwd=tmp_path, guard=lambda: None, timeout=0.3, stdout_path=output)
    assert expired.value.timeout == 0.3
    process, _ = spawned[0]
    assert process.poll() is not None
    assert process.stdout.closed and process.stderr.closed
    assert output.read_bytes() in (b"", b"partial")
    output.unlink()


@pytest.mark.skipif(os.name == "nt", reason="POSIX SIGTERM-ignore escalation; Windows kills terminate() directly")
def test_deadline_escalates_to_kill_and_reaps_sigterm_ignoring_child(tmp_path, spawned):
    import signal

    with pytest.raises(subprocess.TimeoutExpired):
        native.run_guarded_process(child("import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(20)"),
            cwd=tmp_path, guard=lambda: None, timeout=0.5)
    process, _ = spawned[0]
    assert process.returncode == -signal.SIGKILL
    assert process.stderr.closed


def test_pipe_setup_failure_reaps_child_and_closes_resources(tmp_path, spawned, monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX nonblocking setup fault; Windows uses PeekNamedPipe")

    def broken(*args):
        raise OSError("controlled setup failure")

    monkeypatch.setattr(native.os, "set_blocking", broken)
    output = tmp_path / "probe.json"
    with pytest.raises(OSError, match="controlled setup failure"):
        native.run_guarded_process(child("import time; time.sleep(20)"),
            cwd=tmp_path, guard=lambda: None, timeout=5, stdout_path=output)
    process, _ = spawned[0]
    assert process.poll() is not None
    assert process.stdout.closed and process.stderr.closed
    output.unlink()


def test_spawn_failure_closes_output_file(tmp_path):
    output = tmp_path / "probe.json"
    with pytest.raises(FileNotFoundError):
        native.run_guarded_process([str(tmp_path / "nonexistent-native-tool")],
            cwd=tmp_path, guard=lambda: None, timeout=5, stdout_path=output)
    output.unlink()


def test_pipe_read_failure_reaps_child_without_publishing_diagnostics(tmp_path, spawned, monkeypatch):
    def broken(stream):
        raise OSError("controlled pipe failure")

    monkeypatch.setattr(native, "_read_process_pipe", broken)
    with pytest.raises(OSError, match="controlled pipe failure"):
        native.run_guarded_process(child("import time; time.sleep(20)"),
            cwd=tmp_path, guard=lambda: None, timeout=5)
    process, _ = spawned[0]
    assert process.poll() is not None and process.stderr.closed


def test_drain_after_child_exit_still_obeys_deadline(tmp_path, spawned, monkeypatch):
    # Emulate an inherited write handle held open by another process. No leaked
    # fixture descendant is needed to verify the owner's post-exit wait bound.
    import time

    monkeypatch.setattr(native, "_read_process_pipe", lambda stream: None)
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        native.run_guarded_process(child("pass"), cwd=tmp_path, guard=lambda: None, timeout=0.3)
    assert time.monotonic() - started < 3
    assert spawned[0][0].returncode == 0
    assert spawned[0][0].stderr.closed


def test_final_guard_rechecks_after_all_output_is_drained(tmp_path, spawned, monkeypatch):
    original = native._read_process_pipe
    reached_eof = []

    def read(stream):
        value = original(stream)
        if value == b"":
            reached_eof.append(stream)
        return value

    def guard():
        if reached_eof and spawned[0][0].poll() is not None:
            raise RuntimeError("late fence closed")

    monkeypatch.setattr(native, "_read_process_pipe", read)
    with pytest.raises(RuntimeError, match="late fence closed"):
        native.run_guarded_process(child("pass"), cwd=tmp_path, guard=guard, timeout=5)
    assert spawned[0][0].stderr.closed


@pytest.mark.parametrize("available,expected,read_size", [(0, None, None), (-1, b"", None), (4, b"data", 4), (100_000, b"data", 65_536)])
def test_synthetic_windows_pipe_drain_never_reads_without_available_bytes(monkeypatch, available, expected, read_size):
    from types import SimpleNamespace

    calls = []
    # Replace only this module's os reference, not the real OS identity used by pytest.
    monkeypatch.setattr(native, "os", SimpleNamespace(name="nt", read=lambda fd, size: calls.append((fd, size)) or b"data"))
    monkeypatch.setattr(native, "_windows_pipe_available", lambda stream: available)
    assert native._read_process_pipe(SimpleNamespace(fileno=lambda: 123)) == expected
    assert calls == ([] if read_size is None else [(123, read_size)])


@pytest.mark.parametrize("error", [0, 109, 232, 5])
def test_synthetic_windows_peek_uses_full_handle_and_propagates_errors(monkeypatch, error):
    import ctypes
    from ctypes import wintypes
    from types import SimpleNamespace

    handle = 2**40 + 123
    calls = []

    def peek(actual, buffer, size, read, available, remaining):
        calls.append(actual)
        ctypes.cast(available, ctypes.POINTER(wintypes.DWORD))[0] = 321
        return error == 0

    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(get_osfhandle=lambda fd: handle))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: SimpleNamespace(PeekNamedPipe=peek), raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda code: OSError(code, "controlled Windows error"), raising=False)
    stream = SimpleNamespace(fileno=lambda: 123)
    if error == 5:
        with pytest.raises(OSError):
            native._windows_pipe_available(stream)
    else:
        assert native._windows_pipe_available(stream) == (321 if error == 0 else -1)
    assert calls == [handle]
    assert peek.argtypes[0] is wintypes.HANDLE and peek.restype is wintypes.BOOL


def test_real_cpu_ffmpeg_encoder_probe_and_media_round_trip(tmp_path):
    import shutil

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        pytest.skip("native CPU ffmpeg/ffprobe are required for the explicit integration check")
    compiled = native.compiler_profile({"preset": "REVIEW_MP4"}, duration_ms=1000, max_bytes=2_000_000)
    native.require_encoders(ffmpeg, compiled, cwd=tmp_path, guard=lambda: None)
    output = tmp_path / "fixture.mp4"
    command = [ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=10:d=1",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "1", "-c:v", "mpeg4", "-c:a", "aac",
        "-pix_fmt", "yuv420p", "-threads", "1", "-y", str(output)]
    native.run_guarded_process(command, cwd=tmp_path, guard=lambda: None, timeout=10)
    proof = native.prove_output(output, {"width": 64, "height": 64, "fps": 10, "duration_ms": 1000}, compiled,
        guard=lambda: None)
    assert proof["profile_validation"] == "NATIVE_FFPROBE_EXACT"
    assert proof["video_codec"] == "mpeg4" and proof["audio_codec"] == "aac"
    assert output.stat().st_size < 2_000_000
