"""Original idle/read-only queue behavior and zero-write observer regressions."""
import json
from pathlib import Path
import pytest
from app.services import export_job_service as module

CONTEXT = {'mode': 'local', 'novel_id': 'book', 'workspace_id': None,
           'storyline_id': None, 'branch_id': None, 'actor_id': 'local-author'}


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
            for p in root.rglob('*')}


def service(root):
    return module.ExportJobService(root, lambda *_: pytest.fail('no exporter permitted'))


@pytest.mark.parametrize('kind', ['fresh', 'legacy', 'managed', 'corrupt'])
def test_idle_startup_and_observation_need_no_writer_lock(tmp_path, monkeypatch, kind):
    row = {'id': 'j', 'novel_id': 'book', 'format': 'txt', 'status': 'succeeded',
           'permission_context': CONTEXT}
    if kind == 'managed':
        owner = service(tmp_path)
        try:
            owner._write({'j': row})
        finally:
            owner._pool.shutdown(wait=True)
    elif kind == 'legacy':
        (tmp_path / 'export_jobs.json').write_text(json.dumps({'j': row}))
    elif kind == 'corrupt':
        (tmp_path / 'export_jobs.json').write_text('{broken')
    monkeypatch.setattr(module, 'workspace_mutation', lambda *_: pytest.fail('read attempted writer lock'))
    owner = service(tmp_path)
    try:
        before = snapshot(tmp_path)
        if kind in {'managed', 'legacy'}:
            assert owner.get('j')['id'] == 'j'
            assert owner.list('book', permission_context=CONTEXT)['items'][0]['id'] == 'j'
        if kind == 'managed':
            observed = owner.binding_observation(['j'])
            assert owner.revalidate_binding(['j'], observed)
        else:
            with pytest.raises(ValueError, match='EXPORT_BINDING_UNSUPPORTED'):
                owner.binding_observation(['j'])
        assert snapshot(tmp_path) == before
    finally:
        owner._pool.shutdown(wait=True)


def test_original_json_key_and_tuple_coercions_remain_supported(tmp_path):
    owner = service(tmp_path)
    try:
        row = {'id': 'j', 'status': 'succeeded', 'payload': {1: ('a',), 'two': 'b'}}
        owner._write({'j': row})
        before = owner.binding_observation(['j'])
        owner._write({'j': row})
        assert owner.binding_observation(['j']) == before
        row['payload'][1] = ('changed',)
        owner._write({'j': row})
        assert owner.binding_observation(['j']) != before
    finally:
        owner._pool.shutdown(wait=True)
