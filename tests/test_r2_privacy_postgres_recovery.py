"""Real PostgreSQL upgrade, process reopen, File import and new-instance recovery.

Only runs with the explicit disposable TEST_POSTGRES_DATABASE_URL opt-in. Every
created database has a random test-owned name; no pre-existing database is dropped.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest
import psycopg
from psycopg import sql

from app.backup_restore import BackupError, backup_directory, restore_directory
from app.migrate_file_to_postgres import migrate
from app.packaging.postgres_migrations import PackagedPostgresMigrationRunner
from app.privacy import cloud_safe_context
from app.repositories.postgres.novel import PostgresNovelRepository
from app.repositories.postgres.session import Database
from app.repository import FileRepository

ROOT = Path(__file__).resolve().parents[1]
TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
pytestmark = [pytest.mark.postgres_backend_only, pytest.mark.skipif(not TEST_URL, reason="NOT_RUN: disposable PostgreSQL not configured")]


def with_database(url, name):
    parsed = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1))
    return urlunsplit(parsed._replace(path="/"+name))


@pytest.fixture
def isolated_databases():
    names = []
    admin_url = with_database(TEST_URL,"postgres")
    def create(*, initialize=True):
        name = "r2_privacy_" + uuid.uuid4().hex
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        names.append(name)
        url = with_database(TEST_URL,name)
        if initialize:
            with psycopg.connect(url,autocommit=True) as connection:
                for path in sorted((ROOT/"database/migrations").glob("*.sql")):
                    if int(path.name.split("_",1)[0]) <= 16:
                        connection.execute(path.read_text())
        return url
    yield create, names
    with psycopg.connect(admin_url,autocommit=True) as connection:
        for name in names:
            # These names were created by this fixture or the restore test only.
            assert name.startswith("r2_privacy_")
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def run_migrations(url):
    with psycopg.connect(url,autocommit=True) as connection:
        runner = PackagedPostgresMigrationRunner(migrations_path=ROOT/"database/migrations", execute_sql=connection.execute)
        runner.run()
        runner.run()  # checksum-guarded idempotence


def database_digest(url):
    result = {}
    with psycopg.connect(url) as connection:
        tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
        for (name,) in tables:
            rows = connection.execute(sql.SQL("SELECT to_jsonb(t) FROM {} t").format(sql.Identifier(name))).fetchall()
            canonical = sorted(json.dumps(row[0],sort_keys=True,separators=(",",":"),default=str) for row in rows)
            result[name] = {"count":len(rows), "sha256":hashlib.sha256("\n".join(canonical).encode()).hexdigest()}
    return result


def test_upgrade_from_legacy_marks_unknown_and_survives_fresh_process(isolated_databases):
    create,_ = isolated_databases; url=create()
    with psycopg.connect(url) as connection:
        nid=connection.execute("INSERT INTO novels(slug,title) VALUES ('legacy','Synthetic privacy') RETURNING id").fetchone()[0]
        connection.execute("INSERT INTO foreshadowing(novel_id,title,details) VALUES (%s,'UNKNOWN_CANARY','{}')",(nid,))
        connection.execute("INSERT INTO foreshadowing(novel_id,title,details) VALUES (%s,'REDACT_CANARY','{\"privacy_level\":\"REDACT_BEFORE_CLOUD\"}')",(nid,))
        connection.execute("INSERT INTO timeline_events(novel_id,title,event_time,sequence,privacy) VALUES (%s,'LOCAL_CANARY','now',1,'LOCAL_ONLY')",(nid,))
        connection.execute("INSERT INTO canon_entries(novel_id,entity_type,fact_key,fact_value,privacy,source) VALUES (%s,'story','fact','{\"fact\":\"CANON_CANARY\",\"privacy_level\":\"CLOUD_ALLOWED\"}','LOCAL_ONLY','test')",(nid,))
    run_migrations(url)
    db=Database(url); repository=PostgresNovelRepository(db)
    hints=repository.get_data_set('legacy','foreshadowing')
    assert {x['privacy_level'] for x in hints}=={'LOCAL_ONLY','REDACT_BEFORE_CLOUD'}
    assert next(x for x in hints if x['title']=='UNKNOWN_CANARY')['privacy_status']=='UNKNOWN'
    for name in ('foreshadowing','timeline','canon'):
        assert '_CANARY' not in json.dumps(cloud_safe_context(repository.get_data_set('legacy',name))[0])
    # DB constraint prevents future unlabelled/invalid foreshadowing rows.
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(url) as connection:
            connection.execute("INSERT INTO foreshadowing(novel_id,title,details) VALUES (%s,'bad','{}')",(nid,))
    code = '''
import json, os
from app.repositories.postgres.session import Database
from app.repositories.postgres.novel import PostgresNovelRepository
from app.privacy import cloud_safe_context
r=PostgresNovelRepository(Database(os.environ['R2_REOPEN_DB']))
for name in ('foreshadowing','timeline','canon'):
    rows=r.get_data_set('legacy',name)
    assert all(x.get('privacy_level') != 'CLOUD_ALLOWED' for x in rows)
    assert '_CANARY' not in json.dumps(cloud_safe_context(rows)[0])
print('fresh process policy check passed')
'''
    result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'R2_REOPEN_DB':url},capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    db.engine.dispose()


def test_file_migration_repeat_cannot_downgrade_and_updates_resolve_source_ids(tmp_path,isolated_databases):
    create,_=isolated_databases;url=create();run_migrations(url)
    file=FileRepository(tmp_path/'source');file.create_novel({'id':'migration','title':'Synthetic migration'})
    root=file.novels/'migration'
    for path,rows in (
        ('timeline/events.json',[{'id':'event','title':'LOCAL_CANARY','sequence':1,'privacy_level':'LOCAL_ONLY'}]),
        ('foreshadowing.json',[{'id':'hint','title':'REDACT_CANARY','privacy_level':'REDACT_BEFORE_CLOUD'}]),
        ('characters/characters.json',[{'id':'hero','name':'Hero'}]),
    ):(root/path).write_text(json.dumps(rows))
    first=migrate(file.data,url,tmp_path/'migration-first.json')
    assert not first['failed'] and not first['conflicts']
    again=migrate(file.data,url,tmp_path/'migration-again.json')
    assert not again['updated'] and not again['imported']
    database=Database(url);repository=PostgresNovelRepository(database)
    assert repository.get_data_set('migration','characters')[0]['privacy_level']=='LOCAL_ONLY'
    repository.upsert_timeline_event('migration','event',{'title':'updated'})
    repository.upsert_foreshadowing('migration','hint',{'title':'updated'})
    assert len(repository.get_data_set('migration','timeline'))==1
    assert len(repository.get_data_set('migration','foreshadowing'))==1
    (root/'timeline/events.json').write_text(json.dumps([{'id':'event','title':'loose','sequence':1,'privacy_level':'CLOUD_ALLOWED'}]))
    (root/'foreshadowing.json').write_text(json.dumps([{'id':'hint','title':'loose','privacy_level':'CLOUD_ALLOWED'}]))
    migrate(file.data,url,tmp_path/'migration-loose.json')
    assert repository.get_data_set('migration','timeline')[0]['privacy_level']=='LOCAL_ONLY'
    assert repository.get_data_set('migration','foreshadowing')[0]['privacy_level']=='REDACT_BEFORE_CLOUD'
    database.engine.dispose()


def test_dump_restore_into_new_database_matches_every_table_and_sidecar(tmp_path,isolated_databases):
    if not shutil.which('pg_dump') or not shutil.which('pg_restore'):
        pytest.skip('NOT_RUN: PostgreSQL dump/restore client binaries missing')
    create,names=isolated_databases;url=create();run_migrations(url)
    database=Database(url);repository=PostgresNovelRepository(database)
    repository.create({'id':'recover','title':'Synthetic recovery'})
    repository.upsert_timeline_event('recover','event',{'title':'LOCAL_CANARY','privacy_level':'LOCAL_ONLY'})
    repository.upsert_foreshadowing('recover','hint',{'title':'REDACT_CANARY','privacy_level':'REDACT_BEFORE_CLOUD'})
    source=tmp_path/'source';(source/'novel_data/jobs').mkdir(parents=True)
    sidecar=b'{"id":"job","snapshot_id":"snapshot","project_id":"recover"}'
    (source/'novel_data/jobs/job.json').write_bytes(sidecar)
    saved=tmp_path/'backup';backup_directory(source,saved,app_version='0.7.0',offline_confirmed=True,database_url=url)
    new_name='r2_privacy_'+uuid.uuid4().hex;names.append(new_name);new_url=with_database(url,new_name)
    restored=tmp_path/'recovered';restore_directory(saved,restored,database_url=new_url)
    assert (restored/'novel_data/jobs/job.json').read_bytes()==sidecar
    assert database_digest(url)==database_digest(new_url)
    with pytest.raises(BackupError,match='already exists'):
        restore_directory(saved,tmp_path/'another-target',database_url=new_url)
    assert (tmp_path/'another-target/.restore-incomplete').exists()
    database.engine.dispose()
