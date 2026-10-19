"""Opt-in original owner read safety; default content behavior stays unchanged."""
import hashlib
import os

import pytest

from app.services.asset_library_service import AssetIntegrityError, AssetLibraryService


@pytest.fixture
def content(tmp_path):
    owner = AssetLibraryService(tmp_path)
    data = b"original content" * 5000
    path = owner.root / "sample.bin"
    path.write_bytes(data)
    meta = {"id": "sample", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return owner, path, meta, data


def require_safe_platform():
    if not getattr(os, "O_NOFOLLOW", 0) or not getattr(os, "O_NONBLOCK", 0):
        pytest.skip("bounded original-owner read unsupported on this platform")


def test_bounded_reader_matches_default_and_guards_chunks(content):
    require_safe_platform()
    owner, path, meta, data = content
    calls = []
    assert owner._verified_content(meta) == data
    assert owner._verified_content(meta, max_bytes=len(data), guard=lambda: calls.append(True)) == data
    assert len(calls) >= 7
    assert path.read_bytes() == data


@pytest.mark.parametrize("limit", [True, False, 0, -1, "10", 1.0, 26 * 1024 * 1024])
def test_invalid_opt_in_limit_rejected_before_path_access(content, monkeypatch, limit):
    owner, _, meta, _ = content
    monkeypatch.setattr(owner, "_bin_path", lambda *_: pytest.fail("path admission happened"))
    with pytest.raises(ValueError, match="ASSET_BOUNDED_READ_LIMIT_INVALID"):
        owner._verified_content(meta, max_bytes=limit)


def test_oversize_rejected_before_path_or_binary_read(content, monkeypatch):
    owner, _, meta, _ = content
    monkeypatch.setattr(owner, "_bin_path", lambda *_: pytest.fail("path admission happened"))
    with pytest.raises(ValueError, match="ASSET_BOUNDED_READ_LIMIT"):
        owner._verified_content(meta, max_bytes=1)


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_NONBLOCK"])
def test_unavailable_primitives_fail_closed_without_default_fallback(content, monkeypatch, flag):
    owner, _, meta, data = content
    if os.name == "nt":
        from app.services import asset_bounded_file_windows
        monkeypatch.setattr(asset_bounded_file_windows, "windows_bounded_read_supported", lambda: False)
    else:
        monkeypatch.setattr(os, flag, 0, raising=False)
    with pytest.raises(ValueError, match="ASSET_BOUNDED_READ_UNSUPPORTED"):
        owner._verified_content(meta, max_bytes=len(data))
    assert owner._verified_content(meta) == data


def test_observed_symlink_never_opens_target(content, tmp_path):
    require_safe_platform()
    owner, path, meta, data = content
    target = tmp_path / "private-target"
    target.write_bytes(data)
    path.unlink(); path.symlink_to(target)
    with pytest.raises(AssetIntegrityError):
        owner._verified_content(meta, max_bytes=len(data))
    assert target.read_bytes() == data


def test_fifo_is_rejected_before_open(content, monkeypatch):
    require_safe_platform()
    if not hasattr(os, "mkfifo"): pytest.skip("no FIFO primitive")
    owner, path, meta, data = content
    path.unlink(); os.mkfifo(path)
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("FIFO opened"))
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_INVALID"):
        owner._verified_content(meta, max_bytes=len(data))


def test_swap_to_symlink_between_stat_and_open_is_rejected(content, tmp_path, monkeypatch):
    require_safe_platform()
    owner, path, meta, data = content
    target = tmp_path / "outside.bin"; target.write_bytes(data)
    original = os.open
    def replaced(filename, flags):
        path.unlink(); path.symlink_to(target)
        return original(filename, flags)
    monkeypatch.setattr(os, "open", replaced)
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_UNAVAILABLE"):
        owner._verified_content(meta, max_bytes=len(data))


def test_growth_during_guarded_read_fails_integrity(content):
    require_safe_platform()
    owner, path, meta, data = content
    calls = 0
    def guard():
        nonlocal calls
        calls += 1
        if calls == 2:
            with path.open("ab") as handle: handle.write(b"changed")
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_INVALID"):
        owner._verified_content(meta, max_bytes=len(data), guard=guard)


def test_same_bytes_replacement_between_stat_and_open_rejected(content, monkeypatch):
    require_safe_platform()
    owner, path, meta, data = content
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(data)
    original = os.open
    def replaced(filename, flags):
        os.replace(replacement, path)
        return original(filename, flags)
    monkeypatch.setattr(os, "open", replaced)
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_INVALID"):
        owner._verified_content(meta, max_bytes=len(data))


def test_fifo_replacement_after_stat_uses_nonblocking_open(content, monkeypatch):
    require_safe_platform()
    if not hasattr(os, "mkfifo"): pytest.skip("no FIFO primitive")
    owner, path, meta, data = content
    original = os.open
    def replaced(filename, flags):
        assert flags & os.O_NONBLOCK and flags & os.O_NOFOLLOW
        path.unlink(); os.mkfifo(path)
        return original(filename, flags)
    monkeypatch.setattr(os, "open", replaced)
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_INVALID"):
        owner._verified_content(meta, max_bytes=len(data))


def test_fd_closed_if_validation_after_open_fails(content, monkeypatch):
    require_safe_platform()
    owner, _, meta, data = content
    original_open, original_fstat = os.open, os.fstat
    opened = []
    def opening(*args):
        descriptor = original_open(*args); opened.append(descriptor); return descriptor
    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(os, "fstat", lambda *_: (_ for _ in ()).throw(OSError("private path")))
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_UNAVAILABLE"):
        owner._verified_content(meta, max_bytes=len(data))
    assert len(opened) == 1
    with pytest.raises(OSError): original_fstat(opened[0])


def test_fd_closed_if_fdopen_fails(content, monkeypatch):
    require_safe_platform()
    owner, _, meta, data = content
    original_open, original_fstat = os.open, os.fstat
    opened = []
    def opening(*args):
        descriptor = original_open(*args); opened.append(descriptor); return descriptor
    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(os, "fdopen", lambda *_: (_ for _ in ()).throw(OSError("private path")))
    with pytest.raises(AssetIntegrityError, match="ASSET_BOUNDED_CONTENT_UNAVAILABLE"):
        owner._verified_content(meta, max_bytes=len(data))
    assert len(opened) == 1
    with pytest.raises(OSError): original_fstat(opened[0])


def test_open_fd_closed_on_mid_read_authority_revocation(content, monkeypatch):
    require_safe_platform()
    owner, _, meta, data = content
    original_open, original_fstat = os.open, os.fstat
    opened, calls = [], 0
    def opening(*args):
        descriptor = original_open(*args); opened.append(descriptor); return descriptor
    def guard():
        nonlocal calls
        calls += 1
        if calls >= 2: raise PermissionError("authority revoked")
    monkeypatch.setattr(os, "open", opening)
    with pytest.raises(PermissionError, match="authority revoked"):
        owner._verified_content(meta, max_bytes=len(data), guard=guard)
    assert len(opened) == 1
    with pytest.raises(OSError): original_fstat(opened[0])


def test_authority_error_preserved(content):
    require_safe_platform()
    owner, _, meta, data = content
    def guard(): raise PermissionError("authority revoked")
    with pytest.raises(PermissionError, match="authority revoked"):
        owner._verified_content(meta, max_bytes=len(data), guard=guard)
