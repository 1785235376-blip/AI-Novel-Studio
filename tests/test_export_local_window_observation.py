from copy import deepcopy
import json
import pytest
from app.services.export_job_service import ExportJobService

LOCAL={'mode':'local','novel_id':'book'}

@pytest.fixture
def owner(tmp_path, monkeypatch):
    monkeypatch.setattr(ExportJobService,'_submit',lambda *a:None)
    o=ExportJobService(tmp_path,lambda *a:pytest.fail('no execution'))
    yield o
    o._pool.shutdown(wait=True)


def seed(o,count=3):
    o._write({f'j-{i:03}':{'id':f'j-{i:03}','novel_id':'book','format':'txt','status':'queued',
             'permission_context':deepcopy(LOCAL),'created_at':f'{i:05}','snapshot':{'private':'secret'}}
              for i in range(count)})


def test_matches_original_empty_and_capped_window(owner):
    for count in (0,3,101):
        seed(owner,count)
        v=owner.local_task_observation('book')
        actual=owner.list('book',permission_context=LOCAL,limit=100,offset=0)
        assert v['rows']==actual['items']
        assert v['source_more']==(actual['next_offset'] is not None)
        assert set(v['row_lifecycles'])=={r['id'] for r in v['rows']}
        assert all('snapshot' not in row for row in v['rows'])
        assert 'secret' not in json.dumps(v['rows'])


def test_foreign_actor_scope_and_hidden_tail_do_not_invalidate(owner):
    seed(owner,101);v=owner.local_task_observation('book');d=owner._read()
    d['j-000']['snapshot']={'private':'changed tail'}
    d['foreign']={'id':'foreign','novel_id':'book','status':'queued','permission_context':{**LOCAL,'actor_id':'other'}}
    owner._write(d)
    assert owner.local_task_observation('book')==v


def test_selected_private_aba_and_document_recreation_change_binding(owner):
    seed(owner);v=owner.local_task_observation('book');d=owner._read();original=deepcopy(d)
    d['j-001']['snapshot']={'private':'changed'};owner._write(d);owner._write(original)
    now=owner.local_task_observation('book');assert now['rows']==v['rows'];assert now['row_lifecycles']!=v['row_lifecycles']
    owner.path.unlink();owner._write(original)
    assert owner.local_task_observation('book')['document_incarnation']!=v['document_incarnation']


def test_legacy_and_missing_zero_write_refusal(owner):
    for legacy in (False,True):
        if legacy:owner.path.write_text('{}')
        before=owner.path.read_bytes() if owner.path.exists() else None
        with pytest.raises(ValueError):owner.local_task_observation('book')
        assert (owner.path.read_bytes() if owner.path.exists() else None)==before


def test_observation_no_writer_coordinator(owner,monkeypatch):
    seed(owner);from app.services import export_job_service as module
    monkeypatch.setattr(module,'workspace_mutation',lambda *a:pytest.fail('read must not write'))
    before=owner.path.read_bytes();owner.local_task_observation('book');assert owner.path.read_bytes()==before
