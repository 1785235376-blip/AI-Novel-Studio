from copy import deepcopy
from app.experimental.imports import JOBS
import pytest
from test_taskcenter_mixed_external import rig,export_rig,mixed_rig,get
from test_taskcenter_mixed_external_cases import token,import_write,export_write


@pytest.mark.parametrize('reader',['import','export'])
def test_source_feature_revocation_mid_original_read_is_not_ignored(mixed_rig,monkeypatch,reader):
    e=mixed_rig;t=token(e);owner=e.importer if reader=='import' else e.source;name='jobs' if reader=='import' else 'list';original=getattr(owner,name)
    def changed(*a,**kw):
        result=original(*a,**kw);monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2');return result
    monkeypatch.setattr(owner,name,changed);r=get(e,{'cursor':t})
    assert r.status_code==404,r.text
    assert 'items' not in r.json()


def test_original_reauthorization_cannot_be_replaced_with_local_observation(mixed_rig,monkeypatch):
    e=mixed_rig;original=e.importer.jobs
    def changed(*a,**kw):
        result=original(*a,**kw);object.__setattr__(e.rig.settings,'enable_collaboration_runtime',True);return result
    monkeypatch.setattr(e.importer,'jobs',changed);r=get(e)
    assert r.status_code==400,r.text
    assert r.json()['detail']['code']=='BRANCH_SCOPE_REQUIRED'
    assert 'items' not in r.json()


def test_project_recreated_inside_original_reader_restarts(mixed_rig,monkeypatch):
    e=mixed_rig;t=token(e);original=e.source.list
    def changed(*a,**kw):
        result=original(*a,**kw)
        (e.rig.root/'novels'/e.rig.nid/'creative_project_v2.json').unlink();e.rig.workspace.creative.store.incarnation(e.rig.nid)
        return result
    monkeypatch.setattr(e.source,'list',changed);r=get(e,{'cursor':t});assert r.status_code==409,r.text


@pytest.mark.parametrize('mutation',['import_aba','export_aba','project_recreate','source_replace'])
def test_final_engine_hook_cannot_emit_stale_mixed_page(mixed_rig,monkeypatch,mutation):
    from copy import copy
    e=mixed_rig;t=token(e);engine=e.api.taskcenter_cursor_adapter.mixed_adapter.engine;original=engine.page
    def changed(*a,**kw):
        result=original(*a,**kw)
        if mutation=='import_aba':
            rid=e.imports[0];row=e.store.read(e.rig.nid,e.rig.scope)['collections'][JOBS][rid]
            import_write(e,lambda rows:rows[rid].update(prompt='private-after-engine'))
            import_write(e,lambda rows:rows.__setitem__(rid,row))
        elif mutation=='export_aba':
            rid=e.ids[0];row=e.source._read()[rid]
            export_write(e,lambda rows:rows[rid].update(snapshot={'private':'private-after-engine'}))
            export_write(e,lambda rows:rows.__setitem__(rid,row))
        elif mutation=='project_recreate':
            (e.rig.root/'novels'/e.rig.nid/'creative_project_v2.json').unlink();e.rig.workspace.creative.store.incarnation(e.rig.nid)
        else:monkeypatch.setattr(e.legacy,'export_job_service',copy(e.source))
        return result
    monkeypatch.setattr(engine,'page',changed);r=get(e,{'cursor':t})
    assert r.status_code==409,r.text
    assert 'private-after-engine' not in r.text and 'items' not in r.json()
