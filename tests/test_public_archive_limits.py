"""Inert archive fixtures; bounded inspection never extracts or imports payloads."""
from __future__ import annotations

import gzip
import io
import tarfile
import zipfile

import pytest

from test_public_wheel_artifact import build

pytestmark = pytest.mark.file_backend_only


def tar_bytes(entries=(), *, end=True):
    chunks = []
    for name, data, kind in entries:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.size = len(data)
        if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            member.linkname = 'inert-target'
        chunks.extend((member.tobuf(format=tarfile.USTAR_FORMAT), data, bytes((-len(data)) % 512)))
    if end:
        chunks.append(bytes(1024))
    return b''.join(chunks)


def zip_bytes(name, data):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return output.getvalue()


def pax_record(key, value):
    record = f' {key}={value}\n'.encode()
    size = len(record) + 1
    while size != len(record) + len(str(size)):
        size = len(record) + len(str(size))
    return str(size).encode() + record


def inspect(data, name='fixture.tar', **kwargs):
    return build.check_tar(data, name, **kwargs)


@pytest.mark.parametrize('suffix', ['.tar', '.tar.gz', '.tgz'])
def test_supported_tar_suffixes_use_bounded_scanner_without_extraction(tmp_path, monkeypatch, suffix):
    def forbidden(*args, **kwargs):
        raise AssertionError('Filesystem extraction is forbidden')
    monkeypatch.setattr(tarfile.TarFile, 'extract', forbidden)
    monkeypatch.setattr(tarfile.TarFile, 'extractall', forbidden)
    raw = tar_bytes([('public', b'', tarfile.DIRTYPE), ('public/inert.txt', b'neutral', tarfile.REGTYPE)])
    data = raw if suffix == '.tar' else gzip.compress(raw)
    (tmp_path / ('inert' + suffix)).write_bytes(data)
    build.check_artifact_namespace(tmp_path)
    assert inspect(data, 'inert' + suffix)[0] == {'public/inert.txt': b'neutral'}


@pytest.mark.parametrize('name', ['../inert', '/inert', 'a/../../inert', 'a\\inert', 'a//inert', './inert', 'C:/inert', 'a/./inert'])
def test_unsafe_paths_fail(name):
    with pytest.raises(ValueError, match='PUBLIC_TAR_UNSAFE_PATH'):
        inspect(tar_bytes([(name, b'', tarfile.REGTYPE)]))


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE,
                                  tarfile.GNUTYPE_SPARSE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK,
                                  tarfile.XGLTYPE, b'Z'])
def test_links_devices_and_unsupported_physical_headers_fail(kind):
    with pytest.raises(ValueError, match='PUBLIC_TAR_UNSUPPORTED_MEMBER'):
        inspect(tar_bytes([('inert', b'', kind)]))


def test_duplicate_files_and_file_directory_collisions_fail():
    for kind in (tarfile.REGTYPE, tarfile.DIRTYPE):
        with pytest.raises(ValueError, match='PUBLIC_TAR_DUPLICATE_PATH'):
            inspect(tar_bytes([('same', b'', tarfile.REGTYPE), ('same', b'', kind)]))


@pytest.mark.parametrize('key,value', [('GNU.sparse.map', '0,1'), ('size', '999999999'), ('linkpath', 'elsewhere'),
                                      ('comment', 'inert'), ('mtime', 'nan'), ('path', '../inert')])
def test_pax_overrides_are_strictly_bounded_and_allowlisted(key, value):
    with pytest.raises(ValueError, match='PUBLIC_TAR_(UNSUPPORTED_PAX|INVALID_PAX|UNSAFE_PATH)'):
        inspect(tar_bytes([('././@PaxHeader', pax_record(key, value), tarfile.XHDTYPE), ('file', b'', tarfile.REGTYPE)]))


def test_local_pax_path_and_mtime_are_supported_without_a_tarfile_iterator():
    raw = tar_bytes([('././@PaxHeader', pax_record('path', 'public/inert.txt') + pax_record('mtime', '123.25'), tarfile.XHDTYPE),
                     ('public/short', b'neutral', tarfile.REGTYPE)])
    assert inspect(raw)[0] == {'public/inert.txt': b'neutral'}


@pytest.mark.parametrize('mode', ['duplicate', 'consecutive', 'dangling', 'bad_length', 'too_large', 'key_budget'])
def test_pax_physical_abuse_fails(monkeypatch, mode):
    data = pax_record('mtime', '1')
    if mode == 'duplicate':
        data += data
    elif mode == 'bad_length':
        data = b'999999999999999999999 mtime=1\n'
    elif mode == 'too_large':
        monkeypatch.setattr(build, 'PAX_BYTES', len(data) - 1)
    elif mode == 'key_budget':
        monkeypatch.setattr(build, 'PAX_KEYS', 0)
    entries = [('././@PaxHeader', data, tarfile.XHDTYPE)]
    if mode == 'consecutive':
        entries += entries
    if mode != 'dangling':
        entries.append(('file', b'', tarfile.REGTYPE))
    with pytest.raises(ValueError, match='PUBLIC_TAR_'):
        inspect(tar_bytes(entries))


def test_pax_headers_count_towards_member_budget():
    raw = tar_bytes([('././@PaxHeader', pax_record('mtime', '1'), tarfile.XHDTYPE), ('file', b'', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match='PUBLIC_ARCHIVE_INSPECTION_LIMIT'):
        inspect(raw, budget=[1, len(raw)])


def test_member_size_and_decompressed_stream_are_bounded_before_parse(monkeypatch):
    raw = tar_bytes([('file', b'1234', tarfile.REGTYPE)])
    monkeypatch.setattr(build, 'TAR_MEMBER_BYTES', 3)
    with pytest.raises(ValueError, match='PUBLIC_TAR_MEMBER_LIMIT'):
        inspect(raw)
    def no_parse(*args, **kwargs):
        raise AssertionError('Raw budget must fail before header parsing')
    monkeypatch.setattr(tarfile.TarInfo, 'frombuf', no_parse)
    with pytest.raises(ValueError, match='PUBLIC_ARCHIVE_INSPECTION_LIMIT'):
        inspect(gzip.compress(raw), 'fixture.tar.gz', budget=[100, len(raw) - 1])
    with pytest.raises(ValueError, match='PUBLIC_ARCHIVE_INSPECTION_LIMIT'):
        inspect(raw, budget=[100, len(raw) - 1])


@pytest.mark.parametrize('change', ['second_gzip', 'gzip_garbage', 'truncated_gzip', 'invalid_gzip', 'second_tar', 'tar_garbage', 'missing_end', 'one_end_block', 'padding', 'checksum', 'directory_data'])
def test_trailing_data_truncation_and_bad_headers_fail(change):
    raw = tar_bytes([('file', b'x', tarfile.REGTYPE)])
    name = 'fixture.tar'
    if change in ('second_gzip', 'gzip_garbage', 'truncated_gzip', 'invalid_gzip'):
        name = 'fixture.tar.gz'
        data = gzip.compress(raw)
        if change == 'second_gzip': data += gzip.compress(raw)
        if change == 'gzip_garbage': data += b'inert'
        if change == 'truncated_gzip': data = data[:-1]
        if change == 'invalid_gzip': data = b'inert'
    else:
        data = raw
        if change == 'second_tar': data += raw
        if change == 'tar_garbage': data += b'inert'
        if change == 'missing_end': data = raw[:-1024]
        if change == 'one_end_block': data = raw[:-512]
        if change == 'padding': data = raw[:513] + b'!' + raw[514:]
        if change == 'checksum': data = b'!' + raw[1:]
        if change == 'directory_data': data = tar_bytes([('dir', b'!', tarfile.DIRTYPE)])
    with pytest.raises(ValueError, match='PUBLIC_TAR_'):
        inspect(data, name)


@pytest.mark.parametrize('outer', ['zip', 'tar'])
def test_mixed_archives_share_namespace_checks(tmp_path, outer):
    private = 'STUDIO_PRIVATE_EXTENSIONS/inert.txt'
    if outer == 'zip':
        data = zip_bytes('nested.tgz', gzip.compress(tar_bytes([(private, b'neutral', tarfile.REGTYPE)])))
    else:
        data = tar_bytes([('nested.zip', zip_bytes(private, b'neutral'), tarfile.REGTYPE)])
    (tmp_path / ('fixture.' + outer)).write_bytes(data)
    with pytest.raises(ValueError, match='PUBLIC_PRIVATE_ARCHIVE'):
        build.check_artifact_namespace(tmp_path)


def test_mixed_recursion_shares_entry_and_byte_budgets():
    nested = tar_bytes([('inner.zip', zip_bytes('inert.txt', b'neutral'), tarfile.REGTYPE)])
    outer = zip_bytes('inner.tar', nested)
    for budget in ([2, 1000000], [100, 2 * len(nested) - 1]):
        with zipfile.ZipFile(io.BytesIO(outer)) as archive:
            with pytest.raises(ValueError, match='PUBLIC_ARCHIVE_INSPECTION_LIMIT'):
                build.check_archive(archive, budget=budget)


def test_mixed_recursion_depth_fails_closed():
    data = b'neutral'
    name = 'inert.txt'
    for level in range(5):
        data = tar_bytes([(name, data, tarfile.REGTYPE)]) if level % 2 == 0 else zip_bytes(name, data)
        name = 'nested.tar' if level % 2 == 0 else 'nested.zip'
    with pytest.raises(ValueError, match='PUBLIC_ARCHIVE_INSPECTION_LIMIT'):
        inspect(data, name)


def test_compressed_input_read_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'ARCHIVE_BYTES', 8)
    (tmp_path / 'oversized.tar.gz').write_bytes(b'x' * 9)
    with pytest.raises(ValueError, match='PUBLIC_ARCHIVE_INSPECTION_LIMIT'):
        build.check_artifact_namespace(tmp_path)


@pytest.mark.parametrize('reverse', [False, True])
def test_file_parent_collisions_fail(reverse):
    entries = [('parent', b'', tarfile.REGTYPE), ('parent/child', b'', tarfile.REGTYPE)]
    with pytest.raises(ValueError, match='PUBLIC_TAR_PATH_COLLISION'):
        inspect(tar_bytes(list(reversed(entries)) if reverse else entries))


def test_truncated_member_and_unaligned_padding_fail():
    raw = tar_bytes([('file', b'x', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match='PUBLIC_TAR_TRUNCATED_MEMBER'):
        inspect(raw[:512])
    with pytest.raises(ValueError, match='PUBLIC_TAR_UNALIGNED_STREAM'):
        inspect(raw + b'\x00')


@pytest.mark.parametrize('private_in', ['header', 'pax'])
def test_private_namespace_cannot_hide_in_overridden_pax_path(private_in):
    private = 'studio_private_extensions/inert'
    raw = tar_bytes([('././@PaxHeader', pax_record('path', private if private_in == 'pax' else 'safe'), tarfile.XHDTYPE),
                     (private if private_in == 'header' else 'safe', b'', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match='PUBLIC_PRIVATE_ARCHIVE'):
        inspect(raw)


def test_pax_effective_path_duplicate_fails():
    raw = tar_bytes([('same', b'', tarfile.REGTYPE),
                     ('././@PaxHeader', pax_record('path', 'same'), tarfile.XHDTYPE),
                     ('different-header-name', b'', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match='PUBLIC_TAR_DUPLICATE_PATH'):
        inspect(raw)


@pytest.mark.parametrize('size', [-1, build.TAR_MEMBER_BYTES + 1, 2 ** 40])
def test_negative_or_oversized_base256_header_fails_before_payload(size):
    member = tarfile.TarInfo('inert')
    member.size = size
    raw = member.tobuf(format=tarfile.GNU_FORMAT) + bytes(1024)
    with pytest.raises(ValueError, match='PUBLIC_TAR_MEMBER_LIMIT'):
        inspect(raw)
