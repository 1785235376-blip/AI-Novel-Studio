"""Name-only explanation, not an index scan, quota calculation, or admission."""
import hashlib
import os
from pathlib import Path

import pytest

from app.services.asset_library_service import AssetLibraryService
from app.services.asset_query_index import FileAssetQueryIndex


@pytest.mark.parametrize('name,category', [
    ('index.sqlite3', 'PRIMARY_INDEX_NAME_UNVERIFIED'),
    ('cursor.key', 'CURSOR_METADATA_NAME_UNVERIFIED'),
    ('cursor.identity', 'CURSOR_METADATA_NAME_UNVERIFIED'),
    ('index.sqlite3-journal', 'STAGING_OR_JOURNAL_NAME_UNVERIFIED'),
    ('index.sqlite3-wal', 'STAGING_OR_JOURNAL_NAME_UNVERIFIED'),
    ('index.sqlite3-shm', 'STAGING_OR_JOURNAL_NAME_UNVERIFIED'),
    ('building-' + 'a' * 32 + '.sqlite3', 'STAGING_OR_JOURNAL_NAME_UNVERIFIED'),
    ('building-' + 'a' * 32 + '.sqlite3-journal', 'STAGING_OR_JOURNAL_NAME_UNVERIFIED'),
    ('foreign-private.txt', 'UNKNOWN_ENTRY'),
    ('../cursor.key', 'UNKNOWN_ENTRY'),
    ('C:\\cursor.key', 'UNKNOWN_ENTRY'),
    ('building-' + 'g' * 32 + '.sqlite3', 'UNKNOWN_ENTRY'),
    ('', 'UNKNOWN_ENTRY'),
    (None, 'UNKNOWN_ENTRY'),
    ('x' * 129, 'UNKNOWN_ENTRY'),
])
def test_classification_is_not_attribution_or_admission(name, category):
    result = AssetLibraryService._classify_shared_index_capacity_name(name)
    assert result == {
        'classification': category, 'ownership': 'UNKNOWN',
        'project_charge_known': False, 'capacity_exempt': False,
        'write_admission_proven': False,
    }
    assert not name or name not in repr(result)


def test_name_classification_does_not_observe_or_initialize_any_file(tmp_path, monkeypatch):
    # The same supplied name gets the same answer regardless of whether the
    # shared directory exists. The classifier must not reveal its existence.
    owner = AssetLibraryService(tmp_path)
    directory = owner.root / '.asset-query-index'
    before = sorted(p.name for p in owner.root.iterdir())
    expected = owner._classify_shared_index_capacity_name('index.sqlite3')
    assert not directory.exists()
    assert sorted(p.name for p in owner.root.iterdir()) == before

    # Synthetic files contain no user/project data and no cursor key material.
    directory.mkdir()
    primary, unknown = directory / 'index.sqlite3', directory / 'not-owned.bin'
    primary.write_bytes(b'synthetic index bytes')
    unknown.write_bytes(b'synthetic orphan bytes')
    inventory = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
    with monkeypatch.context() as patch:
        def forbidden(*args, **kwargs):
            raise AssertionError('name-only diagnostic must not touch filesystem')
        patch.setattr(Path, 'lstat', forbidden)
        patch.setattr(Path, 'open', forbidden)
        patch.setattr(os, 'scandir', forbidden)
        assert owner._classify_shared_index_capacity_name('index.sqlite3') == expected
        assert owner._classify_shared_index_capacity_name('not-owned.bin')['classification'] == 'UNKNOWN_ENTRY'
        # A synthetic cursor basename is classified as a name only. No cursor
        # path is opened or created, and key bytes are never supplied.
        assert FileAssetQueryIndex._classify_unverified_capacity_name('cursor.key')['ownership'] == 'UNKNOWN'
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()} == inventory
    assert not (directory / 'cursor.key').exists()
    assert not (owner.root / '.workspace-mutation-locks').exists()


def test_known_name_is_not_proof_the_input_exists(tmp_path):
    owner = AssetLibraryService(tmp_path)
    assert owner._classify_shared_index_capacity_name('index.sqlite3')['ownership'] == 'UNKNOWN'
    assert not (owner.root / '.asset-query-index').exists()
