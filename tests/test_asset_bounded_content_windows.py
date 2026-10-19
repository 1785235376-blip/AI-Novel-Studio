"""Real Windows objects in owned task tmp paths; no owner integration yet.

NPFS has no on-disk pipe file: our one-instance temporary pipe name is derived
from this task's tmp path plus a UUID, never an existing pipe. Closing its sole
owned server handle removes it. No privilege/security setting is changed.
"""
import ctypes
from ctypes import wintypes
from dataclasses import replace
import hashlib
import json
import mmap
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from app.services import asset_bounded_file_windows as reader

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='BLOCKED: native Windows required')


@pytest.fixture
def asset(tmp_path):
    root = tmp_path / 'assets'; root.mkdir()
    data = bytes(range(256)) * 600
    path = root / 'sample.bin'; path.write_bytes(data)
    return root, path, data


def arguments(asset, **updates):
    root, _, data = asset
    return dict(trusted_root=root, expected_size=len(data), max_bytes=len(data),
                expected_sha256=hashlib.sha256(data).hexdigest(), guard=lambda: None, **updates)


@pytest.fixture
def native(monkeypatch):
    if not reader.windows_bounded_read_supported():
        pytest.skip('BLOCKED: required native Windows file entry points unavailable')
    api = reader._Kernel()
    create, close, read = api.dll.CreateFileW, api.dll.CloseHandle, api.dll.ReadFile
    state = {'active': set(), 'opens': [], 'reads': [], 'api': api}
    def opening(*args):
        handle = create(*args)
        state['opens'].append(dict(path=args[0], access=args[1], share=args[2],
                                   security=args[3], disposition=args[4], flags=args[5],
                                   handle=handle))
        if handle not in (None, ctypes.c_void_p(-1).value):
            assert handle not in state['active']
            state['active'].add(handle)
        return handle
    def closing(handle):
        result = close(handle)
        if result:
            assert handle in state['active'], 'unowned or double native close'
            state['active'].remove(handle)
        return result
    def reading(handle, buffer, count, received, overlapped):
        result = read(handle, buffer, count, received, overlapped)
        state['reads'].append(dict(requested=count, received=ctypes.cast(received,
                             ctypes.POINTER(wintypes.DWORD)).contents.value, success=bool(result)))
        return result
    monkeypatch.setattr(api.dll, 'CreateFileW', opening)
    monkeypatch.setattr(api.dll, 'CloseHandle', closing)
    monkeypatch.setattr(api.dll, 'ReadFile', reading)
    monkeypatch.setattr(reader, '_kernel_api', lambda: api)
    yield state
    assert not state['active'], 'native asset/probe handle leaked'


def test_real_read_has_exact_bytes_bounds_no_follow_and_read_sharing(asset, native):
    calls = []
    options = arguments(asset); options['guard'] = lambda: calls.append(True)
    assert reader.read_windows_bounded_asset(asset[1], **options) == asset[2]
    assert len(calls) >= 10
    assert native['reads'] and all(0 < r['requested'] <= 65536 for r in native['reads'])
    assert sum(r['received'] for r in native['reads']) == len(asset[2])
    assert native['opens'] and all(o['share'] == 1 and o['flags'] & 0x00200000
                                  and o['disposition'] == 3 and o['security'] is None
                                  for o in native['opens'])
    assert asset[1].read_bytes() == asset[2]


@pytest.mark.parametrize('size', [1, 65535, 65536, 65537])
def test_exact_limit_boundaries(asset, native, size):
    root, path, _ = asset; data = b'x' * size; path.write_bytes(data)
    assert reader.read_windows_bounded_asset(path, **arguments((root, path, data))) == data
    assert sum(r['received'] for r in native['reads']) == size


@pytest.mark.parametrize('limit', [True, False, 0, -1, '1', 1.0, 25 * 1024 * 1024 + 1])
def test_invalid_limit_never_opens(asset, native, limit):
    options = arguments(asset); options['max_bytes'] = limit
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_READ_LIMIT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **options)
    assert native['opens'] == native['reads'] == []


@pytest.mark.parametrize('size', [True, False, 0, -1, '1', 1.0, 1000000])
def test_invalid_expected_size_never_opens(asset, native, size):
    options = arguments(asset); options['expected_size'] = size
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_READ_LIMIT$'):
        reader.read_windows_bounded_asset(asset[1], **options)
    assert native['opens'] == native['reads'] == []


def test_actual_oversize_or_truncation_never_reads(asset, native):
    for data in (asset[2] + b'excess', asset[2][:-1], b''):
        asset[1].write_bytes(data)
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['opens'] == native['reads'] == []


def test_same_size_bad_digest_returns_no_bytes(asset, native):
    options = arguments(asset); options['expected_sha256'] = '0' * 64
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **options)
    assert native['reads']


@pytest.mark.parametrize('name', ['NUL.bin', 'con.bin', 'COM1.bin', 'LPT9.bin',
                                  'sample.bin:stream', 'sample.bin.', 'sample.bin ',
                                  'other.txt'])
def test_device_ads_and_non_owner_names_rejected_before_open(asset, native, name):
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[0] / name, **arguments(asset))
    assert native['opens'] == native['reads'] == []


def test_outside_child_and_parent_traversal_never_opens(asset, native):
    for path in (asset[0].parent / 'outside.bin', str(asset[0] / '..' / 'sample.bin')):
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            reader.read_windows_bounded_asset(path, **arguments(asset))
    assert native['opens'] == native['reads'] == []


def test_directory_at_leaf_never_opens(asset, native):
    asset[1].unlink(); asset[1].mkdir()
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['opens'] == native['reads'] == []


def _symlink(link, target):
    try:
        link.symlink_to(target)
    except OSError as error:
        if getattr(error, 'winerror', None) in (5, 1314):
            pytest.skip(f'BLOCKED: file-symlink creation denied, winerror={error.winerror}; no privilege change')
        raise


def test_real_file_symlink_never_opens_target(asset, native):
    root, path, data = asset
    target = root / 'target.bin'; target.write_bytes(data)
    path.unlink(); _symlink(path, target)
    try:
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            reader.read_windows_bounded_asset(path, **arguments(asset))
        assert native['opens'] == native['reads'] == []
        assert target.read_bytes() == data
    finally:
        path.unlink()


def test_real_junction_at_asset_leaf_rejected_and_target_untouched(asset, native):
    root, path, data = asset
    target = root / 'junction-target'; target.mkdir(); (target / 'proof').write_bytes(data)
    path.unlink()
    result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(path), str(target)],
                            capture_output=True)
    if result.returncode:
        pytest.fail(f'owned temporary junction fixture failed, exit={result.returncode}')
    try:
        assert path.lstat().st_file_attributes & 0x400
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            reader.read_windows_bounded_asset(path, **arguments(asset))
        assert native['opens'] == native['reads'] == []
        assert (target / 'proof').read_bytes() == data
    finally:
        os.rmdir(path)  # Remove only this exact owned junction, never its target tree.
    assert (target / 'proof').read_bytes() == data


@pytest.fixture
def pipe(tmp_path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                       wintypes.DWORD, ctypes.c_void_p]
    kernel.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]; kernel.CloseHandle.restype = wintypes.BOOL
    task = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:24]
    name = '\\\\.\\pipe\\PoemSeedAssetBoundedTests.' + task + '.' + uuid4().hex
    handle = kernel.CreateNamedPipeW(name, 0x40080003, 0, 1, 4096, 4096, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error in (5, 1314):
            pytest.skip(f'BLOCKED: owned NPFS fixture creation denied, winerror={error}')
        pytest.fail(f'owned NPFS fixture creation failed, winerror={error}')
    try:
        yield name, handle
    finally:
        assert kernel.CloseHandle(handle)


def test_real_named_pipe_path_rejected_without_connecting(asset, native, pipe):
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(pipe[0], **arguments(asset))
    assert native['opens'] == native['reads'] == []


def test_real_pipe_handle_rejected_before_metadata_or_body(native, pipe, monkeypatch):
    monkeypatch.setattr(native['api'], '_query', lambda *_a: pytest.fail('pipe metadata queried'))
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        native['api'].identity(pipe[1], lambda: None)
    assert native['reads'] == []


def test_same_content_replacement_between_lstat_and_open_rejected(asset, native, monkeypatch):
    root, path, data = asset
    other = root / 'replacement.bin'; other.write_bytes(data)
    previous = path.stat(); os.utime(other, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    open_native = native['api'].open
    swapped = False
    def opening(filename, access, guard):
        nonlocal swapped
        if access == 0x80000000 and not swapped:
            swapped = True; os.replace(other, path)
        return open_native(filename, access, guard)
    monkeypatch.setattr(native['api'], 'open', opening)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(path, **arguments(asset))
    assert swapped and native['reads'] == [] and path.read_bytes() == data


def test_leaf_swap_to_symlink_after_lstat_never_reads_target(asset, native, monkeypatch):
    root, path, data = asset
    target = root / 'target.bin'; target.write_bytes(data)
    admission = root / 'symlink-check.bin'; _symlink(admission, target); admission.unlink()
    original = native['api'].open
    def opening(filename, access, guard):
        if access == 0x80000000:
            path.unlink(); path.symlink_to(target)
        return original(filename, access, guard)
    monkeypatch.setattr(native['api'], 'open', opening)
    try:
        with pytest.raises(reader.WindowsBoundedAssetError):
            reader.read_windows_bounded_asset(path, **arguments(asset))
        assert native['reads'] == [] and target.read_bytes() == data
    finally:
        path.unlink()


def test_existing_write_handle_causes_private_safe_closed_failure(asset, native):
    root, path, data = asset
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]; kernel.CloseHandle.restype = wintypes.BOOL
    writer = kernel.CreateFileW(str(path), 0x40000000, 7, None, 3, 0, None)
    assert writer != ctypes.c_void_p(-1).value
    try:
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_UNAVAILABLE$'):
            reader.read_windows_bounded_asset(path, **arguments(asset))
        assert native['reads'] == []
    finally:
        assert kernel.CloseHandle(writer)
    assert path.read_bytes() == data


def test_other_process_cannot_obtain_write_or_delete_access(asset, native):
    code = '''import ctypes,json,sys
from ctypes import wintypes as w
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE];k.CreateFileW.restype=w.HANDLE
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
rows=[]
for access in (0x40000000,0x10000):
 h=k.CreateFileW(sys.argv[1],access,7,None,3,0,None); error=ctypes.get_last_error()
 valid=h not in (None,ctypes.c_void_p(-1).value)
 if valid:k.CloseHandle(h)
 rows.append({'opened':valid,'error':error})
print(json.dumps(rows))'''
    with reader.open_windows_bounded_asset(asset[1], **arguments(asset)) as lease:
        result = subprocess.run([sys.executable, '-B', '-c', code, str(asset[1])],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [{'opened': False, 'error': 32}, {'opened': False, 'error': 32}]
        assert lease.read_all() == asset[2]


def test_replacement_after_open_is_blocked_by_read_lease(asset, native):
    replacement = asset[0] / 'replacement.bin'; replacement.write_bytes(asset[2])
    with reader.open_windows_bounded_asset(asset[1], **arguments(asset)) as lease:
        with pytest.raises(OSError) as failure:
            os.replace(replacement, asset[1])
        assert failure.value.winerror in (5, 32)
        assert lease.read_all() == asset[2]


def test_full_128_bit_identity_and_volume_are_compared(asset, native, monkeypatch):
    identity = native['api'].identity
    probes = 0
    def queried(handle, guard):
        nonlocal probes
        found = identity(handle, guard); probes += 1
        if probes == 3:
            changed = bytearray(found.file_id); changed[15] ^= 1
            return replace(found, file_id=bytes(changed))
        return found
    monkeypatch.setattr(native['api'], 'identity', queried)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['reads'] == []


def test_volume_identity_mismatch_rejected(asset, native, monkeypatch):
    query = native['api'].identity; calls = 0
    def queried(handle, guard):
        nonlocal calls
        found = query(handle, guard); calls += 1
        return replace(found, volume=found.volume ^ (1 << 40)) if calls == 3 else found
    monkeypatch.setattr(native['api'], 'identity', queried)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['reads'] == []


def test_capability_query_unavailable_closes_and_never_falls_back(asset, native, monkeypatch):
    original = native['api'].dll.GetFileInformationByHandleEx
    def queried(handle, kind, value, size):
        if kind == 18:
            ctypes.set_last_error(50); return 0
        return original(handle, kind, value, size)
    monkeypatch.setattr(native['api'].dll, 'GetFileInformationByHandleEx', queried)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['reads'] == []


def test_guard_denial_before_open_is_preserved(asset, native):
    def denied(): raise PermissionError('authority revoked')
    options = arguments(asset); options['guard'] = denied
    with pytest.raises(PermissionError, match='^authority revoked$'):
        reader.read_windows_bounded_asset(asset[1], **options)
    assert native['opens'] == native['reads'] == []


def test_guard_revocation_after_native_read_closes_without_return(asset, native):
    def guard():
        if native['reads']: raise PermissionError('authority revoked')
    options = arguments(asset); options['guard'] = guard
    with pytest.raises(PermissionError, match='^authority revoked$'):
        reader.read_windows_bounded_asset(asset[1], **options)
    assert len(native['reads']) == 1


def test_guard_revocation_takes_priority_over_io_projection(asset, native, monkeypatch):
    revoked = False
    def failed(*_args):
        nonlocal revoked
        revoked = True; ctypes.set_last_error(5); return 0
    def guard():
        if revoked: raise PermissionError('authority revoked')
    monkeypatch.setattr(native['api'].dll, 'ReadFile', failed)
    options = arguments(asset); options['guard'] = guard
    with pytest.raises(PermissionError, match='^authority revoked$'):
        reader.read_windows_bounded_asset(asset[1], **options)


def test_private_os_error_is_fixed_and_does_not_open(asset, native, monkeypatch):
    def unavailable(_self): raise OSError('SYNTHETIC_PRIVATE_PATH')
    monkeypatch.setattr(Path, 'lstat', unavailable)
    with pytest.raises(reader.WindowsBoundedAssetError) as error:
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert str(error.value) == 'ASSET_BOUNDED_CONTENT_UNAVAILABLE'
    assert native['opens'] == native['reads'] == []


def test_lease_is_single_use_and_closed_lease_cannot_read(asset, native):
    with reader.open_windows_bounded_asset(asset[1], **arguments(asset)) as lease:
        assert lease.read_all() == asset[2]
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            lease.read_all()
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        lease.verify_current()


def _directory_handle(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]; kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0x02200000, None)
    assert handle not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
    return kernel, handle


def test_real_directory_handle_is_not_a_regular_disk_file(asset, native):
    kernel, handle = _directory_handle(asset[0])
    try:
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            native['api'].identity(handle, lambda: None)
        assert native['reads'] == []
    finally:
        assert kernel.CloseHandle(handle)


def test_junction_swap_after_lstat_does_not_follow_or_read(asset, native, monkeypatch):
    root, path, data = asset
    target = root / 'outside-target'; target.mkdir(); (target / 'proof').write_bytes(data)
    link = root / 'replacement-link.bin'
    result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
    assert result.returncode == 0, 'owned junction fixture creation failed'
    opening = native['api'].open
    swapped = False
    def replaced(filename, access, guard):
        nonlocal swapped
        if access == 0x80000000 and not swapped:
            swapped = True; path.unlink(); os.rename(link, path)
        return opening(filename, access, guard)
    monkeypatch.setattr(native['api'], 'open', replaced)
    try:
        with pytest.raises(reader.WindowsBoundedAssetError):
            reader.read_windows_bounded_asset(path, **arguments(asset))
        assert swapped and native['reads'] == []
        assert (target / 'proof').read_bytes() == data
    finally:
        os.rmdir(path if swapped else link)
    assert (target / 'proof').read_bytes() == data


def test_root_junction_is_rejected_without_opening_asset(asset, native):
    link = asset[0].parent / 'linked-assets'
    result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(asset[0])], capture_output=True)
    assert result.returncode == 0, 'owned root junction fixture creation failed'
    try:
        options = arguments(asset); options['trusted_root'] = link
        with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
            reader.read_windows_bounded_asset(link / 'sample.bin', **options)
        assert native['opens'] == native['reads'] == []
    finally:
        os.rmdir(link)


def test_existing_writable_mapping_cannot_return_stale_verified_content(asset, native):
    # Real pre-existing mapped writer; no model or native executable is run.
    with asset[1].open('r+b') as writer:
        mapped = mmap.mmap(writer.fileno(), 0, access=mmap.ACCESS_WRITE)
    changed = False
    def guard():
        nonlocal changed
        if native['reads'] and not changed:
            mapped[0] ^= 1; mapped.flush(); changed = True
    options = arguments(asset); options['guard'] = guard
    try:
        with pytest.raises(reader.WindowsBoundedAssetError) as error:
            reader.read_windows_bounded_asset(asset[1], **options)
        assert error.value.code in (reader.UNAVAILABLE, reader.INVALID)
    finally:
        mapped.close()


def test_unavailable_native_entry_points_fail_closed(asset, monkeypatch):
    def unavailable(*_args, **_kwargs): raise OSError('SYNTHETIC_PRIVATE_LOADER_DETAIL')
    monkeypatch.setattr(ctypes, 'WinDLL', unavailable)
    assert reader.windows_bounded_read_supported() is False
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))


@pytest.mark.parametrize('path,root', [
    ('\\\\host.invalid\\share\\sample.bin', '\\\\host.invalid\\share'),
    ('\\\\?\\GLOBALROOT\\Device\\Synthetic\\sample.bin', '\\\\?\\GLOBALROOT\\Device\\Synthetic'),
    ('relative\\sample.bin', 'relative'),
])
def test_untrusted_namespaces_never_open_or_contact_external_paths(asset, native, path, root):
    options = arguments(asset); options['trusted_root'] = root
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(path, **options)
    assert native['opens'] == native['reads'] == []


@pytest.mark.parametrize('delta', [-1, 1])
def test_real_resize_between_lstat_and_open_never_reads(asset, native, monkeypatch, delta):
    opening = native['api'].open
    def resized(filename, access, guard):
        if access == 0x80000000:
            asset[1].write_bytes(asset[2][:-1] if delta < 0 else asset[2] + b'x')
        return opening(filename, access, guard)
    monkeypatch.setattr(native['api'], 'open', resized)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['reads'] == []


def test_native_read_error_is_fixed_and_closes(asset, native, monkeypatch):
    def failed(*_args):
        ctypes.set_last_error(5); return 0
    monkeypatch.setattr(native['api'].dll, 'ReadFile', failed)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_UNAVAILABLE$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))


def test_unexpected_native_eof_cannot_return_partial_content(asset, native, monkeypatch):
    def short(_handle, _buffer, _count, received, _overlapped):
        ctypes.cast(received, ctypes.POINTER(wintypes.DWORD)).contents.value = 0
        return 1
    monkeypatch.setattr(native['api'].dll, 'ReadFile', short)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))


def test_unknown_handle_type_is_unsupported_without_body_read(asset, native, monkeypatch):
    monkeypatch.setattr(native['api'].dll, 'GetFileType', lambda _handle: 0)
    with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$'):
        reader.read_windows_bounded_asset(asset[1], **arguments(asset))
    assert native['reads'] == []


def test_single_root_rebind_is_blocked_or_detected_not_ancestor_aba_claim(asset, native):
    root, path, data = asset
    moved = root.parent / 'owned-old-assets'
    changed = False
    try:
        with reader.open_windows_bounded_asset(path, **arguments(asset)) as lease:
            try:
                root.rename(moved)
            except OSError as error:
                assert error.winerror in (5, 32)
                assert lease.read_all() == data
            else:
                changed = True; root.mkdir(); (root / path.name).write_bytes(data)
                with pytest.raises(reader.WindowsBoundedAssetError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
                    lease.read_all()
    finally:
        if changed:
            (root / path.name).unlink(); root.rmdir(); moved.rename(root)
    assert path.read_bytes() == data


def test_caller_exception_preserved_and_all_native_handles_closed(asset, native):
    with pytest.raises(RuntimeError, match='^synthetic caller cancellation$'):
        with reader.open_windows_bounded_asset(asset[1], **arguments(asset)):
            raise RuntimeError('synthetic caller cancellation')
    assert native['reads'] == []
    assert native['active'] == set()


def test_guard_revoked_after_real_final_close_prevents_return(asset, native, monkeypatch):
    close = native['api'].close
    state = {'revoked': False, 'real_final_close_succeeded': False}
    def closing(handle):
        result = close(handle)  # Real CloseHandle, with owned-handle tracking.
        main = next((item['handle'] for item in native['opens']
                     if item['access'] == 0x80000000), None)
        if result and handle == main:
            assert not native['active']
            state['real_final_close_succeeded'] = True
            state['revoked'] = True
        return result
    def guard():
        if state['revoked']:
            raise PermissionError('authority revoked after native close')
    monkeypatch.setattr(native['api'], 'close', closing)
    options = arguments(asset); options['guard'] = guard
    rejected, returned_bytes = False, None
    try:
        data = reader.read_windows_bounded_asset(asset[1], **options)
    except PermissionError as error:
        assert str(error) == 'authority revoked after native close'
        rejected = True
    else:
        returned_bytes = len(data)
    assert state == {'revoked': True, 'real_final_close_succeeded': True}
    assert not native['active']
    assert rejected, f'returned {returned_bytes} verified bytes after real final close revoked authority'
    assert returned_bytes is None
