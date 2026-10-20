"""Hardened ZIP/file-set boundaries for the B07 export target contract.

Every case is a small constructed archive: boundary values, case-insensitive
collisions, file/directory prefix conflicts, duplicate entries, lying size
headers, encryption flags, traversal and the normal export round-trip. No large
disk/memory stress packages are used.
"""
import io
import json
import struct
import types
import zipfile

import pytest

import app.experimental.interactive_export_contract as contract
from app.experimental.interactive_export_contract import (
    MAX_FILE_BYTES, MAX_TOTAL_BYTES, check_path_set, normalize_files, package_export_zip,
    read_zip_safely,
)

PREFIX = 'interactive-boundary-test/'
FAKE_TARGET = 'BOUNDARY_TEST_TARGET_V1'
CAPS = {key: {'supported': True, 'lossy': False, 'note': ''} for key in contract.CAPABILITY_KEYS}
SPEC = {'title': 'Boundary story', 'graph_id': 'graph', 'graph_version': 1, 'entry_node_id': 'n1', 'max_steps': 3,
        'graph_record_ids': [], 'variables': [{'name': 'flag', 'type': 'bool', 'initial': False, 'minimum': 0, 'maximum': 100}],
        'nodes': [
            {'node_id': 'n1', 'node_version': 1, 'title': 'Start', 'dialogue': 'Start', 'character_id': None,
             'background_asset_id': None, 'music_asset_id': None, 'ending': '',
             'choices': [{'id': 'go', 'label': 'Go', 'target': 'n2', 'condition': '', 'assignments': {'flag': True}}]},
            {'node_id': 'n2', 'node_version': 1, 'title': 'End', 'dialogue': 'End', 'character_id': None,
             'background_asset_id': None, 'music_asset_id': None, 'ending': 'Done', 'choices': []}]}


def _snapshot():
    return {'story_id': 'boundary-story', 'revision': 2, 'status': 'APPROVED', 'title': SPEC['title'], 'spec': SPEC,
            'spec_digest': 'a' * 64, 'source_digest': 'b' * 64, 'review_receipt': 'c' * 64, 'characters': {},
            'media_manifest': [], 'witness': [{'node_id': 'n2', 'ending': 'Done', 'choices': ['go']}],
            'analysis': {'can_review': True, 'analysis_complete': True, 'issues': [], 'warnings': [], 'states_checked': 2,
                         'endings': [{'node_id': 'n2', 'ending': 'Done', 'choices': ['go']}]}}


def _fake_module():
    descriptor = {'target_id': FAKE_TARGET, 'display_name': 'Boundary fixture target', 'kind': 'RUNNABLE_PROJECT',
                  'format_version': 'boundary-1', 'adapter_revision': 1, 'engine': None, 'capabilities': CAPS,
                  'losses': [], 'runtime_requirements': [], 'launch_instructions': 'fixture',
                  'integration_notes': [], 'evidence': {'SOURCE_IMPLEMENTED': 'PASS'}}

    def compatibility(snapshot):
        return {'can_export': True, 'capabilities': dict(CAPS), 'losses': [], 'issues': [], 'notes': []}

    def build(snapshot, options):
        return {'files': {'project.godot': b'[application]\n', 'data/story.json':
                          json.dumps({'id': snapshot['story_id']}, sort_keys=True).encode('utf-8')}}
    return types.SimpleNamespace(DESCRIPTOR=descriptor, compatibility=compatibility, build=build)


@pytest.fixture
def fake_target(monkeypatch):
    contract.clear_target_cache()
    monkeypatch.setattr(contract, 'TARGET_MODULES', {**contract.TARGET_MODULES, FAKE_TARGET: '.boundary_fixture_adapter'})
    monkeypatch.setitem(contract._MODULE_CACHE, FAKE_TARGET, _fake_module())
    yield FAKE_TARGET
    contract.clear_target_cache()


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _patch_field(content: bytes, signature: bytes, offset: int, fmt: str, value) -> bytes:
    content = bytearray(content)
    start = 0
    found = False
    while True:
        index = bytes(content).find(signature, start)
        if index < 0: break
        struct.pack_into(fmt, content, index + offset, value)
        start = index + 4
        found = True
    assert found, 'signature not found: ' + repr(signature)
    return bytes(content)


def _patch_uncompressed_size(content: bytes, value: int) -> bytes:
    content = _patch_field(content, b'PK\x03\x04', 22, '<I', value)
    return _patch_field(content, b'PK\x01\x02', 24, '<I', value)


def _patch_flag_bits(content: bytes, value: int) -> bytes:
    content = _patch_field(content, b'PK\x03\x04', 6, '<H', value)
    return _patch_field(content, b'PK\x01\x02', 8, '<H', value)


# ---------------------------------------------------------------------------
# file-set boundaries
# ---------------------------------------------------------------------------
def test_single_file_byte_boundary_is_enforced_before_reading():
    assert MAX_FILE_BYTES == 8 * 1024 * 1024
    assert list(normalize_files({'exact.bin': b'x' * MAX_FILE_BYTES})) == ['exact.bin']
    with pytest.raises(ValueError, match='BUNDLE_FILE_TOO_LARGE'):
        normalize_files({'over.bin': b'x' * (MAX_FILE_BYTES + 1)})
    # 8388609 bytes: the exact value Hermia reproduced as accepted.
    with pytest.raises(ValueError, match='BUNDLE_FILE_TOO_LARGE'):
        normalize_files({'over.bin': b'x' * 8388609})


def test_total_byte_budget_is_enforced(monkeypatch):
    monkeypatch.setattr(contract, 'MAX_TOTAL_BYTES', 100)
    with pytest.raises(ValueError, match='BUNDLE_TOTAL_SIZE_INVALID'):
        normalize_files({'a.txt': b'x' * 60, 'b.txt': b'y' * 60})


def test_case_insensitive_collisions_are_rejected():
    with pytest.raises(ValueError, match='BUNDLE_PATH_COLLISION'):
        normalize_files({'A.txt': b'a', 'a.txt': b'b'})
    with pytest.raises(ValueError, match='BUNDLE_PATH_COLLISION'):
        normalize_files({'dir/Story.json': b'{}', 'dir/story.json': b'{}'})


def test_file_directory_prefix_conflicts_are_rejected():
    with pytest.raises(ValueError, match='BUNDLE_PATH_PREFIX_CONFLICT'):
        normalize_files({'a': b'x', 'a/b': b'y'})
    with pytest.raises(ValueError, match='BUNDLE_PATH_PREFIX_CONFLICT'):
        normalize_files({'a/b/c.txt': b'y', 'a/b': b'x'})
    with pytest.raises(ValueError, match='BUNDLE_PATH_PREFIX_CONFLICT'):
        check_path_set(['game', 'game/script.rpy'])
    check_path_set(['game/script.rpy', 'game/options.rpy', 'README.txt'])


@pytest.mark.parametrize('bad', ['../evil', '/abs', 'a\\b', 'C:/x', 'con', 'trailing.', '.hidden'])
def test_dangerous_paths_stay_rejected(bad):
    with pytest.raises(ValueError):
        normalize_files({bad: b'x'})


# ---------------------------------------------------------------------------
# ZIP directory and read budget
# ---------------------------------------------------------------------------
def test_read_zip_rejects_declared_oversized_entry():
    content = _zip({PREFIX + 'ok.txt': b'ok', PREFIX + 'big.bin': b'x' * (MAX_FILE_BYTES + 1)})
    with pytest.raises(ValueError, match='BUNDLE_ZIP_ENTRY_TOO_LARGE'):
        read_zip_safely(content, PREFIX)


def test_read_zip_checks_declared_total_budget(monkeypatch):
    monkeypatch.setattr(contract, 'MAX_TOTAL_BYTES', 64)
    monkeypatch.setattr(contract, 'MAX_FILE_BYTES', 64)
    content = _zip({PREFIX + 'a.bin': b'x' * 40, PREFIX + 'b.bin': b'y' * 40})
    with pytest.raises(ValueError, match='BUNDLE_ZIP_TOTAL_TOO_LARGE'):
        read_zip_safely(content, PREFIX)


def test_read_zip_rejects_case_collision_and_prefix_conflict():
    with pytest.raises(ValueError, match='BUNDLE_PATH_COLLISION'):
        read_zip_safely(_zip({PREFIX + 'A.txt': b'a', PREFIX + 'a.txt': b'b'}), PREFIX)
    with pytest.raises(ValueError, match='BUNDLE_PATH_PREFIX_CONFLICT'):
        read_zip_safely(_zip({PREFIX + 'a': b'x', PREFIX + 'a/b': b'y'}), PREFIX)


def test_read_zip_rejects_duplicate_entry_names():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(PREFIX + 'same.txt', b'one')
        archive.writestr(PREFIX + 'same.txt', b'two')
    with pytest.raises(ValueError, match='BUNDLE_PATH_COLLISION'):
        read_zip_safely(buffer.getvalue(), PREFIX)


@pytest.mark.parametrize('name', [PREFIX + '../escape.txt', PREFIX + '/absolute.txt', PREFIX + 'con.txt'])
def test_read_zip_rejects_unsafe_member_paths(name):
    with pytest.raises(ValueError):
        read_zip_safely(_zip({name: b'x'}), PREFIX)


def test_read_zip_normalises_backslash_separators_before_validation():
    # zipfile rewrites os.sep to "/" for archive member names on Windows, so a
    # crafted backslash-separated name arrives as a plain relative path and is
    # still validated by the shared path rules; traversal stays rejected.
    content = _zip({PREFIX + 'back/slash.txt': b'x'})
    original = (PREFIX + 'back/slash.txt').encode()
    crafted = content.replace(original, original.replace(b'back/slash.txt', b'back\\slash.txt'))
    files = read_zip_safely(crafted, PREFIX)
    assert files == {'back/slash.txt': b'x'}

def test_read_zip_rejects_entry_outside_expected_prefix():
    with pytest.raises(ValueError, match='BUNDLE_ZIP_PREFIX_INVALID'):
        read_zip_safely(_zip({'other-root/file.txt': b'x'}), PREFIX)


def test_read_zip_rejects_lying_uncompressed_size():
    content = _zip({PREFIX + 'story.bin': b'x' * (1024 * 1024)})
    lying = _patch_uncompressed_size(content, 64)
    # zipfile's own CRC check fires first for this crafted header; either way the
    # archive is rejected before unbounded payload allocation.
    with pytest.raises(ValueError, match='BUNDLE_ZIP_ENTRY_INTEGRITY_INVALID'):
        read_zip_safely(lying, PREFIX)


def test_read_zip_rejects_encrypted_entry_flag():
    content = _zip({PREFIX + 'story.bin': b'payload'})
    encrypted = _patch_flag_bits(content, 0x1)
    with pytest.raises(ValueError, match='BUNDLE_ZIP_ENCRYPTED'):
        read_zip_safely(encrypted, PREFIX)


def test_bounded_entry_reader_never_trusts_header_or_total_budget():
    with pytest.raises(ValueError, match='BUNDLE_ZIP_DECLARED_SIZE_MISMATCH'):
        contract._read_entry_bounded(io.BytesIO(b'x' * 100), 10, 0)
    with pytest.raises(ValueError, match='BUNDLE_ZIP_TOTAL_TOO_LARGE'):
        contract._read_entry_bounded(io.BytesIO(b'x' * 10), 10, MAX_TOTAL_BYTES)
    with pytest.raises(ValueError, match='BUNDLE_ZIP_ENTRY_TOO_LARGE'):
        contract._read_entry_bounded(io.BytesIO(b''), MAX_FILE_BYTES + 1, 0)


def test_read_zip_bounds_compressed_input_size(monkeypatch):
    monkeypatch.setattr(contract, 'MAX_TOTAL_BYTES', 16)
    content = b'x' * (16 + contract.ZIP_OVERHEAD_BYTES + 1)
    with pytest.raises(ValueError, match='BUNDLE_ZIP_TOO_LARGE'):
        read_zip_safely(content, PREFIX)


# ---------------------------------------------------------------------------
# normal deliverable still round-trips
# ---------------------------------------------------------------------------
def test_normal_export_bundle_still_round_trips(fake_target):
    bundle = contract.build_export_bundle(fake_target, _snapshot())
    package = package_export_zip(bundle)
    files = read_zip_safely(package['content'], package['prefix'])
    assert files == bundle.files
    assert 'manifest.json' in files and 'source-receipt.json' in files
    assert json.loads(files['manifest.json'])['target_id'] == FAKE_TARGET
