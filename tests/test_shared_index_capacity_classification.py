"""Name-only explanation, not an index scan, quota calculation, or admission."""
import hashlib
import os
from pathlib import Path

import pytest

from app.creative.audio_index_capacity_diagnostic import (
    AudioIndexCapacityDiagnosticUnavailable,
    inspect_local_shared_index_capacity,
)
from app.repositories.file.mutation_coordinator import ReadOnlyCoordinationUnavailable
from app.services.asset_library_service import AssetLibraryService
from app.services.asset_query_index import AssetQueryBudgetExceeded, FileAssetQueryIndex
from test_studio_asset_query import rig


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


def _snapshot(root):
    return {str(path.relative_to(root)): ('dir' if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest())
            for path in root.rglob('*')}


def test_local_existing_original_lease_observes_unknown_classes_without_writes(rig, monkeypatch):
    rig.seed('fixture.wav', 'audio')
    directory = rig.assets.root / '.asset-query-index'
    directory.mkdir()
    (directory / 'index.sqlite3').write_bytes(b'synthetic index contents')
    (directory / 'unexpected-private-object').write_bytes(b'synthetic unattributed contents')
    before = _snapshot(rig.root)
    original_open = Path.open
    def guard_index_contents(path, *args, **kwargs):
        if path.parent == directory:
            raise AssertionError('shared index contents must not be opened')
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guard_index_contents)
        result = inspect_local_shared_index_capacity(rig.workspace, rig.nid)
    assert result == {
        'observation': 'DIRECTORY_OBSERVED',
        'classes': ['PRIMARY_INDEX_NAME_UNVERIFIED', 'UNKNOWN_ENTRY'],
        'complete_inventory': False,
        'ownership': 'UNKNOWN', 'project_charge_known': False,
        'capacity_exempt': False, 'write_admission_proven': False,
        'scope': 'SHARED_INDEX_ONLY',
    }
    assert 'unexpected-private-object' not in repr(result)
    assert 'index.sqlite3' not in repr(result)
    assert _snapshot(rig.root) == before
    assert not (directory / 'cursor.key').exists()


def test_missing_project_cannot_observe_shared_index(rig, monkeypatch):
    rig.seed('fixture.wav', 'audio')
    before = _snapshot(rig.root)
    def forbidden(*args, **kwargs):
        raise AssertionError('unavailable project must not inspect shared index')
    with monkeypatch.context() as patch:
        patch.setattr(os, 'scandir', forbidden)
        # Existing-only authority may reject before project lookup if the
        # missing project's coordination state was never initialized.
        with pytest.raises(ReadOnlyCoordinationUnavailable):
            inspect_local_shared_index_capacity(rig.workspace, 'synthetic-nonexistent-project')
    assert _snapshot(rig.root) == before


def test_unobserved_directory_does_not_claim_quota_or_initialize(rig):
    rig.seed('fixture.wav', 'audio')
    before = _snapshot(rig.root)
    result = inspect_local_shared_index_capacity(rig.workspace, rig.nid)
    assert result['observation'] == 'DIRECTORY_NOT_OBSERVED'
    assert result['classes'] == [] and result['ownership'] == 'UNKNOWN'
    assert result['complete_inventory'] is False
    assert result['project_charge_known'] is False and result['write_admission_proven'] is False
    assert _snapshot(rig.root) == before
    assert not (rig.assets.root / '.asset-query-index').exists()


def test_missing_existing_asset_lock_fails_without_provisioning(rig):
    rig.workspace.store.incarnation(rig.nid)
    before = _snapshot(rig.root)
    with pytest.raises((ValueError, RuntimeError)):
        inspect_local_shared_index_capacity(rig.workspace, rig.nid)
    assert _snapshot(rig.root) == before
    assert not (rig.assets.root / '.workspace-mutation-locks').exists()


def test_unsupported_shared_or_postgres_does_not_scan(rig, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('unsupported authority must not inspect shared index')
    monkeypatch.setattr(os, 'scandir', forbidden)
    monkeypatch.setattr(rig.workspace.store.store, 'backend', 'postgres')
    with pytest.raises(AudioIndexCapacityDiagnosticUnavailable):
        inspect_local_shared_index_capacity(rig.workspace, rig.nid)
    monkeypatch.setattr(rig.workspace.store.store, 'backend', 'file')
    object.__setattr__(rig.settings, 'enable_collaboration_runtime', True)
    with pytest.raises(AudioIndexCapacityDiagnosticUnavailable):
        inspect_local_shared_index_capacity(rig.workspace, rig.nid)


def test_unexpected_large_index_directory_refuses_without_inventory(rig):
    rig.seed('fixture.wav', 'audio')
    directory = rig.assets.root / '.asset-query-index'
    directory.mkdir()
    for i in range(FileAssetQueryIndex.MAX_INDEX_DIRECTORY_ENTRIES + 1):
        (directory / f'synthetic-{i:03d}').write_bytes(b'x')
    before = _snapshot(rig.root)
    with pytest.raises(AssetQueryBudgetExceeded) as exc:
        inspect_local_shared_index_capacity(rig.workspace, rig.nid)
    assert 'synthetic-' not in str(exc.value)
    assert _snapshot(rig.root) == before
