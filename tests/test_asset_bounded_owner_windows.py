"""Windows owner wiring over genuine File records and synthetic image bytes.

Service methods only: no HTTP, UI, model/provider or complete V2 acceptance.
"""
import base64
import copy
import ctypes
import io
import os

from PIL import Image, ImageDraw
import pytest

from app.services.asset_library_service import AssetIntegrityError
from app.services import asset_bounded_file_windows as native_reader
from test_v2_independent_workspace import rig
from test_comic_ora_staging import staging, prepare, stage
from test_asset_bounded_content_windows import native

pytestmark = [pytest.mark.skipif(os.name != 'nt', reason='BLOCKED: native Windows required'),
              pytest.mark.file_backend_only,
              pytest.mark.parametrize('rig', ['file'], indirect=True)]


@pytest.fixture(params=['PNG', 'JPEG'])
def file_image(rig, request):
    kind = request.param
    image = Image.new('RGB', (96, 80), 'white')
    ImageDraw.Draw(image).rectangle((8, 8, 60, 60), fill='blue')
    stream = io.BytesIO(); image.save(stream, format=kind); image.close()
    raw = stream.getvalue(); mime = 'image/png' if kind == 'PNG' else 'image/jpeg'
    row = rig.assets.create(rig.nid, 'SYNTHETIC-' + kind + '.' + kind.lower(),
                            base64.b64encode(raw).decode(), mime, 'image')
    return rig, row, raw, kind


def test_owner_reads_real_png_and_jpeg_without_metadata_changes(file_image):
    rig, row, raw, kind = file_image
    before = copy.deepcopy(rig.assets._load(row['id']))
    calls = []
    actual = rig.assets.content(row['id'], max_bytes=len(raw), guard=lambda: calls.append(True))
    assert actual == raw and len(calls) >= 7
    assert rig.assets._load(row['id']) == before
    assert rig.assets._bin_path(row['id']).read_bytes() == raw
    with Image.open(io.BytesIO(actual)) as decoded:
        decoded.load(); assert decoded.format == kind and decoded.size == (96, 80)


@pytest.mark.parametrize('mutation', ['digest', 'truncate', 'extend', 'missing'])
def test_owner_corrupt_image_preserves_integrity_error_and_metadata(file_image, native, mutation):
    rig, row, raw, _ = file_image
    before = copy.deepcopy(rig.assets._load(row['id']))
    path = rig.assets._bin_path(row['id'])
    if mutation == 'missing':
        path.unlink()
    else:
        damaged = {'digest': bytes([raw[0] ^ 1]) + raw[1:],
                   'truncate': raw[:-1], 'extend': raw + b'x'}[mutation]
        path.write_bytes(damaged)
    code = 'UNAVAILABLE' if mutation == 'missing' else 'INVALID'
    with pytest.raises(AssetIntegrityError, match='^ASSET_BOUNDED_CONTENT_' + code + '$'):
        rig.assets.content(row['id'], max_bytes=len(raw))
    assert rig.assets._load(row['id']) == before
    if mutation != 'digest':
        assert native['reads'] == []


def test_owner_capability_missing_never_opens_or_falls_back(file_image, monkeypatch):
    rig, row, raw, _ = file_image
    monkeypatch.setattr(native_reader, 'windows_bounded_read_supported', lambda: False)
    def forbidden(*_args, **_kwargs):
        pytest.fail('unavailable bounded reader touched the binary path or default reader')
    with monkeypatch.context() as patch:
        patch.setattr(rig.assets, '_bin_path', forbidden)
        with pytest.raises(ValueError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$') as error:
            rig.assets.content(row['id'], max_bytes=len(raw))
        assert type(error.value) is ValueError
    assert rig.assets.content(row['id']) == raw


def test_owner_native_failure_projects_fixed_integrity_error(file_image, native, monkeypatch):
    rig, row, raw, _ = file_image
    def failed(*_args):
        ctypes.set_last_error(5)
        return 0
    monkeypatch.setattr(native['api'].dll, 'ReadFile', failed)
    with pytest.raises(AssetIntegrityError, match='^ASSET_BOUNDED_CONTENT_UNAVAILABLE$'):
        rig.assets.content(row['id'], max_bytes=len(raw))


def test_owner_guard_denied_before_binary_path(file_image, native, monkeypatch):
    rig, row, raw, _ = file_image
    def forbidden(*_args):
        pytest.fail('revoked reader touched the binary path')
    def guard():
        raise PermissionError('synthetic owner authority revoked')
    monkeypatch.setattr(rig.assets, '_bin_path', forbidden)
    with pytest.raises(PermissionError, match='^synthetic owner authority revoked$'):
        rig.assets.content(row['id'], max_bytes=len(raw), guard=guard)
    assert native['opens'] == native['reads'] == []


def test_owner_same_bytes_identity_retarget_is_invalid(file_image, native, monkeypatch):
    rig, row, raw, _ = file_image
    before = copy.deepcopy(rig.assets._load(row['id']))
    path = rig.assets._bin_path(row['id'])
    other = path.with_name('synthetic-replacement.bin'); other.write_bytes(raw)
    previous = path.stat(); os.utime(other, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    opening = native['api'].open
    swapped = False
    def swap(filename, access, guard):
        nonlocal swapped
        if access == 0x80000000 and not swapped:
            swapped = True
            os.replace(other, path)
        return opening(filename, access, guard)
    monkeypatch.setattr(native['api'], 'open', swap)
    with pytest.raises(AssetIntegrityError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
        rig.assets.content(row['id'], max_bytes=len(raw))
    assert swapped and native['reads'] == [] and path.read_bytes() == raw
    assert rig.assets._load(row['id']) == before


def test_owner_final_real_close_revocation_returns_no_bytes(file_image, native, monkeypatch):
    rig, row, raw, _ = file_image
    before = copy.deepcopy(rig.assets._load(row['id']))
    closing = native['api'].close
    revoked = False
    def close(handle):
        nonlocal revoked
        result = closing(handle)
        main = next((item['handle'] for item in native['opens'] if item['access'] == 0x80000000), None)
        if result and handle == main:
            assert not native['active']
            revoked = True
        return result
    def guard():
        if revoked:
            raise PermissionError('owner revoked after real final close')
    monkeypatch.setattr(native['api'], 'close', close)
    with pytest.raises(PermissionError, match='^owner revoked after real final close$'):
        rig.assets.content(row['id'], max_bytes=len(raw), guard=guard)
    assert revoked and not native['active']
    assert rig.assets._load(row['id']) == before


@pytest.mark.parametrize('failure', ['none', 'corrupt', 'identity', 'revoked'])
def test_original_private_ora_staging_bounded_read(rig, staging, native, monkeypatch, failure):
    row = prepare(rig, staging)
    result = stage(rig, staging, row)
    assert result['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
    aid = result['steps'][0]['asset_id']
    path = rig.assets._bin_path(aid)
    before = copy.deepcopy(rig.assets._load(aid))
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as decoded:
        decoded.load(); assert decoded.format == 'PNG'
    native['opens'].clear(); native['reads'].clear()
    guard = lambda: None
    if failure == 'corrupt':
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    elif failure == 'identity':
        other = path.with_name('synthetic-ora-replacement.bin'); other.write_bytes(raw)
        opening = native['api'].open
        def swap(filename, access, authority):
            if access == 0x80000000 and other.exists():
                os.replace(other, path)
            return opening(filename, access, authority)
        monkeypatch.setattr(native['api'], 'open', swap)
    elif failure == 'revoked':
        def guard():
            if native['reads']:
                raise PermissionError('private ORA authority revoked')
    with rig.service._asset_scope(rig.nid, rig.scope):
        def read():
            return rig.assets.content(aid, actor_id=rig.actor, max_bytes=len(raw), guard=guard)
        if failure == 'none':
            assert read() == raw
        elif failure == 'revoked':
            with pytest.raises(PermissionError, match='^private ORA authority revoked$'):
                read()
        else:
            with pytest.raises(AssetIntegrityError, match='^ASSET_BOUNDED_CONTENT_INVALID$'):
                read()
        for actor in (None, 'other'):
            with pytest.raises(FileNotFoundError):
                rig.assets.content(aid, actor_id=actor, max_bytes=len(raw))
    with pytest.raises(FileNotFoundError):
        rig.assets.content(aid, actor_id=rig.actor, max_bytes=len(raw))
    assert rig.assets._load(aid) == before
    assert not native['active']
