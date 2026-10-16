"""Retained process/exception references do not retain owned native handles.

Real small children and default strict TemporaryDirectory cleanup are used.
Tests do not clear tracebacks, rely on GC, ignore cleanup errors or use models.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace

import pytest

from app.media_files import MediaValidationError
from app import media_files as media
from app.services import studio_timeline_export as native
from test_v2_media_probe_bounds import controlled, FLAC_BYTES


@pytest.fixture
def retained_children(monkeypatch, tmp_path):
    original = subprocess.Popen
    original_directory = tempfile.TemporaryDirectory
    children = []

    def create(*args, **kwargs):
        process = original(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(native.subprocess, "Popen", create)
    def directory(*args, **kwargs):
        kwargs["dir"] = tmp_path
        return original_directory(*args, **kwargs)
    monkeypatch.setattr(media.tempfile, "TemporaryDirectory", directory)
    yield children
    # A deliberately failing before-fix run must not leak fixture resources.
    for process in children:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        if os.name == "nt":
            process._handle.Close()


def assert_released(process):
    assert process.returncode is not None
    assert process.poll() == process.wait(timeout=0) == process.returncode
    assert all(stream is None or stream.closed for stream in (process.stdout, process.stderr))
    if os.name == "nt":
        assert process._handle.closed, "owned Windows process handle survived reaping"
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        flags = wintypes.DWORD()
        query = kernel.GetHandleInformation
        query.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
        query.restype = wintypes.BOOL
        assert not query(int(process._handle), ctypes.byref(flags))
        assert ctypes.get_last_error() == 6  # ERROR_INVALID_HANDLE
    else:
        with pytest.raises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)


def command(code):
    return [sys.executable, "-c", code]


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("phase", ["immediate", "ready"])
def test_guard_identity_and_strict_directory_cleanup_with_retained_traceback(
        tmp_path, retained_children, failure, phase):
    refused = failure("controlled authority cancellation")
    with media._media_inspection_directory() as directory:
        path = Path(directory)

        def guard():
            if retained_children and (phase == "immediate" or (path / "ready").exists()):
                raise refused

        with pytest.raises(failure) as raised:
            native.run_guarded_process(command(
                "import pathlib,time; pathlib.Path('ready').write_text('ready'); time.sleep(60)"),
                cwd=path, guard=guard, timeout=5, stdout_path=path / "capture")
        assert raised.value is refused and refused.__traceback__ is not None
        assert_released(retained_children[0])
    # raised/refused/process remain reachable while real strict cleanup runs.
    assert not path.exists()
    assert raised.value is refused and refused.__traceback__ is not None


def test_success_closes_handle_before_private_capture_directory_cleanup(tmp_path, retained_children):
    with media._media_inspection_directory() as directory:
        path = Path(directory)
        capture = path / "capture"
        native.run_guarded_process(command("print('controlled output')"), cwd=path,
            guard=lambda: None, timeout=5, stdout_path=capture)
        assert_released(retained_children[0])
        assert capture.read_bytes().strip() == b"controlled output"
    assert not path.exists()


def test_nonzero_exit_closes_handle_while_private_error_traceback_is_retained(tmp_path, retained_children):
    with media._media_inspection_directory() as directory:
        path = Path(directory)
        with pytest.raises(subprocess.CalledProcessError) as raised:
            native.run_guarded_process(command("import sys; sys.stderr.write('fixture'); raise SystemExit(7)"),
                cwd=path, guard=lambda: None, timeout=5)
        assert raised.value.returncode == 7 and raised.value.stderr == b"fixture"
        assert_released(retained_children[0])
    assert not path.exists() and raised.value.__traceback__ is not None


def test_deadline_closes_handle_before_cleanup_with_retained_timeout(tmp_path, retained_children):
    with media._media_inspection_directory() as directory:
        path = Path(directory)
        with pytest.raises(subprocess.TimeoutExpired) as raised:
            native.run_guarded_process(command("import time; time.sleep(60)"),
                cwd=path, guard=lambda: None, timeout=0.15, stdout_path=path / "capture")
        assert raised.value.timeout == 0.15
        assert_released(retained_children[0])
    assert not path.exists() and raised.value.__traceback__ is not None


def test_overflow_keeps_capture_bound_and_releases_handle_before_cleanup(tmp_path, retained_children):
    with media._media_inspection_directory() as directory:
        path = Path(directory)
        capture = path / "capture"
        with pytest.raises(MediaValidationError, match="^STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT$"):
            native.run_guarded_process(command("import os; os.write(1, b'x' * 1048577)"),
                cwd=path, guard=lambda: None, timeout=5, stdout_path=capture)
        assert_released(retained_children[0])
        assert capture.stat().st_size == 1_048_576
    assert not path.exists()


def sharing_error(code=32):
    error = OSError(13, "controlled private cleanup failure")
    error.winerror = code
    return error


def test_nonsharing_cleanup_error_is_not_retried_or_waited(tmp_path, monkeypatch):
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        path = Path(directory)
        identity = (path.stat().st_dev, path.stat().st_ino)
        calls, sleeps = [], []
        error = sharing_error(5)

        def failed():
            calls.append(True)
            raise error

        monkeypatch.setattr(media.time, "sleep", lambda value: sleeps.append(value))
        with pytest.raises(OSError) as raised:
            media._cleanup_media_directory(SimpleNamespace(name=directory, cleanup=failed), identity)
        assert raised.value is error and calls == [True] and sleeps == []


@pytest.mark.parametrize("unsafe", ["nonempty", "replacement"])
def test_sharing_error_on_nonempty_or_replaced_directory_never_retries(tmp_path, monkeypatch, unsafe):
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        path = Path(directory)
        identity = (path.stat().st_dev, path.stat().st_ino)
        old = None
        if unsafe == "nonempty":
            (path / "retained").write_bytes(b"synthetic fixture")
        else:
            old = path.with_name(path.name + "-original")
            path.rename(old)
            path.mkdir()
        calls, sleeps = [], []
        error = sharing_error()

        def failed():
            calls.append(True)
            raise error

        monkeypatch.setattr(media.time, "sleep", lambda value: sleeps.append(value))
        try:
            with pytest.raises(OSError) as raised:
                media._cleanup_media_directory(SimpleNamespace(name=directory, cleanup=failed), identity)
            assert raised.value is error and calls == [True] and sleeps == []
            if unsafe == "nonempty":
                assert (path / "retained").read_bytes() == b"synthetic fixture"
        finally:
            if old is not None:
                old.rmdir()


@pytest.mark.parametrize("change", ["replacement", "new_file"])
def test_cleanup_retry_rechecks_owned_empty_directory_after_wait(tmp_path, monkeypatch, change):
    # The wait is a real interleaving boundary: do not recursively clean a new
    # owner or content written after the first identity/empty check.
    monkeypatch.setattr(media, "os", SimpleNamespace(name="nt", scandir=os.scandir))
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        path = Path(directory)
        identity = (path.stat().st_dev, path.stat().st_ino)
        original_cleanup = tempfile.TemporaryDirectory.cleanup
        calls, waits = [], []
        error = sharing_error()
        previous = None
        temporary = SimpleNamespace(name=directory)

        def cleanup():
            calls.append(True)
            if len(calls) == 1:
                raise error
            # Actual TemporaryDirectory recursive removal would delete this
            # later content if the owner revalidation were omitted.
            assert path.resolve().is_relative_to(tmp_path.resolve())
            actual = SimpleNamespace(name=directory, _finalizer=SimpleNamespace(detach=lambda: True),
                                     _ignore_cleanup_errors=False, _rmtree=tempfile.TemporaryDirectory._rmtree)
            return original_cleanup(actual)

        def interleave(delay):
            nonlocal previous
            waits.append(delay)
            if change == "replacement":
                previous = path.with_name(path.name + "-previous-owner")
                path.rename(previous)
                path.mkdir()
            (path / "later-content").write_bytes(b"must remain until explicitly disposed")

        temporary.cleanup = cleanup
        monkeypatch.setattr(media.time, "sleep", interleave)
        try:
            with pytest.raises(OSError) as raised:
                media._cleanup_media_directory(temporary, identity)
            assert raised.value is error
            assert calls == [True] and waits == [0.025]
            assert (path / "later-content").read_bytes() == b"must remain until explicitly disposed"
        finally:
            if previous is not None:
                previous.rmdir()


def hold_directory(path):
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    # Share reads/writes, deliberately withhold DELETE sharing on our fixture.
    handle = create(str(path), 0x80000000, 3, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    released = []

    def release():
        if not released:
            assert close(handle)
            released.append(True)

    return release


def test_real_directory_lock_premise_uses_windows_delete_sharing(tmp_path):
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        path = Path(directory)
        if os.name != "nt":
            assert path.is_dir()
            return
        release = hold_directory(path)
        try:
            with pytest.raises(PermissionError) as raised:
                path.rmdir()
            assert raised.value.winerror == 32 and path.is_dir()
        finally:
            release()


def remove_owned_fixture(path, tmp_path):
    # Permanent-failure tests verify the leak before explicitly releasing their
    # own lock; final fixture cleanup is bounded to the generated test subtree.
    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert path.name.startswith("novel-media-")
    import shutil
    shutil.rmtree(path)


def test_real_transient_windows_sharing_preserves_guard_and_removes_directory(controlled, tmp_path):
    if os.name != "nt":
        with media._media_inspection_directory() as directory:
            path = Path(directory)
        assert not path.exists()
        return
    controlled.probe_wait = True
    refused = OSError("controlled authority cancellation")
    release, timer = None, None

    def guard():
        nonlocal release, timer
        if controlled.children and (controlled.directories[-1] / "ready").exists():
            release = hold_directory(controlled.directories[-1])
            timer = threading.Timer(0.04, release)
            timer.start()
            raise refused

    try:
        with pytest.raises(OSError) as raised:
            media.inspect_media(FLAC_BYTES, "audio", guard=guard)
        assert raised.value is refused
        assert not any(path.exists() for path in controlled.directories)
        assert not getattr(refused, "__notes__", [])
        assert_released(controlled.children[0][1])
    finally:
        if timer is not None:
            timer.join(timeout=1)
            assert not timer.is_alive()
        if release is not None:
            release()


@pytest.mark.parametrize("guard_failure", [True, False])
def test_real_permanent_windows_sharing_is_explicit_and_keeps_primary_guard(controlled, tmp_path, guard_failure):
    if os.name != "nt":
        with media._media_inspection_directory() as directory:
            path = Path(directory)
        assert not path.exists()
        return
    controlled.probe_wait = guard_failure
    controlled.probe_exitcode = 0 if guard_failure else 7
    refused = OSError("controlled authority cancellation")
    release = None

    def guard():
        nonlocal release
        if controlled.children and release is None:
            release = hold_directory(controlled.directories[-1])
        if guard_failure and release is not None:
            raise refused

    try:
        with pytest.raises(OSError if guard_failure else MediaValidationError) as raised:
            media.inspect_media(FLAC_BYTES, "audio", guard=guard)
        if guard_failure:
            assert raised.value is refused
            assert raised.value.__notes__ == ["Media inspection temporary directory cleanup did not complete."]
            assert isinstance(raised.value.__cause__, MediaValidationError)
            assert str(raised.value.__cause__) == "media temporary directory cleanup failed"
        else:
            assert str(raised.value) == "media decoding failed"
            assert raised.value.__cause__ is None and raised.value.__suppress_context__
        assert len(controlled.directories) == 1 and controlled.directories[0].exists()
        assert list(controlled.directories[0].iterdir()) == []
        assert_released(controlled.children[0][1])
    finally:
        if release is not None:
            release()
        for path in controlled.directories:
            if path.exists():
                remove_owned_fixture(path, tmp_path)
