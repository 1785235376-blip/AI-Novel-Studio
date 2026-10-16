"""Owned synthetic PostgreSQL observation; never substitutes a fake Session."""
from __future__ import annotations
import json, os, platform, sys, traceback, uuid
from pathlib import Path
sys.path.insert(0, os.environ['AUDIT_SOURCE_ROOT'])
from sqlalchemy import select, text
from app.repositories.postgres import Database, PostgresNovelRepository, PostgresChapterRepository
from app.repositories.postgres.models import ChapterModel

def observe():
    database = Database(os.environ['DATABASE_URL'])
    database.require_healthy()
    with database.session() as session:
        version = session.scalar(text('SELECT version()'))
        version_num = int(session.scalar(text('SHOW server_version_num')))
    assert 160000 <= version_num < 170000, version
    novels, chapters = PostgresNovelRepository(database), PostgresChapterRepository(database)
    nid = 'a43-real-pg-' + uuid.uuid4().hex
    novels.create({'id': nid, 'title': 'A43 disposable synthetic probe'})
    def rows():
        with database.session() as session:
            return [{'uuid':str(r.id),'number':r.chapter_number,'version':r.version,'title':r.title} for r in session.scalars(select(ChapterModel).where(ChapterModel.novel_id == uuid.UUID(novel_uuid))).all()]
    try:
        a = chapters.create(nid, {'title':'A', 'content':'A-MANUSCRIPT-SYNTHETIC'})
        b = chapters.create(nid, {'title':'B', 'content':'B-MANUSCRIPT-SYNTHETIC'})
        from app.repositories.postgres.common import chapter_or_raise
        with database.session() as session:
            novel, row = chapter_or_raise(session,a['id']); novel_uuid = str(novel.id)
        before = chapters.get(a['id']); before_rows = rows()
        error = None; order = None
        try:
            order = chapters.move(a['id'],'down')
        except Exception as exc:
            error = {'type':type(exc).__name__,'message':str(exc)}
        after = chapters.get(a['id']); after_rows = rows()
        same_id_version_different_document = before['id'] == after['id'] and before['version'] == after['version'] and before['document'] != after['document']
        old_save = None
        if error is None:
            old_save = chapters.save(a['id'], before['document'], before['version'])
        result = {'layer':'REAL_POSTGRESQL_16_ORIGINAL_REPOSITORY_SYNTHETIC_MANUSCRIPT', 'python':platform.python_version(), 'server_version':version,'server_version_num':version_num,'before':before,'other':b,'before_rows':before_rows,'returned_order':order,'move_exception':error,'after':after,'after_rows':after_rows,'same_id_and_version_now_different_document':same_id_version_different_document,'old_id_version_save':old_save,'after_old_save_rows':rows()}
        return result
    finally:
        novels.delete(nid)
        database.engine.dispose()

if __name__ == '__main__':
    result = observe()
    destination = Path(os.environ['A43_PG_OBSERVATION'])
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
