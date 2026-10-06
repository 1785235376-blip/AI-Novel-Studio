"""A43 additive identity migration, only disposable synthetic schemas."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import uuid

import pytest

from app.packaging.postgres_migrations import (
    PackagedMigration, PackagedMigrationError, PackagedPostgresMigrationRunner,
    load_identity_migrations, load_packaged_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database/migrations"


@pytest.mark.parametrize("mode", ["off", "on", "v1"])
def test_identity_upgrade_is_mandatory_for_actual_default_runner(monkeypatch, mode):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "advanced_planning_v2" if mode != "off" else "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if mode == "v1" else "false")
    calls = []
    runner = PackagedPostgresMigrationRunner(migrations_path=MIGRATIONS, execute_sql=calls.append)
    # Historical registry is kept compatible; actual run includes shared fixes.
    assert runner.migrations == load_packaged_migrations(MIGRATIONS, include_experimental=mode == "on")
    runner.run()
    upgrade = next(sql for sql in calls if "CREATE TABLE IF NOT EXISTS chapter_identities" in sql)
    assert "0004_stable_chapter_identity" in upgrade
    assert "0004_stable_chapter_identity" in calls[-1]
    assert "chapter identity schema is not ready" in calls[-1]
    assert "chapter_identity_provenance" in calls[-1]
    assert calls.index(upgrade) == len(calls) - 2


def test_identity_failure_never_reaches_ready(monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    calls = []
    def execute(sql):
        calls.append(sql)
        if "CREATE TABLE IF NOT EXISTS chapter_identities" in sql:
            raise RuntimeError("injected migration failure")
    runner = PackagedPostgresMigrationRunner(migrations_path=MIGRATIONS, execute_sql=execute)
    with pytest.raises(PackagedMigrationError):
        runner.run()
    assert not any("chapter identity schema is not ready" in sql for sql in calls)


def test_missing_identity_migration_blocks_default_runner(tmp_path):
    for filename in ("017_chapter_archive_state.sql", "018_context_privacy.sql", "019_experimental_scope_documents.sql"):
        (tmp_path / filename).write_bytes((MIGRATIONS / filename).read_bytes())
    with pytest.raises(FileNotFoundError):
        PackagedPostgresMigrationRunner(migrations_path=tmp_path, execute_sql=lambda sql: None)


def test_identity_migration_bytes_are_checksummed():
    migration, = load_identity_migrations(MIGRATIONS)
    assert migration.checksum == hashlib.sha256((MIGRATIONS / "020_stable_chapter_identity.sql").read_text().strip().encode()).hexdigest()
    assert "DELETE FROM" not in migration.sql.upper()
    assert "DROP TABLE" not in migration.sql.upper()


@pytest.mark.parametrize("sql", ["BEGIN; SELECT 1; COMMIT;", "SELECT 1; ROLLBACK;", "START TRANSACTION; SELECT 1;", "COMMIT"])
def test_top_level_transaction_controls_still_rejected(tmp_path, sql):
    path = tmp_path / "unsafe.sql"; path.write_text(sql)
    with pytest.raises(PackagedMigrationError):
        PackagedMigration.from_file("bad", "bad", path)


def test_transaction_neutral_block_and_literal_are_accepted(tmp_path):
    path = tmp_path / "safe.sql"
    path.write_text("DO $safe$ BEGIN PERFORM 'COMMIT'; END $safe$; -- BEGIN is a comment\nSELECT 'ROLLBACK';")
    assert PackagedMigration.from_file("safe", "safe", path).checksum


@pytest.mark.postgres_backend_only
def test_real_postgres_legacy_migration_preserves_bytes_and_reserves_aliases():
    url = os.environ.get("TEST_POSTGRES_DATABASE_URL")
    if not url:
        pytest.skip("NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is not configured")
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
    connection = psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))
    schema = "a43_migration_" + uuid.uuid4().hex
    try:
        # One transaction rolls back the entire isolated synthetic schema.
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema)))
        connection.execute("""
          CREATE TABLE novels(id UUID PRIMARY KEY, slug TEXT UNIQUE NOT NULL, metadata JSONB NOT NULL DEFAULT '{}');
          CREATE TABLE chapters(id UUID PRIMARY KEY, novel_id UUID NOT NULL REFERENCES novels(id), chapter_number INTEGER NOT NULL,
            markdown_path TEXT NOT NULL, document JSONB, version INTEGER NOT NULL, title TEXT,
            UNIQUE(novel_id,chapter_number));
          CREATE TABLE chapter_versions(id UUID PRIMARY KEY, chapter_id UUID NOT NULL REFERENCES chapters(id), version INTEGER NOT NULL, document JSONB NOT NULL);
          CREATE TABLE generation_jobs(id UUID PRIMARY KEY, novel_id UUID, chapter_id UUID, request JSONB, result JSONB);
          CREATE TABLE chapter_context_snapshots(id UUID PRIMARY KEY, snapshot JSONB);
          CREATE TABLE experimental_scope_documents(scope_key TEXT PRIMARY KEY, document JSONB);
        """)
        nid, aid, bid, cid, empty_id = (uuid.uuid4() for _ in range(5))
        connection.execute("INSERT INTO novels(id,slug,metadata) VALUES (%s,'legacy',%s),(%s,'empty','{}')",
                           (nid, Jsonb({"source_id": "legacy:31:v7"}), empty_id))
        docs = [{"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": marker}]}]} for marker in ("A", "B", "C")]
        for chapter_id, number, original, doc in ((aid, 2, 1, docs[0]), (bid, 1, 2, docs[1]), (cid, 3, 3, docs[2])):
            connection.execute("INSERT INTO chapters VALUES (%s,%s,%s,%s,%s,2,%s)",
                               (chapter_id, nid, number, f"chapters/chapter-{original:04d}.md", Jsonb(doc), str(chapter_id)))
            connection.execute("INSERT INTO chapter_versions VALUES (%s,%s,1,%s)", (uuid.uuid4(), chapter_id, Jsonb(doc)))
        connection.execute("INSERT INTO generation_jobs VALUES (%s,%s,NULL,%s,NULL)",
                           (uuid.uuid4(), nid, Jsonb({"_repository_payload": {"chapter_id": "legacy:99"}})))
        connection.execute("INSERT INTO generation_jobs VALUES (%s,%s,%s,%s,NULL)",
                           (uuid.uuid4(), nid, aid, Jsonb({"_repository_payload": {"chapter_id": "legacy:1"}})))
        connection.execute("INSERT INTO chapter_context_snapshots VALUES (%s,%s)", (uuid.uuid4(), Jsonb({"chapter_version_id": "legacy:37:v2"})))
        connection.execute("INSERT INTO experimental_scope_documents VALUES ('synthetic',%s)", (Jsonb({"novel_id": "legacy", "source_id": "legacy:44"}),))
        before_chapters = connection.execute("SELECT id,novel_id,chapter_number,markdown_path,document,version,title FROM chapters ORDER BY id").fetchall()
        before_history = connection.execute("SELECT * FROM chapter_versions ORDER BY id").fetchall()
        before_jobs = connection.execute("SELECT * FROM generation_jobs ORDER BY id").fetchall()
        migration, = load_identity_migrations(MIGRATIONS)
        connection.execute(migration.sql)
        assert connection.execute("SELECT id,novel_id,chapter_number,markdown_path,document,version,title FROM chapters ORDER BY id").fetchall() == before_chapters
        assert connection.execute("SELECT * FROM chapter_versions ORDER BY id").fetchall() == before_history
        assert connection.execute("SELECT * FROM generation_jobs ORDER BY id").fetchall() == before_jobs
        assert dict(connection.execute("SELECT chapter_number,identity_status FROM chapters").fetchall()) == {1: "AMBIGUOUS", 2: "AMBIGUOUS", 3: "ACTIVE"}
        reservations = dict(connection.execute("SELECT chapter_number,state FROM chapter_identities").fetchall())
        assert set(reservations) >= {1, 2, 3, 31, 37, 44, 99}
        assert reservations[99] == "DELETED"
        assert dict(connection.execute("SELECT slug,chapter_identity_provenance FROM novels").fetchall()) == {"legacy": "LEGACY_UNKNOWN", "empty": "LEGACY_UNKNOWN"}
        fresh_id = uuid.uuid4()
        connection.execute("INSERT INTO novels(id,slug) VALUES (%s,'fresh')", (fresh_id,))
        connection.execute(migration.sql)
        assert connection.execute("SELECT chapter_identity_provenance FROM novels WHERE id=%s", (fresh_id,)).fetchone()[0] == "ALLOCATED"
        assert connection.execute("SELECT * FROM chapter_versions ORDER BY id").fetchall() == before_history
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.postgres_backend_only
def test_real_postgres_deleted_uuid_cannot_be_reissued(monkeypatch):
    url = os.environ.get("TEST_POSTGRES_DATABASE_URL")
    if not url:
        pytest.skip("NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is not configured")
    from sqlalchemy import select, text
    from app.repositories.postgres.session import Database
    from app.repositories.postgres.novel import PostgresNovelRepository
    from app.repositories.postgres.chapter import PostgresChapterRepository
    from app.repositories.postgres.models import ChapterIdentityModel, ChapterModel
    database = Database(url)
    novels = PostgresNovelRepository(database); chapters = PostgresChapterRepository(database)
    nid = novels.create({"title": "Synthetic UUID reservation " + str(uuid.uuid4())})["id"]
    try:
        with database.session() as session:
            session.execute(text("UPDATE novels SET chapter_identity_provenance='LEGACY_UNKNOWN' WHERE slug=:slug"), {"slug": nid})
        old = chapters.create(nid, {"title": "Old UUID"})
        old_uuid = uuid.UUID(old["id"].rsplit(":~", 1)[1])
        chapters.delete(old["id"])
        monkeypatch.setattr("app.repositories.postgres.chapter.uuid.uuid4", lambda: old_uuid)
        with pytest.raises(FileExistsError):
            chapters.create(nid, {"title": "Never another generation"})
        with database.session() as session:
            reservation = session.scalar(select(ChapterIdentityModel).where(ChapterIdentityModel.chapter_id == old_uuid))
            assert reservation.state == "DELETED"
            assert reservation.public_token == "~" + str(old_uuid)
            assert session.get(ChapterModel, old_uuid) is None
        with pytest.raises(FileNotFoundError):
            chapters.get(old["id"])
    finally:
        novels.delete(nid)
        database.engine.dispose()


@pytest.mark.postgres_backend_only
def test_real_postgres_reservation_public_token_mismatch_blocks_current_owner():
    url = os.environ.get("TEST_POSTGRES_DATABASE_URL")
    if not url:
        pytest.skip("NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is not configured")
    from sqlalchemy import select
    from app.document import markdown_to_document
    from app.repositories.postgres.session import Database
    from app.repositories.postgres.novel import PostgresNovelRepository
    from app.repositories.postgres.chapter import PostgresChapterRepository
    from app.repositories.postgres.models import ChapterIdentityModel, ChapterModel
    database = Database(url)
    novels = PostgresNovelRepository(database); chapters = PostgresChapterRepository(database)
    nid = novels.create({"title": "Synthetic binding " + str(uuid.uuid4())})["id"]
    try:
        created = chapters.create(nid, {"title": "KEEP_BODY"})
        with database.session() as session:
            # Identify the disposable project's exact owner, never another row.
            from app.repositories.postgres.common import novel_or_raise
            novel = novel_or_raise(session, nid)
            reservation = session.get(ChapterIdentityModel, (novel.id, created["number"]))
            original_uuid = reservation.chapter_id
            reservation.public_token = "~" + str(uuid.uuid4())
        with pytest.raises(FileNotFoundError, match="IDENTITY_AMBIGUOUS"):
            chapters.get(created["id"])
        with pytest.raises(FileNotFoundError, match="IDENTITY_AMBIGUOUS"):
            chapters.save(created["id"], markdown_to_document("WRONG_OWNER"), 1)
        with database.session() as session:
            original = session.get(ChapterModel, original_uuid)
            assert original.title == "KEEP_BODY" and original.version == 1
    finally:
        novels.delete(nid)
        database.engine.dispose()
