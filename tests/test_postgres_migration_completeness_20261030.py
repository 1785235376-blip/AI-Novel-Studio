"""Require actual packaged migration assets, not just injected fake SQL tests."""
from pathlib import Path
import hashlib
import pytest
from app.packaging.postgres_migrations import (
    load_packaged_migrations, load_identity_migrations, PackagedPostgresMigrationRunner,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    '018_context_privacy.sql': 'e2e6c2c45a07b9593c5e4ff9400d3eb0e4bad6096ea0aaadb1bba691df3bb5b1',
    '019_experimental_scope_documents.sql': 'eb3516c8f802e51efa523950807795ea9400bf91f62e9191d1c726a5cb10ffaf',
    '020_stable_chapter_identity.sql': '92774a1b26f4e79056e7f0d5d3fedf76b77887a109de7a1251bd6b16081722f7',
}


@pytest.mark.parametrize('name,sha256', EXPECTED.items())
def test_recovered_migration_matches_recorded_original_blob(name, sha256):
    assert hashlib.sha256((ROOT / 'database/migrations' / name).read_bytes()).hexdigest() == sha256


@pytest.mark.parametrize('experimental', [False, True])
def test_packaged_loader_and_identity_assets_are_complete(experimental):
    migrations = ROOT / 'database/migrations'
    selected = load_packaged_migrations(migrations, include_experimental=experimental)
    assert [x.migration_id for x in selected] == ['0001_chapter_archive_state', '0002_context_privacy'] + (
        ['0003_experimental_scope_documents'] if experimental else [])
    identity = load_identity_migrations(migrations)
    assert [x.migration_id for x in identity] == ['0004_stable_chapter_identity']
    runner = PackagedPostgresMigrationRunner(migrations_path=migrations,
        execute_sql=lambda _: None, include_experimental=experimental)
    assert runner.migrations == selected and runner.identity_migrations == identity
    for migration in selected + identity:
        assert migration.checksum == hashlib.sha256(migration.sql.encode()).hexdigest()
