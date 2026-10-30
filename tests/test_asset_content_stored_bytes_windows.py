"""Physical byte observations use the same verified native content handle."""
import base64
import ctypes
from ctypes import wintypes
import msvcrt
import os

import pytest

from app.services.asset_bounded_file_windows import WindowsBoundedAssetError
from test_asset_physical_observation import observe
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != 'nt', reason='Windows native handle')]


def sparse_file(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    with path.open('r+b') as target:
        native = msvcrt.get_osfhandle(target.fileno())
        result = wintypes.DWORD()
        if not kernel.DeviceIoControl(native, 0x000900C4, None, 0, None, 0, ctypes.byref(result), None):
            pytest.skip('synthetic sparse files unsupported on this volume')
        target.truncate(0)
        target.seek(1024 * 1024)
        target.write(b'!')
        target.flush()
        os.fsync(target.fileno())


def compressed_file(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    with path.open('r+b') as target:
        native = msvcrt.get_osfhandle(target.fileno())
        result, format_value = wintypes.DWORD(), wintypes.WORD(1)
        if not kernel.DeviceIoControl(native, 0x0009C040, ctypes.byref(format_value), ctypes.sizeof(format_value),
                                      None, 0, ctypes.byref(result), None):
            pytest.skip('synthetic compressed files unsupported on this volume')
        target.flush()
        os.fsync(target.fileno())


def reference_size(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetCompressedFileSizeW.restype = wintypes.DWORD
    upper = wintypes.DWORD()
    ctypes.set_last_error(0)
    lower = kernel.GetCompressedFileSizeW(str(path), ctypes.byref(upper))
    if lower == 0xffffffff and ctypes.get_last_error():
        pytest.skip('volume cannot report compressed file size')
    return (upper.value << 32) | lower


def test_sparse_content_measures_stored_not_logical_bytes(audio_history):
    e = audio_history
    data = b'\0' * (1024 * 1024) + b'!'
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        asset = e.rig.assets.create(e.rig.nid, 'sparse.bin', base64.b64encode(data).decode(),
                                    'application/octet-stream', 'audio')
    content_path = e.rig.assets._bin_path(asset['id'])
    sparse_file(content_path)
    reference = reference_size(content_path)
    assert 0 < reference < len(data), 'sparse fixture must demonstrate a difference'
    before = snapshot(e.rig.root)
    result = observe(e, asset['id'])
    assert result['content_file_length_bytes'] == len(data)
    assert result['content_default_stream_stored_bytes'] == reference
    assert result['content_other_streams'] == 'UNKNOWN'
    assert result['metadata_stored_bytes'] == 'UNKNOWN'
    assert result['allocated_storage_bytes'] == 'UNKNOWN'
    assert result['quota_admission'] == 'NOT_AVAILABLE'
    assert snapshot(e.rig.root) == before


def test_compressed_content_measures_default_stream_only(audio_history):
    e = audio_history
    data = b'z' * (1024 * 1024)
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        asset = e.rig.assets.create(e.rig.nid, 'compressible.bin', base64.b64encode(data).decode(),
                                    'application/octet-stream', 'audio')
    content_path = e.rig.assets._bin_path(asset['id'])
    compressed_file(content_path)
    reference = reference_size(content_path)
    if reference >= len(data):
        pytest.skip('volume did not compress the synthetic file')
    result = observe(e, asset['id'])
    assert result['content_default_stream_stored_bytes'] == reference
    assert result['content_other_streams'] == 'UNKNOWN'
    assert result['allocated_storage_bytes'] == 'UNKNOWN'
    assert result['quota_admission'] == 'NOT_AVAILABLE'


def test_unsupported_native_measurement_keeps_unknown_and_integrity(audio_history, monkeypatch):
    from app.services import asset_bounded_file_windows
    def unavailable(*args, **kwargs):
        raise WindowsBoundedAssetError('ASSET_BOUNDED_READ_UNSUPPORTED')
    monkeypatch.setattr(asset_bounded_file_windows._Kernel, 'stored_bytes', unavailable)
    result = observe(audio_history)
    assert result['content_default_stream_stored_bytes'] == 'UNKNOWN'
    assert result['allocated_storage_bytes'] == 'UNKNOWN'
    assert result['quota_admission'] == 'NOT_AVAILABLE'


def test_alternate_stream_is_not_claimed_in_file_total(audio_history):
    e = audio_history
    path = e.rig.assets._bin_path(e.asset['id'])
    try:
        with open(str(path) + ':synthetic-capacity-test', 'xb') as other:
            other.write(b'synthetic alternate stream')
    except OSError:
        pytest.skip('alternate streams unsupported on this volume')
    result = observe(e)
    assert result['content_default_stream_stored_bytes'] == reference_size(path)
    assert result['content_other_streams'] == 'UNKNOWN'
    assert result['allocated_storage_bytes'] == 'UNKNOWN'
    assert result['quota_admission'] == 'NOT_AVAILABLE'


def test_native_report_of_extra_hardlink_rejects_observation(audio_history, monkeypatch):
    # Inject a native-query response: this proves detection, not an actual race.
    from app.services import asset_bounded_file_windows
    original = asset_bounded_file_windows._Kernel._query
    def extra_link(api, handle, kind, structure, guard):
        value = original(api, handle, kind, structure, guard)
        if kind == 1:
            value.links = 2
        return value
    monkeypatch.setattr(asset_bounded_file_windows._Kernel, '_query', extra_link)
    with pytest.raises(ValueError, match='asset physical observation unavailable'):
        observe(audio_history)


def test_measurement_requires_verified_handle_and_current_authority(audio_history):
    from app.services.asset_bounded_file_windows import open_windows_bounded_asset
    e = audio_history
    access = {'valid': True}
    def guard():
        if not access['valid']:
            raise PermissionError('authority revoked')
    with open_windows_bounded_asset(e.rig.assets._bin_path(e.asset['id']), trusted_root=e.rig.assets.root,
            expected_size=len(e.content), max_bytes=e.rig.assets.MAX_BYTES,
            expected_sha256=e.asset['sha256'], guard=guard) as lease:
        with pytest.raises(WindowsBoundedAssetError):
            lease.stored_bytes()
        assert lease.read_all() == e.content
        assert lease.stored_bytes() == reference_size(e.rig.assets._bin_path(e.asset['id']))
        access['valid'] = False
        with pytest.raises(PermissionError, match='authority revoked'):
            lease.stored_bytes()
        access['valid'] = True
