import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_independent import record, Session, DB, pg_setup
from app.repositories.postgres.generation import PostgresGenerationRepository
from app.repositories.generation_repository import GenerationProjectIdentityError
from unittest.mock import patch
from types import SimpleNamespace
from uuid import UUID,uuid4
from copy import deepcopy
item=record('postgres');item['chapter_id']='other-project:1';item['ordinary_project_binding']['chapter_id']=item['chapter_id']
owner=SimpleNamespace(id=UUID(item['ordinary_project_binding']['project_incarnation'][9:]))
other=SimpleNamespace(id=uuid4());chapter=SimpleNamespace(id=uuid4(),novel_id=other.id)
def attempt(value, resolved_chapter):
    s=Session(None,owner);s.add=lambda row:setattr(s,'row',row)
    repo=PostgresGenerationRepository(DB(s))
    def resolve(session, cid):
        assert session is s
        assert s.statements and 'FROM novels' in s.statements[0] if 'ordinary_project_binding' in value else True
        return other,resolved_chapter
    with patch('app.repositories.postgres.generation.chapter_or_raise',side_effect=resolve),patch('app.repositories.postgres.generation.novel_or_raise',return_value=owner):
        try:repo.save(value)
        except GenerationProjectIdentityError as exc:
            assert str(exc)=='GENERATION_ORDINARY_CHAPTER_OWNER_MISMATCH'
            assert not s.flushed and s.row is None
            return False
    assert s.flushed and s.row.novel_id==owner.id and s.row.chapter_id==resolved_chapter.id
    return True
assert attempt(item,chapter) is False
print('ordinary_cross_project_save_refused_before_add_flush: PASS')
matched=SimpleNamespace(id=uuid4(),novel_id=owner.id)
assert attempt(item,matched) is True
print('ordinary_same_project_save_same_session: PASS')
legacy=deepcopy(item);del legacy['ordinary_project_binding']
assert attempt(legacy,chapter) is True
print('legacy_cross_project_behavior_unchanged: PASS')
item,row,s,repo=pg_setup();row.chapter_id=uuid4()
assert repo.get(item['id'])['chapter_id'] is None and len(repo.load_all())==1
print('read_side_chapter_reconciliation_still_out_of_scope: CONFIRMED')
